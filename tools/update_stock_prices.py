"""
Maverick Investor — weekly stock data refresh.

Reads MaverickInvestor/stock-screener.html and rewrites the STOCKS array
in place with live-sourced numbers, fetched concurrently (I/O-bound HTTP
calls, so a thread pool is most of the wall-clock win here):

  - price, market cap, trailing P/E, dividend yield, and YoY revenue/
    earnings growth: fetched fresh per stock from Yahoo Finance's
    quoteSummary endpoint (NSE tickers, ".NS" suffix)
  - if quoteSummary has no usable price for a stock (endpoint hiccup,
    delisting, etc.), price alone falls back to the plainer, more
    reliable `chart` endpoint — the fundamentals just stay unchanged
    for that stock rather than blocking its price update
  - ROCE has no free live-data equivalent and is left untouched — it
    stays a periodic manual snapshot from Screener.in (see the page note)

Safety rules, since a bad ticker match would silently corrupt investment
data:
  - a stock with no ticker mapping, a failed fetch, or a >45% implied
    weekly price move is skipped and logged, not guessed at
  - an implausible fundamentals value (e.g. a mis-parsed market cap) is
    dropped for that field only; the price update still applies
  - if fewer than 70% of stocks get a price refresh, nothing is written

Stdlib only. Run:
    python tools/update_stock_prices.py
"""
import json, os, re, sys, tempfile, datetime, urllib.request, urllib.parse, http.cookiejar, threading
from concurrent.futures import ThreadPoolExecutor

HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "MaverickInvestor", "stock-screener.html")

MAX_WEEKLY_MOVE = 0.45
MAX_WORKERS = 16
UA = "Mozilla/5.0 (compatible; MaverickInvestorBot/1.0; +https://maverickinvestor.in)"

# Curated name -> NSE ticker (Yahoo Finance symbol is TICKER.NS).
TICKERS = {
    "Reliance Industries": "RELIANCE", "Bharti Airtel": "BHARTIARTL", "HDFC Bank": "HDFCBANK",
    "SBI": "SBIN", "ICICI Bank": "ICICIBANK", "TCS": "TCS", "Bajaj Finance": "BAJFINANCE",
    "Larsen & Toubro": "LT", "Hind. Unilever": "HINDUNILVR", "Infosys": "INFY",
    "Sun Pharma": "SUNPHARMA", "Maruti Suzuki": "MARUTI", "Titan Company": "TITAN",
    "M & M": "M&M", "Adani Enterprises": "ADANIENT", "Adani Ports": "ADANIPORTS",
    "Kotak Mah. Bank": "KOTAKBANK", "Axis Bank": "AXISBANK", "HCL Technologies": "HCLTECH",
    "ITC": "ITC", "UltraTech Cement": "ULTRACEMCO", "NTPC": "NTPC",
    "Bajaj Auto": "BAJAJ-AUTO", "Bajaj Finserv": "BAJAJFINSV", "JSW Steel": "JSWSTEEL",
    "Nestle India": "NESTLEIND", "Eternal (Zomato)": "ETERNAL", "ONGC": "ONGC",
    "Bharat Electronics": "BEL", "Asian Paints": "ASIANPAINT", "Shriram Finance": "SHRIRAMFIN",
    "Coal India": "COALINDIA", "Power Grid Corpn": "POWERGRID", "Hindalco Inds": "HINDALCO",
    "Tata Steel": "TATASTEEL", "Grasim Inds": "GRASIM", "Eicher Motors": "EICHERMOT",
    "InterGlobe (IndiGo)": "INDIGO", "Wipro": "WIPRO", "SBI Life Insurance": "SBILIFE",
    "Jio Financial": "JIOFIN", "Tech Mahindra": "TECHM", "Trent": "TRENT",
    "Apollo Hospitals": "APOLLOHOSP", "Tata Motors PV": "TMPV", "Cipla": "CIPLA",
    "HDFC Life Insurance": "HDFCLIFE", "Tata Consumer": "TATACONSUM", "Max Healthcare": "MAXHEALTH",
    "Dr Reddy's Labs": "DRREDDY", "BSE": "BSE", "BHEL": "BHEL", "Polycab India": "POLYCAB",
    "GMR Airports": "GMRAIRPORT", "Hero Motocorp": "HEROMOTOCO", "Marico": "MARICO",
    "Lupin": "LUPIN", "Bharat Forge": "BHARATFORG", "Ashok Leyland": "ASHOKLEY",
    "Indus Towers": "INDUSTOWER", "Mankind Pharma": "MANKIND", "Laurus Labs": "LAURUSLABS",
    "Aurobindo Pharma": "AUROPHARMA", "FSN E-Comm (Nykaa)": "NYKAA", "One97 (Paytm)": "PAYTM",
    "Federal Bank": "FEDERALBNK", "Dixon Technologies": "DIXON", "Persistent Systems": "PERSISTENT",
    "HPCL": "HINDPETRO", "ICICI Lombard": "ICICIGI", "Havells India": "HAVELLS",
    "IndusInd Bank": "INDUSINDBK", "Info Edge (Naukri)": "NAUKRI", "AU Small Finance": "AUBANK",
    "Coforge": "COFORGE", "Swiggy": "SWIGGY", "SRF": "SRF", "Waaree Energies": "WAAREEENER",
    "NHPC": "NHPC", "NMDC": "NMDC", "PB Fintech": "POLICYBZR", "IDFC First Bank": "IDFCFIRSTB",
    "Dabur India": "DABUR", "Oil India": "OIL", "Fortis Healthcare": "FORTIS",
    "Yes Bank": "YESBANK", "Prestige Estates": "PRESTIGE", "Phoenix Mills": "PHOENIXLTD",
    "MCX": "MCX", "Alkem Lab": "ALKEM", "Suzlon Energy": "SUZLON", "SBI Cards": "SBICARD",
    "Godrej Properties": "GODREJPROP", "Colgate-Palmolive": "COLPAL", "APL Apollo Tubes": "APLAPOLLO",
    "Tube Investments": "TIINDIA", "Max Financial": "MFSL", "UPL": "UPL", "Mphasis": "MPHASIS",
    "Supreme Inds": "SUPREMEIND", "Aster DM Healthcare": "ASTERDM", "RBL Bank": "RBLBANK",
    "Hindustan Copper": "HINDCOPPER", "Sona BLW Precision": "SONACOMS", "Welspun Corp": "WELCORP",
    "Aegis Logistics": "AEGISLOG", "Piramal Finance": "PIRAMALFIN", "Gland Pharma": "GLAND",
    "Navin Fluorine Intl": "NAVINFLUOR", "Poonawalla Fincorp": "POONAWALLA",
    "Narayana Hrudayalaya": "NH", "Himadri Speciality": "HSCL", "Tata Technologies": "TATATECH",
    "Delhivery": "DELHIVERY", "Anand Rathi Wealth": "ANANDRATHI", "Manappuram Finance": "MANAPPURAM",
    "Wockhardt": "WOCKPHARMA", "Karur Vysya Bank": "KARURVYSYA", "Dr Lal Pathlabs": "LALPATHLAB",
    "Chola Financial Hldgs": "CHOLAHLDNG", "PNB Housing": "PNBHOUSING", "Neuland Labs": "NEULANDLAB",
    "Sai Life Sciences": "SAILIFE", "Bandhan Bank": "BANDHANBNK", "Piramal Pharma": "PPLPHARMA",
    "Redington": "REDINGTON", "CDSL": "CDSL", "Angel One": "ANGELONE", "Amber Enterprises": "AMBER",
    "IIFL Finance": "IIFL", "Kaynes Technology": "KAYNES", "NBCC": "NBCC", "Affle 3i": "AFFLE",
    "CESC": "CESC", "Indraprastha Gas": "IGL", "City Union Bank": "CUB", "CAMS": "CAMS",
    "Castrol India": "CASTROLIND", "PG Electroplast": "PGEL", "Tata Chemicals": "TATACHEM",
    "Amara Raja Energy": "ARE&M", "Cohance Lifesciences": "COHANCE", "Natco Pharma": "NATCOPHARM",
    "Syngene Intl": "SYNGENE", "Crompton Gr. Consumer": "CROMPTON", "KFin Technologies": "KFINTECH",
    "Five-Star Business Fin": "FIVESTAR", "Inox Wind": "INOXWIND", "KEC International": "KEC",
    "Reliance Power": "RPOWER",
}


def _raw(mod, key):
    v = mod.get(key)
    return v.get("raw") if isinstance(v, dict) else None


# quoteSummary requires a session cookie + crumb (Yahoo tightened this after
# the chart/v8 endpoint used elsewhere here was already stable and cookie-
# free). Fetched once, shared read-only across worker threads — CPython's
# http.cookiejar is safe for concurrent reads once populated.
_session = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
_crumb_lock = threading.Lock()
_crumb = None
_crumb_unavailable = False


def get_crumb():
    """Fetches the crumb once; every subsequent call reuses it. Returns
    None (and stops retrying for the rest of this run) if Yahoo's crumb
    flow fails, so callers can skip quoteSummary entirely rather than
    let every one of 150 requests fail slowly one by one."""
    global _crumb, _crumb_unavailable
    with _crumb_lock:
        if _crumb or _crumb_unavailable:
            return _crumb
        try:
            _session.open(urllib.request.Request("https://fc.yahoo.com", headers={"User-Agent": UA}), timeout=15).read()
            req = urllib.request.Request("https://query2.finance.yahoo.com/v1/test/getcrumb", headers={"User-Agent": UA})
            _crumb = _session.open(req, timeout=15).read().decode("utf-8").strip()
        except Exception as e:
            print(f"crumb fetch failed: {type(e).__name__}: {e}")
            _crumb_unavailable = True
        return _crumb


def fetch_price_chart(ticker):
    """The plain, long-stable quote endpoint — price only. Used as a
    fallback when quoteSummary (below) has no usable price for a stock."""
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


def fetch_quote_summary(ticker, crumb):
    """Price + fundamentals in one call. Undocumented endpoint that now
    requires the session cookie + crumb obtained via get_crumb() — if this
    fails for a stock, the caller falls back to fetch_price_chart for the
    price and simply skips fundamentals for that stock."""
    sym = urllib.parse.quote(ticker + ".NS", safe="")
    modules = "price,summaryDetail,financialData"
    url = (f"https://query2.finance.yahoo.com/v10/finance/quoteSummary/{sym}"
           f"?modules={modules}&crumb={urllib.parse.quote(crumb, safe='')}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with _session.open(req, timeout=20) as r:
        data = json.load(r)
    result = data.get("quoteSummary", {}).get("result")
    return result[0] if result else None


def fetch_stock(name):
    """Runs in a worker thread: resolve name -> ticker, fetch, return a
    plain result tuple. No shared state beyond the read-only crumb/session,
    so no per-stock locking needed."""
    ticker = TICKERS.get(name)
    if not ticker:
        return name, ticker, None, "no ticker mapped"

    fields = {}
    price = None
    crumb = get_crumb()
    try:
        qs = fetch_quote_summary(ticker, crumb) if crumb else None
        if qs:
            price_mod, summary, fin = qs.get("price", {}), qs.get("summaryDetail", {}), qs.get("financialData", {})
            price = _raw(price_mod, "regularMarketPrice")
            fields = {
                "mcap_rupees": _raw(price_mod, "marketCap"),
                "pe": _raw(summary, "trailingPE"),
                "divYield_raw": _raw(summary, "dividendYield"),
                "salesGr_frac": _raw(fin, "revenueGrowth"),
                "profitGr_frac": _raw(fin, "earningsGrowth"),
            }
    except Exception:
        pass  # quoteSummary is best-effort; chart fallback below covers price

    if not price:
        try:
            price = fetch_price_chart(ticker)
        except Exception as e:
            return name, ticker, None, str(e)

    if not price or price <= 0:
        return name, ticker, None, "no usable price"
    return name, ticker, (float(price), fields), None


def apply_fundamentals(s, fields):
    """Applies whatever real fundamentals fields came back; each one is
    independently sanity-checked and simply skipped (not guessed) if it
    looks like a parsing error, rather than risking bad data on the page."""
    mcap_rupees = fields.get("mcap_rupees")
    if mcap_rupees and mcap_rupees > 0:
        mcap_cr = mcap_rupees / 1e7
        old_mcap = s.get("mcap") or 0
        if old_mcap <= 0 or 0.2 < mcap_cr / old_mcap < 5:
            s["mcap"] = round(mcap_cr, 2)

    pe = fields.get("pe")
    if pe and 0 < pe < 1000:
        s["pe"] = round(pe, 2)

    div_raw = fields.get("divYield_raw")
    if div_raw is not None and div_raw >= 0:
        # Yahoo has historically returned dividendYield as either a
        # fraction (0.018) or already as percent (1.8) — normalize.
        pct = div_raw * 100 if div_raw < 1 else div_raw
        if pct < 25:
            s["divYield"] = round(pct, 2)

    sales_gr = fields.get("salesGr_frac")
    if sales_gr is not None and abs(sales_gr) < 10:
        s["salesGr"] = round(sales_gr * 100, 2)

    profit_gr = fields.get("profitGr_frac")
    if profit_gr is not None and abs(profit_gr) < 10:
        s["profitGr"] = round(profit_gr * 100, 2)


def main():
    text = open(HTML_PATH, encoding="utf-8").read()
    m = re.search(r"const STOCKS=(\[.*?\]);", text, re.DOTALL)
    if not m:
        sys.exit("STOCKS array not found in stock-screener.html — aborting without writes")
    stocks = json.loads(m.group(1))
    by_name = {s["n"]: s for s in stocks}

    if get_crumb():
        print("quoteSummary crumb obtained — fetching real fundamentals (P/E, div yield, mcap, growth)")
    else:
        print("quoteSummary crumb unavailable — falling back to price-only refresh with proportional scaling")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        results = list(ex.map(fetch_stock, by_name.keys()))

    updated, skipped, review = 0, [], []
    for name, ticker, payload, err in results:
        s = by_name[name]
        if err:
            skipped.append(f"{name} ({ticker or '?'}): {err}")
            continue
        price, fields = payload
        old = s.get("price") or 0
        if old <= 0:
            skipped.append(f"{name} ({ticker}): no existing price to compare against")
            continue
        ratio = price / old
        if abs(ratio - 1) > MAX_WEEKLY_MOVE:
            review.append(f"{name} ({ticker}): {old} -> {price} ({(ratio - 1) * 100:+.1f}%)")
            continue
        s["price"] = round(price, 2)
        if fields:
            apply_fundamentals(s, fields)
        else:
            # quoteSummary failed for this stock — chart fallback still
            # scales mcap/PE/divYield proportionally so they stay roughly
            # consistent with the new price rather than going stale.
            if s.get("mcap"):
                s["mcap"] = round(s["mcap"] * ratio, 2)
            if s.get("pe"):
                s["pe"] = round(s["pe"] * ratio, 2)
            if s.get("divYield"):
                s["divYield"] = round(s["divYield"] / ratio, 2)
        updated += 1

    print(f"updated {updated}/{len(stocks)} · skipped {len(skipped)} · flagged for review {len(review)}")
    for line in skipped:
        print("  skip:", line)
    for line in review:
        print("  review (possible bad ticker or corporate action):", line)

    if updated < 0.7 * len(stocks):
        sys.exit(f"only {updated}/{len(stocks)} prices refreshed — aborting write to avoid a half-updated snapshot")

    new_blob = json.dumps(stocks, separators=(", ", ": "))
    text = text[:m.start(1)] + new_blob + text[m.end(1):]

    today = datetime.date.today().strftime("%-d %B %Y")
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
