import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import quote_generator as q  # noqa: E402

SAMPLE = Path(__file__).resolve().parents[1] / "sample_data" / "quote.json"


def test_totals_with_discount_and_tax():
    items = [{"description": "a", "quantity": 2, "unit_price": "100.10"}]
    t = q.compute_totals(items, discount_pct=10)
    assert t.subtotal == Decimal("200.20")
    assert t.discount == Decimal("20.02")
    assert t.tax == Decimal("28.83")  # 180.18 * 0.16 = 28.8288
    assert t.total == Decimal("209.01")


def test_rounding_is_half_up():
    assert q.money("0.005") == Decimal("0.01")


@pytest.mark.parametrize("bad", [
    {"items": [], "discount_pct": 0},
    {"items": [{"quantity": 0, "unit_price": 5}], "discount_pct": 0},
    {"items": [{"quantity": 1, "unit_price": -5}], "discount_pct": 0},
    {"items": [{"quantity": 1, "unit_price": 5}], "discount_pct": 120},
])
def test_invalid_inputs(bad):
    with pytest.raises(q.QuoteError):
        q.compute_totals(**bad)


def test_missing_client_name():
    with pytest.raises(q.QuoteError):
        q.build_quote({"client": {}, "items": [{"unit_price": 1}]}, "x.pdf")


def test_cli_writes_pdf(tmp_path):
    out = tmp_path / "out.pdf"
    assert q.main([str(SAMPLE), "-o", str(out)]) == 0
    assert out.read_bytes().startswith(b"%PDF")


def test_cli_bad_json_returns_error(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{nope")
    assert q.main([str(bad), "-o", str(tmp_path / "o.pdf")]) == 1


def test_sample_totals():
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))
    t = q.build_quote(data, SAMPLE.parent / "_tmp.pdf")
    (SAMPLE.parent / "_tmp.pdf").unlink()
    assert t.subtotal == Decimal("19500.00")
    assert t.total == Decimal("20358.00")  # 19500 - 10% = 17550; + 16% = 20358


def test_build_to_memory_buffer():
    from io import BytesIO
    buf = BytesIO()
    q.build_quote(json.loads(SAMPLE.read_text(encoding="utf-8")), buf)
    assert buf.getvalue().startswith(b"%PDF")
