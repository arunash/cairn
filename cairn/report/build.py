#!/usr/bin/env python3
"""Build the Cairn insights report → web/report.html, from your live Robinhood account.

The deterministic **Insights** layer — read-only, no LLM. It unifies what Robinhood scatters:
  • account value, cash, and net money you've contributed
  • every position with cost basis, unrealized P&L, holding period (LT/ST), and weight
  • concentration (top name + Herfindahl index)
  • realized capital gains this year, split long-term vs short-term
  • options premium collected and dividends received
  • wash-sale candidates to review

Written to a local file only. Nothing is uploaded. Figures are reconstructed from your order
history (FIFO) — a decision aid, not tax advice. Reconcile against your 1099.
"""
import os
import html
import datetime
import robin_stocks.robinhood as rh

from cairn.compute.base import login, ROOT
from cairn.compute import base, positions, realized, washsale, premium, cashflow

OUT = os.path.join(ROOT, "web", "report.html")


def _try(fn, default=None):
    try:
        return fn()
    except Exception as e:
        print(f"  (skipped a section: {e})")
        return default


def _cash():
    try:
        p = rh.profiles.load_account_profile() or {}
        return float(p.get("portfolio_cash") or p.get("cash") or 0)
    except Exception:
        return 0.0


def _collect():
    login()
    rows, total = _try(positions.holdings, ([], 0.0))
    return {
        "rows": rows,
        "total": total,
        "cash": _cash(),
        "conc": positions.concentration(rows, total) if rows else None,
        "realized": _try(realized.summary),
        "premium": _try(premium.summary),
        "cashflow": _try(cashflow.summary),
        "wash": _try(washsale.summary),
        "incomplete": base.LOAD_INCOMPLETE,
        "ts": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "year": datetime.date.today().year,
    }


def _money(x):
    return f"${x:,.0f}"


def _signed(x):
    return ("+" if x >= 0 else "−") + f"${abs(x):,.0f}"


def _card(k, v, cls=""):
    return f"<div class='card'><div class='k'>{k}</div><div class='v {cls}'>{v}</div></div>"


def _render(d):
    rows, total, cash = d["rows"], d["total"], d["cash"]
    account = total + cash
    upl = sum(r["pl"] for r in rows)
    cf, rz, pr, wash = d["cashflow"], d["realized"], d["premium"], d["wash"]

    cards = [
        _card("Account value", _money(account)),
        _card("Unrealized P&amp;L", _signed(upl), "up" if upl >= 0 else "dn"),
        _card("Cash", _money(cash)),
    ]
    if cf:
        cards.append(_card("Net contributed", _money(cf["net_contributed"])))
    top = "".join(cards)

    conc_html = ""
    if d["conc"] and d["conc"]["top"]:
        c = d["conc"]
        conc_html = (f"<div class='band gold'>Concentration — <b>{html.escape(c['top'])} is "
                     f"{c['top_weight']:.0f}% of your equity</b> · {c['n']} positions · "
                     f"HHI {c['hhi']:,}. The higher one name runs, the more the whole book moves with it.</div>")

    trs = "\n".join(
        "<tr><td class='s'>{sym}</td><td>{qty:g}</td><td>{price}</td><td>{basis}</td>"
        "<td>{eq}</td><td class='{cls}'>{pl} ({plp:+.0f}%)</td><td class='term'>{term}</td><td>{w:.1f}%</td></tr>".format(
            sym=html.escape(r["sym"]), qty=round(r["qty"], 4), price=_money(r["price"]), basis=_money(r["basis"]),
            eq=_money(r["equity"]), cls=("up" if r["pl"] >= 0 else "dn"), pl=_signed(r["pl"]),
            plp=r["plpct"], term=html.escape(str(r.get("term", "—"))) + ("" if r.get("recon_ok", True) else " ≈"),
            w=r["weight"])
        for r in rows) or "<tr><td colspan='8' style='color:var(--faint)'>No stock positions.</td></tr>"
    recon_bad = [r["sym"] for r in rows if not r.get("recon_ok", True)]
    recon_html = ""
    if recon_bad:
        recon_html = (f"<div class='sub' style='margin-top:8px'>≈ {len(recon_bad)} position(s) "
                      f"({html.escape(', '.join(recon_bad))}) have lot history that doesn't reconcile to Robinhood's "
                      f"current share count — usually a stock split, transfer-in, or DRIP. Their <b>value &amp; unrealized "
                      f"P&amp;L are exact</b> (straight from Robinhood); the reconstructed cost basis &amp; holding period are approximate.</div>")

    # realized / income strip
    strip = []
    if rz:
        strip.append(_card(f"Realized {d['year']} · long-term", _signed(rz['lt']), "up" if rz['lt'] >= 0 else "dn"))
        strip.append(_card(f"Realized {d['year']} · short-term", _signed(rz['st']), "up" if rz['st'] >= 0 else "dn"))
    if pr:
        strip.append(_card(f"Options premium · {d['year']}", _signed(pr['ytd'])))
    if cf:
        strip.append(_card(f"Dividends · {d['year']}", _money(cf['dividends_ytd'])))
    strip_html = f"<div class='top'>{''.join(strip)}</div>" if strip else ""

    warn_html = ""
    if d.get("incomplete"):
        warn_html = ("<div class='band crit'><b>⚠ Order history incomplete</b> — some pages of your "
                     "trade history didn't load, so realized gains and holding periods may be partial. Re-run to retry.</div>")

    wash_html = ""
    if wash and wash["count"]:
        items = "".join(
            f"<li><b>{html.escape(w['sym'])}</b> — {w['count']} lot(s), {_signed(w['loss'])} potentially disallowed</li>"
            for w in wash["by_symbol"])
        wash_html = (f"<div class='band crit'><b>⚠ Wash-sale candidates — {wash['count']} lots, "
                     f"{_signed(wash['total_loss'])} total</b><ul>{items}</ul>"
                     f"<span class='fine'>Usually weekly ETF reinvestment: the loss shifts to the replacement shares' "
                     f"basis, it isn't lost. A screen, not a determination — confirm on your 1099-B.</span></div>")

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cairn — your report</title>
<style>
  :root{{--ground:#0F1411;--surface:#161C18;--ink:#ECEFE9;--muted:#9AA39C;--faint:#6E766F;
    --hairline:#2A312B;--accent:#77BB95;--gold:#D3B168;--crit:#E08A7E;
    --serif:"Iowan Old Style",Palatino,Georgia,serif;--sans:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;}}
  *{{box-sizing:border-box;margin:0;padding:0;}}
  body{{background:var(--ground);color:var(--ink);font-family:var(--sans);line-height:1.5;padding:40px 22px 80px;}}
  .wrap{{max-width:900px;margin:0 auto;}}
  h1{{font-family:var(--serif);font-size:30px;letter-spacing:.02em;}}
  h2{{font-family:var(--serif);font-size:19px;margin:30px 0 12px;color:var(--muted);font-weight:600;}}
  .sub{{color:var(--faint);font-size:13px;margin-top:4px;}}
  .top{{display:flex;gap:12px;flex-wrap:wrap;margin:22px 0;}}
  .card{{background:var(--surface);border:1px solid var(--hairline);border-radius:14px;padding:15px 17px;flex:1;min-width:150px;}}
  .card .k{{font-size:12px;color:var(--muted);}}
  .card .v{{font-family:var(--serif);font-size:24px;margin-top:4px;font-variant-numeric:tabular-nums;}}
  .up{{color:var(--accent);}} .dn{{color:var(--crit);}}
  .band{{background:var(--surface);border:1px solid var(--hairline);border-radius:10px;padding:12px 16px;
    color:var(--muted);font-size:14px;margin:6px 0 4px;}}
  .band.gold{{border-left:3px solid var(--gold);}} .band.crit{{border-left:3px solid var(--crit);}}
  .band b{{color:var(--ink);}} .band ul{{margin:8px 0 4px 18px;font-size:13px;}} .band .fine{{font-size:12px;color:var(--faint);}}
  table{{width:100%;border-collapse:collapse;font-size:14px;font-variant-numeric:tabular-nums;}}
  th,td{{text-align:right;padding:9px 8px;border-bottom:1px solid var(--hairline);}}
  th:first-child,td:first-child{{text-align:left;}}
  th{{color:var(--faint);font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.07em;}}
  td.s{{font-weight:600;}} td.term{{color:var(--muted);font-size:12px;}}
  footer{{margin-top:30px;color:var(--faint);font-size:12px;line-height:1.6;}}
</style></head><body><div class="wrap">
  <h1>Your portfolio, on one page</h1>
  <div class="sub">Generated {d['ts']} · read-only · local file — nothing was uploaded</div>
  <div class="top">{top}</div>
  {warn_html}
  {conc_html}
  {wash_html}
  <h2>Positions</h2>
  <table>
    <tr><th>Symbol</th><th>Qty</th><th>Price</th><th>Cost basis</th><th>Value</th><th>Unrealized</th><th>Held</th><th>Weight</th></tr>
    {trs}
  </table>
  {recon_html}
  <h2>Realized &amp; income</h2>
  {strip_html or "<div class='sub'>No realized activity yet this year.</div>"}
  <footer>
    Cairn · money, unmangled. Figures are reconstructed from your order history using FIFO lot matching;
    stock splits and transferred-in shares are not basis-adjusted, and wash-sale flags are a screen only.
    <b>Reconcile against your 1099 — this is software, not financial or tax advice.</b>
  </footer>
</div></body></html>
"""


def build():
    d = _collect()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(_render(d))
    n = len(d["rows"])
    print(f"Wrote {OUT}  ({n} positions · {_money(d['total'] + d['cash'])} account value)")
    print("Open it:  open web/report.html")


if __name__ == "__main__":
    build()
