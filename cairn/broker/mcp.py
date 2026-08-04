#!/usr/bin/env python3
"""Cairn's bridge to Robinhood, exposed as an MCP server for Claude Code.

SECURITY MODEL — read-only by default (enforced here, not just by prompt):

  * READ tools (portfolio, quotes, positions, orders, account) are ALWAYS registered.
  * WRITE tools (buy/sell stock, sell options) are registered ONLY when the environment
    variable  CAIRN_ACT_ENABLED == "1".

In Insights and Ask (Chat) modes that flag is unset, so the write tools are never added to
the server — they do not exist over the wire. A jailbroken, confused, or prompt-injected
agent cannot call a tool that was never registered. This is defense in depth: the guardrails
in CLAUDE.md are the first line; this gate is the one that actually holds.

Credentials come from the local .env (RH_USERNAME / RH_PASSWORD), are used only to log in,
and never leave this process. Nothing here prints, logs, or returns them.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
ACT_ENABLED = os.getenv("CAIRN_ACT_ENABLED", "0").strip() == "1"

try:
    from mcp.server.fastmcp import FastMCP
except Exception as exc:  # pragma: no cover - dependency hint
    raise SystemExit("Cairn's broker needs the MCP SDK. Install it:  pip install 'mcp>=1.2.0'") from exc

import robin_stocks.robinhood as rh

mcp = FastMCP("cairn-robinhood")

_logged_in = False


def _ensure_login():
    """Log in on first use. Raises if credentials are missing — never guesses, never logs them."""
    global _logged_in
    if _logged_in:
        return
    user, pw = os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD")
    if not user or not pw:
        raise RuntimeError("RH_USERNAME / RH_PASSWORD are not set in your local .env")
    rh.login(user, pw, store_session=True)
    _logged_in = True


# ── READ tools — always registered ────────────────────────────────────────────
@mcp.tool()
def get_portfolio() -> dict:
    """Current holdings: quantity, price, equity, and P&L for every position. Read-only."""
    _ensure_login()
    return rh.account.build_holdings()


@mcp.tool()
def get_account_summary() -> dict:
    """Cash, buying power, and total portfolio equity. Read-only."""
    _ensure_login()
    return rh.profiles.load_account_profile()


@mcp.tool()
def get_quote(symbol: str) -> dict:
    """Latest quote for a single ticker. Read-only."""
    _ensure_login()
    quotes = rh.stocks.get_quotes(symbol.upper())
    return (quotes or [None])[0] or {}


@mcp.tool()
def get_options_positions() -> list:
    """Open options positions. Read-only."""
    _ensure_login()
    return rh.options.get_open_option_positions() or []


@mcp.tool()
def get_options_orders() -> list:
    """Recent options orders (filled / open / cancelled). Read-only."""
    _ensure_login()
    return rh.orders.get_all_option_orders() or []


# ── WRITE tools — defined always, REGISTERED only in Act mode ──────────────────
# These are plain functions with no @mcp.tool() decorator. They become callable tools
# only inside the `if ACT_ENABLED` block below, so they simply don't exist on the server
# when Cairn runs read-only.
def buy_stock(symbol: str, amount_dollars: float) -> dict:
    """Place a fractional market BUY for a dollar amount. Requires Act mode."""
    _ensure_login()
    return rh.orders.order_buy_fractional_by_price(
        symbol.upper(), round(float(amount_dollars), 2), timeInForce="gfd")


def sell_stock(symbol: str, quantity: float) -> dict:
    """Place a market SELL for a share quantity. Requires Act mode."""
    _ensure_login()
    return rh.orders.order_sell_market(symbol.upper(), float(quantity))


def sell_option(symbol: str, expiry: str, strike: float, option_type: str,
                price: float, contracts: int = 1) -> dict:
    """Sell-to-open a covered call / cash-secured put at a limit credit. Requires Act mode."""
    _ensure_login()
    if option_type not in ("call", "put"):
        raise ValueError("option_type must be 'call' or 'put'")
    return rh.orders.order_sell_option_limit(
        "open", "credit", round(float(price), 2), symbol.upper(), int(contracts),
        expiry, float(strike), optionType=option_type, timeInForce="gtc")


if ACT_ENABLED:
    mcp.add_tool(buy_stock)
    mcp.add_tool(sell_stock)
    mcp.add_tool(sell_option)


def main():
    mode = "ACT MODE — write tools ENABLED" if ACT_ENABLED else "READ-ONLY — write tools NOT registered"
    print(f"[cairn.broker] Robinhood MCP starting · {mode}", file=sys.stderr)
    mcp.run()


if __name__ == "__main__":
    main()
