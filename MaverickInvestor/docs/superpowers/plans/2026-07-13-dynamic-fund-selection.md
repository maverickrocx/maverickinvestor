# Dynamic Fund Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the MF Advisor's hard-coded fund table with a quarterly-curated, dynamically ranked fund set (plus a Gold category and passive index candidates), precomputed weekly into a JSON the website and app read.

**Architecture:** A Python ranking job reads `candidates.json`, fetches live NAV + benchmark data from mfapi.in, computes Tier-A metrics, ranks each category by a weighted-percentile composite, and writes `fund-rankings.json`. A weekly GitHub Actions job regenerates it. `mf-advisor.html` and the app's `AdvisorScreen` read that file and apply the pick rule (#1 always, #2 when the category weight >20%). The persona-logic verification Excel is regenerated from the finalized logic.

**Tech Stack:** Python 3 (stdlib only: urllib, json, statistics, math) for the job and Excel (openpyxl); vanilla JS in `mf-advisor.html`; Kotlin/Compose for the app; GitHub Actions for scheduling.

## Global Constraints

- Scheme codes must be Direct-Growth and validated each run (scheme name contains fund + "Direct" + "Growth"); mismatch → exclude + log.
- Eligibility: active funds ≥5y history, passive index funds ≥3y; exclude merged/closed/dividend plans.
- NAV de-spike: a single point jumping >15% and reverting >15% next day → replace with neighbour mean.
- Pick rule: allocation weight ≤20% → fund #1 only; >20% → #1 and #2 (equal split); #3 is reserve.
- Three weight profiles (percentiles sum to 100): Active-Equity (LC/FC/MC/SC), Debt, Tracker (Gold). Exact weights per the spec table.
- Gold% by [effective persona × horizon] per the spec table; 0% for Short horizon; funded by scaling the 5-way mix to (100−Gold)%.
- Resilience: never overwrite `fund-rankings.json` with partial data; keep last good copy on any failure.
- Reference scripts already proven in scratchpad: `rank_funds.py`, `build_ranking_excel.py`, `build_advisor_excel.py`.

---

### Task 1: Curated candidates.json

**Files:**
- Create: `MaverickInvestor/data/candidates.json`

**Interfaces:**
- Produces: the maintained input consumed by the ranking job. Shape:
  `{ "reviewedOn":"2026-07-13", "categories": { "largeCap": { "benchmarkSchemeCode":120716, "profile":"activeEquity", "funds":[ {"label":"Mirae Asset Large Cap","schemeCode":118825,"ter":0.54,"aum":38420,"isIndex":false}, … ] }, "gold": { "benchmarkSchemeCode":null, "profile":"tracker", "funds":[…] }, "debt": { "benchmarkSchemeCode":null, "profile":"debt", "funds":[…] } } }`

- [ ] **Step 1: Create the file** with the six categories (largeCap, flexiCap, midCap, smallCap, gold, debt), using the verified codes from the approved preview. Seed each equity category from the preview shortlist and expand toward ~10 where confident; carry `ter`, `aum`, `isIndex`. Benchmarks: largeCap 120716 (UTI Nifty 50), flexiCap 152731 (Axis Nifty 500), midCap 147622 (Motilal Nifty Midcap 150), smallCap 148519 (Nippon Nifty Smallcap 250); gold/debt `null`. Include the passive candidates (Axis Nifty 100 Index 147666 with `isIndex:true` in largeCap; Axis Nifty 500 Index 152731 `isIndex:true` in flexiCap). Gold funds: Nippon Gold Savings 118663, SBI Gold 119788, Axis Gold 120473, Kotak Gold 119781. Debt: HDFC Short Term 119016, ICICI Corp Bond 120692, HDFC Corp Bond 118987, ABSL Corp Bond 119533, Kotak Corp Bond 133791, Axis Corp Bond 141588.

- [ ] **Step 2: Validate JSON** — Run: `python -c "import json;json.load(open('MaverickInvestor/data/candidates.json'))"` — Expected: no output (valid).

- [ ] **Step 3: Commit** — `git add MaverickInvestor/data/candidates.json && git commit -m "Add curated fund candidates.json for dynamic selection"`

---

### Task 2: Ranking job (tools/rank_funds.py)

**Files:**
- Create: `tools/rank_funds.py` (port from scratchpad `rank_funds.py` + `build_ranking_excel.py` scoring)
- Test: `tools/test_rank_funds.py`

**Interfaces:**
- Consumes: `candidates.json` (Task 1).
- Produces: `write_rankings(candidates_path, out_path)` → writes `fund-rankings.json` shaped `{ "asOf":"YYYY-MM-DD", "categories": { "largeCap": { "benchmark":"Nifty 50", "ranked":[ {"rank":1,"label":…,"schemeCode":…,"composite":71.8,"metrics":{"cagr5":…,"sortino":…,"maxdd":…,"ter":…,"aum":…}} ] } } }`. Also exposes pure functions `metrics(series, bench)`, `despike(series)`, `composite(funds, profile)` for tests.

- [ ] **Step 1: Write failing tests** in `tools/test_rank_funds.py`:

```python
import rank_funds as rf
def test_despike_removes_single_glitch():
    s = [(i, 100.0) for i in range(10)]
    s[5] = (5, 55.0)                      # one corrupt dip
    out = rf.despike(list(s))
    assert abs(out[5][1] - 100.0) < 1e-6
def test_cagr_basic():
    import datetime
    s = [(datetime.date(2021,1,1),100.0),(datetime.date(2026,1,1),200.0)]
    assert abs(rf.cagr(s,5) - (2**0.2 - 1)) < 1e-6
def test_pick_rule():
    assert rf.funds_used(20) == 1        # <=20% -> 1 fund
    assert rf.funds_used(21) == 2        # >20%  -> 2 funds
```

- [ ] **Step 2: Run to verify fail** — `cd tools && python -m pytest test_rank_funds.py -v` — Expected: FAIL (module/functions missing).

- [ ] **Step 3: Implement `tools/rank_funds.py`** by porting scratchpad `rank_funds.py` (fetch, `navseries` with de-spike as `despike()`, `cagr`, `metrics` incl. IR guard) and the scoring from `build_ranking_excel.py` (`pct`, `aum_band`, `WEIGHTS_*`, composite). Read from `candidates.json` instead of the hard-coded dict; select the weight profile from each category's `profile`. Add `funds_used(weight): return 2 if weight>20 else 1`. Add the **overlap guard** (drop #2 if monthly-return correlation to #1 >0.98, promote next). Write `write_rankings()` that assembles the output schema and writes atomically to a temp file then renames.

- [ ] **Step 4: Run tests** — `cd tools && python -m pytest test_rank_funds.py -v` — Expected: PASS.

- [ ] **Step 5: Commit** — `git add tools/rank_funds.py tools/test_rank_funds.py && git commit -m "Add dynamic fund ranking job"`

---

### Task 3: Generate & commit initial fund-rankings.json

**Files:**
- Create (generated): `MaverickInvestor/data/fund-rankings.json`

- [ ] **Step 1: Run the job** — `cd tools && python -c "import rank_funds; rank_funds.write_rankings('../MaverickInvestor/data/candidates.json','../MaverickInvestor/data/fund-rankings.json')"` — Expected: prints per-category top-3; file written.

- [ ] **Step 2: Sanity-check output** — `python -c "import json;d=json.load(open('MaverickInvestor/data/fund-rankings.json'));assert set(d['categories'])>= {'largeCap','flexiCap','midCap','smallCap','gold','debt'};print(d['asOf'], {k:v['ranked'][0]['label'] for k,v in d['categories'].items()})"` — Expected: prints the #1 fund per category matching the approved preview (Mirae, PPFAS, Edelweiss Mid, Axis Small, SBI Gold, ICICI Corp Bond).

- [ ] **Step 3: Commit** — `git add MaverickInvestor/data/fund-rankings.json && git commit -m "Generate initial fund-rankings.json"`

---

### Task 4: Weekly GitHub Actions job

**Files:**
- Create: `.github/workflows/rank-funds.yml`

- [ ] **Step 1: Create the workflow:**

```yaml
name: Refresh fund rankings
on:
  schedule: [{ cron: "0 20 * * 0" }]   # Sundays 20:00 UTC
  workflow_dispatch:
permissions:
  contents: write
jobs:
  rank:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - name: Regenerate rankings
        run: |
          cd tools
          python -c "import rank_funds; rank_funds.write_rankings('../MaverickInvestor/data/candidates.json','../MaverickInvestor/data/fund-rankings.json')"
      - name: Commit if changed
        run: |
          git config user.name "maverick-bot"
          git config user.email "noreply@maverickinvestor.in"
          git add MaverickInvestor/data/fund-rankings.json
          git diff --staged --quiet || git commit -m "chore: weekly fund-rankings refresh"
          git push
```

- [ ] **Step 2: Verify YAML** — Run: `python -c "import yaml,sys;yaml.safe_load(open('.github/workflows/rank-funds.yml'))" || echo "install pyyaml or eyeball"` — Expected: no error (or eyeball the indentation).

- [ ] **Step 3: Commit** — `git add .github/workflows/rank-funds.yml && git commit -m "Add weekly fund-rankings workflow"`

- [ ] **Step 4: Note for owner:** the job must write inside the `MaverickInvestor/` folder so the existing Pages deploy workflow republishes it. The rankings refresh commit triggers that deploy automatically.

---

### Task 5: mf-advisor.html — add Gold category to allocation

**Files:**
- Modify: `MaverickInvestor/mf-advisor.html` (the `ALLOC` matrix, `CAT_KEYS`, `CAT_LABELS`, `getAllocation`)

**Interfaces:**
- Consumes: existing `getAllocation(effKey, hKey)` returning a 5-array `[lc,fc,mc,sc,debt]`.
- Produces: a 6-array `[lc,fc,mc,sc,gold,debt]`; `CAT_KEYS=['largeCap','flexiCap','midCap','smallCap','gold','debt']`.

- [ ] **Step 1: Add Gold weight table and insertion** — after the existing `ALLOC`/guardrail logic in `getAllocation`, insert:

```javascript
// Gold sleeve % by [effKey][hKey]; 0 for short horizon
const GOLD = {
  guardian:{s:0,m:5,l:5,xl:5}, preserver:{s:0,m:5,l:7,xl:7},
  balancer:{s:0,m:5,l:7,xl:10}, grower:{s:0,m:5,l:7,xl:7}, maverick:{s:0,m:0,l:5,xl:5}
};
function insertGold(base5, effKey, hKey){    // base5 = [lc,fc,mc,sc,debt]
  const g = GOLD[effKey][hKey];
  if(!g) return [base5[0],base5[1],base5[2],base5[3],0,base5[4]];
  const scale = (100-g)/100;
  const s = base5.map(v=>v*scale);
  return [s[0],s[1],s[2],s[3],g,s[4]];       // [lc,fc,mc,sc,gold,debt]
}
```

Call `insertGold(...)` at the end of `getAllocation` (before returning), and update `CAT_KEYS=['largeCap','flexiCap','midCap','smallCap','gold','debt']`, `CAT_LABELS=['Large Cap','Flexi Cap','Mid Cap','Small Cap','Gold','Debt']`, `CAT_CSS` (+`c-gold`), and any code indexing category 4 as debt (debt is now index 5).

- [ ] **Step 2: Verify in browser** — start preview, open `mf-advisor.html`, run a plan for a Long-horizon Balancer; in console check the allocation array has 6 entries summing to 100 with a non-zero Gold. Expected: e.g. Gold ≈ 7%.

- [ ] **Step 3: Commit** — `git add MaverickInvestor/mf-advisor.html && git commit -m "Add Gold category to advisor allocation"`

---

### Task 6: mf-advisor.html — read fund-rankings.json + pick rule

**Files:**
- Modify: `MaverickInvestor/mf-advisor.html` (`FUND_DB`, `buildFundList`, `runCalculation`, results table)

**Interfaces:**
- Consumes: `MaverickInvestor/data/fund-rankings.json` (Task 3); `getAllocation` 6-array (Task 5).
- Produces: `S.funds` built from ranked lists via the pick rule.

- [ ] **Step 1: Load rankings** — near the top of the script, add:

```javascript
let RANKINGS = null;
async function loadRankings(){
  try { RANKINGS = await (await fetch('data/fund-rankings.json',{cache:'no-store'})).json(); }
  catch(e){ RANKINGS = null; }   // buildFundList falls back to bundled default
}
```
Call `await loadRankings()` at the start of `runCalculation()`.

- [ ] **Step 2: Rewrite `buildFundList`** to pick from rankings with the pick rule:

```javascript
function buildFundList(allocation){    // allocation = [lc,fc,mc,sc,gold,debt]
  const keys = ['largeCap','flexiCap','midCap','smallCap','gold','debt'];
  const labels = ['Large Cap','Flexi Cap','Mid Cap','Small Cap','Gold','Debt'];
  const funds = [];
  keys.forEach((k,ci)=>{
    const pct = allocation[ci]; if(pct<=0) return;
    const ranked = (RANKINGS && RANKINGS.categories[k] && RANKINGS.categories[k].ranked) || [];
    const n = pct>20 ? 2 : 1;
    const pick = ranked.slice(0, n);
    if(pick.length===0) return;
    const per = pct/pick.length;
    pick.forEach(f=>funds.push({ name:f.label, code:f.schemeCode, cat:k, catLabel:labels[ci],
      alloc:per, xirr:null, sharpe:(f.metrics&&f.metrics.sharpe)||null,
      ter:(f.metrics&&f.metrics.ter)||null, aum:(f.metrics&&f.metrics.aum)||null }));
  });
  const total = funds.reduce((s,f)=>s+f.alloc,0);
  funds.forEach(f=>f.alloc=Math.round(f.alloc/total*100*10)/10);
  return funds;
}
```

Keep the old `FUND_DB` object as a minimal bundled fallback used only if `RANKINGS` is null (build the same structure from it). Update the results/portfolio table to read `f.ter`/`f.sharpe` (may be null → show "—").

- [ ] **Step 3: Verify in browser** — reload, run a plan; confirm the recommended portfolio now lists the ranked funds (Mirae, PPFAS, etc.), Gold appears for long horizons, and per-category funds = 1 or 2 by the >20% rule. Check console for no fetch errors.

- [ ] **Step 4: Commit** — `git add MaverickInvestor/mf-advisor.html && git commit -m "Advisor reads dynamic fund-rankings with pick rule"`

---

### Task 7: Verify website end-to-end and deploy

- [ ] **Step 1: Browser verification** — with the preview server, run three personas (short-horizon Guardian, long-horizon Balancer, long-horizon Maverick). Confirm: allocations sum to 100 with Gold where expected; funds match rankings; portfolio CAGR and SIP render; no console errors. Take a screenshot of one result.

- [ ] **Step 2: Push** — `git push origin main` — the Pages deploy workflow republishes the site with `data/fund-rankings.json`.

- [ ] **Step 3: Confirm live** — after the deploy completes, `curl -s https://maverickinvestor.in/data/fund-rankings.json | python -c "import sys,json;print(json.load(sys.stdin)['asOf'])"` — Expected: today's date.

---

### Task 8: App AdvisorScreen — Gold + rankings + pick rule

**Files:**
- Create: `MaverickInvestor-Compose/app/src/main/assets/fund-rankings.json` (copy of the generated file)
- Modify: `MaverickInvestor-Compose/app/src/main/java/com/maverickinvestor/app/ui/screens/AdvisorScreen.kt`

**Interfaces:**
- Consumes: bundled `fund-rankings.json` asset.
- Produces: advisor allocation + recommended funds mirroring the website (6 categories, pick rule).

- [ ] **Step 1: Bundle the asset** — copy `MaverickInvestor/data/fund-rankings.json` to the app `assets/` folder.

- [ ] **Step 2: Add a loader** reading the asset via `context.assets.open("fund-rankings.json")` into a data class `RankedFund(rank:Int,label:String,schemeCode:Int)` grouped by category; parse with the bundled Gson.

- [ ] **Step 3: Add Gold to the allocation** — extend the app's `profileFor(...)` allocation lists to include a Gold sleeve consistent with the website `GOLD` table, and render recommended funds by the ≤20/>20 pick rule from the loaded rankings.

- [ ] **Step 4: Build** — from `C:\Maverick Investor Android\MaverickInvestor-Compose` run the Gradle `assembleDebug` (as in prior builds). Expected: BUILD SUCCESSFUL.

- [ ] **Step 5: Commit + sync** — commit the app changes and copy the changed files to the OneDrive backup copy.

---

### Task 9: Regenerate the risk-persona Excel with finalized logic

**Files:**
- Modify: scratchpad `build_advisor_excel.py` → read the 6-category allocation (with Gold), draw funds from `fund-rankings.json` via the pick rule, and recompute portfolio CAGR from the ranked funds' live XIRR.
- Output: `Website & App/MF_Advisor_Persona_Logic.xlsx` (overwrite)

- [ ] **Step 1: Update the engine replica** in the builder: add the `GOLD` table and `insertGold`, extend categories to 6, and replace the static `catXIRR` with the ranked funds' metrics from `fund-rankings.json` (category CAGR = the picked funds' blended live return at the row's horizon).

- [ ] **Step 2: Regenerate** — `python build_advisor_excel.py` — Expected: "saved …MF_Advisor_Persona_Logic.xlsx", 80 personas, Gold present in allocations.

- [ ] **Step 3: Spot-check** — reload with openpyxl; confirm a Long-horizon Balancer row shows a Gold sleeve and its funds match the rankings; portfolio CAGR is populated.

- [ ] **Step 4: Share** — report the file path and the summary of what changed (Gold added, dynamic funds, pick rule, live CAGR).

---

## Self-Review

**Spec coverage:** candidates.json (T1) · ranking job with metrics/de-spike/overlap/weight-profiles (T2) · output JSON (T3) · weekly job + resilience via atomic write & "commit if changed" (T2/T4) · Gold matrix (T5) · read rankings + pick rule (T6) · website deploy (T7) · app (T8) · verification Excel (T9). Eligibility filters and scheme-code validation live in the ported job (T2). Global/sectoral remain out of scope. All spec sections map to a task.

**Placeholder scan:** none — code shown for each novel piece; ranking logic ports proven scratchpad scripts.

**Type consistency:** `getAllocation` → 6-array `[lc,fc,mc,sc,gold,debt]` used identically in T5/T6/T9; `CAT_KEYS` order fixed; pick rule `>20 → 2 else 1` identical in T2/T6/T8; ranking output schema in T2 matches readers in T6/T8/T9.
