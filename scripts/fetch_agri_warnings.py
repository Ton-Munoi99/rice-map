#!/usr/bin/env python3
"""
Generate province-level agricultural warnings from existing data.
Combines: Open-Meteo forecast + GSMaP satellite + RID dam levels
Output: data/agri-warnings.json
"""
import json
import os
import sys
import io
from datetime import date

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(ROOT_DIR, "data")

FORECAST_PATH   = os.path.join(DATA_DIR, "rain-forecast.json")
GSMAP_PATH      = os.path.join(DATA_DIR, "rain-gsmap.json")
DAM_PATH        = os.path.join(DATA_DIR, "dam-water.json")
SCOREBOARD_PATH = os.path.join(DATA_DIR, "alert-scoreboard.json")
OUTPUT_PATH     = os.path.join(DATA_DIR, "agri-warnings.json")

# ต้องมีอย่างน้อยเท่านี้ window ก่อนเชื่อ bias (กัน overcorrect จากข้อมูลน้อย/สุ่ม)
MIN_WINDOWS_FOR_CALIBRATION = 5

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
FLOOD_HIGH_MM  = 120
FLOOD_MED_MM   = 60
FLOOD_LOW_MM   = 30
DROUGHT_RAIN   = 5
DROUGHT_DAM    = 40
DAM_LOW_PCT    = 30

# ---------------------------------------------------------------------------
# Warning type definitions
# ---------------------------------------------------------------------------
WARNING_TYPES = {
    "flood_high": {"icon": "🔴", "type": "flood",  "level": "high",   "level_num": 3,
                   "th": "เสี่ยงน้ำท่วมรุนแรง",    "en": "High flood risk"},
    "flood_med":  {"icon": "🟠", "type": "flood",  "level": "medium", "level_num": 2,
                   "th": "เสี่ยงน้ำท่วมปานกลาง",   "en": "Moderate flood risk"},
    "flood_low":  {"icon": "🟡", "type": "flood",  "level": "low",    "level_num": 1,
                   "th": "เฝ้าระวังน้ำท่วม",       "en": "Flood watch"},
    "drought":    {"icon": "🏜",  "type": "drought","level": "drought","level_num": 0.5,
                   "th": "เสี่ยงแล้ง (ฝนน้อย+เขื่อนต่ำ)", "en": "Drought risk (low rain+dam)"},
    "dam_low":    {"icon": "💧", "type": "dam",    "level": "dam_low","level_num": 0.5,
                   "th": "ระดับเขื่อนน้ำน้อย",     "en": "Low dam level"},
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path):
    """Load JSON file; return None if missing or unreadable."""
    if not os.path.exists(path):
        print(f"[SKIP] File not found: {path}", file=sys.stderr)
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[WARN] Could not read {path}: {e}", file=sys.stderr)
        return None


def get_provinces(data):
    """Return provinces dict from a data file, or {}."""
    if data is None:
        return {}
    return data.get("provinces", {})


def round2(v):
    return round(float(v), 2) if v is not None else None


def load_forecast_bias():
    """ดึง bias สะสมของพยากรณ์ (พยากรณ์ - ฝนจริง GSMaP) จาก alert-scoreboard.json
    ถ้าพยากรณ์ over-predict เป็นระบบ (bias > 0) ค่านี้จะถูกหักออกก่อนตัดสินระดับเตือน
    เพื่อลด false positive โดยไม่ต้องแก้สูตรพยากรณ์เอง"""
    d = load_json(SCOREBOARD_PATH)
    rolling = (d or {}).get("rolling")
    if not rolling or rolling.get("windows_scored", 0) < MIN_WINDOWS_FOR_CALIBRATION:
        return 0.0
    return rolling.get("bias_mm") or 0.0


# ---------------------------------------------------------------------------
# Warning generation per province
# ---------------------------------------------------------------------------

def build_warnings(prov_name, fc_7d, gs_7d, dam_pct, fc_bias=0.0):
    """
    Return list of warning dicts for a province.
    fc_7d  : 7-day forecast rain (mm) or None
    gs_7d  : 7-day GSMaP satellite rain (mm) or None
    dam_pct: dam level (% capacity) or None
    fc_bias: ค่าเฉลี่ย (พยากรณ์ - จริง) สะสม — หักออกจาก fc_7d ก่อนตัดสินระดับ (ไม่กระทบข้อความที่แสดง)
    """
    warnings = []
    fc_7d_adj = max(0.0, fc_7d - fc_bias) if fc_7d is not None else None

    # -----------------------------------------------------------------------
    # Flood warnings (check both forecast and gsmap, use highest trigger)
    # -----------------------------------------------------------------------
    # Determine flood level triggered by each source
    def flood_level(mm):
        if mm is None:
            return None
        if mm >= FLOOD_HIGH_MM:
            return "flood_high"
        if mm >= FLOOD_MED_MM:
            return "flood_med"
        if mm >= FLOOD_LOW_MM:
            return "flood_low"
        return None

    fc_level  = flood_level(fc_7d_adj)
    gs_level  = flood_level(gs_7d)

    # Priority order for flood levels
    FLOOD_ORDER = ["flood_high", "flood_med", "flood_low"]

    # Pick the more severe of the two sources
    if fc_level or gs_level:
        lvls = [l for l in [fc_level, gs_level] if l]
        best = min(lvls, key=lambda l: FLOOD_ORDER.index(l))  # lower index = more severe
        wt = WARNING_TYPES[best]

        # Build message with available values
        parts_th = []
        parts_en = []
        if fc_7d is not None and fc_level is not None:
            parts_th.append(f"คาดว่าฝนสะสม 7 วันข้างหน้า {fc_7d:.0f} มม.")
            parts_en.append(f"7-day forecast rainfall {fc_7d:.0f}mm")
        if gs_7d is not None and gs_level is not None:
            parts_th.append(f"ดาวเทียม GSMaP: {gs_7d:.0f} มม.")
            parts_en.append(f"GSMaP satellite: {gs_7d:.0f}mm")
        # If only one source triggers but both exist, still mention gsmap
        if fc_7d is not None and gs_7d is not None and gs_level is None and fc_level is not None:
            parts_th.append(f"(ดาวเทียม: {gs_7d:.0f} มม.)")
            parts_en.append(f"(satellite: {gs_7d:.0f}mm)")
        if fc_7d is not None and gs_7d is not None and fc_level is None and gs_level is not None:
            parts_th.append(f"(พยากรณ์: {fc_7d:.0f} มม.)")
            parts_en.append(f"(forecast: {fc_7d:.0f}mm)")

        suffix_th = wt["th"]
        suffix_en = wt["en"]
        msg_th = " + ".join(parts_th) + f" — {suffix_th}"
        msg_en = " + ".join(parts_en) + f" — {suffix_en}"

        # Determine primary trigger value / threshold
        # Use the value from the source that actually triggered the best (worst) level.
        # e.g. if gsmap triggers high but forecast only triggers low, show gsmap value.
        if gs_level == best:
            primary_val = gs_7d
        elif fc_level == best:
            primary_val = fc_7d
        else:
            primary_val = fc_7d if fc_7d is not None else gs_7d
        threshold_map = {"flood_high": FLOOD_HIGH_MM, "flood_med": FLOOD_MED_MM, "flood_low": FLOOD_LOW_MM}

        warnings.append({
            "icon":       wt["icon"],
            "type":       wt["type"],
            "level":      wt["level"],
            "message_th": msg_th,
            "message_en": msg_en,
            "source":     "พยากรณ์ Open-Meteo" + (" + JAXA GSMaP" if gs_level else "")
                          if fc_level else "JAXA GSMaP",
            "value":      round2(primary_val),
            "threshold":  threshold_map[best],
        })

    # -----------------------------------------------------------------------
    # Drought warning (needs gsmap AND dam)
    # -----------------------------------------------------------------------
    if gs_7d is not None and dam_pct is not None:
        if gs_7d < DROUGHT_RAIN and dam_pct < DROUGHT_DAM:
            wt = WARNING_TYPES["drought"]
            warnings.append({
                "icon":       wt["icon"],
                "type":       wt["type"],
                "level":      wt["level"],
                "message_th": f"ฝนน้อยกว่า {DROUGHT_RAIN} มม./7 วัน ({gs_7d:.1f} มม.) + เขื่อน {dam_pct:.0f}% — เสี่ยงแล้ง",
                "message_en": f"Rain < {DROUGHT_RAIN}mm/7d ({gs_7d:.1f}mm) + dam at {dam_pct:.0f}% — drought risk",
                "source":     "JAXA GSMaP + กรมชลประทาน",
                "value":      round2(gs_7d),
                "threshold":  DROUGHT_RAIN,
            })

    # -----------------------------------------------------------------------
    # Dam low warning (needs dam only)
    # -----------------------------------------------------------------------
    if dam_pct is not None:
        if dam_pct < DAM_LOW_PCT:
            wt = WARNING_TYPES["dam_low"]
            warnings.append({
                "icon":       wt["icon"],
                "type":       wt["type"],
                "level":      wt["level"],
                "message_th": f"เขื่อนระดับน้ำ {dam_pct:.1f}% ของความจุ",
                "message_en": f"Dam at {dam_pct:.1f}% of capacity",
                "source":     "กรมชลประทาน (RID)",
                "value":      round2(dam_pct),
                "threshold":  DAM_LOW_PCT,
            })

    # -----------------------------------------------------------------------
    # Normal status (no flood/drought risk — rain < 30mm)
    # -----------------------------------------------------------------------
    if not warnings:
        rain_max = max(v for v in [fc_7d, gs_7d] if v is not None) if any(v is not None for v in [fc_7d, gs_7d]) else 0
        warnings.append({
            "icon":       "✅",
            "type":       "normal",
            "level":      "normal",
            "message_th": f"ฝนปกติ ({rain_max:.0f} มม./7 วัน) — ไม่มีความเสี่ยง",
            "message_en": f"Normal rainfall ({rain_max:.0f}mm/7d) — no risk",
            "source":     "Open-Meteo + JAXA GSMaP",
            "value":      round2(rain_max),
            "threshold":  FLOOD_LOW_MM,
        })

    return warnings


def top_level(warnings):
    """Return (level_string, level_num) for the worst warning in the list."""
    if not warnings:
        return "normal", 0

    LEVEL_ORDER = {
        "high":    3,
        "medium":  2,
        "low":     1,
        "drought": 0.5,
        "dam_low": 0.5,
        "none":    0,
    }
    best = max(warnings, key=lambda w: LEVEL_ORDER.get(w["level"], 0))
    return best["level"], LEVEL_ORDER.get(best["level"], 0)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # Load sources
    forecast_data = load_json(FORECAST_PATH)
    gsmap_data    = load_json(GSMAP_PATH)
    dam_data      = load_json(DAM_PATH)

    if forecast_data is None:
        print("[ERROR] rain-forecast.json is required but missing.", file=sys.stderr)
        sys.exit(1)

    fc_provs  = get_provinces(forecast_data)
    gs_provs  = get_provinces(gsmap_data)
    dam_provs = get_provinces(dam_data)

    # Province list comes from forecast (77 provinces)
    all_provinces = sorted(fc_provs.keys())
    print(f"Processing {len(all_provinces)} provinces...")

    fc_bias = load_forecast_bias()
    if fc_bias:
        print(f"Calibrating forecast: -{fc_bias:.1f}mm (measured over-prediction bias from alert-scoreboard.json)")

    result_provinces = {}
    summary = {"high": 0, "medium": 0, "low": 0, "drought": 0, "dam_low": 0, "none": 0}

    for prov in all_provinces:
        fc_entry  = fc_provs.get(prov, {})
        gs_entry  = gs_provs.get(prov, {})
        dam_entry = dam_provs.get(prov, {})

        fc_7d  = fc_entry.get("rain_7d")
        gs_7d  = gs_entry.get("rain_7d")
        dam_pct = dam_entry.get("dam_level_pct")

        warnings = build_warnings(prov, fc_7d, gs_7d, dam_pct, fc_bias)
        level_str, level_num = top_level(warnings)

        result_provinces[prov] = {
            "level":     level_str,
            "level_num": level_num,
            "warnings":  warnings,
        }

        # Tally summary (each province counted once, by its highest level)
        if level_str in summary:
            summary[level_str] += 1
        else:
            summary[level_str] = 1

    # Build output
    output = {
        "_meta": {
            "updated": date.today().isoformat(),
            "sources": ["Open-Meteo Forecast", "JAXA GSMaP", "RID Dam"],
            "thresholds": {
                "flood_high_mm":  FLOOD_HIGH_MM,
                "flood_med_mm":   FLOOD_MED_MM,
                "flood_low_mm":   FLOOD_LOW_MM,
                "drought_rain_mm": DROUGHT_RAIN,
                "drought_dam_pct": DROUGHT_DAM,
                "dam_low_pct":    DAM_LOW_PCT,
            },
            "forecast_bias_correction_mm": round(fc_bias, 1),
        },
        "summary": {
            "high":    summary.get("high", 0),
            "medium":  summary.get("medium", 0),
            "low":     summary.get("low", 0),
            "drought": summary.get("drought", 0),
            "dam_low": summary.get("dam_low", 0),
            "none":    summary.get("none", 0),
        },
        "provinces": result_provinces,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nWrote {OUTPUT_PATH}")
    print("\n--- Summary ---")
    total = len(all_provinces)
    s = output["summary"]
    print(f"  High flood risk  : {s['high']:3d} provinces")
    print(f"  Medium flood risk: {s['medium']:3d} provinces")
    print(f"  Flood watch (low): {s['low']:3d} provinces")
    print(f"  Drought risk     : {s['drought']:3d} provinces")
    print(f"  Dam low          : {s['dam_low']:3d} provinces")
    print(f"  No warning       : {s['none']:3d} provinces")
    print(f"  Total            : {total:3d} provinces")

    # Show a few examples with warnings
    print("\n--- Sample warnings ---")
    shown = 0
    for prov, data in result_provinces.items():
        if data["level"] not in ("none",) and shown < 5:
            print(f"\n  {prov} [{data['level']} / {data['level_num']}]")
            for w in data["warnings"]:
                print(f"    {w['icon']} {w['message_en']}")
            shown += 1


def _selftest():
    """assert-based check: bias correction must move borderline cases without
    breaking obviously-safe or obviously-severe ones"""
    # 130mm forecast, 46.8 bias → adjusted 83.2mm → drops from flood_high to flood_med
    w = build_warnings("Test", fc_7d=130, gs_7d=None, dam_pct=None, fc_bias=46.8)
    assert w[0]["level"] == "medium", w
    # far above threshold even after correction → still high
    w = build_warnings("Test", fc_7d=300, gs_7d=None, dam_pct=None, fc_bias=46.8)
    assert w[0]["level"] == "high", w
    # bias can't push below zero
    w = build_warnings("Test", fc_7d=10, gs_7d=None, dam_pct=None, fc_bias=46.8)
    assert w[0]["level"] == "normal", w
    # zero bias = unchanged behavior (calibration not yet trusted)
    w = build_warnings("Test", fc_7d=130, gs_7d=None, dam_pct=None, fc_bias=0.0)
    assert w[0]["level"] == "high", w
    print("✅ _selftest passed")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
