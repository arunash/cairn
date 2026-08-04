#!/usr/bin/env python3
"""Best-effort per-account ACH deposit/withdrawal parse from monthly account statements.
Set WINDOW_FROM/WINDOW_TO and fill SMAP with your own account numbers before running."""
import warnings; warnings.filterwarnings("ignore")
import robin_stocks.robinhood as rh, os, urllib.request, urllib.error, subprocess, re, tempfile, shutil
from collections import defaultdict
from dotenv import load_dotenv
load_dotenv(".env")
rh.login(os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD"), store_session=True)
token = rh.helper.SESSION.headers.get("Authorization")

class NoRedir(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a): return None
op = urllib.request.build_opener(NoRedir)

def fetch(url, path):
    try:
        data = op.open(urllib.request.Request(url, headers={"Authorization": token}), timeout=60).read()
    except urllib.error.HTTPError as e:
        data = urllib.request.urlopen(e.headers["Location"], timeout=60).read()
    open(path, "wb").write(data)

WINDOW_FROM, WINDOW_TO = "2026-01", "2026-06"
docs = [d for d in (rh.account.get_documents() or [])
        if d.get("type") == "account_statement" and WINDOW_FROM <= (d.get("date") or "")[:7] <= WINDOW_TO]
print("statements in window:", len(docs))

# Map each brokerage account number (exactly as printed on your statements) to a label.
SMAP = {"<account-number-1>":"Individual / margin", "<account-number-2>":"IRA",
        "<account-number-3>":"Cash", "<account-number-4>":"Custodial / UTMA"}
AMT = re.compile(r"\$([\d,]+\.\d{2})")
DATE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
ACCT = re.compile(r"Account #:\s*(\d+)")

# Statements are downloaded into a private 0700 temp dir (not shared /tmp) and removed after —
# they contain account numbers and balances, so we don't leave them lying around.
TMPDIR = tempfile.mkdtemp(prefix="cairn_stmt_")
agg = defaultdict(lambda: defaultdict(lambda: {"in": 0.0, "out": 0.0}))
for d in docs:
    ym = (d.get("date") or "")[:7]
    p = os.path.join(TMPDIR, f"st_{ym}_{d['id'][:6]}.pdf")
    fetch(d.get("download_url") or d.get("url"), p)
    lines = subprocess.run(["pdftotext", "-layout", p, "-"], capture_output=True, text=True).stdout.splitlines()
    cur = None
    for i, ln in enumerate(lines):
        m = ACCT.search(ln)
        if m:
            cur = m.group(1); continue
        if cur and ("ACH Deposit" in ln or "ACH Withdrawal" in ln):
            direction = "in" if "Deposit" in ln else "out"
            amt = None
            for j in range(i, min(i + 3, len(lines))):
                a = AMT.findall(lines[j])
                if a:
                    amt = float(a[-1].replace(",", "")); break
            dm = DATE.search(ln)
            mon = f"{dm.group(3)}-{dm.group(1)}" if dm else ym
            if amt:
                agg[cur][mon][direction] += amt

for snum, name in SMAP.items():
    if snum not in agg:
        print(f"\n=== {name} — no ACH activity found ===")
        continue
    print(f"\n=== {name} ===")
    print(f"{'Month':9}{'In':>12}{'Out':>12}{'Net':>12}")
    ti = to = 0
    for mo in sorted(agg[snum]):
        i, o = agg[snum][mo]["in"], agg[snum][mo]["out"]; ti += i; to += o
        print(f"{mo:9}{i:>12,.0f}{o:>12,.0f}{i-o:>12,.0f}")
    print(f"{'TOTAL':9}{ti:>12,.0f}{to:>12,.0f}{ti-to:>12,.0f}")

shutil.rmtree(TMPDIR, ignore_errors=True)  # wipe the downloaded statement PDFs
