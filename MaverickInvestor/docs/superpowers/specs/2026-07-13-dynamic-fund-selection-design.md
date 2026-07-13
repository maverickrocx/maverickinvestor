# Dynamic Fund Selection — Design Spec

**Date:** 2026-07-13
**Status:** Approved by owner (brainstorming complete)
**Applies to:** MF Advisor engine on both maverickinvestor.in (`mf-advisor.html`) and the Android app (`MaverickInvestor-Compose`).

## Purpose

Replace the advisor's hard-coded 2-funds-per-category table with a **dynamically ranked, quarterly-curated** fund set, chosen on live NAV-derived quality metrics. This fixes the stale-scheme-code problem (7 of 10 original codes were wrong) and makes fund selection defensible, auditable, and self-refreshing.

## Current state & problems

- `FUND_DB` in `mf-advisor.html` hard-codes 2 funds per category (10 total). Several scheme codes point to the wrong scheme (e.g. `120687` "ICICI Corporate Bond" is actually the ICICI Exports & Services equity fund; `118834` "Mirae Large Cap" is Mirae Large & Midcap; Axis/HDFC/Nippon codes dead or wrong), so those funds silently fell back to a static CAGR.
- Sharpe / expense / AUM shown in the results table are hard-coded and display-only — never used for selection, and never refreshed.
- Selection = "first-listed" order, not any computed ranking.

## Scope

**In scope (v1):**
- Curated candidate shortlist per category (~10–12 funds), maintained and **reviewed quarterly**.
- Passive **index funds** compete as candidates within Large Cap and Flexi Cap (index *funds*, SIP-friendly — not ETFs).
- **Gold** added as a 6th allocation category (satellite, 5–10%), via Gold Fund-of-Funds.
- Weekly **precompute job** produces a `fund-rankings.json` that the website and app read instantly.
- Tier-A metrics (computable from free NAV data + the maintained shortlist).

**Out of scope (deferred):**
- Global / international funds (opt-in, phase-2 — tax and RBI-subscription-limit caveats).
- Sectoral / thematic funds (excluded from goal engine by design — concentration + timing risk).
- Tier-B metrics needing holdings/manager data: true holdings overlap, concentration, turnover, manager tenure, Morningstar/VR percentile.

## Architecture — precompute, cache, read

```
candidates.json  ──►  ranking job (weekly, GitHub Actions)  ──►  fund-rankings.json  ──►  website + app
   (curated,                fetch NAV + benchmark,                  (top-3/category,        (read instantly;
   quarterly)               compute metrics, rank                    metrics, as-of date)    live SIP-XIRR at run time)
```

- The job runs on a schedule (weekly) via GitHub Actions, the same infra the site deploys through. It commits the refreshed `MaverickInvestor/data/fund-rankings.json`, which deploys with the site. The app bundles the same file as an asset (refreshed on app update) and may fetch the live copy with the bundled one as fallback.
- Nothing heavy runs during a user session. Per-fund **SIP-XIRR** for the *chosen* funds is still computed live at advisor run time (as today) for the portfolio return estimate; ranking itself is precomputed.

### `candidates.json` (maintained input)

Per category: an array of candidates, each `{ label, schemeCode, ter, aum, isIndex }`, plus the category's `benchmarkSchemeCode`. Carries `reviewedOn` (date) and is the single file touched at each quarterly review. `ter`, `aum`, and `benchmarkSchemeCode` live here because NAV data does not provide them.

### `fund-rankings.json` (job output)

```
{
  "asOf": "2026-07-13",
  "categories": {
    "largeCap": {
      "benchmark": "Nifty 50",
      "ranked": [ { "rank":1, "label":"…", "schemeCode":118825, "composite":71.8,
                    "metrics": { "cagr5":0.106, "sortino":0.79, "maxdd":-0.37, … } }, … ]
    }, …
  }
}
```

## Eligibility filters (before ranking)

Applied per candidate; failures are excluded with a logged reason:
- Direct-Growth plan only.
- Track record ≥ 5 years for **active** funds; ≥ 3 years for **passive index** funds (no manager risk to judge, and index funds are newer).
- Correct SEBI category (verify scheme name matches).
- Exclude merged / closed / dividend-plan schemes.
- NAV series **de-spiked**: a single point that jumps >15% and reverts >15% the next day is replaced by the neighbour mean (removes mfapi glitches that would corrupt drawdown/volatility).

## Metrics (Tier-A, from NAV + shortlist)

| Metric | Direction | Source |
|---|---|---|
| Return blend (mean of 3/5/7-yr CAGR) | higher better | NAV |
| Consistency (σ of trailing 1-yr returns, monthly, ~5y) | lower better | NAV |
| Sortino (rf 6.5%) | higher better | NAV |
| Sharpe (rf 6.5%) | higher better | NAV |
| Max drawdown | higher (less negative) better | NAV |
| Volatility (annualised σ) | lower better | NAV |
| Alpha (CAPM vs benchmark) | higher better | NAV + benchmark |
| Beta | context (not scored) | NAV + benchmark |
| Up-capture / Down-capture | up higher / down lower better | NAV + benchmark |
| Information ratio (alpha ÷ tracking error) | higher better | NAV + benchmark |
| Expense (TER) | lower better | shortlist |
| AUM band | see below | shortlist |

**AUM band:** Large Cap / Flexi / Debt → larger is fine (liquidity), score by raw AUM. Mid Cap / Small Cap → sweet-spot band (peak ~₹15–20k cr) that penalises very large AUM for capacity constraints.

**Benchmarks (per category):** Large Cap → Nifty 50 index fund; Flexi Cap → Nifty 500 index fund; Mid Cap → Nifty Midcap 150 index fund; Small Cap → Nifty Smallcap 250 index fund. Gold and Debt use **absolute** metrics only (no equity benchmark → no alpha/capture/IR). Information ratio is suppressed when tracking error ≈ 0 (an index fund measured against its own index).

## Scoring — weighted percentile composite

For each metric, each candidate gets a **0–100 percentile rank within its category** (inverted for lower-is-better metrics). The composite is a weighted sum; funds are ranked by composite, descending. Weights are **tunable parameters**, exposed for the quarterly review.

Three per-category weight profiles (one profile per category, so all candidates in a category are scored on equal terms):

| Metric | Active Equity (LC, FC, MC, SC) | Debt | Tracker (Gold) |
|---|---|---|---|
| Return blend | 20% | 25% | 15% |
| Consistency | 10% | 10% | 10% |
| Sortino | 12% | 18% | 10% |
| Sharpe | 8% | 12% | — |
| Information ratio | 10% | — | — |
| Max drawdown | 8% | 15% | 15% |
| Down-capture | 7% | — | — |
| Up-capture | 5% | — | — |
| Expense (TER) | 10% | 10% | **40%** |
| AUM band | 10% | 10% | 10% |

Rationale for the **Tracker** profile: Gold FoFs (and pure index funds) all track the same underlying, so returns are near-identical across funds; selection should lean heavily on cost. Passive index funds inside Large Cap / Flexi are ranked under the **Active Equity** profile — they compete on the same terms and win only when active managers fail to add risk-adjusted value (observed: over the current window active large-caps out-ranked the Nifty 100 index, which is the intended self-correcting behaviour).

**Overlap guard:** after ranking, if the #2 fund's monthly-return correlation to #1 exceeds ~0.98, drop it and promote the next candidate (proxy for holdings overlap until Tier-B).

## Fund pick rule (per portfolio)

For each category the persona's allocation touches:
- Allocation weight **≤ 20%** → use rank **#1** only.
- Allocation weight **> 20%** → use rank **#1 and #2**, split equally.
- Rank **#3** is a reserve, used only if #1 or #2 becomes ineligible between refreshes.

Then re-normalise the selected funds to sum to 100%.

## Gold integration into the allocation matrix

The `ALLOC` matrix gains a 6th sleeve (Gold). Gold% by [effective persona × horizon]:

| | Short (s) | Medium (m) | Long (l) | Very-long (xl) |
|---|---|---|---|---|
| Guardian | 0 | 5 | 5 | 5 |
| Preserver | 0 | 5 | 7 | 7 |
| Balancer | 0 | 5 | 7 | 10 |
| Grower | 0 | 5 | 7 | 7 |
| Maverick | 0 | 0 | 5 | 5 |

Gold is 0% for Short horizons (goal too near for gold's volatility). The sleeve is funded by scaling the existing 5-way allocation to `(100 − Gold)%` proportionally, then appending Gold — preserving the equity/debt shape. Age guardrails and the corpus-adequacy nudge apply after Gold insertion.

## Quarterly review process

`candidates.json` carries `reviewedOn`. Each quarter: re-vet each category's shortlist (add strong new funds, drop persistent laggards), refresh `ter`/`aum`, confirm benchmark codes, and re-verify every scheme code still resolves to the right Direct-Growth scheme. A recurring quarterly reminder is scheduled. Weight profiles are reviewed at the same time.

## Resilience & data quality

- If the weekly job fails, or any candidate's NAV fetch is incomplete, the **last good `fund-rankings.json` is kept** — never overwritten with partial data. The advisor always reads a valid, recent ranking and can never fall back to broken hard-coded codes.
- Every scheme code is validated (scheme name contains the expected fund + "Direct" + "Growth") each run; a mismatch excludes the candidate and logs it.
- De-spiking (above) protects risk metrics from corrupt NAV points.

## Integration

- **Website:** `mf-advisor.html` fetches `data/fund-rankings.json` at load; `buildFundList()` reads the ranked lists and applies the pick rule instead of using `FUND_DB`. A bundled copy is the offline fallback. The results table shows the live metrics from the ranking (not hard-coded numbers).
- **App:** bundles `fund-rankings.json` as an asset (refreshed on app update); optionally fetches the live copy from the site with the bundled one as fallback. `AdvisorScreen` reads the same structure.

## Verification

A verification workbook regenerates from `fund-rankings.json` each quarter (same style as `MF_Advisor_Fund_Ranking_PREVIEW.xlsx`): every candidate, its metrics, composite score, rank, and the resulting portfolio picks — so each quarter's selection can be audited before it goes live.

## Testing

- Unit: metric functions (CAGR, Sortino, max drawdown, capture, alpha/beta, IR) against known series.
- Eligibility: young index fund admitted at ≥3y, young active fund rejected at <5y; de-spike removes an injected glitch.
- Ranking: composite reproduces the reviewed preview for the current shortlist; overlap guard drops a near-duplicate.
- Pick rule: category at exactly 20% → 1 fund; at 21% → 2 funds.
- Resilience: simulated job failure keeps the previous `fund-rankings.json`.
- Integration: website and app render the ranked funds; offline fallback works.
