#!/usr/bin/env python3
"""Cairn command line.  Usage:

    python -m cairn report     # build web/report.html from your live account (read-only)
    python -m cairn ledger     # update the intent-based pool ledger

Both are read-only. Trading only ever happens through the Act-mode MCP tools, with approval.
"""
import sys


def main():
    cmd = (sys.argv[1] if len(sys.argv) > 1 else "report").lower()
    if cmd == "report":
        from cairn.report.build import build
        build()
    elif cmd == "ledger":
        from cairn.compute.ledger import main as ledger_main
        ledger_main()
    else:
        print(f"unknown command: {cmd}\nusage: python -m cairn [report|ledger]", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
