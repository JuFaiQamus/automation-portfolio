# Kitchen Ticket Printer

A small, dependency-light service that prints kitchen tickets automatically when an order is created by an automation workflow. Built for a restaurant that takes orders through WhatsApp and delivery apps and needed tickets to appear in the kitchen without anyone touching a screen.

## The problem

Orders were being captured and registered in the POS by an n8n workflow, but the kitchen still had no automatic way to receive them. The POS cloud API can't push to a local thermal printer, and the printer only speaks ESC/POS on the local network.

## The solution

```
n8n order workflow ──► Postgres queue table ──► this service (on-site device) ──► thermal printer
   (creates POS receipt,     tickets_impresion        polls every 5 s              ESC/POS over TCP :9100
    assigns folio)           impreso = false          prints, marks impreso = true
```

- **Decoupled by a queue table.** n8n never needs to reach the printer; the on-site device pulls work. If the printer is off or the Wi-Fi drops, rows stay `impreso = false` and are retried automatically. No orders are lost.
- **Runs on cheap hardware.** Plain Python + `pg8000` (pure Python), so it runs on an Android phone via Termux.
- **No secrets in code.** All configuration comes from environment variables (`.env.example`).
- **Failure alerting built in.** Optional heartbeat ping to an uptime monitor, sent only while the loop is healthy, so a silent device triggers an alert instead of a customer complaint.

## Try it without a printer or database

```bash
python print_kitchen_tickets.py --demo
```

Renders a sample ticket as text and writes the raw ESC/POS bytes to `demo_ticket.bin`.

## Run it for real

```bash
pip install -r requirements.txt
psql "$DATABASE_URL" -f schema.sql      # once
cp .env.example .env                    # fill in values, then export them
python print_kitchen_tickets.py
```

On Android/Termux, run `termux-wake-lock` first so the OS doesn't suspend the process.

## Design notes and known limitations

- Polling (5 s) is simple and robust for restaurant volumes. `LISTEN/NOTIFY` would reduce latency but adds failure modes on flaky networks.
- Single printer, single consumer. With several consumers, claim rows with `SELECT ... FOR UPDATE SKIP LOCKED` to avoid double prints.
- A ticket that fails repeatedly is retried forever; a retry cap and an alert would be the next improvement.

**Stack:** Python 3, PostgreSQL, ESC/POS over TCP, Termux (Android), n8n (upstream).
