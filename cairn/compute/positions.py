#!/usr/bin/env python3
"""Positions across ALL of the user's accounts, using Robinhood's authoritative per-position
cost basis (already split- and transfer-adjusted), plus concentration and holding-period.

Basis, quantity, value, and unrealized P&L come straight from Robinhood — correct even for
split stocks (NVDA 10:1) and transferred-in shares (equity comp), with no reconstruction.
The FIFO lot engine is used only to estimate the long- vs short-term split of each holding,
anchored to Robinhood's real share count; where it can't reconcile, the position is flagged.
"""
import robin_stocks.robinhood as rh
from collections import defaultdict
from cairn.compute.base import login, symbol_for, accounts
from cairn.compute.lots import build


def holdings():
    """Return (rows, total_equity, accounts). Rows are aggregated per symbol across accounts."""
    login()
    accts = accounts()
    raw = {}
    prices = {}
    acct_equity = defaultdict(float)

    for a in accts:
        an = a["number"]
        for p in (rh.account.get_open_stock_positions(account_number=an) or []):
            qty = float(p.get("quantity") or 0)
            if qty <= 0:
                continue
            sym = symbol_for(p.get("instrument"))
            if not sym:
                continue
            basis = float(p.get("average_buy_price") or 0)
            if sym not in prices:
                try:
                    prices[sym] = float(rh.stocks.get_latest_price(sym)[0])
                except Exception:
                    prices[sym] = basis
            price = prices[sym]
            equity = qty * price
            acct_equity[an] += equity
            r = raw.setdefault(sym, {"qty": 0.0, "cost": 0.0, "equity": 0.0, "price": price, "accts": set()})
            r["qty"] += qty
            r["cost"] += basis * qty
            r["equity"] += equity
            r["accts"].add(an[-4:] if an else "????")

    rows = []
    for sym, r in raw.items():
        qty, cost, equity = r["qty"], r["cost"], r["equity"]
        rows.append({
            "sym": sym, "qty": qty, "price": r["price"], "basis": (cost / qty if qty else 0.0),
            "equity": equity, "cost": cost, "pl": equity - cost,
            "plpct": ((equity - cost) / cost * 100) if cost else 0.0,
            "accounts": sorted(r["accts"]),
        })
    rows.sort(key=lambda x: x["equity"], reverse=True)
    total = sum(x["equity"] for x in rows)
    for x in rows:
        x["weight"] = (x["equity"] / total * 100) if total else 0.0

    # holding-period split, anchored to Robinhood's real share count (scale-invariant proportion)
    _, open_lots = build()
    by_sym = defaultdict(list)
    for lot in open_lots:
        by_sym[lot["sym"]].append(lot)
    for x in rows:
        lots = by_sym.get(x["sym"], [])
        lot_tot = sum(l["qty"] for l in lots)
        if lot_tot <= 0:
            x["term"], x["recon_ok"] = "—", False
            continue
        lt_share = sum(l["qty"] for l in lots if l["term"] == "LT") / lot_tot
        lt_qty = lt_share * x["qty"]
        x["recon_ok"] = abs(lot_tot - x["qty"]) <= max(0.02 * x["qty"], 0.01)
        if not x["recon_ok"]:
            # lots don't reconcile (split / transfer / DRIP) → don't assert a possibly-wrong term
            x["term"] = "—"
        elif lt_qty >= x["qty"] - 1e-6:
            x["term"] = "LT"
        elif lt_qty <= 1e-6:
            x["term"] = "ST"
        else:
            x["term"] = f"{lt_share * 100:.0f}% LT"

    for a in accts:
        a["equity"] = round(acct_equity.get(a["number"], 0.0), 2)
    return rows, total, accts


def concentration(rows, total):
    """Top position + Herfindahl-Hirschman Index (0–10000; higher = more concentrated)."""
    if not rows or not total:
        return {"top": None, "top_weight": 0.0, "hhi": 0, "n": 0}
    hhi = sum(r["weight"] ** 2 for r in rows)
    top = rows[0]
    return {"top": top["sym"], "top_weight": top["weight"], "hhi": round(hhi), "n": len(rows)}
