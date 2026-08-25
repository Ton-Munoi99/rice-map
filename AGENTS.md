# AGENTS.md

This file provides guidance to Codex (Codex.ai/code) when working with code in this repository.

## Local Development

```bash
# Run a local HTTP server (required — fetch() calls block on file://)
python -m http.server 8888
# Then open: http://localhost:8888
```

No build step, no npm, no bundler. The app is a single HTML file with two companion JS data files.

## Data Pipeline Scripts

All scripts live in `scripts/`. Run them from the repo root.

```bash
# Rebuild the rice production dataset (rice-data.csv/js) — run the stages in order:
python scripts/build_rice_dataset.py           # base 2565-2567 (OAE Table 1.4) + prices → csv+js
python scripts/update_rice_data.py             # apply official 2568 (data/oae_extracted.json) → csv+js
node   scripts/estimate_2568_2569.js           # fill remaining empty 2569 with trend estimates (js)
python scripts/clear_estimated_trend_prices.py # strip estimated prices + final csv/js sync

# Rebuild rice mills JSON from DIT Excel export
# Requires: thai_rice_mills_dit_YYYY-MM-DD.xlsx in repo root
python scripts/build_rice_mills.py

# Fetch live data manually (normally run by GitHub Actions)
python scripts/fetch_dam_water.py
python scripts/fetch_miller_prices.py
python scripts/fetch_trea_fob.py
python scripts/fetch_weather.py
python scripts/fetch_weather_forecast.py

# Real fertilizer prices — weekly refresh (Mon 18:00 BKK) → data/fertilizer-prices.json
# Scrapes maintained co-op/retailer price lists via Firecrawl (their prices are
# buried in page-builder markup, so raw urllib can't read them). Requires GitHub
# Actions secret FIRECRAWL_API_KEY. No-ops (keeps existing JSON) if unset.
# Govt provincial-commerce announcements are one-off posts → kept as STATIC_ROWS.
python scripts/fetch_fertilizer_prices.py
```

> **Notes on the rice-data pipeline:**
> - The official **2568** rows (`source: oae_stats_2568_table_1_4`) come from
>   `data/oae_extracted.json` (a committed artifact) applied by `update_rice_data.py`.
>   To refresh from a newer OAE edition, run `scripts/extract_oae.py` first — it needs
>   `สถิติการเกษตรของประเทศไทย ปี 2568.pdf` at repo root (or pass the path as argv[1]);
>   its page ranges are calibrated to the Thai-language edition.
> - `rice-data.csv` is authoritative (the app loads it first; `rice-data.js` is the
>   fallback). `clear_estimated_trend_prices.py` is the final sync stage: it clears
>   estimated prices and rewrites BOTH csv and js from one row set, so after a full
>   pipeline run the two files are always identical in content.
> - `build_oae_rice_data.py` is an **older, superseded** rice-data builder (`main()`
>   output is not in the live data). Do **not** run it to rebuild rice-data — but do
>   **not** delete it: `build_naprang_data.py` imports its parse helpers
>   (`extract_lines`, `clean_text`, `canon`, `SKIP_PREFIXES`) to build `naprang-data.js`.

## Architecture

### Single-page app — `index.html` (~8,300 lines)

Everything is in one file: CSS (top), HTML structure (middle), JS (bottom, inside `<script>`). No framework.

**Global state** — one object drives all rendering:
```js
let S = { rice: "white", layer: "production", year: "2567", reg: "all", sel: null };
```
Mutate `S` then call `rerender()`. Never read DOM state — always read from `S`.

**Key JS globals:**
| Name | Purpose |
|------|---------|
| `S` | Current UI state |
| `DATA` | `{[province_en]: {white: {[year]: {production, yield, area, price, ...}}, jasmine: {...}}}` |
| `DATA_META` | Dataset load status |
| `VIEW` | SVG camera state (zoom/pan) |
| `layerMeta` | Per-layer display config (`th`, `en`, `unit`, `summaryMode`) |
| `COST_BASE` | OAE production cost benchmarks — white: 6,100 ฿/rai, jasmine: 5,150 ฿/rai |
| `FERT_MOC` | MOC fertilizer price survey (8 formulas, min/max ฿/bag) |
| `FERT_DOA_RATES` | กรมการข้าว recommended rates (kg/rai) — 46-0-0: **10**, 16-20-0: **25**, 15-15-15: **25** |

**Adding a new layer:**
1. Add entry to `layerMeta` (th, en, unit, unitShort, summary, summaryMode) —
   set `noTimeseries: true` there if the layer has no yearly series (was a separate
   `LAYER_NO_TIMESERIES` list until 19 Aug 2569; folded into `layerMeta` so one edit covers it)
2. Add dispatch in `valueOf()` and `hasLayerValue()`
3. Add color palette case in `getPalette()`
4. Add format case in `fmtCompact()` if needed
5. Add layer button in HTML `#layerButtons`
6. Add badge/title/description/data-source-note cases in render functions
7. Add detail card case in `selectProvince()`

**Data flow:** `valueOf(en, rice, year, layer)` → dispatches to per-layer value functions → `rerender()` → SVG fill colors via `getPalette()` + `lerp()`.

**Current layers (20):** `production`, `yield`, `area`, `naprang`, `naprangArea`, `households`, `price`, `mills`, `profit`, `straw`, `biomass`, `dam`, `gsmap`, `forecast`, `tmdRain` (48h detailed forecast, TMD), `waterlevel`, `rainstation`, `alerts` (flood risk), `soilMoisture`, `riceEvi` — all 20 have a button; none are hidden. Sidebar also has non-layer cards: Weather Watch (`storm-alerts.json`) and Rice News (`rice-news.json`).

**Profit formula:** `(price ฿/ton × yield kg/rai / 1000) − COST_BASE[rice].oaeRaiCost`

**Fertilizer ratio card:** shown in province detail when `layer !== "profit"` — bags of urea (46-0-0) per ton of rice = `ricePricePerTon / ureaMidPrice`; bags needed per rai = `FERT_DOA_RATES["46-0-0"] / 50 = 0.2`.

### Companion data files

| File | Contents |
|------|---------|
| `rice-data.js` | Sets `window.RICE_DATA_ROWS` — ~4,000 rows, นาปี only (OAE Table 1.4), white + jasmine |
| `naprang-data.js` | Sets `window.NAPRANG_DATA_ROWS` — second-crop (นาปรัง) production + harvested area by province, 2565–2568 (OAE naprang PDFs) |
| `thailand-data.js` | Sets `window.THAILAND_GEO` — province polygons (GeoJSON) for all 77 provinces |

### JSON data files (`data/`)

Auto-updated by GitHub Actions crons (23 files total). Key ones:
- `prices-live.json` — Thai Rice Millers Association prices · `trea-fob.json` — TREA FOB export prices
- `dam-water.json` — RID dam levels · `water-level.json` + `rain-stations.json` — ThaiWater station snapshots
- `rain-daily.json` (Open-Meteo 7-day past) · `rain-forecast.json` (Open-Meteo 7-day forecast, multi-point p90) · `rain-gsmap.json` (JAXA GSMaP satellite) · `tmd-forecast.json` (TMD 48h hourly, 2km, every 6h)
- `agri-warnings.json` — synthesized flood/drought risk · `storm-alerts.json` — GDACS storms · `disease-risk.json`
- `soil-moisture.json` (NASA SMAP) · `rice-evi.json` (+ `-district`/`-validation`) — MODIS/GLAD satellite
- `rice-news.json` — Google News RSS (Thai rice news, 3×/day)
- `biomass-plants.json` — DEDE plant registry via GeoServer WFS (`fetch_biomass_plants.py`, yearly)
- Not auto-updated: `rice-mills.json` (built from DIT Excel), `districts-geo.json`, `oae_extracted.json`

### GitHub Actions

19 workflows in `.github/workflows/` (18 write data + `check-data-freshness.yml`, which only reads). The 18 data workflows commit directly to `main` through the shared
`./.github/actions/commit-data` composite action, which stages the listed paths, skips the
commit when nothing changed, and retries `git pull --rebase` + push up to 3× so concurrent
cron runs do not collide. Add new data workflows by calling that action rather than
re-inlining the git block.

## Important Constraints

- **`rice-data.js` = นาปีเท่านั้น** — main-season (นาปี) from OAE Table 1.4. Second-crop (นาปรัง) data lives separately in `naprang-data.js` and drives the `naprang` / `naprangArea` layers.
- **ข้าวขาว = OAE "ข้าวเจ้าอื่นๆ"** — excludes glutinous rice (ข้าวเหนียว) and Pathum Thani 1
- **Year keys are Thai Buddhist Era strings** — `"2567"` not `2567` (number)
- **Province keys are English names** — matching `NM` lookup map and `thailand-data.js`
- **Do not push to git without owner review** — confirm before any `git push`
- **Record every change in `CHANGELOG.md`** — owner's standing instruction. Any change that
  alters behaviour, data, or documentation goes in the current month's section under
  เพิ่ม / เปลี่ยนแปลง / แก้ไข / ลบออก, in Thai, before handing the work back. Skip only the
  automated `auto:` data commits, which the file already excludes by design.
  Write what changed *and why it mattered* — a bug entry should say what a reader would
  have seen wrong, not just which function moved. Something diagnosed but deliberately
  left alone belongs under **ทราบปัญหา / รอดำเนินการ** with the reason, so the next person
  does not rediscover it or "fix" it without the context.
