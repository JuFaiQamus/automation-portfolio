import sys
from pathlib import Path

import pymupdf
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pdf_translator as t  # noqa: E402

DICT = {"Hello world": "Hola mundo", "Good morning": "Buenos dias"}


def make_pdf(path, lines):
    doc = pymupdf.open()
    page = doc.new_page()
    y = 100
    for line in lines:
        page.insert_text((72, y), line, fontsize=12)
        y += 60
    doc.save(str(path))
    doc.close()


def text_of(path):
    doc = pymupdf.open(str(path))
    out = " ".join(p.get_text() for p in doc)
    doc.close()
    return out


def test_translates_and_removes_original(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    make_pdf(src, ["Hello world", "Good morning"])
    n = t.translate_pdf(str(src), str(dst), lambda s: DICT.get(s, s))
    out = text_of(dst)
    assert n == 2
    assert "Hola mundo" in out and "Buenos dias" in out
    assert "Hello" not in out


def test_failed_block_keeps_original(tmp_path):
    src, dst = tmp_path / "a.pdf", tmp_path / "b.pdf"
    make_pdf(src, ["Hello world", "Good morning"])

    def flaky(s):
        if s == "Good morning":
            raise ConnectionError("offline")
        return DICT[s]

    assert t.translate_pdf(str(src), str(dst), flaky) == 1
    out = text_of(dst)
    assert "Hola mundo" in out and "Good morning" in out


def test_fit_font_size_shrinks_to_minimum():
    measure = lambda text, size: len(text) * size  # noqa: E731
    assert t.fit_font_size("abcd", 100, measure) == 12   # fits at the start size
    assert t.fit_font_size("abcdefghij", 70, measure) == 7
    assert t.fit_font_size("x" * 500, 10, measure) == t.MIN_FONT


def test_cli_reports_missing_file(tmp_path, capsys):
    assert t.main([str(tmp_path / "nope.pdf"), str(tmp_path / "o.pdf")]) == 1
