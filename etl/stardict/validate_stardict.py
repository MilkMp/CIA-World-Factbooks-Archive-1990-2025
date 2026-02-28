#!/usr/bin/env python3
"""Deep validation of all StarDict dictionaries -- 16 tests."""

import os
import gzip
import struct
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
STARDICT_DIR = os.path.join(PROJECT_ROOT, "data", "stardict")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "factbook_field_values.db")


def get_entries(dict_dir):
    idx_path = os.path.join(STARDICT_DIR, dict_dir, dict_dir + ".idx")
    dz_path = os.path.join(STARDICT_DIR, dict_dir, dict_dir + ".dict.dz")
    with open(idx_path, "rb") as f:
        idx_data = f.read()
    with gzip.open(dz_path, "rb") as f:
        dict_data = f.read()
    entries = {}
    i = 0
    while i < len(idx_data):
        np = idx_data.index(b"\x00", i)
        word = idx_data[i:np].decode("utf-8")
        offset, size = struct.unpack(">II", idx_data[np + 1 : np + 9])
        i = np + 9
        entries[word] = dict_data[offset : offset + size].decode(
            "utf-8", errors="replace"
        )
    return entries


def get_entry(dict_dir, country):
    entries = get_entries(dict_dir)
    return entries.get(country)


def get_synonyms(dict_dir):
    syn_path = os.path.join(STARDICT_DIR, dict_dir, dict_dir + ".syn")
    idx_path = os.path.join(STARDICT_DIR, dict_dir, dict_dir + ".idx")
    with open(idx_path, "rb") as f:
        idx_data = f.read()
    words = []
    i = 0
    while i < len(idx_data):
        np = idx_data.index(b"\x00", i)
        words.append(idx_data[i:np].decode("utf-8"))
        i = np + 9
    with open(syn_path, "rb") as f:
        syn_data = f.read()
    syns = {}
    i = 0
    while i < len(syn_data):
        np = syn_data.index(b"\x00", i)
        sw = syn_data[i:np].decode("utf-8")
        idx = struct.unpack(">I", syn_data[np + 1 : np + 5])[0]
        syns[sw] = words[idx] if idx < len(words) else "OUT_OF_RANGE"
        i = np + 5
    return syns


def main():
    dirs = sorted(os.listdir(STARDICT_DIR))
    conn = sqlite3.connect(DB_PATH)
    results = []

    print("=" * 70)
    print("STARDICT DEEP VALIDATION -- 16 TESTS")
    print("=" * 70)

    # ── T1: File presence ──────────────────────────────────────────────
    total = sum(
        1
        for d in dirs
        for ext in [".ifo", ".idx", ".dict.dz", ".syn"]
        if os.path.exists(os.path.join(STARDICT_DIR, d, d + ext))
    )
    t1 = total == 288
    results.append(("File presence (288 files)", t1))
    print(f"\n[T1]  File presence: {total}/288 -> {'PASS' if t1 else 'FAIL'}")

    # ── T2: No empty entries ───────────────────────────────────────────
    empty = 0
    for d in dirs:
        for name, content in get_entries(d).items():
            if len(content) < 10:
                empty += 1
    t2 = empty == 0
    results.append(("No empty entries", t2))
    print(f"[T2]  No empty entries: {empty} -> {'PASS' if t2 else 'FAIL'}")

    # ── T3: DB count match (using same join path as builder) ───────────
    mismatch = 0
    for year in range(1990, 2026):
        # Count using same join path as GENERAL_QUERY
        db_c = conn.execute(
            """SELECT COUNT(DISTINCT co.CountryID)
               FROM Countries co
               JOIN MasterCountries mc ON co.MasterCountryID = mc.MasterCountryID
               JOIN CountryCategories cc ON co.CountryID = cc.CountryID
               JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
                                     AND cf.CountryID = co.CountryID
               WHERE co.Year = ?""",
            (year,),
        ).fetchone()[0]
        ifo = os.path.join(
            STARDICT_DIR,
            f"cia-factbook-{year}-general",
            f"cia-factbook-{year}-general.ifo",
        )
        sd_c = 0
        with open(ifo) as f:
            for line in f:
                if line.startswith("wordcount="):
                    sd_c = int(line.split("=")[1])
        # Allow for dedup (Serbia 2008: 2 CountryIDs -> 1 entry)
        if sd_c > db_c or sd_c < db_c - 1:
            mismatch += 1
            print(f"    MISMATCH: {year} DB={db_c} SD={sd_c}")
    t3 = mismatch == 0
    results.append(("DB count match (36 years)", t3))
    print(f"[T3]  DB count match: {mismatch}/36 mismatches -> {'PASS' if t3 else 'FAIL'}")

    # ── T4: Every entry has <h3> ───────────────────────────────────────
    missing_h3 = 0
    for d in dirs:
        for name, content in get_entries(d).items():
            if "<h3>" not in content:
                missing_h3 += 1
    t4 = missing_h3 == 0
    results.append(("Every entry has <h3>", t4))
    print(f"[T4]  Every entry has <h3>: {missing_h3} missing -> {'PASS' if t4 else 'FAIL'}")

    # ── T5: Gen/Struct country lists match per year ────────────────────
    list_mm = 0
    for year in range(1990, 2026):
        g = set(get_entries(f"cia-factbook-{year}-general").keys())
        s = set(get_entries(f"cia-factbook-{year}-structured").keys())
        if g != s:
            list_mm += 1
    t5 = list_mm == 0
    results.append(("Gen/Struct lists match", t5))
    print(f"[T5]  Gen/Struct lists match: {list_mm}/36 mismatches -> {'PASS' if t5 else 'FAIL'}")

    # ── T6: No duplicate entries ───────────────────────────────────────
    dup_count = 0
    for d in dirs:
        idx_path = os.path.join(STARDICT_DIR, d, d + ".idx")
        with open(idx_path, "rb") as f:
            idx_data = f.read()
        names = []
        i = 0
        while i < len(idx_data):
            np = idx_data.index(b"\x00", i)
            names.append(idx_data[i:np].decode("utf-8"))
            i = np + 9
        dup_count += len(names) - len(set(names))
    t6 = dup_count == 0
    results.append(("No duplicate entries", t6))
    print(f"[T6]  No duplicates: {dup_count} -> {'PASS' if t6 else 'FAIL'}")

    # ── T7: Min entry size >= 50 bytes ─────────────────────────────────
    small = 0
    for d in dirs:
        idx_path = os.path.join(STARDICT_DIR, d, d + ".idx")
        with open(idx_path, "rb") as f:
            idx_data = f.read()
        i = 0
        while i < len(idx_data):
            np = idx_data.index(b"\x00", i)
            _, size = struct.unpack(">II", idx_data[np + 1 : np + 9])
            i = np + 9
            if size < 50:
                small += 1
    t7 = small == 0
    results.append(("Min entry >= 50 bytes", t7))
    print(f"[T7]  Min entry size: {small} under 50 bytes -> {'PASS' if t7 else 'FAIL'}")

    # ── T8: ISO synonym lookup (15 codes) ──────────────────────────────
    syns = get_synonyms("cia-factbook-2025-general")
    iso_checks = [
        ("US", "United States"), ("CN", "China"), ("AU", "Australia"),
        ("RU", "Russia"), ("BR", "Brazil"), ("IN", "India"),
        ("JP", "Japan"), ("DE", "Germany"), ("FR", "France"),
        ("GB", "United Kingdom"), ("MX", "Mexico"), ("NG", "Nigeria"),
        ("CH", "Switzerland"), ("KR", "Korea, South"), ("ES", "Spain"),
    ]
    syn_passed = sum(1 for c, e in iso_checks if syns.get(c) == e)
    t8 = syn_passed == 15
    results.append(("ISO synonyms (15 codes)", t8))
    print(f"[T8]  ISO synonyms: {syn_passed}/15 -> {'PASS' if t8 else 'FAIL'}")

    # ── T9: HTML tag balance (11 dicts across eras) ────────────────────
    t9 = True
    for d in [
        "cia-factbook-1990-general", "cia-factbook-1991-structured",
        "cia-factbook-1992-general", "cia-factbook-1993-structured",
        "cia-factbook-1995-general", "cia-factbook-2001-structured",
        "cia-factbook-2005-general", "cia-factbook-2010-structured",
        "cia-factbook-2015-general", "cia-factbook-2021-structured",
        "cia-factbook-2025-general",
    ]:
        with gzip.open(
            os.path.join(STARDICT_DIR, d, d + ".dict.dz"), "rb"
        ) as f:
            c = f.read().decode("utf-8", errors="replace")
        if c.count("<h3>") != c.count("</h3>") or c.count("<b>") != c.count("</b>"):
            t9 = False
    results.append(("HTML tag balance (11 dicts)", t9))
    print(f"[T9]  HTML tag balance: {'PASS' if t9 else 'FAIL'}")

    # ── T10: Gen vs Struct content differs ─────────────────────────────
    t10 = True
    for y in [1990, 1995, 2000, 2005, 2010, 2015, 2020, 2025]:
        gd = f"cia-factbook-{y}-general"
        sd = f"cia-factbook-{y}-structured"
        with gzip.open(os.path.join(STARDICT_DIR, gd, gd + ".dict.dz"), "rb") as f:
            g = f.read()
        with gzip.open(os.path.join(STARDICT_DIR, sd, sd + ".dict.dz"), "rb") as f:
            s = f.read()
        if g == s:
            t10 = False
    results.append(("Gen/Struct content differs", t10))
    print(f"[T10] Gen/Struct differs: {'PASS' if t10 else 'FAIL'}")

    # ── T11: 50 ground truth checks ────────────────────────────────────
    checks = [
        (2025, "United States", "general", "9,833,517"),
        (2025, "United States", "structured", "9,147,593"),
        (2025, "United States", "structured", "685,924"),
        (2025, "United States", "general", "338,016,259"),
        (2025, "China", "general", "9,596,960"),
        (2025, "China", "general", "Beijing"),
        (2025, "Russia", "general", "17,098,242"),
        (2025, "India", "general", "3,287,263"),
        (2025, "Brazil", "general", "8,515,770"),
        (2025, "Australia", "general", "7,741,220"),
        (2025, "Japan", "general", "Tokyo"),
        (2025, "Germany", "general", "Berlin"),
        (2025, "France", "general", "Paris"),
        (2025, "United Kingdom", "general", "London"),
        (1990, "Soviet Union", "general", "Moscow"),
        (1990, "Yugoslavia", "general", "Belgrade"),
        (1990, "German Democratic Republic", "general", "Berlin"),
        (1990, "Germany, Federal Republic of", "general", "Bonn"),
        (2000, "Japan", "structured", "male"),
        (2010, "Nigeria", "general", "Abuja"),
        (2015, "Mexico", "general", "Mexico City"),
        (2025, "United States", "structured", "total_population"),
        (2025, "United States", "structured", "female"),
        (2025, "Canada", "general", "Ottawa"),
        (2025, "Mexico", "general", "Mexico City"),
        (2025, "South Africa", "general", "Pretoria"),
        (2025, "Egypt", "general", "Cairo"),
        (2025, "Kenya", "general", "Nairobi"),
        (2025, "Argentina", "general", "Buenos Aires"),
        (2025, "Colombia", "general", "Bogota"),
        (2025, "Peru", "general", "Lima"),
        (2025, "Thailand", "general", "Bangkok"),
        (2025, "Indonesia", "general", "Jakarta"),
        (2025, "Philippines", "general", "Manila"),
        (2025, "Vietnam", "general", "Hanoi"),
        (2025, "Turkey (Turkiye)", "general", "Ankara"),
        (2025, "Iran", "general", "Tehran"),
        (2025, "Canada", "general", "9,984,670"),
        (2025, "Argentina", "general", "2,780,400"),
        (2025, "Mexico", "general", "1,964,375"),
        (2025, "Indonesia", "general", "1,904,569"),
        (2000, "United States", "general", "Washington"),
        (2000, "Russia", "general", "Moscow"),
        (2000, "China", "general", "Beijing"),
        (2000, "Brazil", "general", "Brasilia"),
        (2000, "India", "general", "New Delhi"),
        (2010, "United States", "general", "Washington"),
        (2010, "Japan", "general", "Tokyo"),
        (2010, "Germany", "general", "Berlin"),
        (2010, "Mexico", "general", "Mexico City"),
    ]
    gt_passed = 0
    gt_failed = 0
    for year, country, edition, value in checks:
        d = f"cia-factbook-{year}-{edition}"
        entry = get_entry(d, country)
        if entry and value in entry:
            gt_passed += 1
        else:
            gt_failed += 1
            print(f"    FAIL: {year} {country} ({edition}) -> \"{value}\"")
    t11 = gt_failed == 0
    results.append((f"Ground truth ({gt_passed}/{len(checks)})", t11))
    print(f"[T11] Ground truth: {gt_passed}/{len(checks)} -> {'PASS' if t11 else 'FAIL'}")

    # ── T12: Structured sub-fields (20 countries) ──────────────────────
    sub_checks = [
        "United States", "China", "Russia", "Japan", "Germany", "France",
        "United Kingdom", "Brazil", "India", "Australia", "Canada", "Mexico",
        "South Africa", "Nigeria", "Egypt", "Argentina", "Indonesia",
        "Thailand", "Iran", "Turkey (Turkiye)",
    ]
    sub_ok = 0
    for country in sub_checks:
        entry = get_entry("cia-factbook-2025-structured", country)
        if entry and ("total_population" in entry or "total population" in entry) \
                and "male" in entry and "female" in entry:
            sub_ok += 1
        else:
            print(f"    FAIL sub-fields: {country}")
    t12 = sub_ok == 20
    results.append(("Structured sub-fields (20)", t12))
    print(f"[T12] Structured sub-fields: {sub_ok}/20 -> {'PASS' if t12 else 'FAIL'}")

    # ── T13: Historical entity names ───────────────────────────────────
    hist_checks = [
        (1990, ["Soviet Union", "Yugoslavia", "German Democratic Republic",
                "Germany, Federal Republic of"]),
        (1991, ["Soviet Union", "Yugoslavia"]),
        (1992, ["Czechoslovakia", "Russia", "Serbia and Montenegro"]),
        (2025, ["Russia", "Czechia", "Serbia"]),
    ]
    t13 = True
    for year, expected in hist_checks:
        names = set(get_entries(f"cia-factbook-{year}-general").keys())
        for exp in expected:
            if exp not in names:
                t13 = False
                print(f"    FAIL: {year} missing \"{exp}\"")
    results.append(("Historical entity names", t13))
    print(f"[T13] Historical names: {'PASS' if t13 else 'FAIL'}")

    # ── T14: Encoding quality ──────────────────────────────────────────
    total_chars = 0
    total_repl = 0
    for d in dirs:
        with gzip.open(
            os.path.join(STARDICT_DIR, d, d + ".dict.dz"), "rb"
        ) as f:
            content = f.read().decode("utf-8", errors="replace")
        total_chars += len(content)
        total_repl += content.count("\ufffd")
    pct = (total_repl / total_chars * 100) if total_chars > 0 else 0
    t14 = pct < 0.001
    results.append(("Encoding quality (<0.001%)", t14))
    print(
        f"[T14] Encoding: {total_repl} bad / {total_chars:,} total "
        f"= {pct:.6f}% -> {'PASS' if t14 else 'FAIL'}"
    )

    # ── T15: Every DB country name in StarDict (allowing join gaps) ────
    name_errors = 0
    for year in range(1990, 2026):
        # Use the same join path as the builder
        db_names = set(
            r[0]
            for r in conn.execute(
                """SELECT DISTINCT co.Name
                   FROM Countries co
                   JOIN MasterCountries mc ON co.MasterCountryID = mc.MasterCountryID
                   JOIN CountryCategories cc ON co.CountryID = cc.CountryID
                   JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
                                         AND cf.CountryID = co.CountryID
                   WHERE co.Year = ?""",
                (year,),
            ).fetchall()
        )
        sd_names = set(get_entries(f"cia-factbook-{year}-general").keys())
        only_db = db_names - sd_names
        only_sd = sd_names - db_names
        # Allow for dedup (same name from 2 CountryIDs merges into 1)
        if only_sd:
            name_errors += len(only_sd)
            print(f"    {year} in SD only: {only_sd}")
        if only_db:
            name_errors += len(only_db)
            print(f"    {year} in DB only: {only_db}")
    t15 = name_errors == 0
    results.append(("All names match DB", t15))
    print(f"[T15] Name match: {name_errors} errors -> {'PASS' if t15 else 'FAIL'}")

    conn.close()

    # ── T16: Round-trip read via pyglossary ───────────────────────────
    t16 = True
    t16_errors = []
    try:
        from pyglossary.glossary_v2 import Glossary
        Glossary.init()

        for edition in ["general", "structured"]:
            dict_name = f"cia-factbook-2025-{edition}"
            ifo_path = os.path.join(
                STARDICT_DIR, dict_name, f"{dict_name}.ifo"
            )

            glos = Glossary()
            glos.directRead(ifo_path)

            # Read .ifo wordcount for comparison
            expected_count = 0
            with open(ifo_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("wordcount="):
                        expected_count = int(line.strip().split("=")[1])

            # Iterate all entries, collect by primary headword
            entry_map = {}
            entry_count = 0
            for entry in glos:
                words = entry.l_term  # list of headwords
                defi = entry.defi     # definition text
                fmt = entry.defiFormat  # should be "h"
                if words:
                    entry_map[words[0]] = (defi, fmt)
                    entry_count += 1

            # Check 1: entry count matches
            if entry_count != expected_count:
                t16 = False
                t16_errors.append(
                    f"{edition}: count {entry_count} != ifo {expected_count}"
                )

            # Check 2: specific entries exist with expected content
            spot_checks = [
                ("United States", "Washington"),
                ("China", "Beijing"),
                ("Australia", "Canberra"),
                ("Japan", "Tokyo"),
                ("United Kingdom", "London"),
            ]
            for country, expected_text in spot_checks:
                if country not in entry_map:
                    t16 = False
                    t16_errors.append(f"{edition}: {country} not found")
                else:
                    defi, fmt = entry_map[country]
                    if fmt != "h":
                        t16 = False
                        t16_errors.append(
                            f"{edition}: {country} format '{fmt}' != 'h'"
                        )
                    if expected_text not in defi:
                        t16 = False
                        t16_errors.append(
                            f"{edition}: {country} missing '{expected_text}'"
                        )
                    if "<h3>" not in defi:
                        t16 = False
                        t16_errors.append(
                            f"{edition}: {country} missing <h3> tags"
                        )

            glos.clear()

    except ImportError:
        t16 = False
        t16_errors.append("pyglossary not installed")
    except Exception as e:
        t16 = False
        t16_errors.append(f"error: {e}")

    for err in t16_errors:
        print(f"    FAIL: {err}")
    results.append(("Round-trip read (pyglossary)", t16))
    print(f"[T16] Round-trip read: {'PASS' if t16 else 'FAIL'}")

    # ── Summary ────────────────────────────────────────────────────────
    passed = sum(1 for _, r in results if r)
    print("\n" + "=" * 70)
    print(f"FINAL SCORE: {passed}/{len(results)} tests passed")
    for name, result in results:
        print(f"  {'PASS' if result else 'FAIL'}: {name}")
    status = "ALL TESTS PASS" if all(r for _, r in results) else "SOME TESTS FAILED"
    print(f"STATUS: {status}")
    print("=" * 70)
    return all(r for _, r in results)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
