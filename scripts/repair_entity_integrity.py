#!/usr/bin/env python3
"""Issue #38: repair reviewed legacy identities and four entity classifications.

Dry run by default. --apply requires a new full SQLite backup path. No IDs from
one export are reused in another. Historical source names/text stay intact.
"""
import argparse
import json
from pathlib import Path
import shutil
import sqlite3

# Exact source name -> (correct FIPS, previously misassigned FIPS).
# Palau identification is explicit in the 1990-92 source's nationality,
# capital and government fields, despite the entry's trusteeship title.
IDENTITIES = {
    'cape verde': ('CV', 'CA'),
    'cocos islands': ('CK', 'CO'),
    'man, isle of': ('IM', 'MA'),
    'south georgia and the': ('SX', 'GG'),
    'wake atoll': ('WQ', 'WA'),
    'st. helena': ('SH', 'ST'),
    'st. kitts and nevis': ('SC', 'ST'),
    'st. lucia': ('ST', 'ST'),
    'st. pierre and miquelon': ('SB', 'ST'),
    'st. vincent and the grenadines': ('VC', 'ST'),
    'pacific islands, trust territory of the': ('PS', 'PA'),
    'iraq - saudi arabia neutral zone': ('IY', 'IZ'),
}
NEUTRAL_ZONE = 'Iraq - Saudi Arabia Neutral Zone'


def connect(path, readonly=True):
    db = sqlite3.connect(Path(path).resolve().as_uri() + ('?mode=ro' if readonly else '?mode=rw'), uri=True)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    return db


def plan(db):
    masters = {r['CanonicalCode']: dict(r) for r in db.execute('SELECT * FROM MasterCountries')}
    result = {'new_masters': [], 'classifications': [], 'editions': [], 'glossary_fields': [], 'trimmed_fields': [], 'derived_values': 0}
    neutral = db.execute("SELECT 1 FROM Countries WHERE lower(Name)=? AND Source='text' AND Year IN (1990,1991)", (NEUTRAL_ZONE.lower(),)).fetchone()
    if neutral and 'IY' not in masters:
        new = dict(MasterCountryID=max(r['MasterCountryID'] for r in masters.values())+1,
                   CanonicalCode='IY', CanonicalName=NEUTRAL_ZONE, ISOAlpha2=None,
                   EntityType='dissolved', AdministeringMasterCountryID=None)
        masters['IY'] = new
        result['new_masters'].append(new)
    if neutral and (masters['IY']['CanonicalName'] != NEUTRAL_ZONE or masters['IY']['EntityType'] != 'dissolved'):
        raise ValueError('IY already has a conflicting identity')
    for code, name, expected in [('GG', 'Georgia', 'sovereign'), ('ZI', 'Zimbabwe', 'sovereign'),
                                 ('CW', 'Cook Islands', 'freely_associated'), ('NE', 'Niue', 'freely_associated')]:
        old = masters.get(code)
        if not old or old['CanonicalName'] != name or old['EntityType'] not in ('territory', expected):
            raise ValueError(f'Unexpected master identity/classification for {code}')
        if old['EntityType'] != expected:
            result['classifications'].append({'before': old, 'after_type': expected})
    by_id = {r['MasterCountryID']: r for r in masters.values()}
    for row in db.execute("SELECT * FROM Countries WHERE Source='text' AND Year BETWEEN 1990 AND 2001 ORDER BY Year,CountryID"):
        match = IDENTITIES.get(row['Name'].casefold().strip())
        if not match:
            continue
        target_code, wrong_code = match
        target = masters[target_code]
        old_master = by_id.get(row['MasterCountryID'])
        if old_master and old_master['CanonicalCode'] not in (target_code, wrong_code):
            raise ValueError(f'Unexpected owner for {row["Name"]} {row["Year"]}')
        if row['Name'] == NEUTRAL_ZONE and row['Year'] not in (1990, 1991):
            raise ValueError('Unexpected neutral-zone edition')
        after = dict(row)
        after.update(MasterCountryID=target['MasterCountryID'], Code=target_code.lower())
        if row['Name'].casefold() == 'south georgia and the':
            after['Name'] = target['CanonicalName']
        if after == dict(row):
            continue
        duplicate = db.execute('SELECT CountryID FROM Countries WHERE Year=? AND MasterCountryID=? AND CountryID<>?',
                               (row['Year'], target['MasterCountryID'], row['CountryID'])).fetchone()
        if duplicate:
            raise ValueError(f'Target edition already exists: {target_code} {row["Year"]}')
        result['editions'].append({'before': dict(row), 'after': after, 'target': target['CanonicalName']})
    # Only the known 1998 Zimbabwe back-matter block. Retain both authentic
    # Transnational Issues fields; fail closed if the glossary signature differs.
    all_rows = [dict(r) for r in db.execute('''SELECT cf.* FROM CountryFields cf
        JOIN Countries c USING(CountryID) JOIN CountryCategories cc USING(CategoryID)
        WHERE c.Year=1998 AND lower(c.Name)='zimbabwe' AND c.Source='text'
          AND cc.CategoryTitle='Transnational Issues' ORDER BY cf.FieldID''')]
    rows = []
    if all_rows:
        if [r['FieldName'] for r in all_rows[:2]] != ['Disputes-international', 'Illicit drugs']:
            raise ValueError('Unexpected authentic Zimbabwe fields')
        real_drugs = all_rows[1]
        marker = ' | @NOTES AND DEFINITIONS'
        if marker in real_drugs['Content']:
            after = dict(real_drugs, Content=real_drugs['Content'].split(marker, 1)[0].rstrip())
            result['trimmed_fields'].append({'before': real_drugs, 'after': after})
        rows = all_rows[2:]
    if rows:
        signature = any(r['FieldName']=='Dependency status' and
                        r['Content'].startswith('This entry describes the formal relationship') for r in rows)
        # Older maintenance removed most glossary rows but left duplicate
        # Disputes/Illicit drugs definitions; support that already-patched state.
        residual = (len(rows)==2 and {r['FieldName'] for r in rows} == {'Disputes-international','Illicit drugs'}
                    and all(r['Content'].startswith('This entry') for r in rows))
        if not ((len(rows)==176 and signature) or residual):
            raise ValueError(f'Unexpected Zimbabwe appendix: {len(rows)} fields; no edits applied')
        result['glossary_fields'] = rows
    affected = rows + [r['before'] for r in result['trimmed_fields']]
    if affected and db.execute("SELECT 1 FROM sqlite_master WHERE name='FieldValues'").fetchone():
        result['derived_values'] = sum(db.execute('SELECT COUNT(*) FROM FieldValues WHERE FieldID=?', (r['FieldID'],)).fetchone()[0] for r in affected)
    return result


def summary(result):
    return {
        'new_masters': result['new_masters'],
        'classifications': [{'name': r['before']['CanonicalName'], 'from': r['before']['EntityType'], 'to': r['after_type']} for r in result['classifications']],
        'editions': [{'year': r['before']['Year'], 'source_name': r['before']['Name'], 'target': r['target'],
                      'from_master': r['before']['MasterCountryID'], 'to_master': r['after']['MasterCountryID']} for r in result['editions']],
        'glossary_fields': len(result['glossary_fields']), 'trimmed_fields': len(result['trimmed_fields']), 'derived_values': result['derived_values'],
    }


def apply(db, result):
    for row in result['new_masters']:
        db.execute('INSERT INTO MasterCountries VALUES (?,?,?,?,?,?)', tuple(row.values()))
    for row in result['classifications']:
        db.execute('UPDATE MasterCountries SET EntityType=? WHERE MasterCountryID=?', (row['after_type'], row['before']['MasterCountryID']))
    for row in result['editions']:
        after = row['after']
        db.execute('UPDATE Countries SET Code=?,Name=?,MasterCountryID=? WHERE CountryID=?',
                   (after['Code'], after['Name'], after['MasterCountryID'], after['CountryID']))
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for row in result['glossary_fields']:
        if 'FieldValues' in tables:
            db.execute('DELETE FROM FieldValues WHERE FieldID=?', (row['FieldID'],))
        if 'CountryFieldsFTS' in tables:
            db.execute("INSERT INTO CountryFieldsFTS(CountryFieldsFTS,rowid,Content) VALUES ('delete',?,?)", (row['FieldID'], row['Content']))
        db.execute('DELETE FROM CountryFields WHERE FieldID=?', (row['FieldID'],))
    for change in result['trimmed_fields']:
        before, after = change['before'], change['after']
        if 'FieldValues' in tables:
            db.execute('DELETE FROM FieldValues WHERE FieldID=?', (before['FieldID'],))
        if 'CountryFieldsFTS' in tables:
            db.execute("INSERT INTO CountryFieldsFTS(CountryFieldsFTS,rowid,Content) VALUES ('delete',?,?)", (before['FieldID'], before['Content']))
            db.execute('INSERT INTO CountryFieldsFTS(rowid,Content) VALUES (?,?)', (after['FieldID'], after['Content']))
        db.execute('UPDATE CountryFields SET Content=? WHERE FieldID=?', (after['Content'], after['FieldID']))
    remaining = plan(db)
    if any(remaining.values()):
        raise ValueError('Post-repair validation failed')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('database')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--backup', type=Path)
    args = parser.parse_args()
    with connect(args.database) as db:
        result = plan(db)
        print(json.dumps(summary(result), indent=2))
        if not args.apply or not any(result.values()):
            return
        if not args.backup:
            parser.error('--apply requires --backup (a new full SQLite backup file)')
        if args.backup.exists():
            parser.error('Backup path already exists; refusing to overwrite')
        size = Path(args.database).stat().st_size
        if shutil.disk_usage(args.backup.parent).free < size * 1.5:
            parser.error('Insufficient free space for backup and SQLite journal')
        # Exclusive creation prevents accidentally overwriting a prior backup.
        with args.backup.open('xb'):
            pass
        with sqlite3.connect(args.backup) as backup:
            db.backup(backup)
            if backup.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('Backup integrity check failed')
    with connect(args.database, readonly=False) as db:
        db.execute('BEGIN IMMEDIATE')
        if plan(db) != result:
            raise ValueError('Data changed since backup; refusing repair')
        apply(db, result)
        if db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise ValueError('Post-repair integrity check failed')
    print(f'Repair committed. Full backup: {args.backup}')


if __name__ == '__main__':
    main()
