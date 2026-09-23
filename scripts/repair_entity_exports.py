#!/usr/bin/env python3
"""Apply issue #38's reviewed identity rules to the published reference exports.

The SQLite deployment and SQL Server exports use different row IDs. Resolve
each export's own identities; never copy IDs or overwrite a deployed database.
"""
import csv
import gzip
import io
import json
import re
import sqlite3
from collections import Counter
from pathlib import Path
from repair_entity_integrity import IDENTITIES, NEUTRAL_ZONE

ROOT = Path(__file__).resolve().parents[1]


def literal(value, tsql=False):
    if value is None:
        return 'NULL'
    if isinstance(value, int):
        return str(value)
    return ('N' if tsql else '') + "'" + value.replace("'", "''") + "'"


def repair_exports(root=ROOT):
    data = root/'data'
    db = sqlite3.connect(':memory:')
    db.row_factory = sqlite3.Row
    for name in ('master_countries','countries'):
        db.executescript((data/'reference_tables'/f'{name}.sqlite.sql').read_text())
    masters = {r['CanonicalCode']:dict(r) for r in db.execute('SELECT * FROM MasterCountries')}
    new_master = None
    if 'IY' not in masters:
        new_master = dict(MasterCountryID=max(r['MasterCountryID'] for r in masters.values())+1,
                          CanonicalCode='IY',CanonicalName=NEUTRAL_ZONE,ISOAlpha2=None,
                          EntityType='dissolved',AdministeringMasterCountryID=None)
        masters['IY']=new_master
    old_by_id = {r['MasterCountryID']:r for r in masters.values()}
    changes={}
    classifications={}
    for code in ('CW','NE'):
        before=masters[code]
        if before['EntityType']=='territory':
            after=dict(before,EntityType='freely_associated')
            classifications[before['MasterCountryID']]=(before,after)
    original_sql=(data/'countries.sql').read_text()
    for row in db.execute("SELECT * FROM Countries WHERE Source='text' AND Year BETWEEN 1990 AND 2001"):
        match=IDENTITIES.get(row['Name'].casefold().strip())
        if not match:
            continue
        target,wrong=match
        old=old_by_id.get(row['MasterCountryID'])
        if old and old['CanonicalCode'] not in (target,wrong):
            raise ValueError(f'Unexpected published owner: {dict(row)}')
        after=dict(row,Code=target.lower(),MasterCountryID=masters[target]['MasterCountryID'])
        if row['Name'].casefold()=='south georgia and the':
            after['Name']=masters[target]['CanonicalName']
        expected_sql='  ('+', '.join(literal(v,True) for v in after.values())+')'
        if after!=dict(row) or expected_sql not in original_sql:
            changes[row['CountryID']] = (dict(row),after)
    # Verify the identity columns in each export. Older SQL dumps can have
    # NULL links where the later reference CSV has already been linked.
    for table,stem,key,updates in [('Countries','countries','CountryID',changes),
                                  ('MasterCountries','master_countries','MasterCountryID',classifications)]:
        sqlpath=data/f'{stem}.sql'
        sql=sqlpath.read_text()
        for before,after in updates.values():
            old='  ('+', '.join(literal(v,True) for v in before.values())+')'
            new='  ('+', '.join(literal(v,True) for v in after.values())+')'
            if sql.count(old)!=1:
                prefix='  ('+', '.join(literal(v,True) for v in list(before.values())[:-1])+', '
                pattern=re.escape(prefix)+r'(NULL|\d+)\)'
                matches=list(re.finditer(pattern,sql))
                wrong=IDENTITIES[before['Name'].casefold().strip()][1]
                allowed={str(before['MasterCountryID']),str(after['MasterCountryID']),str(masters[wrong]['MasterCountryID']),'NULL'}
                if len(matches)!=1 or matches[0].group(1) not in allowed:
                    raise ValueError(f'Unexpected SQL export for {before[key]}')
                old=matches[0].group(0)
            sql=sql.replace(old,new)
        sqlitepath=data/'reference_tables'/f'{stem}.sqlite.sql'
        sqlite_sql=sqlitepath.read_text()
        for before,after in updates.values():
            old=f'INSERT INTO {table} VALUES ('+', '.join(literal(v) for v in before.values())+');'
            new=f'INSERT INTO {table} VALUES ('+', '.join(literal(v) for v in after.values())+');'
            if sqlite_sql.count(old)!=1:
                raise ValueError(f'Unexpected SQLite export for {before[key]}')
            sqlite_sql=sqlite_sql.replace(old,new)
        csvpath=data/'reference_tables'/f'{stem}.csv'
        reader=csv.DictReader(io.StringIO(csvpath.read_text()))
        columns=reader.fieldnames
        rows=list(reader)
        for row in rows:
            if int(row[key]) in updates:
                before,after=updates[int(row[key])]
                if row!={k:'' if v is None else str(v) for k,v in before.items()}:
                    raise ValueError(f'Unexpected CSV export for {row[key]}')
                row.update(after)
        if table=='MasterCountries' and new_master:
            tail=sql.rfind(');')
            sql=sql[:tail]+'),\n  ('+', '.join(literal(v,True) for v in new_master.values())+sql[tail:]
            sql=sql.replace('MasterCountries: 281 rows','MasterCountries: 282 rows')
            sqlite_sql+=f"INSERT INTO {table} VALUES ("+', '.join(literal(v) for v in new_master.values())+');\n'
            sqlite_sql=sqlite_sql.replace('MasterCountries: 281 rows','MasterCountries: 282 rows')
            rows.append(new_master)
        sqlpath.write_text(sql)
        sqlitepath.write_text(sqlite_sql)
        out=io.StringIO();writer=csv.DictWriter(out,columns,lineterminator='\n');writer.writeheader();writer.writerows(rows)
        csvpath.write_text(out.getvalue())

    # The earlier dump repair removed the 176 appendix rows, but its preamble
    # remains attached to the real Illicit drugs field. Trim only that boundary.
    path=data/'fields/country_fields_1998.sql.gz'
    text=gzip.open(path,'rt').read()
    trimmed=0
    lines=text.splitlines(keepends=True)
    for i,line in enumerate(lines):
        if '1626048,' in line and '@NOTES AND DEFINITIONS' in line:
            prefix=line.split('@NOTES AND DEFINITIONS',1)[0].rstrip(' |')
            ending=',' if line.rstrip().endswith(',') else ';'
            lines[i]=prefix+"')"+ending+'\n';trimmed+=1
    if trimmed:
        with gzip.GzipFile(filename=str(path),mode='wb',mtime=0) as f:
            f.write(''.join(lines).encode())

    # Refresh affected browse metadata from these exports' own field counts.
    if changes or classifications or new_master or trimmed:
        counts=Counter()
        for path in (data/'fields').glob('country_fields_*.sql.gz'):
            with gzip.open(path,'rt') as f:
                for line in f:
                    match=re.match(r'\s*\(\d+,\s*\d+,\s*(\d+),',line)
                    if match:counts[int(match[1])]+=1
        afterdb=sqlite3.connect(':memory:');afterdb.row_factory=sqlite3.Row
        for stem in ('master_countries','countries'):
            afterdb.executescript((data/'reference_tables'/f'{stem}.sqlite.sql').read_text())
        entries=[]
        for master in afterdb.execute('SELECT * FROM MasterCountries ORDER BY CanonicalName'):
            editions=list(afterdb.execute('SELECT CountryID,Year FROM Countries WHERE MasterCountryID=?',(master['MasterCountryID'],)))
            if not editions:continue
            years={r['Year'] for r in editions};code=master['CanonicalCode'];iso=master['ISOAlpha2'] or ''
            entries.append(dict(name=master['CanonicalName'],fips=code,iso2=iso,type=master['EntityType'],first=min(years),last=max(years),years=len(years),fields=sum(counts[r['CountryID']] for r in editions),link_code=iso or code.lower()))
        (root/'docs/_entity_data.json').write_text(json.dumps({'entities':entries},separators=(',',':')))
    return {'edition_corrections':len(changes),'classifications':len(classifications),'new_historical_entity':bool(new_master),'trimmed_glossary_preamble':trimmed}


if __name__=='__main__':
    print(json.dumps(repair_exports(),indent=2))
