#!/usr/bin/env python3
"""Daily pool-level ledger — splits your Robinhood accounts into the intent-based POOLS
defined in config/ledger.json, logs day-over-day change, and tracks premium collected.

A "pool" is money grouped by PURPOSE, not by account (see config/ledger.example.json).
  equity(pool) = sum(equity of its accounts) + its banks_static
If two pools share ONE brokerage/margin account, a pool can claim a "slice" of it
(cash + specific positions + optionally all of one vehicle ETF). That slice is added to
the claiming pool and subtracted from the pool that physically holds the shared account,
so nothing is double-counted.

Data: local API (:5001) for equity; robin_stocks for option-order premium.
Run daily after the close. This module only READS — it never places a trade.
"""
import json, os, csv, urllib.request, datetime, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(BASE, "..", ".."))
CFG_PATH = os.environ.get("CAIRN_LEDGER", os.path.join(ROOT, "config", "ledger.json"))
CSV_PATH = os.path.join(ROOT, "config", "daily-ledger.csv")
MD_PATH  = os.path.join(ROOT, "config", "daily-ledger.md")


def fetch_accounts(api):
    with urllib.request.urlopen(api, timeout=90) as r:
        return json.load(r)["data"]["accounts"]

def equity(accts, num):
    return next((float(a.get("equity") or 0) for a in accts if a.get("account_number") == num), 0.0)

def positions(accts, num):
    return next((a.get("positions") or [] for a in accts if a.get("account_number") == num), [])

def sym_value(pos, symbol):
    return sum(float(p.get("market_value") or 0) for p in pos if p.get("symbol") == symbol)

def slice_value(accts, shared_account, sc):
    """Value of one pool's slice inside a shared account: cash + named positions + (optionally) all of one vehicle ETF."""
    pos = positions(accts, shared_account)
    val = float(sc.get("cash", 0) or 0)
    for sym, qty in (sc.get("positions") or {}).items():
        for p in pos:
            if p.get("symbol") == sym and float(p.get("quantity") or 0) > 0:
                unit = float(p["market_value"]) / float(p["quantity"]); val += unit * float(qty); break
    if sc.get("vehicle_all"):
        val += sym_value(pos, sc["vehicle_all"])
    return val


def compute_pools(accts, cfg):
    """Return {pool_name: equity} for every pool in the config."""
    shared = cfg.get("shared_account")
    result, slice_total, slice_owner = {}, 0.0, None
    for name, pool in cfg["pools"].items():
        base = sum(equity(accts, n) for n in pool.get("accounts", [])) + float(pool.get("banks_static", 0) or 0)
        sc = pool.get("slice_of_shared")
        if sc and shared:
            sv = slice_value(accts, shared, sc); base += sv; slice_total += sv; slice_owner = name
        result[name] = base
    # the pool that physically holds the shared account loses the slice another pool claimed
    if shared and slice_total:
        for name, pool in cfg["pools"].items():
            if name != slice_owner and shared in pool.get("accounts", []):
                result[name] -= slice_total
    return {k: round(v, 2) for k, v in result.items()}


def premium_by_date(cfg):
    """Net option premium (credits - buy-to-close debits) per date, split into the owner pool
    vs everything else. An order counts as the owner's if its id is in premium_split.owner_order_ids."""
    ps = cfg.get("premium_split", {})
    owner_pool = ps.get("owner_pool", "owner"); default_pool = ps.get("default_pool", "rest")
    owner_ids = set(ps.get("owner_order_ids") or [])
    try:
        import robin_stocks.robinhood as rh
        from dotenv import load_dotenv
        load_dotenv(".env")
        rh.login(os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD"), store_session=True)
    except Exception:
        return {}, owner_pool, default_pool
    start = cfg.get("start_date", "1970-01-01")
    accts = [a for a in dict.fromkeys(
        [cfg.get("shared_account")] + [x for p in cfg["pools"].values() for x in p.get("accounts", [])]) if a]
    agg = defaultdict(lambda: {owner_pool: 0.0, default_pool: 0.0})
    for acct in accts:
        try:
            for o in rh.orders.get_all_option_orders(account_number=acct) or []:
                if o.get("state") != "filled":
                    continue
                d = (o.get("created_at") or "")[:10]
                if d < start:
                    continue
                prem = float(o.get("processed_premium") or 0)
                signed = prem if o.get("direction") == "credit" else -prem
                who = owner_pool if o.get("id") in owner_ids else default_pool
                agg[d][who] += signed
        except Exception:
            continue
    return dict(agg), owner_pool, default_pool


def load_rows():
    if not os.path.exists(CSV_PATH):
        return []
    with open(CSV_PATH) as f:
        return list(csv.DictReader(f))

def save_rows(rows, fields):
    with open(CSV_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)


def render_md(rows, prem, pool_names, owner_pool, default_pool):
    def money(x): return f"${float(x):,.0f}"
    def delta(cur, prev):
        if prev in (None, ""): return "—"
        d = float(cur) - float(prev)
        return f"{'▲' if d>0 else '▼'} ${abs(d):,.0f}" if d else "•"

    latest = rows[-1]; prev = rows[-2] if len(rows) > 1 else None
    tot = {p: sum(v.get(p, 0.0) for v in prem.values()) for p in (owner_pool, default_pool)}
    prem_total = tot[owner_pool] + tot[default_pool]

    L = ["# 📊 Daily Ledger\n",
         f"_Auto-generated {latest['date']} · pools per `config/ledger.json` · DoD = vs prior trading day_\n",
         "## Today\n", "| Pool | Value | Day-over-day |", "|---|---:|---:|"]
    for p in pool_names:
        L.append(f"| {p} | {money(latest.get(p, 0))} | {delta(latest.get(p, 0), prev.get(p) if prev else None)} |")
    L.append(f"| **Total** | **{money(latest['total'])}** | {delta(latest['total'], prev['total'] if prev else None)} |")
    L.append(f"\n**💰 Premium since {rows[0]['date']}: {money(prem_total)}** — "
             f"{default_pool} {money(tot[default_pool])} · {owner_pool} {money(tot[owner_pool])} _(net of buy-to-close)_\n")

    L.append("## History (last 30 days)\n")
    L.append("| Date | " + " | ".join(f"{p} | Δ" for p in pool_names) + " | Total | Δ |")
    L.append("|" + "---|" * (1 + 2 * len(pool_names) + 2))
    window = rows[-30:]
    for i, r in enumerate(window):
        pr = window[i - 1] if i > 0 else None
        cells = " | ".join(f"{money(r.get(p, 0))} | {delta(r.get(p, 0), pr.get(p) if pr else None)}" for p in pool_names)
        L.append(f"| {r['date']} | {cells} | {money(r['total'])} | {delta(r['total'], pr['total'] if pr else None)} |")
    open(MD_PATH, "w").write("\n".join(L) + "\n")


def main():
    cfg = json.load(open(CFG_PATH))
    pool_names = list(cfg["pools"].keys())
    accts = fetch_accounts(cfg.get("api", "http://localhost:5001/api/portfolio"))
    pools = compute_pools(accts, cfg)
    total = round(sum(pools.values()), 2)
    today = datetime.date.today().isoformat()

    fields = ["date"] + pool_names + ["total"]
    rows = [r for r in load_rows() if r.get("date") != today]
    row = {"date": today, "total": total}; row.update(pools)
    rows.append(row); rows.sort(key=lambda r: r["date"])
    save_rows(rows, fields)

    prem, owner_pool, default_pool = premium_by_date(cfg)
    render_md(rows, prem, pool_names, owner_pool, default_pool)

    prev = rows[-2] if len(rows) > 1 else None
    def d(k): return "" if not prev else f" ({float(rows[-1][k]) - float(prev[k]):+,.0f} DoD)"
    summ = "  ".join(f"{p} ${float(pools[p]):,.0f}{d(p)}" for p in pool_names)
    print(f"{today}  {summ} | Total ${total:,.0f}{d('total')}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ledger error: {e}", file=sys.stderr); sys.exit(1)
