"""Quote / proposal PDF generator.

Turns a small JSON document into a branded PDF quote. Three ways to use it:

    python quote_generator.py sample_data/quote.json -o quote.pdf   # CLI
    python quote_generator.py --serve                               # HTTP service
    from quote_generator import build_quote                         # library

The HTTP mode (POST /quote with JSON, PDF in the response) is what lets an
n8n workflow generate a quote from a form, a chat or a CRM record using a
plain HTTP Request node.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

CENT = Decimal("0.01")
DEFAULT_TAX_RATE = Decimal("0.16")  # Mexican VAT (IVA)


class QuoteError(ValueError):
    """Raised when the input document is invalid."""


@dataclass(frozen=True)
class Totals:
    subtotal: Decimal
    discount: Decimal
    taxable: Decimal
    tax: Decimal
    total: Decimal


def money(value) -> Decimal:
    try:
        return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)
    except Exception as exc:  # decimal.InvalidOperation
        raise QuoteError(f"Invalid amount: {value!r}") from exc


def fmt(value: Decimal, currency: str = "MXN") -> str:
    return f"${value:,.2f} {currency}"


def line_total(item: dict) -> Decimal:
    qty = Decimal(str(item.get("quantity", 1)))
    if qty <= 0:
        raise QuoteError(f"Quantity must be positive: {item.get('description')!r}")
    price = money(item.get("unit_price"))
    if price < 0:
        raise QuoteError(f"Negative price: {item.get('description')!r}")
    return (qty * price).quantize(CENT, rounding=ROUND_HALF_UP)


def compute_totals(items: list[dict], discount_pct=0, tax_rate=DEFAULT_TAX_RATE) -> Totals:
    if not items:
        raise QuoteError("A quote needs at least one item")
    pct = Decimal(str(discount_pct))
    if not Decimal(0) <= pct <= Decimal(100):
        raise QuoteError("discount_pct must be between 0 and 100")
    subtotal = sum((line_total(i) for i in items), Decimal(0))
    discount = (subtotal * pct / 100).quantize(CENT, rounding=ROUND_HALF_UP)
    taxable = subtotal - discount
    tax = (taxable * Decimal(str(tax_rate))).quantize(CENT, rounding=ROUND_HALF_UP)
    return Totals(subtotal, discount, taxable, tax, taxable + tax)


def validate(data: dict) -> None:
    for key in ("client", "items"):
        if key not in data:
            raise QuoteError(f"Missing field: {key}")
    if not data["client"].get("name"):
        raise QuoteError("client.name is required")


def build_quote(data: dict, out_path) -> Totals:
    """Render the quote to ``out_path`` and return the computed totals."""
    validate(data)
    currency = data.get("currency", "MXN")
    totals = compute_totals(
        data["items"], data.get("discount_pct", 0), data.get("tax_rate", DEFAULT_TAX_RATE)
    )
    brand = data.get("issuer", {})
    accent = colors.HexColor(brand.get("accent_color", "#0B1F3A"))

    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=accent, alignment=0, fontSize=22)
    body = ParagraphStyle("b", parent=styles["BodyText"], fontSize=9.5, leading=13)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.grey)

    target = out_path if hasattr(out_path, "write") else str(out_path)
    doc = SimpleDocTemplate(target, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Quote {data.get('number', '')}".strip())
    story = [
        Paragraph(brand.get("name", "Quote"), h1),
        Paragraph(brand.get("contact", ""), small),
        Spacer(1, 8),
        Paragraph(f"<b>Quote {data.get('number', '')}</b> &nbsp; {data.get('date', '')}", body),
        Paragraph(f"<b>For:</b> {data['client']['name']}", body),
        Paragraph(data["client"].get("company", ""), body),
        Spacer(1, 10),
    ]

    rows = [["Description", "Qty", "Unit price", "Amount"]]
    for item in data["items"]:
        rows.append([
            Paragraph(item.get("description", ""), body),
            f"{Decimal(str(item.get('quantity', 1))):g}",
            fmt(money(item["unit_price"]), currency),
            fmt(line_total(item), currency),
        ])
    table = Table(rows, colWidths=[85 * mm, 18 * mm, 35 * mm, 35 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F5F9")]),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.grey),
    ]))
    story += [table, Spacer(1, 10)]

    summary = [["Subtotal", fmt(totals.subtotal, currency)]]
    if totals.discount:
        summary.append([f"Discount ({data.get('discount_pct')}%)", "-" + fmt(totals.discount, currency)])
    summary += [[f"Tax ({Decimal(str(data.get('tax_rate', DEFAULT_TAX_RATE))) * 100:g}%)", fmt(totals.tax, currency)],
                ["TOTAL", fmt(totals.total, currency)]]
    st = Table(summary, colWidths=[40 * mm, 45 * mm], hAlign="RIGHT")
    st.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"),
                            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                            ("LINEABOVE", (0, -1), (-1, -1), 1, accent)]))
    story.append(st)

    if data.get("notes"):
        story += [Spacer(1, 14), Paragraph("<b>Terms</b>", body), Paragraph(data["notes"], body)]
    if data.get("valid_until"):
        story.append(Paragraph(f"Valid until {data['valid_until']}.", small))
    doc.build(story)
    return totals


def serve(host="127.0.0.1", port=5055):
    from io import BytesIO
    from flask import Flask, jsonify, request, send_file

    app = Flask(__name__)

    @app.post("/quote")
    def quote():
        data = request.get_json(silent=True)
        if data is None:
            return jsonify(error="Body must be JSON"), 400
        buf = BytesIO()
        try:
            build_quote(data, buf)
        except QuoteError as exc:
            return jsonify(error=str(exc)), 422
        buf.seek(0)
        return send_file(buf, mimetype="application/pdf", download_name="quote.pdf")

    app.run(host=host, port=port)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Generate a PDF quote from JSON.")
    ap.add_argument("input", nargs="?", help="Quote JSON file")
    ap.add_argument("-o", "--output", default="quote.pdf")
    ap.add_argument("--serve", action="store_true", help="Run an HTTP service (POST /quote)")
    args = ap.parse_args(argv)
    if args.serve:
        serve()
        return 0
    if not args.input:
        ap.error("input JSON is required unless --serve is used")
    try:
        totals = build_quote(json.loads(Path(args.input).read_text(encoding="utf-8")), args.output)
    except (QuoteError, OSError, json.JSONDecodeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {args.output} (total {totals.total})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
