# Invoice Price Tracker

Reads Mexican **CFDI invoices (XML)** from your suppliers, keeps a price history per ingredient, and flags increases, so a cost change reaches the kitchen before it reaches the margin.

```
$ python price_tracker.py report --threshold 5

  Ingredient                Unit   Previous      Last   Change  Supplier
▲ Avocado                   kg        62.00     71.30   +15.0%  VERDURAS DEMO SA DE CV
▲ Chicken breast            kg        78.00     86.58   +11.0%  CARNES DEMO SA DE CV
▲ Lime                      kg        30.00     32.00    +6.7%  VERDURAS DEMO SA DE CV
  Chicken thigh             kg        53.00     53.00    +0.0%  CARNES DEMO SA DE CV
```

## Why XML instead of OCR

In Mexico the stamped XML is the fiscal document; the PDF is only a printed copy. The XML already carries quantity, unit key, unit price and UUID per line, so there is nothing to recognize and no OCR error to correct. OCR is only needed for purchases without an invoice (market vendors), which this project does not cover.

## Quick start

```bash
python price_tracker.py import sample_invoices/ --aliases sample_invoices/aliases.csv
python price_tracker.py report --threshold 5
python price_tracker.py history avocado
python price_tracker.py report --json        # for n8n or any other automation
python -m unittest discover -s tests         # 10 tests
```

Python 3.9+, standard library only. If `defusedxml` is installed it is used automatically (recommended, since invoices come from third parties).

## What it does

- Parses CFDI XML (any version: it reads the namespace from the file) and keeps **income invoices only**. Credit notes and payment receipts are skipped.
- **Normalizes units** so grams and kilos compare correctly (`GRM` → kg, `MLT` → l).
- **Aliases:** a small CSV maps supplier descriptions to your ingredient names (`PECHUGA DE POLLO S/H` → `Chicken breast`).
- **Idempotent import:** each line is keyed by invoice UUID + line number, so re-importing the same folder never duplicates data.
- Compares the latest purchase with the previous one per ingredient (same unit and currency) and alerts above a threshold.

## Using it from n8n

`report --json` prints a list of objects with `ingredient`, `last_price`, `previous_price`, `change_pct` and `alert`. An n8n workflow can run the script on a schedule (Execute Command node, or a small HTTP wrapper), filter `alert == true` and send a WhatsApp or email summary.

## Limits and next steps

- The sample invoices are **fictitious and simplified**. They follow the CFDI 4.0 structure but are not valid fiscal documents. **Validate the parser with several real supplier XMLs before relying on it**: suppliers fill descriptions and unit keys inconsistently, and that is where the aliases file earns its keep.
- Only price changes are tracked; the next step is joining prices with recipes to show the effect on each dish's food cost.
- Comparing across suppliers and a drop-folder or email-inbox ingestion step are not implemented yet.
- Amounts are compared per purchase; discounts and taxes at line level are ignored.

**Stack:** Python 3, SQLite, XML (CFDI).
