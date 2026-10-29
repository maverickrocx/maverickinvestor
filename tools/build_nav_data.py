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
                              and the Tools page's duplicate-fund check
  data/fund-list.json         name and group of every fund above, for pickers
  data/crash-replay.json      every Nifty 50 fall of 10%+ since 2013, and how
                              each fund fared through it (Tools page)

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


CAT_GROUPS = {"largeCap": "Large Cap", "flexiCap": "Flexi Cap", "midCap": "Mid Cap",
              "smallCap": "Small Cap", "gold": "Gold", "debt": "Debt"}
NIFTY50 = 120716          # UTI Nifty 50 Index Fund (Direct): defines "market falls"
CRASH_DEPTH = -0.10
# Familiar names for the Nifty 50 peaks that started a 10%+ fall.
CRASH_NAMES = {"2015-03": "2015–16 slowdown", "2018-08": "2018 IL&FS sell-off",
               "2020-01": "COVID-19 crash", "2021-10": "2022 rate-hike sell-off",
               "2024-09": "2024–25 correction"}


def fund_catalogue():
    """{code: {"name", "group"}} for every scheme a page shows, backtests or
    ranks: the home tracker's FUND_CONFIG, the MF Advisor's FUND_DB, and the
    ranking pool with its index benchmarks. The ranking pool's labels win."""
    funds = {}
    adv = open(os.path.join(SITE, "mf-advisor.html"), encoding="utf-8").read()
    for name, code in re.findall(r"\['([^']+)',\s*(\d+),", adv):
        funds[int(code)] = {"name": name, "group": None}
    home = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    for name, group, code in re.findall(
            r"name:'([^']+)',\s*group:'([^']+)',.*?schemeCode:(\d+)", home):
        funds[int(code)] = {"name": name.strip(), "group": group}
    cand = json.load(open(os.path.join(DATA, "candidates.json")))
    for key, cat in cand["categories"].items():
        for f in cat["funds"]:
            funds[f["schemeCode"]] = {"name": f["label"], "group": CAT_GROUPS.get(key, key)}
        if cat.get("benchmarkSchemeCode") and cat["benchmarkSchemeCode"] not in funds:
            funds[cat["benchmarkSchemeCode"]] = {"name": f'{cat["benchmarkName"]} index fund',
                                                 "group": "Index"}
    for f in funds.values():
        f["group"] = f["group"] or "Other"
    return funds


def scheme_codes():
    return sorted(fund_catalogue())


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


def market_falls(nifty):
    """Peak-to-recovery episodes in which the Nifty 50 fund fell 10%+."""
    out, peak_d, peak_v, low_d, low_v = [], None, 0, None, None
    for d, v in nifty:
        if v >= peak_v:
            if low_v is not None and low_v / peak_v - 1 <= CRASH_DEPTH:
                out.append({"peak": peak_d, "low": low_d, "recovered": d,
                            "depth": low_v / peak_v - 1})
            peak_d, peak_v, low_d, low_v = d, v, None, None
        elif low_v is None or v < low_v:
            low_d, low_v = d, v
    if low_v is not None and low_v / peak_v - 1 <= CRASH_DEPTH:
        out.append({"peak": peak_d, "low": low_d, "recovered": None, "depth": low_v / peak_v - 1})
    return out


def replay(series, fall, today):
    """₹100 invested at the fall's Nifty peak: the fund's lowest point during
    the fall, when it got back to ₹100, and a weekly path for a sparkline."""
    start = [v for d, v in series if d <= fall["peak"]]
    if not start or series[0][0] > fall["peak"] - datetime.timedelta(days=7):
        return None
    base = start[-1]
    end = fall["recovered"] or today
    during = [(d, v) for d, v in series if fall["peak"] <= d <= end]
    low_d, low_v = min(during, key=lambda t: t[1])
    back = next((d for d, v in series if d > low_d and v >= base), None)
    path_end = max(end, back or today) + datetime.timedelta(days=60)
    path, last_week = [], None
    for d, v in series:
        if fall["peak"] <= d <= path_end and (last_week is None or (d - last_week).days >= 7):
            path.append(round(v / base * 100, 1))
            last_week = d
    return {"low": round(low_v / base * 100, 1), "lowDate": low_d.isoformat(),
            "back": back.isoformat() if back else None,
            "months": round((back - fall["peak"]).days / 30.44, 1) if back else None,
            "today": round(series[-1][1] / base * 100, 1), "path": path}


def _write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(obj, fh, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    catalogue = fund_catalogue()
    codes = sorted(catalogue)
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
    _write_json(os.path.join(DATA, "fund-list.json"),
                {str(c): catalogue[c] for c in codes if c in hist})

    full = {}
    for c in codes:
        if series.get(c) and len(series[c]) > 1:
            full[c] = summarise(series[c], amfi.get(c))[1]
    if NIFTY50 in full:
        today = datetime.date.fromisoformat(latest)
        falls = market_falls(full[NIFTY50])
        crashes = []
        for fall in falls:
            key = fall["peak"].strftime("%Y-%m")
            funds_out = {str(c): r for c, s in full.items() if (r := replay(s, fall, today))}
            crashes.append({
                "name": CRASH_NAMES.get(key, "Fall from the " + fall["peak"].strftime("%b %Y") + " peak"),
                "peak": fall["peak"].isoformat(), "low": fall["low"].isoformat(),
                "recovered": fall["recovered"].isoformat() if fall["recovered"] else None,
                "depth": round(fall["depth"] * 100, 1), "funds": funds_out})
        _write_json(os.path.join(DATA, "crash-replay.json"),
                    {"asOf": latest, "market": str(NIFTY50), "crashes": crashes})
        print(f"wrote crash-replay.json ({len(crashes)} market falls since 2013)")
    amfi_n = sum(1 for f in funds.values() if f.get("source") == "AMFI")
    print(f"wrote navs.json ({len(funds)} funds, {amfi_n} with AMFI's official NAV, as of {latest}) "
          f"and {len(hist)} history files")


if __name__ == "__main__":
    main()
