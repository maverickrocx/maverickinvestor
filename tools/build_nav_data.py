"""
Maverick Investor — daily NAV files for the browser.

mfapi.in stopped sending CORS headers in October 2026, so pages can no longer
fetch NAVs from it in the reader's browser. This job fetches them server-side
and writes same-origin files the pages read instead:

  data/navs.json              latest NAV, 1-day, 1-year and 3-year return for
                              every fund on the home page and in the MF Advisor
  data/nav-history/<code>.json
                              first NAV of each month plus the latest NAV, in
                              mfapi's own shape ({"data": [{date, nav}, ...]},
                              newest first), for the MF Advisor's SIP backtest

The latest NAV comes from AMFI's official daily file (NAVAll.txt) when it is
newer than or equal to mfapi's; mfapi supplies the history behind the returns.

Safety: a fund whose fetch fails keeps yesterday's entry; if fewer than 90% of
funds refresh, nothing is written at all.

Stdlib only. Run:
    python tools/build_nav_data.py
"""
import datetime
import json
import os
import re
import sys
import tempfile
import urllib.request

import rank_funds

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "MaverickInvestor")
DATA = os.path.join(SITE, "data")
NAVS = os.path.join(DATA, "navs.json")
HIST = os.path.join(DATA, "nav-history")
AMFI_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"
MIN_COVERAGE = 0.90


def scheme_codes():
    """Every scheme code a page shows or backtests: the home tracker's
    FUND_CONFIG, the MF Advisor's bundled FUND_DB, and the ranking pool."""
    codes = set()
    home = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    codes |= {int(c) for c in re.findall(r"schemeCode:(\d+)", home)}
    adv = open(os.path.join(SITE, "mf-advisor.html"), encoding="utf-8").read()
    codes |= {int(c) for c in re.findall(r"\['[^']+',\s*(\d+),", adv)}
    cand = json.load(open(os.path.join(DATA, "candidates.json")))
    for cat in cand["categories"].values():
        codes |= {f["schemeCode"] for f in cat["funds"]}
        if cat.get("benchmarkSchemeCode"):
            codes.add(cat["benchmarkSchemeCode"])
    return sorted(codes)


def amfi_latest():
    """{code: (date, nav)} from AMFI's official daily file; {} if unreachable."""
    try:
        req = urllib.request.Request(AMFI_URL, headers={"User-Agent": "MaverickInvestorBot/1.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            text = r.read().decode("utf-8", "replace")
    except Exception as e:
        print(f"AMFI NAVAll.txt unavailable ({type(e).__name__}); using mfapi.in only")
        return {}
    out = {}
    for line in text.splitlines():
        parts = line.split(";")
        if len(parts) < 6 or not parts[0].strip().isdigit():
            continue
        try:
            d = datetime.datetime.strptime(parts[-1].strip(), "%d-%b-%Y").date()
            out[int(parts[0])] = (d, float(parts[-2]))
        except ValueError:
            continue
    return out


def _back(series, days):
    """Value on the last NAV date at or before `days` before the latest."""
    target = series[-1][0] - datetime.timedelta(days=days)
    prior = [v for d, v in series if d <= target]
    return prior[-1] if prior else None


def summarise(series, amfi):
    if amfi and amfi[0] >= series[-1][0]:
        if amfi[0] > series[-1][0]:
            series = series + [amfi]
        else:
            series = series[:-1] + [amfi]
        source = "AMFI"
    else:
        source = "mfapi.in"
    cur_d, cur = series[-1]
    prev = series[-2][1] if len(series) > 1 else None
    y1, y3 = _back(series, 365), _back(series, 3 * 365)
    pct = lambda a, b: round((a / b - 1) * 100, 2) if a and b else None
    rec = {
        "nav": round(cur, 4),
        "date": cur_d.isoformat(),
        "d1": pct(cur, prev),
        "y1": pct(cur, y1),
        "y3": round(((cur / y3) ** (1 / 3) - 1) * 100, 2) if y3 else None,
        "source": source,
    }
    return rec, series


def monthly_history(series):
    firsts, seen = [], set()
    for d, v in series:
        if (d.year, d.month) not in seen:
            seen.add((d.year, d.month))
            firsts.append((d, v))
    rows = firsts[::-1]
    if series[-1] != firsts[-1]:
        rows = [series[-1]] + rows
    return {"data": [{"date": d.strftime("%d-%m-%Y"), "nav": f"{v:.4f}"} for d, v in rows]}


def _write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    codes = scheme_codes()
    amfi = amfi_latest()
    series = rank_funds.fetch_all_series(codes)
    # mfapi.in drops some requests under parallel load; one slow sequential
    # pass recovers nearly all of them.
    for c in [c for c in codes if not series.get(c)]:
        series[c] = rank_funds.navseries(c)[0]
    try:
        prev = json.load(open(NAVS)).get("funds", {})
    except Exception:
        prev = {}

    funds, hist, missing = {}, {}, []
    for c in codes:
        s = series.get(c)
        if not s or len(s) < 2:
            missing.append(c)
            if str(c) in prev:
                funds[str(c)] = prev[str(c)]
            continue
        funds[str(c)], full = summarise(s, amfi.get(c))
        hist[c] = monthly_history(full)

    coverage = 1 - len(missing) / len(codes)
    if missing:
        print(f"no fresh NAVs for {missing}; kept yesterday's entries where there were any")
    if coverage < MIN_COVERAGE:
        sys.exit(f"only {coverage:.0%} of funds refreshed (floor {MIN_COVERAGE:.0%}) — nothing written")

    os.makedirs(HIST, exist_ok=True)
    for c, h in hist.items():
        _write_json(os.path.join(HIST, f"{c}.json"), h)
    latest = max(f["date"] for f in funds.values())
    _write_json(NAVS, {"asOf": latest, "generated": datetime.date.today().isoformat(),
                       "funds": funds})
    amfi_n = sum(1 for f in funds.values() if f.get("source") == "AMFI")
    print(f"wrote navs.json ({len(funds)} funds, {amfi_n} with AMFI's official NAV, as of {latest}) "
          f"and {len(hist)} history files")


if __name__ == "__main__":
    main()
