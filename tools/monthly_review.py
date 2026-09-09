"""
Maverick Investor — monthly data review.

Some numbers on the site cannot be refreshed automatically and should not
be faked:

  - data/rates.json — PPF, SSY, SCSS, NSC, KVP, POMIS, EPF and the repo
    rate. Notified by press release (PIB), annually (EPFO) or at each
    bi-monthly MPC. AMFI and the ministries publish no machine-readable
    feed, and amfiindia.com/robots.txt is a blanket Disallow, so these are
    a manually verified snapshot by design.
  - data/candidates.json — per-fund TER and AUM, which feed roughly a fifth
    of the ranking composite. Same problem, same answer: the user supplies a
    file (see import_fund_costs.py).
  - scheme codes across three files, which drift as AMCs rename, merge and
    retire schemes.

This replaces check_rates_due.py, which printed a `::warning::` into the
Actions log — a place nobody looks. Instead it opens one GitHub issue
listing exactly what needs a human, updates that same issue on later runs
rather than filing duplicates, and closes it once the underlying dates have
moved on.

It never edits a data file. Deciding what PPF pays is not a job for a cron.

Needs `gh` on PATH and GH_TOKEN in the environment (both standard in
Actions). Run:
    python tools/monthly_review.py            # open/update/close the issue
    python tools/monthly_review.py --dry-run  # print the report, touch nothing
"""
import datetime
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "MaverickInvestor")
RATES = os.path.join(SITE, "data", "rates.json")
CANDIDATES = os.path.join(SITE, "data", "candidates.json")

ISSUE_TITLE = "Monthly data review: manual figures need re-verifying"
ISSUE_LABEL = "data-review"
# TER and AUM move slowly enough that a quarter is a fair review cycle, but
# the ranking composite leans on them, so we start nudging at 90 days.
CANDIDATES_MAX_AGE_DAYS = 90


def check_rates(today):
    rates = json.load(open(RATES, encoding="utf-8"))
    due = datetime.date.fromisoformat(rates["nextReviewDue"])
    if today < due:
        return None
    return (
        f"**Small savings / EPF / repo rates** — review was due {due:%d %b %Y} "
        f"({(today - due).days} days ago). Current snapshot is `{rates['quarter']}`, "
        f"stamped {rates['asOf']}.\n"
        f"  - Small savings rates: [Ministry of Finance / PIB releases](https://pib.gov.in/allRel.aspx)\n"
        f"  - EPF rate: [EPFO](https://www.epfindia.gov.in/)\n"
        f"  - Repo rate: [RBI MPC decisions](https://www.rbi.org.in/Scripts/BS_PressReleaseDisplay.aspx)\n"
        f"  - Update `MaverickInvestor/data/rates.json`, including `asOf` and `nextReviewDue`."
    )


def check_candidates(today):
    cand = json.load(open(CANDIDATES, encoding="utf-8"))
    reviewed = datetime.date.fromisoformat(cand["reviewedOn"])
    age = (today - reviewed).days
    if age < CANDIDATES_MAX_AGE_DAYS:
        return None
    n = sum(len(c["funds"]) for c in cand["categories"].values())
    return (
        f"**Fund TER and AUM** — last reviewed {reviewed:%d %b %Y} ({age} days ago), "
        f"covering {n} funds. These feed ~20% of the ranking composite, so staleness "
        f"skews the rankings themselves.\n"
        f"  - AMFI publishes both as downloads under Research & Information "
        f"(Average AUM, and TER of Mutual Fund Schemes). Their robots.txt forbids "
        f"crawling, so this stays a manual download rather than an automated pull.\n"
        f"  - Drop the figures into `MaverickInvestor/data/fund-costs.csv` and run "
        f"`python tools/import_fund_costs.py`."
    )


def check_scheme_codes():
    try:
        out = subprocess.run(
            [sys.executable, os.path.join(ROOT, "tools", "verify_scheme_codes.py"), "--json"],
            capture_output=True, text=True, timeout=180, check=True,
        ).stdout
        bad = json.loads(out)
    except Exception as e:
        return f"**Scheme code check did not run** — {type(e).__name__}. Worth a look."
    if not bad:
        return None
    lines = "\n".join(
        f"  - `{b['code']}` ({b['label']}) in {b['source']} — {b['status']}: {b['detail']}"
        for b in bad
    )
    return (f"**{len(bad)} scheme code reference(s) no longer resolve correctly.** A wrong "
            f"code does not error, it quietly shows a different fund's NAV.\n{lines}")


def gh(*args, check=True):
    return subprocess.run(["gh", *args], capture_output=True, text=True, check=check)


def find_open_issue():
    out = gh("issue", "list", "--label", ISSUE_LABEL, "--state", "open",
             "--json", "number,title", check=False)
    if out.returncode != 0:
        return None
    for issue in json.loads(out.stdout or "[]"):
        if issue["title"] == ISSUE_TITLE:
            return issue["number"]
    return None


def main():
    today = datetime.date.today()
    items = [c for c in (check_rates(today), check_candidates(today), check_scheme_codes()) if c]

    if items:
        body = (
            f"Automated monthly check, {today:%d %B %Y}. "
            f"{len(items)} item(s) below need a person — these are the figures the site "
            f"cannot refresh on its own, and guessing at them would be worse than leaving "
            f"them stale.\n\n"
            + "\n\n".join(f"### {i + 1}. {item}" for i, item in enumerate(items))
            + "\n\n---\nThis issue closes itself once the underlying dates have moved on. "
              "Raised by `tools/monthly_review.py`."
        )
    else:
        body = None

    if "--dry-run" in sys.argv:
        print(body or f"{today:%d %B %Y}: nothing outstanding — no issue needed.")
        return

    existing = find_open_issue()

    if not items:
        if existing:
            gh("issue", "close", str(existing),
               "--comment", "All manual figures are current again — closing automatically.")
            print(f"closed #{existing} — nothing outstanding")
        else:
            print("nothing outstanding, no open issue")
        return

    if existing:
        gh("issue", "edit", str(existing), "--body", body)
        print(f"updated #{existing} with {len(items)} outstanding item(s)")
    else:
        # The label may not exist yet on a fresh repo; create it, ignoring
        # the error if it is already there.
        gh("label", "create", ISSUE_LABEL, "--description",
           "Manual data figures needing periodic re-verification",
           "--color", "D4C5F9", check=False)
        out = gh("issue", "create", "--title", ISSUE_TITLE,
                 "--label", ISSUE_LABEL, "--body", body)
        print(f"opened issue with {len(items)} outstanding item(s): {out.stdout.strip()}")


if __name__ == "__main__":
    main()
