"""
Invoice price tracker
---------------------
Reads Mexican CFDI invoices (XML), keeps a history of what you paid for each
ingredient, and flags price increases.

Why XML and not OCR: in Mexico the stamped XML *is* the fiscal document; the PDF
is only a printed representation. The XML carries quantity, unit price, unit code
and UUID per line item, so there is nothing to "recognize" and no OCR errors.

Usage:
  python price_tracker.py import sample_invoices/            # load XML files or folders
  python price_tracker.py report --threshold 5               # flag increases >= 5 %
  python price_tracker.py report --json                      # machine-readable (for n8n)
  python price_tracker.py history "pollo"                    # full history of one item

Standard library only (defusedxml is used automatically if installed).
"""

import argparse
import csv
import json
import sqlite3
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

try:  # hardened parser: invoices come from third parties
    from defusedxml import ElementTree as ET
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET

DB_DEFAULT = "prices.db"

# SAT unit keys -> (family, factor to the base unit of that family)
# base units: kg for weight, l for volume, pza for everything else
UNIT_MAP = {
    "KGM": ("kg", Decimal(1)),
    "GRM": ("kg", Decimal("0.001")),
    "LTR": ("l", Decimal(1)),
    "MLT": ("l", Decimal("0.001")),
}


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def norm_text(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.upper().split())


def to_decimal(value, default=Decimal(0)) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError):
        return default


# ------------------------------------------------------------------ parsing

def parse_cfdi(path):
    """Return a dict with the invoice header and its line items, or None if the
    file is not an income invoice (credit notes, payment receipts, etc.)."""
    root = ET.parse(path).getroot()
    if local(root.tag) != "Comprobante":
        raise ValueError(f"{path}: not a CFDI (root is <{local(root.tag)}>)")

    tipo = root.get("TipoDeComprobante", "")
    if tipo != "I":  # I = ingreso; E = egreso (credit note), P = pago, T = traslado
        return None

    emisor = next((c for c in root if local(c.tag) == "Emisor"), None)
    conceptos = next((c for c in root if local(c.tag) == "Conceptos"), None)
    uuid = next(
        (e.get("UUID") for e in root.iter() if local(e.tag) == "TimbreFiscalDigital"),
        None,
    )
    if emisor is None or conceptos is None:
        raise ValueError(f"{path}: missing Emisor or Conceptos")

    items = []
    for c in conceptos:
        if local(c.tag) != "Concepto":
            continue
        items.append(
            {
                "description": c.get("Descripcion", ""),
                "sku": c.get("NoIdentificacion", ""),
                "qty": to_decimal(c.get("Cantidad")),
                "unit_key": c.get("ClaveUnidad", ""),
                "unit_price": to_decimal(c.get("ValorUnitario")),
            }
        )
    return {
        "uuid": uuid or f"NO-UUID:{Path(path).name}",
        "date": root.get("Fecha", "")[:10],
        "currency": root.get("Moneda", "MXN"),
        "supplier_rfc": emisor.get("Rfc", ""),
        "supplier": emisor.get("Nombre", ""),
        "items": items,
    }


def normalize_price(unit_price: Decimal, unit_key: str):
    """Price per base unit (kg / l / pza) so grams and kilos compare correctly."""
    family, factor = UNIT_MAP.get(unit_key, (unit_key or "pza", Decimal(1)))
    return family, unit_price / factor


# ------------------------------------------------------------------ aliases

def load_aliases(path):
    """CSV with columns: pattern,ingredient. If an invoice description contains the
    pattern (accent/case-insensitive) the line is stored under that ingredient."""
    aliases = []
    if path and Path(path).exists():
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                aliases.append((norm_text(row["pattern"]), row["ingredient"].strip()))
    return aliases


def ingredient_name(description: str, aliases) -> str:
    d = norm_text(description)
    for pattern, ingredient in aliases:
        if pattern and pattern in d:
            return ingredient
    return d.title()


# ------------------------------------------------------------------ storage

def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS purchases (
            uuid TEXT NOT NULL,
            line_no INTEGER NOT NULL,
            date TEXT NOT NULL,
            supplier_rfc TEXT,
            supplier TEXT,
            ingredient TEXT NOT NULL,
            description TEXT,
            qty TEXT,
            unit TEXT NOT NULL,
            unit_price TEXT NOT NULL,
            currency TEXT NOT NULL,
            PRIMARY KEY (uuid, line_no)
        )
        """
    )
    return conn


def import_files(conn, paths, aliases):
    files = []
    for p in map(Path, paths):
        files += sorted(p.glob("*.xml")) if p.is_dir() else [p]
    added = skipped = 0
    for f in files:
        try:
            inv = parse_cfdi(f)
        except Exception as e:
            print(f"! {f.name}: {e}", file=sys.stderr)
            continue
        if inv is None:
            print(f"- {f.name}: skipped (not an income invoice)")
            continue
        for n, it in enumerate(inv["items"], start=1):
            unit, price = normalize_price(it["unit_price"], it["unit_key"])
            cur = conn.execute(
                "INSERT OR IGNORE INTO purchases VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    inv["uuid"], n, inv["date"], inv["supplier_rfc"], inv["supplier"],
                    ingredient_name(it["description"], aliases), it["description"],
                    str(it["qty"]), unit, str(price), inv["currency"],
                ),
            )
            added += cur.rowcount
            skipped += 1 - cur.rowcount
    conn.commit()
    return added, skipped


# ------------------------------------------------------------------ analysis

def build_report(conn, threshold_pct):
    """For every ingredient (same unit and currency) compare the latest purchase
    with the one before it."""
    rows = conn.execute(
        "SELECT * FROM purchases ORDER BY ingredient, unit, currency, date, uuid, line_no"
    ).fetchall()
    groups = {}
    for r in rows:
        groups.setdefault((r["ingredient"], r["unit"], r["currency"]), []).append(r)

    report = []
    for (ingredient, unit, currency), purchases in groups.items():
        last = purchases[-1]
        prev = purchases[-2] if len(purchases) > 1 else None
        last_price = Decimal(last["unit_price"])
        change = None
        if prev is not None:
            prev_price = Decimal(prev["unit_price"])
            if prev_price > 0:
                change = (last_price - prev_price) / prev_price * 100
        report.append(
            {
                "ingredient": ingredient,
                "unit": unit,
                "currency": currency,
                "last_date": last["date"],
                "last_supplier": last["supplier"],
                "last_price": float(round(last_price, 2)),
                "previous_price": float(round(Decimal(prev["unit_price"]), 2)) if prev else None,
                "change_pct": float(round(change, 1)) if change is not None else None,
                "alert": bool(change is not None and change >= Decimal(str(threshold_pct))),
                "purchases": len(purchases),
            }
        )
    report.sort(key=lambda r: (not r["alert"], -(r["change_pct"] or -999)))
    return report


def print_report(report, threshold_pct):
    if not report:
        print("No data. Run `import` first.")
        return
    print(f"Price changes (alert at +{threshold_pct}%)\n")
    print(f"{'':2}{'Ingredient':<26}{'Unit':<5}{'Previous':>10}{'Last':>10}{'Change':>9}  Supplier")
    for r in report:
        flag = "▲ " if r["alert"] else "  "
        prev = f"{r['previous_price']:.2f}" if r["previous_price"] is not None else "-"
        chg = f"{r['change_pct']:+.1f}%" if r["change_pct"] is not None else "n/a"
        print(f"{flag}{r['ingredient'][:25]:<26}{r['unit']:<5}{prev:>10}{r['last_price']:>10.2f}{chg:>9}  {r['last_supplier']}")


def print_history(conn, text):
    pat = f"%{norm_text(text)}%"
    rows = conn.execute(
        "SELECT * FROM purchases WHERE UPPER(ingredient) LIKE ? OR UPPER(description) LIKE ? "
        "ORDER BY ingredient, date",
        (pat, pat),
    ).fetchall()
    if not rows:
        print("No matches.")
        return
    for r in rows:
        print(f"{r['date']}  {r['ingredient']:<24} {Decimal(r['unit_price']):>9.2f}/{r['unit']:<3} {r['supplier']}")


# ------------------------------------------------------------------ CLI

def main(argv=None):
    ap = argparse.ArgumentParser(description="Track ingredient prices from CFDI XML invoices")
    ap.add_argument("--db", default=DB_DEFAULT)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_imp = sub.add_parser("import", help="load XML files or folders")
    p_imp.add_argument("paths", nargs="+")
    p_imp.add_argument("--aliases", help="CSV with columns pattern,ingredient")

    p_rep = sub.add_parser("report", help="latest vs previous price per ingredient")
    p_rep.add_argument("--threshold", type=float, default=5.0)
    p_rep.add_argument("--json", action="store_true")

    p_his = sub.add_parser("history", help="purchase history for an ingredient")
    p_his.add_argument("text")

    args = ap.parse_args(argv)
    conn = connect(args.db)

    if args.cmd == "import":
        added, skipped = import_files(conn, args.paths, load_aliases(args.aliases))
        print(f"Imported {added} line items ({skipped} already in the database).")
    elif args.cmd == "report":
        report = build_report(conn, args.threshold)
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            print_report(report, args.threshold)
    elif args.cmd == "history":
        print_history(conn, args.text)


if __name__ == "__main__":
    main()
