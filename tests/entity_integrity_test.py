import importlib.util
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from repair_entity_integrity import apply, plan


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class RepairTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
            PRAGMA foreign_keys=ON;
            CREATE TABLE MasterCountries(MasterCountryID INTEGER PRIMARY KEY,CanonicalCode,CanonicalName,ISOAlpha2,EntityType,AdministeringMasterCountryID);
            CREATE TABLE Countries(CountryID INTEGER PRIMARY KEY,Year,Code,Name,Source,MasterCountryID REFERENCES MasterCountries);
            CREATE TABLE CountryCategories(CategoryID INTEGER PRIMARY KEY,CountryID REFERENCES Countries,CategoryTitle);
            CREATE TABLE CountryFields(FieldID INTEGER PRIMARY KEY,CategoryID REFERENCES CountryCategories,CountryID REFERENCES Countries,FieldName,Content);
            CREATE TABLE FieldValues(ValueID INTEGER PRIMARY KEY,FieldID REFERENCES CountryFields,NumericVal);
            CREATE VIRTUAL TABLE CountryFieldsFTS USING fts5(Content,content=CountryFields,content_rowid=FieldID);
            INSERT INTO MasterCountries VALUES(7,'GG','Georgia','GE','territory',NULL),(8,'ZI','Zimbabwe','ZW','territory',NULL),
              (10,'CW','Cook Islands','CK','territory',NULL),(11,'NE','Niue','NU','territory',NULL),
              (9,'SX','South Georgia and the South Sandwich Islands','GS','territory',NULL);
            INSERT INTO Countries VALUES(31,1997,'gg','Georgia','text',7),(32,1997,'gg','South Georgia and the','text',7),(33,1998,'zi','Zimbabwe','text',8);
            INSERT INTO CountryCategories VALUES(41,32,'Government'),(42,33,'Transnational Issues');
            INSERT INTO CountryFields VALUES(51,41,32,'Dependency status','dependent territory of the UK'),
              (52,42,33,'Disputes-international','quadripoint disagreement'),
              (53,42,33,'Illicit drugs','authentic text | @NOTES AND DEFINITIONS | appendix');
        ''')
        # Reproduce all 176 appendix rows, including names also used by real fields.
        for i in range(176):
            name = ['Dependency status','Disputes-international','Illicit drugs'][i] if i<3 else f'Glossary {i}'
            content = 'This entry describes the formal relationship between a nonindependent entity and a state.' if i==0 else 'This entry is a definition.'
            self.db.execute('INSERT INTO CountryFields VALUES(?,?,33,?,?)',(100+i,42,name,content))
        self.db.execute('INSERT INTO FieldValues VALUES(1,100,1998)')
        self.db.execute("INSERT INTO CountryFieldsFTS(CountryFieldsFTS) VALUES('rebuild')")
        self.db.commit()

    def test_repair_preserves_real_fields_and_is_idempotent(self):
        result = plan(self.db)
        self.assertEqual(len(result['glossary_fields']),176)
        self.assertEqual(len(result['classifications']),4)
        with self.db:
            apply(self.db,result)
        self.assertEqual(self.db.execute('SELECT MasterCountryID FROM Countries WHERE CountryID=32').fetchone()[0],9)
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM CountryFields').fetchone()[0],3)
        self.assertEqual(self.db.execute('SELECT Content FROM CountryFields WHERE FieldID=53').fetchone()[0],'authentic text')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM FieldValues').fetchone()[0],0)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM CountryFieldsFTS WHERE CountryFieldsFTS MATCH 'definition'").fetchone()[0],0)
        self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])
        self.assertFalse(any(plan(self.db).values()))

    def test_duplicate_target_stops_before_any_write(self):
        self.db.execute("INSERT INTO Countries VALUES(34,1997,'sx','South Georgia and the South Sandwich Islands','text',9)")
        with self.assertRaisesRegex(ValueError,'Target edition already exists'):
            plan(self.db)
        self.assertEqual(self.db.execute("SELECT EntityType FROM MasterCountries WHERE CanonicalCode='GG'").fetchone()[0],'territory')

    def test_unexpected_appendix_is_not_deleted(self):
        self.db.execute('DELETE FROM CountryFields WHERE FieldID=275')
        with self.assertRaisesRegex(ValueError,'Unexpected Zimbabwe appendix'):
            plan(self.db)


class ExportTest(unittest.TestCase):
    def test_un_member_classifications_and_published_identities(self):
        import csv
        from repair_entity_integrity import IDENTITIES
        db=sqlite3.connect(':memory:')
        for stem in ('master_countries','countries'):
            db.executescript((ROOT/'data/reference_tables'/f'{stem}.sqlite.sql').read_text())
        with (ROOT/'data/lookup_tables/un_member_classifications.csv').open() as source:
            members=list(csv.DictReader(source))
        self.assertEqual(len(members),193)
        self.assertEqual(len({r['ISOAlpha2'] for r in members}),193)
        for row in members:
            found=db.execute('SELECT EntityType FROM MasterCountries WHERE ISOAlpha2=?',(row['ISOAlpha2'],)).fetchall()
            self.assertIn((row['ExpectedArchiveType'],),found,row)
        for name,(target,_) in IDENTITIES.items():
            rows=db.execute("SELECT c.Code,m.CanonicalCode FROM Countries c LEFT JOIN MasterCountries m USING(MasterCountryID) WHERE lower(c.Name)=? AND c.Source='text'",(name,)).fetchall()
            self.assertTrue(all(r==(target.lower(),target) for r in rows),(name,rows))


class ImportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.loader = module('loader',ROOT/'etl/load_gutenberg_years.py')
        cls.classifier = module('classifier',ROOT/'etl/classify_entities.py')

    def test_matching_never_guesses_a_country_prefix(self):
        mapping = {'georgia': (1,'gg'),'canada':(2,'ca'),'iraq':(3,'iz')}
        for name in ['South Georgia and the','Cape Verde','Iraq - Saudi Arabia Neutral Zone']:
            self.assertEqual(self.loader.find_master_match(name,mapping),(None,None))
        with self.assertRaisesRegex(ValueError,'no data deleted'):
            self.loader.validate_country_matches([('Cape Verde',[])],mapping)

    def test_exact_reviewed_aliases_resolve(self):
        class Cursor:
            def execute(self,*args): pass
            def fetchall(self): return [(1,'GG','Georgia'),(2,'SX','South Georgia and the South Sandwich Islands'),(3,'CV','Cabo Verde'),(4,'IM','Isle of Man')]
        mapping,_ = self.loader.build_name_to_master_map(Cursor())
        for name, code in [('South Georgia and the','sx'),('Cape Verde','cv'),('Man, Isle Of','im')]:
            self.assertEqual(self.loader.find_master_match(name,mapping)[1],code)

    def test_glossary_is_not_parsed_as_zimbabwe(self):
        text = '@Zimbabwe:Transnational Issues\nIllicit drugs: authentic\n@NOTES AND DEFINITIONS\nDependency status: This entry describes a dependency\n'
        parsed = self.loader.parse_atsign_format(text)
        self.assertEqual(parsed,[('Zimbabwe',[('Transnational Issues',[('Illicit drugs','authentic')])])])

    def test_classifier_ignores_definitions_and_prioritizes_free_association(self):
        self.assertEqual(self.classifier.classify('This entry describes a territory','republic','XXTEST','Test')[0],'sovereign')
        self.assertEqual(self.classifier.classify('self-governing in free association','','TEST','Test')[0],'freely_associated')
        for code,name in [('GG','Georgia'),('ZI','Zimbabwe')]:
            self.assertEqual(self.classifier.classify('dependent territory','republic',code,name)[0],'sovereign')

    def test_both_fields_query_only_the_latest_edition(self):
        class Cursor:
            queries=[]
            def execute(self,sql,*args): self.queries.append(sql)
            def fetchone(self): return None
        cursor=Cursor()
        self.classifier.get_gov_fields(cursor,1)
        self.assertEqual(len(cursor.queries),2)
        for sql in cursor.queries:
            self.assertIn('c.Year = (SELECT MAX(Year)',sql)


if __name__ == '__main__':
    unittest.main()
