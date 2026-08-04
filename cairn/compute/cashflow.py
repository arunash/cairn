#!/usr/bin/env python3
"""Cash in and out of the account: ACH bank transfers + dividends received.

'net_contributed' is your own money in minus out — the baseline your gains are measured against.
Statement-PDF parsing (cairn/ingest/statements.py) is a fallback when the transfers API is thin.
"""
import datetime
import robin_stocks.robinhood as rh
from cairn.compute.base import login


def summary(year=None):
    login()
    year = year or datetime.date.today().year
    deposits = withdrawals = 0.0
    for t in (rh.account.get_bank_transfers() or []):
        if t.get("state") in ("cancelled", "failed", "reversed"):
            continue
        amt = float(t.get("amount") or 0)
        if t.get("direction") == "deposit":
            deposits += amt
        else:
            withdrawals += amt

    div_total = div_ytd = 0.0
    for d in (rh.account.get_dividends() or []):
        if d.get("state") not in (None, "paid", "reinvested"):
            continue
        amt = float(d.get("amount") or 0)
        div_total += amt
        paid = (d.get("paid_at") or d.get("payable_date") or "")[:4]
        if paid == str(year):
            div_ytd += amt
    return {
        "deposits": round(deposits, 2),
        "withdrawals": round(withdrawals, 2),
        "net_contributed": round(deposits - withdrawals, 2),
        "dividends_total": round(div_total, 2),
        "dividends_ytd": round(div_ytd, 2),
        "year": year,
    }
