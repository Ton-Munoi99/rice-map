#!/usr/bin/env python3
"""
Alert scoreboard — วัดความแม่นของพยากรณ์ฝน 7 วัน (แกนหลักของ layer เตือนน้ำท่วม)
เทียบกับฝนจริงจากดาวเทียม GSMaP

วิธี (ซื่อสัตย์ ไม่มั่ว):
  วัน D พยากรณ์ฝนสะสม 7 วัน (D..D+6) → เก็บ snapshot
  ~7 วันต่อมา GSMaP บันทึกฝน "จริง" ช่วงเดียวกัน → จับคู่ด้วย set ของวันที่
  ที่ "ตรงกันเป๊ะ" แล้วให้คะแนน (ไม่จับคู่ = ไม่ให้คะแนน ไม่เดา)

รันต่อท้าย update-rain.yml เพราะ rain-forecast.json + rain-gsmap.json ถูกสร้าง
ในรอบเดียวกัน → ข้อมูลสดและสอดคล้อง

Output: data/alert-scoreboard.json
  rolling accuracy (60 window ล่าสุด) + recent + _pending (สำหรับ match รอบหน้า)
"""
import json, os, sys
from datetime import date

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORECAST  = "data/rain-forecast.json"
GSMAP     = "data/rain-gsmap.json"
OUT       = "data/alert-scoreboard.json"

HEAVY_MM  = 120   # เกณฑ์ 🔴 เสี่ยงสูง (เท่า agri-warnings FLOOD_HIGH_MM)
ANY_MM    = 30    # เกณฑ์ 🟡 เริ่มเฝ้าระวัง (เท่า FLOOD_LOW_MM)
MIN_WINDOWS_FOR_CALIBRATION = 5  # ต้องตรงกับ fetch_agri_warnings.py
KEEP_WINDOWS = 60  # rolling อิงกี่ window ล่าสุด
KEEP_PENDING_DAYS = 16  # snapshot ที่ไม่ถูก match เกินนี้ = ทิ้ง (GSMaP window เลยไปแล้ว)


def load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def confusion(pairs, thr):
    """pairs: list of (predicted_mm, actual_mm) → TP/FP/FN/TN ที่ threshold thr"""
    tp = fp = fn = tn = 0
    for pred, act in pairs:
        p, a = pred >= thr, act >= thr
        if p and a: tp += 1
        elif p and not a: fp += 1
        elif not p and a: fn += 1
        else: tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn}


def score_window(fc, actual, bias=None):
    """fc/actual: {province: mm} → เมตริกของ window นี้

    bias = ค่าที่ fetch_agri_warnings หักออกจากพยากรณ์ "ณ วันที่ snapshot"
    (ไม่ใช่ค่าปัจจุบัน — ใช้ค่าปัจจุบันย้อนหลังจะเป็น lookahead) ถ้ามี จะให้คะแนน
    เพิ่มอีกชุดว่าถ้าหัก bias แล้วเตือน 🔴 แม่นขึ้นจริงไหม
    """
    provs = sorted(set(fc) & set(actual))
    pairs = [(fc[p], actual[p]) for p in provs]
    n = len(pairs)
    mae = round(sum(abs(pr - ac) for pr, ac in pairs) / n, 1) if n else 0.0
    bias_mm = round(sum(pr - ac for pr, ac in pairs) / n, 1) if n else 0.0
    out = {
        "province_days": n,
        "heavy": confusion(pairs, HEAVY_MM),
        "any": confusion(pairs, ANY_MM),
        "mae_mm": mae,
        "bias_mm": bias_mm,
    }
    if bias:
        adj = [(max(0.0, pr - bias), ac) for pr, ac in pairs]
        out["heavy_cal"] = confusion(adj, HEAVY_MM)
        out["bias_applied"] = round(bias, 1)
    return out


def rollup(windows):
    """รวมหลาย window → precision/recall/accuracy + MAE/bias ถ่วงน้ำหนักด้วยจำนวน"""
    agg = {k: 0 for k in ("h_tp", "h_fp", "h_fn", "a_tp", "a_fp", "a_fn", "a_tn", "pd",
                          "c_tp", "c_fp", "c_fn", "c_windows", "c_pd")}
    mae_sum = bias_sum = 0.0
    for w in windows:
        h, a, pd = w["heavy"], w["any"], w["province_days"]
        agg["h_tp"] += h["tp"]; agg["h_fp"] += h["fp"]; agg["h_fn"] += h["fn"]
        agg["a_tp"] += a["tp"]; agg["a_fp"] += a["fp"]; agg["a_fn"] += a["fn"]; agg["a_tn"] += a["tn"]
        agg["pd"] += pd
        mae_sum += w["mae_mm"] * pd
        bias_sum += w["bias_mm"] * pd
        c = w.get("heavy_cal")   # มีเฉพาะ window ที่ snapshot หลังเปิด calibration
        if c:
            agg["c_tp"] += c["tp"]; agg["c_fp"] += c["fp"]; agg["c_fn"] += c["fn"]
            agg["c_windows"] += 1; agg["c_pd"] += pd

    def ratio(num, den):
        return round(num / den, 3) if den else None

    pd = agg["pd"]
    result_cal = None
    if agg["c_windows"]:
        result_cal = {
            "windows_scored": agg["c_windows"],
            "province_days": agg["c_pd"],
            "precision": ratio(agg["c_tp"], agg["c_tp"] + agg["c_fp"]),
            "recall":    ratio(agg["c_tp"], agg["c_tp"] + agg["c_fn"]),
            "tp": agg["c_tp"], "fp": agg["c_fp"], "fn": agg["c_fn"],
        }
    return {
        "windows_scored": len(windows),
        "province_days": pd,
        "heavy": {  # >=120mm — คำเตือน 🔴 ที่ actionable
            "precision": ratio(agg["h_tp"], agg["h_tp"] + agg["h_fp"]),  # เตือน 🔴 แล้วตกจริงกี่ %
            "recall":    ratio(agg["h_tp"], agg["h_tp"] + agg["h_fn"]),  # ที่ตกหนักจริง เตือนทันกี่ %
            "tp": agg["h_tp"], "fp": agg["h_fp"], "fn": agg["h_fn"],
        },
        # เตือน 🔴 หลังหัก bias — เทียบกับ heavy ตรงๆ ว่า calibration ช่วยจริงไหม
        # นับเฉพาะ window ที่ snapshot หลังเปิด calibration (ไม่ย้อนหลัง = ไม่ lookahead)
        "heavy_calibrated": result_cal,
        "any": {  # >=30mm — มีฝนน่ากังวลไหม
            "accuracy": ratio(agg["a_tp"] + agg["a_tn"], pd),
            "tp": agg["a_tp"], "tn": agg["a_tn"], "fp": agg["a_fp"], "fn": agg["a_fn"],
        },
        "mae_mm": round(mae_sum / pd, 1) if pd else None,
        "bias_mm": round(bias_sum / pd, 1) if pd else None,
    }


def main():
    fc_data = load(FORECAST)
    gs_data = load(GSMAP)
    today = date.today().isoformat()

    board = load(OUT) if os.path.exists(OUT) else {"recent": [], "_pending": []}
    pending = board.get("_pending", [])
    recent = board.get("recent", [])

    # bias ที่ fetch_agri_warnings ใช้ "วันนี้" — อ่านจาก board ก่อนอัปเดต ซึ่งเป็นไฟล์
    # เดียวกับที่มันอ่านไปเมื่อครู่ใน workflow เดียวกัน (มันรันก่อนสคริปต์นี้)
    prev_rolling = board.get("rolling") or {}
    bias_today = 0.0
    if prev_rolling.get("windows_scored", 0) >= MIN_WINDOWS_FOR_CALIBRATION:
        bias_today = prev_rolling.get("bias_mm") or 0.0

    # 1) snapshot พยากรณ์วันนี้ (D..D+6) ถ้ายังไม่มี window เดียวกัน
    fc_dates = fc_data["_meta"].get("dates", [])
    fc_key = ",".join(fc_dates)
    fc_prov = {n: v["rain_7d"] for n, v in fc_data["provinces"].items()}
    if fc_dates and not any(p["window"] == fc_key for p in pending):
        pending.append({"snapped": today, "window": fc_key, "fc": fc_prov, "bias": bias_today})
        print(f"snapshot forecast for {fc_dates[0]}..{fc_dates[-1]} "
              f"({len(fc_prov)} provinces, bias in effect {bias_today:.1f}mm)")

    # 2) จับคู่ snapshot ที่ window ตรงกับ GSMaP วันนี้เป๊ะ → ให้คะแนน
    gs_key = ",".join(gs_data["_meta"].get("dates", []))
    gs_prov = {n: v["rain_7d"] for n, v in gs_data["provinces"].items()}
    scored_keys = {w["window"] for w in recent}
    still_pending = []
    for snap in pending:
        if snap["window"] == gs_key and gs_key and snap["window"] not in scored_keys:
            m = score_window(snap["fc"], gs_prov, snap.get("bias"))
            m["window_end"] = snap["window"].split(",")[-1]
            m["window"] = snap["window"]
            recent.append(m)
            print(f"scored window ending {m['window_end']}: "
                  f"heavy tp/fp/fn={m['heavy']['tp']}/{m['heavy']['fp']}/{m['heavy']['fn']} MAE={m['mae_mm']}mm")
        else:
            still_pending.append(snap)

    # 3) prune snapshot เก่าที่ไม่ถูก match (GSMaP window เลยไปแล้ว)
    still_pending = [p for p in still_pending
                     if (date.fromisoformat(today) - date.fromisoformat(p["snapped"])).days <= KEEP_PENDING_DAYS]

    recent.sort(key=lambda w: w["window_end"])
    recent = recent[-KEEP_WINDOWS:]

    result = {
        "_meta": {
            "updated": today,
            "method": "7-day rain forecast vs GSMaP satellite actual, matched by exact date window",
            "note": ("วัดความแม่นพยากรณ์ฝน 7 วัน เทียบฝนจริงดาวเทียม GSMaP · "
                     f"heavy = ≥{HEAVY_MM}มม. (เตือน 🔴), any = ≥{ANY_MM}มม. · "
                     "จับคู่เฉพาะช่วงวันที่ตรงกันเป๊ะ"),
            "heavy_mm": HEAVY_MM,
            "any_mm": ANY_MM,
        },
        "rolling": rollup(recent) if recent else None,
        "recent": recent[-14:],
        "_pending": still_pending,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    r = result["rolling"]
    if r:
        print(f"\n✅ Scoreboard: {r['windows_scored']} windows, {r['province_days']} province-days · "
              f"🔴 precision {r['heavy']['precision']} recall {r['heavy']['recall']} · MAE {r['mae_mm']}mm")
    else:
        print(f"\n✅ Scoreboard seeded; {len(still_pending)} snapshot(s) pending, ยังไม่มี window ครบกำหนด")


if __name__ == "__main__":
    main()
