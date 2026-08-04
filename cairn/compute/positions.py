#!/usr/bin/env python3
"""Current positions, concentration, and per-symbol holding-period (long vs short-term) split."""
import robin_stocks.robinhood as rh
from cairn.compute.base import login
from cairn.compute.lots import build


def holdings():
    """Live holdings with cost basis, unrealized P&L, and portfolio weight. Returns (rows, total_equity)."""
    login()
    h = rh.account.build_holdings() or {}
    rows = []
    for sym, d in h.items():
        qty = float(d.get("quantity") or 0)
        price = float(d.get("price") or 0)
        basis = float(d.get("average_buy_price") or 0)
        equity = float(d.get("equity") or qty * price)
        cost = basis * qty
        rows.append({
            "sym": sym, "qty": qty, "price": price, "basis": basis, "equity": equity,
            "cost": cost, "pl": equity - cost, "plpct": ((equity - cost) / cost * 100) if cost else 0.0,
        })
    rows.sort(key=lambda r: r["equity"], reverse=True)
    total = sum(r["equity"] for r in rows)
    for r in rows:
        r["weight"] = (r["equity"] / total * 100) if total else 0.0

    # annotate each holding with how much of its share count is long-term (held > 1 year)
    _, open_lots = build()
    lt_qty = {}
    tot_qty = {}
    for lot in open_lots:
        tot_qty[lot["sym"]] = tot_qty.get(lot["sym"], 0.0) + lot["qty"]
        if lot["term"] == "LT":
            lt_qty[lot["sym"]] = lt_qty.get(lot["sym"], 0.0) + lot["qty"]
    for r in rows:
        t = tot_qty.get(r["sym"], 0.0)
        lt = lt_qty.get(r["sym"], 0.0)
        if t <= 0:
            r["term"] = "—"
        elif lt >= t - 1e-9:
            r["term"] = "LT"
        elif lt <= 1e-9:
            r["term"] = "ST"
        else:
            r["term"] = f"{lt / t * 100:.0f}% LT"
    return rows, total


def concentration(rows, total):
    """Top position + Herfindahl-Hirschman Index (0–10000; higher = more concentrated)."""
    if not rows or not total:
        return {"top": None, "top_weight": 0.0, "hhi": 0, "n": 0}
    hhi = sum(r["weight"] ** 2 for r in rows)
    top = rows[0]
    return {"top": top["sym"], "top_weight": top["weight"], "hhi": round(hhi), "n": len(rows)}
