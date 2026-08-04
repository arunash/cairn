#!/usr/bin/env python3
"""Example wheel execution. DRY-RUN by default; --live to place.
 1. Rotate a slice: sell some QQQ in the shared account, buy VOO (a growth vehicle) with proceeds.
 2. IRA redeploy: sell 1 AMZN ~0.30d ~30DTE put.
 3. Re-wheel: NVDA covered call (shared account, growth) + HOOD covered call (IRA, preserve).
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import robin_stocks.robinhood as rh
from dotenv import load_dotenv
from datetime import date
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
rh.login(os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD"), store_session=True)
LIVE = "--live" in sys.argv
MAIN = "MARGIN_ACCT"; IRA = "IRA_ACCT"

def tick(p): return round(round(p/0.05)*0.05, 2) if p >= 3 else round(max(p, 0.01), 2)
def px(s): return float(rh.stocks.get_latest_price(s)[0])
def pick_exp(sym, days=30):
    exps = rh.options.get_chains(sym)["expiration_dates"]
    t = date.today()
    return min(exps, key=lambda e: abs((date.fromisoformat(e) - t).days - days))
def md(o):
    m = rh.options.get_option_market_data_by_id(o["id"]); return m[0] if m and m[0] else None
def find(sym, exp, ot, td=0.30):
    spot = px(sym); best = None
    for o in rh.options.find_tradable_options(sym, exp, optionType=ot):
        k = float(o["strike_price"])
        if abs(k - spot) / spot > 0.18: continue
        if ot == "call" and k < spot: continue
        if ot == "put" and k > spot: continue
        m = md(o)
        if not m or m.get("delta") in (None, "None"): continue
        de = abs(float(m["delta"])); bid = float(m.get("bid_price") or 0)
        if bid <= 0: continue
        if best is None or abs(de - td) < abs(best[1] - td): best = (o, de, m)
    return best
def rid(r): return (r.get("id") or r.get("detail") or r) if isinstance(r, dict) else r

print(f"=== MONDAY 2026-08-03  {'*** LIVE ***' if LIVE else 'DRY-RUN'} ===\n")

qqq, voo = px("QQQ"), px("VOO")
sell_qqq = 25.03; proceeds = sell_qqq * qqq
ax = px("AMZN"); aexp = pick_exp("AMZN", 30); ap = find("AMZN", aexp, "put", 0.30)
nx = px("NVDA"); nexp = pick_exp("NVDA", 30); nc = find("NVDA", nexp, "call", 0.30)
hx = px("HOOD"); hexp = pick_exp("HOOD", 30); hc = find("HOOD", hexp, "call", 0.30)

def line(o): k=float(o[0]["strike_price"]); return k, float(o[2]["bid_price"]), o[1]
print(f"[1] VOO FLAG  SELL {sell_qqq} QQQ @ ~${qqq:.2f} (~${proceeds:,.0f})  ->  BUY VOO @ ~${voo:.2f}")
if ap: k,b,d=line(ap); print(f"[2] AMZN put  SELL 1 {aexp} ${k:.0f}P  d{d:.2f}  ~${tick(b)*100:,.0f}  coll ${k*100:,.0f}")
if nc: k,b,d=line(nc); print(f"[3a] NVDA call SELL 1 {nexp} ${k:.0f}C  d{d:.2f}  ~${tick(b)*100:,.0f}  (growth)")
if hc: k,b,d=line(hc); print(f"[3b] HOOD call SELL 1 {hexp} ${k:.0f}C  d{d:.2f}  ~${tick(b)*100:,.0f}  (preserve)")

if LIVE:
    print("\n--- PLACING ---")
    r = rh.orders.order_sell_market("QQQ", sell_qqq, account_number=MAIN); print("  sell QQQ:", rid(r))
    amt = round(proceeds * 0.995, 2)
    r = rh.orders.order_buy_fractional_by_price("VOO", amt, account_number=MAIN); print(f"  buy VOO ${amt}:", rid(r))
    if ap:
        k, b, d = line(ap)
        r = rh.orders.order_sell_option_limit("open", "credit", tick(b), "AMZN", 1, aexp, k, optionType="put", account_number=IRA, timeInForce="gtc"); print("  AMZN put:", rid(r))
    if nc:
        k, b, d = line(nc)
        r = rh.orders.order_sell_option_limit("open", "credit", tick(b), "NVDA", 1, nexp, k, optionType="call", account_number=MAIN, timeInForce="gtc"); print("  NVDA call:", rid(r))
    if hc:
        k, b, d = line(hc)
        r = rh.orders.order_sell_option_limit("open", "credit", tick(b), "HOOD", 1, hexp, k, optionType="call", account_number=IRA, timeInForce="gtc"); print("  HOOD call:", rid(r))
    print("\nPlaced. Verify fills in a moment.")
else:
    print("\nDRY-RUN only. Re-run with --live to place.")
