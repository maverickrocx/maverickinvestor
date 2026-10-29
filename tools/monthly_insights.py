"""
Maverick Investor — monthly fund review for the home page.

On the first run of each month this job:
  1. snapshots data/fund-rankings.json to data/rankings-history/YYYY-MM.json
  2. writes data/monthly-review.json: how each category's top 3 moved since
     last month's snapshot, and the numbers behind each move, in plain words

Later runs in the same month do nothing unless --force is given, so the
review reads as one monthly edition, not a daily ticker.

Stdlib only. Run:
    python tools/monthly_insights.py           # monthly; no-op mid-month
    python tools/monthly_insights.py --force   # rebuild the review now
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
RANKINGS = os.path.join(DATA, "fund-rankings.json")
SNAPS = os.path.join(DATA, "rankings-history")
OUT = os.path.join(DATA, "monthly-review.json")

CAT_NAMES = {"largeCap": "Large Cap", "flexiCap": "Flexi Cap", "midCap": "Mid Cap",
             "smallCap": "Small Cap", "gold": "Gold", "debt": "Debt"}

# metric -> (higher is better, how to say it got better, got worse, formatter)
_pc = lambda v: f"{v * 100:.1f}%"
_pc2 = lambda v: f"{v:.2f}%"
_x = lambda v: f"{v:.2f}"
_cap = lambda v: f"{v:.0f}%"
REASONS = {
    "cagr3":       (True,  "3-year return rose", "3-year return slipped", _pc),
    "cagr5":       (True,  "5-year return rose", "5-year return slipped", _pc),
    "sortino":     (True,  "more return for the ups and downs taken", "less return for the ups and downs taken", _x),
    "maxdd":       (True,  "worst fall became shallower", "worst fall deepened", _pc),
    "dncap":       (False, "held up better in falling months", "fell harder in falling months", _cap),
    "consistency": (False, "returns swung less from year to year", "returns swung more from year to year", _pc),
    "ter":         (False, "costs came down", "costs went up", _pc2),
}


def month_key(d):
    return d.strftime("%Y-%m")


def snapshots():
    if not os.path.isdir(SNAPS):
        return []
    return sorted(f[:-5] for f in os.listdir(SNAPS) if f.endswith(".json"))


def load_snap(key):
    return json.load(open(os.path.join(SNAPS, key + ".json")))


def _why(now_m, was_m, spreads):
    """Up to two metric moves that best explain a rank change, biggest first,
    each measured against how widely that metric varies across the category."""
    moves = []
    for k, (hib, up, down, fmt) in REASONS.items():
        a, b = was_m.get(k), now_m.get(k)
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
    for key, cat in now["categories"].items():
        ranked = cat["ranked"]
        prev = {f["schemeCode"]: f for f in was["categories"].get(key, {}).get("ranked", [])}
        spreads = {}
        for k in REASONS:
            vals = [f["metrics"].get(k) for f in ranked if f["metrics"].get(k) is not None]
            spreads[k] = statistics.pstdev(vals) if len(vals) > 1 else None
        moves = []
        for f in ranked[:3]:
            p = prev.get(f["schemeCode"])
            if p is None:
                moves.append({"label": f["label"], "rank": f["rank"], "was": None,
                              "why": ["new to our shortlist this month"]})
                continue
            if p["rank"] == f["rank"]:
                continue
            rose = f["rank"] < p["rank"]
            why = [t for _, t, better in _why(f["metrics"], p["metrics"], spreads) if better == rose][:2]
            moves.append({"label": f["label"], "rank": f["rank"], "was": p["rank"],
                          "why": why or ["its own numbers barely moved; its rivals' moved more"]})
        top = ranked[0]["label"] if ranked else None
        out.append({"category": key, "name": CAT_NAMES.get(key, key), "top": top,
                    "topWas": next((f["label"] for f in prev.values() if f["rank"] == 1), None),
                    "moves": moves})
    return out


def _write_json(path, obj):
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(obj, fh, indent=1)
    os.replace(tmp, path)


def main():
    force = "--force" in sys.argv
    today = datetime.date.today()
    os.makedirs(SNAPS, exist_ok=True)
    this_month = month_key(today)
    if this_month not in snapshots():
        shutil.copyfile(RANKINGS, os.path.join(SNAPS, this_month + ".json"))
        print(f"snapshotted rankings as {this_month}")
    elif not force:
        print(f"{this_month} review already published; nothing to do (use --force to rebuild)")
        return

    keys = snapshots()
    if len(keys) < 2:
        print("need two monthly snapshots before there is anything to compare")
        return
    now, was = load_snap(keys[-1]), load_snap(keys[-2])
    _write_json(OUT, {
        "month": keys[-1], "since": was["asOf"], "asOf": now["asOf"],
        "generated": today.isoformat(),
        "changes": changes(now, was),
    })
    print(f"wrote monthly-review.json for {keys[-1]} (changes since {was['asOf']})")


if __name__ == "__main__":
    main()
