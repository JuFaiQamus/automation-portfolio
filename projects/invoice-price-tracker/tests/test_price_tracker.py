import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import price_tracker as pt  # noqa: E402

SAMPLES = ROOT / "sample_invoices"
ALIASES = pt.load_aliases(SAMPLES / "aliases.csv")


class ParseTests(unittest.TestCase):
    def test_parses_header_and_items(self):
        inv = pt.parse_cfdi(SAMPLES / "carnes_2026-09-15_003.xml")
        self.assertEqual(inv["date"], "2026-09-15")
        self.assertEqual(inv["supplier_rfc"], "AAA010101AAA")
        self.assertEqual(len(inv["items"]), 2)
        self.assertEqual(inv["items"][0]["unit_price"], Decimal("86.58"))
        self.assertRegex(inv["uuid"], r"^[0-9A-F-]{36}$")

    def test_credit_note_is_skipped(self):
        self.assertIsNone(pt.parse_cfdi(SAMPLES / "carnes_2026-09-16_006.xml"))

    def test_rejects_non_cfdi_xml(self):
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "x.xml"
            bad.write_text("<root/>", encoding="utf-8")
            with self.assertRaises(ValueError):
                pt.parse_cfdi(bad)


class UnitTests(unittest.TestCase):
    def test_grams_are_converted_to_kilos(self):
        unit, price = pt.normalize_price(Decimal("0.03"), "GRM")
        self.assertEqual(unit, "kg")
        self.assertEqual(price, Decimal("30"))

    def test_unknown_unit_is_kept(self):
        unit, price = pt.normalize_price(Decimal("12"), "H87")
        self.assertEqual((unit, price), ("H87", Decimal("12")))


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = pt.connect(str(Path(self.tmp.name) / "t.db"))
        pt.import_files(self.conn, [SAMPLES], ALIASES)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_import_is_idempotent(self):
        added, skipped = pt.import_files(self.conn, [SAMPLES], ALIASES)
        self.assertEqual(added, 0)
        self.assertEqual(skipped, 10)

    def test_chicken_breast_alert(self):
        report = {r["ingredient"]: r for r in pt.build_report(self.conn, 5)}
        self.assertTrue(report["Chicken breast"]["alert"])
        self.assertEqual(report["Chicken breast"]["change_pct"], 11.0)

    def test_flat_price_is_not_alerted(self):
        report = {r["ingredient"]: r for r in pt.build_report(self.conn, 5)}
        self.assertFalse(report["Chicken thigh"]["alert"])

    def test_threshold_is_respected(self):
        report = {r["ingredient"]: r for r in pt.build_report(self.conn, 12)}
        self.assertFalse(report["Chicken breast"]["alert"])  # +11 % < 12 %
        self.assertTrue(report["Avocado"]["alert"])          # +15 % >= 12 %

    def test_credit_note_does_not_enter_history(self):
        n = self.conn.execute("SELECT COUNT(*) FROM purchases").fetchone()[0]
        self.assertEqual(n, 10)


if __name__ == "__main__":
    unittest.main()
