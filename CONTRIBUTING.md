# Contributing to Cairn

Thanks for looking under the hood. Cairn is built in the open, and the fastest way to help is
to run it on your own account and tell me where it's wrong or thin.

## Ground rules

1. **Never commit personal data.** Account IDs, cost basis, credentials, and generated reports
   belong only in git-ignored files (`.env`, `config/ledger.json`, `web/`). Before you push,
   run `git status` and confirm none of those appear. See [`SECURITY.md`](SECURITY.md).
2. **Read-only stays read-only.** Insights and Ask modes must never gain trading ability. Any
   write capability goes through the `CAIRN_ACT_ENABLED` gate in `cairn/broker/mcp.py` and keeps
   a human in the loop.
3. **Never guess a number.** If a figure can't be fetched, the code should say so — not invent it.

## Good first issues

- New deterministic engines in `cairn/compute` (realized LT/ST gains, wash-sale detection,
  statement-based cash-flows) — each is a pure function over data Robinhood already returns.
- Richer `web/report.html` sections (holding period, options ladder, dividend income).
- More `cairn/act` playbooks, always dry-run → approve → `--live`.

## Workflow

Fork → branch → keep changes small and reviewable → open a PR describing what you ran it against
(redact any real numbers). Bug reports with the failing input (sanitized) are just as welcome as code.
