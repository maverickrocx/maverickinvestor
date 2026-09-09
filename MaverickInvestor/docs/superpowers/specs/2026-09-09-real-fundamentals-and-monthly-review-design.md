# Real fundamentals + monthly review — design

**Date:** 2026-09-09
**Status:** Approved

## Problem

The Saturday refresh job (`weekly-data-refresh.yml`) reliably updates two things: MF
NAV rankings and the 150 stock prices. Everything else on the stock screener is
either frozen or estimated.

- `roce`, `profitGr`, `salesGr` — a hand-typed Screener.in snapshot from 7 Aug 2026.
  Never refreshed.
- `pe`, `mcap`, `divYield` — not fetched. `update_stock_prices.py` scales them by the
  same ratio the price moved, so they *look* current but are derived, not observed.
  Yahoo's `quoteSummary` endpoint (which would supply the real values) returns 401
  without a crumb, and the crumb handshake is rejected.
- `data/rates.json` (PPF/EPF/SCSS/NSC/SSY/repo) — a manual snapshot. `check_rates_due.py`
  runs weekly and emits a `::warning::` into the Actions log, which nobody reads.
- `data/candidates.json` — per-fund TER and AUM, `reviewedOn: 2026-07-13`. Feeds ~20%
  of the ranking composite weight, so staleness actively skews rankings.
- Scheme codes disagree across three files (see "Scheme code reconciliation").

## Findings

**Yahoo `quoteSummary` is blocked everywhere, not just from CI.** The existing module
docstring attributes the failure to "datacenter/CI IPs". Verified 2026-09-09 from a
residential connection: `quoteSummary` and `v7/finance/quote` both return 401. The
`v8/finance/chart` endpoint remains open and cookie-free. Chasing the crumb flow
further is not worthwhile.

**Screener.in supplies every missing field and permits automated reads.**
`https://www.screener.in/robots.txt` disallows only `/user/*`, query-parameter URLs
(`/*?q=`, `/*?sort=`, `/*?limit=`, `/*?page=`) and `/company/source/quarter/*`.
`/company/<SYMBOL>/consolidated/` is permitted. It is also the source the screener page
already credits. Verified against RELIANCE, SUZLON, ANANDRATHI and M&M (the last
requiring URL-encoding): all six fields parse cleanly.

**AMFI forbids crawling.** `https://www.amfiindia.com/robots.txt` is
`User-agent: *` / `Disallow: /`. No automated TER/AUM pull will be built. The user
supplies a file instead.

**Screener.in will not tolerate a weekly 150-page crawl.** Discovered during
implementation, not design. A first attempt at 4 concurrent workers with 0.4s spacing
completed ~85 of 150 stocks, then this IP was tarpitted: every subsequent request —
`robots.txt` included — took a flat 21.2 seconds. No 429, no `Retry-After`, just silence
stretched out. That is a clear signal about what they will tolerate, and the response is
to ask for less rather than to spread load across UAs or addresses until it stops being
noticed.

This forced a cadence split, and the split is better design anyway: these six figures
only move when a company reports, which is quarterly. Refreshing them weekly was 150
needless requests against someone else's server for numbers that had not changed.

## Design

### 1. Weekly job — schedule unchanged

`weekly-data-refresh.yml` stays on `cron: "0 1 * * 6"` (Saturday 01:00 UTC / 06:30 IST).
Confirmed as a deliberate choice: Friday's close has settled on both feeds by then, and
nothing moves over the weekend.

Steps become:

1. `rank_funds.py` — unchanged
2. `update_stock_prices.py` — rewritten: **price only** (below)
3. `verify_scheme_codes.py` — new, warn-only
4. Commit `fund-rankings.json` + `stock-screener.html`

`check_rates_due.py` is removed from this job; it moves to the monthly one.

### 2. Price and fundamentals split into two tools

Different cadences and different risk profiles, so they became separate modules sharing
one ticker map (`stock_tickers.py`) — kept in one place so the two jobs cannot drift
apart.

| Tool | Cadence | Fields | Source |
|---|---|---|---|
| `update_stock_prices.py` | Weekly | `price` | Yahoo `v8/finance/chart` |
| `update_fundamentals.py` | Monthly | `pe`, `mcap`, `divYield`, `roce`, `salesGr`, `profitGr` | Screener.in |

`salesGr` / `profitGr` come from the "Compounded {Sales,Profit} Growth" table's **TTM**
row, matched by label rather than position — a company young enough to lack a 10-year
row would otherwise shift the offsets and yield the wrong period entirely.

The Yahoo crumb machinery (`get_crumb`, `fetch_quote_summary`, `_session`) is deleted.
So is the proportional-scaling fallback — a field that cannot be observed is now left at
its previous value and reported, never silently derived.

**Growth definition change.** Stored `salesGr` for Reliance is 27.02; Screener's TTM
figure is 15. These measure different periods. Approved decision: adopt Screener's TTM
column so all 150 rows share one definition. Every value in both growth columns changes
on first run. This is expected, not a regression.

**Crawl etiquette.** Sequential — one request at a time, 5s spacing, identifying
User-Agent, once a month. A full pass is ~13 minutes of mostly waiting, which a monthly
cron absorbs without noticing. If this dataset ever needs to be fresher than monthly, the
answer is a sanctioned feed (Screener sells data exports), not a faster crawler.

**Safety rules** (existing ones retained, extended to new fields):

- No ticker mapping, failed fetch, or price move >45% → stock skipped and logged, never guessed
- Each fundamental independently range-checked; an implausible value drops that one
  field only, leaving the rest of the row updated
- Screener price cross-checked against Yahoo price; divergence >25% flags a probable
  bad ticker mapping and skips that stock's fundamentals
- Fewer than 70% of stocks get a price refresh → no prices written
- Fewer than **90%** return usable fundamentals → **no fundamentals written at all**.
  Added after the first run left the table holding 85 September rows beside 65 August
  ones with nothing on the page to distinguish them. A uniformly older table is honest;
  a silently mixed one is not.

### 3. Monthly job — `monthly-review.yml` (new)

Runs `cron: "0 2 1 * *"` (1st of month, 02:00 UTC). Runs `tools/monthly_review.py`,
which replaces `check_rates_due.py`.

It first runs `update_fundamentals.py` (the Screener.in crawl above), then checks three
things and never edits data files:

- `rates.json.nextReviewDue` — has it passed?
- `candidates.json.reviewedOn` — older than 90 days?
- Scheme-code warnings from `verify_scheme_codes.py`

If anything is outstanding it opens **one** GitHub issue (label `data-review`) listing
exactly what needs manual attention, with source links. It reuses the existing open
issue rather than filing a duplicate, and closes it automatically once the underlying
dates have advanced. Uses `GITHUB_TOKEN` via `gh` — no new secrets.

### 4. TER/AUM import — `import_fund_costs.py` (new)

User-supplied file at `data/fund-costs.csv`:

```
schemeCode,ter,aum
118825,0.54,38420
```

The script validates every row (scheme code exists in `candidates.json`, TER in
0–3%, AUM > 0), prints a before/after table for eyeballing, merges into
`candidates.json`, and stamps `reviewedOn` with today's date. Run manually, not on a
cron — it only executes when the user has supplied a fresh file.

If the user instead supplies AMFI's own Excel export, the importer is adapted to its
columns then. AMFI keys on scheme *name*, not code; with 32 funds every match is printed
for manual confirmation before any write.

### 5. Scheme code reconciliation

`verify_scheme_codes.py` checks every code in `candidates.json`, `index.html`
`FUND_CONFIG`, and `mf-advisor.html` `FUND_DB` against `api.mfapi.in/mf/<code>` metadata:
code resolves, plan is Direct-Growth, category matches its declared bucket. Warn-only in
the weekly job; surfaced in the monthly issue.

**What the check actually found.** 76 references across 54 distinct codes; 7 broken, all
of them in `mf-advisor.html` `FUND_DB`, and worse than "stale". These do not error — they
quietly serve a different fund's NAV and metrics:

| Label shown to the visitor | Old code | Actually resolved to | Fixed to |
|---|---|---|---|
| Axis Bluechip Fund | 112922 | *Aditya Birla Sun Life India Reforms Fund-DIVIDEND* | 120465 (Axis Large Cap) |
| ICICI Pru Corporate Bond Fund | 120687 | *ICICI Pru Exports & Services Fund — IDCW* (equity sectoral) | 120692 |
| HDFC Short Term Debt Fund | 119214 | *Morgan Stanley Multi Asset Fund — Quarterly Dividend* | 119016 |
| Mirae Asset Large Cap Fund | 118834 | *Mirae Asset Large & Midcap Fund* | 118825 |
| HDFC Flexi Cap Fund | 100270 | nothing (dead code) | 118955 |
| HDFC Mid-Cap Opportunities Fund | 100216 | nothing (dead code) | 118989 |
| Nippon India Small Cap Fund | 118798 | nothing (dead code) | 118778 |

Every replacement is a code `candidates.json` already carries and the verifier already
passes, not a guess. `FUND_DB` is the advisor's offline fallback, so this surfaced only
when `fund-rankings.json` failed to load — which is exactly why it went unnoticed.
Post-fix the verifier reports 0 of 76 needing attention.

**Two checks were wrong at first and were tightened**, because a report full of false
positives is a report nobody reads:

- Index funds and benchmarks legitimately sit in a category bucket while AMFI files them
  under "Other Scheme - Index Funds". The bucket check no longer applies to them.
- AMFI's `scheme_name` does not always carry the plan suffix (`127042` Motilal Oswal
  Midcap is a valid Direct-Growth scheme whose record simply omits it), and several AMCs
  label the growth option "Cumulative". Absence of "Direct" is now treated as unproven
  rather than damning; presence of "Regular" still fails. Growth is confirmed from
  `isin_growth` metadata rather than string-matching the name.

### 6. Site copy

`stock-screener.html` currently tells visitors ROCE and growth are a manual snapshot and
that P/E and market cap are price-scaled. Both statements stop being true. Update:

- Line ~149: both `fundAsOf` and `priceAsOf` are now stamped automatically, by their
  respective jobs, and shown separately — they genuinely have different vintages
- Line ~188: the "About the data" note now states the real cadence (price weekly,
  fundamentals monthly) and that growth is a TTM figure

A new `id="fundAsOf"` stamp is written by the script on each run alongside `priceAsOf`.

## Non-goals

- Automating TER/AUM (AMFI disallows crawling)
- Technical signals — RSI, moving averages, Bollinger Bands (still phase 2)
- Moving the weekly job to Sunday (considered, explicitly declined)
- Touching the calculator slider defaults in `tools.html` — user-driven inputs, not data

## Risks

**Screener.in blocks or rate-limits us.** The 70% floor means a bad week writes nothing
rather than corrupting the page, but the data would then quietly age. The monthly issue
surfaces it. Mitigation is deliberate politeness, not evasion — if Screener signals we
are unwelcome, we stop and revisit, we do not work around it.

**A wrong ticker maps to a real but different company.** This is the failure mode that
would silently publish wrong investment data. Guarded by the Yahoo/Screener price
cross-check: two independent sources agreeing on price is strong evidence the symbol is
right.

**First fundamentals run produces a large diff.** All 150 rows change across up to six
columns, and the growth columns change definition. Expected — but it should be reviewed
before it lands, not trusted blind. As of this commit that backfill has **not** run: the
tarpit made it impossible to complete on 2026-09-09, so the page still carries 7 Aug
fundamentals. The first full refresh happens on the monthly job, or sooner via
`workflow_dispatch` once the block has expired.
