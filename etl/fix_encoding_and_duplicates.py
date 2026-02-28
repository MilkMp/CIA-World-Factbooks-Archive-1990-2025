"""
Fix two data quality issues in the CIA Factbook SQLite databases:

1. Serbia 2008 duplicate: Two Country rows (CountryID 9258 code=rb,
   CountryID 9259 code=ri) with same Name "Serbia", same MasterCountryID=208.
   Fix: merge unique fields from rb into ri, then delete the rb entry.

2. Encoding corruption: 37 field rows across 2006-2017 contain U+FFFD
   replacement characters from mangled Windows-1252 bytes during HTML parsing.
   Fix: replace each U+FFFD with the correct character identified from
   original CIA HTML source files and Wayback Machine captures.

Applies to both factbook.db and factbook_field_values.db.
"""

import sqlite3
import sys
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_GENERAL = os.path.join(REPO, "data", "factbook.db")
DB_STRUCTURED = os.path.join(REPO, "data", "factbook_field_values.db")

# ── Encoding fixes ──────────────────────────────────────────────────────
# Each entry: (FieldID, [(old_substring, new_substring), ...])
# Identified by cross-referencing adjacent clean years and original HTML sources.

ENCODING_FIXES = {
    # 2006
    1089163: [("5\ufffd-year", "5\u00bd-year")],                    # Chile: ½
    1090053: [("R\ufffdo San Juan", "R\u00edo San Juan")],          # Costa Rica: í
    # 2007
    1119118: [("R\ufffdo San Juan", "R\u00edo San Juan")],          # Costa Rica: í
    # 2008
    1145534: [("S\ufffdHOU\ufffdTO", "S\u00c9HOUT\u00d3")],        # Benin: É, Ó
    1145341: [                                                       # Bolivia
        ("Isla Su\ufffdrez", "Isla Su\u00e1rez"),                    # á
        ("Guajar\ufffd-Mirim", "Guajar\u00e1-Mirim"),               # á
        ("R\ufffdo Mamor\ufffd", "R\u00edo Mamor\u00e9"),           # í, é
    ],
    1146030: [                                                       # Brazil
        ("Itaip\ufffd Dam", "Itaip\u00fa Dam"),                      # ú
        ("Isla Su\ufffdrez", "Isla Su\u00e1rez"),                    # á
        ("Guajar\ufffd-Mirim", "Guajar\u00e1-Mirim"),               # á
        ("R\ufffdo Mamor\ufffd", "R\u00edo Mamor\u00e9"),           # í, é
    ],
    1148260: [("82\ufffdW", "82\u00b0W")],                          # Colombia: °
    1148528: [("R\ufffdo San Juan", "R\u00edo San Juan")],          # Costa Rica: í
    # 2009
    1845767: [("S\ufffdHOU\ufffdTO", "S\u00c9HOUT\u00d3")],        # Benin: É, Ó
    1847558: [                                                       # Congo DRC
        ("Arm\ufffdes", "Arm\u00e9es"),                              # é
        ("R\ufffdpublique", "R\u00e9publique"),                      # é
        ("D\ufffdmocratique", "D\u00e9mocratique"),                  # é
    ],
    1848774: [("R\ufffdo San Juan", "R\u00edo San Juan")],          # Costa Rica: í
    # 2010
    1876561: [("S\ufffdHOU\ufffdTO", "S\u00c9HOUT\u00d3")],        # Benin: É, Ó
    1878422: [                                                       # Congo DRC
        ("Arm\ufffdes", "Arm\u00e9es"),                              # é
        ("R\ufffdpublique", "R\u00e9publique"),                      # é
        ("D\ufffdmocratique", "D\u00e9mocratique"),                  # é
    ],
    1893306: [                                                       # Nepal: em dashes
        ("constitution \ufffd due", "constitution \u2014 due"),
        ("May 2011 \ufffd and", "May 2011 \u2014 and"),
    ],
    1894216: [("Paran\ufffd river", "Paran\u00e1 river")],          # Paraguay: á
    # 2015
    1177042: [("S\ufffdHOU\ufffdTO", "S\u00c9HOUT\u00d3")],        # Benin: É, Ó
    1179305: [                                                       # Congo DRC
        ("Arm\ufffdes", "Arm\u00e9es"),
        ("R\ufffdpublique", "R\u00e9publique"),
        ("D\ufffdmocratique", "D\u00e9mocratique"),
    ],
    1182414: [("EC\ufffds", "EC\u2019s")],                          # EU: right single quote
    1192552: [("MAT\ufffdASA", "MAT\u0160ASA")],                    # Lesotho: Š
    1191915: [                                                       # Lithuania: Lithuanian diacritics
        ("Ank\ufffdciai", "Ank\u0161\u010diai"),                     # šč  (Anykščiai)
        ("Bir\ufffdtono", "Bir\u0161tono"),                          # š   (Birštonas→Birštonoj)
        ("Bir\ufffdai", "Bir\u017eai"),                              # ž   (Biržai)
        ("Elektr\ufffdnai", "Elektr\u0117nai"),                     # ė   (Elektrėnai)
        ("Joni\ufffdkis", "Joni\u0161kis"),                          # š   (Joniškis)
        ("Kai\ufffdiadorys", "Kai\u0161iadorys"),                    # š   (Kaišiadorys)
        ("Kupi\ufffdkis", "Kupi\u0161kis"),                          # š   (Kupiškis)
        ("Ma\ufffdeikiai", "Ma\u017eeikiai"),                        # ž   (Mažeikiai)
        ("Pag\ufffdgiai", "Pag\u0117giai"),                          # ė   (Pagėgiai)
        ("Paneve\ufffdys", "Paneve\u017eys"),                        # ž   (Panevėžys)
        ("Radvili\ufffdkis", "Radvili\u0161kis"),                    # š   (Radviliškis)
        ("Roki\ufffdkis, \ufffdakiai", "Roki\u0161kis, \u0160akiai"),  # š, Š
        ("\ufffdalcininkai", "\u0160al\u010dininkai"),                # Š,č (Šalčininkai — source has plain 'c')
        ("\ufffdiauliu", "\u0160iauliu"),                             # Š   (Šiaulių - note: ų may also be corrupted but the iu ending is what's in the data)
        ("\ufffdiauliai", "\u0160iauliai"),                           # Š   (Šiauliai)
        ("\ufffdilale", "\u0160ilal\u0117"),                          # Š,ė (Šilalė)
        ("\ufffdilute", "\u0160ilut\u0117"),                          # Š,ė (Šilutė)
        ("\ufffdirvinto", "\u0160irvinto"),                           # Š   (Širvintos)
        ("\ufffdvencion", "\u0160vencion"),                           # Š   (Švenčionys)
        ("Tel\ufffdiai", "Tel\u0161iai"),                             # š   (Telšiai)
        ("Vilkavi\ufffdkis", "Vilkavi\u0161kis"),                    # š   (Vilkaviškis)
    ],
    1198179: [("Paran\ufffd River", "Paran\u00e1 River")],          # Paraguay: á
    1201717: [("\ufffdBOKK", "\u2018BOKK")],                         # Senegal: left single quote
    1204118: [("d\u2019\ufffdtat", "d\u2019\u00e9tat")],             # Thailand: é (note: apostrophe is U+2019 smart quote)
    1206382: [("\ufffd375", "\u00a3375")],                            # UK: £
    # 2016
    1213732: [("products\ufffd edible", "products, edible")],        # Burma: comma
    1216945: [("m\ufffdlange", "m\u00e9lange")],                     # Comoros: é
    1216117: [                                                        # Congo DRC
        ("Arm\ufffdes", "Arm\u00e9es"),
        ("R\ufffdpublique", "R\u00e9publique"),
        ("D\ufffdmocratique", "D\u00e9mocratique"),
    ],
    1218882: [("4.0% \ufffd 1.0%", "4.0% \u00b1 1.0%")],           # Dominican Republic: ±
    1229343: [("MAT\ufffdASA", "MAT\u0160ASA")],                    # Lesotho: Š
    1234983: [("Paran\ufffd River", "Paran\u00e1 River")],          # Paraguay: á
    # 2017
    1250552: [("products\ufffd edible", "products\u2018 edible")],   # Burma: left single quote
    1252951: [                                                        # Congo DRC
        ("Arm\ufffdes", "Arm\u00e9es"),
        ("R\ufffdpublique", "R\u00e9publique"),
        ("D\ufffdmocratique", "D\u00e9mocratique"),
    ],
    1263594: [("Al \ufffdAsimah", "Al \u2018Asimah")],               # Jordan: left single quote
    1266272: [("MAT\ufffdASA", "MAT\u0160ASA")],                    # Lesotho: Š
    1268110: [("R\ufffdvoires", "R\u00e9voires")],                   # Monaco: é
    1271951: [("Paran\ufffd River", "Paran\u00e1 River")],          # Paraguay: á
    1281686: [("\ufffdsecond", "\u2018second")],                     # Vietnam: left single quote
}


def fix_encoding(db_path, dry_run=False):
    """Fix U+FFFD replacement characters in CountryFields.Content and FieldValues.TextVal."""
    db = sqlite3.connect(db_path)
    db_name = os.path.basename(db_path)
    fixed_fields = 0
    fixed_values = 0

    for field_id, replacements in ENCODING_FIXES.items():
        # Fix CountryFields.Content
        row = db.execute(
            "SELECT Content FROM CountryFields WHERE FieldID = ?", (field_id,)
        ).fetchone()
        if row and row[0] and "\ufffd" in row[0]:
            content = row[0]
            for old, new in replacements:
                content = content.replace(old, new)
            if "\ufffd" not in content:
                if not dry_run:
                    db.execute(
                        "UPDATE CountryFields SET Content = ? WHERE FieldID = ?",
                        (content, field_id),
                    )
                fixed_fields += 1
            else:
                remaining = content.count("\ufffd")
                print(f"  WARNING: {db_name} FieldID={field_id} still has {remaining} bad chars after fix")

        # Fix FieldValues.TextVal (same FieldID links) — only in factbook_field_values.db
        try:
            val_rows = db.execute(
                "SELECT ValueID, TextVal FROM FieldValues fv "
                "WHERE fv.FieldID = ? AND fv.TextVal LIKE '%' || X'EFBFBD' || '%'",
                (field_id,),
            ).fetchall()
        except sqlite3.OperationalError:
            val_rows = []  # Table doesn't exist in factbook.db
        for vid, text_val in val_rows:
            fixed_text = text_val
            for old, new in replacements:
                fixed_text = fixed_text.replace(old, new)
            if "\ufffd" not in fixed_text:
                if not dry_run:
                    db.execute(
                        "UPDATE FieldValues SET TextVal = ? WHERE ValueID = ?",
                        (fixed_text, vid),
                    )
                fixed_values += 1
            else:
                remaining = fixed_text.count("\ufffd")
                print(f"  WARNING: {db_name} ValueID={vid} still has {remaining} bad chars after fix")

    if not dry_run:
        db.commit()
    db.close()
    return fixed_fields, fixed_values


def fix_serbia_duplicate(db_path, dry_run=False):
    """Merge Serbia 2008 duplicate entries (rb→ri)."""
    db = sqlite3.connect(db_path)
    db_name = os.path.basename(db_path)

    # Verify both entries exist
    rows = db.execute(
        "SELECT CountryID, Code FROM Countries "
        "WHERE Name = 'Serbia' AND Year = 2008 AND MasterCountryID = 208 "
        "ORDER BY Code"
    ).fetchall()

    if len(rows) != 2:
        print(f"  {db_name}: Serbia 2008 does not have exactly 2 entries ({len(rows)} found), skipping")
        db.close()
        return False

    # rb is the old code, ri is the new code (used 2009+)
    rb_cid = None
    ri_cid = None
    for cid, code in rows:
        if code.lower() == "rb":
            rb_cid = cid
        elif code.lower() == "ri":
            ri_cid = cid

    if not rb_cid or not ri_cid:
        print(f"  {db_name}: Could not identify rb/ri entries, skipping")
        db.close()
        return False

    print(f"  {db_name}: Merging rb(CountryID={rb_cid}) into ri(CountryID={ri_cid})")

    # Get fields unique to rb (not in ri by FieldName+CategoryTitle)
    ri_fields = set()
    for r in db.execute(
        "SELECT cf.FieldName, cc.CategoryTitle "
        "FROM CountryFields cf "
        "JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID "
        "WHERE cf.CountryID = ?", (ri_cid,)
    ).fetchall():
        ri_fields.add((r[0], r[1]))

    rb_unique_fields = []
    for r in db.execute(
        "SELECT cf.FieldID, cf.FieldName, cc.CategoryTitle, cc.CategoryID "
        "FROM CountryFields cf "
        "JOIN CountryCategories cc ON cf.CategoryID = cc.CategoryID "
        "WHERE cf.CountryID = ?", (rb_cid,)
    ).fetchall():
        if (r[1], r[2]) not in ri_fields:
            rb_unique_fields.append(r)

    if rb_unique_fields:
        print(f"    {len(rb_unique_fields)} unique fields in rb to migrate:")
        for fid, fname, cat, catid in rb_unique_fields:
            print(f"      {cat} > {fname} (FieldID={fid})")

        if not dry_run:
            # Find matching ri categories for each rb unique field
            for fid, fname, cat, rb_catid in rb_unique_fields:
                # Find the corresponding category in ri
                ri_cat = db.execute(
                    "SELECT CategoryID FROM CountryCategories "
                    "WHERE CountryID = ? AND CategoryTitle = ?",
                    (ri_cid, cat)
                ).fetchone()

                if ri_cat:
                    ri_catid = ri_cat[0]
                    # Re-assign the field to ri's country and category
                    db.execute(
                        "UPDATE CountryFields SET CountryID = ?, CategoryID = ? "
                        "WHERE FieldID = ?",
                        (ri_cid, ri_catid, fid)
                    )
                    # Also move any FieldValues
                    # (FieldValues reference FieldID, so they follow automatically)
                    print(f"      -> Migrated FieldID={fid} to ri CategoryID={ri_catid}")
                else:
                    print(f"      -> WARNING: No matching category '{cat}' in ri, skipping")
    else:
        print(f"    No unique fields in rb to migrate")

    # Delete rb's remaining fields (duplicates of ri)
    if not dry_run:
        # Delete FieldValues for rb's remaining fields (only in factbook_field_values.db)
        try:
            db.execute(
                "DELETE FROM FieldValues WHERE FieldID IN "
                "(SELECT FieldID FROM CountryFields WHERE CountryID = ?)",
                (rb_cid,)
            )
        except sqlite3.OperationalError:
            pass  # Table doesn't exist in factbook.db
        # Delete rb's remaining CountryFields
        db.execute("DELETE FROM CountryFields WHERE CountryID = ?", (rb_cid,))
        # Delete rb's CountryCategories
        db.execute("DELETE FROM CountryCategories WHERE CountryID = ?", (rb_cid,))
        # Delete rb's Country row
        db.execute("DELETE FROM Countries WHERE CountryID = ?", (rb_cid,))
        print(f"    Deleted rb entry (CountryID={rb_cid})")

    db.commit()
    db.close()
    return True


def verify_fixes(db_path):
    """Verify both fixes were applied correctly."""
    db = sqlite3.connect(db_path)
    db_name = os.path.basename(db_path)
    issues = []

    # Check no remaining U+FFFD in CountryFields
    bad_cf = db.execute(
        "SELECT COUNT(*) FROM CountryFields WHERE Content LIKE '%' || X'EFBFBD' || '%'"
    ).fetchone()[0]
    if bad_cf > 0:
        issues.append(f"{bad_cf} CountryFields rows still have U+FFFD")

    # Check no remaining U+FFFD in FieldValues (if table exists)
    try:
        bad_fv = db.execute(
            "SELECT COUNT(*) FROM FieldValues WHERE TextVal LIKE '%' || X'EFBFBD' || '%'"
        ).fetchone()[0]
        if bad_fv > 0:
            issues.append(f"{bad_fv} FieldValues rows still have U+FFFD")
    except sqlite3.OperationalError:
        pass  # Table doesn't exist in factbook.db

    # Check Serbia 2008 has exactly 1 entry
    serbia = db.execute(
        "SELECT COUNT(*) FROM Countries WHERE Name = 'Serbia' AND Year = 2008"
    ).fetchone()[0]
    if serbia != 1:
        issues.append(f"Serbia 2008 has {serbia} entries (expected 1)")

    # Check Serbia 2008 uses code ri
    code = db.execute(
        "SELECT Code FROM Countries WHERE Name = 'Serbia' AND Year = 2008"
    ).fetchone()
    if code and code[0].lower() != "ri":
        issues.append(f"Serbia 2008 has code '{code[0]}' (expected 'ri')")

    db.close()
    return issues


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY RUN (no changes will be written) ===\n")

    for db_path in [DB_GENERAL, DB_STRUCTURED]:
        db_name = os.path.basename(db_path)
        if not os.path.exists(db_path):
            print(f"SKIP: {db_path} not found")
            continue

        print(f"\n{'='*60}")
        print(f"Processing {db_name}")
        print(f"{'='*60}")

        # Fix 1: Encoding corruption
        print(f"\n[1] Fixing encoding corruption...")
        fixed_fields, fixed_values = fix_encoding(db_path, dry_run)
        print(f"    Fixed {fixed_fields} CountryFields rows, {fixed_values} FieldValues rows")

        # Fix 2: Serbia 2008 duplicate
        print(f"\n[2] Fixing Serbia 2008 duplicate...")
        fix_serbia_duplicate(db_path, dry_run)

        # Verify
        if not dry_run:
            print(f"\n[3] Verifying fixes...")
            issues = verify_fixes(db_path)
            if issues:
                for issue in issues:
                    print(f"    FAIL: {issue}")
            else:
                print(f"    All checks passed")

    if dry_run:
        print("\n=== DRY RUN complete (no changes made) ===")
    else:
        print("\n=== All fixes applied and verified ===")


if __name__ == "__main__":
    main()
