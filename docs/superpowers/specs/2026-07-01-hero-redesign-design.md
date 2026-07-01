# Hero Redesign Design

## Context

`index.html`'s hero section already has a candlestick canvas background, a glassmorphism dashboard card, JetBrains Mono on numeric figures, and GSAP-driven stat-pill counters (dark theme, `#f97316` orange accent) from prior work. This project takes that baseline further and brings the other five pages up to the same visual language, since a survey found they diverge:

- `about.html`, `fund-advisor.html`, `learn.html`, `mf-advisor.html`, `stock-screener.html` each carry an identical, independently duplicated `#mi-bg-canvas` "matrix" background script instead of candlesticks.
- Only `index.html` loads JetBrains Mono and GSAP.
- `about.html` has real stats (₹66L+ portfolio, 13.6% XIRR, 5+ years, 30+ funds) embedded as plain paragraph text, not styled figures.
- `tools.html` / `learn.html` carry leftover, unused `.dashboard-card` CSS.
- `fund-advisor.html` / `mf-advisor.html` open directly into a goal-picker card grid rather than a heading hero.

The site is static HTML with no build step (GitHub Pages, per the `CNAME` file), so each page is currently a fully self-contained file with inline `<style>`/`<script>`.

## Scope

In scope: the hero section (or, for the two goal-picker pages, the top-of-page canvas + card grid) and the shared candlestick script, on all 7 pages listed above. Out of scope: any other page content (fund tables, calculators, footer, nav), and the `RiskMaverick` subfolder (separate project, not touched).

## Phase 1 — Homepage hero upgrade (`index.html`)

### 1. Candlestick motion realism
Opacity stays at the current ~0.18 (a deliberate choice — full-strength/parallax version was considered and rejected in favor of subtlety). Two changes to `initCandleCanvas()`:
- **Trend clustering**: replace the flat `Math.random() > 0.42` up/down coin-flip per candle with a slowly-evolving trend bias (e.g. a bias value updated every few candle-resets, nudged up or down, clamped to a range) so 3–5 consecutive candles tend to lean the same direction — reads as a real price run instead of noise.
- **Progressive formation**: instead of a candle fading in already at full body height, grow the body height from 0 to its target over ~15 frames after its wick draws, so new candles visibly "print" rather than pop in.

The existing upward drift-and-recycle loop, canvas resize handling, and 28px column spacing are unchanged.

### 2. Dashboard card depth (`.dashboard-card`)
- **Stacked-card depth**: a `::before` pseudo-element panel — same border-radius, more blur, lower opacity, offset ~10px down-and-left — sits behind `.dashboard-card` to read as a deck of cards. Pure CSS, no new markup.
- **Gradient border**: replace the flat `rgba(255,255,255,.12)` border with a conic-gradient ring (orange → transparent → green-ish → transparent) using the double-background (padding-box content + border-box gradient) technique, so it renders consistently without relying on `border-image`.
- **Entrance sheen**: a diagonal skewed-gradient sweep (`::after`) crosses the card once, timed to the existing GSAP entrance tween (`gsap.from('.dashboard-card', ...)`) — not a continuous loop.

### 3. Stat pills — all three counted
- Pill 1: `2000+` Funds Tracked (unchanged).
- Pill 2: `SEBI` → `14%` XIRR (rounded from the real 13.6% figure on `about.html`; rounding chosen to keep the counter whole-number-only, avoiding decimal-counter logic).
- Pill 3: `Free` → `100%` Free.
- All three get `data-count`/`data-suffix` and are picked up by the existing `.val[data-count]` GSAP counter loop.
- **Finishing flourish**: on each counter's `onComplete`, a brief (~0.3s) scale-bounce + orange glow pulse, then settles — not a looping effect.

### 4. Font
No change — `.stat-pill .val`, `.dc-amount`, `.ds-val` already use `var(--font-mono)` (JetBrains Mono), so the new pill values inherit it automatically.

## Phase 2 — Shared module + site-wide hero parity

### 5. Extract shared candlestick script
Move the (now more complex, trend/formation-aware) candlestick drawing logic out of `index.html`'s inline `<script>` into one external file, e.g. `assets/candles.js`, parameterized by canvas element id and container selector so it can target either a hero-scoped canvas (`position:absolute` within `.hero`, as on `index.html`) or a full-page canvas (`position:fixed`, as the other pages currently use for `#mi-bg-canvas`). All 6 pages load this one file instead of duplicating the logic.

### 6. Replace `#mi-bg-canvas` matrix backgrounds
On `about.html`, `fund-advisor.html`, `learn.html`, `mf-advisor.html`, `stock-screener.html`: swap the matrix-effect drawing code for the shared candlestick script, keeping each page's existing canvas element, positioning, and opacity untouched — only what's drawn changes. Add the shared script tag and the JetBrains Mono `<link>` (currently only on `index.html`) to every page that lacks them.

### 7. `about.html` stat pills
Promote the inline bio stats into 4 animated stat pills in `.about-hero`, matching the homepage pattern: `₹66L+` (portfolio), `14%` (XIRR, rounded consistent with Phase 1's pill 2), `5+` (years), `30+` (funds). Requires adding GSAP to this page (currently not loaded). The bio paragraph keeps a shorter version of the same claims in prose form — the pills don't replace the narrative, they highlight it.

### 8. Goal-picker pages glassmorphism
On `fund-advisor.html` and `mf-advisor.html`: restyle `.goal-card` tiles with the same glass recipe as `.dashboard-card` (translucent blurred background, gradient border) on top of the swapped candlestick background. These pages don't get stat pills — the cards are a picker, not a stats display.

### 9. Remaining pages — background swap only
`learn.html`, `tools.html`, `stock-screener.html`: swap `#mi-bg-canvas` to the shared candlestick script; no numeric figures currently live in these heroes, so no font or stat-pill work applies here. (`tools.html` and `learn.html`'s leftover unused `.dashboard-card` CSS rules are left as-is — cleanup of dead CSS is out of scope for this project.)

## Out of scope
- Any page content outside the hero / top-of-page canvas area.
- The `RiskMaverick` subfolder.
- Full site-wide JetBrains Mono audit (fund tables, calculators elsewhere on the page) — only figures that live within the hero sections themselves.
- Cleanup of the pre-existing unused `.dashboard-card` CSS on `tools.html`/`learn.html`.
