"""
Maverick Investor — dynamic MF fund ranking job.

Reads MaverickInvestor/data/candidates.json, fetches live NAV + benchmark data
from mfapi.in, computes Tier-A metrics, ranks each category by a weighted-
percentile composite, and writes MaverickInvestor/data/fund-rankings.json.

Stdlib only. Run:
    python -c "import rank_funds; rank_funds.write_rankings(CAND, OUT)"
"""
import json, os, sys, time, tempfile, urllib.request, datetime, statistics, math
from concurrent.futures import ThreadPoolExecutor

RF = 0.065  # risk-free assumption for Sharpe/Sortino

# ── Weight profiles (percentiles sum to 100) ──────────────────────────────
WEIGHTS = {
    "activeEquity": {'return_blend':0.20,'consistency':0.10,'sortino':0.12,'sharpe':0.08,
                     'ir':0.10,'maxdd':0.08,'dncap':0.07,'upcap':0.05,'ter':0.10,'aum_band':0.10},
    "debt":         {'return_blend':0.25,'consistency':0.10,'sortino':0.18,'sharpe':0.12,
                     'maxdd':0.15,'ter':0.10,'aum_band':0.10},
    "tracker":      {'return_blend':0.15,'consistency':0.10,'sortino':0.10,'maxdd':0.15,
                     'ter':0.40,'aum_band':0.10},
}
LOWER_BETTER = {'consistency','vol','dncap','ter'}


def _get(url, attempts=3):
    # mfapi.in drops the odd request under parallel load; retry with backoff
    # rather than let one blip silently remove a fund from the rankings.
    for i in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=25) as r:
                return json.load(r)
        except Exception:
            if i == attempts - 1:
                raise
            time.sleep(2 * (i + 1))


def despike(series):
    """Fix single corrupt NAV points: a >15% jump that reverts >15% next day."""
    for i in range(1, len(series) - 1):
        p, c, n = series[i-1][1], series[i][1], series[i+1][1]
        if p > 0 and c > 0 and abs(c/p - 1) > 0.15 and abs(n/c - 1) > 0.15 and (c/p - 1)*(n/c - 1) < 0:
            series[i] = (series[i][0], (p + n) / 2)
    return series


def navseries(code):
    if not code:
        return [], ""
    try:
        d = _get(f"https://api.mfapi.in/mf/{code}")
    except Exception:
        return [], ""
    out = []
    for row in d.get("data", []):
        try:
            dd, mm, yy = row["date"].split("-")
            v = float(row["nav"])
            if v > 0:
                out.append((datetime.date(int(yy), int(mm), int(dd)), v))
        except Exception:
            pass
    out.sort()
    return despike(out), d.get("meta", {}).get("scheme_name", "")


def cagr(series, years):
    if not series:
        return None
    end_d, end_v = series[-1]
    target = end_d.replace(year=end_d.year - years)
    prior = [(d, v) for d, v in series if d <= target]
    if not prior:
        return None
    start_v = prior[-1][1]
    return (end_v / start_v) ** (1 / years) - 1 if start_v > 0 else None


def _daily(series):
    return [series[i][1]/series[i-1][1] - 1 for i in range(1, len(series)) if series[i-1][1] > 0]


def _monthly(series):
    m = {}
    for d, v in series:
        m[(d.year, d.month)] = v
    vals = [m[k] for k in sorted(m)]
    return [vals[i]/vals[i-1] - 1 for i in range(1, len(vals)) if vals[i-1] > 0]


def _maxdd(series):
    peak, mdd = -1, 0
    for _, v in series:
        peak = max(peak, v)
        if peak > 0:
            mdd = min(mdd, v/peak - 1)
    return mdd


def _month_ends(series):
    m = {}
    for d, v in series:
        m[(d.year, d.month)] = v
    return m


def _rolling5(series, other=None, hurdle=None):
    """Share of rolling 5-year windows (month-end to month-end) in which the
    fund's CAGR beat `other`'s CAGR over the same window, or a fixed `hurdle`
    rate. Returns (share, window count, first window's start year); share is
    None under 12 windows."""
    fm = _month_ends(series)
    om = _month_ends(other) if other else None
    wins = n = 0
    first = None
    for k in sorted(fm):
        start = (k[0] - 5, k[1])
        if start not in fm or fm[start] <= 0:
            continue
        if om is not None and (start not in om or k not in om or om[start] <= 0):
            continue
        fc = (fm[k] / fm[start]) ** 0.2 - 1
        bar = (om[k] / om[start]) ** 0.2 - 1 if om is not None else hurdle
        n += 1
        first = first or start[0]
        wins += fc > bar
    return (wins / n if n >= 12 else None), n, first


def metrics(series, bench=None, ter=None, aum=None, ppf=None):
    dr = _daily(series)
    if len(dr) < 200:
        return None
    mean_d, sd_d = statistics.mean(dr), statistics.pstdev(dr)
    vol = sd_d * math.sqrt(252)
    ann = mean_d * 252
    rf_d = RF / 252
    downs = [min(x - rf_d, 0) for x in dr]
    dd = math.sqrt(sum(x*x for x in downs)/len(downs)) * math.sqrt(252)
    m = dict(cagr3=cagr(series, 3), cagr5=cagr(series, 5), cagr7=cagr(series, 7),
             vol=vol, sharpe=(ann - RF)/vol if vol > 0 else None,
             sortino=(ann - RF)/dd if dd > 0 else None, maxdd=_maxdd(series),
             ter=ter, aum=aum)
    # 1-yr rolling consistency (std over last 5y)
    mvals = {}
    for d, v in series:
        mvals[(d.year, d.month)] = v
    seq = [mvals[k] for k in sorted(mvals)]
    roll = [seq[i]/seq[i-12] - 1 for i in range(12, len(seq)) if seq[i-12] > 0][-60:]
    m['consistency'] = statistics.pstdev(roll) if len(roll) >= 12 else None
    m['beatPPF5'], m['windows5'], m['since5'] = _rolling5(series, hurdle=ppf) if ppf else (None, 0, None)
    m['beatBench5'], m['windowsBench5'], m['sinceBench5'] = _rolling5(series, bench) if bench else (None, 0, None)
    if bench:
        fm, bm = _monthly(series), _monthly(bench)
        n = min(len(fm), len(bm))
        fm, bm = fm[-n:], bm[-n:]
        if n >= 24:
            var_b = statistics.pvariance(bm)
            cov = sum((fm[i]-statistics.mean(fm))*(bm[i]-statistics.mean(bm)) for i in range(n))/n
            beta = cov/var_b if var_b > 0 else None
            annf, annb = statistics.mean(fm)*12, statistics.mean(bm)*12
            m['alpha'] = (annf - RF) - (beta*(annb - RF) if beta else 0)
            m['beta'] = beta
            m['benchMonths'] = n
            ub = sum(bm[i] for i in range(n) if bm[i] > 0)
            db = sum(bm[i] for i in range(n) if bm[i] < 0)
            m['upcap'] = (sum(fm[i] for i in range(n) if bm[i] > 0)/ub*100) if ub else None
            m['dncap'] = (sum(fm[i] for i in range(n) if bm[i] < 0)/db*100) if db else None
            te = statistics.pstdev([fm[i]-bm[i] for i in range(n)]) * math.sqrt(12)
            m['ir'] = (annf - annb)/te if te > 0.01 else None
    return m


def _val(f, k):
    if k == 'return_blend':
        xs = [f['metrics'].get('cagr3'), f['metrics'].get('cagr5'), f['metrics'].get('cagr7')]
        xs = [x for x in xs if x is not None]
        return statistics.mean(xs) if xs else None
    if k == 'aum_band':
        return _aum_band(f['_catkey'], f['metrics'].get('aum') or 0)
    return f['metrics'].get(k)


def _aum_band(catkey, aum):
    if catkey == 'smallCap':
        peak, cap = 15000, 30000
    elif catkey == 'midCap':
        peak, cap = 20000, 45000
    else:
        return aum
    return aum/peak if aum <= peak else max(0.2, 1 - (aum - peak)/(cap - peak)*0.8)


def _pct(values, higher_better=True):
    present = [v for v in values if v is not None]
    med = statistics.median(present) if present else 0
    f = [v if v is not None else med for v in values]
    n = len(f)
    out = []
    for v in f:
        if higher_better:
            worse = sum(1 for u in f if u < v); eq = sum(1 for u in f if u == v)
        else:
            worse = sum(1 for u in f if u > v); eq = sum(1 for u in f if u == v)
        out.append((worse + (eq - 1)/2)/(n - 1)*100 if n > 1 else 50)
    return out


def composite(funds, profile):
    W = WEIGHTS[profile]
    pcts = {k: _pct([_val(f, k) for f in funds], higher_better=(k not in LOWER_BETTER)) for k in W}
    for i, f in enumerate(funds):
        f['composite'] = round(sum(W[k]*pcts[k][i] for k in W), 1)
    return sorted(funds, key=lambda f: -f['composite'])


def funds_used(weight):
    return 2 if weight > 20 else 1


def _corr(a, b):
    n = min(len(a), len(b))
    a, b = a[-n:], b[-n:]
    if n < 12:
        return 0
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((a[i]-ma)*(b[i]-mb) for i in range(n))
    den = math.sqrt(sum((x-ma)**2 for x in a)*sum((x-mb)**2 for x in b))
    return num/den if den else 0


def fetch_all_series(codes, max_workers=12):
    """Fetch NAV series for every scheme code concurrently — these are
    independent I/O-bound HTTP calls, so a thread pool cuts wall-clock time
    roughly max_workers-fold versus fetching one at a time."""
    codes = sorted(set(c for c in codes if c))
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        results = list(ex.map(navseries, codes))
    return {code: series for code, (series, _name) in zip(codes, results)}


def _pctx(x):
    return f"{round(x * 100)}%"


def verdict(m, cat, ppf, peer_ter):
    """Plain-English read of a fund's numbers: what it does well ('plus') and
    what to be ready for ('watch'). Education, not a recommendation."""
    plus, watch = [], []
    bench = cat.get('benchmarkName')
    b5 = m.get('beatBench5')
    if b5 is not None and bench:
        if b5 >= 0.6:
            plus.append(f"Beat the {bench} in {_pctx(b5)} of 5-year periods since {m['sinceBench5']}.")
        elif b5 <= 0.4:
            watch.append(f"Trailed the {bench} in {_pctx(1 - b5)} of 5-year periods since {m['sinceBench5']}.")
    dn = m.get('dncap')
    if dn is not None and bench and (m.get('benchMonths') or 0) >= 36:
        if dn <= 95:
            plus.append(f"In the market's bad months it fell about {round(100 - dn)}% less than the {bench}.")
        elif dn >= 105:
            watch.append(f"In the market's bad months it fell about {round(dn - 100)}% more than the {bench}.")
    p5 = m.get('beatPPF5')
    if p5 is not None and ppf is not None:
        line = f"Beat today's PPF rate ({ppf * 100:.1f}%) in {_pctx(p5)} of 5-year periods since {m['since5']}."
        if cat.get('profile') != 'activeEquity':
            line += " PPF is tax-free, so the real gap is smaller."
        (plus if p5 >= 0.6 else watch).append(line)
    ter = m.get('ter')
    if ter is not None and peer_ter is not None:
        if ter < peer_ter:
            plus.append(f"Cheaper than most funds on our list for its category ({ter:.2f}% a year).")
        elif ter > peer_ter:
            watch.append(f"Costs more than most funds on our list for its category ({ter:.2f}% a year).")
    mdd = m.get('maxdd')
    if mdd is not None:
        if mdd > -0.10:
            plus.append(f"A steady ride: its worst fall from a peak was only {round(-mdd * 100)}%.")
        else:
            watch.append(f"Its worst fall from a peak was {round(-mdd * 100)}%. Be ready to sit through drops like that.")
    return {"plus": plus[:3], "watch": watch[:2]}


def rank_category(cat, bench_series, series_cache, ppf=None):
    prof = cat['profile']
    bench = bench_series if prof == 'activeEquity' else None
    eligible = []
    for fd in cat['funds']:
        s = series_cache.get(fd['schemeCode'], [])
        yrs = round((s[-1][0]-s[0][0]).days/365, 1) if s else 0
        min_yrs = 3 if fd.get('isIndex') else 5
        if yrs < min_yrs:
            continue
        mt = metrics(s, bench, fd.get('ter'), fd.get('aum'), ppf)
        if not mt:
            continue
        eligible.append({'label': fd['label'], 'schemeCode': fd['schemeCode'],
                         '_catkey': None, 'metrics': mt, '_monthly': _monthly(s)})
    return eligible


# ── Picks by period (home page "Our picks by period") ─────────────────────
# Today's ranking over the last 1, 3 or 5 years on five measures. Separate
# from the composite above, which blends 3/5/7-year history and more metrics.
PERIOD_WEIGHTS = {'xirr': 0.30, 'vsBench': 0.25, 'sharpe': 0.20, 'ter': 0.15, 'beta': 0.10}
PERIOD_LOWER_BETTER = {'ter', 'beta'}


def _xirr(flows):
    """flows: [(date, amount)], investments negative, final value positive."""
    t0 = flows[0][0]
    def npv(r):
        return sum(a / (1 + r) ** ((d - t0).days / 365.0) for d, a in flows)
    lo, hi = -0.99, 5.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def _sip_xirr(window):
    flows, units, seen = [], 0.0, set()
    for d, v in window:
        if (d.year, d.month) not in seen:
            seen.add((d.year, d.month))
            flows.append((d, -1000.0))
            units += 1000.0 / v
    end_d, end_v = window[-1]
    if len(flows) < 6:
        return None
    flows.append((end_d, units * end_v))
    return _xirr(flows)


def _weekly(window):
    w = {}
    for d, v in window:
        w[d.isocalendar()[:2]] = v
    return w


def _wk_returns(wk, keys):
    return [wk[keys[i]] / wk[keys[i - 1]] - 1 for i in range(1, len(keys))]


def _beta(fw, yw):
    keys = sorted(k for k in fw if k in yw)
    if len(keys) < 26:
        return None
    f, y = _wk_returns(fw, keys), _wk_returns(yw, keys)
    my, mf = statistics.mean(y), statistics.mean(f)
    var = sum((b - my) ** 2 for b in y)
    return sum((a - mf) * (b - my) for a, b in zip(f, y)) / var if var else None


def period_picks(cfg, series_cache, years):
    today_end = max(s[-1][0] for s in series_cache.values() if s)
    start = today_end.replace(year=today_end.year - years)
    def window(code):
        s = series_cache.get(code) or []
        if not s or s[0][0] > start + datetime.timedelta(days=10):
            return None
        return [(d, v) for d, v in s if d >= start]
    out = {}
    for catkey, cat in cfg["categories"].items():
        funds = []
        for fd in cat["funds"]:
            w = window(fd["schemeCode"])
            if not w or len(w) < 120:
                continue
            yrs = (w[-1][0] - w[0][0]).days / 365.0
            dr = _daily(w)
            vol = statistics.pstdev(dr) * math.sqrt(252)
            funds.append({"label": fd["label"], "schemeCode": fd["schemeCode"], "_w": w,
                          "cagr": (w[-1][1] / w[0][1]) ** (1 / yrs) - 1,
                          "xirr": _sip_xirr(w), "ter": fd.get("ter"),
                          "sharpe": (statistics.mean(dr) * 252 - RF) / vol if vol else None})
        if len(funds) < 2:
            continue
        bw = window(cat.get("benchmarkSchemeCode")) if cat.get("benchmarkSchemeCode") else None
        if bw:
            yard_name = cat.get("benchmarkName")
            yrs = (bw[-1][0] - bw[0][0]).days / 365.0
            yard_cagr = (bw[-1][1] / bw[0][1]) ** (1 / yrs) - 1
            yard_wk = _weekly(bw)
        else:
            yard_name = "average of funds we track"
            yard_cagr = statistics.mean(f["cagr"] for f in funds)
            wks = [_weekly(f["_w"]) for f in funds]
            common = sorted(set.intersection(*[set(w) for w in wks]))
            # equal-weighted peer index built from weekly returns
            yard_wk, lvl = {}, 100.0
            for i, k in enumerate(common):
                if i:
                    lvl *= 1 + statistics.mean(w[k] / w[common[i - 1]] - 1 for w in wks)
                yard_wk[k] = lvl
        for f in funds:
            f["vsBench"] = f["cagr"] - yard_cagr
            f["beta"] = _beta(_weekly(f["_w"]), yard_wk)
        pcts = {k: _pct([f[k] for f in funds], higher_better=k not in PERIOD_LOWER_BETTER)
                for k in PERIOD_WEIGHTS}
        for i, f in enumerate(funds):
            f["score"] = round(sum(PERIOD_WEIGHTS[k] * pcts[k][i] for k in PERIOD_WEIGHTS), 1)
        funds.sort(key=lambda f: -f["score"])
        r4 = lambda x: round(x, 4) if x is not None else None
        out[catkey] = {"yardstick": yard_name, "ranked": [
            {"rank": i, "label": f["label"], "schemeCode": f["schemeCode"], "score": f["score"],
             "xirr": r4(f["xirr"]), "cagr": r4(f["cagr"]), "vsBench": r4(f["vsBench"]),
             "sharpe": r4(f["sharpe"]), "beta": r4(f["beta"]), "ter": f["ter"]}
            for i, f in enumerate(funds, 1)]}
    return {"start": start.isoformat(), "end": today_end.isoformat(), "categories": out}


def write_period_picks(cfg, series_cache, out_path):
    out = {"asOf": datetime.date.today().isoformat(), "weights": PERIOD_WEIGHTS,
           "periods": {str(y): period_picks(cfg, series_cache, y) for y in (1, 3, 5)}}
    d = os.path.dirname(out_path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(out, fh, indent=1)
    os.replace(tmp, out_path)
    print("wrote", out_path)


def _ppf_rate(rates_path):
    try:
        for r in json.load(open(rates_path))["smallSavings"]:
            if r["scheme"].startswith("Public Provident Fund"):
                return r["rate"] / 100
    except Exception:
        pass
    return None


def write_rankings(candidates_path, out_path):
    cfg = json.load(open(candidates_path))
    all_codes = [bcode for cat in cfg["categories"].values() if (bcode := cat.get("benchmarkSchemeCode"))]
    all_codes += [fd['schemeCode'] for cat in cfg["categories"].values() for fd in cat['funds']]
    series_cache = fetch_all_series(all_codes)
    # A missing series would quietly drop that fund (or a category's
    # benchmark) from the published rankings. Keep the last good file instead;
    # the job fails visibly and the next run tries again.
    missing = [c for c, s in series_cache.items() if not s]
    if missing:
        sys.exit(f"no NAV history for scheme codes {missing} after retries — "
                 "fund-rankings.json left unchanged")

    ppf = _ppf_rate(os.path.join(os.path.dirname(candidates_path), "rates.json"))
    out = {"asOf": datetime.date.today().isoformat(), "ppfRate": ppf, "categories": {}}
    for catkey, cat in cfg["categories"].items():
        bcode = cat.get("benchmarkSchemeCode")
        bench = series_cache.get(bcode) if bcode else None
        funds = rank_category(cat, bench, series_cache, ppf)
        for f in funds:
            f['_catkey'] = catkey
        ranked = composite(funds, cat['profile'])
        # overlap guard: drop #2 if too correlated with #1, promote next
        if len(ranked) >= 2 and _corr(ranked[0]['_monthly'], ranked[1]['_monthly']) > 0.98:
            dup = ranked.pop(1)
            ranked.append(dup)
        cat_out = {"benchmark": cat.get("benchmarkName"), "ranked": []}
        ters = [f['metrics'].get('ter') for f in ranked if f['metrics'].get('ter') is not None]
        peer_ter = statistics.median(ters) if ters else None
        for i, f in enumerate(ranked, 1):
            m = f['metrics']
            cat_out["ranked"].append({
                "rank": i, "label": f['label'], "schemeCode": f['schemeCode'],
                "composite": f['composite'],
                "metrics": {k: (round(m[k], 4) if isinstance(m.get(k), float) else m.get(k))
                            for k in ('cagr3','cagr5','cagr7','sortino','sharpe','maxdd','vol',
                                      'alpha','beta','upcap','dncap','ir','consistency','ter','aum',
                                      'beatPPF5','windows5','since5','beatBench5','windowsBench5','sinceBench5','benchMonths')},
                "verdict": verdict(m, cat, ppf, peer_ter),
            })
        out["categories"][catkey] = cat_out
        print(f"{catkey:9} #1 {ranked[0]['label'] if ranked else '—'}")
    # atomic write — never leave a partial file
    d = os.path.dirname(out_path)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(out, fh, indent=2)
    os.replace(tmp, out_path)
    print("wrote", out_path)
    write_period_picks(cfg, series_cache, os.path.join(d, "period-picks.json"))
    return out


if __name__ == "__main__":
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    write_rankings(os.path.join(base, "MaverickInvestor", "data", "candidates.json"),
                   os.path.join(base, "MaverickInvestor", "data", "fund-rankings.json"))
