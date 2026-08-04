#!/usr/bin/env python3
"""Watches for the right time to trim a CONCENTRATED position: ~tax-free AND minimal forward
premium given up. Emails TO when the window opens (once/day max). Read-only — it only alerts,
it never trades. Edit the CONFIG block for your own position."""
import warnings, os, ssl, smtplib
warnings.filterwarnings("ignore")
import robin_stocks.robinhood as rh
from dotenv import load_dotenv
from datetime import date
from email.mime.text import MIMEText
load_dotenv(".env")
rh.login(os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD"), store_session=True)

# ── CONFIG: describe the over-weight holding you want to trim ──
TO       = "you@example.com"
TICKER   = "<ticker>"       # the concentrated position
BASIS    = 0.0              # your cost basis per share
STRIKE   = 0.0              # strike of the covered calls sitting on the shares
EXP      = "2026-12-31"     # those calls' expiry (YYYY-MM-DD)
TRIM     = 700              # shares to sell
KEEP     = 1000             # shares to keep for a fresh covered-call program
REDEPLOY = "30% SCHD / 70% QQQ"
SENTINEL = os.path.expanduser("~/.cairn/.trim_alerted")


def gmail_send(subject, html):
    pw = open(os.path.expanduser("~/.cairn/gmail_app_password.txt")).read().strip()
    m = MIMEText(html, "html"); m["Subject"] = subject; m["From"] = TO; m["To"] = TO; m["Reply-To"] = TO
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(TO, pw); s.sendmail(TO, [TO], m.as_string())


spot = float(rh.stocks.get_latest_price(TICKER)[0])
gain = (spot - BASIS) * TRIM
ccm = None
for o in rh.options.find_tradable_options(TICKER, EXP, optionType="call"):
    if abs(float(o["strike_price"]) - STRIKE) < 0.01:
        md = rh.options.get_option_market_data_by_id(o["id"]); md = md[0] if md and md[0] else None
        if md: ccm = float(md.get("mark_price") or md.get("ask_price") or 0)
        break
dte = (date.fromisoformat(EXP) - date.today()).days

window, reason = False, ""
if dte <= 4 and spot < STRIKE:
    window = True
    reason = (f"The ${STRIKE:.0f} calls expire worthless in ~{dte} days ({TICKER} ${spot:.2f} &lt; ${STRIKE:.0f}) &mdash; "
              f"<b>no buy-back, zero forward premium given up</b>. Trim now: only ~${gain:,.0f} gain on {TRIM} sh "
              f"({'tax-free' if spot <= BASIS else 'tiny tax'}).")
elif spot <= BASIS:
    window = True
    reason = (f"{TICKER} ${spot:.2f} is <b>at/below your ${BASIS:.0f} basis &mdash; the trim is TAX-FREE.</b> "
              f"${STRIKE:.0f} CC buy-back ~${(ccm or 0)*(TRIM+KEEP):,.0f} to clear the shares.")
elif spot <= BASIS * 0.97 and ccm is not None and ccm <= 1.0:
    window = True
    reason = (f"{TICKER} ${spot:.2f} is near basis (only ~${gain:,.0f} gain on {TRIM} sh) AND the ${STRIKE:.0f} calls are "
              f"cheap (${ccm:.2f}) &mdash; a good low-cost window.")

last = open(SENTINEL).read().strip() if os.path.exists(SENTINEL) else ""
today = date.today().isoformat()
if window and last != today:
    html = f"""<h2>🎯 {TICKER} trim window is open</h2>
    <p>{reason}</p>
    <p><b>The plan:</b> buy back the ${STRIKE:.0f} calls (if any left) &rarr; sell <b>{TRIM} {TICKER}</b> (keep {KEEP:,})
    &rarr; redeploy <b>{REDEPLOY}</b> &rarr; sell fresh <b>30-DTE / 0.30&Delta; covered calls</b> on the {KEEP:,}.</p>
    <p>Reply <b>&ldquo;do the {TICKER} trim&rdquo;</b> and Cairn will stage the full sequence (Act mode, with your approval).</p>
    <p style="color:#888;font-size:12px">{TICKER} ${spot:.2f} · basis ${BASIS:.0f} · ${STRIKE:.0f} CC mark ${ccm} · {dte}d to {EXP}</p>"""
    gmail_send(f"🎯 {TICKER} trim window is open", html)
    os.makedirs(os.path.dirname(SENTINEL), exist_ok=True)
    open(SENTINEL, "w").write(today)
    print(f"ALERT SENT — {TICKER} ${spot:.2f}")
else:
    print(f"no alert. {TICKER} ${spot:.2f} | gain ${gain:,.0f} | ${STRIKE:.0f}CC ${ccm} | {dte}d | window={window}")
