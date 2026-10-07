"""
Recipe costing + menu engineering
---------------------------------
Combines three small files into a food-cost report for a menu:

  recipes.csv  dish, ingredient, qty, unit, yield_pct    (what goes into each dish)
  menu.csv     dish, price, units_sold                    (what it sells for and how much it sells)
  prices.csv   ingredient, unit, price                    (fallback ingredient prices)

and, optionally, the SQLite database built by ../invoice-price-tracker, so that
ingredient prices always come from your latest supplier invoice.

Usage:
  python recipe_costing.py --recipes sample_data/recipes.csv --menu sample_data/menu.csv \
         --prices sample_data/prices.csv
  python recipe_costing.py ... --prices-db ../invoice-price-tracker/prices.db   # latest invoice price wins
  python recipe_costing.py ... --target-food-cost 32 --commission 25 --json

Standard library only.
"""

import argparse
import csv
import json
import sqlite3
import sys
import unicodedata
from decimal import Decimal, InvalidOperation

# unit -> (base unit, factor to base)
UNITS = {
    "g": ("kg", Decimal("0.001")),
    "kg": ("kg", Decimal(1)),
    "ml": ("l", Decimal("0.001")),
    "l": ("l", Decimal(1)),
    "pza": ("pza", Decimal(1)),
}

ACTIONS = {
    "Star": "Protect it: keep quality and portion consistent, feature it.",
    "Plowhorse": "Popular but thin margin: review portion, ingredients or raise the price slightly.",
    "Puzzle": "Good margin but few orders: reposition on the menu, rename, or have staff suggest it.",
    "Dog": "Low sales and low margin: rework the recipe or consider removing it.",
}


class DataError(Exception):
    pass


def key(name: str) -> str:
    s = unicodedata.normalize("NFKD", name or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.casefold().split())


def dec(value, what):
    try:
        return Decimal(str(value).strip())
    except InvalidOperation:
        raise DataError(f"Invalid number for {what}: {value!r}")


def to_base(qty: Decimal, unit: str):
    unit = unit.strip().lower()
    if unit not in UNITS:
        raise DataError(f"Unknown unit {unit!r}. Use one of: {', '.join(UNITS)}")
    base, factor = UNITS[unit]
    return base, qty * factor


# ------------------------------------------------------------------ loading

def read_csv(path, required):
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if rows:
        missing = [c for c in required if c not in rows[0]]
        if missing:
            raise DataError(f"{path}: missing column(s) {', '.join(missing)}")
    return rows


def load_prices(csv_path=None, db_path=None):
    """ingredient key -> (base unit, price per base unit, source)."""
    prices = {}
    if csv_path:
        for r in read_csv(csv_path, ["ingredient", "unit", "price"]):
            base, factor = to_base(Decimal(1), r["unit"])
            prices[key(r["ingredient"])] = (base, dec(r["price"], "price") / factor, "csv")
    if db_path:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT ingredient, unit, unit_price FROM purchases ORDER BY date, uuid, line_no"
        ).fetchall()
        conn.close()
        for ingredient, unit, unit_price in rows:  # later rows overwrite earlier ones
            base = unit if unit in ("kg", "l") else "pza"
            prices[key(ingredient)] = (base, dec(unit_price, "unit_price"), "invoice")
    return prices


def load_recipes(path):
    recipes = {}
    for r in read_csv(path, ["dish", "ingredient", "qty", "unit"]):
        yield_pct = dec(r.get("yield_pct") or 100, "yield_pct")
        if not (0 < yield_pct <= 100):
            raise DataError(f"yield_pct must be between 1 and 100 ({r['dish']} / {r['ingredient']})")
        recipes.setdefault(r["dish"].strip(), []).append(
            {"ingredient": r["ingredient"].strip(), "qty": dec(r["qty"], "qty"),
             "unit": r["unit"], "yield_pct": yield_pct}
        )
    return recipes


def load_menu(path):
    return [
        {"dish": r["dish"].strip(), "price": dec(r["price"], "price"),
         "units": int(dec(r["units_sold"], "units_sold"))}
        for r in read_csv(path, ["dish", "price", "units_sold"])
    ]


# ------------------------------------------------------------------ costing

def dish_cost(dish, lines, prices):
    total = Decimal(0)
    detail = []
    missing = []
    for ln in lines:
        p = prices.get(key(ln["ingredient"]))
        if p is None:
            missing.append(ln["ingredient"])
            continue
        base, price, source = p
        line_base, qty_base = to_base(ln["qty"], ln["unit"])
        if line_base != base:
            raise DataError(
                f"{dish} / {ln['ingredient']}: recipe uses {ln['unit']} ({line_base}) "
                f"but the price is per {base}"
            )
        # yield: only part of what you buy is usable (trimming, peeling, cooking loss)
        cost = qty_base / (ln["yield_pct"] / 100) * price
        total += cost
        detail.append({"ingredient": ln["ingredient"], "cost": cost, "source": source})
    if missing:
        raise DataError(f"{dish}: no price for {', '.join(sorted(set(missing)))}")
    return total, detail


def analyze(recipes, menu, prices, target_food_cost=None, commission=Decimal(0)):
    rows = []
    for item in menu:
        lines = recipes.get(item["dish"])
        if not lines:
            raise DataError(f"{item['dish']}: in menu.csv but has no recipe")
        cost, detail = dish_cost(item["dish"], lines, prices)
        price = item["price"]
        margin = price - cost
        rows.append(
            {
                "dish": item["dish"],
                "price": price,
                "cost": cost,
                "food_cost_pct": cost / price * 100 if price else Decimal(0),
                "margin": margin,
                "net_margin": price * (1 - commission / 100) - cost,
                "units": item["units"],
                "detail": detail,
            }
        )

    # Menu engineering (Kasavana & Smith): classify by popularity and contribution margin.
    total_units = sum(r["units"] for r in rows)
    n = len(rows)
    if total_units and n:
        pop_threshold = Decimal("0.7") * Decimal(1) / n          # 70 % of an equal share
        avg_margin = sum(r["margin"] * r["units"] for r in rows) / total_units
        for r in rows:
            mix = Decimal(r["units"]) / total_units
            popular = mix >= pop_threshold
            profitable = r["margin"] >= avg_margin
            r["mix_pct"] = mix * 100
            r["class"] = (
                "Star" if popular and profitable else
                "Plowhorse" if popular else
                "Puzzle" if profitable else "Dog"
            )
            r["action"] = ACTIONS[r["class"]]
    else:
        for r in rows:
            r["mix_pct"], r["class"], r["action"] = Decimal(0), "n/a", "No sales data."
    for r in rows:
        r["over_target"] = bool(target_food_cost is not None and r["food_cost_pct"] > target_food_cost)
    return rows


# ------------------------------------------------------------------ output

def money(x):
    return f"{Decimal(x):,.2f}"


def print_table(rows, target, commission):
    net_col = f"Net@-{commission:g}%" if commission else None
    head = f"{'Dish':<22}{'Price':>8}{'Cost':>8}{'FC %':>7}{'Margin':>9}"
    head += f"{net_col:>11}" if net_col else ""
    head += f"{'Units':>7}  Class"
    print(head)
    for r in rows:
        flag = "!" if r["over_target"] else " "
        line = f"{r['dish'][:21]:<22}{money(r['price']):>8}{money(r['cost']):>8}"
        line += f"{r['food_cost_pct']:>6.1f}{flag}{money(r['margin']):>9}"
        line += f"{money(r['net_margin']):>11}" if net_col else ""
        line += f"{r['units']:>7}  {r['class']}"
        print(line)
    if target is not None:
        print(f"\n! = food cost above the {target:g}% target")
    print("\nWhat to do:")
    for cls in ("Star", "Plowhorse", "Puzzle", "Dog"):
        names = [r["dish"] for r in rows if r["class"] == cls]
        if names:
            print(f"  {cls:<10} {', '.join(names)}\n             {ACTIONS[cls]}")


def to_json(rows):
    out = []
    for r in rows:
        out.append({
            "dish": r["dish"], "price": float(r["price"]), "cost": round(float(r["cost"]), 2),
            "food_cost_pct": round(float(r["food_cost_pct"]), 1), "margin": round(float(r["margin"]), 2),
            "net_margin": round(float(r["net_margin"]), 2), "units": r["units"],
            "mix_pct": round(float(r["mix_pct"]), 1), "class": r["class"],
            "over_target": r["over_target"], "action": r["action"],
        })
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Recipe costing and menu engineering")
    ap.add_argument("--recipes", required=True)
    ap.add_argument("--menu", required=True)
    ap.add_argument("--prices", help="CSV with ingredient,unit,price")
    ap.add_argument("--prices-db", help="SQLite from invoice-price-tracker (latest invoice price wins)")
    ap.add_argument("--target-food-cost", type=float, help="flag dishes above this food cost %%")
    ap.add_argument("--commission", type=float, default=0.0, help="delivery platform fee %% for net margin")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    if not (args.prices or args.prices_db):
        ap.error("provide --prices and/or --prices-db")
    try:
        prices = load_prices(args.prices, args.prices_db)
        rows = analyze(load_recipes(args.recipes), load_menu(args.menu), prices,
                       args.target_food_cost, Decimal(str(args.commission)))
    except (DataError, OSError, sqlite3.Error) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(to_json(rows), ensure_ascii=False, indent=2))
    else:
        print_table(rows, args.target_food_cost, args.commission)
    return 0


if __name__ == "__main__":
    sys.exit(main())
