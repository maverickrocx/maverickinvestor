"""
Maverick Investor — dynamic MF fund ranking job.

Reads MaverickInvestor/data/candidates.json, fetches live NAV + benchmark data
from mfapi.in, computes Tier-A metrics, ranks each category by a weighted-
percentile composite, and writes MaverickInvestor/data/fund-rankings.json.

Stdlib only. Run:
    python -c "import rank_funds; rank_funds.write_rankings(CAND, OUT)"
"""
import json, os, tempfile, urllib.request, datetime, statistics, math

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


def _get(url):
    with urllib.request.urlopen(url, timeout=25) as r:
        return json.load(r)


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


def metrics(series, bench=None, ter=None, aum=None):
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


def rank_category(cat, bench_series):
    prof = cat['profile']
    bench = bench_series if prof == 'activeEquity' else None
    eligible = []
    for fd in cat['funds']:
        s, nm = navseries(fd['schemeCode'])
        yrs = round((s[-1][0]-s[0][0]).days/365, 1) if s else 0
        min_yrs = 3 if fd.get('isIndex') else 5
        if yrs < min_yrs:
            continue
        mt = metrics(s, bench, fd.get('ter'), fd.get('aum'))
        if not mt:
            continue
        eligible.append({'label': fd['label'], 'schemeCode': fd['schemeCode'],
                         '_catkey': None, 'metrics': mt, '_monthly': _monthly(s)})
    return eligible


def write_rankings(candidates_path, out_path):
    cfg = json.load(open(candidates_path))
    # benchmarks
    bench_cache = {}
    out = {"asOf": datetime.date.today().isoformat(), "categories": {}}
    for catkey, cat in cfg["categories"].items():
        for fd in cat["funds"]:
            fd  # noqa
        bcode = cat.get("benchmarkSchemeCode")
        if bcode and bcode not in bench_cache:
            bench_cache[bcode] = navseries(bcode)[0]
        bench = bench_cache.get(bcode) if bcode else None
        funds = rank_category(cat, bench)
        for f in funds:
            f['_catkey'] = catkey
        ranked = composite(funds, cat['profile'])
        # overlap guard: drop #2 if too correlated with #1, promote next
        if len(ranked) >= 2 and _corr(ranked[0]['_monthly'], ranked[1]['_monthly']) > 0.98:
            dup = ranked.pop(1)
            ranked.append(dup)
        cat_out = {"benchmark": cat.get("benchmarkName"), "ranked": []}
        for i, f in enumerate(ranked, 1):
            m = f['metrics']
            cat_out["ranked"].append({
                "rank": i, "label": f['label'], "schemeCode": f['schemeCode'],
                "composite": f['composite'],
                "metrics": {k: (round(m[k], 4) if isinstance(m.get(k), float) else m.get(k))
                            for k in ('cagr3','cagr5','cagr7','sortino','sharpe','maxdd','vol',
                                      'alpha','beta','upcap','dncap','ir','consistency','ter','aum')}
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
    return out


if __name__ == "__main__":
    import sys
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    write_rankings(os.path.join(base, "MaverickInvestor", "data", "candidates.json"),
                   os.path.join(base, "MaverickInvestor", "data", "fund-rankings.json"))
