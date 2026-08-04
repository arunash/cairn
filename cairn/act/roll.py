#!/usr/bin/env python3
"""Roll a wheel book out one week, same strike (edit EXP_FROM/EXP_TO and `targets`).
   Shows guaranteed-fill net credit (STO bid - BTC ask). --live rolls where net >= MIN.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import robin_stocks.robinhood as rh
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
rh.login(os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD"), store_session=True)
LIVE = "--live" in sys.argv
MAIN = "MARGIN_ACCT"
EXP_FROM, EXP_TO = "2026-08-28", "2026-09-04"
MIN = 40.0  # min net credit per position to bother rolling

def tick(p): return round(round(p/0.05)*0.05, 2) if p >= 3 else round(max(p, 0.01), 2)
def px(s): return float(rh.stocks.get_latest_price(s)[0])
def getopt(sym, exp, strike, ot):
    for o in rh.options.find_tradable_options(sym, exp, optionType=ot):
        if abs(float(o["strike_price"]) - strike) < 0.01: return o
    return None
def mk(o):
    m = rh.options.get_option_market_data_by_id(o["id"]); return m[0] if m and m[0] else {}
def rid(r): return (r.get("id") or r) if isinstance(r, dict) else r

# Example book to roll — replace with your own open short options: (symbol, strike, "call"|"put", contracts)
targets = [("AAPL",220,"call",1),("MSFT",400,"put",1),("SPY",560,"put",2)]

print(f"=== ROLL 08-28 → 09-04  {'*** LIVE ***' if LIVE else 'DRY-RUN'} ===\n")
print(f"{'position':16}{'spot':>8}{'BTC ask':>9}{'STO bid':>9}{'net credit':>12}  roll?")
plan = []
for sym, k, ot, qty in targets:
    bo, so = getopt(sym, EXP_FROM, k, ot), getopt(sym, EXP_TO, k, ot)
    if not bo or not so:
        print(f"{sym+' '+str(k)+ot[0].upper():16}  (option not found)"); continue
    bm, sm = mk(bo), mk(so)
    btc = float(bm.get("ask_price") or 0); sto = float(sm.get("bid_price") or 0)
    net = (sto - btc) * 100 * qty
    spot = px(sym)
    ok = net >= MIN
    if ok: plan.append((sym, k, ot, qty, btc, sto))
    print(f"{sym+' '+str(k)+ot[0].upper()+' x'+str(qty):16}{spot:>8.0f}{btc:>9.2f}{sto:>9.2f}{net:>+12,.0f}  {'YES' if ok else 'skip'}")

tot = sum((s - b) * 100 * q for _, _, _, q, b, s in plan)
print(f"\nRolls that clear ${MIN:.0f} net: {len(plan)}  |  total net credit ~${tot:,.0f}")

if LIVE and plan:
    print("\n--- ROLLING (BTC then STO, sequenced) ---")
    for sym, k, ot, qty, btc, sto in plan:
        r1 = rh.orders.order_buy_option_limit("close", "debit", tick(btc), sym, qty, EXP_FROM, k, optionType=ot, account_number=MAIN, timeInForce="gtc")
        print(f"  BTC {sym} {k}{ot[0].upper()} x{qty} @ {tick(btc)}:", rid(r1))
        import time; time.sleep(1.5)
        r2 = rh.orders.order_sell_option_limit("open", "credit", tick(sto), sym, qty, EXP_TO, k, optionType=ot, account_number=MAIN, timeInForce="gtc")
        print(f"  STO {sym} {k}{ot[0].upper()} x{qty} @ {tick(sto)}:", rid(r2))
    print("\nRolled.")
elif not LIVE:
    print("\nDRY-RUN. add --live to roll the YES rows.")
