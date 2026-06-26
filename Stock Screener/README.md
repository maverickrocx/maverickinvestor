# Mid/Smallcap Equity Screener — v3 (Mac Excel 365)

## Package contents
- **MidSmallcap_Screener.xlsx** — workbook: 8 sheets, 5,134 formulas (zero errors), full
  scoring engine (40% Fundamentals / 40% Technicals / 20% Macro), Mac setup on Setup sheet
- **ScreenerEngine.bas** — v3 VBA engine (import this file; do NOT open-and-paste it)
- **YahooFetch.applescript** — Mac curl helper (mandatory)

## Setup on Mac — clean install (10 min)
1. **Install the curl helper**: Finder → Shift+Cmd+G →
   `~/Library/Application Scripts/com.microsoft.Excel/`
   (create the folders with exactly those names if missing) → copy `YahooFetch.applescript` in.
   Already done previously? Skip — the script is unchanged.
2. **Open MidSmallcap_Screener.xlsx** → Tools > Macro > Visual Basic Editor
3. **Remove ALL old modules**: in the Project panel expand Modules; right-click each
   (ScreenerEngine, ScreenerEngine1, Module1…) → Remove → "No" to export. Folder must be empty.
4. **File > Import File…** → select `ScreenerEngine.bas`. It must appear as exactly
   `ScreenerEngine` (no number suffix — a suffix means an old copy survived step 3).
5. **Pre-flight**: Debug > Compile VBAProject — silence = clean.
6. **File > Save As** → format: Excel Macro-Enabled Workbook (**.xlsm**)
7. Tools > Macro > Macros… → **RefreshAllData** → Run.

## v3 rate-limit defenses (why this version behaves differently)
- Acquires a real Yahoo session cookie before requesting the auth crumb; crumb is strictly validated
- 1.5s between calls (~40/min) → full refresh ≈ 8–10 min; "Too Many Requests" responses
  trigger escalating backoff and an automatic switch to Yahoo's query2 backup host
- **Resumable**: rows stamped "OK" today are skipped on re-run — an interrupted refresh
  continues where it stopped, never repeats completed work
- Circuit breaker: 8 consecutive failures aborts with a clear cooldown message
- If the crumb can't be obtained, fundamentals are skipped (prices still fetch) and the
  completion dialog tells you to re-run later for the missing half

## IMPORTANT before first v3 run
If you attempted a refresh in the last hour, Yahoo's limiter may still be cooling down on
your IP — wait 45–60 minutes from the last attempt, then run. If you hit the circuit-breaker
message, wait the stated time and simply run again (resume handles the rest).

## Monthly manual inputs (Macro sheet, yellow cells)
RBI stance (rbi.org.in) · CPI (mospi.gov.in) · FII 3M flows (fpi.nsdl.co.in) · Global cues.
RISK-OFF regime (<40) docks smallcap composites 8 pts before verdicts apply.

## Maintenance
Re-download index constituent CSVs from nsearchives.nseindia.com after each March/September
rebalance and update the Tickers sheet. Screening tool ≠ investment advice — verify from
primary filings before acting.
