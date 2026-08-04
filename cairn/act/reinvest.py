#!/usr/bin/env python3
"""STANDING RULE: reinvest collected premiums IMMEDIATELY, routed per pool.
   preserve premium -> QQQ (in the account it was collected).  growth premium -> VOO (shared account).
   Run right after any premium is collected.
Usage: reinvest.py [--ira-qqq AMT] [--main-qqq AMT] [--main-voo AMT] [--live]
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import robin_stocks.robinhood as rh
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
rh.login(os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD"), store_session=True)
LIVE = "--live" in sys.argv
MAIN = "MARGIN_ACCT"; IRA = "IRA_ACCT"

def arg(flag):
    if flag in sys.argv:
        try: return float(sys.argv[sys.argv.index(flag) + 1])
        except Exception: return 0.0
    return 0.0
def rid(r): return (r.get("id") or r) if isinstance(r, dict) else r

jobs = []
if arg("--ira-qqq") > 0:  jobs.append(("QQQ", arg("--ira-qqq"),  IRA,  "preserve premium (IRA)"))
if arg("--main-qqq") > 0: jobs.append(("QQQ", arg("--main-qqq"), MAIN, "preserve premium (taxable)"))
if arg("--main-voo") > 0: jobs.append(("VOO", arg("--main-voo"), MAIN, "growth premium"))

print(f"=== REINVEST PREMIUMS  {'*** LIVE ***' if LIVE else 'DRY-RUN'} ===")
for sym, amt, acct, who in jobs:
    print(f"  BUY ${amt:.2f} {sym}   ({who}, acct …{acct[-4:]})")
    if LIVE:
        r = rh.orders.order_buy_fractional_by_price(sym, round(amt, 2), account_number=acct, timeInForce="gfd")
        print("     ->", rid(r))
if not LIVE:
    print("DRY-RUN. add --live to place.")
