"""
Maverick Investor — weekly stock price refresh.

Reads MaverickInvestor/stock-screener.html, fetches each stock's latest
closing price from Yahoo Finance's public quote endpoint (NSE tickers,
".NS" suffix), and rewrites the STOCKS array in place: price, and mcap/pe/
divYield scaled by the same ratio the price moved. ROCE and profit/sales
growth are fundamentals from Screener.in and are left untouched here —
those still need a manual refresh (see the "Fundamentals sourced from
Screener.in" note on the page).

Safety rules, since a bad ticker match would silently corrupt investment
data:
  - a stock with no ticker mapping, a failed fetch, or a >45% implied
    weekly move is skipped and logged, not guessed at
  - if fewer than 70% of stocks refresh successfully, nothing is written

Stdlib only. Run:
    python tools/update_stock_prices.py
"""
import json, os, re, sys, tempfile, datetime, urllib.request, urllib.parse

HTML_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "MaverickInvestor", "stock-screener.html")

MAX_WEEKLY_MOVE = 0.45
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
    "Apollo Hospitals": "APOLLOHOSP", "Tata Motors PV": "TATAMOTORS", "Cipla": "CIPLA",
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
    "Aegis Logistics": "AEGISLOG", "Piramal Finance": "PEL", "Gland Pharma": "GLAND",
    "Navin Fluorine Intl": "NAVINFLUOR", "Poonawalla Fincorp": "POONAWALLA",
    "Narayana Hrudayalaya": "NH", "Himadri Speciality": "HIMADRI", "Tata Technologies": "TATATECH",
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


def main():
    text = open(HTML_PATH, encoding="utf-8").read()
    m = re.search(r"const STOCKS=(\[.*?\]);", text, re.DOTALL)
    if not m:
        sys.exit("STOCKS array not found in stock-screener.html — aborting without writes")
    stocks = json.loads(m.group(1))

    updated, skipped, review = 0, [], []
    for s in stocks:
        ticker = TICKERS.get(s["n"])
        if not ticker:
            skipped.append(f"{s['n']} (no ticker mapped)")
            continue
        try:
            price = fetch_price(ticker)
        except Exception as e:
            skipped.append(f"{s['n']} ({ticker}): {e}")
            continue
        old = s.get("price") or 0
        if not price or price <= 0 or old <= 0:
            skipped.append(f"{s['n']} ({ticker}): no usable price")
            continue
        ratio = price / old
        if abs(ratio - 1) > MAX_WEEKLY_MOVE:
            review.append(f"{s['n']} ({ticker}): {old} -> {price} ({(ratio - 1) * 100:+.1f}%)")
            continue
        s["price"] = round(price, 2)
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
