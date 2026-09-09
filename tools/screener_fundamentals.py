"""
Maverick Investor — Screener.in fundamentals fetcher.

Supplies the six per-stock fundamentals the screener page shows but Yahoo
will no longer serve: P/E, market cap, dividend yield, ROCE, and TTM sales
and profit growth.

Why Screener.in: it is the source the page already credits, and its
robots.txt permits exactly this path. As of 2026-09-09 it disallows only
/user/*, query-parameter URLs (?q=, ?sort=, ?limit=, ?page=) and
/company/source/quarter/* — /company/<SYMBOL>/consolidated/ is allowed.
We crawl sequentially with real spacing and an identifying UA, and only
once a month — these figures only change when a company reports. Screener
tarpitted a faster first attempt (see update_fundamentals.py), which is a
clear enough signal about what they will tolerate. The response to that is
to ask for less, never to spread the load across UAs or addresses until it
stops being noticed.

Why not Yahoo quoteSummary: it returns 401 without a session crumb, and
the crumb handshake is itself rejected. Verified 2026-09-09 from a
residential connection, so this is not the CI-IP problem an earlier
revision of update_stock_prices.py assumed — it is simply closed.

Stdlib only.
"""
import html
import re
import threading
import time
import urllib.parse
import urllib.request

UA = "Mozilla/5.0 (compatible; MaverickInvestorBot/1.0; +https://maverickinvestor.in)"
BASE = "https://www.screener.in/company/{sym}/consolidated/"
TIMEOUT = 25

# Deliberate spacing between requests, enforced across any callers.
# Learned the hard way on 2026-09-09: a 150-page burst at 4 workers with 0.4s
# spacing got this IP tarpitted to a flat 21.2s per request, robots.txt
# included. Callers should fetch sequentially at this spacing, not in a pool.
REQUEST_SPACING = 5.0
_throttle = threading.Lock()
_last_request = [0.0]


def _polite_wait():
    with _throttle:
        gap = time.monotonic() - _last_request[0]
        if gap < REQUEST_SPACING:
            time.sleep(REQUEST_SPACING - gap)
        _last_request[0] = time.monotonic()


def _fetch(sym):
    """A company page. `sym` is an NSE ticker; & and friends need encoding
    (M&M is a real symbol) or the URL silently truncates."""
    url = BASE.format(sym=urllib.parse.quote(sym, safe=""))
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.9",
    })
    _polite_wait()
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8", "replace")


def _num(raw):
    """Screener renders Indian-format numbers ('17,52,328'). Commas are
    grouping only, never decimal, so stripping them is safe."""
    try:
        return float(raw.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def parse_ratios(text):
    """The top-of-page ratio list: Market Cap, Current Price, Stock P/E,
    ROCE, Dividend Yield and friends, as name/number span pairs."""
    out = {}
    for m in re.finditer(r'<li[^>]*class="flex flex-space-between"[^>]*>([\s\S]{0,400}?)</li>', text):
        block = m.group(1)
        name = re.search(r'<span class="name">\s*([^<]+?)\s*</span>', block)
        number = re.search(r'<span class="number">\s*([-\d,.]+)\s*</span>', block)
        if name and number:
            out[html.unescape(name.group(1)).strip()] = _num(number.group(1))
    return out


def parse_growth(text, heading):
    """One 'Compounded X Growth' table -> its TTM row.

    The table lists 10 Years / 5 Years / 3 Years / TTM. We want TTM
    specifically, matched by label rather than by position — a company
    young enough to lack a 10-year row would otherwise shift the offsets
    and hand back the wrong period entirely.
    """
    table = re.search(
        r'<table class="ranges-table">\s*<tr>\s*<th[^>]*>\s*' + re.escape(heading) + r'\s*</th>[\s\S]*?</table>',
        text,
    )
    if not table:
        return None
    row = re.search(r'<td>\s*TTM:\s*</td>\s*<td>\s*([-\d,.]+)\s*%?\s*</td>', table.group(0))
    return _num(row.group(1)) if row else None


def fetch(sym):
    """All six fundamentals for one NSE symbol, plus Screener's own price
    so the caller can cross-check the ticker actually resolved to the
    company it expected.

    Returns (fields_dict, None) or (None, error_string). Missing individual
    fields come back as None rather than raising — a page that omits ROCE
    should still yield its P/E.
    """
    try:
        text = _fetch(sym)
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:120]}"

    ratios = parse_ratios(text)
    if not ratios:
        return None, "no ratio block found (page layout changed?)"

    return {
        "price": ratios.get("Current Price"),
        "pe": ratios.get("Stock P/E"),
        "mcap": ratios.get("Market Cap"),
        "divYield": ratios.get("Dividend Yield"),
        "roce": ratios.get("ROCE"),
        "salesGr": parse_growth(text, "Compounded Sales Growth"),
        "profitGr": parse_growth(text, "Compounded Profit Growth"),
    }, None
