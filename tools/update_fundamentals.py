"""
Maverick Investor — monthly stock fundamentals refresh.

Rewrites P/E, market cap, dividend yield, ROCE and TTM sales/profit growth
for every row in the STOCKS array in MaverickInvestor/stock-screener.html,
sourced from Screener.in — the source the page credits.

Why monthly, and why slow
-------------------------
These six figures only move when a company reports, which is quarterly.
Fetching them weekly would be 150 needless requests against someone else's
server for numbers that had not changed.

That matters here beyond good manners. On 2026-09-09 a 150-page burst at 4
concurrent workers got this IP tarpitted: every subsequent request, robots.txt
included, took a flat 21.2 seconds. No 429, no Retry-After — just silence
stretched out. That is Screener telling us we asked for too much, and the
correct response is to ask for less, not to spread the load across UAs or
addresses until it stops noticing.

So: once a month, one request at a time, with real spacing between them.
A full pass is roughly 13 minutes of mostly waiting, which a monthly cron
absorbs without noticing.

If this dataset ever needs to be fresher than monthly, the answer is a
sanctioned feed — Screener sells data exports — not a faster crawler.

Safety rules, since a bad match would silently corrupt investment data:
  - Screener's price is cross-checked against the price already on the page;
    a >25% disagreement means the symbol probably resolved to a different
    company, so that stock is skipped entirely
  - an implausible individual value is dropped for that field only
  - if fewer than 90% of stocks return usable fundamentals, NOTHING is
    written — a half-refreshed table would silently mix two vintages of
    data across rows, which is worse than one uniformly older table

Stdlib only. Run:
    python tools/update_fundamentals.py
"""
import datetime
import json
import os
import re
import sys
import tempfile

import screener_fundamentals
import stock_tickers

HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "MaverickInvestor", "stock-screener.html")

# Two independent sources agreeing on price is the strongest evidence we have
# that a ticker resolved to the company we meant.
MAX_SOURCE_DIVERGENCE = 0.25
# Below this share of stocks refreshed, write nothing at all.
MIN_COVERAGE = 0.90

# field -> (low, high) plausibility bounds. A value outside its range is a
# parse error, not a remarkable company, so the field is dropped rather
# than published.
BOUNDS = {
    "pe": (0, 1000),
    "divYield": (0, 25),
    "roce": (-100, 200),
    "salesGr": (-100, 1000),
    "profitGr": (-100, 1000),
}


def clean(fields, current, name, ticker, notes):
    """Validate one stock's scraped fundamentals against the row we already
    have. Returns a dict of accepted field updates, or None to skip the row."""
    screener_price = fields.get("price")
    page_price = current.get("price") or 0
    if screener_price and page_price > 0:
        divergence = abs(screener_price / page_price - 1)
        if divergence > MAX_SOURCE_DIVERGENCE:
            notes.append(f"{name} ({ticker}): price disagrees with the page "
                         f"({page_price} vs Screener {screener_price}, {divergence * 100:.0f}%) "
                         f"— skipped, check the ticker mapping")
            return None

    out = {}
    mcap = fields.get("mcap")
    if mcap and mcap > 0:
        old = current.get("mcap") or 0
        # Market cap tracks price; an order-of-magnitude jump means a misparse
        # (crore vs rupee, most likely), not genuine news.
        if old <= 0 or 0.2 < mcap / old < 5:
            out["mcap"] = round(mcap, 2)

    for key, (low, high) in BOUNDS.items():
        v = fields.get(key)
        if v is not None and low < v < high:
            out[key] = round(v, 2)

    return out


def main():
    text = open(HTML_PATH, encoding="utf-8").read()
    m = re.search(r"const STOCKS=(\[.*?\]);", text, re.DOTALL)
    if not m:
        sys.exit("STOCKS array not found in stock-screener.html — aborting without writes")
    stocks = json.loads(m.group(1))

    total = len(stocks)
    print(f"fetching fundamentals for {total} stocks from Screener.in, "
          f"one at a time at {screener_fundamentals.REQUEST_SPACING}s spacing "
          f"(~{total * screener_fundamentals.REQUEST_SPACING / 60:.0f} min)")

    # Collected first, applied only if coverage clears the floor — so a run
    # that dies partway leaves the page untouched rather than half-updated.
    pending, failures, notes = {}, [], []
    for i, s in enumerate(stocks, 1):
        name = s["n"]
        ticker = stock_tickers.TICKERS.get(name)
        if not ticker:
            failures.append(f"{name}: no ticker mapped")
            continue

        fields, err = screener_fundamentals.fetch(ticker)
        if err:
            failures.append(f"{name} ({ticker}): {err}")
            continue

        accepted = clean(fields, s, name, ticker, notes)
        if accepted is None:
            failures.append(f"{name} ({ticker}): failed price cross-check")
            continue
        pending[name] = accepted

        if i % 25 == 0:
            print(f"  {i}/{total} …")

    coverage = len(pending) / total
    print(f"fundamentals fetched for {len(pending)}/{total} ({coverage * 100:.0f}%) · "
          f"{len(failures)} failed")
    for line in failures:
        print("  fail:", line)
    for line in notes:
        print("  note:", line)

    if coverage < MIN_COVERAGE:
        sys.exit(f"only {coverage * 100:.0f}% coverage (floor is {MIN_COVERAGE * 100:.0f}%) — "
                 f"writing nothing rather than mixing two vintages of data in one table")

    by_name = {s["n"]: s for s in stocks}
    for name, updates in pending.items():
        by_name[name].update(updates)

    new_blob = json.dumps(stocks, separators=(", ", ": "))
    text = text[:m.start(1)] + new_blob + text[m.end(1):]

    today = f"{datetime.date.today().day} {datetime.date.today():%B %Y}"
    text, n = re.subn(r'(id="fundAsOf">)[^<]*(</span>)', rf"\g<1>{today}\g<2>", text, count=1)
    if n == 0:
        sys.exit('id="fundAsOf" marker not found — aborting without writes')

    d = os.path.dirname(HTML_PATH)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, HTML_PATH)
    print("wrote", HTML_PATH)


if __name__ == "__main__":
    main()
