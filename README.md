# Automation Portfolio

Hi, I'm **JuanMa**, an automation and operations consultant based in Aguascalientes, México. I design and build automations that remove manual work for any kind of business, and I run client engagements end to end: diagnostic, design, implementation and handover.

Founder of **QamusDev**, an automation studio for small and mid-size businesses. I have 10+ years in professional kitchens, so restaurants are my strongest domain, but the same approach works for retail, services, clinics, logistics or back-office teams: anywhere people copy data by hand, answer the same messages all day or chase information across tools.

📍 México · 🗣 English (professional working proficiency) / Spanish (native) · ✉️ jufaiqamusdev@gmail.com · 🔗 [LinkedIn](https://www.linkedin.com/in/juan-manuel-romo-faisal-b9111a128/)

## Featured work

| Project | What it shows | Stack |
|---|---|---|
| [WhatsApp ordering assistant](case-studies/restaurant-order-automation.md) | Case study: AI agent that takes orders by text, voice note or photo, quotes delivery, creates the POS order, prints the kitchen ticket, schedules late orders and hands off to the owner | n8n, WhatsApp Cloud API, OpenAI, Postgres, Loyverse |
| [Kitchen ticket printer](projects/kitchen-ticket-printer) | Runnable code: queue-based service that prints tickets on a thermal printer, with failure alerting | Python, PostgreSQL, ESC/POS |
| [Invoice price tracker](projects/invoice-price-tracker) | Runnable code: reads supplier CFDI XML invoices, tracks ingredient prices and flags increases, with tests | Python, SQLite, XML (CFDI) |
| [Recipe costing + menu engineering](projects/recipe-costing) | Runnable code: dish food cost with ingredient yields, linked to invoice prices, plus a Star/Plowhorse/Puzzle/Dog menu analysis, with tests, validated against a real restaurant's costing workbook | Python, CSV, SQLite |
| [Quote PDF generator](projects/quote-pdf-generator) | Runnable code: JSON in, branded PDF quote out, with exact money maths and an HTTP mode that n8n can call | Python, ReportLab, Flask |
| [Hand gesture trigger](projects/hand-gesture-trigger) | Runnable code: webcam hand gestures fire webhooks for touchless control, with tested gesture logic | Python, OpenCV, MediaPipe |
| [PDF translator](projects/pdf-translator) | Runnable code: translates PDFs in place, keeping the layout, with per-block failure handling | Python, PyMuPDF |

More workflows are on the way. See the roadmap below.

## How I work

1. **Diagnose** the current process with business frameworks (process mapping, 5 Whys, Business Model Canvas) before touching any tool.
2. **Design for failure.** Every critical piece (webhooks, POS connection, messaging, on-site devices) gets active alerting. We should find out about a failure before the customer does.
3. **Hand over** with documentation the client's team can actually use.

## Skills

**Automation & integration:** n8n, webhooks, REST APIs, OAuth, Google Workspace
**AI in workflows:** LLM structured extraction, speech-to-text, prompt design for deterministic output
**Backend & data:** Python, PostgreSQL, SQL
**Messaging & POS:** WhatsApp Cloud API, Loyverse
**Industry depth:** restaurants and food service (kitchen ops, costing, delivery, POS)
**Consulting:** discovery, scoping, fixed-scope packages and retainers, client management

## Roadmap

- [x] Quote/proposal PDF generator (callable from n8n)
- [ ] n8n workflow template that calls the quote generator from a form
- [ ] Lead-capture → CRM → follow-up sequence (n8n template)
- [x] Invoice price tracking from CFDI XML
- [x] Link ingredient prices to recipe costing (food cost per dish)
- [ ] Daily operations report delivered to WhatsApp or email
- [ ] Error-handling workflow template for n8n

## Privacy

Client work is shown as anonymized case studies. This repository contains no client names, credentials, phone numbers or internal IDs.
