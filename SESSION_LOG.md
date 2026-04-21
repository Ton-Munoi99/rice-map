# Rice Map — Session Log (บันทึกการสนทนา)

> Workspace: `c:\Users\sponlapatp\Desktop\Rice Map`
> GitHub: https://github.com/Ton-Munoi99/rice-map
> Live: https://ton-munoi99.github.io/rice-map/
> AI: Antigravity (Google DeepMind)

---

## Session 1 — เริ่มต้นโปรเจกต์ (ก่อน 20 เม.ย. 2568)

### สิ่งที่ทำ
- สร้าง Rice Map Dashboard ตั้งแต่ต้น
- โหลดข้อมูล OAE จาก PDF/CSV (ปี 2565–2567) เข้า `rice-data.js`
- Choropleth map ข้าวนาปีรายจังหวัด 77 จังหวัด
- Layer: ผลผลิต / ผลผลิตต่อไร่ / เนื้อที่เก็บเกี่ยว / ราคา
- ประมาณการแนวโน้มปี 2568–2569 ด้วย script `estimate_2568_2569.js`
- Calibrate เนื้อที่เพาะปลูก 2568 จากข้อมูลกรมการข้าว (58.5 ล้านไร่)
- เพิ่มราคาข้าวเปลือกจากสมาคมโรงสีข้าวไทย (TRMA) รายจังหวัด

---

## Session 2 — 20 เมษายน 2568 (Conversation: c1f1cc21)

### คำถามและการดำเนินการ

**Q: ราคา DIT กับสมาคม ราคาเดียวกันไหม?**
- A: ไม่เหมือนกัน DIT รายงานเป็นภาพรวมรายภาค, สมาคมโรงสีข้าวไทยรายงานรายจังหวัด
- DIT PDF เป็น scanned image แกะยาก, เลือกใช้สมาคมโรงสีฯ แทน

**Q: สร้าง Skill OCR**
- สอบถามเรื่อง OCR สำหรับ PDF scan
- ข้อมูลค่าปุ๋ย/ต้นทุนจาก DIT เป็น scanned image ทำให้ OCR ยาก
- แนะนำใช้แหล่งอื่นที่มีข้อมูล machine-readable แทน

**Q: ข้าวเปลือกรายจังหวัด ไม่ใช่รายภูมิภาค**
- ยืนยันว่าข้อมูลใน rice-data.js เป็นรายจังหวัดทั้งหมด ✅

**Q: อยากได้ราคาหน้า Gate Farm**
- ราคา gate farm หาจาก OAE data
- OAE มี API: https://dataapi.moc.go.th/gis-product-prices?product_id=R11029

**Q: เพิ่มราคา FOB ข้าวขาว และข้าวหอมมะลิ**
- สำรวจแหล่งข้อมูล 3 แบบ
- เลือก: **สมาคมผู้ส่งออกข้าวไทย (TREA)** — มีราคา F.O.B. รายสัปดาห์
- เขียน scraper Python `scripts/fetch_trea_fob.py`
- เพิ่ม GitHub Action `update-trea-fob.yml` ทำงานอัตโนมัติทุก พุธ-พฤหัส
- ข้อมูล FOB เก็บที่ `data/trea-fob.json`

**Q: ราคาที่ไร่นา (OAE) อยู่ตรงไหน?**
- อธิบาย Live Price Widget ในแต่ละ Layer ของ Dashboard

**Q: ข้อ 2 ทำให้ชัดเจนกว่านี้**
- ปรับ UI Layout ของ Live Price Widget
- แยกชัดระหว่าง FOB / OAE Farm-gate / ราคาโรงสี

**Q: ราคาส่งออก เอาให้ใหญ่ๆ**
- เพิ่ม font size และ color ให้บรรทัด F.O.B. เด่นชัดขึ้น
- ผู้ใช้ reverted กลับเอง → ยอมรับและ commit ตามที่ผู้ใช้แก้

---

**Q: มีอะไรแนะนำเพิ่มเติม? Folder มีอะไรไม่ใช้ลบทิ้ง**

### การเคลียร์ Folder (ลบไฟล์ที่ไม่ใช้)
ลบออก:
- `oae_stats_latest.pdf` (~48MB) — ข้อมูลถูก extract เข้า rice-data.js แล้ว
- `jasmine_2565.pdf`, `jasmine_2566.pdf`
- `rice_napi_2565.pdf`, `rice_napi_2566.pdf`, `rice_naprang_2566.pdf`, `rice_naprang_2567.pdf`
- `price_17042569.pdf`, `price_30122568.pdf` — scanned PDF ราคา
- `rice-data_bak_*.js` — backup ชั่วคราว
- `thailand.json` — ต้นฉบับที่ compile เข้า thailand-data.js แล้ว
- `scripts/scrape_trea.py` — script ทดสอบที่รวมกับ fetch_trea_fob.py แล้ว

---

**Q: จำนวนเกษตรกร ต้นทุนปุ๋ย พอหาได้ไหมในระดับจังหวัด?**

### สำรวจแหล่งข้อมูล
| ข้อมูล | แหล่ง | ระดับจังหวัด? | ความยาก |
|---|---|---|---|
| จำนวนครัวเรือนเกษตรกร | OAE catalog.oae.go.th | ✅ มีรายจังหวัด | ง่าย - มี CSV |
| ต้นทุนปุ๋ย/ต้นทุนการผลิต | OAE สถิติการเกษตร | ⚠️ ส่วนใหญ่เป็นระดับภาค | ยาก — อยู่ใน PDF |

---

**Q: ดีครับ เพิ่มเข้าไปเลย (จำนวนครัวเรือนเกษตรกร)**

### สิ่งที่ทำ
1. **ดาวน์โหลดข้อมูล** จาก OAE Data Catalog:
   - URL: `catalog.oae.go.th/dataset/e21cc6cd-8641-44c9-b335-eceb548b83b4`
   - File: `data/farmer_households.csv` (จำนวนครัวเรือนเกษตรกร ปี 2565-2566, รายจังหวัด)

2. **สร้าง `scripts/build_households.py`**
   - อ่าน CSV (encoding: cp874)
   - สร้าง dict `{ ชื่อจังหวัดภาษาไทย: จำนวนครัวเรือน }` จากปีล่าสุด (2566)
   - Append เข้า `rice-data.js` เป็น `window.PROVINCE_HOUSEHOLDS`

3. **เพิ่ม Layer ใหม่ใน `index.html`**:
   - ปุ่ม "ครัวเรือนเกษตรกร / Farmer Households" ใน Layer Controls
   - `layerMeta.households` — unit: ครัวเรือน (ปี 2566)
   - `householdValueOf(en)` — lookup ด้วย `NM[en]` (en→ไทย) แล้วหาใน PROVINCE_HOUSEHOLDS
   - `yearsForLayer('households')` → return `["2566"]`
   - Choropleth แสดงสีตามจำนวนครัวเรือน
   - Tooltip แสดง "👨‍🌾 ครัวเรือนเกษตรกร: X ครัวเรือน" ในทุก layer
   - Detail Card มีกล่องเขียวแสดงจำนวนครัวเรือนแยกต่างหาก

4. **Bug Fix**: `const PROVINCE_HOUSEHOLDS` ใน rice-data.js ไม่ผูกกับ `window`
   - แก้เป็น `window.PROVINCE_HOUSEHOLDS = {...}` ทำให้ index.html access ได้

### ข้อมูล PROVINCE_HOUSEHOLDS (ปี 2566, OAE)
ครอบคลุม 76 จังหวัด — ตัวอย่าง:
- นครราชสีมา: 366,974 ครัวเรือน
- อุบลราชธานี: 348,062 ครัวเรือน
- ขอนแก่น: 265,770 ครัวเรือน
- เชียงราย: 191,700 ครัวเรือน
- ภูเก็ต: 7,247 ครัวเรือน (ต่ำสุด)

---

## สถานะ Commits ล่าสุด (20 เม.ย. 2568)

```
6a0793c fix: assign PROVINCE_HOUSEHOLDS to window for cross-script access
d5ab192 feat: add farmer household layer (OAE 2566)
bd23c49 style: user reverted FOB price styling back to default size
b372938 style: emphasize FOB export prices
937f1a8 ...
```

---

## สถานะไฟล์ปัจจุบัน

```
Rice Map/
├── index.html              ← ~2668 บรรทัด (เพิ่ม households layer)
├── rice-data.js            ← RICE_DATA_ROWS + window.PROVINCE_HOUSEHOLDS
├── thailand-data.js        ← GeoJSON SVG
├── rice-data.csv           ← CSV snapshot
├── data/
│   ├── prices/             ← PDF ราคาสมาคมโรงสีฯ
│   ├── prices-live.json    ← OAE live prices
│   ├── trea-fob.json       ← F.O.B. prices (TREA)
│   └── farmer_households.csv ← OAE ครัวเรือนเกษตรกร 2565-2566
├── scripts/
│   ├── build_oae_rice_data.py
│   ├── build_rice_dataset.py
│   ├── build_households.py   ← NEW: สร้าง PROVINCE_HOUSEHOLDS
│   ├── check_syntax.js
│   ├── estimate_2568_2569.js
│   ├── extract_pdf_prices.py
│   ├── fetch_oae_prices.py
│   └── fetch_trea_fob.py
└── .github/
    └── workflows/
        └── update-trea-fob.yml ← GitHub Action อัพเดต FOB ทุก พุธ-พฤหัส
```

---

## Data Layers ปัจจุบัน (5 layers)

| Layer | Key | ข้อมูล | Unit |
|---|---|---|---|
| ผลผลิต | `production` | OAE 2565-2567 + trend 2568-2569 | ตัน |
| ผลผลิตต่อไร่ | `yield` | OAE 2565-2567 + trend 2568-2569 | กก./ไร่ |
| เนื้อที่เก็บเกี่ยว | `area` | OAE 2565-2567 + trend 2568-2569 | ไร่ |
| ราคาที่โรงสีรับซื้อ | `price` | สมาคมโรงสีข้าวไทย 2568-2569 | บาท/ตัน |
| ครัวเรือนเกษตรกร | `households` | OAE 2566 (ทุกสินค้าเกษตร) | ครัวเรือน |

---

## Live Price Widget (แสดงในแผนที่)

3 ระดับข้อมูลราคา:
1. **🚢 F.O.B.** — TREA (สมาคมผู้ส่งออกข้าวไทย) รายสัปดาห์ → `data/trea-fob.json`
2. **🌾 OAE Farm-gate** — ราคาหน้าไร่นาระดับประเทศ → `data/prices-live.json`
3. **🏭 ราคาที่โรงสีรับซื้อ** — สมาคมโรงสีข้าวไทย รายจังหวัด → rice-data.js

---

## Next Steps (แผนต่อ)

- [ ] เพิ่มข้อมูลต้นทุนปุ๋ย/ต้นทุนการผลิต (ต้องหาจาก OAE PDF ระดับจังหวัด)
- [ ] เมื่อ OAE ออก yearbook ปี 2568 → นำเข้าแทนที่ estimated_trend
- [ ] พิจารณาเพิ่ม Layer จำนวนเกษตรกร ข้าว โดยเฉพาะ (จาก DOAE)
- [ ] Mobile responsive สมบูรณ์กว่าเดิม

---


---

## Session 3 — 21 เมษายน 2568 (Conversation: c7771ff9)

### คำถามและการดำเนินการ

**Q: ราคาปุ๋ย update ไหม?**
- ตรวจสอบพบว่าเดิมเป็นข้อมูลสุ่ม (Mock)
- พัฒนา script เชื่อมต่อ MOC Data API เพื่อดึงข้อมูลจริง

### สิ่งที่ทำ
1. **สร้าง `scripts/fetch_fert_moc.py`**
   - ดึงราคาขายปลีกรายจังหวัดจาก MOC API สำหรับ ปุ๋ยยูเรีย 46-0-0, 16-20-0, 15-15-15
   - บันทึกเข้า `data/fert-data.js` แทนข้อมูล Mock เดิม
2. **สร้าง GitHub Action `update-fert-prices.yml`**
   - ตั้งค่าให้อัปเดตราคาทุกวันจันทร์และศุกร์ (07:00 UTC) อัตโนมัติ

---

> **บันทึกโดย Antigravity** | 21 เมษายน 2568 เวลา 13:35 น.
