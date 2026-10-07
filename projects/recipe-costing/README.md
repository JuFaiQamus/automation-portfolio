# Recipe Costing + Menu Engineering

Turns three small files (recipes, menu, ingredient prices) into a food-cost report and tells you what to do with each dish. It can read prices straight from the [invoice price tracker](../invoice-price-tracker), so a supplier price change shows up in your dish margins.

```
$ python recipe_costing.py --recipes sample_data/recipes.csv --menu sample_data/menu.csv \
      --prices sample_data/prices.csv --target-food-cost 32 --commission 25

Dish                             Price    Cost   FC %   Margin   Net@-25%  Units  Class
Chicken Bowl                    129.00   27.18  21.1    101.82      69.57    320  Star
Thigh Bowl                      109.00   16.98  15.6     92.02      64.77    210  Star
Avocado Veggie Bowl             119.00   20.26  17.0     98.74      68.99     90  Puzzle
Loaded Chicken Bowl             159.00   39.08  24.6    119.92      80.17     70  Puzzle
Green Smoothie                   69.00   18.77  27.2     50.23      32.98    150  Plowhorse
Chips & Guacamole                69.00   14.97  21.7     54.03      36.78     40  Dog
```

## How the cost is calculated

For each ingredient line: `quantity ÷ yield % × price per kg (or l / piece)`.

The **yield %** is what makes this useful in a real kitchen: if you buy avocado at $62/kg but only 70 % ends up on the plate (peel and pit), 60 g on the plate costs `0.060 ÷ 0.70 × 62 = $5.31`, not $3.72. Quantities in `g`, `kg`, `ml`, `l` and `pza` are converted automatically, and a recipe that mixes weight and volume against a price is rejected with a clear message.

## Menu engineering

Each dish is classified with the classic Kasavana & Smith matrix, using the common convention for the thresholds:

| | High margin | Low margin |
|---|---|---|
| **Popular** | ⭐ Star: protect it | 🐴 Plowhorse: review portion/cost or raise the price a little |
| **Not popular** | 🧩 Puzzle: reposition, rename, have staff suggest it | 🐕 Dog: rework or remove |

- *Popular* = sells at least 70 % of an equal share of the menu (`0.7 × 1/number of dishes`).
- *High margin* = contribution margin ($ per plate) at or above the sales-weighted average.

Optional flags: `--target-food-cost 32` marks dishes above that food-cost %, and `--commission 25` adds the margin left after a delivery platform's fee.

## Validated against a real restaurant

I ran it on a real restaurant's costing workbook (16 menu items, 138 recipe lines, ingredient prices with yield losses, and sub-recipes such as sauces priced per kg). Every dish cost matched the workbook to the cent (largest difference: 0.00 MXN). Details are kept anonymous; no client data is in this repository.

Running it also surfaced two things in the original workbook that deserved a second look:

- An ingredient bought **by the piece** was entered with a quantity that did not match the recipe book's weight, so that component was most likely under-costed (a small amount per plate, but multiplied across every order).
- Several liquids were entered in grams against a per-litre price. The script rejects this by design; the workbook silently treated 1 g as 1 ml. I made the 1 g = 1 ml convention explicit in the data.

On the real menu, the `--target-food-cost` flag immediately singled out the few items above a 30 % food cost.

## Connect it to supplier invoices

```bash
python ../invoice-price-tracker/price_tracker.py import invoices/ --aliases aliases.csv
python recipe_costing.py --recipes recipes.csv --menu menu.csv --prices prices.csv \
       --prices-db ../invoice-price-tracker/prices.db
```

Prices from your latest invoice override `prices.csv`; ingredients without an invoice keep their CSV price. In the sample data this moves the Chicken Bowl's cost from $27.18 to $29.51 after the chicken price increase.

## Files

| File | Columns |
|---|---|
| `recipes.csv` | `dish, ingredient, qty, unit, yield_pct` (blank yield = 100) |
| `menu.csv` | `dish, price, units_sold` |
| `prices.csv` | `ingredient, unit, price` (price per `unit`) |

Ingredient names must match between files (case and accents are ignored). `--json` prints the same report for use in n8n or a dashboard.

## Tests and limits

```bash
python -m unittest discover -s tests    # 12 tests, including a hand-calculated dish cost
```

- All sample data is **fictitious**. Replace it with your own recipes, prices and sales.
- Cost covers ingredients only: labor, packaging and overhead are not included yet.
- Sub-recipes (sauces, bases) are not supported; list their ingredients directly in the dish.
- `units_sold` should cover a representative period (for example, four weeks). A few days of data can misclassify dishes.

**Stack:** Python 3 (standard library), CSV, SQLite.
