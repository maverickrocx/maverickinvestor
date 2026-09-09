"""
Maverick Investor — weekly stock price refresh.

Rewrites the `price` field of every row in the STOCKS array in
MaverickInvestor/stock-screener.html from Yahoo Finance's plain `chart`
endpoint (NSE tickers, ".NS" suffix) — cookie-free, fast and long-stable.

Price only. The other six columns (P/E, market cap, dividend yield, ROCE,
sales and profit growth) come from Screener.in on a monthly cadence via
update_fundamentals.py, because they only move when a company reports and
because Screener will not tolerate a weekly 150-page crawl (see that
module for the details).

Safety rules, since a bad ticker match would silently corrupt investment
data:
  - a stock with no ticker mapping, a failed fetch, or a >45% implied
    weekly price move is skipped and logged, not guessed at
  - if fewer than 70% of stocks refresh, nothing is written at all

Stdlib only. Run:
    python tools/update_stock_prices.py
"""
import datetime
import json
import os
import re
import sys
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import stock_tickers

HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "MaverickInvestor", "stock-screener.html")

MAX_WEEKLY_MOVE = 0.45
MAX_WORKERS = 16
UA = "Mozilla/5.0 (compatible; MaverickInvestorBot/1.0; +https://maverickinvestor.in)"


def fetch_price(ticker):
    sym = urllib.parse.quote(ticker + ".NS", safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.load(r)
    result = data.get("chart", {}).get("result")
    if not result:
        return None
    price = result[0].get("meta", {}).get("regularMarketPrice")
    return float(price) if price else None


def fetch_stock(name):
    ticker = stock_tickers.TICKERS.get(name)
    if not ticker:
        return name, ticker, None, "no ticker mapped"
    try:
        price = fetch_price(ticker)
    except Exception as e:
        return name, ticker, None, f"{type(e).__name__}: {str(e)[:80]}"
    if not price or price <= 0:
        return name, ticker, None, "no usable price"
    return name, ticker, price, None


def main():
    text = open(HTML_PATH, encoding="utf-8").read()
    m = re.search(r"const STOCKS=(\[.*?\]);", text, re.DOTALL)
    if not m:
        sys.exit("STOCKS array not found in stock-screener.html — aborting without writes")
    stocks = json.loads(m.group(1))
    by_name = {s["n"]: s for s in stocks}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(fetch_stock, by_name.keys()))

    updated, skipped, review = 0, [], []
    for name, ticker, price, err in results:
        s = by_name[name]
        if err:
            skipped.append(f"{name} ({ticker or '?'}): {err}")
            continue
        old = s.get("price") or 0
        if old <= 0:
            skipped.append(f"{name} ({ticker}): no existing price to compare against")
            continue
        ratio = price / old
        if abs(ratio - 1) > MAX_WEEKLY_MOVE:
            review.append(f"{name} ({ticker}): {old} -> {price} ({(ratio - 1) * 100:+.1f}%)")
            continue
        s["price"] = round(price, 2)
        updated += 1

    print(f"prices updated {updated}/{len(stocks)} · skipped {len(skipped)} · flagged {len(review)}")
    for line in skipped:
        print("  skip:", line)
    for line in review:
        print("  review (possible bad ticker or corporate action):", line)

    if updated < 0.7 * len(stocks):
        sys.exit(f"only {updated}/{len(stocks)} prices refreshed — "
                 f"aborting write to avoid a half-updated snapshot")

    new_blob = json.dumps(stocks, separators=(", ", ": "))
    text = text[:m.start(1)] + new_blob + text[m.end(1):]

    today = f"{datetime.date.today().day} {datetime.date.today():%B %Y}"
    text, n = re.subn(r'(id="priceAsOf">)[^<]*(</span>)', rf"\g<1>{today}\g<2>", text, count=1)
    if n == 0:
        sys.exit('id="priceAsOf" marker not found — aborting without writes')

    d = os.path.dirname(HTML_PATH)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)
    os.replace(tmp, HTML_PATH)
    print("wrote", HTML_PATH)


if __name__ == "__main__":
    main()
