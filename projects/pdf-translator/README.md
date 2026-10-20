# PDF translator (layout-preserving)

Translates a PDF from one language to another while keeping the design: each text block is replaced in place and the font size shrinks until the translation fits the original box.

Useful for menus, price lists, manuals, brochures and contracts that need a second language without rebuilding the design from scratch.

```bash
pip install -r requirements.txt
python pdf_translator.py input.pdf output.pdf --from en --to es
```

## Design notes

- **Redactions are applied once per page**, after all blocks are collected, instead of after every block.
- **Failures are isolated.** If the translation service fails for a block, that block keeps its original text and the rest of the document is still translated.
- **Fit check.** The font shrinks by measured width, and again if the text box still reports overflow.
- **Translator is injectable.** `translate_pdf` takes any `str -> str` function, so tests run offline and a different engine (a paid API, an LLM) can replace the default free one.

## Tests

```bash
pip install pytest
pytest
```

Tests generate a small PDF, translate it with a fake dictionary translator, and check that the original text is gone, that failures leave the original block, and that font fitting behaves.

## Limits

PDFs with real text only (scanned pages need OCR first), a single built-in font, and one style per block. Dense multi-column layouts may need manual review.
