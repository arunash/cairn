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
   │ skills/  insights·ask·act  │ ───────────► │  positions · quotes        │
   │ CLAUDE.md = rules+guards   │ ◄─────────── │  trade & options history   │
   │ config/ledger.json = YOU   │   write*     │  monthly statements (PDF)  │
   └───────────────────────────┘  *Act only    └────────────────────────────┘
              │  runs
              ▼
   cairn/  ingest ──► compute ──► report ──► web/report.html
           (3 sources)  (the insight modules)   (the page you read)
           watch/  daily refresh + alerts (concentration-trim watcher, earnings, etc.)
```

- **Ingest** pulls from all three Robinhood surfaces + live quotes.
- **Compute** runs the deterministic modules: concentration, cost-basis & holding period, realized LT/ST gains, premium (net of buy-to-closes), wash-sale, and the intent ledger.
- **Report** renders it. **Claude Code** reads it, answers questions, and — only in Act mode — executes with your approval.

## Security

- **Local-first.** Your Robinhood login sits in `.env` on your machine. There is no Cairn server.
- **Read-only by default.** Insights & chat never have trading permission.
- **No outbound calls** except to *your* Robinhood account and (for chat) *your* Claude.
- **Disconnect anytime** — delete the local session token and it's cut off instantly.
- **Auditable** — it's all here, MIT, nothing obfuscated.

## Repo structure

```
cairn/
├── CLAUDE.md              # the agent's behavior, YOUR rules, the hard guardrails
├── .mcp.json             # Robinhood MCP (read tools always; write gated to Act)
├── config/
│   └── ledger.example.json   # intent-based pools + your rules (copy → ledger.json)
├── cairn/
│   ├── ingest/           # positions · history · statements (PDF parse)
│   ├── compute/          # concentration · costbasis · realized · premium · washsale · ledger
│   ├── report/           # build the report
│   ├── act/              # wheel · roll · reinvest · trim  (human-in-loop)
│   └── watch/            # daily refresh + condition alerts
├── skills/               # Claude Code playbooks: insights · ask · act · steward
└── web/report.html       # the insights front page
```

## ⚠️ Before you publish a fork

The `cairn/` modules are ported from a working prototype and contain **account-specific values** (account IDs, a cost basis or two). Move those into `config/ledger.json` (git-ignored) before making your fork public. See [`docs/PUBLISH.md`](docs/PUBLISH.md).

## License

MIT — do anything, no warranty. This is **software, not financial advice.** You run it, you own the decisions.
