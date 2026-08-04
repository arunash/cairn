#!/usr/bin/env python3
"""Options premium collected — net credits minus buy-to-close debits — all-time, this year, per symbol."""
import datetime
from cairn.compute.base import option_orders


def summary(year=None):
    year = year or datetime.date.today().year
    total = ytd = 0.0
    by_symbol = {}
    for o in option_orders():
        if o.get("state") != "filled":
            continue
        prem = float(o.get("processed_premium") or 0)
        signed = prem if o.get("direction") == "credit" else -prem
        total += signed
        sym = o.get("chain_symbol") or "?"
        by_symbol[sym] = by_symbol.get(sym, 0.0) + signed
        if (o.get("created_at") or "")[:4] == str(year):
            ytd += signed
    return {
        "year": year,
        "total": round(total, 2),
        "ytd": round(ytd, 2),
        "by_symbol": {k: round(v, 2) for k, v in sorted(by_symbol.items(), key=lambda kv: -kv[1])},
    }
