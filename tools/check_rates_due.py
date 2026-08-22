"""
Maverick Investor — small-savings/repo rate review reminder.

There is no free, machine-readable feed for PPF/EPF/SCSS/NSC/SSY or the
RBI repo rate — small savings rates are notified quarterly by press
release (PIB), EPF annually, and repo rate at each bi-monthly MPC meeting.
Scraping those on a weekly cron would mostly find nothing and add fragile
maintenance for near-zero benefit, so MaverickInvestor/data/rates.json is
a manually verified snapshot instead (see its "note" field).

This check costs nothing (a date comparison, no network call) and is run
as part of the weekly refresh purely to surface a reminder when
data/rates.json.nextReviewDue has passed — it never edits the file.

Stdlib only. Run:
    python tools/check_rates_due.py
"""
import datetime, json, os

RATES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "MaverickInvestor", "data", "rates.json")


def main():
    rates = json.load(open(RATES_PATH))
    due = datetime.date.fromisoformat(rates["nextReviewDue"])
    today = datetime.date.today()
    if today >= due:
        print(f"::warning::rates.json review was due {due.isoformat()} (today {today.isoformat()}) — "
              f"check for a new small-savings/EPF/repo-rate notification and update data/rates.json manually")
    else:
        print(f"rates.json OK — next manual review due {due.isoformat()}")


if __name__ == "__main__":
    main()
