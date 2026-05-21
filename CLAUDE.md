# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
# Rebuild rice production dataset from OAE source Excel
python scripts/build_oae_rice_data.py

# Rebuild rice mills JSON from DIT Excel export
# Requires: thai_rice_mills_dit_YYYY-MM-DD.xlsx in repo root
python scripts/build_rice_mills.py

# Fetch live data manually (normally run by GitHub Actions)
python scripts/fetch_dam_water.py
python scripts/fetch_miller_prices.py
python scripts/fetch_trea_fob.py
python scripts/fetch_weather.py
python scripts/fetch_weather_forecast.py
```

PDF price files: drop `price_DDMMYYYY.pdf` into `data/prices/` and push — GitHub Actions auto-extracts via `process-pdf-prices.yml`.

## Architecture

### Single-page app — `index.html` (~3,800 lines)

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
1. Add entry to `layerMeta` (th, en, unit, unitShort, summary, summaryMode)
2. Add dispatch in `valueOf()` and `hasLayerValue()`
3. Add color palette case in `getPalette()`
4. Add format case in `fmtCompact()` if needed
5. Add layer button in HTML `#layerButtons`
6. Add badge/title/description/data-source-note cases in render functions
7. Add detail card case in `selectProvince()`

**Data flow:** `valueOf(en, rice, year, layer)` → dispatches to per-layer value functions → `rerender()` → SVG fill colors via `getPalette()` + `lerp()`.

**Profit formula:** `(price ฿/ton × yield kg/rai / 1000) − COST_BASE[rice].oaeRaiCost`

**Fertilizer ratio card:** shown in province detail when `layer !== "profit"` — bags of urea (46-0-0) per ton of rice = `ricePricePerTon / ureaMidPrice`; bags needed per rai = `FERT_DOA_RATES["46-0-0"] / 50 = 0.2`.

### Companion data files

| File | Contents |
|------|---------|
| `rice-data.js` | Sets `window.RICE_DATA_ROWS` — ~4,000 rows, นาปี only (OAE Table 1.4), white + jasmine |
| `thailand-data.js` | Sets `window.THAILAND_SVG_DATA` — SVG paths for all 77 provinces |

### JSON data files (`data/`)

Auto-updated by GitHub Actions crons:
- `dam-water.json` — RID dam levels (daily, 16:00 + 18:00 BKK)
- `prices-live.json` — Thai Rice Millers Association prices
- `trea-fob.json` — TREA FOB export prices
- `weather-province.json` + `weather-forecast.json` — Open-Meteo rainfall data
- `rice-mills.json` — DIT registered mills (built from Excel, not auto-updated)

### GitHub Actions

8 workflows in `.github/workflows/`. All commit directly to `main` using `git pull --rebase` before push to avoid conflicts with concurrent runs.

## Important Constraints

- **ข้อมูลนาปีเท่านั้น** — All `rice-data.js` data is main-season (นาปี) from OAE Table 1.4. No second-crop (นาปรัง) data exists in this repo.
- **ข้าวขาว = OAE "ข้าวเจ้าอื่นๆ"** — excludes glutinous rice (ข้าวเหนียว) and Pathum Thani 1
- **Year keys are Thai Buddhist Era strings** — `"2567"` not `2567` (number)
- **Province keys are English names** — matching `NM` lookup map and `thailand-data.js`
- **Do not push to git without owner review** — confirm before any `git push`
