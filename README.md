# Cairn

[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](./LICENSE) [![Python](https://img.shields.io/badge/python-%3E%3D3.9-3776AB?logo=python&logoColor=white)](#requirements) [![local-first](https://img.shields.io/badge/local--first-%F0%9F%94%92-2F6B4F.svg)](#security) [![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](./CONTRIBUTING.md)

**An insights engine for your Robinhood account that runs on your machine.** It unifies everything Robinhood scatters — live positions, trade & options history, and monthly statements — into one report you can actually read *and ask questions of*: concentration, cost basis, holding period, realized long/short-term gains, premium income, wash-sale flags, and opportunities.

Robinhood keeps your data on three surfaces that never talk to each other — **the UI** (now), **history** (the past), **statements** (the record) — and none of them synthesize. So the insights you actually need are impossible to get without exporting CSVs and hand-stitching spreadsheets. Cairn does the stitching, on your machine.

> Built in the open. Runs **local-first** — your credentials live only on your device, the connection is strictly **read-only**, and every line is auditable. MIT licensed.

**⭐ If Cairn shows you something Robinhood couldn't, give it a star** — it's the only way I know it's useful to someone.

---

## Quick start

```bash
git clone https://github.com/arunash/cairn.git && cd cairn
cp .env.example .env               # add your Robinhood login — stays on this machine
pip install -r requirements.txt
python -m cairn report             # builds web/report.html from your live account
open web/report.html               # your insights, on one page
```

Then open the folder in **Claude Code** and just ask: *"what should I do about my concentration?"*, *"what's my tax situation?"*, *"how much premium did I collect?"*

You need nothing but a Robinhood login for the report. For the chat you need [Claude Code](https://claude.com/claude-code) (it's the brain). Everything runs locally.

> **Where does it open?** `web/report.html` is a plain file on your machine — `open` it and it loads from a `file://` path in your browser. There is no hosted portal and no server.

> **Status — built in the open.** Working today: the report (account value, unrealized P&L, concentration, per-position cost basis) and the intent **ledger** (pool split, day-over-day, options premium). On the roadmap: realized long/short-term gains, wash-sale flags, and statement-based cash-flows. Issues and PRs welcome.

---

## The three layers — all free, all local

| Layer | What it does | Runs on |
|---|---|---|
| **1 · Insights** | The report — deterministic compute + render | Python, **no LLM** |
| **2 · Ask Cairn** | Chat & advice, in the context of your whole account | Claude Code, **read-only** |
| **3 · Act & Steward** | Places trades, runs the wheel, rolls, trims, watches | Claude Code + write tools, **human-in-loop** |

The safety line is *structural*: layers 1–2 only ever have **read** tools, so they physically **cannot trade**. Layer 3 unlocks the write tools and still approves every single order with you.

## How it works

```
   CLAUDE CODE  (the brain, local)            YOUR ROBINHOOD  (your account)
   ┌───────────────────────────┐   read       ┌────────────────────────────┐
   │ CLAUDE.md = rules+guards   │ ───────────► │  positions · quotes        │
   │ config/ledger.json = YOU   │ ◄─────────── │  trade & options history   │
   │ broker/mcp.py = the gate   │   write*     │  monthly statements (PDF)  │
   └───────────────────────────┘  *Act only    └────────────────────────────┘
              │  runs
              ▼
   cairn/  report ──► web/report.html          python -m cairn report
           compute/ledger · act/* · watch/*    ledger · wheel · roll · trim · alerts
```

- **Report** (`python -m cairn report`) pulls your live holdings read-only and renders the page — account value, unrealized P&L, concentration, and per-position cost basis & weight.
- **Compute** holds the deterministic engines; today that's the intent **ledger** (`cairn/compute/ledger.py`): pool split, day-over-day, and options premium net of buy-to-closes. Realized LT/ST gains and wash-sale flags are the roadmap.
- **Claude Code** reads the report, answers questions in plain language, and — only in Act mode — executes with your approval.

## Security

- **Local-first.** Your Robinhood login sits in `.env` on your machine. There is no Cairn server.
- **Read-only by default.** Insights & chat never have trading permission.
- **No outbound calls** except to *your* Robinhood account and (for chat) *your* Claude.
- **Disconnect anytime** — delete the local session token and it's cut off instantly.
- **Auditable** — it's all here, MIT, nothing obfuscated.

## Repo structure

```
cairn/
├── CLAUDE.md                 # the agent's behavior, YOUR rules, the hard guardrails
├── SECURITY.md               # read-only-by-default model + secret handling
├── .mcp.json                 # Robinhood MCP wiring (read tools always; write gated to Act)
├── config/
│   └── ledger.example.json   # intent-based pools + your rules (copy → ledger.json)
├── cairn/
│   ├── broker/mcp.py         # the MCP gate — write tools registered only when CAIRN_ACT_ENABLED=1
│   ├── report/build.py       # builds web/report.html (the insights page)
│   ├── compute/ledger.py     # intent ledger · day-over-day · premium split
│   ├── ingest/statements.py  # monthly statement PDF → ACH cash-flow parse
│   ├── act/                  # wheel · roll · reinvest · trim  (human-in-loop)
│   └── watch/                # trim watcher · reminders (email alerts)
└── web/report.html           # generated locally — your insights page (git-ignored)
```

## Keeping your fork clean

Your personal data never belongs in the repo. Account IDs, cost basis, credentials, and
generated output all live in **git-ignored** files only:

| File | What | Where it comes from |
|------|------|---------------------|
| `.env` | your Robinhood login | copy `.env.example` |
| `config/ledger.json` | your accounts & pools | copy `config/ledger.example.json` |
| `web/report.html`, `config/daily-ledger.*` | generated output | created at runtime |

The tracked `cairn/` modules ship with **placeholders only** — `MARGIN_ACCT`, `IRA_ACCT`,
`<ticker>`, `BASIS = 0.0`. Put your real values into `config/ledger.json`, never into the code.
Before you push, confirm `git status` shows none of the files above. See [`SECURITY.md`](SECURITY.md).

## License

MIT — do anything, no warranty. This is **software, not financial advice.** You run it, you own the decisions.
