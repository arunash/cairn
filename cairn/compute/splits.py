#!/usr/bin/env python3
"""A small, curated table of forward stock splits — LOCAL data, no network call.

Robinhood doesn't expose split factors via its API, so reconstructing realized gains from
raw order history mis-matches quantities across a split (a pre-split buy of 1 share vs a
post-split sell of N). This table lets the lot engine restate pre-split executions into
current-share terms, so FIFO realized gains and holding periods come out right for these names.

It covers common, widely-held recent splits. It is deliberately curated (wrong split data is
worse than none) — extend it with a PR. Ratio = new shares per old share; date = ex-date.
Positions/basis do NOT use this table — those come from Robinhood's already-adjusted numbers.
"""

# symbol -> list of (ex_date, forward_ratio)
SPLITS = {
    "AAPL": [("2020-08-31", 4)],
    "TSLA": [("2020-08-31", 5), ("2022-08-25", 3)],
    "NVDA": [("2021-07-20", 4), ("2024-06-10", 10)],
    "AMZN": [("2022-06-06", 20)],
    "GOOGL": [("2022-07-18", 20)],
    "GOOG": [("2022-07-18", 20)],
    "SHOP": [("2022-07-04", 10)],
    "DXCM": [("2022-06-13", 4)],
    "FTNT": [("2022-06-23", 5)],
    "PANW": [("2022-09-14", 3)],
    "WMT": [("2024-02-26", 3)],
    "AVGO": [("2024-07-15", 10)],
    "CMG": [("2024-06-26", 50)],
    "SMCI": [("2024-10-01", 10)],
    "LRCX": [("2024-10-03", 10)],
}


def adjust(symbol, date, qty, price):
    """Restate an execution into current-share terms: apply every split that happened AFTER it."""
    factor = 1.0
    for ex_date, ratio in SPLITS.get(symbol, ()):
        if (date or "")[:10] < ex_date:
            factor *= ratio
    if factor != 1.0:
        return qty * factor, price / factor
    return qty, price
