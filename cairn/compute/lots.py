#!/usr/bin/env python3
"""FIFO lot engine — the foundation for realized gains, holding periods, and wash-sale flags.

It replays your filled stock executions in date order, matching each sale against the
oldest open buy lots (FIFO), and produces:
  • realized events — each matched sale slice with cost, proceeds, gain, days held, LT/ST
  • open lots       — the buy lots still held, each with its acquisition date & holding period

Assumptions & limits (read before trusting the numbers):
  • FIFO matching. Robinhood's own 1099 may use a different default — reconcile against it.
  • Stock splits and shares transferred IN are NOT basis-adjusted; they can distort a lot.
  • Options and short sales are handled by other modules, not here.
This is bookkeeping to help you see your position — it is NOT tax advice.
"""
import datetime
from collections import defaultdict, deque
from cairn.compute.base import symbol_for, stock_orders

_cache = {}


def _days(d1, d2):
    try:
        return (datetime.date.fromisoformat(d2[:10]) - datetime.date.fromisoformat(d1[:10])).days
    except Exception:
        return 0


def exec_events():
    """All filled stock buy/sell executions as dicts (date, sym, side, qty, price), chronological."""
    if "ev" in _cache:
        return _cache["ev"]
    orders = stock_orders()
    ev = []
    for o in orders:
        if o.get("state") != "filled":
            continue
        sym = symbol_for(o.get("instrument"))
        if not sym:
            continue
        side = o.get("side")
        for ex in (o.get("executions") or []):
            qty = float(ex.get("quantity") or 0)
            price = float(ex.get("price") or 0)
            if qty <= 0:
                continue
            date = ex.get("settlement_date") or (o.get("last_transaction_at") or "")[:10]
            ev.append({"date": date, "sym": sym, "side": side, "qty": qty, "price": price})
    ev.sort(key=lambda e: e["date"])
    _cache["ev"] = ev
    return ev


def build():
    """Return (realized, open_lots). Cached per process."""
    if "built" in _cache:
        return _cache["built"]
    events = exec_events()
    queues = defaultdict(deque)   # sym -> deque of {qty, price, date}
    realized = []
    for e in events:
        sym = e["sym"]
        if e["side"] == "buy":
            queues[sym].append({"qty": e["qty"], "price": e["price"], "date": e["date"]})
        elif e["side"] == "sell":
            remaining = e["qty"]
            q = queues[sym]
            while remaining > 1e-9 and q:
                lot = q[0]
                take = min(remaining, lot["qty"])
                days = _days(lot["date"], e["date"])
                realized.append({
                    "sym": sym, "acquired": lot["date"], "sold": e["date"], "qty": take,
                    "cost": round(lot["price"] * take, 2), "proceeds": round(e["price"] * take, 2),
                    "gain": round((e["price"] - lot["price"]) * take, 2),
                    "days": days, "term": "LT" if days > 365 else "ST",
                })
                lot["qty"] -= take
                remaining -= take
                if lot["qty"] <= 1e-9:
                    q.popleft()
            # a sell with no remaining lots (transfer-in or short) can't be basis-matched → skipped

    today = datetime.date.today().isoformat()
    open_lots = []
    for sym, q in queues.items():
        for lot in q:
            if lot["qty"] <= 1e-9:
                continue
            days = _days(lot["date"], today)
            open_lots.append({
                "sym": sym, "acquired": lot["date"], "qty": lot["qty"], "price": lot["price"],
                "days": days, "term": "LT" if days > 365 else "ST",
            })
    _cache["built"] = (realized, open_lots)
    return realized, open_lots
