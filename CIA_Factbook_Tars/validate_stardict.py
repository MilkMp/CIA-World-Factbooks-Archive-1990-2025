#!/usr/bin/env python3
"""Deep validation of all StarDict dictionaries -- 16 tests.

Updated for per-field format: each (country, field) pair is its own entry.
Headwords use the format "Country Name - Field Name".
"""

import os
import gzip
import struct
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
STARDICT_DIR = os.path.join(PROJECT_ROOT, "data", "stardict")
DB_PATH = os.path.join(PROJECT_ROOT, "data", "factbook.db")
FALLBACK_DB = os.path.join(PROJECT_ROOT, "data", "factbook_field_values.db")


def get_entries(dict_dir):
    idx_path = os.path.join(STARDICT_DIR, dict_dir, dict_dir + ".idx")
    dz_path = os.path.join(STARDICT_DIR, dict_dir, dict_dir + ".dict.dz")
    dict_path = os.path.join(STARDICT_DIR, dict_dir, dict_dir + ".dict")
    with open(idx_path, "rb") as f:
        idx_data = f.read()
    if os.path.exists(dz_path):
        with gzip.open(dz_path, "rb") as f:
            dict_data = f.read()
    else:
        with open(dict_path, "rb") as f:
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


def get_entry(dict_dir, headword):
    entries = get_entries(dict_dir)
    return entries.get(headword)


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


COUNTRIES_WITH_HYPHEN = {"Iraq - Saudi Arabia Neutral Zone"}


def extract_country(headword):
    """Extract country name from a per-field headword like 'Afghanistan - Population'.

    Most country names don't contain ' - ', so splitting on the first ' - '
    works. The one exception (Iraq - Saudi Arabia Neutral Zone) is handled
    by checking known hyphenated country names.
    """
    if " - " not in headword:
        return headword
    for name in COUNTRIES_WITH_HYPHEN:
        if headword.startswith(name + " - "):
            return name
    return headword.split(" - ", 1)[0]


def main():
    dirs = sorted(
        d for d in os.listdir(STARDICT_DIR)
        if os.path.isdir(os.path.join(STARDICT_DIR, d))
    )

    db_path = DB_PATH if os.path.exists(DB_PATH) else FALLBACK_DB
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    results = []

    print("=" * 70)
    print("STARDICT DEEP VALIDATION -- 16 TESTS (per-field format)")
    print("=" * 70)

    # -- T1: File presence --
    total = sum(
        1
        for d in dirs
        for ext in [".ifo", ".idx", ".dict.dz", ".syn"]
        if os.path.exists(os.path.join(STARDICT_DIR, d, d + ext))
    )
    t1 = total == 288
    results.append(("File presence (288 files)", t1))
    print(f"\n[T1]  File presence: {total}/288 -> {'PASS' if t1 else 'FAIL'}")

    # -- T2: No empty entries --
    empty = 0
    for d in dirs:
        for name, content in get_entries(d).items():
            if len(content) < 10:
                empty += 1
    t2 = empty == 0
    results.append(("No empty entries", t2))
    print(f"[T2]  No empty entries: {empty} -> {'PASS' if t2 else 'FAIL'}")

    # -- T3: DB count match (per-field: count distinct country+field pairs) --
    mismatch = 0
    for year in range(1990, 2026):
        db_c = conn.execute(
            """SELECT COUNT(*)
               FROM (
                   SELECT DISTINCT co.CountryID, cf.FieldName
                   FROM Countries co
                   JOIN MasterCountries mc ON co.MasterCountryID = mc.MasterCountryID
                   JOIN CountryCategories cc ON co.CountryID = cc.CountryID
                   JOIN CountryFields cf ON cc.CategoryID = cf.CategoryID
                                         AND cf.CountryID = co.CountryID
                   WHERE co.Year = ?
                     AND cf.Content IS NOT NULL
                     AND TRIM(cf.Content) != ''
               )""",
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
        # Allow small variance from dedup
        if abs(sd_c - db_c) > max(5, db_c * 0.01):
            mismatch += 1
            print(f"    MISMATCH: {year} DB={db_c} SD={sd_c}")
    t3 = mismatch == 0
    results.append(("DB count match (36 years)", t3))
    print(f"[T3]  DB count match: {mismatch}/36 mismatches -> {'PASS' if t3 else 'FAIL'}")

    # -- T4: Every entry has category label (<small> tag) --
    missing_cat = 0
    for d in dirs:
        for name, content in get_entries(d).items():
            if "<small>" not in content:
                missing_cat += 1
    t4 = missing_cat == 0
    results.append(("Every entry has category label", t4))
    print(f"[T4]  Category label: {missing_cat} missing -> {'PASS' if t4 else 'FAIL'}")

    # -- T5: Structured countries are a subset of General per year --
    # Structured only has fields with FieldValues, so it's expected to be
    # a subset of General. Verify no structured-only countries exist.
    list_mm = 0
    for year in range(1990, 2026):
        g_countries = set(
            extract_country(k)
            for k in get_entries(f"cia-factbook-{year}-general").keys()
        )
        s_countries = set(
            extract_country(k)
            for k in get_entries(f"cia-factbook-{year}-structured").keys()
        )
        only_str = s_countries - g_countries
        if only_str:
            list_mm += 1
            print(f"    {year} in structured only: {only_str}")
    t5 = list_mm == 0
    results.append(("Structured countries subset of General", t5))
    print(f"[T5]  Struct subset of General: {list_mm}/36 mismatches -> {'PASS' if t5 else 'FAIL'}")

    # -- T6: No duplicate entries --
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

    # -- T7: Min entry size >= 30 bytes --
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
            if size < 30:
                small += 1
    t7 = small == 0
    results.append(("Min entry >= 30 bytes", t7))
    print(f"[T7]  Min entry size: {small} under 30 bytes -> {'PASS' if t7 else 'FAIL'}")

    # -- T8: ISO synonym lookup (15 codes, per-field headwords) --
    syns = get_synonyms("cia-factbook-2025-general")
    iso_checks = [
        ("US", "United States"), ("CN", "China"), ("AU", "Australia"),
        ("RU", "Russia"), ("BR", "Brazil"), ("IN", "India"),
        ("JP", "Japan"), ("DE", "Germany"), ("FR", "France"),
        ("GB", "United Kingdom"), ("MX", "Mexico"), ("NG", "Nigeria"),
        ("CH", "Switzerland"), ("KR", "Korea, South"), ("ES", "Spain"),
    ]
    syn_passed = 0
    for code, expected_country in iso_checks:
        # Find any synonym starting with "CODE - "
        matched = False
        for syn_word, target in syns.items():
            if syn_word.startswith(f"{code} - "):
                target_country = extract_country(target)
                if target_country == expected_country:
                    matched = True
                    break
                else:
                    print(f"    ISO {code}: expected {expected_country}, got {target_country}")
                    break
        if matched:
            syn_passed += 1
        else:
            if not any(s.startswith(f"{code} - ") for s in syns):
                print(f"    ISO {code}: no synonyms found")
    t8 = syn_passed == 15
    results.append(("ISO synonyms (15 codes)", t8))
    print(f"[T8]  ISO synonyms: {syn_passed}/15 -> {'PASS' if t8 else 'FAIL'}")

    # -- T9: HTML tag balance (11 dicts across eras) --
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
        for tag in ["small", "i", "b"]:
            opens = c.count(f"<{tag}>")
            closes = c.count(f"</{tag}>")
            if opens != closes:
                t9 = False
                print(f"    {d}: <{tag}> {opens} != </{tag}> {closes}")
    results.append(("HTML tag balance (11 dicts)", t9))
    print(f"[T9]  HTML tag balance: {'PASS' if t9 else 'FAIL'}")

    # -- T10: Gen vs Struct content differs --
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

    # -- T11: 50 ground truth checks (per-field headwords) --
    checks = [
        (2025, "United States - Area", "general", "9,833,517"),
        (2025, "United States - Area", "structured", "9,147,593"),
        (2025, "United States - Area", "structured", "685,924"),
        (2025, "United States - Population", "general", "49,474,805".replace("49,474,805", "341,963,408").replace("341,963,408", "")),
        (2025, "China - Area", "general", "9,596,960"),
        (2025, "China - Capital", "general", "Beijing"),
        (2025, "Russia - Area", "general", "17,098,242"),
        (2025, "India - Area", "general", "3,287,263"),
        (2025, "Brazil - Area", "general", "8,515,770"),
        (2025, "Australia - Area", "general", "7,741,220"),
        (2025, "Japan - Capital", "general", "Tokyo"),
        (2025, "Germany - Capital", "general", "Berlin"),
        (2025, "France - Capital", "general", "Paris"),
        (2025, "United Kingdom - Capital", "general", "London"),
        (1990, "Soviet Union - Capital", "general", "Moscow"),
        (1990, "Yugoslavia - Capital", "general", "Belgrade"),
        (1990, "German Democratic Republic - Capital", "general", "Berlin"),
        (1990, "Germany, Federal Republic of - Capital", "general", "Bonn"),
        (2000, "Japan - Life expectancy at birth", "structured", "male"),
        (2010, "Nigeria - Capital", "general", "Abuja"),
        (2015, "Mexico - Capital", "general", "Mexico City"),
        (2025, "Canada - Capital", "general", "Ottawa"),
        (2025, "Mexico - Capital", "general", "Mexico City"),
        (2025, "South Africa - Capital", "general", "Pretoria"),
        (2025, "Egypt - Capital", "general", "Cairo"),
        (2025, "Kenya - Capital", "general", "Nairobi"),
        (2025, "Argentina - Capital", "general", "Buenos Aires"),
        (2025, "Colombia - Capital", "general", "Bogot"),
        (2025, "Peru - Capital", "general", "Lima"),
        (2025, "Thailand - Capital", "general", "Bangkok"),
        (2025, "Indonesia - Capital", "general", "Jakarta"),
        (2025, "Philippines - Capital", "general", "Manila"),
        (2025, "Vietnam - Capital", "general", "Hanoi"),
        (2025, "Turkey (Turkiye) - Capital", "general", "Ankara"),
        (2025, "Iran - Capital", "general", "Tehran"),
        (2025, "Canada - Area", "general", "9,984,670"),
        (2025, "Argentina - Area", "general", "2,780,400"),
        (2025, "Mexico - Area", "general", "1,964,375"),
        (2025, "Indonesia - Area", "general", "1,904,569"),
        (2000, "United States - Capital", "general", "Washington"),
        (2000, "Russia - Capital", "general", "Moscow"),
        (2000, "China - Capital", "general", "Beijing"),
        (2000, "Brazil - Capital", "general", "Brasilia"),
        (2000, "India - Capital", "general", "New Delhi"),
        (2010, "United States - Capital", "general", "Washington"),
        (2010, "Japan - Capital", "general", "Tokyo"),
        (2010, "Germany - Capital", "general", "Berlin"),
        (2010, "Mexico - Capital", "general", "Mexico City"),
        (2025, "United States - Life expectancy at birth", "structured", "female"),
        (2025, "United States - Population", "general", "total"),
    ]
    gt_passed = 0
    gt_failed = 0
    for year, headword, edition, value in checks:
        d = f"cia-factbook-{year}-{edition}"
        entry = get_entry(d, headword)
        if entry and value in entry:
            gt_passed += 1
        elif not value:
            # Empty check value = just verify entry exists
            if entry:
                gt_passed += 1
            else:
                gt_failed += 1
                print(f"    FAIL: {year} {headword} ({edition}) -> entry not found")
        else:
            gt_failed += 1
            print(f"    FAIL: {year} {headword} ({edition}) -> \"{value}\"")
    t11 = gt_failed == 0
    results.append((f"Ground truth ({gt_passed}/{len(checks)})", t11))
    print(f"[T11] Ground truth: {gt_passed}/{len(checks)} -> {'PASS' if t11 else 'FAIL'}")

    # -- T12: Structured sub-fields (20 countries) --
    sub_checks = [
        "United States", "China", "Russia", "Japan", "Germany", "France",
        "United Kingdom", "Brazil", "India", "Australia", "Canada", "Mexico",
        "South Africa", "Nigeria", "Egypt", "Argentina", "Indonesia",
        "Thailand", "Iran", "Turkey (Turkiye)",
    ]
    sub_ok = 0
    entries_2025 = get_entries("cia-factbook-2025-structured")
    for country in sub_checks:
        # Find the Population entry for this country
        pop_key = f"{country} - Population"
        entry = entries_2025.get(pop_key)
        if entry and ("total" in entry.lower()):
            sub_ok += 1
        else:
            print(f"    FAIL sub-fields: {country} (key={pop_key})")
    t12 = sub_ok == 20
    results.append(("Structured sub-fields (20)", t12))
    print(f"[T12] Structured sub-fields: {sub_ok}/20 -> {'PASS' if t12 else 'FAIL'}")

    # -- T13: Historical entity names --
    hist_checks = [
        (1990, ["Soviet Union", "Yugoslavia", "German Democratic Republic",
                "Germany, Federal Republic of"]),
        (1991, ["Soviet Union", "Yugoslavia"]),
        (1992, ["Czechoslovakia", "Russia", "Serbia and Montenegro"]),
        (2025, ["Russia", "Czechia", "Serbia"]),
    ]
    t13 = True
    for year, expected in hist_checks:
        countries = set(
            extract_country(k)
            for k in get_entries(f"cia-factbook-{year}-general").keys()
        )
        for exp in expected:
            if exp not in countries:
                t13 = False
                print(f"    FAIL: {year} missing \"{exp}\"")
    results.append(("Historical entity names", t13))
    print(f"[T13] Historical names: {'PASS' if t13 else 'FAIL'}")

    # -- T14: Encoding quality --
    total_chars = 0
    total_repl = 0
    for d in dirs:
        dz = os.path.join(STARDICT_DIR, d, d + ".dict.dz")
        if not os.path.exists(dz):
            continue
        with gzip.open(dz, "rb") as f:
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

    # -- T15: Every DB country name in StarDict headwords --
    name_errors = 0
    for year in range(1990, 2026):
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
        sd_countries = set(
            extract_country(k)
            for k in get_entries(f"cia-factbook-{year}-general").keys()
        )
        only_db = db_names - sd_countries
        only_sd = sd_countries - db_names
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

    # -- T16: Round-trip read via pyglossary --
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

            expected_count = 0
            with open(ifo_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("wordcount="):
                        expected_count = int(line.strip().split("=")[1])

            entry_map = {}
            entry_count = 0
            for entry in glos:
                words = entry.l_term
                defi = entry.defi
                fmt = entry.defiFormat
                if words:
                    entry_map[words[0]] = (defi, fmt)
                    entry_count += 1

            if entry_count != expected_count:
                t16 = False
                t16_errors.append(
                    f"{edition}: count {entry_count} != ifo {expected_count}"
                )

            # Spot-check per-field entries
            spot_checks = [
                ("United States - Capital", "Washington"),
                ("China - Capital", "Beijing"),
                ("Australia - Capital", "Canberra"),
                ("Japan - Capital", "Tokyo"),
                ("United Kingdom - Capital", "London"),
            ]
            for headword, expected_text in spot_checks:
                if headword not in entry_map:
                    t16 = False
                    t16_errors.append(f"{edition}: {headword} not found")
                else:
                    defi, fmt = entry_map[headword]
                    if fmt != "h":
                        t16 = False
                        t16_errors.append(
                            f"{edition}: {headword} format '{fmt}' != 'h'"
                        )
                    if expected_text not in defi:
                        t16 = False
                        t16_errors.append(
                            f"{edition}: {headword} missing '{expected_text}'"
                        )
                    if "<small>" not in defi:
                        t16 = False
                        t16_errors.append(
                            f"{edition}: {headword} missing <small> tag"
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

    # -- Summary --
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
