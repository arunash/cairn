#!/usr/bin/env python3
"""Cairn command line.  Usage:

    python -m cairn report     # build web/report.html from your live account (read-only)
    python -m cairn taxes      # print realized LT/ST gains, premium, and wash-sale flags
    python -m cairn ledger     # update the intent-based pool ledger

All read-only. Trading only ever happens through the Act-mode MCP tools, with approval.
"""
import sys


def _taxes():
    from cairn.compute import realized, premium, washsale
    rz = realized.summary()
    pr = premium.summary()
    wash = washsale.flags()
    print(f"— Realized {rz['year']} —")
    print(f"  long-term  : {rz['lt']:+,.2f}")
    print(f"  short-term : {rz['st']:+,.2f}")
    print(f"  net        : {rz['net']:+,.2f}")
    print(f"— Options premium —\n  {pr['year']}: {pr['ytd']:+,.2f}   all-time: {pr['total']:+,.2f}")
    if wash:
        print(f"— Wash-sale candidates ({len(wash)}) — screen only, confirm on 1099-B —")
        for w in wash:
            print(f"  {w['sym']:6} loss {w['loss']:+,.2f} sold {w['sold']}  repurchased {', '.join(w['replaced_on'])}")
    else:
        print("— No wash-sale candidates —")


def main():
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "report").lower()
    if cmd == "report":
        from cairn.report.build import build
        build()
    elif cmd == "taxes":
        _taxes()
    elif cmd == "ledger":
        from cairn.compute.ledger import main as ledger_main
        ledger_main()
    else:
        print(f"unknown command: {cmd}\nusage: python -m cairn [report|taxes|ledger]", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
