"""Translate a PDF while keeping its layout.

Each text block is replaced in place with its translation, and the font size
shrinks until the text fits the original box.

    python pdf_translator.py input.pdf output.pdf --from en --to es

Limits: works on PDFs with real text (not scans), uses a built-in font, and
keeps one font style per block. Complex multi-column designs may need tuning.
"""
from __future__ import annotations

import argparse
import sys
from typing import Callable

import pymupdf

MIN_FONT, MAX_FONT = 6, 12


def fit_font_size(text: str, width: float, measure: Callable[[str, float], float],
                  start: float = MAX_FONT, minimum: float = MIN_FONT) -> float:
    """Largest size (stepping down by 1) whose single-line width fits ``width``."""
    size = start
    while size > minimum and measure(text, size) > width:
        size -= 1
    return max(size, minimum)


def make_translator(source: str, target: str) -> Callable[[str], str]:
    from deep_translator import GoogleTranslator
    t = GoogleTranslator(source=source, target=target)
    return lambda text: t.translate(text) or text


def translate_pdf(src: str, dst: str, translate: Callable[[str], str]) -> int:
    """Translate ``src`` into ``dst``. Returns the number of blocks translated."""
    doc = pymupdf.open(src)
    count = 0
    try:
        for page in doc:
            blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
            jobs = []
            for x0, y0, x1, y1, text, *_ in blocks:
                try:
                    translated = translate(text.strip())
                except Exception as exc:  # network / API failure: keep the original text
                    print(f"page {page.number + 1}: translation failed ({exc}); block left as is",
                          file=sys.stderr)
                    continue
                jobs.append((pymupdf.Rect(x0, y0, x1, y1), translated))
                page.add_redact_annot(jobs[-1][0], fill=(1, 1, 1))
            page.apply_redactions()  # once per page, after all blocks are collected
            for rect, translated in jobs:
                size = fit_font_size(
                    translated, rect.width,
                    lambda t, s: pymupdf.get_text_length(t, fontname="helv", fontsize=s))
                # insert_textbox returns a negative number if the text did not fit
                while page.insert_textbox(rect, translated, fontsize=size, fontname="helv") < 0 \
                        and size > MIN_FONT:
                    size -= 1
                count += 1
        doc.save(dst)
    finally:
        doc.close()
    return count


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Translate a PDF keeping its layout.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--from", dest="source", default="en")
    ap.add_argument("--to", dest="target", default="es")
    a = ap.parse_args(argv)
    try:
        n = translate_pdf(a.input, a.output, make_translator(a.source, a.target))
    except (OSError, pymupdf.FileDataError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Translated {n} text blocks -> {a.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
