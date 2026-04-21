#!/usr/bin/env python3
"""
Fetch large-dam water levels from RID (กรมชลประทาน) public API.
Free, no API key. 35 large dams updated daily.

Output: data/dam-water.json
"""
import json, sys, io, requests
from datetime import datetime

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

API_URL = "https://app.rid.go.th/reservoir/api/dam/public"
OUTPUT  = "data/dam-water.json"

# ── Dam ID → English province name (matches GeoJSON province names) ──────────
DAM_PROVINCE = {
    # ภาคเหนือ
    "100104": "Chiang Mai",      # เขื่อนแม่กวงอุดมธารา
    "100105": "Lampang",         # เขื่อนกิ่วลม
    "100106": "Lampang",         # เขื่อนกิ่วคอหมา
    "100107": "Phitsanulok",     # เขื่อนแควน้อยบำรุงแดน
    "100108": "Lampang",         # เขื่อนแม่มอก
    "200101": "Tak",             # เขื่อนภูมิพล
    "200102": "Uttaradit",       # เขื่อนสิริกิติ์
    "200103": "Chiang Mai",      # เขื่อนแม่งัดสมบูรณ์ชล
    # ภาคตะวันออกเฉียงเหนือ
    "100201": "Udon Thani",      # เขื่อนห้วยหลวง
    "100202": "Sakon Nakhon",    # เขื่อนน้ำอูน
    "100206": "Kalasin",         # เขื่อนลำปาว
    "100207": "Nakhon Ratchasima", # เขื่อนลำตะคอง
    "100208": "Nakhon Ratchasima", # เขื่อนลำพระเพลิง
    "100209": "Nakhon Ratchasima", # เขื่อนมูลบน
    "100210": "Nakhon Ratchasima", # เขื่อนลำแชะ
    "100211": "Buri Ram",        # เขื่อนลำนางรอง
    "200203": "Sakon Nakhon",    # เขื่อนน้ำพุง
    "200204": "Chaiyaphum",      # เขื่อนจุฬาภรณ์
    "200205": "Khon Kaen",       # เขื่อนอุบลรัตน์
    "200212": "Ubon Ratchathani",# เขื่อนสิรินธร
    # ภาคกลาง
    "100301": "Saraburi",        # เขื่อนป่าสักชลสิทธิ์
    "100302": "Uthai Thani",     # เขื่อนทับเสลา
    "100303": "Suphan Buri",     # เขื่อนกระเสียว
    # ภาคตะวันตก
    "200401": "Kanchanaburi",    # เขื่อนศรีนครินทร์
    "200402": "Kanchanaburi",    # เขื่อนวชิราลงกรณ
    # ภาคตะวันออก
    "100501": "Nakhon Nayok",    # เขื่อนขุนด่านปราการชล
    "100502": "Chachoengsao",    # เขื่อนคลองสียัด
    "100503": "Chon Buri",       # เขื่อนบางพระ
    "100504": "Rayong",          # เขื่อนหนองปลาไหล
    "100505": "Rayong",          # เขื่อนประแสร์
    "100514": "Prachin Buri",    # เขื่อนนฤบดินทรจินดา
    # ภาคใต้
    "100602": "Prachuap Khiri Khan", # เขื่อนปราณบุรี
    "200601": "Phetchaburi",     # เขื่อนแก่งกระจาน
    "200603": "Surat Thani",     # เขื่อนรัชชประภา
    "200604": "Yala",            # เขื่อนบางลาง
}


def main():
    print(f"Fetching RID dam data from {API_URL} ...")
    r = requests.get(API_URL, timeout=30)
    r.raise_for_status()
    d = r.json()
    api_date = d.get("date", "")
    print(f"  API date: {api_date}  |  total dams: {d.get('total')}")

    # Collect all dams flat
    all_dams = []
    for region in d["data"]:
        for dam in region.get("dam", []):
            dam["_region"] = region["region"]
            all_dams.append(dam)

    # Aggregate by province (volume-weighted % storage)
    prov_dams   = {}   # province → list of dam records
    for dam in all_dams:
        dam_id  = dam.get("id", "")
        province = DAM_PROVINCE.get(dam_id)
        if not province:
            print(f"  ⚠ no province mapping for id={dam_id} name={dam.get('name')}")
            continue
        prov_dams.setdefault(province, []).append(dam)

    provinces = {}
    for province, dams in sorted(prov_dams.items()):
        total_vol = sum(float(d["volume"] or 0) for d in dams if d.get("volume") is not None)
        total_cap = sum(float(d["storage"] or 0) for d in dams if d.get("storage") is not None)
        weighted_pct = round(total_vol / total_cap * 100, 2) if total_cap > 0 else None

        provinces[province] = {
            "dam_level_pct":    weighted_pct,
            "total_volume_mm3": round(total_vol, 2),
            "total_storage_mm3": round(total_cap, 2),
            "n_dams": len(dams),
            "dams": [
                {
                    "id":      dm["id"],
                    "name":    dm["name"],
                    "pct":     dm.get("percent_storage"),
                    "volume":  dm.get("volume"),
                    "storage": dm.get("storage"),
                    "inflow":  dm.get("inflow"),
                    "outflow": dm.get("outflow"),
                }
                for dm in dams
            ],
        }
        tag = "🔴" if (weighted_pct or 0) < 30 else ("🟡" if (weighted_pct or 0) < 60 else "💧")
        dam_names = ", ".join(dm["name"] for dm in dams)
        print(f"  {tag} {province:25s} {weighted_pct:5.1f}%  ({len(dams)} เขื่อน: {dam_names})")

    output = {
        "_meta": {
            "updated":     api_date,
            "fetched_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
            "source":      "กรมชลประทาน (RID) — app.rid.go.th/reservoir/api/dam/public",
            "n_dams":      len(all_dams),
            "n_provinces": len(provinces),
            "note": "ระดับน้ำในเขื่อนขนาดใหญ่ 35 แห่ง รวมปริมาณน้ำตามน้ำหนักพื้นที่กักเก็บ · 35 large dams, volume-weighted % storage per province",
        },
        "provinces": provinces,
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\nSaved {len(provinces)} provinces → {OUTPUT}")


if __name__ == "__main__":
    main()
