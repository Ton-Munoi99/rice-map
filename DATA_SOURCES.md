# แหล่งข้อมูลและวิธีคำนวณ — Thailand Rice Intelligence Map

เอกสารนี้อธิบายทุกชั้นข้อมูล (layer) และวิดเจ็ตในเว็บว่า **คืออะไร · ใช้ข้อมูลอะไร ·
คำนวณอย่างไร · คิดมาอย่างไร · อ้างอิงจากไหน (พร้อมลิงก์ตรง)** เพื่อความโปร่งใสและตรวจสอบได้

> **หลักการ:** ข้อมูลราชการ/ดาวเทียมใช้ตามต้นฉบับ · ค่าที่ต้องคำนวณระบุสูตรและค่าคงที่ชัดเจน ·
> ชั้นที่ "สังเคราะห์เพื่อเฝ้าระวัง" (เช่น พื้นที่เสี่ยงน้ำท่วม) ระบุว่าไม่ใช่ประกาศทางการ ·
> ทุก reference เป็นลิงก์ตรงไปหน้า/endpoint/ไฟล์ที่ระบบดึงจริง

สารบัญ: [ผลผลิต & เศรษฐกิจข้าว](#1-ผลผลิต--เศรษฐกิจข้าว) · [น้ำ & สภาพอากาศ](#2-น้ำ--สภาพอากาศ) ·
[ดาวเทียม & ดัชนีพืช](#3-ดาวเทียม--ดัชนีพืช) · [อื่นๆ](#4-อื่นๆ) · [ตารางสรุป + ลิงก์](#ตารางสรุปแหล่งข้อมูล--ลิงก์)

---

## 1. ผลผลิต & เศรษฐกิจข้าว

### ผลผลิต (ตัน) / ผลผลิตต่อไร่ (กก./ไร่) / เนื้อที่เก็บเกี่ยว (ไร่) — นาปี
- **คืออะไร:** สถิติการผลิตข้าวนาปี (ฤดูฝน) รายจังหวัด
- **ข้อมูล:** สำนักงานเศรษฐกิจการเกษตร (**OAE**) — รายงานสถิติการเกษตร **ตาราง 1.4**
- **หมายเหตุ:** "ข้าวขาว" = "ข้าวเจ้าอื่นๆ" ของ OAE (ไม่รวมข้าวเหนียว/ปทุมธานี 1) · ปีเป็น พ.ศ. · เฉพาะนาปี
- **ลิงก์ตรง:**
  - หน้า dataset: <https://catalog.oae.go.th/dataset/ba103542-830f-418a-b614-9645ebbe1a93>
  - PDF สถิติที่ใช้ประมวลผล: <https://catalog.oae.go.th/dataset/ba103542-830f-418a-b614-9645ebbe1a93/resource/4d5d1421-bb3b-4635-a43d-f6167d619db1/download/fd747711b82231d4.pdf>
  - PDF ปี 2565: <https://catalog.oae.go.th/dataset/2d949230-33ba-4ffc-be18-04d2d779ec64/resource/415736c7-1027-4712-8fcd-f0c41d6c7f08/download/2565.pdf> · ปี 2566: <https://catalog.oae.go.th/dataset/2d949230-33ba-4ffc-be18-04d2d779ec64/resource/a0e1a68f-270f-4605-83ba-b70fbd5b87a0/download/2566.pdf>
- **สคริปต์ (เรียงตามลำดับ):** `scripts/build_rice_dataset.py` (ฐาน 2565-2567 + ราคา) → `scripts/update_rice_data.py` (เติม 2568 ทางการจาก `data/oae_extracted.json`) → `scripts/estimate_2568_2569.js` (ประมาณการ 2569) → `scripts/clear_estimated_trend_prices.py`
  - ข้อมูล 2568 refresh ด้วย `scripts/extract_oae.py` (parse PDF สถิติ ปี 2568 → `data/oae_extracted.json`)
  - `build_oae_rice_data.py` เป็น builder เก่าที่ถูกแทนแล้ว เก็บไว้เพราะ `build_naprang_data.py` import ฟังก์ชัน parse จากมัน

### ผลผลิต / เนื้อที่เก็บเกี่ยว — นาปรัง (ฤดูแล้ง)
- **คืออะไร:** สถิติข้าวนาปรัง (ปลูกฤดูแล้งในเขตชลประทาน) รายจังหวัด
- **ข้อมูล:** OAE — "ปริมาณการผลิตข้าวนาปรัง รายจังหวัด" ปี 2565–2568
- **สำคัญ:** หอมมะลิเป็นข้าวไวแสง **ปลูกได้เฉพาะนาปี** → เลือกหอมมะลิบน layer นาปรัง = ไม่มีข้อมูล (ตั้งใจ ไม่ใช่บั๊ก)
- **ลิงก์ตรง:**
  - หน้า dataset: <https://catalog.oae.go.th/dataset/dataoae1104>
  - PDF ปี 2565: <https://catalog.oae.go.th/dataset/2446c264-3f68-4c79-ac44-dd9db8f07ebf/resource/294179c7-eb04-4ceb-8303-ccbf61780d26/download/untitled.pdf>
  - PDF ปี 2566: <https://catalog.oae.go.th/dataset/2446c264-3f68-4c79-ac44-dd9db8f07ebf/resource/863efbb5-2fc4-40b2-8fb3-47a73f6ee465/download/untitled.pdf>
  - PDF ปี 2567: <https://catalog.oae.go.th/dataset/2446c264-3f68-4c79-ac44-dd9db8f07ebf/resource/d2aa5a07-d756-45b6-83c1-6bd936abbc01/download/untitled.pdf>
  - PDF ปี 2568: <https://catalog.oae.go.th/dataset/2446c264-3f68-4c79-ac44-dd9db8f07ebf/resource/4185c3d5-a99d-40e1-adfe-844d0c9f8c56/download/7e8a9d2271fc1172.pdf>
- **สคริปต์:** `scripts/build_naprang_data.py`

### ราคาที่โรงสีรับซื้อ (฿/ตัน)
- **คืออะไร:** ราคารับซื้อข้าวเปลือกที่โรงสี รายจังหวัด · บันทึกความชื้น 15% (มีคอลัมน์ 25% ด้วยถ้ามี)
- **ข้อมูล:** **สมาคมโรงสีข้าวไทย** (ดึง PDF อัตโนมัติ)
- **ลิงก์ตรง:**
  - เว็บสมาคม: <http://www.thairicemillers.org/>
  - โฟลเดอร์ PDF ราคา (รูปแบบ `PricericeDDMMYYYY.pdf`): <http://www.thairicemillers.org/images/introc_1429264173/>
  - ตัวอย่างไฟล์: <http://www.thairicemillers.org/images/introc_1429264173/Pricerice17042569.pdf>
- **ราคา OAE (สำรอง/ระดับชาติ):** CKAN API <https://catalog.oae.go.th/api/3/action/datastore_search> (resource `c72f9a58-6969-48d6-9203-7859362adaf7`)
- **สคริปต์:** `scripts/fetch_miller_prices.py`, `scripts/fetch_oae_prices.py`

### ราคาส่งออก FOB
- **คืออะไร:** ราคาส่งออกข้าวหน้าท่าเรือ
- **ข้อมูล:** **สมาคมผู้ส่งออกข้าวไทย (TREA)**
- **ลิงก์ตรง:** <https://www.thairiceexporters.or.th/price.htm> *(เว็บมีใบรับรอง SSL ไม่ตรงชื่อโฮสต์ — เบราว์เซอร์อาจเตือน; สคริปต์ดึงโดยข้ามการตรวจ cert)* · อัตราแลกเปลี่ยน USD: <https://open.er-api.com/v6/latest/USD>
- **สคริปต์:** `scripts/fetch_trea_fob.py`

### กำไร/ขาดทุนประมาณการ (฿/ไร่)
- **คำนวณ:** `กำไร = (ราคาโรงสี ฿/ตัน × ผลผลิต กก./ไร่ ÷ 1000) − ต้นทุน`
- **ต้นทุน (OAE):** ข้าวขาว **6,100** ฿/ไร่ · หอมมะลิ **5,150** ฿/ไร่
- **หมายเหตุ:** ป้าย "ประมาณการ" — ต้นทุนใช้ค่าเฉลี่ย OAE ไม่ใช่ต้นทุนจริงรายแปลง
- **ที่มาต้นทุน:** ต้นทุนการผลิตข้าว OAE — <https://www.oae.go.th/> (หมวดต้นทุนการผลิต)

### ราคาปุ๋ยเคมี & อัตราส่วนฟาง-ปุ๋ย
- **ข้อมูล:** ราคาปุ๋ยจาก **กรมการค้าภายใน/กระทรวงพาณิชย์ (MOC)** สำรวจ 8 สูตร (อัปเดตในโค้ด 23 เม.ย. 2569) · อัตราใส่ปุ๋ยแนะนำจาก **กรมการข้าว (DOA)** เช่น ยูเรีย 46-0-0 = 10 กก./ไร่
- **คำนวณ:** จำนวนกระสอบยูเรียต่อข้าว 1 ตัน = ราคาข้าว ÷ ราคายูเรีย (ค่ากลาง MOC)
- **ลิงก์:** ราคาสินค้า MOC <https://www.dit.go.th/> · คำแนะนำการใช้ปุ๋ย กรมการข้าว <https://www.ricethailand.go.th/>
- **หมายเหตุ:** ค่าฝังใน `index.html` (`FERT_MOC`, `FERT_DOA_RATES`) อัปเดตด้วยมือจากผลสำรวจ

### 🌾 ฟางข้าว
- **คืออะไร:** ปริมาณฟางที่เกิดจากการปลูกข้าว + "ฟางเหลือใช้" (มักถูกเผา → PM2.5 หรือใช้เป็นเชื้อเพลิงชีวมวล)
- **ข้อมูล:** ผลผลิตข้าว OAE (นาปี ขาว+หอมมะลิ + นาปรัง) — แหล่งเดียวกับด้านบน
- **คำนวณ:**
  1. ฟางทั้งหมด = ผลผลิตข้าว × **RPR 1.169** *(Residue-to-Product Ratio: ข้าว 1 ตัน → ฟาง 1.169 ตัน)*
  2. ฟางเหลือใช้ = ฟางทั้งหมด × **SAF 0.583** *(Surplus Availability Factor: หลังหักที่ชาวนาใช้เอง เหลือ 58.3%)*
- **อ้างอิง:** ค่า RPR/SAF จาก **กรมพัฒนาพลังงานทดแทนและอนุรักษ์พลังงาน (พพ./DEDE)** — <https://www.dede.go.th/> · ศูนย์องค์ความรู้ฯ <https://kc.dede.go.th/>

### ⚡ โรงไฟฟ้าชีวมวล
- **คืออะไร:** โรงไฟฟ้าชีวมวล 79 แห่งทั่วประเทศ + ธงว่ารับซื้อฟางข้าว/แกลบไหม · การ์ด "ตลาดรับซื้อฟาง/แกลบ" จับคู่ฟางเหลือใช้ของจังหวัดกับโรงที่รับซื้อ (ระดับจังหวัด/ภาค)
- **ข้อมูล:** **DEDE** — "ข้อมูลการรับซื้อเชื้อเพลิงชีวมวลของโรงไฟฟ้าในประเทศไทย ปี 2565" (79 โรง, ข้อมูลเบื้องต้นจากโรงที่ตอบแบบสอบถาม)
- **ลิงก์ตรง:**
  - หน้าองค์ความรู้ + ไฟล์ PDF: <https://kc.dede.go.th/knowledge-view.aspx?p=231>
  - แผนที่พิกัดโรงไฟฟ้าชีวมวล (GIS DEDE): <https://gis.dede.go.th/gallery-map-view.aspx?p=77>
- **สคริปต์/ข้อมูล:** `data/biomass-plants.json` (สกัดจาก PDF ด้วยมือ)

### 🏭 โรงสีข้าว
- **ข้อมูล:** **กรมการค้าภายใน (DIT)** — โรงสีจดทะเบียน (จำนวน + ขนาด ใหญ่/กลาง/เล็ก)
- **ลิงก์:** เว็บ DIT <https://www.dit.go.th/> (ส่งออกเป็น Excel `thai_rice_mills_dit_YYYY-MM-DD.xlsx`)
- **สคริปต์:** `scripts/build_rice_mills.py` (สร้าง `data/rice-mills.json` จาก Excel export)

### 👨‍🌾 ครัวเรือนเกษตรกร
- **ข้อมูล:** **OAE ปี 2566** — จำนวนครัวเรือนเกษตรกร (รวมทุกสินค้า ไม่เฉพาะข้าว)
- **ลิงก์:** พอร์ทัลข้อมูลเปิด OAE <https://catalog.oae.go.th/> (ไฟล์ `data/farmer_households.csv` ในรีโป)

---

## 2. น้ำ & สภาพอากาศ

### 🌦 พยากรณ์ฝน 7 วันข้างหน้า (multi-point p90)
- **คืออะไร:** ฝนที่**คาดว่าจะตก** 7 วันข้างหน้า (โมเดลพยากรณ์ ไม่ใช่ของจริง)
- **ข้อมูล:** **Open-Meteo Forecast API** (ฟรี ไม่ต้อง API key) — รวมผลจากโมเดลพยากรณ์อากาศโลก (ECMWF/GFS ฯลฯ)
- **คำนวณ:** สุ่ม **≤6 จุด**กระจายในเขต polygon จังหวัด → ดึงพยากรณ์รายวันแต่ละจุด → เอา **p90 (เปอร์เซ็นไทล์ 90)** ข้ามจุดแต่ละวัน → รวม 7 วัน
- **ทำไม p90 ไม่ใช่ค่าเฉลี่ย:** ฝนบางจังหวัดตกกระจุกเฉพาะจุด (ปะทะเทือกเขา — orographic) วัดจุดกลางจุดเดียวจะพลาด · p90 จับฝนกระจุกได้แต่ไม่ตื่นตูมเท่า max
- **ลิงก์ตรง:**
  - API endpoint ที่ดึง: <https://api.open-meteo.com/v1/forecast> (พารามิเตอร์ `daily=precipitation_sum&forecast_days=7&timezone=Asia/Bangkok`)
  - เอกสาร: <https://open-meteo.com/en/docs>
- **สคริปต์:** `scripts/fetch_rain_forecast.py`

### 🛰 ปริมาณฝนรวม 7 วันล่าสุด (ดาวเทียม GSMaP)
- **คืออะไร:** ฝนที่ตก**จริง**ย้อนหลัง 7 วัน วัดจากดาวเทียม
- **ดาวเทียมวัดยังไง:** ดาวเทียมกลุ่ม **GPM** (NASA + JAXA ญี่ปุ่น) ใช้เซนเซอร์ไมโครเวฟ + อินฟราเรด มองทะลุเมฆ ตรวจเม็ดน้ำ/น้ำแข็งในเมฆ → ประเมินอัตราฝน (มม./ชั่วโมง) ทุก 1 ชม. ความละเอียด ~0.1° (≈11 กม.)
- **คำนวณ:** รวมฝนรายชั่วโมง 24 ชม. = ฝนรายวัน → 7 วัน → **เฉลี่ยเชิงพื้นที่ทั้ง polygon จังหวัด** ด้วย Google Earth Engine `reduceRegions` (ไม่ใช่จุดเดียว) · ข้อมูลช้าจากจริง ~4 ชม.
- **ลิงก์ตรง:**
  - GEE dataset (`JAXA/GPM_L3/GSMaP/v8/operational`): <https://developers.google.com/earth-engine/datasets/catalog/JAXA_GPM_L3_GSMaP_v8_operational>
  - โครงการ GSMaP (JAXA): <https://sharaku.eorc.jaxa.jp/GSMaP/> · GPM (NASA): <https://gpm.nasa.gov/>
- **สคริปต์:** `scripts/fetch_rain_gsmap.py`

### 🌧️ สถานีฝน Realtime & 💧 ระดับน้ำในแม่น้ำ/คลอง
- **คืออะไร:** ฝน 24 ชม. และระดับน้ำเทียบตลิ่ง จากสถานีวัดจริง (จุดต่อจุด)
- **ข้อมูล:** **ThaiWater** — สถาบันสารสนเทศทรัพยากรน้ำ (สสน./HII)
- **ลิงก์ตรง (API):**
  - ฝน 24 ชม.: <https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h>
  - ระดับน้ำ: <https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load>
  - พอร์ทัล: <https://www.thaiwater.net/>
- **สคริปต์:** `scripts/fetch_rain_stations.py`, `scripts/fetch_water_level.py`

### ระดับน้ำในเขื่อน
- **คืออะไร:** % ความจุน้ำในเขื่อนใหญ่ + ตัวเตือนการปล่อยน้ำ (outflow)
- **ข้อมูล:** **กรมชลประทาน (RID)** — เขื่อนขนาดใหญ่ 35 แห่ง
- **ลิงก์ตรง (API):** <https://app.rid.go.th/reservoir/api/dam/public> · เว็บ RID <https://www.rid.go.th/>
- **สคริปต์:** `scripts/fetch_dam_water.py`

### 🚨 พื้นที่เสี่ยงน้ำท่วม (สังเคราะห์ 3 แหล่ง)
- **คืออะไร:** ระดับเสี่ยงน้ำท่วม/แล้ง รายจังหวัด — **สังเคราะห์เอง** จากหลายสัญญาณ
- **ข้อมูล 3 แหล่งรวมกัน:** พยากรณ์ฝน (Open-Meteo) + ฝนดาวเทียม (GSMaP) + ระดับเขื่อน (RID) — ลิงก์ตามหัวข้อด้านบน
- **คำนวณ (เกณฑ์):**

  | ระดับ | เกณฑ์ |
  |-------|-------|
  | 🔴 เสี่ยงสูง | ฝน 7 วัน (พยากรณ์ **หรือ** ดาวเทียม อันที่สูงกว่า) ≥ **120 มม.** |
  | 🟠 เฝ้าระวัง | ≥ **60 มม.** |
  | 🟡 ระวัง | ≥ **30 มม.** |
  | 🏜 เสี่ยงแล้ง | ฝนดาวเทียม < **5 มม./7วัน** + เขื่อน < **40%** |
  | 💧 น้ำต้นทุนน้อย | เขื่อน < **30%** |

- **คิดมาอย่างไร:** รวม "คาดการณ์ + ของจริง + น้ำต้นทุน" ให้เห็นความเสี่ยงรอบด้าน · เลือกค่าที่แย่ที่สุด (worst-case)
- **⚠️ ความซื่อสัตย์:** เป็นการ**สังเคราะห์เพื่อเฝ้าระวังเบื้องต้น ไม่ใช่ประกาศเตือนภัยทางการ** — ประกาศจริงดู กรมอุตุนิยมวิทยา <https://www.tmd.go.th/> · ปภ. <https://www.disaster.go.th/>
- **สคริปต์:** `scripts/fetch_agri_warnings.py`

### 🌩️ สภาพอากาศสำคัญ (Weather Watch)
- **ข้อมูล:** **GDACS** (Global Disaster Alert and Coordination System) — พายุ/มรสุมใกล้ไทย (ชื่อพายุ ระยะห่าง ทิศทาง)
- **ลิงก์ตรง (RSS):** <https://www.gdacs.org/xml/rss.xml> · เว็บ <https://www.gdacs.org/>
- **สคริปต์:** `scripts/fetch_storm_alerts.py`

### 💧 ความชื้นในดิน (ดาวเทียม SMAP)
- **คืออะไร:** ความชื้นผิวดินเทียบความจุอุ้มน้ำ (0–100%) → บอกความเหมาะปลูก/ต้องการน้ำ
- **ดาวเทียมวัดยังไง:** ดาวเทียม **NASA SMAP** ใช้เรดิโอมิเตอร์ไมโครเวฟวัดความชื้นชั้นผิวดิน (NASA+USDA ใช้ติดตามพืชผลทั่วโลก)
- **ข้อมูล:** `NASA/SMAP/SPL4SMGP/008` band `sm_surface_wetness` (เฉลี่ย 7 วัน, 11 กม.) via GEE — ครอบคลุม 77/77 จังหวัด
- **ลิงก์ตรง:**
  - GEE dataset: <https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008>
  - ภารกิจ SMAP (NASA): <https://smap.jpl.nasa.gov/>
- **สคริปต์:** `scripts/fetch_soil_moisture.py`

---

## 3. ดาวเทียม & ดัชนีพืช

### 🌿 ดัชนีพืชพรรณ NDVI
- **คืออะไร:** ความเขียวของพืชพรรณทั้งจังหวัด (ยิ่งเขียว = ค่าสูง)
- **NDVI คืออะไร:** ดัชนีคำนวณจากแสงอินฟราเรดใกล้ (NIR) กับแสงแดงที่พืชสะท้อน — พืชสุขภาพดีสะท้อน NIR สูง
- **ข้อมูล:** NASA **MODIS MOD13A3** (NDVI รายเดือน 1 กม.) via GEE
- **ลิงก์ตรง (GEE dataset):** <https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3>
- **สคริปต์:** `scripts/fetch_ndvi.py`

### 🌾 สภาพนาข้าว (Rice EVI) — ซับซ้อนที่สุด
- **คืออะไร:** ความเขียว/สมบูรณ์ของ**ต้นข้าว เฉพาะพื้นที่นาข้าวจริง** (ไม่รวมพืชอื่น)
- **EVI คืออะไร:** *Enhanced Vegetation Index* — ดัชนีความเขียวจากแสงที่ใบสะท้อน (NIR/แดง/น้ำเงิน) คล้าย NDVI แต่แม่นกว่าในพื้นที่เขียวทึบ
- **ข้อมูล:** NASA **MODIS MOD13A3** (EVI รายเดือน 1 กม.) via GEE
- **ปัญหาที่ต้องแก้:** ดาวเทียมเห็น "ความเขียว" ทุกอย่าง (ยาง/ปาล์ม/ป่า/บ่อกุ้ง) ต้องกรองให้เหลือแค่**นาข้าว**
- **วิธีแยกนาข้าว (Rice Mask + Phenology):**
  1. **ตีกรอบเริ่มต้น:** พื้นที่นาข้าว GLAD 2020 (Class 24) ∪ พื้นที่เพาะปลูก MODIS MCD12Q1
  2. **ยืนยันด้วยวงจรชีวิตข้าว** (pixel ต้องผ่านทั้งหมด):
     - เคยมีเดือน**น้ำท่วมขัง** (LSWI > EVI — วิธี Xiao 2005) = ช่วงเตรียมดิน/ปักดำ
     - มีเดือน canopy **เขียวจริง** (peak EVI ≥ 0.40) → ตัดน้ำเปิด/บ่อกุ้ง/นาเกลือ
     - EVI **แกว่งตามฤดู** (amplitude ≥ 0.25) → ตัดยาง/ปาล์ม/ป่าที่เขียวคงที่ทั้งปี
  3. **ตัดปาล์มออกตรงๆ** ด้วย BIOPAMA Global Oil Palm layer
  4. **ตรวจสอบกับ OAE:** validate ว่าพื้นที่นาที่ตรวจได้ไม่เกินจริง (overcount)
- **คิดมาอย่างไร:** แยกนาข้าวจากพืชอื่นด้วยดาวเทียมล้วนยากมาก จึงซ้อนหลายชั้น (mask + วงจรชีวิต + cross-check สถิติราชการ)
- **ลิงก์ตรง (GEE datasets):**
  - MODIS MOD13A3 (EVI/NDVI): <https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3>
  - GLAD LCLUC 2020: <https://gee-community-catalog.org/projects/glad_gclu/> (asset `projects/glad/GLCLU2020/v2/LCLUC_2020`, class 24 = นาข้าว)
  - MODIS MCD12Q1 (Land Cover): <https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1>
  - BIOPAMA Global Oil Palm: <https://developers.google.com/earth-engine/datasets/catalog/BIOPAMA_GlobalOilPalm_v1>
- **งานวิจัยอ้างอิง (วิธี LSWI flooding):** Xiao et al. (2005), *Mapping paddy rice agriculture in southern China using multi-temporal MODIS images*, Remote Sensing of Environment — <https://doi.org/10.1016/j.rse.2004.12.009>
- **สคริปต์:** `scripts/fetch_rice_evi.py`, `scripts/validate_rice_evi.py`

---

## 4. อื่นๆ

### 🔬 ความเสี่ยงโรค/แมลง
- **คืออะไร:** ความเสี่ยงโรคข้าว/แมลง ประเมินจากอุณหภูมิ+ความชื้น (ไม่ใช่ดาวเทียม)
- **ข้อมูล:** สภาพอากาศ 7 วันจาก **Open-Meteo** — <https://api.open-meteo.com/v1/forecast>
- **คำนวณ (เกณฑ์จากงานวิจัย):**
  - โรคไหม้ (Blast): อุณหภูมิต่ำ < 22°C + ความชื้น > 80% + มีฝน
  - เพลี้ยกระโดดสีน้ำตาล: 25–30°C + ความชื้น > 80%
  - โรคกาบใบแห้ง: > 30°C + ความชื้น > 85% + มีฝน
- **สคริปต์:** `scripts/fetch_disease_risk.py`

### 🧮 แท็บจำลอง (Simulator)
- **คืออะไร:** จำลองกำไร/ขาดทุนต่อไร่ ปรับราคา/ผลผลิต/ต้นทุนได้เอง
- **ฐานคำนวณ:** สูตรกำไรเดียวกับด้านบน (ราคา × ผลผลิต − ต้นทุน OAE)

### 📰 ข่าวข้าวล่าสุด
- **ข้อมูล:** **Google News RSS** — ค้นคำข้าวเศรษฐกิจ/เกษตร ช่วง 14 วันล่าสุด
- **กรอง:** ต้องมีคำข้าว/ชาวนา · ตัดพืชอื่น (ข้าวสาลี/ข้าวโพด)/อาหารจานเดียว/สำนักต่างชาติแปลอัตโนมัติ · dedupe · เก็บใหม่สุด 8 ข่าว
- **แสดง:** หัวข้อ + ที่มา + ลิงก์ต้นฉบับ (ไม่ scrape เนื้อข่าว — ไม่มีปัญหาลิขสิทธิ์)
- **ลิงก์ตรง (RSS):** <https://news.google.com/rss/search?q=ราคาข้าว&hl=th&gl=TH&ceid=TH:th>
- **สคริปต์:** `scripts/fetch_rice_news.py`

---

## ตารางสรุปแหล่งข้อมูล + ลิงก์

| หัวข้อ | แหล่ง | ประเภท | ลิงก์ตรง (endpoint/หน้า) | สคริปต์ |
|--------|-------|--------|--------------------------|---------|
| ผลผลิต/ผลผลิตต่อไร่/เนื้อที่ นาปี | OAE ตาราง 1.4 | ราชการ | [catalog.oae…ba103542](https://catalog.oae.go.th/dataset/ba103542-830f-418a-b614-9645ebbe1a93) | build_rice_dataset.py |
| ผลผลิต/เนื้อที่ นาปรัง | OAE naprang | ราชการ | [catalog.oae…dataoae1104](https://catalog.oae.go.th/dataset/dataoae1104) | build_naprang_data.py |
| ราคาโรงสี | สมาคมโรงสีข้าวไทย | สมาคม | [thairicemillers.org](http://www.thairicemillers.org/images/introc_1429264173/) | fetch_miller_prices.py |
| ราคา OAE (สำรอง) | OAE CKAN | ราชการ | [catalog.oae…datastore_search](https://catalog.oae.go.th/api/3/action/datastore_search) | fetch_oae_prices.py |
| ราคาส่งออก FOB | TREA | สมาคม | [thairiceexporters…price.htm](https://www.thairiceexporters.or.th/price.htm) | fetch_trea_fob.py |
| กำไร/ขาดทุน | คำนวณ (ราคา×ผลผลิต−ต้นทุน) | คำนวณ | — | (index.html) |
| ราคาปุ๋ย / อัตราปุ๋ย | MOC / กรมการข้าว | ราชการ | [dit.go.th](https://www.dit.go.th/) · [ricethailand.go.th](https://www.ricethailand.go.th/) | (index.html) |
| ฟางข้าว | OAE × RPR/SAF (พพ.) | คำนวณ | [kc.dede.go.th](https://kc.dede.go.th/) | (index.html) |
| โรงไฟฟ้าชีวมวล | DEDE 2565 | ราชการ | [kc.dede…p=231](https://kc.dede.go.th/knowledge-view.aspx?p=231) | data/biomass-plants.json |
| โรงสีข้าว | DIT (Excel export) | ราชการ | [dit.go.th](https://www.dit.go.th/) | build_rice_mills.py |
| ครัวเรือนเกษตรกร | OAE 2566 | ราชการ | [catalog.oae.go.th](https://catalog.oae.go.th/) | data/farmer_households.csv |
| พยากรณ์ฝน 7 วัน | Open-Meteo (p90) | โมเดล (API) | [api.open-meteo…forecast](https://api.open-meteo.com/v1/forecast) | fetch_rain_forecast.py |
| ฝนรวม 7 วัน (ดาวเทียม) | JAXA GSMaP v8 | 🛰️ ดาวเทียม (GEE) | [GEE: GSMaP v8](https://developers.google.com/earth-engine/datasets/catalog/JAXA_GPM_L3_GSMaP_v8_operational) | fetch_rain_gsmap.py |
| สถานีฝน 24h | ThaiWater | ราชการ (API) | [api-v3.thaiwater…rain_24h](https://api-v3.thaiwater.net/api/v1/thaiwater30/public/rain_24h) | fetch_rain_stations.py |
| ระดับน้ำแม่น้ำ | ThaiWater | ราชการ (API) | [api-v3.thaiwater…waterlevel](https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel_load) | fetch_water_level.py |
| ระดับน้ำเขื่อน | กรมชลประทาน (RID) | ราชการ (API) | [app.rid.go.th…dam/public](https://app.rid.go.th/reservoir/api/dam/public) | fetch_dam_water.py |
| พื้นที่เสี่ยงน้ำท่วม | สังเคราะห์ (3 แหล่ง) | สังเคราะห์ | (รวม Open-Meteo+GSMaP+RID) | fetch_agri_warnings.py |
| สภาพอากาศสำคัญ | GDACS | ต่างประเทศ (RSS) | [gdacs.org/xml/rss.xml](https://www.gdacs.org/xml/rss.xml) | fetch_storm_alerts.py |
| ความชื้นในดิน | NASA SMAP L4 | 🛰️ ดาวเทียม (GEE) | [GEE: SMAP L4](https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008) | fetch_soil_moisture.py |
| ดัชนีพืชพรรณ NDVI | NASA MODIS MOD13A3 | 🛰️ ดาวเทียม (GEE) | [GEE: MOD13A3](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3) | fetch_ndvi.py |
| สภาพนาข้าว (Rice EVI) | MODIS+GLAD+phenology | 🛰️ ดาวเทียม+คำนวณ | [GEE: MOD13A3](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13A3) · [Xiao 2005](https://doi.org/10.1016/j.rse.2004.12.009) | fetch_rice_evi.py |
| ความเสี่ยงโรค/แมลง | Open-Meteo + เกณฑ์วิจัย | คำนวณ (API) | [api.open-meteo…forecast](https://api.open-meteo.com/v1/forecast) | fetch_disease_risk.py |
| ข่าวข้าว | Google News RSS | รวมข่าว (RSS) | [news.google.com/rss/search](https://news.google.com/rss/search?q=ราคาข้าว&hl=th&gl=TH&ceid=TH:th) | fetch_rice_news.py |

---

## หมายเหตุสำคัญ

- **ข้อมูลนาปีเท่านั้น** สำหรับ layer ผลผลิต/ผลผลิตต่อไร่/เนื้อที่ (จาก OAE ตาราง 1.4) — ยกเว้น layer นาปรังที่ระบุชัด
- **Google Earth Engine (GEE)** = แพลตฟอร์มประมวลผลข้อมูลดาวเทียมของ Google ใช้ดึง/คำนวณข้อมูลดาวเทียมทั้งหมด (GSMaP, SMAP, MODIS, GLAD, oil-palm) — <https://earthengine.google.com/>
- **การอัปเดตอัตโนมัติ** ทำผ่าน GitHub Actions (cron) — ดูรายการงานใน [`.github/workflows/`](.github/workflows/)
- **ค่าฝังในโค้ด** (ต้นทุน OAE, ราคาปุ๋ย MOC, อัตราปุ๋ย DOA, RPR/SAF) อยู่ใน `index.html` — อัปเดตด้วยมือจากเอกสารต้นทาง
- ปีในเว็บเป็น **พ.ศ. (Buddhist Era)**

_ปรับปรุงล่าสุด: กรกฎาคม 2569 · ดู [CHANGELOG.md](CHANGELOG.md) สำหรับประวัติการพัฒนา_
