# Security

Cairn runs entirely on **your own machine**, against **your own** Robinhood account. There is
no Cairn server, no telemetry, and no account for anyone else to attack. The threat model is
therefore narrow — protecting *your* credentials and *your* account from mistakes — and the
design reflects that.

## The safety model

### Read-only by default, enforced in code
Cairn talks to Robinhood through an MCP server (`cairn/broker/mcp.py`). That server registers
its tools in two tiers:

| Tier | Tools | When registered |
|------|-------|-----------------|
| **Read** | `get_portfolio`, `get_account_summary`, `get_quote`, `get_options_positions`, `get_options_orders` | **Always** |
| **Write** | `buy_stock`, `sell_stock`, `sell_option` | **Only when `CAIRN_ACT_ENABLED=1`** |

The write tools are plain functions with **no** tool decorator; they are attached to the server
only inside an `if CAIRN_ACT_ENABLED` block. In Insights and Ask (Chat) modes the flag is unset,
so those tools **do not exist over the wire** — a confused, jailbroken, or prompt-injected agent
cannot call a tool that was never registered. The prompt guardrails in `CLAUDE.md` are the first
line of defense; this gate is the one that actually holds.

### Human-in-the-loop for every trade
Even in Act mode, the playbooks (`cairn/act/*`) dry-run first, print the exact order, and require
an explicit confirmation before anything is placed. Nothing fires automatically.

## Credentials & secrets

- Your Robinhood login lives in a local `.env` (`RH_USERNAME` / `RH_PASSWORD`) that is **git-ignored**.
  It is read only to authenticate and is never printed, logged, or returned by any tool.
- `robin_stocks` caches a session token under `~/.tokens/` (also git-ignored). Treat it like a password.
- Optional email alerts read a Gmail **app password** from `~/.cairn/gmail_app_password.txt` — use an
  app password, never your real Gmail password, and keep that file `chmod 600`.
- `config/ledger.json`, generated reports, and daily ledgers are git-ignored — only the `*.example`
  templates (with placeholder account IDs) are tracked.

**Before you commit or fork:** confirm `git status` shows none of `.env`, `config/ledger.json`,
`web/report.html`, or `*-tracker.md`.

## Hardening already in place
- Downloaded statement PDFs go to a private `0700` temp dir and are deleted after parsing.
- The ledger will only fetch account data from a loopback (`localhost`/`127.0.0.1`) or an HTTPS
  URL — never `file://` or arbitrary plain-HTTP hosts.
- No `eval`, `exec`, `shell=True`, `pickle.load`, or `yaml.load` anywhere; all subprocess calls
  use argument lists (no shell string interpolation).

## Reporting a vulnerability
Found something? Please open a GitHub issue for non-sensitive reports, or email the maintainer
for anything that could put a user's account at risk. Since Cairn is local-first, most issues
affect only the person running it — but responsible disclosure is still appreciated.
