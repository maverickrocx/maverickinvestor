"""
Maverick Investor — AMFI scheme code verifier.

The site names mutual funds by AMFI scheme code in three separate places,
and they have drifted apart:

  - MaverickInvestor/data/candidates.json   (feeds the ranking job)
  - MaverickInvestor/index.html FUND_CONFIG (the live NAV tracker)
  - MaverickInvestor/mf-advisor.html FUND_DB (the advisor's offline fallback)

FUND_DB in particular still carries six-digit legacy codes (100270, 100216,
112922) that predate the Direct-plan split, so they either resolve to a
regular plan with a higher TER or no longer resolve at all. A wrong code
here does not throw — it quietly shows the visitor a different fund's NAV.

This checks every code against api.mfapi.in metadata and reports three
things per code: does it resolve, is it Direct-Growth, and does its
category match the bucket the site files it under.

Warn-only by design. It runs inside the weekly job to keep the report
fresh, but a scheme code going stale is not a reason to fail a data
refresh — the monthly review issue is where it gets surfaced for action.

Stdlib only. Run:
    python tools/verify_scheme_codes.py           # human-readable report
    python tools/verify_scheme_codes.py --json    # machine-readable, for monthly_review
"""
import json
import os
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "MaverickInvestor")
UA = "Mozilla/5.0 (compatible; MaverickInvestorBot/1.0; +https://maverickinvestor.in)"

# Site bucket -> the words we expect in mfapi's scheme_category. Kept loose
# on purpose: AMFI's category strings vary ("Equity Scheme - Large Cap Fund",
# "Equity Schemes - Large Cap Fund"), and this is a drift alarm, not a parser.
CATEGORY_HINTS = {
    "largeCap": ["large cap"],
    "flexiCap": ["flexi cap", "multi cap"],
    "midCap": ["mid cap"],
    "smallCap": ["small cap"],
    "gold": ["gold", "fof", "fund of funds"],
    "debt": ["debt", "corporate bond", "short duration", "banking and psu", "gilt"],
    "index": ["index", "other scheme"],
    "global": ["fof", "fund of funds", "overseas", "international"],
}


def fetch_meta(code):
    url = f"https://api.mfapi.in/mf/{code}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("meta") or None
    except Exception:
        return None


def collect():
    """Every (source, bucket, label, code, is_index) the site declares.

    is_index matters because an index fund legitimately sits in a category
    bucket while AMFI files it under 'Other Scheme - Index Funds' — flagging
    those as mismatches would bury the real breakage in noise."""
    out = []

    cand = json.load(open(os.path.join(SITE, "data", "candidates.json"), encoding="utf-8"))
    for bucket, cfg in cand["categories"].items():
        for f in cfg["funds"]:
            out.append(("candidates.json", bucket, f["label"], f["schemeCode"],
                        bool(f.get("isIndex"))))
        if cfg.get("benchmarkSchemeCode"):
            # Benchmarks are tracker funds by definition.
            out.append(("candidates.json", bucket, f"{cfg.get('benchmarkName')} (benchmark)",
                        cfg["benchmarkSchemeCode"], True))

    idx = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
    for name, cat, code in re.findall(
            r"name:'([^']+)'[^}]*?cat:'([^']+)'[^}]*?schemeCode:(\d+)", idx):
        out.append(("index.html FUND_CONFIG", cat, name, int(code),
                    cat in ("index", "global")))

    mfa = open(os.path.join(SITE, "mf-advisor.html"), encoding="utf-8").read()
    block = mfa[mfa.index("const FUND_DB"):mfa.index("const CAT_KEYS")]
    for bucket_match in re.finditer(r"(\w+):\[([\s\S]*?)\],?\s*(?=\w+:\[|\};)", block):
        bucket = bucket_match.group(1)
        for label, code in re.findall(r"\['([^']+)',(\d+),", bucket_match.group(2)):
            out.append(("mf-advisor.html FUND_DB", bucket, label, int(code), False))

    return out


def main():
    entries = collect()
    # De-duplicate the network calls: the same code appears in several files.
    codes = sorted({e[3] for e in entries})
    with ThreadPoolExecutor(max_workers=8) as ex:
        meta_by_code = dict(zip(codes, ex.map(fetch_meta, codes)))

    results = []
    for entry in entries:
        source, bucket, label, code, is_index = entry
        meta = meta_by_code.get(code)
        if not meta or not (meta.get("scheme_name") or "").strip():
            results.append((entry, "DEAD", "code does not resolve to a named scheme on mfapi.in"))
            continue
        name = (meta.get("scheme_name") or "").lower()
        category = (meta.get("scheme_category") or "").lower()
        problems = []
        # AMFI's scheme_name does not always carry the plan suffix, so absence
        # of "direct" is not evidence of a regular plan — but presence of
        # "regular" certainly is.
        if "regular" in name:
            problems.append("is the Regular plan, not Direct")
        # Several AMCs (ICICI notably) label the growth option "Cumulative",
        # and some records omit the option entirely while still carrying an
        # isin_growth — trust the metadata over the name.
        if not (("growth" in name or "cumulative" in name) or meta.get("isin_growth")):
            problems.append("not a Growth option")
        # Index funds sit in a category bucket but are filed by AMFI under
        # index/other-scheme, so the bucket check does not apply to them.
        hints = None if is_index else CATEGORY_HINTS.get(bucket)
        if hints and not any(h in category for h in hints):
            problems.append(f"category is '{meta.get('scheme_category')}'")
        if problems:
            results.append((entry, "MISMATCH",
                            "; ".join(problems) + f" — resolves to '{meta.get('scheme_name')}'"))
        else:
            results.append((entry, "OK", meta.get("scheme_name")))

    bad = [r for r in results if r[1] != "OK"]

    if "--json" in sys.argv:
        print(json.dumps([
            {"source": e[0], "bucket": e[1], "label": e[2], "code": e[3],
             "status": status, "detail": detail}
            for (e, status, detail) in bad
        ], indent=2))
        return

    print(f"checked {len(results)} scheme code references "
          f"({len(set(e[3] for e, _, _ in results))} distinct codes) · {len(bad)} need attention\n")
    for (source, bucket, label, code, _is_index), status, detail in bad:
        print(f"  [{status}] {code}  {label}")
        print(f"           in {source} under '{bucket}'")
        print(f"           {detail}")
    if not bad:
        print("  all scheme codes resolve to the right Direct-Growth scheme.")


if __name__ == "__main__":
    main()
