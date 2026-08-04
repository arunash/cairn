#!/usr/bin/env python3
"""Realized capital gains, split long-term vs short-term, for a given tax year."""
import datetime
from cairn.compute.lots import build


def summary(year=None):
    year = year or datetime.date.today().year
    realized, _ = build()
    ytd = [r for r in realized if r["sold"][:4] == str(year)]
    lt = sum(r["gain"] for r in ytd if r["term"] == "LT")
    st = sum(r["gain"] for r in ytd if r["term"] == "ST")
    by_symbol = {}
    for r in ytd:
        by_symbol[r["sym"]] = round(by_symbol.get(r["sym"], 0.0) + r["gain"], 2)
    return {
        "year": year,
        "lt": round(lt, 2),
        "st": round(st, 2),
        "net": round(lt + st, 2),
        "events": ytd,
        "by_symbol": by_symbol,
    }
