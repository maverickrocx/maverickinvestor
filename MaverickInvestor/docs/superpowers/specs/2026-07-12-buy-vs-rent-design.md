# Buy vs Rent Calculator — Design Spec

**Date:** 2026-07-12
**Status:** Approved by owner
**Scope:** v1 — residential house only. Commercial property mode explicitly deferred.

## Purpose

Help Indian investors answer: "Should I buy a house (down payment + home loan EMI, property appreciation) or keep renting and invest the same money in mutual funds?" Includes a buy-to-let mode that reframes the question as "Is this house a better investment than mutual funds?"

## Placement & Layout

- New full-width section on `MaverickInvestor/tools.html`, anchor `id="buy-vs-rent"`, positioned after the "More Calculators" section and before the footer.
- Section header follows existing pattern: `.section-label` ("Buy vs Rent"), `.section-title`, `.section-sub`.
- Two-column grid (left inputs card, right results card) using the site's existing card styling (`.calc-card` visual language, dark theme). Stacks to one column at the same breakpoints as the existing calc grid.
- Footer "Tools" column gets a new link: "Buy vs Rent" → `tools.html#buy-vs-rent`.
- Chart.js added to tools.html via the same CDN `<script>` tag mf-advisor.html uses.

## Inputs (left card)

Mode toggle (two pills, styled like existing `.tab-btn`):
- **Buy to live** (default)
- **Buy to let**

Sliders, each with live value label (existing calculator pattern), re-computing on every `input` event (no Calculate button):

| Input | Range | Step | Default |
|---|---|---|---|
| Property price | ₹20L – ₹10Cr | ₹5L | ₹80L |
| Down payment | 10 – 100% | 5% | 20% |
| Stamp duty & registration | 0 – 10% | 0.5% | 7% |
| Loan interest rate | 6 – 12% | 0.25% | 8.5% |
| Loan tenure | 5 – 30 yrs | 1 | 20 |
| Monthly rent (same/similar property) | ₹5K – ₹5L | ₹1K | ₹25K |
| Rent escalation | 0 – 10%/yr | 0.5% | 5% |
| Property appreciation | 0 – 15%/yr | 0.5% | 6% |
| MF expected return | 6 – 18%/yr | 0.5% | 12% |
| Comparison horizon | 5 – 30 yrs | 1 | 20 |

## Financial Model

Single engine for both modes, built on an **equal-cash-outflow fairness rule**: every month both paths spend the same total; whichever path spends less invests the difference into mutual funds that month.

Definitions:
- `D` = down payment = price × dp%
- `S` = stamp duty = price × duty%
- `L` = loan principal = price − D
- `EMI` = standard amortized EMI on `L` at loan rate over tenure (0 if dp = 100%)
- `rent(t)` = monthly rent in year y = rent₀ × (1 + esc)^y (steps annually)
- Loan outstanding at any month from the standard amortization balance formula
- MF pots compound monthly at (1 + r)^(1/12) − 1 equivalent monthly rate

### Buy to live
- **Buyer path:** t₀ outflow D + S. Pays EMI monthly until min(tenure, horizon). Net worth(y) = price × (1+app)^y − loan outstanding(y) + buyer's MF pot.
- **Renter path:** t₀ invests D + S as MF lumpsum. Pays rent(t) monthly. Monthly diff = EMI − rent(t): if positive, renter SIPs the diff; if negative (rent > EMI, or after loan tenure ends when EMI = 0), the **buyer** SIPs the reverse diff into the buyer's MF pot. Net worth(y) = renter MF corpus.

### Buy to let
Same engine with rent flipped to the buyer's side as income:
- **Buyer path:** t₀ outflow D + S. Monthly net cost = EMI − rent(t): if positive, paid out of pocket; if negative (rental income exceeds EMI), surplus SIPs into buyer's MF pot. Net worth(y) = property value − loan outstanding + buyer MF pot.
- **MF path:** t₀ invests D + S lumpsum; monthly SIPs whatever the buyer paid out of pocket that month (max(0, EMI − rent(t))). Net worth(y) = MF corpus.

### Edge cases
- Horizon < tenure → outstanding balance correctly deducted from buyer's net worth.
- Horizon > tenure → EMI stops; buyer-side investing of the freed-up cash flow continues per the fairness rule.
- Down payment 100% → no loan, EMI 0; comparison is lumpsum property vs lumpsum + rent-diff MF.
- Simulation runs monthly internally; chart samples year-end values.

## Outputs (right card)

1. **Verdict banner:** winner + margin at horizon end, e.g. "🏡 Buying leaves you ₹42L ahead after 20 years" / "📈 Renting + SIP wins by ₹1.2 Cr". In buy-to-let mode the labels become "Property investment" vs "Mutual funds".
2. **Chart.js line chart:** two lines — buy-path net worth and rent/MF-path net worth — years 0..horizon. Y-axis, tooltip, and labels use auto Lakh/Crore unit selection based on the largest value shown (same logic as the fixed MF Advisor wealth chart).
3. **Crossover note** under the chart: "Buying overtakes in year N" or "Buying doesn't overtake within your horizon" (or the reverse, whichever applies).
4. **Stat row** (4 small stats): Monthly EMI · Total interest paid · Property value at horizon · MF corpus at horizon.
5. **Disclaimer line:** ignores maintenance, property tax, income tax, and vacancy; educational only, not investment advice.

## Formatting & Conventions

- Rupee formatting: auto ₹K / ₹L / ₹Cr (reuse `fmtL`-style helper).
- All code inline in tools.html (existing convention — no separate JS file).
- Dark-theme styling consistent with existing sections; verdict banner uses site orange (#f97316) accent.

## Out of Scope (v1)

- Commercial property mode (deferred; revisit with investment framing).
- Maintenance/property tax/society charges input.
- Home-loan tax benefits (Sec 24b / 80C) and rent HRA benefit.
- Vacancy assumptions for buy-to-let.
- PDF export.

## Testing

- Verify EMI math against the page's existing Loan EMI calculator for identical inputs.
- Sanity checks: dp 100% (no loan), horizon > tenure (buyer invests post-loan), rent > EMI (flow reversal), extreme appreciation/MF returns (unit auto-switch to Cr).
- Browser verification of both modes, chart rendering, crossover note, responsive stacking, and dark-theme consistency.
