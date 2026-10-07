"""
Kitchen ticket printer service
------------------------------
Polls a Postgres table for new orders and prints them on an ESC/POS thermal
printer over TCP (port 9100). Designed to run unattended on a small device on
the restaurant's local network (e.g. an Android phone running Termux).

Flow:
  n8n (order workflow) -> INSERT into tickets_impresion -> this service picks up
  rows where impreso = false -> prints -> marks them as printed.

Configuration is read from environment variables (see .env.example).
No credentials live in the code.

Usage:
  python print_kitchen_tickets.py          # run the polling loop
  python print_kitchen_tickets.py --demo   # render a sample ticket, no DB/printer needed
"""

import json
import os
import re
import socket
import sys
import time
import traceback
import urllib.request
from datetime import datetime

# ---------------------------------------------------------------- configuration

BUSINESS_NAME = os.environ.get("BUSINESS_NAME", "MY RESTAURANT")
PRINTER_IP = os.environ.get("PRINTER_IP", "192.168.1.50")
PRINTER_PORT = int(os.environ.get("PRINTER_PORT", "9100"))
POLL_SECONDS = int(os.environ.get("POLL_SECONDS", "5"))
TICKET_WIDTH = int(os.environ.get("TICKET_WIDTH", "32"))  # characters per line
HEARTBEAT_URL = os.environ.get("HEARTBEAT_URL", "")       # optional uptime-monitor ping
HEARTBEAT_EVERY = int(os.environ.get("HEARTBEAT_EVERY", "300"))  # seconds

ESC = b"\x1b"
GS = b"\x1d"


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def encode(s: str) -> bytes:
    """CP1252 so accents and ñ print correctly on most thermal printers."""
    return s.encode("cp1252", errors="replace")


# ---------------------------------------------------------------- ticket layout

def build_ticket(folio, customer_name, customer_phone, items,
                 delivery_type, address, payment_method, total) -> bytes:
    sep = b"-" * TICKET_WIDTH + b"\n"
    out = []

    out.append(ESC + b"@")                    # initialize printer
    out.append(ESC + b"a" + b"\x01")          # center
    out.append(ESC + b"!" + b"\x30")          # double height + width
    out.append(encode(f"{BUSINESS_NAME}\n"))
    out.append(ESC + b"!" + b"\x00")
    out.append(encode("KITCHEN TICKET\n"))
    out.append(sep)

    out.append(ESC + b"!" + b"\x30")
    out.append(encode(f"ORDER {folio}\n"))
    out.append(ESC + b"!" + b"\x00")
    out.append(encode(f"Time: {datetime.now().strftime('%H:%M')}\n"))

    out.append(ESC + b"a" + b"\x00")          # left align
    out.append(sep)

    label = "PICKUP" if delivery_type == "recoger" else "DELIVERY"
    out.append(ESC + b"!" + b"\x08")          # bold
    out.append(encode(f"{label}\n"))
    out.append(ESC + b"!" + b"\x00")

    if delivery_type == "domicilio" and address:
        out.append(encode(f"Address: {address}\n"))
    if customer_name:
        out.append(encode(f"Customer: {customer_name}\n"))
    if customer_phone:
        out.append(encode(f"Phone: {customer_phone}\n"))
    out.append(sep)

    for item in items:
        qty = item.get("cantidad", 1)
        name = item.get("producto", "")
        size = item.get("tamano") or item.get("tamaño") or ""
        line = f"{qty}x {name}" + (f" ({size})" if size else "")
        out.append(encode(line + "\n"))

    out.append(sep)
    out.append(encode(f"Payment: {payment_method}\n"))
    out.append(encode(f"Total: ${total}\n"))
    out.append(b"\n\n\n")
    out.append(GS + b"V" + b"\x42" + b"\x00")  # feed + partial cut
    return b"".join(out)


def send_to_printer(data: bytes, timeout: int = 5) -> None:
    with socket.create_connection((PRINTER_IP, PRINTER_PORT), timeout=timeout) as s:
        s.sendall(data)


# ---------------------------------------------------------------- polling loop

def check_and_print() -> None:
    import pg8000.native  # imported lazily so --demo works without it

    conn = pg8000.native.Connection(
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"],
        port=int(os.environ.get("DB_PORT", "5432")),
        database=os.environ["DB_NAME"],
    )
    try:
        rows = conn.run(
            """
            SELECT id, folio, cliente_nombre, cliente_telefono, pedido_json,
                   total, forma_pago, tipo_entrega, direccion
            FROM tickets_impresion
            WHERE impreso = false
            ORDER BY id ASC
            """
        )
        for (id_, folio, name, phone, order_json, total,
             payment, delivery_type, address) in rows:
            try:
                items = json.loads(order_json)
                ticket = build_ticket(folio, name, phone, items,
                                      delivery_type, address, payment, total)
                send_to_printer(ticket)
                conn.run("UPDATE tickets_impresion SET impreso = true WHERE id = :id", id=id_)
                log(f"Order {folio} printed OK")
            except Exception as e:  # keep the loop alive; the row stays unprinted and is retried
                log(f"ERROR printing order {folio}: {e}")
                traceback.print_exc()
    finally:
        conn.close()


def ping_heartbeat() -> None:
    if not HEARTBEAT_URL:
        return
    try:
        urllib.request.urlopen(HEARTBEAT_URL, timeout=10).read()
    except Exception as e:
        log(f"Heartbeat failed: {e}")


def main_loop() -> None:
    log("Ticket printer service started. Waiting for orders...")
    last_ping = 0.0
    while True:
        try:
            check_and_print()
            if time.time() - last_ping >= HEARTBEAT_EVERY:
                ping_heartbeat()  # only pinged while the loop is healthy, so silence = alert
                last_ping = time.time()
        except Exception as e:
            log(f"Connection error: {e}")
            traceback.print_exc()
        time.sleep(POLL_SECONDS)


# ---------------------------------------------------------------- demo mode

def demo() -> None:
    ticket = build_ticket(
        folio=1042,
        customer_name="Ana Pérez",
        customer_phone="+52 449 000 0000",
        items=[
            {"cantidad": 2, "producto": "Protein Bowl", "tamano": "Large"},
            {"cantidad": 1, "producto": "Green Smoothie"},
        ],
        delivery_type="domicilio",
        address="Calle Ejemplo 123, Col. Centro",
        payment_method="Card",
        total=289,
    )
    with open("demo_ticket.bin", "wb") as f:
        f.write(ticket)
    # Human-readable preview: strip ESC/GS control sequences
    text = re.sub(rb"\x1b[@]|\x1b[a!][\x00-\xff]|\x1dV[\x00-\xff]{2}", b"", ticket)
    print(text.decode("cp1252", errors="replace"))
    log("Raw ESC/POS bytes written to demo_ticket.bin")


if __name__ == "__main__":
    demo() if "--demo" in sys.argv else main_loop()
