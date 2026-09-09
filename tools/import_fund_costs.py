"""
Maverick Investor — TER / AUM importer.

Merges user-supplied expense ratios and fund sizes into
MaverickInvestor/data/candidates.json, which the ranking job reads. TER and
AUM together carry roughly a fifth of the ranking composite, so stale
figures do not just look wrong — they reorder the recommendations.

Why this is manual: amfiindia.com/robots.txt is `Disallow: /`, so the AUM
and TER tables published there are not ours to crawl. Downloading them by
hand is fine; automating it against their stated wishes is not. So the
human fetches the file, and this script does the careful part — validating
and merging it without silently mangling anything.

Input: MaverickInvestor/data/fund-costs.csv

    schemeCode,ter,aum
    118825,0.54,38420

`aum` is in ₹ crore, matching what candidates.json already stores. Rows may
carry extra columns (a label, a date) and they are ignored, so an export
trimmed down from a spreadsheet works as-is.

Nothing is written until every row has been checked and the full before/after
is printed, because a typo here is invisible on the site — it just quietly
shifts which fund ranks first.

Stdlib only. Run:
    python tools/import_fund_costs.py             # show the diff, then write
    python tools/import_fund_costs.py --dry-run   # show the diff only
"""
import csv
import datetime
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CANDIDATES = os.path.join(ROOT, "MaverickInvestor", "data", "candidates.json")
COSTS_CSV = os.path.join(ROOT, "MaverickInvestor", "data", "fund-costs.csv")

# A direct-plan equity TER above 2.25% would breach SEBI's cap for all but the
# smallest schemes, so anything higher is a data-entry error, not a fund.
TER_RANGE = (0.0, 2.5)
MIN_AUM_CR = 1.0


def load_rows(path):
    rows, problems = {}, []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for lineno, row in enumerate(csv.DictReader(fh), start=2):
            norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
            raw_code = norm.get("schemecode") or norm.get("scheme_code") or norm.get("code")
            if not raw_code:
                problems.append(f"line {lineno}: no schemeCode column")
                continue
            try:
                code = int(float(raw_code))
                ter = float(norm["ter"])
                aum = float(norm["aum"].replace(",", ""))
            except (KeyError, ValueError, AttributeError):
                problems.append(f"line {lineno}: could not read schemeCode/ter/aum from {row}")
                continue

            if not TER_RANGE[0] <= ter <= TER_RANGE[1]:
                problems.append(f"line {lineno}: TER {ter} outside {TER_RANGE} — check units (% not fraction)")
                continue
            if aum < MIN_AUM_CR:
                problems.append(f"line {lineno}: AUM {aum} below {MIN_AUM_CR} Cr — check units (₹ crore)")
                continue
            if code in rows:
                problems.append(f"line {lineno}: schemeCode {code} appears twice")
                continue
            rows[code] = {"ter": ter, "aum": aum}
    return rows, problems


def main():
    if not os.path.exists(COSTS_CSV):
        sys.exit(f"no file at {COSTS_CSV}\n"
                 f"Create it with columns schemeCode,ter,aum — see this module's docstring.")

    rows, problems = load_rows(COSTS_CSV)
    cand = json.load(open(CANDIDATES, encoding="utf-8"))

    known = {}
    for bucket, cfg in cand["categories"].items():
        for f in cfg["funds"]:
            known[f["schemeCode"]] = (bucket, f)

    unknown = sorted(set(rows) - set(known))
    missing = sorted(set(known) - set(rows))

    changes = []
    for code, vals in rows.items():
        if code not in known:
            continue
        bucket, fund = known[code]
        if fund["ter"] != vals["ter"] or fund["aum"] != vals["aum"]:
            changes.append((bucket, fund, vals))

    print(f"read {len(rows)} valid row(s) from fund-costs.csv | "
          f"{len(known)} funds in candidates.json\n")

    if problems:
        print("Rows rejected:")
        for p in problems:
            print("  [x]", p)
        print()
    if unknown:
        print("Scheme codes not in candidates.json (ignored — add the fund there first):")
        for c in unknown:
            print(f"  [?] {c}")
        print()
    if missing:
        print("Funds in candidates.json with no row supplied (left unchanged):")
        for c in missing:
            print(f"  [-] {c} {known[c][1]['label']}")
        print()

    if not changes:
        print("No TER/AUM values differ — nothing to write.")
        return

    print(f"{len(changes)} fund(s) will change:\n")
    print(f"  {'fund':<38} {'TER':>14}   {'AUM (Cr)':>18}")
    for bucket, fund, vals in changes:
        ter_s = f"{fund['ter']} -> {vals['ter']}" if fund["ter"] != vals["ter"] else f"{fund['ter']} (same)"
        aum_s = f"{fund['aum']:,.0f} -> {vals['aum']:,.0f}" if fund["aum"] != vals["aum"] else f"{fund['aum']:,.0f} (same)"
        print(f"  {fund['label'][:38]:<38} {ter_s:>14}   {aum_s:>18}")

    if "--dry-run" in sys.argv:
        print("\n--dry-run: nothing written.")
        return

    for bucket, fund, vals in changes:
        fund["ter"] = vals["ter"]
        fund["aum"] = vals["aum"]

    cand["reviewedOn"] = datetime.date.today().isoformat()
    with open(CANDIDATES, "w", encoding="utf-8") as fh:
        json.dump(cand, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    print(f"\nwrote {CANDIDATES} | reviewedOn = {cand['reviewedOn']}")
    print("Re-run tools/rank_funds.py to fold the new figures into the rankings.")


if __name__ == "__main__":
    main()
