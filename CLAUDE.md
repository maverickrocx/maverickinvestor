# Maverick Investor

Indian personal-finance site: live MF NAV trackers, MF advisor, stock screener,
calculators, learning pages. Plain static HTML/CSS/JS, no build step.

## Layout and deploy

- `MaverickInvestor/` is the site root. GitHub Pages serves it at
  maverickinvestor.in (see `MaverickInvestor/CNAME`). Not Netlify.
- Any push to `main` deploys via `.github/workflows/deploy.yml` in about a minute.
- Owner's preference: merge changes straight to `main`; no PR unless asked.

## Data pipeline (GitHub Actions, not Claude)

| Workflow | When | Does |
|---|---|---|
| `weekly-data-refresh.yml` | Sat 01:00 UTC | `tools/rank_funds.py` (mfapi.in → `data/fund-rankings.json`), `tools/update_stock_prices.py` (Yahoo chart → price in `stock-screener.html`), `tools/verify_scheme_codes.py` (warn-only) |
| `monthly-review.yml` | 1st, 02:00 UTC | `tools/update_fundamentals.py` (Screener.in → P/E, mcap, div yield, ROCE, TTM growth), then `tools/monthly_review.py` opens/updates one GitHub issue labelled `data-review` |
| `deploy.yml` | push to main, or after either job above | publishes `MaverickInvestor/` |

The bots commit with the default `GITHUB_TOKEN`, which does not fire `on: push`.
Any new workflow that commits site data must be added to `deploy.yml`'s
`workflow_run.workflows` list, or its data will not go live until an unrelated push.

Manual data: `data/rates.json` (small-savings/EPF/repo rates, review by
`nextReviewDue`) and TER/AUM in `data/candidates.json` (import with
`tools/import_fund_costs.py`; AMFI's robots.txt forbids crawling it).
Design rationale: `MaverickInvestor/docs/superpowers/specs/`.

## Guardrails

- The bots rewrite these by regex. Keep them intact:
  `stock-screener.html` `const STOCKS=[...];` (single line),
  `id="priceAsOf"`, `id="fundAsOf"`.
- `index.html` is ~1,000 lines. Edit it with a Python read/replace/write rather
  than the Edit tool (Edit has truncated it before). Afterwards check it ends
  with `</html>`, still calls `loadFundNAVs();`, and has exactly 1
  `Promise.allSettled`.
- Screener.in tarpits fast crawls: keep `update_fundamentals.py` sequential
  with its spacing. Yahoo `quoteSummary` is blocked outright; only
  `v8/finance/chart` works.
- Check page changes with Playwright at 1440px and 390px: no JS errors, no
  horizontal overflow.

## Design system (RiskMaverick port — in progress)

- One stylesheet: `MaverickInvestor/assets/css/site.css`. Light palette is the
  default; `[data-theme="dark"]` switches. Tokens mirror RiskMaverick's.
- Shared nav/footer: `assets/js/chrome.js` renders `<mi-nav>` / `<mi-footer>`
  (load it synchronously in `<head>`). Edit links there, once.
- Also per page: the inline no-flash `mi-theme` script first in `<head>`, then
  `theme.js`, `edge-guide.js`, `page-utils.js`, `reveal.js` before `</body>`.
  The head script also adds `html.rv` (tile entrance animation) unless the
  reader prefers reduced motion; tiles to animate are listed in `reveal.js`
  and the matching `.rv :is(...)` rule in `site.css`.
- Converted so far: `index.html`. The other pages still carry their own inline
  palettes until they are converted.

## Cloud sessions

The cloud environment's network policy may block mfapi.in, screener.in,
riskmaverick.com and maverickinvestor.in. GitHub works either way. Network
settings apply when a session starts, so change them before opening a new one.
