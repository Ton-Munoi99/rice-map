# Rice Map Handoff

Last updated: 2026-07-09 by Claude Code

## Log

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

The 14 workflows share boilerplate but differ in schedules, Python versions,
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
