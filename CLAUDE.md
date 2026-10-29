# Maverick Investor

Indian personal-finance site: live MF NAV trackers, MF advisor, stock screener,
calculators, learning pages. Plain static HTML/CSS/JS, no build step.

## Layout and deploy

- `MaverickInvestor/` is the site root. GitHub Pages serves it at
  maverickinvestor.in (see `MaverickInvestor/CNAME`). Not Netlify.
- Any push to `main` deploys via `.github/workflows/deploy.yml` in about a minute.
- Owner's preference: merge changes straight to `main`; no PR unless asked.

## Data pipeline (one Claude scheduled task)

All site data is refreshed by a single Claude cloud scheduled task,
"Maverick Investor - Data Refresh" (Tue–Sat ~07:00 IST, push + email
summary to the owner). It runs the scripts below, commits straight to `main`,
and the push fires `deploy.yml`. There are no scheduled GitHub Actions; the
task's prompt is the source of truth for the cadence.

| Script | When the task runs it | Does |
|---|---|---|
| `tools/rank_funds.py` | every run | mfapi.in → `data/fund-rankings.json` (ranks, metrics, plain-English `verdict`, rolling 5-yr "beat PPF / benchmark" shares); refuses to write if any fund's NAVs are missing |
| `tools/build_nav_data.py` | every run | AMFI `NAVAll.txt` + mfapi.in → `data/navs.json` (home tracker), `data/nav-history/<code>.json` (MF Advisor backtest, duplicate check), `data/fund-list.json` and `data/crash-replay.json` (Tools page fund checks, via `assets/js/fund-checks.js`) |
| `tools/monthly_insights.py` | every run (no-op after the month's first) | snapshots rankings to `data/rankings-history/YYYY-MM.json`, writes `data/monthly-review.json` (what changed + picks report card) |
| `tools/update_stock_prices.py` | Saturdays, or if `priceAsOf` is 7+ days old | Yahoo chart → price in `stock-screener.html` |
| `tools/verify_scheme_codes.py` | with the stock prices (warn-only) | flags drifted AMFI scheme codes |
| `tools/update_fundamentals.py` | first run of each month (`fundAsOf` in an earlier month) | Screener.in → P/E, mcap, div yield, ROCE, TTM growth |
| `tools/monthly_review.py --dry-run` | after the fundamentals | report of manual items; the task files/updates the `data-review` issue from it |

mfapi.in stopped sending CORS headers in Oct 2026, so no page may fetch it in
the browser: pages read the same-origin files above instead. The home page's
Monthly Fund Review section (above the tracker) renders from
`fund-rankings.json` + `monthly-review.json`.
`deploy.yml` publishes `MaverickInvestor/` on every push to `main`.

Manual data: `data/rates.json` (small-savings/EPF/repo rates, review by
`nextReviewDue`) and TER/AUM in `data/candidates.json` (import with
`tools/import_fund_costs.py`). AMFI's robots.txt allowed automated reads as of
Oct 2026 (it used to forbid them); `build_nav_data.py` reads only `NAVAll.txt`.
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

## Design system (RiskMaverick port)

- One stylesheet: `MaverickInvestor/assets/css/site.css`. Light palette is the
  default; `[data-theme="dark"]` switches. Tokens mirror RiskMaverick's.
- Shared nav/footer: `assets/js/chrome.js` renders `<mi-nav>` / `<mi-footer>`
  (load it synchronously in `<head>`). Edit links there, once.
- Also per page: the inline no-flash `mi-theme` script first in `<head>`, then
  `theme.js`, `edge-guide.js`, `page-utils.js`, `reveal.js` before `</body>`.
  The head script also adds `html.rv` (tile entrance animation) unless the
  reader prefers reduced motion; tiles to animate are listed in `reveal.js`
  and the matching `.rv :is(...)` rule in `site.css`.
- Every page is on the system (Home, Tools & Goals, MF Advisor, Stock Screener,
  Learn, About). Each has `<body class="page-xxx">`; page-only styles live in
  `site.css` under a `PAGE — X` header, scoped to that class. No inline
  `<style>` blocks or per-page palettes.
- Inner-page layout: `section.page-hero` (section-label, h1 with an `<em>`,
  `.lede`), then `.container.page-body` holding `.tile` / `.tile--accent`
  cards. Tiles are opaque so the backdrop never shows through them.
- Backdrop: `<canvas id="page-candles" class="page-candles">` right after
  `<body>`, drawn by `assets/js/backdrop.js` (uses `assets/candles.js`).
- Charts read colours from the tokens (`cssVar('--ink-muted')` etc.) so they
  follow the theme.

## Cloud sessions

The cloud environment's network policy may block mfapi.in, screener.in,
riskmaverick.com and maverickinvestor.in. GitHub works either way. Network
settings apply when a session starts, so change them before opening a new one.
