# Quote PDF generator

Turns a small JSON document into a clean, branded PDF quote. It works for any business that sends proposals: consultancies, caterers, contractors, agencies, workshops.

- Money is handled with `Decimal` and half-up rounding, so totals match what an accountant would calculate.
- Validation errors are explicit (no items, negative price, discount over 100%).
- Three ways to run it: command line, Python library, or a small HTTP service.

[Open the sample PDF](sample_data/sample_quote.pdf)

## Usage

```bash
pip install -r requirements.txt

# Command line
python quote_generator.py sample_data/quote.json -o quote.pdf

# HTTP service (POST /quote)
python quote_generator.py --serve
```

Input format: see [`sample_data/quote.json`](sample_data/quote.json). Fields: `number`, `date`, `valid_until`, `currency`, `issuer` (name, contact, accent color), `client`, `items` (description, quantity, unit price), `discount_pct`, `tax_rate` (default 16%), `notes`.

## Using it from n8n

The HTTP mode is designed for workflow tools:

1. Run the service next to n8n (a small container or a process on the same server).
2. In n8n, build the quote JSON from any trigger: a form submission, a WhatsApp conversation, a CRM deal, a spreadsheet row.
3. Add an **HTTP Request** node: `POST http://<service>:5055/quote`, body type JSON, response format **File**.
4. Pass the binary output to Gmail, WhatsApp or Google Drive nodes to send or store the quote.

Invalid input returns HTTP 422 with a JSON `error` message, so the workflow can branch on failures instead of sending a broken document.

## Tests

```bash
pip install pytest
pytest
```

11 tests cover rounding, discount and tax maths, invalid input, the CLI and in-memory rendering.
