#!/usr/bin/env python3
"""Build the Cairn insights report → web/report.html, from your live Robinhood account.

This is the deterministic **Insights** layer — read-only, no LLM. It pulls your holdings
through robin_stocks and renders one static page: total value, unrealized P&L, concentration,
and per-position cost basis / weight. Deeper analytics (realized long/short-term gains, options
premium, wash-sale flags, statement cash-flows) live in `cairn/compute` and surface as they land.

The page is written to your machine only. Nothing is uploaded.
"""
import os
import html
import datetime
import robin_stocks.robinhood as rh
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "web", "report.html")


def _login():
    load_dotenv(os.path.join(ROOT, ".env"))
    user, pw = os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD")
    if not user or not pw:
        raise SystemExit("Set RH_USERNAME / RH_PASSWORD in .env first (copy from .env.example).")
    rh.login(user, pw, store_session=True)


def _gather():
    holdings = rh.account.build_holdings() or {}
    rows = []
    for sym, h in holdings.items():
        qty = float(h.get("quantity") or 0)
        price = float(h.get("price") or 0)
        basis = float(h.get("average_buy_price") or 0)
        equity = float(h.get("equity") or qty * price)
        cost = basis * qty
        rows.append({
            "sym": sym, "qty": qty, "price": price, "basis": basis,
            "equity": equity, "cost": cost, "pl": equity - cost,
            "plpct": ((equity - cost) / cost * 100) if cost else 0.0,
        })
    rows.sort(key=lambda r: r["equity"], reverse=True)
    total = sum(r["equity"] for r in rows)
    for r in rows:
        r["weight"] = (r["equity"] / total * 100) if total else 0.0

    cash = 0.0
    try:
        prof = rh.profiles.load_account_profile() or {}
        cash = float(prof.get("portfolio_cash") or prof.get("cash") or 0)
    except Exception:
        pass
    return rows, total, cash


def _money(x):
    return f"${x:,.0f}"


def _signed(x):
    return ("+" if x >= 0 else "−") + f"${abs(x):,.0f}"


def _render(rows, total, cash):
    upl = sum(r["pl"] for r in rows)
    top = rows[0] if rows else None
    account = total + cash
    conc = f"{top['sym']} is {top['weight']:.0f}% of your equity" if top else "no positions"
    trs = "\n".join(
        "<tr><td class='s'>{sym}</td><td>{qty:g}</td><td>{price}</td><td>{basis}</td>"
        "<td>{eq}</td><td class='{cls}'>{pl} ({plp:+.0f}%)</td><td>{w:.1f}%</td></tr>".format(
            sym=html.escape(r["sym"]), qty=r["qty"], price=_money(r["price"]), basis=_money(r["basis"]),
            eq=_money(r["equity"]), cls=("up" if r["pl"] >= 0 else "dn"),
            pl=_signed(r["pl"]), plp=r["plpct"], w=r["weight"])
        for r in rows)
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cairn — your report</title>
<style>
  :root{{--ground:#0F1411;--surface:#161C18;--ink:#ECEFE9;--muted:#9AA39C;--faint:#6E766F;
    --hairline:#2A312B;--accent:#77BB95;--gold:#D3B168;--crit:#E08A7E;
    --serif:"Iowan Old Style",Palatino,Georgia,serif;--sans:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;}}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:var(--ground);color:var(--ink);font-family:var(--sans);line-height:1.5;padding:40px 22px 80px;}}
  .wrap{{max-width:860px;margin:0 auto;}}
  h1{{font-family:var(--serif);font-size:30px;letter-spacing:.02em;}}
  .sub{{color:var(--faint);font-size:13px;margin-top:4px;}}
  .top{{display:flex;gap:14px;flex-wrap:wrap;margin:26px 0;}}
  .card{{background:var(--surface);border:1px solid var(--hairline);border-radius:14px;padding:16px 18px;flex:1;min-width:150px;}}
  .card .k{{font-size:12px;color:var(--muted);letter-spacing:.02em;}}
  .card .v{{font-family:var(--serif);font-size:26px;margin-top:4px;font-variant-numeric:tabular-nums;}}
  .up{{color:var(--accent);}} .dn{{color:var(--crit);}}
  .conc{{background:var(--surface);border:1px solid var(--hairline);border-left:3px solid var(--gold);
    border-radius:10px;padding:12px 16px;color:var(--muted);font-size:14px;margin-bottom:22px;}}
  .conc b{{color:var(--ink);}}
  table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums;}}
  th,td{{text-align:right;padding:10px 8px;border-bottom:1px solid var(--hairline);}}
  th:first-child,td:first-child{{text-align:left;}}
  th{{color:var(--faint);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.08em;}}
  td.s{{font-weight:600;}}
  footer{{margin-top:28px;color:var(--faint);font-size:12px;}}
</style></head><body><div class="wrap">
  <h1>Your portfolio, on one page</h1>
  <div class="sub">Generated {ts} · read-only · local file — nothing was uploaded</div>
  <div class="top">
    <div class="card"><div class="k">Account value</div><div class="v">{_money(account)}</div></div>
    <div class="card"><div class="k">Unrealized P&amp;L</div><div class="v {'up' if upl>=0 else 'dn'}">{_signed(upl)}</div></div>
    <div class="card"><div class="k">Cash</div><div class="v">{_money(cash)}</div></div>
  </div>
  <div class="conc">Concentration — <b>{html.escape(conc)}</b>. The higher one name runs, the more the whole book moves with it.</div>
  <table>
    <tr><th>Symbol</th><th>Qty</th><th>Price</th><th>Cost basis</th><th>Value</th><th>Unrealized</th><th>Weight</th></tr>
    {trs}
  </table>
  <footer>Cairn · money, unmangled · not financial advice — a tool you run yourself.</footer>
</div></body></html>
"""


def build():
    _login()
    rows, total, cash = _gather()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(_render(rows, total, cash))
    print(f"Wrote {OUT}  ({len(rows)} positions · {_money(total + cash)} account value)")
    print("Open it:  open web/report.html")


if __name__ == "__main__":
    build()
