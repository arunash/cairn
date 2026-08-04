#!/usr/bin/env python3
"""Example one-off reminder: nudge yourself to wheel a holding once its earnings clear.
Emails TO, then self-removes its LaunchAgent so it doesn't recur. This is a template —
set TICKER + TO (or delete the file). It only sends mail; it never trades."""
import os, ssl, smtplib, subprocess
from email.mime.text import MIMEText

TO = "you@example.com"
TICKER = "<ticker>"

def gmail_send(subject, html):
    pw = open(os.path.expanduser("~/.cairn/gmail_app_password.txt")).read().strip()
    m = MIMEText(html, "html"); m["Subject"] = subject; m["From"] = TO; m["To"] = TO; m["Reply-To"] = TO
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=ssl.create_default_context()) as s:
        s.login(TO, pw); s.sendmail(TO, [TO], m.as_string())

html = f"""
<h2>⏰ Wheel {TICKER} after earnings</h2>
<p>{TICKER} has now reported — the print is out, so it's clean to wheel.</p>
<ul>
  <li><b>Sell a covered call</b> — ~30 DTE / ~0.30 delta into the still-elevated post-earnings IV.
      Pick a strike at or above your cost basis so a call-away isn't a loss. If it gapped down hard, reassess first.</li>
  <li><b>Check any short puts</b> on the same name for assignment risk if it cratered.</li>
</ul>
<p>Tell Cairn &ldquo;wheel {TICKER}&rdquo; and it&rsquo;ll pull live strikes and stage the order (Act mode, with your approval).</p>
<p style="color:#888;font-size:12px">— Cairn · one-off reminder</p>
"""

gmail_send(f"⏰ Wheel {TICKER} after earnings", html)

# self-clean: this is a one-off, don't recur
try:
    plist = os.path.expanduser("~/Library/LaunchAgents/com.cairn.reminder.plist")
    subprocess.run(["launchctl", "unload", plist], check=False)
    os.remove(plist)
except Exception:
    pass
print("reminder sent + self-cleaned")
