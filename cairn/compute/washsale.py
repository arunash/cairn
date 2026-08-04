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


def summary(year=None):
    """Aggregate the raw flags by symbol — count of flagged lots + total loss potentially
    disallowed. A repurchase within 30 days of a loss sale (e.g. weekly ETF reinvestment)
    triggers this; the losses are added to the replacement shares' basis, not lost."""
    fl = flags(year)
    agg = {}
    for f in fl:
        a = agg.setdefault(f["sym"], {"count": 0, "loss": 0.0})
        a["count"] += 1
        a["loss"] += f["loss"]
    rows = [{"sym": k, "count": v["count"], "loss": round(v["loss"], 2)} for k, v in agg.items()]
    rows.sort(key=lambda r: r["loss"])  # most negative first
    return {"count": len(fl), "total_loss": round(sum(f["loss"] for f in fl), 2), "by_symbol": rows}
