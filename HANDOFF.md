# Rice Map Handoff

Last updated: 2026-07-15 by Claude Code

## Log

- 2026-07-15 (Claude): Restored scripted regeneration of the official 2568 rice data,
  closing the reproducibility gap found during the pipeline trace below. Recovered
  `data/oae_extracted.json` (committed OAE 2568 Table 1.4 extraction) from commit
  85dd87e, and restored portable `scripts/extract_oae.py` (PDF → json refresh) +
  `scripts/update_rice_data.py` (json → rice-data.{csv,js}, reads authoritative csv,
  writes both, LF). Verified: update_rice_data.py reproduces the committed csv
  byte-for-byte and the 2568 js rows exactly; it also synced js to csv (cleared 60
  stale estimated 2569 price cells). Full ordered pipeline now documented in AGENTS.md.
- 2026-07-15 (Claude): Ponytail audit cleanup + rice-data pipeline trace.
  Removed dead code: `extract_pdf_prices.py` (orphan — its `process-pdf-prices.yml`
  never existed; prices come from fetch_miller_prices/fetch_oae_prices) and the dead
  `data/prices/` PDF-drop folder; `fetch_rice_mills_api.py` (abandoned DIT-API path,
  mills reverted to Excel via build_rice_mills.py). Then traced the two "duplicate"
  rice-data builders — they are NOT duplicates: `build_rice_dataset.py` is the real
  base builder (emits source=oae_stats_table_1_4, present in live data), while
  `build_oae_rice_data.py`'s main() is superseded (source=oae_pdf_direct, absent) but
  it is a live parse-helper dependency of `build_naprang_data.py` — do not delete it.
  Also found the official 2568 rows (oae_stats_2568_table_1_4) were added by a MANUAL
  commit (85dd87e) with no generating script, so no builder can fully regenerate
  rice-data.csv/js — running the base builder erases 2568. Documented all of this in
  AGENTS.md + DATA_SOURCES.md. Also fixed a UX issue: selecting a naprang layer while
  Jasmine is active now auto-switches to White Rice (jasmine has no second crop).
- 2026-07-14 (Claude): Alert scoreboard — `scripts/score_alerts.py` measures 7-day
  rain-forecast accuracy against GSMaP satellite actual, matched by exact date
  window (forecast for D..D+6 scored ~7 days later when GSMaP covers the same
  dates; unmatched = never scored, no guessing). Runs as a step in
  update-rain.yml (forecast+gsmap fresh in one run); writes
  `data/alert-scoreboard.json` (rolling over last 60 windows). Sidebar card
  🎯 shows heavy-alert precision/recall, any-rain accuracy, MAE/bias; hidden
  until the first window matures (~7 days, rolling=null). Verified: confusion/
  rollup unit math, end-to-end scoring (fc=actual → MAE 0, precision 1.0),
  idempotent re-run, card shows/hides correctly, null-precision edge → "—".
- 2026-07-13 (Claude): URL hash state — the app now reads `#layer=…&rice=…&year=…&reg=…&sel=…`
  on load (`applyHash`, whitelist-validated against layerMeta/RICE_TYPES/REG_KEYS/allEN)
  and writes it back on every state change (`syncHash` in rerender + selectProvince,
  `history.replaceState`, defaults omitted so the base URL stays clean). Shareable
  deep links, e.g. `#layer=forecast&sel=Trat`. Verified in Playwright: inbound apply,
  click→hash update, garbage hash rejected without errors.
- 2026-07-10 (Claude): Added data-freshness monitor. `scripts/check_data_freshness.py`
  compares each data file's last git-commit age against a per-file threshold
  (~3x its cron cadence); `check-data-freshness.yml` runs it daily at 12:00 UTC.
  A stale file fails the run, and GitHub's failure email is the alert — no
  issue-management code. 19 files monitored; manual/static files excluded.
  Verified: live run all-fresh (exit 0) and simulated-stale exits 1.
- 2026-07-09 (Claude): Applied /ponytail-review cuts, all behavior-preserving:
  stdlib `statistics.quantiles` replaces the hand-rolled percentile in
  `fetch_rain_forecast.py` (proved identical on 4,500 random cases, p85/90/95,
  2-6 points); dropped the unread `n_pts` field from rain-forecast output;
  deleted a dead no-op ternary in `fetch_rice_news.py`; removed the constant
  per-item `icon` field (renderer hardcodes it); inlined the never-passed
  `grid` param in `load_sample_points` (sample points verified byte-identical
  to main). Live rice-news run + JS syntax + py_compile all green.
- 2026-07-09 (Claude): Corrected stale facts in `AGENTS.md` — it had been copied
  from an older `CLAUDE.md` and no longer matched the repo. Fixed: line count
  (~3,800 → ~8,200), workflow count (8 → 14), the "no นาปรัง data" constraint
  (naprang-data.js exists and drives the naprang/naprangArea layers), the JSON
  data-file list (23 files), the `thailand-data.js` global (`THAILAND_GEO`, not
  `THAILAND_SVG_DATA`), and added the current 18-layer list. Docs-only, no code.

## Read First

- `AGENTS.md` is the shared repository guide for both Codex and Claude Code.
- This file is the shared work log and queue.
- Run `git status --short` before editing. Do not overwrite another agent's uncommitted changes.
- Complete and verify one queue item at a time. Commit it before switching agents.
- Update this file after each completed item or important decision.

## Cleanup Checkpoint

The following cleanup was completed as one checkpoint:

- Removed obsolete root scripts: `extract_oae.py` and `update_rice_data.py`.
- Removed `SESSION_LOG.md`; this file replaces it as a concise operational log.
- Removed tracked scratch and research artifacts already covered by `.gitignore`.
- Replaced the obfuscated credit re-injection and `MutationObserver` in `index.html`
  and duplicate `body::after` content with one static `.credit` element.
- Consolidated five duplicate optional-data loaders into `fetchLayerData` while
  preserving each layer's refresh behavior.
- Removed commented-out hidden-layer buttons. The supporting data code remains
  intentionally because province detail and district drill-down use it.
- Replaced the duplicated 102-line `CLAUDE.md` with a pointer to shared instructions.
- Added `HANDOFF.md`.
- Added `AGENTS.md` as the shared repository guide.

Verification completed:

```text
node scripts/check_syntax.js  -> JS syntax OK
git diff --check             -> passed
GET /index.html              -> HTTP 200 on local server
Playwright layer smoke test  -> biomass, water level, rain stations, soil moisture passed
Browser console              -> no errors
Province detail              -> Nakhon Sawan cards and async data rendered
CSV export                   -> rice-map-white-2567-all.csv downloaded
Mobile viewport              -> 390x844 screenshot checked; no overlap or overflow found
Python compile               -> all scripts passed compileall
Workflow YAML                -> all 14 files parsed successfully
```

Local preview started at `http://localhost:8888`.

## High-Risk Decisions

These items were traced on 2026-07-09. Do not reopen them as cleanup work without
new requirements or measurements.

### Hidden map layers: keep supporting code

The buttons for `profit`, `rainfall`, `drought`, `ndvi`, and `rain` are intentionally
absent. Their commented HTML was removed. Do not broadly delete their JavaScript:
weather and NDVI data are also consumed by visible province details and district
drill-down. A safe removal requires a product decision to retire those visible cards.

### Data loaders: consolidated

Biomass, water-level, rain-station, soil-moisture, and disease data now use
`fetchLayerData`. `fetchDamData` remains separate because it refreshes map and detail
state even when the request fails. Browser smoke tests passed for the selectable
loader-backed layers.

### GitHub Actions: keep separate

The 17 workflows share one commit step via ./.github/actions/commit-data, and differ in schedules, Python versions,
dependencies, GEE secrets, scripts, generated files, and commit behavior. A reusable
workflow would centralize failure risk and still need most values as parameters.
Keep them separate unless CI maintenance becomes a measured problem.

### Rice CSV and JS: keep both

`rice-data.csv` is the runtime primary source and supports CSV import/export.
`rice-data.js` is the static fallback and is consumed by trend and EVI validation
scripts. Both are generated together. The duplication is deliberate resilience, not
an unresolved source-of-truth problem.

### Station snapshots: keep full datasets

The water-level and rain-station layers render individual station points, and the UI
supports showing all rain stations. Do not replace these files with province
aggregates. Field trimming may be reconsidered only after payload/load-time
measurements and a schema-level consumer test exist.

## Deferred Decisions

- Keep the single-file `index.html` architecture unless a concrete maintenance or
  performance problem justifies a build system.
- Do not add npm, a bundler, or a framework for cleanup alone.
- Do not remove visible data cards merely because their map-layer buttons are hidden.

## Handoff Protocol

Before switching agents:

1. Run `node scripts/check_syntax.js` and `git diff --check`.
2. Record browser checks and any known failure here.
3. Commit the completed queue item with a narrow message.
4. Leave unrelated generated-data changes out of that commit.
5. Tell the next agent: "Read AGENTS.md and HANDOFF.md, then continue the first
   unfinished queue item."
