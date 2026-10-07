import sqlite3
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import recipe_costing as rc  # noqa: E402

DATA = ROOT / "sample_data"


def sample():
    prices = rc.load_prices(csv_path=DATA / "prices.csv")
    recipes = rc.load_recipes(DATA / "recipes.csv")
    menu = rc.load_menu(DATA / "menu.csv")
    return recipes, menu, prices


class CostTests(unittest.TestCase):
    def test_chicken_bowl_cost_matches_hand_calculation(self):
        # 150 g breast @78/kg with 85 % yield + 120 g rice @28 + 80 g beans @38
        # + 60 g avocado @62 with 70 % yield + 10 g lime @30 + 10 ml oil @140/l
        recipes, menu, prices = sample()
        cost, _ = rc.dish_cost("Chicken Bowl", recipes["Chicken Bowl"], prices)
        expected = (Decimal("0.150") / Decimal("0.85") * 78 + Decimal("0.120") * 28
                    + Decimal("0.080") * 38 + Decimal("0.060") / Decimal("0.70") * 62
                    + Decimal("0.010") * 30 + Decimal("0.010") * 140)
        self.assertEqual(round(cost, 6), round(expected, 6))

    def test_lower_yield_raises_cost(self):
        _, _, prices = sample()
        full = [{"ingredient": "Avocado", "qty": Decimal(100), "unit": "g", "yield_pct": Decimal(100)}]
        trimmed = [{**full[0], "yield_pct": Decimal(50)}]
        c_full, _ = rc.dish_cost("x", full, prices)
        c_trim, _ = rc.dish_cost("x", trimmed, prices)
        self.assertEqual(c_trim, c_full * 2)

    def test_invoice_price_overrides_csv_price(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "p.db"
            conn = sqlite3.connect(db)
            conn.execute("CREATE TABLE purchases (uuid TEXT, line_no INT, date TEXT, ingredient TEXT, "
                         "unit TEXT, unit_price TEXT)")
            conn.executemany("INSERT INTO purchases VALUES (?,?,?,?,?,?)", [
                ("A", 1, "2026-09-01", "Chicken breast", "kg", "78.00"),
                ("B", 1, "2026-09-15", "Chicken breast", "kg", "86.58"),
            ])
            conn.commit()
            conn.close()
            prices = rc.load_prices(csv_path=DATA / "prices.csv", db_path=db)
        base, price, source = prices[rc.key("Chicken breast")]
        self.assertEqual((base, price, source), ("kg", Decimal("86.58"), "invoice"))
        self.assertEqual(prices[rc.key("Rice")][2], "csv")  # untouched ingredient keeps CSV price


class ErrorTests(unittest.TestCase):
    def test_missing_price_is_reported(self):
        _, _, prices = sample()
        with self.assertRaisesRegex(rc.DataError, "no price for Saffron"):
            rc.dish_cost("x", [{"ingredient": "Saffron", "qty": Decimal(1), "unit": "g",
                                "yield_pct": Decimal(100)}], prices)

    def test_unit_family_mismatch_is_reported(self):
        _, _, prices = sample()
        with self.assertRaisesRegex(rc.DataError, "price is per kg"):
            rc.dish_cost("x", [{"ingredient": "Rice", "qty": Decimal(100), "unit": "ml",
                                "yield_pct": Decimal(100)}], prices)

    def test_unknown_unit_is_reported(self):
        with self.assertRaisesRegex(rc.DataError, "Unknown unit"):
            rc.to_base(Decimal(1), "cup")


class EngineeringTests(unittest.TestCase):
    def setUp(self):
        recipes, menu, prices = sample()
        self.rows = {r["dish"]: r for r in rc.analyze(recipes, menu, prices, 20, Decimal(25))}

    def test_all_four_classes_appear_in_sample(self):
        self.assertEqual({r["class"] for r in self.rows.values()},
                         {"Star", "Plowhorse", "Puzzle", "Dog"})

    def test_expected_classes(self):
        self.assertEqual(self.rows["Chicken Bowl"]["class"], "Star")
        self.assertEqual(self.rows["Green Smoothie"]["class"], "Plowhorse")
        self.assertEqual(self.rows["Loaded Chicken Bowl"]["class"], "Puzzle")
        self.assertEqual(self.rows["Chips & Guacamole"]["class"], "Dog")

    def test_target_food_cost_flag(self):
        self.assertTrue(self.rows["Green Smoothie"]["over_target"])   # 27.2 % > 20 %
        self.assertFalse(self.rows["Thigh Bowl"]["over_target"])      # 15.6 % < 20 %

    def test_net_margin_after_commission(self):
        r = self.rows["Chicken Bowl"]
        self.assertEqual(r["net_margin"], r["price"] * Decimal("0.75") - r["cost"])

    def test_no_sales_does_not_crash(self):
        recipes, menu, prices = sample()
        for m in menu:
            m["units"] = 0
        rows = rc.analyze(recipes, menu, prices)
        self.assertTrue(all(r["class"] == "n/a" for r in rows))

    def test_dish_without_recipe_is_reported(self):
        recipes, menu, prices = sample()
        menu.append({"dish": "Ghost Dish", "price": Decimal(50), "units": 1})
        with self.assertRaisesRegex(rc.DataError, "no recipe"):
            rc.analyze(recipes, menu, prices)


if __name__ == "__main__":
    unittest.main()
