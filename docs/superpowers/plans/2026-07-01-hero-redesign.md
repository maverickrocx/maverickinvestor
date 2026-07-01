# Hero Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the homepage hero (candlestick motion, glass card depth, counted stat pills) and roll a consistent candlestick-background / mono-figure / glass treatment out to the other real pages of the site.

**Architecture:** Pure static HTML/CSS/vanilla-JS site (GitHub Pages, no build step). Phase 1 edits inline `<style>`/`<script>` blocks already in `index.html`. Phase 2 extracts the candlestick canvas logic into one shared `assets/candles.js` file and points every page's existing background canvas at it, replacing each page's copy of an older "digital rain" script.

**Tech Stack:** Vanilla JS (ES5-style, matches existing code style), GSAP 3.12.5 (already CDN-loaded on `index.html`), CSS (custom properties, `backdrop-filter`, `conic-gradient`), Python's `http.server` for local preview (`.claude/launch.json`, port 3000).

## Global Constraints

- No test framework exists in this repo (static site, no `package.json`). "Testing" in this plan means visual verification through the `preview_*` tools (start the server, reload, `preview_screenshot`/`preview_snapshot`/`preview_console_logs`) — there is no automated assertion step.
- **Per-task discipline required by the user:** implement a task, verify it visually in the preview tool, THEN commit that task alone. Do not batch multiple tasks into one commit, and do not commit before showing the visual result.
- Dark theme + `#f97316` orange accent are already the active theme site-wide — do not touch the `:root` dark-theme override blocks except where a task explicitly adds a new token (`--font-mono`).
- Preserve every page's existing canvas element `id`, position (`fixed` vs the hero-scoped `absolute`), and opacity exactly — only the drawing algorithm changes.
- **Correction to the approved spec:** `fund-advisor.html` was listed in the spec (`docs/superpowers/specs/2026-07-01-hero-redesign-design.md`, items 6 and 8) as a page needing the candlestick swap and goal-card glassmorphism. On inspection, `fund-advisor.html` is a 26-line dead redirect stub (`<meta http-equiv="refresh" content="0; url=mf-advisor.html">`) with no hero, no canvas, and no goal cards — it was merged into `mf-advisor.html` previously. It is dropped from this plan entirely; `mf-advisor.html` is the only real goal-picker page and already covers items 6/8's intent.
- `assets/` does not exist yet in this repo; Task 4 creates it.

---

### Task 1: Candlestick motion realism (`index.html`)

**Files:**
- Modify: `index.html:2733-2854` (the `initCandleCanvas` function inside the "Hero candlestick canvas + GSAP animations" script block)

**Interfaces:**
- Produces: `initCandleCanvas()` behavior consumed later by Task 4 (which extracts this same logic into `assets/candles.js` — Task 4's version supersedes this inline copy).

- [ ] **Step 1: Replace the candle generation and draw loop**

Replace the entire block from `function initCandleCanvas() {` through its closing `}` (currently `index.html:2736-2812`) with:

```javascript
  function initCandleCanvas() {
    var canvas = document.getElementById('hero-candles');
    if (!canvas) return;
    var hero = document.querySelector('.hero');
    canvas.width  = hero.offsetWidth;
    canvas.height = hero.offsetHeight;
    var ctx = canvas.getContext('2d');

    var cols = Math.ceil(canvas.width / 28);
    var candles = [];
    var globalTrend = 0;
    var trendTimer = 0;

    function updateTrend() {
      trendTimer++;
      if (trendTimer > 40 + Math.random() * 60) {
        globalTrend += (Math.random() - 0.5) * 0.6;
        globalTrend = Math.max(-0.8, Math.min(0.8, globalTrend));
        trendTimer = 0;
      }
    }

    for (var i = 0; i < cols; i++) {
      candles.push(makeCandle(i, canvas.height));
    }

    function makeCandle(col, h) {
      var isUp   = Math.random() > (0.5 - globalTrend * 0.35);
      var bodyH  = 10 + Math.random() * 38;
      var bodyY  = 20 + Math.random() * (h - bodyH - 40);
      return {
        x: col * 28 + 6,
        bodyY: bodyY,
        targetBodyH: bodyH,
        bodyH: 0,
        wickTop: bodyY - 4 - Math.random() * 14,
        wickBot: bodyY + bodyH + 4 + Math.random() * 14,
        isUp: isUp,
        alpha: 0,
        targetAlpha: 0.55 + Math.random() * 0.45,
        speed: 0.012 + Math.random() * 0.018,
        delay: Math.random() * 120,
        timer: 0,
        formTimer: 0,
        formDuration: 12 + Math.random() * 10
      };
    }

    var frame = 0;
    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      frame++;
      updateTrend();
      candles.forEach(function(c, idx) {
        c.timer++;
        if (c.timer < c.delay) return;
        if (c.alpha < c.targetAlpha) c.alpha = Math.min(c.targetAlpha, c.alpha + c.speed);
        if (c.bodyH < c.targetBodyH) {
          c.formTimer++;
          c.bodyH = Math.min(c.targetBodyH, (c.formTimer / c.formDuration) * c.targetBodyH);
        }

        var color = c.isUp ? 'rgba(74,222,128,' + c.alpha + ')' : 'rgba(248,113,113,' + c.alpha + ')';
        /* wick */
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.moveTo(c.x + 5, c.wickTop);
        ctx.lineTo(c.x + 5, c.wickBot);
        ctx.stroke();
        /* body (grows in from bodyY as it forms) */
        ctx.fillStyle = color;
        ctx.fillRect(c.x, c.bodyY, 10, c.bodyH);

        /* slowly drift upward and reset */
        c.bodyY -= 0.12;
        c.wickTop -= 0.12;
        c.wickBot -= 0.12;
        if (c.bodyY + c.targetBodyH < -20) {
          var nc = makeCandle(idx, canvas.height);
          nc.bodyY = canvas.height + 10;
          nc.wickTop = nc.bodyY - 4 - Math.random() * 14;
          nc.wickBot = nc.bodyY + nc.targetBodyH + 4 + Math.random() * 14;
          nc.alpha = nc.targetAlpha;
          nc.bodyH = 0;
          nc.formTimer = 0;
          nc.delay = 0;
          candles[idx] = nc;
        }
      });
      requestAnimationFrame(draw);
    }
    draw();

    window.addEventListener('resize', function() {
      canvas.width  = hero.offsetWidth;
      canvas.height = hero.offsetHeight;
    });
  }
```

This adds a `globalTrend` random walk (clamped -0.8..0.8) that biases `isUp` so 3-5 consecutive candles tend to lean the same direction, and makes each candle's body grow from 0 to its target height over `formDuration` frames (~12-22 frames, both on initial spawn and on every recycle) instead of appearing at full height. Opacity fade-in (`alpha`/`targetAlpha`/`speed`) and the 0.18 canvas opacity in the HTML are untouched.

- [ ] **Step 2: Visual verification**

Start the preview server (`preview_start` with the `Maverick Investor` config), open `index.html`, and confirm via `preview_screenshot` + a ~3-4 second observation (e.g. two `preview_screenshot` calls a couple seconds apart, or `preview_console_logs` to confirm no JS errors) that:
- Candles still drift upward continuously with no console errors.
- New candles visibly grow from a thin sliver to full body height rather than popping in at full size.
- Runs of same-color (green/red) candles appear in short clusters rather than looking like uniform noise.

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "Hero candles: trend-clustered direction + progressive formation"
```

---

### Task 2: Dashboard card depth (`index.html`)

**Files:**
- Modify: `index.html:349-362` (`.dashboard-card` rule)
- Modify: `index.html:2844-2847` (GSAP `.dashboard-card` entrance tween — timing reference only, no code change needed, verify the sheen delay lines up)

**Interfaces:**
- Consumes: none (pure CSS).
- Produces: `.dashboard-card::before` (stacked depth panel) and `.dashboard-card::after` (`dcSheen` one-shot animation) selectors — no other task depends on these.

- [ ] **Step 1: Replace the `.dashboard-card` rule and add the depth/sheen rules**

Replace:

```css
    .dashboard-card {
      background: rgba(15,23,42,.55);
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      border: 1px solid rgba(255,255,255,.12);
      border-top: 1px solid rgba(255,255,255,.22);
      border-left: 1px solid rgba(255,255,255,.16);
      box-shadow: 0 8px 32px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.08);
      border-radius: var(--radius);
      padding: 1.5rem;
      width: 100%;
      max-width: 380px;
      color: var(--white);
    }
```

with:

```css
    .dashboard-card {
      position: relative;
      z-index: 1;
      background:
        linear-gradient(rgba(15,23,42,.55), rgba(15,23,42,.55)) padding-box,
        conic-gradient(from 180deg, rgba(249,115,22,.6), rgba(255,255,255,0) 35%, rgba(74,222,128,.5) 65%, rgba(255,255,255,0) 100%) border-box;
      backdrop-filter: blur(24px) saturate(180%);
      -webkit-backdrop-filter: blur(24px) saturate(180%);
      border: 1px solid transparent;
      box-shadow: 0 8px 32px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.08);
      border-radius: var(--radius);
      padding: 1.5rem;
      width: 100%;
      max-width: 380px;
      color: var(--white);
      overflow: hidden;
    }
    .dashboard-card::before {
      content: '';
      position: absolute;
      inset: 0;
      transform: translate(-10px, 10px);
      background: rgba(15,23,42,.35);
      backdrop-filter: blur(14px);
      -webkit-backdrop-filter: blur(14px);
      border: 1px solid rgba(255,255,255,.06);
      border-radius: var(--radius);
      z-index: -1;
    }
    .dashboard-card::after {
      content: '';
      position: absolute;
      top: 0; left: -60%;
      width: 40%; height: 100%;
      background: linear-gradient(115deg, transparent 0%, rgba(255,255,255,.16) 50%, transparent 100%);
      transform: skewX(-20deg);
      pointer-events: none;
      opacity: 0;
      animation: dcSheen 1.4s ease-out 1s 1 forwards;
    }
    @keyframes dcSheen {
      0%   { left: -60%; opacity: 0; }
      15%  { opacity: 1; }
      60%  { opacity: 1; }
      100% { left: 130%; opacity: 0; }
    }
```

Note: `overflow: hidden` is added so the sheen sweep and the offset `::before` panel don't visually spill past the card's rounded corners — verify in Step 2 that this doesn't clip the card's own drop shadow (it won't, since `box-shadow` is on the element itself and `overflow:hidden` only clips a box's own children/pseudo-content, not its own shadow).

- [ ] **Step 2: Visual verification**

Reload the preview, `preview_screenshot` the hero, and confirm:
- The portfolio card shows a visible second, dimmer glass panel offset behind its bottom-left edge.
- The card's border reads as a soft orange-to-green gradient ring rather than flat white.
- On page load, a light diagonal sheen sweeps once across the card (~1-1.5s after load) and does not repeat or loop.
- `preview_inspect` on `.dashboard-card` to confirm `backdrop-filter` is still applied (didn't get dropped by the background-layer change).

- [ ] **Step 3: Commit**

```bash
git add index.html
git commit -m "Hero dashboard card: stacked depth, gradient border, entrance sheen"
```

---

### Task 3: Stat pills — all three counted, with finishing flourish (`index.html`)

**Files:**
- Modify: `index.html:1765-1778` (stat-pill markup)
- Modify: `index.html:2823-2837` (counter GSAP loop)
- Modify: `index.html:332-340` (`.stat-pill` CSS — add pop animation)

**Interfaces:**
- Consumes: `.val[data-count]` convention already established by the existing counter loop.
- Produces: `.stat-pill.pill-pop` class + `pillPop` keyframes, applied/removed by the counter script's `onComplete`.

- [ ] **Step 1: Update stat-pill markup**

Replace (`index.html:1765-1778`):

```html
        <div class="hero-stats">
          <div class="stat-pill">
            <div class="val" data-count="2000" data-suffix="+">0</div>
            <div class="lbl">Funds Tracked</div>
          </div>
          <div class="stat-pill">
            <div class="val">SEBI</div>
            <div class="lbl">Compliant Info</div>
          </div>
          <div class="stat-pill">
            <div class="val">Free</div>
            <div class="lbl">All Calculators</div>
          </div>
        </div>
```

with:

```html
        <div class="hero-stats">
          <div class="stat-pill">
            <div class="val" data-count="2000" data-suffix="+">0</div>
            <div class="lbl">Funds Tracked</div>
          </div>
          <div class="stat-pill">
            <div class="val" data-count="14" data-suffix="%">0</div>
            <div class="lbl">Track Record XIRR</div>
          </div>
          <div class="stat-pill">
            <div class="val" data-count="100" data-suffix="%">0</div>
            <div class="lbl">Free Calculators</div>
          </div>
        </div>
```

- [ ] **Step 2: Add the finishing-flourish CSS**

Add immediately after the existing rule at `index.html:340` (`.stat-pill .lbl { ... }`):

```css
    .stat-pill.pill-pop { animation: pillPop .35s ease-out; }
    @keyframes pillPop {
      0%   { transform: scale(1);    box-shadow: 0 0 0 rgba(249,115,22,0); }
      40%  { transform: scale(1.06); box-shadow: 0 0 18px rgba(249,115,22,.55); }
      100% { transform: scale(1);    box-shadow: 0 0 0 rgba(249,115,22,0); }
    }
```

- [ ] **Step 3: Trigger the flourish from the counter's `onComplete`**

Replace (`index.html:2823-2837`):

```javascript
    /* number counter on data-count elements */
    document.querySelectorAll('.val[data-count]').forEach(function(el) {
      var target = parseInt(el.dataset.count, 10);
      var suffix = el.dataset.suffix || '';
      var obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: 1.8,
        delay: 0.6,
        ease: 'power2.out',
        onUpdate: function() {
          el.textContent = Math.round(obj.val).toLocaleString('en-IN') + suffix;
        }
      });
    });
```

with:

```javascript
    /* number counter on data-count elements */
    document.querySelectorAll('.val[data-count]').forEach(function(el) {
      var target = parseInt(el.dataset.count, 10);
      var suffix = el.dataset.suffix || '';
      var obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: 1.8,
        delay: 0.6,
        ease: 'power2.out',
        onUpdate: function() {
          el.textContent = Math.round(obj.val).toLocaleString('en-IN') + suffix;
        },
        onComplete: function() {
          var pill = el.closest('.stat-pill');
          pill.classList.add('pill-pop');
          setTimeout(function() { pill.classList.remove('pill-pop'); }, 350);
        }
      });
    });
```

- [ ] **Step 4: Visual verification**

Reload, `preview_snapshot` to confirm all three pills read "2,000+", "14%", "100%" after the counters finish (wait ~2.5s post-load or re-run snapshot after a short delay), and confirm (via screenshot timed right around the 2.4s mark) that each pill briefly scales up with an orange glow as its counter finishes, then settles back down.

- [ ] **Step 5: Commit**

```bash
git add index.html
git commit -m "Hero stat pills: all three counted (2000+/14%/100%) with completion flourish"
```

---

### Task 4: Extract shared candlestick + counter modules (`assets/candles.js`, `assets/counter.js`)

**Files:**
- Create: `assets/candles.js`
- Create: `assets/counter.js`
- Modify: `index.html:2732-2855` (remove the now-duplicated `initCandleCanvas` function and its call; load both shared scripts and call them with hero-specific options)

**Interfaces:**
- Produces: `window.initMaverickCandles(options)` — `options.canvasId` (string, required), `options.sizeToWindow` (bool, default `false`), `options.containerSelector` (string, used only when `sizeToWindow` is `false`, default `'.hero'`). Consumed by Tasks 5-9.
- Produces: `window.initMaverickCounters(selector)` — `selector` (string, a CSS selector matching `.val[data-count]` elements). Reads `data-count` (int, required), `data-prefix` (string, optional), `data-suffix` (string, optional) off each matched element; animates each from 0 to `data-count` over 1.8s with a 0.6s delay via GSAP, then adds/removes a `.pill-pop` class on the closest `.stat-pill` ancestor as a completion flourish. No-ops if `gsap` is undefined. Consumed by Task 5.

Note: this task adds the shared counter module in response to a pre-dispatch review finding — Task 3's inline counter script (below) and Task 5's original inline counter script were near-duplicates; extracting now avoids that duplication before Task 5 is implemented.

- [ ] **Step 1: Create `assets/candles.js`**

```javascript
(function (global) {
  function initMaverickCandles(opts) {
    opts = opts || {};
    var canvas = document.getElementById(opts.canvasId || 'mi-bg-canvas');
    if (!canvas) return;
    var sizeToWindow = !!opts.sizeToWindow;
    var container = sizeToWindow ? null : document.querySelector(opts.containerSelector || '.hero');
    var ctx = canvas.getContext('2d');

    function resize() {
      if (sizeToWindow) {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
      } else if (container) {
        canvas.width  = container.offsetWidth;
        canvas.height = container.offsetHeight;
      }
    }
    resize();

    var candles = [];
    var globalTrend = 0;
    var trendTimer = 0;

    function updateTrend() {
      trendTimer++;
      if (trendTimer > 40 + Math.random() * 60) {
        globalTrend += (Math.random() - 0.5) * 0.6;
        globalTrend = Math.max(-0.8, Math.min(0.8, globalTrend));
        trendTimer = 0;
      }
    }

    function makeCandle(col, h) {
      var isUp  = Math.random() > (0.5 - globalTrend * 0.35);
      var bodyH = 10 + Math.random() * 38;
      var bodyY = 20 + Math.random() * (h - bodyH - 40);
      return {
        x: col * 28 + 6,
        bodyY: bodyY,
        targetBodyH: bodyH,
        bodyH: 0,
        wickTop: bodyY - 4 - Math.random() * 14,
        wickBot: bodyY + bodyH + 4 + Math.random() * 14,
        isUp: isUp,
        alpha: 0,
        targetAlpha: 0.55 + Math.random() * 0.45,
        speed: 0.012 + Math.random() * 0.018,
        delay: Math.random() * 120,
        timer: 0,
        formTimer: 0,
        formDuration: 12 + Math.random() * 10
      };
    }

    var cols = Math.ceil(canvas.width / 28) || 1;
    for (var i = 0; i < cols; i++) candles.push(makeCandle(i, canvas.height));

    function draw() {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      updateTrend();
      candles.forEach(function (c, idx) {
        c.timer++;
        if (c.timer < c.delay) return;
        if (c.alpha < c.targetAlpha) c.alpha = Math.min(c.targetAlpha, c.alpha + c.speed);
        if (c.bodyH < c.targetBodyH) {
          c.formTimer++;
          c.bodyH = Math.min(c.targetBodyH, (c.formTimer / c.formDuration) * c.targetBodyH);
        }
        var color = c.isUp ? 'rgba(74,222,128,' + c.alpha + ')' : 'rgba(248,113,113,' + c.alpha + ')';
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.moveTo(c.x + 5, c.wickTop);
        ctx.lineTo(c.x + 5, c.wickBot);
        ctx.stroke();
        ctx.fillStyle = color;
        ctx.fillRect(c.x, c.bodyY, 10, c.bodyH);

        c.bodyY -= 0.12;
        c.wickTop -= 0.12;
        c.wickBot -= 0.12;
        if (c.bodyY + c.targetBodyH < -20) {
          var nc = makeCandle(idx, canvas.height);
          nc.bodyY = canvas.height + 10;
          nc.wickTop = nc.bodyY - 4 - Math.random() * 14;
          nc.wickBot = nc.bodyY + nc.targetBodyH + 4 + Math.random() * 14;
          nc.alpha = nc.targetAlpha;
          nc.bodyH = 0;
          nc.formTimer = 0;
          nc.delay = 0;
          candles[idx] = nc;
        }
      });
      requestAnimationFrame(draw);
    }
    draw();

    window.addEventListener('resize', resize);
  }

  global.initMaverickCandles = initMaverickCandles;
})(window);
```

- [ ] **Step 2: Create `assets/counter.js`**

```javascript
(function (global) {
  function initMaverickCounters(selector) {
    if (typeof gsap === 'undefined') return;
    document.querySelectorAll(selector).forEach(function (el) {
      var target = parseInt(el.dataset.count, 10);
      var prefix = el.dataset.prefix || '';
      var suffix = el.dataset.suffix || '';
      var obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: 1.8,
        delay: 0.6,
        ease: 'power2.out',
        onUpdate: function () {
          el.textContent = prefix + Math.round(obj.val).toLocaleString('en-IN') + suffix;
        },
        onComplete: function () {
          var pill = el.closest('.stat-pill');
          if (!pill) return;
          pill.classList.add('pill-pop');
          setTimeout(function () { pill.classList.remove('pill-pop'); }, 350);
        }
      });
    });
  }

  global.initMaverickCounters = initMaverickCounters;
})(window);
```

- [ ] **Step 3: Point `index.html` at both shared scripts**

In `index.html`'s `<head>`, immediately after the existing GSAP `<script>` tag (`index.html:10`), add:

```html
  <script src="assets/candles.js" defer></script>
  <script src="assets/counter.js" defer></script>
```

Then replace the whole `initCandleCanvas` function body and its call site (the block produced by Task 1, now at approximately `index.html:2733-2855`) — i.e. delete the `function initCandleCanvas() { ... }` definition entirely, and change:

```javascript
  document.addEventListener('DOMContentLoaded', function() {
    initCandleCanvas();
    initGSAP();
  });
```

to:

```javascript
  document.addEventListener('DOMContentLoaded', function() {
    initMaverickCandles({ canvasId: 'hero-candles', containerSelector: '.hero', sizeToWindow: false });
    initGSAP();
  });
```

Also, inside `initGSAP()`, replace the counter block that Task 3 wrote:

```javascript
    /* number counter on data-count elements */
    document.querySelectorAll('.val[data-count]').forEach(function(el) {
      var target = parseInt(el.dataset.count, 10);
      var suffix = el.dataset.suffix || '';
      var obj = { val: 0 };
      gsap.to(obj, {
        val: target,
        duration: 1.8,
        delay: 0.6,
        ease: 'power2.out',
        onUpdate: function() {
          el.textContent = Math.round(obj.val).toLocaleString('en-IN') + suffix;
        },
        onComplete: function() {
          var pill = el.closest('.stat-pill');
          pill.classList.add('pill-pop');
          setTimeout(function() { pill.classList.remove('pill-pop'); }, 350);
        }
      });
    });
```

with:

```javascript
    /* number counter on data-count elements */
    initMaverickCounters('.val[data-count]');
```

(the rest of `initGSAP` — pill entrance, hero-copy entrance, dashboard-card entrance — stays exactly as Task 3 left it.)

- [ ] **Step 4: Visual verification**

Reload the preview, confirm via `preview_console_logs` there's no "initMaverickCandles is not defined" / "initMaverickCounters is not defined" or 404s on `assets/candles.js` / `assets/counter.js` (check `preview_network`), and `preview_screenshot` + `preview_snapshot` to confirm the hero candlestick animation and the stat-pill counters (2,000+ / 14% / 100%, with the pop flourish) look identical to how they looked after Tasks 1 and 3 — this task is a pure refactor, not a visual change.

- [ ] **Step 5: Commit**

```bash
git add assets/candles.js assets/counter.js index.html
git commit -m "Extract candlestick canvas and stat-pill counter into shared assets/ modules"
```

---

### Task 5: `about.html` — candlestick swap, font/GSAP, promoted stat pills

**Files:**
- Modify: `about.html:7` (head — add font + GSAP + shared script tags)
- Modify: `about.html:9-24` (`:root` — add `--font-mono` token)
- Modify: `about.html:225-263` (remove matrix canvas script, call shared module instead)
- Modify: `about.html:293-295` (bio paragraph — shorten to prose, stats now live in pills)
- Modify: `about.html` (add `.about-stats`/`.stat-pill` CSS block and the 4-pill markup inside `.about-hero-inner`)

**Interfaces:**
- Consumes: `window.initMaverickCandles` (Task 4) and `window.initMaverickCounters(selector)` (Task 4) — no duplicate counter script here, `about.html` calls the shared module.

- [ ] **Step 1: Add font, GSAP, and shared-script tags to `<head>`**

After `about.html:7` (`<link rel="icon" ...>`), add:

```html
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700;800&display=swap" rel="stylesheet">
  <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js" defer></script>
  <script src="assets/candles.js" defer></script>
  <script src="assets/counter.js" defer></script>
```

- [ ] **Step 2: Add `--font-mono` token**

In the first `:root` block (`about.html:9-24`), add a line after `--font:` (line 23):

```css
      --font-mono:   'JetBrains Mono', 'Courier New', monospace;
```

- [ ] **Step 3: Replace the matrix canvas script**

Replace (`about.html:225-263`):

```html
<!-- Matrix particle background -->
<canvas id="mi-bg-canvas" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.55"></canvas>
<script>
(function(){
  var C=document.getElementById('mi-bg-canvas');
  var ctx=C.getContext('2d');
  var CS=22, cols, drops, speeds, colors;
  function init(){
    C.width=window.innerWidth; C.height=window.innerHeight;
    cols=Math.floor(C.width/CS);
    drops=Array.from({length:cols},function(){return Math.random()*(-(C.height/CS));});
    speeds=Array.from({length:cols},function(){return 0.25+Math.random()*0.55;});
    colors=Array.from({length:cols},function(){return Math.random()>0.82?'59,130,246':'249,115,22';});
  }
  var last=0;
  function draw(ts){
    requestAnimationFrame(draw);
    if(ts-last<28) return; last=ts;
    ctx.fillStyle='rgba(0,0,0,0.13)';
    ctx.fillRect(0,0,C.width,C.height);
    for(var i=0;i<cols;i++){
      var y=drops[i]*CS, x=i*CS+CS/2, c=colors[i];
      ctx.beginPath(); ctx.arc(x,y,2.8,0,6.28);
      ctx.fillStyle='rgba('+c+',0.9)'; ctx.fill();
      ctx.beginPath(); ctx.arc(x,y-CS,2,0,6.28);
      ctx.fillStyle='rgba('+c+',0.45)'; ctx.fill();
      ctx.beginPath(); ctx.arc(x,y-CS*2,1.4,0,6.28);
      ctx.fillStyle='rgba('+c+',0.2)'; ctx.fill();
      ctx.beginPath(); ctx.arc(x,y-CS*3,1,0,6.28);
      ctx.fillStyle='rgba('+c+',0.08)'; ctx.fill();
      drops[i]+=speeds[i];
      if(drops[i]*CS>C.height+CS*4 && Math.random()>0.97) drops[i]=Math.random()*-8;
    }
  }
  init();
  window.addEventListener('resize',init);
  requestAnimationFrame(draw);
})();
</script>
```

with:

```html
<!-- Candlestick background (shared module) -->
<canvas id="mi-bg-canvas" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.55"></canvas>
<script>
document.addEventListener('DOMContentLoaded', function() {
  initMaverickCandles({ canvasId: 'mi-bg-canvas', sizeToWindow: true });
});
</script>
```

- [ ] **Step 4: Add stat-pill CSS**

Add this block anywhere inside the existing `<style>` (e.g. right after the `.about-hero-inner` rule):

```css
    .about-stats { display: flex; gap: 1.25rem; justify-content: center; margin-top: 1.75rem; flex-wrap: wrap; }
    .about-stats .stat-pill { background: rgba(255,255,255,.1); border: 1px solid rgba(255,255,255,.15); border-radius: 12px; padding: .75rem 1.25rem; text-align: center; }
    .about-stats .stat-pill .val { font-size: 1.4rem; font-weight: 800; color: var(--white); font-family: var(--font-mono); }
    .about-stats .stat-pill .lbl { font-size: .7rem; color: rgba(255,255,255,.65); text-transform: uppercase; letter-spacing: .08em; }
    .about-stats .stat-pill.pill-pop { animation: pillPop .35s ease-out; }
    @keyframes pillPop {
      0%   { transform: scale(1);    box-shadow: 0 0 0 rgba(249,115,22,0); }
      40%  { transform: scale(1.06); box-shadow: 0 0 18px rgba(249,115,22,.55); }
      100% { transform: scale(1);    box-shadow: 0 0 0 rgba(249,115,22,0); }
    }
```

- [ ] **Step 5: Replace the bio paragraph and add the stat-pill markup + counter script**

Replace (`about.html:293-295`, exact current content):

```html
    <p style="font-size:.95rem;color:rgba(255,255,255,.75);max-width:580px;margin:1.25rem auto 0;line-height:1.75;">
      I'm a CFA Charterholder, ERP &amp; SCR certified risk professional, and a retail investor who believes every Indian deserves access to clear, unbiased financial guidance. Over 5+ years of investing I've built a ₹66L+ portfolio tracking 30+ funds — earning a 13.6% XIRR. Maverick Investor is my attempt to share what I've learned: no jargon, no commissions, just honest advice tailored for the Indian market.
    </p>
```

with:

```html
    <p style="font-size:.95rem;color:rgba(255,255,255,.75);max-width:580px;margin:1.25rem auto 0;line-height:1.75;">
      I'm a CFA Charterholder, ERP &amp; SCR certified risk professional, and a retail investor who believes every Indian deserves access to clear, unbiased financial guidance. Maverick Investor is my attempt to share what I've learned: no jargon, no commissions, just honest advice tailored for the Indian market.
    </p>
    <div class="about-stats">
      <div class="stat-pill"><div class="val" data-count="66" data-prefix="₹" data-suffix="L+">₹0</div><div class="lbl">Portfolio</div></div>
      <div class="stat-pill"><div class="val" data-count="14" data-suffix="%">0</div><div class="lbl">XIRR</div></div>
      <div class="stat-pill"><div class="val" data-count="5" data-suffix="+">0</div><div class="lbl">Years</div></div>
      <div class="stat-pill"><div class="val" data-count="30" data-suffix="+">0</div><div class="lbl">Funds</div></div>
    </div>
    <script>
    document.addEventListener('DOMContentLoaded', function() {
      initMaverickCounters('.about-stats .val[data-count]');
    });
    </script>
```

- [ ] **Step 6: Visual verification**

Reload, `preview_snapshot` to confirm the bio paragraph reads correctly (no leftover embedded numbers, no broken `</p>` nesting), confirm 4 stat pills render below it and count up to `₹66L+`, `14%`, `5+`, `30+` with the same pop flourish as the homepage, and confirm the background canvas now shows drifting candlesticks instead of falling dots.

- [ ] **Step 7: Commit**

```bash
git add about.html
git commit -m "about.html: candlestick background, mono stat pills for founder track record"
```

---

### Task 6: `mf-advisor.html` — candlestick swap + glassmorphism goal cards

**Files:**
- Modify: `mf-advisor.html:297-335` (matrix canvas script → shared module call)
- Modify: `mf-advisor.html:61` (`.goal-card` base rule — glass upgrade)
- Modify: `mf-advisor.html` head (add shared script tag)

**Interfaces:**
- Consumes: `window.initMaverickCandles` (Task 4).

- [ ] **Step 1: Add the shared script tag**

Add to `mf-advisor.html`'s `<head>` (near its other `<script>`/`<link>` tags):

```html
  <script src="assets/candles.js" defer></script>
```

- [ ] **Step 2: Replace the matrix canvas script**

Replace (`mf-advisor.html:297-335`, same matrix IIFE shown in Task 5 Step 3 with identical content) with:

```html
<!-- Candlestick background (shared module) -->
<canvas id="mi-bg-canvas" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.55"></canvas>
<script>
document.addEventListener('DOMContentLoaded', function() {
  initMaverickCandles({ canvasId: 'mi-bg-canvas', sizeToWindow: true });
});
</script>
```

- [ ] **Step 3: Glass-ify the goal cards**

Replace (`mf-advisor.html:61`):

```css
.goal-card{cursor:pointer;background:rgba(20,30,50,.7);border:2px solid rgba(255,255,255,.1);border-radius:var(--radius);padding:1.2rem 1rem;text-align:center;transition:all .25s;backdrop-filter:blur(12px);box-shadow:0 4px 24px rgba(0,0,0,.3);}
```

with:

```css
.goal-card{cursor:pointer;background:linear-gradient(rgba(20,30,50,.7),rgba(20,30,50,.7)) padding-box,conic-gradient(from 180deg,rgba(249,115,22,.5),rgba(255,255,255,0) 35%,rgba(74,222,128,.4) 65%,rgba(255,255,255,0) 100%) border-box;border:2px solid transparent;border-radius:var(--radius);padding:1.2rem 1rem;text-align:center;transition:all .25s;backdrop-filter:blur(16px) saturate(160%);box-shadow:0 4px 24px rgba(0,0,0,.3), inset 0 1px 0 rgba(255,255,255,.08);}
```

(`.goal-card:hover` at line 70 and `.goal-card-selected` at line 69 are untouched — they set an opaque `border-color`/`background` on top, which is the desired hover/selected feedback and will still render correctly over the new gradient-border base.)

- [ ] **Step 4: Visual verification**

Reload `mf-advisor.html`, `preview_screenshot` step 0 (goal selection screen), confirm the background now shows candlesticks instead of falling dots, confirm the 6 goal cards show a visible soft gradient border and slightly stronger blur, and `preview_click` one card to confirm the hover/selected orange highlight still works.

- [ ] **Step 5: Commit**

```bash
git add mf-advisor.html
git commit -m "mf-advisor.html: candlestick background + glassmorphism goal cards"
```

---

### Task 7: `learn.html` — candlestick swap only

**Files:**
- Modify: `learn.html:1619-1656` (matrix canvas script → shared module call; confirm exact end line when editing — block ends at the closing `</script>` following the `requestAnimationFrame(draw);` line)
- Modify: `learn.html` head (add shared script tag)

- [ ] **Step 1: Add the shared script tag to `<head>`**

```html
  <script src="assets/candles.js" defer></script>
```

- [ ] **Step 2: Replace the matrix canvas script**

Replace the full `<!-- Matrix particle background -->` through `</script>` block (identical content to Task 5 Step 3) with:

```html
<!-- Candlestick background (shared module) -->
<canvas id="mi-bg-canvas" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.55"></canvas>
<script>
document.addEventListener('DOMContentLoaded', function() {
  initMaverickCandles({ canvasId: 'mi-bg-canvas', sizeToWindow: true });
});
</script>
```

- [ ] **Step 3: Visual verification**

Reload `learn.html`, `preview_screenshot`, confirm candlesticks render behind the page content and no console errors.

- [ ] **Step 4: Commit**

```bash
git add learn.html
git commit -m "learn.html: swap matrix background for shared candlestick module"
```

---

### Task 8: `tools.html` — candlestick swap only

**Files:**
- Modify: `tools.html:1624-~1661` (matrix canvas script → shared module call, same identical block as the others)
- Modify: `tools.html` head (add shared script tag)

- [ ] **Step 1: Add the shared script tag to `<head>`**

```html
  <script src="assets/candles.js" defer></script>
```

- [ ] **Step 2: Replace the matrix canvas script**

Same replacement as Task 7 Step 2 (identical source block, identical target snippet).

- [ ] **Step 3: Visual verification**

Reload `tools.html`, `preview_screenshot`, confirm candlesticks render, no console errors.

- [ ] **Step 4: Commit**

```bash
git add tools.html
git commit -m "tools.html: swap matrix background for shared candlestick module"
```

---

### Task 9: `stock-screener.html` — candlestick swap only

**Files:**
- Modify: `stock-screener.html:122-138` (matrix canvas script → shared module call — this copy is minified/single-line but functionally identical to the others)
- Modify: `stock-screener.html` head (add shared script tag)

- [ ] **Step 1: Add the shared script tag to `<head>`**

```html
  <script src="assets/candles.js" defer></script>
```

- [ ] **Step 2: Replace the matrix canvas script**

Replace (`stock-screener.html:122-138`):

```html
<canvas id="mi-bg-canvas" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.55"></canvas>
<script>
(function(){var C=document.getElementById('mi-bg-canvas');var ctx=C.getContext('2d');var CS=22,cols,drops,speeds,colors;
function init(){C.width=window.innerWidth;C.height=window.innerHeight;cols=Math.floor(C.width/CS);
drops=Array.from({length:cols},function(){return Math.random()*(-(C.height/CS));});
speeds=Array.from({length:cols},function(){return 0.25+Math.random()*0.55;});
colors=Array.from({length:cols},function(){return Math.random()>0.82?'59,130,246':'249,115,22';});}
var last=0;function draw(ts){requestAnimationFrame(draw);if(ts-last<28)return;last=ts;
ctx.fillStyle='rgba(0,0,0,0.13)';ctx.fillRect(0,0,C.width,C.height);
for(var i=0;i<cols;i++){var y=drops[i]*CS,x=i*CS+CS/2,c=colors[i];
ctx.beginPath();ctx.arc(x,y,2.8,0,6.28);ctx.fillStyle='rgba('+c+',0.9)';ctx.fill();
ctx.beginPath();ctx.arc(x,y-CS,2,0,6.28);ctx.fillStyle='rgba('+c+',0.45)';ctx.fill();
ctx.beginPath();ctx.arc(x,y-CS*2,1.4,0,6.28);ctx.fillStyle='rgba('+c+',0.2)';ctx.fill();
ctx.beginPath();ctx.arc(x,y-CS*3,1,0,6.28);ctx.fillStyle='rgba('+c+',0.08)';ctx.fill();
drops[i]+=speeds[i];if(drops[i]*CS>C.height+CS*4&&Math.random()>0.97)drops[i]=Math.random()*-8;}}
init();window.addEventListener('resize',init);requestAnimationFrame(draw);})();
</script>
```

with:

```html
<canvas id="mi-bg-canvas" style="position:fixed;top:0;left:0;width:100%;height:100%;z-index:0;pointer-events:none;opacity:.55"></canvas>
<script>
document.addEventListener('DOMContentLoaded', function() {
  initMaverickCandles({ canvasId: 'mi-bg-canvas', sizeToWindow: true });
});
</script>
```

- [ ] **Step 3: Visual verification**

Reload `stock-screener.html`, `preview_screenshot`, confirm candlesticks render, no console errors, table/screener functionality untouched.

- [ ] **Step 4: Commit**

```bash
git add stock-screener.html
git commit -m "stock-screener.html: swap matrix background for shared candlestick module"
```
