#!/usr/bin/env python3
"""Cairn command line.  Usage:

    python -m cairn report     # build web/report.html from your live account (read-only)
    python -m cairn taxes      # print realized LT/ST gains, premium, and wash-sale flags
    python -m cairn ledger     # update the intent-based pool ledger

All read-only. Trading only ever happens through the Act-mode MCP tools, with approval.
"""
import sys


def _taxes():
    from cairn.compute import realized, premium, washsale, base
    rz = realized.summary()
    pr = premium.summary()
    ws = washsale.summary()
    print(f"— Realized {rz['year']} —")
    print(f"  long-term  : {rz['lt']:+,.2f}")
    print(f"  short-term : {rz['st']:+,.2f}")
    print(f"  net        : {rz['net']:+,.2f}")
    print(f"— Options premium —\n  {pr['year']}: {pr['ytd']:+,.2f}   all-time: {pr['total']:+,.2f}")
    if ws["count"]:
        print(f"— Wash-sale candidates: {ws['count']} lots, {ws['total_loss']:+,.2f} total (screen only, confirm on 1099-B) —")
        for r in ws["by_symbol"]:
            print(f"  {r['sym']:6} {r['count']:>3} lots  {r['loss']:+,.2f}")
    else:
        print("— No wash-sale candidates —")
    if base.LOAD_INCOMPLETE:
        print("\n⚠ order history incomplete — figures may be partial; re-run to retry.")


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
