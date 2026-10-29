"""
Maverick Investor — monthly "What changed" for the home page.

The home page's pick cards follow data/period-picks.json (rank_funds.py): a
1/3/5-year ranking on SIP XIRR, return vs yardstick, Sharpe, expense ratio
and Beta. This job explains how the 3-year ranking moved month to month.

On the first run of each month it:
  1. snapshots data/period-picks.json to data/period-history/YYYY-MM.json
  2. writes data/monthly-review.json: how each category's 3-year top 3
     moved since last month's snapshot, and which of the five measures moved
     them, in plain words

Later runs in the same month do nothing unless --force is given, so the
review reads as one monthly edition, not a daily ticker.

--backfill YYYY-MM=YYYY-MM-DD rebuilds a past month's snapshot from NAV
history as of that date (expense ratios are today's; there is no history
of them), for when a month's snapshot is missing.

Stdlib only. Run:
    python tools/monthly_insights.py                          # monthly; no-op mid-month
    python tools/monthly_insights.py --force                  # rebuild the review now
    python tools/monthly_insights.py --backfill 2026-09=2026-09-05
"""
import datetime
import json
import os
import shutil
import statistics
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "MaverickInvestor", "data")
PICKS = os.path.join(DATA, "period-picks.json")
CANDIDATES = os.path.join(DATA, "candidates.json")
SNAPS = os.path.join(DATA, "period-history")
OUT = os.path.join(DATA, "monthly-review.json")
PERIOD = "3"

CAT_NAMES = {"largeCap": "Large Cap", "flexiCap": "Flexi Cap", "midCap": "Mid Cap",
             "smallCap": "Small Cap", "gold": "Gold", "debt": "Debt"}

# measure -> (higher is better, said when it helped, said when it hurt, formatter)
_pc = lambda v: f"{v * 100:.1f}%"
_pts = lambda v: f"{v * 100:+.1f} pts"
_x = lambda v: f"{v:.2f}"
REASONS = {
    "xirr":    (True,  "SIP return rose", "SIP return slipped", _pc),
    "vsBench": (True,  "lead over its yardstick grew", "lead over its yardstick shrank", _pts),
    "sharpe":  (True,  "more return for the risk taken", "less return for the risk taken", _x),
    "ter":     (False, "costs came down", "costs went up", lambda v: f"{v:.2f}%"),
    "beta":    (False, "swung less than its yardstick", "swung more than its yardstick", _x),
}


def month_key(d):
    return d.strftime("%Y-%m")


def snapshots():
    if not os.path.isdir(SNAPS):
        return []
    return sorted(f[:-5] for f in os.listdir(SNAPS) if f.endswith(".json"))


def load_snap(key):
    return json.load(open(os.path.join(SNAPS, key + ".json")))


def _why(now_f, was_f, spreads):
    """Measure moves that best explain a rank change, biggest first, each
    sized against how widely that measure varies across the category."""
    moves = []
    for k, (hib, up, down, fmt) in REASONS.items():
        a, b = was_f.get(k), now_f.get(k)
        if a is None or b is None or not spreads.get(k):
            continue
        z = (b - a) / spreads[k]
        if abs(z) < 0.25:
            continue
        better = (z > 0) == hib
        moves.append((abs(z), f"{up if better else down} ({fmt(a)} → {fmt(b)})", better))
    moves.sort(key=lambda t: -t[0])
    return moves


def changes(now, was):
    out = []
    for key, cat in now["periods"][PERIOD]["categories"].items():
        ranked = cat["ranked"]
        prev = {f["schemeCode"]: f for f in
                was["periods"][PERIOD]["categories"].get(key, {}).get("ranked", [])}
        spreads = {}
        for k in REASONS:
            vals = [f.get(k) for f in ranked if f.get(k) is not None]
            spreads[k] = statistics.pstdev(vals) if len(vals) > 1 else None
        moves = []
        for f in ranked[:3]:
            p = prev.get(f["schemeCode"])
            if p is None:
                moves.append({"label": f["label"], "rank": f["rank"], "was": None,
                              "why": ["new to the 3-year ranking this month"]})
                continue
            if p["rank"] == f["rank"]:
                continue
            rose = f["rank"] < p["rank"]
            why = [t for _, t, better in _why(f, p, spreads) if better == rose][:2]
            moves.append({"label": f["label"], "rank": f["rank"], "was": p["rank"],
                          "why": why or ["its own numbers barely moved; its rivals' moved more"]})
        out.append({"category": key, "name": CAT_NAMES.get(key, key),
                    "top": ranked[0]["label"] if ranked else None,
                    "topWas": next((f["label"] for f in prev.values() if f["rank"] == 1), None),
                    "moves": moves})
    return out


def _write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, path)


def backfill(spec):
    import rank_funds
    key, day = spec.split("=")
    as_of = datetime.date.fromisoformat(day)
    cfg = json.load(open(CANDIDATES))
    codes = {f["schemeCode"] for c in cfg["categories"].values() for f in c["funds"]}
    codes |= {c["benchmarkSchemeCode"] for c in cfg["categories"].values() if c.get("benchmarkSchemeCode")}
    series = rank_funds.fetch_all_series(sorted(codes))
    for c in [c for c in codes if not series.get(c)]:
        series[c] = rank_funds.navseries(c)[0]
    missing = [c for c in codes if not series.get(c)]
    if missing:
        sys.exit(f"no NAV history for {missing}; backfill not written")
    snap = {"asOf": day, "backfilled": True, "weights": rank_funds.PERIOD_WEIGHTS,
            "periods": {str(y): rank_funds.period_picks(cfg, series, y, as_of) for y in (1, 3, 5)}}
    os.makedirs(SNAPS, exist_ok=True)
    _write_json(os.path.join(SNAPS, key + ".json"), snap)
    print(f"backfilled {key} as of {day}")


def main():
    if "--backfill" in sys.argv:
        backfill(sys.argv[sys.argv.index("--backfill") + 1])
        return
    force = "--force" in sys.argv
    today = datetime.date.today()
    os.makedirs(SNAPS, exist_ok=True)
    this_month = month_key(today)
    if this_month not in snapshots():
        shutil.copyfile(PICKS, os.path.join(SNAPS, this_month + ".json"))
        print(f"snapshotted period picks as {this_month}")
    elif not force:
        print(f"{this_month} review already published; nothing to do (use --force to rebuild)")
        return

    keys = snapshots()
    if len(keys) < 2:
        print("need two monthly snapshots before there is anything to compare")
        return
    now, was = load_snap(keys[-1]), load_snap(keys[-2])
    _write_json(OUT, {
        "month": keys[-1], "period": int(PERIOD), "since": was["asOf"], "asOf": now["asOf"],
        "generated": today.isoformat(), "changes": changes(now, was),
    })
    print(f"wrote monthly-review.json for {keys[-1]} (3-year picks, changes since {was['asOf']})")


if __name__ == "__main__":
    main()
