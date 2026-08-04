#!/usr/bin/env python3
"""Heuristic wash-sale flags.

A wash sale disallows a loss when you buy the same security within 30 calendar days
BEFORE or AFTER selling it at a loss. This flags candidates so you can check them — it:
  • does NOT adjust cost basis or the disallowed amount,
  • does NOT cover 'substantially identical' securities, options, or IRA cross-purchases,
  • is a screen, not a determination.
Always confirm against your broker's 1099-B. This is not tax advice.
"""
import datetime
from cairn.compute.lots import build, exec_events


def _d(s):
    return datetime.date.fromisoformat(s[:10])


def flags(year=None):
    year = year or datetime.date.today().year
    realized, _ = build()
    buys = [e for e in exec_events() if e["side"] == "buy"]
    out = []
    for r in realized:
        if r["gain"] >= 0 or r["sold"][:4] != str(year):
            continue
        sold = _d(r["sold"])
        replaced = sorted({
            b["date"] for b in buys
            if b["sym"] == r["sym"]
            and abs((_d(b["date"]) - sold).days) <= 30
            and b["date"] != r["acquired"]   # not the lot we just sold
        })
        if replaced:
            out.append({
                "sym": r["sym"], "sold": r["sold"],
                "loss": r["gain"], "replaced_on": replaced,
            })
    return out
