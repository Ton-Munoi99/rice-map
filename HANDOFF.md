# Rice Map Handoff

Last updated: 2026-08-28 by Claude Code

## Log

- 2026-08-28 (Claude): Replaced the GISTDA satellite flood layer with a
  gauge-based one and removed GISTDA from the repo entirely. The layer key
  (`floodExtent`), global (`FLOOD_DATA`), and button position are unchanged;
  only its data source and semantics changed. Why: checked the layer against
  real news before trusting it and it failed three ways at once — the scene
  had been stale 3 days (upstream publishes no capture date at all, verified
  as an upstream property, not our bug), it entirely missed the Nan flash
  flood that was the biggest flood story of the week (flash floods recede
  before the next satellite pass), and it coloured Chaiyaphum as flooded while
  the news there reported a drought emergency. New pipeline:
  `scripts/fetch_flood_status.py` → `data/flood-status.json`, derived from the
  `water-level.json` we already fetch (no new API calls), chained as a step
  inside `update-water-level.yml` rather than its own cron — a separate job
  would read a staler station file than the one just committed. Colour comes
  only from measured gauges: severity 2 (flooding) = at least one gauge
  overbank; severity 1 (near overbank) = 3+ high gauges AND 30%+ of that
  province's gauges. News (Google News RSS, per-province) is attached as
  summary text and never drives colour — headlines lie (the Chaiyaphum drought
  story contains the words "flood"). Measured before shipping: 14/77 provinces
  flagged, and the Chao Phraya group it produced (Ayutthaya, Lopburi,
  Suphanburi, Samut Prakan, Bangkok) matches the DDPM warning list issued the
  day before. A first threshold attempt flagged 47/77 and was rejected as the
  same "warn everything" failure the rain alerts had just been fixed for.
  Two real bugs found and fixed during verification: ThaiWater calls Bangkok
  "Bangkok" while the map uses "Bangkok Metropolis" (it silently never
  coloured), and ThaiWater ships Myanmar stations that were being aggregated
  as a province — both fixed by keying on `PROVINCE_TH_EN` instead of the
  API's `province_en`. Also fixed a pre-existing cosmetic bug this inherited:
  word-valued formats (`alertLevel`, now `floodLevel`) had the unit appended,
  reading "เสี่ยงสูง ระดับ"; `embedsUnit()` now suppresses it for both.
  Removed: `scripts/fetch_gistda_flood.py`, `update-gistda-flood.yml`,
  `data/gistda-flood.json`, the GEE flooded-rice estimate (it could never be
  more accurate than the flood extent feeding it), and the now-unused
  `updatedVerbTh/En` layerMeta option. Layer count stays 21; workflows 19→
  actually unchanged in count for data purposes (18 write data). Verified
  in-browser through the real `setLayer` path: 14/14 provinces resolve to map
  polygons, tooltips/legend/rank/notes correct in both languages, other
  layers' legends unaffected, console clean. `python
  scripts/fetch_flood_status.py --selftest` covers the threshold logic.
- 2026-08-25 (Claude): Stale-check sweep. Fixed one real monitor gap —
  `tmd-forecast.json` (new file below) was never added to
  `scripts/check_data_freshness.py`'s `MAX_AGE_DAYS`, so a silently-broken TMD
  pipeline would never have gone red; added it (limit 1 day, matches its 6h
  cron). Also fixed three stale docs: `AGENTS.md`'s "Current layers (18)" list
  (missing `profit` and `tmdRain`, real count is 20; the "profit button is
  hidden" note was also wrong — it has had a button since the ponytail-audit
  below), `AGENTS.md`'s "17 workflows" (real: 19, 18 of which write data),
  `README.md`'s "~16 workflow" (→ 19), and `CHANGELOG.md`'s "Known issues"
  entry on absolute alert thresholds (said "intentionally not fixed" — it was
  fixed 20 Aug, see below). Everything else checked clean: no missing secrets,
  0/42 fallback literals contradict their data file, all 20 layer captions
  reset correctly when switching (`dataSourceNote` probed through the real
  `setLayer` path), no orphaned `layerMeta` entries.
- 2026-08-20/21 (Claude): Added the 20th layer, `tmdRain` — "48h detailed rain
  forecast" from the Thai Meteorological Department (TMD NWP API), 2km
  resolution, updated every 6h. Backend: `scripts/fetch_tmd_forecast.py`
  fetches per-region (6 calls, not per-province) since the docs disagreed with
  the actual response key twice during testing (real key is `WeatherForecasts`,
  matching neither of the two spellings TMD's own docs use — code now accepts
  all three). Frontend wired through the existing config-driven `valueFn`/
  `palette` merge block plus the ~17 spots that still need a per-layer case
  (dataSourceNote, tooltip, rankTitle, yearButtons override, etc. — same
  pattern as `gsmap`/`forecast`). Verified live in-browser: 77/77 provinces
  color, deep-link `#layer=tmdRain` loads cold, console clean, 19-layer
  baseline unaffected. Requires GitHub secret `TMD_API_TOKEN` (set by the repo
  owner, not by an agent). Explored district-level (649-843 amphoe) rain
  granularity as a follow-up per user request — built and tested
  `fetch_rain_forecast.py`/`fetch_rain_gsmap.py` district variants, but the
  user reverted it after comparing against a real flood event (Nan, 19 Aug):
  GSMaP satellite rain at district resolution still badly underestimated the
  reported peak (measured ~35-65mm/day vs ~200mm+ reported on the ground) —
  a satellite-resolution ceiling that administrative-boundary granularity
  doesn't fix. Nothing from that exploration is in the codebase.
- 2026-08-20 (Claude): Flood-alert threshold changed from a fixed 30/60/120mm
  national threshold to 0.5x/1.0x/2.0x of each province's own seasonal-normal
  weekly rainfall (`weather-forecast.json` ÷ 26 weeks), because the fixed
  threshold was flagging 67-84% of provinces simultaneously in wet season and
  was unfair across provinces (120mm = 1.2x Trat's normal week but 2.8x Nakhon
  Ratchasima's). See `province_flood_thresholds()` in
  `fetch_agri_warnings.py`. Same day: reverted the forecast-bias auto-
  calibration added 4 Aug — once enough score windows accumulated to measure
  it, it made both precision (25.4%→12.7%) and recall (87.3%→77.8%) worse
  simultaneously, not a normal trade-off. `load_forecast_bias()` now always
  returns 0.0; the scoring machinery (`score_alerts.py`) still runs in case
  there's ever enough data to reconsider.
- 2026-08-19/20 (Claude): Ponytail-audit cleanup across the repo (~-1,660
  lines net, several commits). Removed 4 orphaned layers with no button
  (`ndvi`/`rain`/`rainfall`/`drought` — the NDVI data pipeline was deleted
  entirely, ~288 lines) and all their dead render branches in `index.html`
  (36 leftover `if (layer === "ndvi") …` sites found across the detail card,
  rank title, source note, and district drill-down). Gave `profit` a button
  instead of deleting it (no equivalent layer replaces it). Consolidated
  duplicated mask/phenology code and tuning constants into `riceutils.py`
  (previously required editing two files in sync — a threshold change once
  slipped and only one file got it). Fixed a real bug found along the way:
  `eviPeriodLabel()` had a self-referential fallback line that caused
  infinite recursion whenever `rice-evi.json` hadn't finished loading yet —
  intermittently blanked the entire map (`RangeError: Maximum call stack`).

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
