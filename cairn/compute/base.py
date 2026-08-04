#!/usr/bin/env python3
"""Shared read-only session + helpers for the compute engines.

Everything here is READ-ONLY. Login uses your local .env; the symbol cache avoids
re-resolving the same instrument URL on every order.
"""
import os
import time
import robin_stocks.robinhood as rh
from dotenv import load_dotenv

try:
    from robin_stocks.robinhood.urls import orders_url, option_orders_url, account_profile_url
    from robin_stocks.robinhood.helper import request_get
    _PAGER = True
except Exception:
    _PAGER = False

_accounts = None

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_logged_in = False
_sym_cache = {}
# set True if any page of order history failed to load after retries — makes lot math partial
LOAD_INCOMPLETE = False


def login():
    """Authenticate once per process from .env. Never prints or returns credentials."""
    global _logged_in
    if _logged_in:
        return
    load_dotenv(os.path.join(ROOT, ".env"))
    user, pw = os.getenv("RH_USERNAME"), os.getenv("RH_PASSWORD")
    if not user or not pw:
        raise SystemExit("Set RH_USERNAME / RH_PASSWORD in .env first (copy from .env.example).")
    rh.login(user, pw, store_session=True)
    _logged_in = True


def symbol_for(instrument_url):
    """Resolve a stock instrument URL → ticker, cached."""
    if not instrument_url:
        return None
    if instrument_url not in _sym_cache:
        try:
            _sym_cache[instrument_url] = rh.stocks.get_symbol_by_url(instrument_url)
        except Exception:
            _sym_cache[instrument_url] = None
    return _sym_cache[instrument_url]


def paged_get(url, tries=6, pause=1.0):
    """Follow Robinhood's `next` cursor, retrying each page — robin_stocks' own paginator
    silently drops the rest of the history on the first hiccup, which corrupts lot math."""
    global LOAD_INCOMPLETE
    out, nxt, guard = [], url, 0
    while nxt and guard < 2000:
        guard += 1
        page = None
        for attempt in range(tries):
            page = request_get(nxt, "regular")
            if isinstance(page, dict) and "results" in page:
                break
            time.sleep(pause * (attempt + 1))
        if not (isinstance(page, dict) and "results" in page):
            LOAD_INCOMPLETE = True
            break
        out.extend(page.get("results") or [])
        nxt = page.get("next")
    return out


def accounts():
    """Every brokerage account the user holds: {number, type, cash}. Cached."""
    global _accounts
    if _accounts is not None:
        return _accounts
    login()
    if _PAGER:
        data = request_get(account_profile_url(), "results") or []
    else:
        p = rh.profiles.load_account_profile() or {}
        data = [p] if p.get("account_number") else []
    _accounts = [{"number": a.get("account_number"), "type": a.get("type"),
                  "cash": float(a.get("portfolio_cash") or a.get("cash") or 0)}
                 for a in data if a.get("account_number")]
    return _accounts


def stock_orders():
    """All stock orders across every account, fully paginated (with retries)."""
    login()
    if not _PAGER:
        return rh.orders.get_all_stock_orders() or []
    out = []
    for a in accounts():
        out += paged_get(orders_url(account_number=a["number"]))
    return out


def option_orders():
    """All options orders across every account, fully paginated (with retries)."""
    login()
    if not _PAGER:
        return rh.orders.get_all_option_orders() or []
    out = []
    for a in accounts():
        out += paged_get(option_orders_url(account_number=a["number"]))
    return out
