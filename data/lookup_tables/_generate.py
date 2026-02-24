"""
Generate lookup table CSVs from ETL script dictionaries.
Extracts embedded mapping data into standalone CSV files.
Run: python data/lookup_tables/_generate.py
"""
import csv
import os
import sys

# Add project root so we can import from etl/ and scripts/
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "data", "lookup_tables")
os.makedirs(OUT, exist_ok=True)


def export_fips_to_iso():
    """Extract FIPS-to-ISO crosswalk from cleanup_master_countries.py."""
    # Import the dict directly
    script = os.path.join(ROOT, "scripts", "archive", "cleanup_master_countries.py")
    ns = {}
    with open(script, "r", encoding="utf-8") as f:
        code = f.read()
    # Extract just the FIPS_TO_ISO dict and NAME_FIXES
    exec(compile(code, script, "exec"), ns)
    fips_map = ns["FIPS_TO_ISO"]
    name_fixes = ns["NAME_FIXES"]
    code_merges = ns["CODE_MERGES"]
    name_updates = ns["NAME_UPDATES"]

    # FIPS-to-ISO crosswalk
    path = os.path.join(OUT, "fips_to_iso2.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["FIPS", "ISOAlpha2", "Notes"])
        for fips in sorted(fips_map.keys()):
            iso = fips_map[fips]
            w.writerow([fips, iso or "", "" if iso else "No ISO code assigned"])
    print(f"  fips_to_iso2.csv: {len(fips_map)} entries")

    # Code merges (old FIPS -> modern FIPS)
    path = os.path.join(OUT, "fips_code_merges.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["OldFIPS", "MergedIntoFIPS"])
        for old in sorted(code_merges.keys()):
            new = code_merges[old]
            w.writerow([old, new])
    print(f"  fips_code_merges.csv: {len(code_merges)} entries")

    # Name fixes (FIPS -> corrected country name)
    path = os.path.join(OUT, "country_name_fixes.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["FIPS", "CorrectedName"])
        for fips in sorted(name_fixes.keys()):
            w.writerow([fips, name_fixes[fips]])
    print(f"  country_name_fixes.csv: {len(name_fixes)} entries")

    # Name updates (FIPS -> modern official name)
    path = os.path.join(OUT, "country_name_updates.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["FIPS", "ModernName"])
        for fips in sorted(name_updates.keys()):
            w.writerow([fips, name_updates[fips]])
    print(f"  country_name_updates.csv: {len(name_updates)} entries")


def export_entity_overrides():
    """Extract entity type overrides from classify_entities.py."""
    script = os.path.join(ROOT, "etl", "classify_entities.py")
    ns = {}
    with open(script, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, script, "exec"), ns)
    overrides = ns["OVERRIDES"]

    path = os.path.join(OUT, "entity_type_overrides.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["FIPS", "EntityType"])
        for fips in sorted(overrides.keys()):
            w.writerow([fips, overrides[fips]])
    print(f"  entity_type_overrides.csv: {len(overrides)} entries")


def export_field_renames():
    """Extract field name mappings from build_field_mappings.py."""
    script = os.path.join(ROOT, "etl", "build_field_mappings.py")
    ns = {}
    with open(script, "r", encoding="utf-8") as f:
        code = f.read()
    exec(compile(code, script, "exec"), ns)
    renames = ns["KNOWN_RENAMES"]
    consolidation = ns["CONSOLIDATION_MAP"]

    # Known renames
    path = os.path.join(OUT, "field_name_renames.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["OriginalName", "CanonicalName"])
        for orig in sorted(renames.keys()):
            w.writerow([orig, renames[orig]])
    print(f"  field_name_renames.csv: {len(renames)} entries")

    # Consolidation map (sub-fields -> parent)
    path = os.path.join(OUT, "field_consolidation.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["SubField", "ParentField"])
        for sub in sorted(consolidation.keys()):
            w.writerow([sub, consolidation[sub]])
    print(f"  field_consolidation.csv: {len(consolidation)} entries")


def main():
    print("Generating lookup table CSVs...")
    print()

    print("From cleanup_master_countries.py:")
    export_fips_to_iso()
    print()

    print("From classify_entities.py:")
    export_entity_overrides()
    print()

    print("From build_field_mappings.py:")
    export_field_renames()
    print()

    # List all generated files
    print("=" * 50)
    print("Generated files:")
    for f in sorted(os.listdir(OUT)):
        if f.endswith(".csv"):
            size = os.path.getsize(os.path.join(OUT, f))
            print(f"  {f:<35s} {size:>6,} bytes")


if __name__ == "__main__":
    main()
