#!/usr/bin/env python3
"""Build the Cairn Insights portal → web/report.html, from your live Robinhood account.

Renders the two-pane insights report: connected banner, topline, position-by-position table
(cost basis · holding period · options-on-it), realized LT/ST gains with the tax read, the
options wheel, "needs your attention" + "forward radar" cards, and an Ask-Cairn chat whose
answers are generated from YOUR real numbers. Read-only, deterministic, no LLM, no upload.

Basis/quantity are Robinhood's own (split- and transfer-adjusted); realized/holding-period
come from the FIFO lot engine. Figures are a decision aid — reconcile against your 1099.
"""
import os
import html
import json
import datetime

import robin_stocks.robinhood as rh
from cairn.compute.base import login, accounts, ROOT
from cairn.compute import base, positions, realized, washsale, premium, cashflow

OUT = os.path.join(ROOT, "web", "report.html")


# ── helpers ──────────────────────────────────────────────────────────────────
def _try(fn, default=None):
    try:
        return fn()
    except Exception as e:
        print(f"  (skipped a section: {e})")
        return default


def _money(x):
    x = float(x or 0)
    return ("−" if x < 0 else "") + "$" + f"{abs(x):,.0f}"


def _signed(x):
    x = float(x or 0)
    return ("+" if x >= 0 else "−") + "$" + f"{abs(x):,.0f}"


def _days_to(d):
    try:
        return (datetime.date.fromisoformat(d[:10]) - datetime.date.today()).days
    except Exception:
        return None


def _quotes(syms):
    """last + previous_close per symbol → for the day-change figure."""
    out = {}
    try:
        for q in (rh.stocks.get_quotes(syms) or []):
            if not q:
                continue
            s = q.get("symbol")
            last = float(q.get("last_trade_price") or q.get("last_extended_hours_trade_price") or 0)
            prev = float(q.get("previous_close") or last)
            out[s] = (last, prev)
    except Exception:
        pass
    return out


def _open_options():
    """symbol -> [ {side, otype, strike, expiry, qty} ] across all accounts."""
    login()
    out = {}
    for a in accounts():
        try:
            positions_ = rh.options.get_open_option_positions(account_number=a["number"]) or []
        except Exception:
            positions_ = []
        for p in positions_:
            qty = float(p.get("quantity") or 0)
            if qty == 0:
                continue
            sym = p.get("chain_symbol")
            oid = p.get("option_id") or (p.get("option") or "").rstrip("/").split("/")[-1]
            try:
                inst = rh.options.get_option_instrument_data_by_id(oid) or {}
            except Exception:
                inst = {}
            out.setdefault(sym, []).append({
                "side": p.get("type"),                       # short / long
                "otype": inst.get("type"),                    # call / put
                "strike": float(inst.get("strike_price") or 0),
                "expiry": inst.get("expiration_date"),
                "qty": qty,
            })
    return out


def _opt_desc(opts):
    parts = []
    for o in opts:
        n = int(o["qty"]) if o["qty"] == int(o["qty"]) else o["qty"]
        k = o["strike"]
        if o["otype"] == "call" and o["side"] == "short":
            parts.append((f"{n}× " if n and n > 1 else "") + f"${k:.0f} covered call")
        elif o["otype"] == "put" and o["side"] == "short":
            parts.append(f"${k:.0f} cash-secured put")
        elif o["otype"]:
            parts.append(f"${k:.0f} {o['otype']} ({o['side']})")
    return " · ".join(parts) if parts else "—"


def _doing(r, top_sym):
    if r["sym"] == top_sym and r["weight"] >= 25:
        return f'<span class="conc">{r["weight"]:.0f}% concentration</span>'
    if r["plpct"] >= 40:
        return f'🟢 Big winner — +{r["plpct"]:.0f}% on cost'
    if r["pl"] <= -800:
        return "Soft · underwater"
    if r["sym"] in ("VOO", "QQQ", "SPY", "VTI", "SCHD", "IVV"):
        return "Broad-market core"
    if r["pl"] > 0:
        return f'🟢 Up +{r["plpct"]:.0f}%'
    return "Flat"


def _collect():
    login()
    rows, total, accts = _try(positions.holdings, ([], 0.0, []))
    cash = sum(a.get("cash", 0.0) for a in accts)
    syms = [r["sym"] for r in rows]
    q = _quotes(syms) if syms else {}
    day = 0.0
    for r in rows:
        last, prev = q.get(r["sym"], (r["price"], r["price"]))
        day += (last - prev) * r["qty"]
    return {
        "rows": rows, "total": total, "accounts": accts, "cash": cash, "day": day,
        "conc": positions.concentration(rows, total) if rows else None,
        "realized": _try(realized.summary), "premium": _try(premium.summary),
        "cashflow": _try(cashflow.summary), "wash": _try(washsale.summary),
        "options": _try(_open_options, {}) or {},
        "incomplete": base.LOAD_INCOMPLETE,
        "ts": datetime.datetime.now().strftime("%H:%M"),
        "year": datetime.date.today().year,
    }


# ── narrative builders (attention cards, radar, chat KB) ─────────────────────
def _attention(d):
    rows, total, cash = d["rows"], d["total"], d["cash"]
    acct = total + cash
    cards, conc = [], d["conc"]
    if conc and conc["top"] and conc["top_weight"] >= 25:
        top = rows[0]
        cards.append(("crit", "Critical", f"Concentration in {conc['top']}",
                      f'<b><span class="fig">{_money(top["equity"])}</span> — {conc["top_weight"]:.0f}% of everything — in one name.</b> '
                      f"When one position runs the book, one bad print takes the whole account with it.",
                      f"<b>→ Trim toward ~20%.</b> Redeploy into a broad, non-correlated sleeve."))
    if acct and cash / acct >= 0.08:
        cards.append(("info", "Opportunity", f"{_money(cash)} cash — part is idle",
                      f"That's {cash / acct * 100:.0f}% of the account sitting uninvested — a quiet drag versus inflation.",
                      "<b>→ Deploy it</b> or ladder into T-bills for ~4–5%."))
    w = d["wash"]
    if w and w.get("count"):
        syms = ", ".join(x["sym"] for x in w["by_symbol"][:3])
        cards.append(("warn", "Tax", f"Wash-sale candidates — {w['count']} lots",
                      f'{_money(w["total_loss"])} of losses on {syms} were repurchased within 30 days, so those deductions are deferred, not banked.',
                      "<b>→ Space out re-buys</b> beyond 30 days after a loss sale to keep the deduction."))
    loser = min(rows, key=lambda r: r["pl"]) if rows else None
    if loser and loser["pl"] <= -1000 and len(cards) < 3:
        cards.append(("warn", "Position", f"{loser['sym']} is underwater",
                      f'{loser["sym"]} is down <span class="fig">{_money(loser["pl"])}</span> ({loser["plpct"]:+.0f}%).',
                      "<b>→ Decide:</b> add, hold, or harvest the loss against gains."))
    return cards[:3]


def _radar(d):
    cards = []
    rz = d["realized"]
    if rz and rz["net"] < 0:
        room = -rz["net"]
        cards.append(("good", "Tax", "Realized-loss cushion — open now",
                      f'You\'re carrying a <span class="fig">{_money(room)}</span> net realized loss this year. '
                      f"You can realize about that much in gains <b>tax-free</b> (e.g. trimming a winner) before you owe."))
    w = d["wash"]
    if w and w.get("count"):
        cards.append(("warn", "Tax", "Wash-sale clock — 30-day window",
                      "After any loss sale, re-buying the same name (or selling puts on it) within 30 days voids the deduction. "
                      "Watch the reinvestment cadence."))
    conc = d["conc"]
    if conc and conc["top"] and conc["top_weight"] >= 25:
        cards.append(("info", "Risk", f"{conc['top']} trim window",
                      f"{conc['top']} at {conc['top_weight']:.0f}% is your single biggest risk. Trimming on strength de-risks the book."))
    return cards[:3]


def _kb(d):
    rows, total, cash = d["rows"], d["total"], d["cash"]
    acct = total + cash
    upl = sum(r["pl"] for r in rows)
    conc = d["conc"] or {}
    rz = d["realized"] or {}
    pr = d["premium"] or {}
    winners = sorted([r for r in rows if r["pl"] > 0], key=lambda r: -r["pl"])
    losers = sorted([r for r in rows if r["pl"] < 0], key=lambda r: r["pl"])
    top = rows[0] if rows else None
    kb = []

    if top and conc.get("top"):
        kb.append({"k": ["trim", "concentration", "concentr", "reduce", "too much"],
                   "a": f'<b>{conc["top"]} is {conc["top_weight"]:.0f}% of the account</b> ({_money(top["equity"])}). '
                        f'Trimming toward ~20% is the highest-value move — it cuts single-name risk. Redeploy the proceeds into a broad, non-correlated sleeve rather than more of the same.'})
        kb.append({"k": ["diversif", "balanced", "spread", "sectors"],
                   "a": f'Your top name is {conc["top_weight"]:.0f}% and the top few dominate the book (HHI {conc.get("hhi", 0):,}). '
                        f'The more one name runs, the more everything moves together. Trimming the leader into a broad index or income sleeve is the fix.'})
    if pr:
        kb.append({"k": ["premium", "income", "wheel", "options", "made from options"],
                   "a": f'You\'ve collected <b>{_signed(pr.get("ytd", 0))} in options premium</b> this year (net of buy-to-closes), '
                        f'{_signed(pr.get("total", 0))} all-time.'})
    if rz:
        if rz.get("net", 0) < 0:
            kb.append({"k": ["tax", "capital gain", "realized", "wash", "harvest", "loss"],
                       "a": f'You\'ve realized a <b>net {_money(rz["net"])} capital loss</b> this year ({_money(rz.get("lt",0))} long-term, {_money(rz.get("st",0))} short-term). '
                            f'That\'s a tax asset — it offsets gains, then $3k of income, rest carries forward. You have room to realize ~{_money(-rz["net"])} of gains tax-free.'})
        else:
            kb.append({"k": ["tax", "capital gain", "realized", "wash", "harvest"],
                       "a": f'You\'ve realized <b>{_signed(rz["net"])} in gains</b> this year ({_signed(rz.get("lt",0))} long-term, {_signed(rz.get("st",0))} short-term). '
                            f'You\'ll owe tax on that unless you harvest offsetting losses before year-end.'})
    if winners:
        w0 = winners[0]
        extra = (", " + ", ".join(f"{x['sym']} {_signed(x['pl'])}" for x in winners[1:3])) if len(winners) > 1 else ""
        kb.append({"k": ["best", "winner", "biggest gain", "doing well", "most up"],
                   "a": f'<b>{w0["sym"]} is the standout — {_signed(w0["pl"])} ({w0["plpct"]:+.0f}% on cost)</b>{extra}.'})
    if losers:
        l0 = losers[0]
        kb.append({"k": ["worst", "loser", "losing", "down", "red"],
                   "a": f'<b>{l0["sym"]}, {_money(l0["pl"])}</b> ({l0["plpct"]:+.0f}%) is your weakest. Net unrealized across the book is {_signed(upl)}.'})
    kb.append({"k": ["cash", "idle", "buying power", "deploy", "sitting"],
               "a": f'You have <b>{_money(cash)} cash</b> ({cash/acct*100:.0f}% of the account). Idle cash is a drag — put it to work or ladder into T-bills.'})
    lt_names = [r["sym"] for r in rows if r.get("term") == "LT"]
    kb.append({"k": ["long term", "short term", "holding period", "held", "how long"],
               "a": (f'Clearly long-term (lower tax): <b>{", ".join(lt_names)}</b>. ' if lt_names else '')
                    + 'Anything under a year sells at the higher short-term rate — letting a lot cross one year can drop the rate a lot.'})
    # ranked "what should I do"
    steps = []
    if conc.get("top") and conc.get("top_weight", 0) >= 25:
        steps.append(f'<b>1) Trim {conc["top"]}</b> toward 20%')
    if acct and cash / acct >= 0.08:
        steps.append(f'<b>{len(steps)+1}) Deploy the {_money(cash)} cash</b>')
    if rz and rz.get("net", 0) < 0:
        steps.append(f'<b>{len(steps)+1}) Use the {_money(-rz["net"])} loss</b> — realize gains tax-free')
    if not steps:
        steps = ["<b>Hold and monitor</b> — nothing urgent flagged"]
    kb.append({"k": ["what should i do", "recommend", "priorities", "next", "advice"],
               "a": "Ranked: " + ". ".join(steps) + "."})
    kb.append({"k": ["how am i doing", "health", "overall", "summary", "good shape"],
               "a": f'Account {_money(acct)}, unrealized {_signed(upl)}. '
                    + (f'Main risk: {conc["top"]} at {conc.get("top_weight",0):.0f}%. ' if conc.get("top_weight", 0) >= 25 else 'Reasonably balanced. ')
                    + (f'Income engine healthy ({_signed(pr.get("ytd",0))} premium YTD).' if pr else '')})
    return kb


# ── render ───────────────────────────────────────────────────────────────────
_CSS = r"""<style>
  :root{
    --ground:#F1F3EF;--surface:#FFFFFF;--surface-2:#F5F7F3;
    --ink:#1B221E;--muted:#5F685F;--faint:#98A199;
    --hairline:#E6E9E3;--hairline-2:#EDF0EA;
    --accent:#2F6B4F;--accent-soft:rgba(47,107,79,.08);
    --crit:#B23A2E;--warn:#B07A2E;--good:#2C7A55;
    --serif:"Iowan Old Style","Palatino Linotype",Palatino,"Book Antiqua",Georgia,serif;
    --sans:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  }
  @media (prefers-color-scheme:dark){:root{
    --ground:#0E120F;--surface:#161B17;--surface-2:#1B211C;
    --ink:#ECEFE9;--muted:#9AA39C;--faint:#69726B;--hairline:#2A312B;--hairline-2:#232A24;
    --accent:#77BB95;--accent-soft:rgba(119,187,149,.12);--crit:#E08A7E;--warn:#D8AC63;--good:#6FB58F;
  }}
  :root[data-theme="light"]{--ground:#F1F3EF;--surface:#FFFFFF;--surface-2:#F5F7F3;--ink:#1B221E;--muted:#5F685F;--faint:#98A199;--hairline:#E6E9E3;--hairline-2:#EDF0EA;--accent:#2F6B4F;--accent-soft:rgba(47,107,79,.08);--crit:#B23A2E;--warn:#B07A2E;--good:#2C7A55;}
  :root[data-theme="dark"]{--ground:#0E120F;--surface:#161B17;--surface-2:#1B211C;--ink:#ECEFE9;--muted:#9AA39C;--faint:#69726B;--hairline:#2A312B;--hairline-2:#232A24;--accent:#77BB95;--accent-soft:rgba(119,187,149,.12);--crit:#E08A7E;--warn:#D8AC63;--good:#6FB58F;}
  *{box-sizing:border-box;margin:0;padding:0;}
  body{font-family:var(--sans);background:var(--ground);color:var(--ink);min-height:100vh;-webkit-font-smoothing:antialiased;padding:28px 16px 64px;line-height:1.5;}
  .doc{max-width:1180px;margin:0 auto;}
  .tab{font-variant-numeric:tabular-nums;}
  .head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;}
  .brand{display:flex;align-items:center;gap:11px;}
  .mark{width:26px;height:26px;position:relative;}
  .mark span{position:absolute;left:50%;transform:translateX(-50%);width:0;height:0;border-left:5px solid transparent;border-right:5px solid transparent;border-bottom:6px solid var(--accent);}
  .mark .s1{bottom:15px;border-left-width:3px;border-right-width:3px;border-bottom-width:4px;opacity:.9;}
  .mark .s2{bottom:8px;opacity:.75;} .mark .s3{bottom:1px;border-left-width:7px;border-right-width:7px;border-bottom-width:7px;opacity:.6;}
  .wordmark{font-family:var(--serif);font-size:23px;font-weight:600;letter-spacing:.03em;}
  .sub{font-size:12px;color:var(--faint);}
  .livebar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px;color:var(--muted);}
  .dot{width:7px;height:7px;border-radius:50%;background:var(--good);}
  .topline{display:grid;grid-template-columns:1.3fr 1fr 1fr 1fr;gap:1px;background:var(--hairline-2);border:1px solid var(--hairline-2);border-radius:16px;overflow:hidden;margin:14px 0 8px;}
  .tl{background:var(--surface);padding:14px 16px;}
  .tl .l{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}
  .tl .v{font-family:var(--serif);font-size:24px;font-weight:600;margin-top:5px;letter-spacing:-.01em;}
  .tl .v.sm{font-size:19px;} .tl .n{font-size:11px;color:var(--faint);margin-top:2px;}
  .tl .up{color:var(--good);} .tl .dn{color:var(--crit);}
  .sect{font-size:12px;letter-spacing:.13em;text-transform:uppercase;color:var(--muted);font-weight:600;margin:30px 0 12px;display:flex;align-items:center;gap:10px;}
  .sect::after{content:"";flex:1;height:1px;background:var(--hairline);}
  .sect .n{font-family:var(--serif);letter-spacing:0;text-transform:none;color:var(--faint);font-weight:400;font-size:12px;}
  .tblwrap{overflow-x:auto;border:1px solid var(--hairline);border-radius:14px;background:var(--surface);}
  table{border-collapse:collapse;width:100%;min-width:720px;font-size:13px;}
  thead th{font-size:10px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted);font-weight:600;text-align:right;padding:11px 12px;border-bottom:1px solid var(--hairline);background:var(--surface-2);}
  thead th:first-child,thead th.l{text-align:left;}
  tbody td{padding:11px 12px;border-top:1px solid var(--hairline-2);text-align:right;vertical-align:top;}
  tbody tr:first-child td{border-top:none;}
  td.l{text-align:left;}
  .tk{font-weight:600;font-size:13.5px;}
  .doing{color:var(--muted);font-size:12px;margin-top:2px;line-height:1.4;}
  .num{font-family:var(--serif);font-variant-numeric:tabular-nums;}
  .pct{color:var(--faint);font-size:11px;}
  .up{color:var(--good);} .dn{color:var(--crit);}
  .pill{display:inline-block;font-size:10px;padding:2px 7px;border-radius:999px;font-weight:600;white-space:nowrap;}
  th:nth-child(4),td:nth-child(4){white-space:nowrap;}
  .pill.lt{background:rgba(44,122,85,.1);color:var(--good);border:1px solid color-mix(in srgb,var(--good) 30%,transparent);}
  .pill.st{background:rgba(176,122,46,.1);color:var(--warn);border:1px solid color-mix(in srgb,var(--warn) 28%,transparent);}
  .pill.na{background:var(--surface-2);color:var(--faint);border:1px solid var(--hairline);}
  .opt{font-size:11px;color:var(--muted);}
  .conc{color:var(--crit);font-weight:600;}
  tr.sumrow td{border-top:2px solid var(--hairline);background:var(--surface-2);font-weight:600;}
  .grid{display:grid;grid-template-columns:minmax(0,1fr) 372px;gap:28px;align-items:start;margin-top:2px;}
  .main{min-width:0;} .side{position:sticky;top:20px;}
  .side .chat{display:flex;flex-direction:column;height:calc(100vh - 40px);}
  .side .thread{flex:1;max-height:none;}
  .chat-h{font-family:var(--serif);font-size:17px;font-weight:600;margin-bottom:12px;padding-bottom:11px;border-bottom:1px solid var(--hairline-2);}
  .chat-h span{font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400;}
  @media (max-width:940px){.grid{grid-template-columns:1fr;gap:0;} .side{position:static;} .side .chat{height:auto;} .side .thread{max-height:360px;}}
  .cards{display:flex;flex-direction:column;gap:11px;}
  .two-col > div > .sect{margin-top:30px;}
  .card{background:var(--surface);border:1px solid var(--hairline);border-radius:14px;padding:15px 17px 15px 19px;position:relative;overflow:hidden;}
  .card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;}
  .card.crit::before{background:var(--crit);} .card.warn::before{background:var(--warn);} .card.good::before{background:var(--good);} .card.info::before{background:var(--accent);}
  .card .ch{display:flex;align-items:baseline;justify-content:space-between;gap:12px;}
  .card .ct{font-size:15px;font-weight:600;} .card .csev{font-size:10px;letter-spacing:.08em;text-transform:uppercase;font-weight:700;flex:none;}
  .card.crit .csev{color:var(--crit);} .card.warn .csev{color:var(--warn);} .card.good .csev{color:var(--good);} .card.info .csev{color:var(--accent);}
  .card .cbody{font-size:13.5px;line-height:1.55;margin-top:6px;} .card .cbody .fig{font-family:var(--serif);font-weight:600;}
  .card .cact{font-size:12.5px;color:var(--muted);margin-top:9px;padding-top:9px;border-top:1px solid var(--hairline-2);} .card .cact b{color:var(--accent);font-weight:600;}
  .cg{display:grid;grid-template-columns:1fr 1fr 1fr;gap:1px;background:var(--hairline-2);border:1px solid var(--hairline-2);border-radius:14px;overflow:hidden;}
  .cgt{background:var(--surface);padding:14px 16px;} .cgt.hl{background:var(--surface-2);}
  .cgt .l{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);}
  .cgt .v{font-family:var(--serif);font-size:22px;font-weight:600;margin-top:5px;} .cgt .n{font-size:11px;color:var(--faint);margin-top:2px;}
  .cgnote{font-size:12.5px;color:var(--muted);line-height:1.55;margin-top:10px;background:rgba(44,122,85,.07);border:1px solid color-mix(in srgb,var(--good) 22%,transparent);border-radius:12px;padding:12px 15px;} .cgnote b{color:var(--good);}
  .two-col{display:grid;grid-template-columns:1fr 1fr;gap:22px;} @media (max-width:760px){.two-col{grid-template-columns:1fr;}}
  .connect{background:var(--surface);border:1px solid color-mix(in srgb,var(--accent) 32%,var(--hairline));border-radius:16px;padding:14px 18px;margin-bottom:10px;}
  .connect-h{display:flex;align-items:center;gap:10px;flex-wrap:wrap;}
  .connect-h .title{font-family:var(--serif);font-size:16px;font-weight:600;display:flex;align-items:center;gap:10px;}
  .cdot{width:8px;height:8px;border-radius:50%;background:var(--good);box-shadow:0 0 0 3px color-mix(in srgb,var(--good) 20%,transparent);flex:none;}
  .connect-h .cmeta{font-family:var(--sans);font-size:12px;color:var(--faint);font-weight:400;}
  .warnband{background:rgba(176,122,46,.09);border:1px solid color-mix(in srgb,var(--warn) 30%,transparent);border-radius:12px;padding:11px 15px;font-size:12.5px;color:var(--muted);margin-bottom:10px;} .warnband b{color:var(--warn);}
  .chat{background:var(--surface);border:1px solid var(--hairline);border-radius:16px;padding:16px;}
  .thread{display:flex;flex-direction:column;gap:10px;overflow-y:auto;margin-bottom:12px;}
  .cmsg{font-size:13.5px;line-height:1.55;max-width:90%;padding:10px 14px;border-radius:14px;}
  .cmsg.cai{background:var(--surface-2);border:1px solid var(--hairline-2);align-self:flex-start;border-bottom-left-radius:4px;}
  .cmsg.you{background:var(--accent);color:#fff;align-self:flex-end;border-bottom-right-radius:4px;}
  .cmsg b{font-weight:600;} .cmsg.cai b{color:var(--accent);}
  .chips{display:flex;gap:7px;flex-wrap:wrap;margin-bottom:11px;}
  .chips button{font-size:12px;color:var(--muted);background:var(--surface-2);border:1px solid var(--hairline);border-radius:999px;padding:6px 12px;cursor:pointer;font-family:inherit;}
  .chips button:hover{border-color:var(--accent);color:var(--accent);}
  .cbar{display:flex;gap:9px;}
  .cbar input{flex:1;border:1px solid var(--hairline);background:var(--surface-2);color:var(--ink);border-radius:12px;padding:12px 14px;font-family:inherit;font-size:13.5px;outline:none;}
  .cbar input:focus{border-color:var(--accent);}
  .cbar button{flex:none;width:42px;border:none;background:var(--accent);color:#fff;border-radius:12px;font-size:16px;cursor:pointer;}
  .foot{margin-top:26px;padding-top:16px;border-top:1px solid var(--hairline);font-size:11px;color:var(--faint);line-height:1.6;} .foot b{color:var(--muted);}
  @media (max-width:640px){.topline{grid-template-columns:1fr 1fr;} .cg{grid-template-columns:1fr;}}
</style>"""

_CHAT_JS = r"""<script>
(function(){
  var KB=__KB__;
  function reply(t){
    t=(t||"").toLowerCase().trim();
    if(/^(buy|sell|short|purchase|place|execute|submit|trade|roll|close|open)\b/.test(t)
       || /\b(place|execute|submit|put in|make|enter)\b[^?]*\b(order|trade|buy|sell|position)\b/.test(t)
       || /\bcan you (buy|sell|place|execute|trade|order|short|roll|close|move|transfer|withdraw)\b/.test(t)
       || /\b(withdraw|transfer|move) (money|cash|funds)\b/.test(t)){
      return "I&rsquo;m <b>read-only</b> &mdash; I analyze and explain your portfolio, but I never place trades or move money. Any action stays in your hands, inside Robinhood.";
    }
    var best=null,bs=0;
    KB.forEach(function(e){var s=0;e.k.forEach(function(kw){if(t.indexOf(kw)>=0&&kw.length>s)s=kw.length;});if(s>bs){bs=s;best=e;}});
    if(best) return best.a;
    return "I don&rsquo;t have an answer for that. I only speak to <b>your Robinhood account and this portfolio</b>, from data I can actually see &mdash; and if I can&rsquo;t fetch a figure I&rsquo;ll say so rather than guess. Try a position, your taxes, concentration, income, or &lsquo;what should I do.&rsquo;";
  }
  var thread=document.getElementById("cthread");
  function add(cls,h){var d=document.createElement("div");d.className="cmsg "+cls;d.innerHTML=h;thread.appendChild(d);thread.scrollTop=thread.scrollHeight;}
  function addYou(text){var d=document.createElement("div");d.className="cmsg you";d.textContent=text;thread.appendChild(d);thread.scrollTop=thread.scrollHeight;}
  function ask(t){t=(t||"").slice(0,400);if(!t.trim())return;addYou(t);setTimeout(function(){add("cai",reply(t));},220);}
  document.getElementById("cform").addEventListener("submit",function(e){e.preventDefault();var i=document.getElementById("cin");ask(i.value);i.value="";});
  document.getElementById("cchips").addEventListener("click",function(e){var b=e.target.closest("button");if(b)ask(b.textContent);});
})();
</script>"""


def _render(d):
    rows, total, cash = d["rows"], d["total"], d["cash"]
    acct = total + cash
    upl = sum(r["pl"] for r in rows)
    day = d["day"]
    top_sym = rows[0]["sym"] if rows else ""
    pr, rz, cf, w = d["premium"], d["realized"], d["cashflow"], d["wash"]
    opts = d["options"]
    price_by = {r["sym"]: r["price"] for r in rows}
    n_opt_lines = sum(len(v) for v in opts.values())

    # topline
    day_cls = "up" if day >= 0 else "dn"
    topline = "".join([
        f'<div class="tl"><div class="l">Account value</div><div class="v tab">{_money(acct)}</div><div class="n {day_cls}">{"▲" if day>=0 else "▼"} {_money(abs(day))} today</div></div>',
        f'<div class="tl"><div class="l">Unrealized P&amp;L</div><div class="v sm tab {"up" if upl>=0 else "dn"}">{_signed(upl)}</div><div class="n">across {len(rows)} positions</div></div>',
        f'<div class="tl"><div class="l">Premium · {d["year"]}</div><div class="v sm tab up">{_signed(pr.get("ytd",0)) if pr else "—"}</div><div class="n">{n_opt_lines} open option lines</div></div>',
        f'<div class="tl"><div class="l">Cash</div><div class="v sm tab">{_money(cash)}</div><div class="n">{cash/acct*100:.0f}% of account</div></div>',
    ])

    # positions table
    trs = []
    for r in rows:
        term = str(r.get("term", "—"))
        pill = "lt" if term == "LT" else ("st" if term == "ST" else "na")
        label = "Long-term" if term == "LT" else ("Short-term" if term == "ST" else term)
        recon = "" if r.get("recon_ok", True) else ' <span class="pct">≈</span>'
        trs.append(
            f'<tr><td class="l"><span class="tk">{html.escape(r["sym"])}</span><div class="doing">{_doing(r, top_sym)}</div></td>'
            f'<td class="num">{_money(r["cost"])}</td>'
            f'<td><span class="num">{_money(r["equity"])}</span><div class="pct">{r["weight"]:.1f}%</div></td>'
            f'<td><span class="pill {pill}">{html.escape(label)}</span>{recon}</td>'
            f'<td class="num {"up" if r["pl"]>=0 else "dn"}">{_signed(r["pl"])}<div class="pct">{r["plpct"]:+.0f}%</div></td>'
            f'<td class="l opt">{html.escape(_opt_desc(opts.get(r["sym"], [])))}</td></tr>')
    trs.append(
        f'<tr class="sumrow"><td class="l">Cash &amp; dry powder</td><td class="num">—</td>'
        f'<td><span class="num">{_money(cash)}</span><div class="pct">{cash/acct*100:.1f}%</div></td>'
        f'<td>—</td><td class="num">—</td><td class="l opt">across {len(d["accounts"])} accounts</td></tr>')

    # realized
    if rz:
        net = rz["net"]
        note = (f'You\'re sitting on a <b>net {_money(net)} capital loss</b> this year — a tax asset. It offsets gains, then $3k of income, '
                f'rest carries forward. You have room to <b>realize ~{_money(-net)} of gains tax-free</b> before you owe.'
                if net < 0 else
                f'You\'ve realized <b>{_signed(net)} in gains</b> this year — you\'ll owe tax on that unless you harvest offsetting losses before year-end.')
        realized_html = (
            '<div class="sect">Realized gains <span class="n">— this year, for tax</span></div>'
            '<div class="cg">'
            f'<div class="cgt"><div class="l">Short-term</div><div class="v {"up" if rz["st"]>=0 else "dn"}">{_signed(rz["st"])}</div><div class="n">taxed as income</div></div>'
            f'<div class="cgt"><div class="l">Long-term</div><div class="v {"up" if rz["lt"]>=0 else "dn"}">{_signed(rz["lt"])}</div><div class="n">lower rate</div></div>'
            f'<div class="cgt hl"><div class="l">Net realized YTD</div><div class="v {"up" if net>=0 else "dn"}">{_signed(net)}</div><div class="n">{"a tax asset" if net<0 else "taxable"}</div></div>'
            '</div>'
            f'<div class="cgnote">{note} From your sell orders this year, split by each lot\'s holding period.</div>')
    else:
        realized_html = ""

    # options table
    opt_rows = []
    for sym, lst in opts.items():
        px = price_by.get(sym)
        for o in lst:
            dte = _days_to(o["expiry"] or "")
            if o["side"] == "short" and o["otype"] == "call":
                status = ('<span class="up">safe (OTM)</span>' if px is not None and px < o["strike"] else '<span class="dn">ITM — call-away risk</span>')
            elif o["side"] == "short" and o["otype"] == "put":
                status = ('<span class="up">safe</span>' if px is not None and px > o["strike"] else '<span class="dn">ITM — assignment risk</span>')
            else:
                status = '<span class="opt">—</span>'
            opt_rows.append(
                f'<tr><td class="l tk">{html.escape(sym)}</td><td class="l opt">{html.escape(_opt_desc([o]))}</td>'
                f'<td>{("~"+str(dte)+"d") if dte is not None else "—"}</td><td>{status}</td></tr>')
    if opt_rows and pr:
        opt_rows.append(
            f'<tr class="sumrow"><td class="l">Premium collected</td><td class="l opt">net of buy-to-closes · {d["year"]}</td>'
            f'<td>—</td><td class="up num">{_signed(pr.get("ytd",0))}</td></tr>')
    options_html = (
        '<div class="sect">Options &amp; premiums <span class="n">— the wheel</span></div>'
        '<div class="tblwrap"><table><thead><tr><th class="l">Underlying</th><th class="l">Open contract</th><th>Expiry</th><th>Status</th></tr></thead>'
        f'<tbody>{"".join(opt_rows)}</tbody></table></div>') if opt_rows else ""

    # attention + radar cards
    def _cardhtml(cards):
        out = []
        for sev, label, title, body, *act in cards:
            a = f'<div class="cact">{act[0]}</div>' if act else ""
            out.append(f'<div class="card {sev}"><div class="ch"><div class="ct">{title}</div><div class="csev">{label}</div></div>'
                       f'<div class="cbody">{body}</div>{a}</div>')
        return "".join(out)

    attn = _attention(d)
    radar = _radar(d)
    cards_html = ""
    if attn or radar:
        cards_html = '<div class="two-col">'
        cards_html += f'<div><div class="sect">Needs your attention</div><div class="cards">{_cardhtml(attn)}</div></div>' if attn else "<div></div>"
        cards_html += f'<div><div class="sect">Forward radar</div><div class="cards">{_cardhtml(radar)}</div></div>' if radar else "<div></div>"
        cards_html += '</div>'

    warn_html = ('<div class="warnband"><b>⚠ Order history incomplete</b> — some pages didn\'t load, so realized gains and holding periods may be partial. Re-run to retry.</div>'
                 if d.get("incomplete") else "")

    recon_bad = [r["sym"] for r in rows if not r.get("recon_ok", True)]
    recon_note = (f'<div style="font-size:11px;color:var(--faint);margin-top:8px;line-height:1.5">≈ {len(recon_bad)} position(s) ({html.escape(", ".join(recon_bad))}) '
                  f'have lot history that doesn\'t reconcile to Robinhood\'s share count (split / transfer / DRIP) — value &amp; unrealized P&amp;L are exact, but reconstructed basis &amp; holding period are approximate.</div>') if recon_bad else ""

    kb_json = json.dumps(_kb(d))
    chat_js = _CHAT_JS.replace("__KB__", kb_json)

    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cairn Insights — your Robinhood account</title>{_CSS}</head><body><div class="doc">
  <div class="head">
    <div class="brand"><div class="mark"><span class="s1"></span><span class="s2"></span><span class="s3"></span></div>
      <div><div class="wordmark">Cairn Insights</div><div class="sub">everything Robinhood scatters, on one page</div></div></div>
    <div class="livebar"><span class="dot"></span><span>Updated {d["ts"]} · read-only · local — nothing was uploaded</span></div>
  </div>
  <div class="grid">
    <div class="main">
      <div class="connect"><div class="connect-h"><div class="title"><span class="cdot"></span> Connected to Robinhood <span class="cmeta">· read-only · local · {len(d["accounts"])} accounts</span></div></div></div>
      {warn_html}
      <div class="topline">{topline}</div>
      <div class="sect">Your portfolio <span class="n">— position by position</span></div>
      <div class="tblwrap"><table><thead><tr><th class="l">Stock</th><th>Cost basis</th><th>Value · %</th><th>Held</th><th>Unrealized</th><th class="l">Options on it</th></tr></thead>
      <tbody>{"".join(trs)}</tbody></table></div>
      <div style="font-size:11px;color:var(--faint);margin-top:8px;line-height:1.5"><b style="color:var(--muted)">Held</b> = holding period, which sets your tax rate: <span class="pill lt" style="font-size:9px">Long-term</span> (&gt;1 yr) is taxed far lower than <span class="pill st" style="font-size:9px">short-term</span>.</div>
      {recon_note}
      {realized_html}
      {options_html}
      {cards_html}
    </div>
    <div class="side"><div class="chat">
      <div class="chat-h">Ask Cairn <span>&mdash; your portfolio, answered</span></div>
      <div class="thread" id="cthread"><div class="cmsg cai">Ask me about your account &mdash; concentration, taxes, a position, or &ldquo;what should I do.&rdquo; I read the whole picture at once. I&rsquo;m <b>read-only</b>: I explain and advise, but never place trades or move money.</div></div>
      <div class="chips" id="cchips"><button>Am I too concentrated?</button><button>What's my tax situation?</button><button>How's my income?</button><button>What should I do?</button></div>
      <form class="cbar" id="cform" autocomplete="off"><input id="cin" placeholder="Ask about your portfolio…" aria-label="Ask"><button type="submit" aria-label="Send">↑</button></form>
    </div></div>
  </div>
  <div class="foot"><b>How this was made:</b> Cairn stitched your live positions &amp; prices, your trade &amp; options history, and your statements into one view, then ran concentration, holding-period, cost-basis, tax, income, and wash-sale checks — <b>read-only, on your machine.</b> Cost basis is Robinhood's own (split/transfer-adjusted); realized &amp; holding-period are reconstructed via FIFO. <b>Reconcile against your 1099 — software, not financial or tax advice.</b></div>
</div>{chat_js}</body></html>
"""


def build():
    d = _collect()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w") as f:
        f.write(_render(d))
    print(f"Wrote {OUT}  ({len(d['rows'])} positions · {_money(d['total'] + d['cash'])} account value)")
    print("Open it:  open web/report.html   (or: python -m cairn serve)")


if __name__ == "__main__":
    build()
