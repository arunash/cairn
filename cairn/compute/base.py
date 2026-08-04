#!/usr/bin/env python3
"""Shared read-only session + helpers for the compute engines.

Everything here is READ-ONLY. Login uses your local .env; the symbol cache avoids
re-resolving the same instrument URL on every order.
"""
import os
import robin_stocks.robinhood as rh
from dotenv import load_dotenv

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_logged_in = False
_sym_cache = {}


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
