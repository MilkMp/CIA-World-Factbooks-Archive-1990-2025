"""Focused reader-edition coverage, including bare and direct lookups."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from etl.stardict.build_reader_stardict import build_entries, country_codes
from etl.stardict.package_reader_stardict import package_year, sha256


class ReaderEditionTest(unittest.TestCase):
    def setUp(self):
        self.rows = [
            (1, 10, "Afghanistan", "af", "Introduction", "Background",
             "First line\nSecond <line>", 100, 1000),
            (1, 10, "Afghanistan", "af", "Geography", "Area",
             "total: 652,230 sq km | land: 652,230 sq km", 101, 1001),
            (2, 20, "Comoros", "cn", "Introduction", "Background",
             "Island nation", 200, 2000),
        ]
        self.masters = {10: ("AF", "AF"), 20: ("KM", "CN"), 30: ("CN", "CH")}
        self.owners = {"AF": 10, "KM": 20, "CN": 30}

    def test_country_category_and_field_entries(self):
        entries, countries, fields = build_entries(
            self.rows, self.masters, self.owners, 2025
        )
        by_name = {words[0]: (words, body) for words, body in entries}
        self.assertEqual((countries, fields), (2, 3))
        self.assertEqual(len(entries), 8)
        self.assertIn("AF", by_name["Afghanistan"][0])
        self.assertIn("Afghanistan Geography", by_name)
        self.assertIn("AF Geography", by_name["Afghanistan Geography"][0])
        self.assertIn("Afghanistan - Area", by_name)
        self.assertIn("AF - Area", by_name["Afghanistan - Area"][0])
        self.assertIn("<h3>Afghanistan: Geography</h3>", by_name["Afghanistan"][1])
        self.assertIn("Second &lt;line&gt;", by_name["Afghanistan"][1])
        self.assertIn("First line<br/>Second", by_name["Afghanistan"][1])
        self.assertIn("total: 652,230 sq km<br/>land:",
                      by_name["Afghanistan Geography"][1])

    def test_iso_collision_does_not_steal_china_alias(self):
        self.assertEqual(country_codes("Comoros", 20, "cn", self.masters,
                                       self.owners, {"KM": 1}),
                         ["Comoros", "KM"])

    def test_historical_name_remains_primary(self):
        codes = country_codes("Cape Verde", 10, "af", self.masters,
                              self.owners, {"AF": 1})
        self.assertEqual(codes[0], "Cape Verde")

    def test_split_country_does_not_get_ambiguous_iso_alias(self):
        rows = [
            (1, 99, "German Democratic Republic", "ge", "Introduction",
             "Background", "East", 1, 1),
            (2, 99, "Germany, Federal Republic of", "gm", "Introduction",
             "Background", "West", 2, 2),
        ]
        entries, _, _ = build_entries(rows, {99: ("DE", "GM")}, {"DE": 99}, 1990)
        aliases = [alias for words, _ in entries for alias in words[1:]]
        self.assertNotIn("DE", aliases)
        self.assertIn("GE", aliases)
        self.assertIn("GM", aliases)

    def test_package_has_only_four_files_and_is_reproducible(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            name = "cia-factbook-2025-reader"
            source = root / "dicts" / name
            source.mkdir(parents=True)
            for suffix in ("ifo", "idx", "dict.dz", "syn"):
                (source / f"{name}.{suffix}").write_bytes(suffix.encode("ascii"))
            first = root / "first"
            second = root / "second"
            first.mkdir()
            second.mkdir()
            archive = package_year(root / "dicts", first, 2025)
            self.assertEqual(sha256(archive), sha256(package_year(root / "dicts", second, 2025)))
            with self.assertRaises(FileExistsError):
                package_year(root / "dicts", first, 2025)


if __name__ == "__main__":
    unittest.main()
