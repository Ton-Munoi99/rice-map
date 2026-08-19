# แหล่งข้อมูลและวิธีคำนวณ — Thailand Rice Intelligence Map

เอกสารนี้อธิบายทุกชั้นข้อมูล (layer) และวิดเจ็ตในเว็บว่า **คืออะไร · ใช้ข้อมูลอะไร ·
คำนวณอย่างไร · คิดมาอย่างไร · อ้างอิงจากไหน (พร้อมลิงก์ตรง)** เพื่อความโปร่งใสและตรวจสอบได้

> **หลักการ:** ข้อมูลราชการ/ดาวเทียมใช้ตามต้นฉบับ · ค่าที่ต้องคำนวณระบุสูตรและค่าคงที่ชัดเจน ·
> ชั้นที่ "สังเคราะห์เพื่อเฝ้าระวัง" (เช่น พื้นที่เสี่ยงน้ำท่วม) ระบุว่าไม่ใช่ประกาศทางการ ·
> ทุก reference เป็นลิงก์ตรงไปหน้า/endpoint/ไฟล์ที่ระบบดึงจริง

สารบัญ: [ผลผลิต & เศรษฐกิจข้าว](#1-ผลผลิต--เศรษฐกิจข้าว) · [น้ำ & สภาพอากาศ](#2-น้ำ--สภาพอากาศ) ·
[ดาวเทียม & ดัชนีพืช](#3-ดาวเทียม--ดัชนีพืช) · [อื่นๆ](#4-อื่นๆ) · [ตารางสรุป + ลิงก์](#ตารางสรุปแหล่งข้อมูล--ลิงก์) ·
[สัญญาอนุญาต](#สัญญาอนุญาตรายแหล่ง)

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
- **ราคา OAE (ระดับชาติ, รายสัปดาห์):** <https://agriapi.nabc.go.th/api/weekly-prices/product> — ราคาที่เกษตรกรขายได้ ข้าวเปลือกเจ้า/หอมมะลิ ความชื้น 15% ย้อนถึง พ.ศ. 2554 · เปิดสาธารณะ ไม่ต้องมี key
  - หน้า dataset ต้นทาง: <https://catalog.oae.go.th/dataset/weekly-prices-paddy>
  - *เดิมใช้ CKAN `datastore_search` resource `c72f9a58-…` ซึ่งตอบ 403 ตั้งแต่ 20 พ.ค. 2569 — ตัว catalog ชี้มาที่ API ใหม่นี้แทน*
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
- **ข้อมูล:** **ราคาจำหน่ายปลีกแนะนำ** (เพดาน ไม่ใช่ราคาตลาด) จาก **สำนักงาน กกร./กรมการค้าภายใน** · 3 สูตรนำเข้า (46-0-0, 18-46-0, 0-0-60) อัปเดตตาม **ประกาศฉบับที่ 7 ลงวันที่ 11 มิ.ย. 2569** (ยกเลิกฉบับที่ 4) — ยูเรีย 1,408–1,576 ฿/กระสอบ 50 กก. รายจังหวัด/ยี่ห้อ · สูตรอื่นยังเป็นค่าจากฉบับที่ 4 (29 เม.ย. 2569) เพราะไม่ได้ประกาศใหม่ · อัตราใส่ปุ๋ยแนะนำจาก **กรมการข้าว (DOA)** เช่น ยูเรีย 46-0-0 = 10 กก./ไร่
- **ข้อควรระวัง:** ประกาศออกถี่ (ฉบับ 4 → 6 → 7 → 8/9 บางฉบับเจาะจงรายจังหวัด) ต้องตามอัปเดตด้วยมือ · ราคาซื้อขายจริงหน้าร้านอาจสูงกว่าราคาแนะนำ
- **ราคาซื้อขายจริง (ตัวอย่างบางจังหวัด):** ตารางเพิ่มเติมใต้ราคาแนะนำ — เก็บจากประกาศสำนักงานพาณิชย์จังหวัด/สหกรณ์การเกษตรทีละแห่ง (ไม่ใช่การสำรวจทั่วประเทศ) ครอบคลุม 6 จังหวัด (หนองคาย/ท่าบ่อ, อุทัยธานี, ตรัง, สิงห์บุรี, สกลนคร, ขอนแก่น) ช่วง มี.ค.–ก.ค. 2569 พร้อมลิงก์ต้นทางต่อแถว — ดู `FERT_REAL_SAMPLES` ใน `index.html`
- **คำนวณ:** จำนวนกระสอบยูเรียต่อข้าว 1 ตัน = ราคาข้าว ÷ ราคายูเรีย (ค่ากลาง MOC)
- **ลิงก์:** ราคาสินค้า MOC <https://www.dit.go.th/> · คำแนะนำการใช้ปุ๋ย กรมการข้าว <https://www.ricethailand.go.th/>
- **หมายเหตุ:** ค่าฝังใน `index.html` (`FERT_MOC`, `FERT_REAL_SAMPLES`, `FERT_DOA_RATES`) อัปเดตด้วยมือจากผลสำรวจ

### 🌾 ฟางข้าว
- **คืออะไร:** ปริมาณฟางที่เกิดจากการปลูกข้าว + "ฟางเหลือใช้" (มักถูกเผา → PM2.5 หรือใช้เป็นเชื้อเพลิงชีวมวล)
- **ข้อมูล:** ผลผลิตข้าว OAE (นาปี ขาว+หอมมะลิ + นาปรัง) — แหล่งเดียวกับด้านบน
- **คำนวณ:**
  1. ฟางทั้งหมด = ผลผลิตข้าว × **RPR 1.169** *(Residue-to-Product Ratio: ข้าว 1 ตัน → ฟาง 1.169 ตัน)*
  2. ฟางเหลือใช้ = ฟางทั้งหมด × **SAF 0.583** *(Surplus Availability Factor: หลังหักที่ชาวนาใช้เอง เหลือ 58.3%)*
- **อ้างอิง:** ค่า RPR/SAF จาก **กรมพัฒนาพลังงานทดแทนและอนุรักษ์พลังงาน (พพ./DEDE)** — <https://www.dede.go.th/> · ศูนย์องค์ความรู้ฯ <https://kc.dede.go.th/>

### 🌊 ระดับน้ำแม่น้ำโขง (MRC)
- **คืออะไร:** ระดับน้ำโขงสายหลัก 31 สถานี (ไทย 9) พร้อม **เกณฑ์เตือน (alarmStage) และเกณฑ์วิกฤต (floodStage) ของแต่ละสถานี** และเวลาที่วัด · แสดงเป็นการ์ดในรายละเอียดจังหวัดริมโขง
- **ทำไมต้องมี:** layer เตือนน้ำท่วมของเราคำนวณจาก**ฝน** แต่โขงขึ้นจาก**การไหลของน้ำต้นทาง** จังหวัดริมโขงจึงท่วมได้ทั้งที่ฝนไม่ตก — ส.ค. 2569 ข่าวรายงานนครพนม 12.01 ม. เกินระดับวิกฤต 12.00 ม. ขณะที่ระบบเราเห็นแค่ฝนในพื้นที่ · ThaiWater ไม่มีสถานีบนโขงสายหลักเลย
- **ข้อมูล:** **Mekong River Commission (MRC)** — near real-time telemetry (~ทุก 15 นาที)
- **ลิงก์ตรง:**
  - เว็บติดตาม: <https://monitoring.mrcmekong.org/>
  - API (ไม่ต้องมี key): `https://api.mrcmekong.org/api/v1/time-series/telemetry/recent/stations`
- **สคริปต์/ข้อมูล:** `scripts/fetch_mekong_level.py` → `data/mekong-level.json` (workflow `update-mekong.yml` รายวัน)

**ข้อควรรู้:**
- `floodStage` ของนครพนม = 12.0 ตรงกับ "ระดับวิกฤต 12.00 เมตร" ที่ข่าวราชการอ้าง — ยืนยันว่าเป็นเกณฑ์ชุดเดียวกัน
- แมปสถานี→จังหวัด **จากพิกัดจริง ไม่ใช่ชื่อสถานี** · บึงกาฬไม่มี bbox ใน `districts-geo.json` (แยกจากหนองคายปี 2554 หลัง GAUL) และ bbox หนองคายยังกินพื้นที่บึงกาฬ จึงใช้รูปหลายเหลี่ยมจาก `riceutils._BUENG_KAN_POLY` และตัดสินด้วยกรอบที่ศูนย์กลางใกล้กว่าเมื่อกรอบซ้อนกัน
- 2 สถานี (อำนาจเจริญ, เขมราฐ) ต้นทางไม่ให้เกณฑ์ → สถานะเป็น `nothreshold` แสดงค่าระดับได้แต่บอกไม่ได้ว่าวิกฤตหรือยัง
- เก็บสถานีเหนือไทย (จีน/ลาว) ไว้ด้วย เพราะนำหน้าช่วงไทยหลายวัน ใช้ดูล่วงหน้าได้ (ยังไม่ได้ใช้ในหน้าเว็บ)
- **สัญญาอนุญาต:** API เปิดสาธารณะไม่ต้องสมัคร แต่ MRC ไม่ได้ระบุเงื่อนไขของ endpoint นี้ไว้ตรงๆ (Terms ที่เผยแพร่เป็นของ Data Portal ซึ่งเป็นคนละบริการและมีค่าธรรมเนียม) · ใช้โดยอ้างอิงแหล่งที่มาชัดเจน · โปรเจกต์นี้ติด non-commercial จาก Open-Meteo อยู่แล้ว จึงไม่ได้เพิ่มข้อจำกัดชนิดใหม่

### ⚡ โรงไฟฟ้าชีวมวล
- **คืออะไร:** ทะเบียนโรงไฟฟ้าชีวมวลที่ขายไฟเข้าระบบ **230 แห่ง 54 จังหวัด รวม 3,518.84 MW** พร้อมชื่อโรง พิกัด ตำบล/อำเภอ และชนิดเชื้อเพลิง · การ์ด "ตลาดฟาง/แกลบ" จับคู่ฟางเหลือใช้ของจังหวัดกับโรงที่ใช้เชื้อเพลิงจากข้าว (ระดับจังหวัด/ภาค)
- **ข้อมูล:** **DEDE** — layer `gisdede:9000_2569_biomassdec68` ข้อมูล ณ ธันวาคม 2568 ดึงผ่าน **GeoServer WFS** เป็น GeoJSON
- **ลิงก์ตรง:**
  - WFS endpoint: <https://gis.dede.go.th/geoserver/wfs> (`request=GetFeature&typeName=gisdede:9000_2569_biomassdec68&outputFormat=application/json`)
  - หน้าชุดข้อมูลใน Data Catalog: <https://pei.dede.go.th/dataset/gis-002>
  - แผนที่ PDF (ภาพ ไม่มี text layer): <https://gis.dede.go.th/gallery-map-list.aspx>
- **สคริปต์/ข้อมูล:** `scripts/fetch_biomass_plants.py` → `data/biomass-plants.json` (workflow `update-biomass.yml` รันปีละครั้ง)

**ข้อควรรู้เรื่องความแม่น:**
- **46 โรง (20%) ต้นทางไม่ระบุชนิดเชื้อเพลิง** (ฟิลด์เป็นค่า default `Renewable`/`Biomass`) และกินกำลังผลิตราว 40% ของทั้งหมด — โรงเหล่านี้อาจใช้ฟาง/แกลบจริงแต่ไม่ปรากฏในตัวเลข 84 โรง
- ธง `rice_straw`/`rice_husks` มาจาก 2 ที่ ดูได้จากฟิลด์ `fuel_src`:
  `dede2569` = ทะเบียนระบุแกลบ/ฟางเอง · `survey2565` = ยกมาจากแบบสอบถามปี 2565 (โรงเคยแจ้งว่ารับซื้อ ไม่ยืนยันว่าตอนนี้ยังใช้) · `both` = ตรงกันทั้งคู่ · ในเว็บติดดอกจัน `*` กำกับตัวที่มาจากสำรวจ 2565
- การยกธงจากปี 2565 จับคู่ด้วยชื่อ **ภายในจังหวัดเดียวกันเท่านั้น** — ถ้า fuzzy ข้ามจังหวัดจะจับ "มิตรผล ด่านช้าง" (สุพรรณบุรี) ไปชนกับ "มิตรผล ภูเวียง" (ขอนแก่น) ซึ่งคนละโรง
- ต้นทางมี **ชื่อโรงซ้ำในจังหวัดเดียวกัน 3 คู่** (คนละหน่วยผลิต/คนละพิกัด) — ไม่ตัดออก เพราะยอดรวมต้องตรงกับที่ พพ. ประกาศ (230 โรง)
- ข้อมูลชุดเดิม (สำรวจ 2565) มีเพียง 79 โรง 35 จังหวัด 1,461 MW เพราะนับเฉพาะโรงที่ตอบแบบสอบถาม — ต่ำกว่าความจริงราว 3 เท่า

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
| โรงไฟฟ้าชีวมวล | DEDE ธ.ค. 2568 | ราชการ | [gis.dede WFS](https://gis.dede.go.th/geoserver/wfs) · [pei.dede gis-002](https://pei.dede.go.th/dataset/gis-002) | data/biomass-plants.json |
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

---

## สัญญาอนุญาตรายแหล่ง

**โค้ดของโปรเจกต์เป็น MIT แต่ข้อมูลไม่ใช่** — แต่ละชุดเป็นของหน่วยงานต้นทางและมีเงื่อนไขของตัวเอง
ตารางนี้ระบุเท่าที่ตรวจสอบได้จากหน้าต้นทางจริง ช่องที่เขียนว่า "ไม่ได้ระบุ" คือหาไม่พบ ไม่ใช่แปลว่าใช้ได้อิสระ

| แหล่ง | ใช้กับ | สัญญาอนุญาต | ใช้เชิงพาณิชย์ |
|---|---|---|---|
| **Open-Meteo** (Free API) | ฝนพยากรณ์/ย้อนหลัง, อากาศรายจังหวัด, ดัชนีโรค | CC BY 4.0 + **non-commercial** | ❌ **ห้าม** — ต้องซื้อแพ็กเกจ |
| OAE (สศก.) | ผลผลิต/เนื้อที่/ราคา/นาปรัง | Open Data Common | ✅ |
| พพ. (DEDE) | โรงไฟฟ้าชีวมวล | Open Data Common | ✅ |
| NASA (SMAP, MODIS) | ความชื้นดิน, NDVI | Full & open data policy | ✅ |
| JAXA GSMaP (ผ่าน GEE) | ฝนดาวเทียม | Terms of use — ต้องอ้างอิงแหล่ง | ⚠️ ตรวจก่อน |
| ThaiWater (สสน./HII) | ระดับน้ำ, สถานีฝน | ไม่ได้ระบุ | ⚠️ ตรวจก่อน |
| MRC (Mekong River Commission) | ระดับน้ำโขง | ไม่ได้ระบุสำหรับ API นี้ | ⚠️ ตรวจก่อน |
| กรมชลประทาน (RID) | ระดับน้ำเขื่อน | ไม่ได้ระบุ | ⚠️ ตรวจก่อน |
| กรมการค้าภายใน (DIT) | โรงสีข้าว | ไม่ได้ระบุ | ⚠️ ตรวจก่อน |
| สมาคมโรงสีข้าวไทย | ราคารับซื้อ | เอกชน — ไม่ได้ระบุ | ⚠️ ตรวจก่อน |
| สมาคมผู้ส่งออกข้าวไทย (TREA) | ราคา FOB | เอกชน — ไม่ได้ระบุ | ⚠️ ตรวจก่อน |
| Google News RSS | ข่าวข้าว | เก็บเฉพาะหัวข้อ + ลิงก์ต้นฉบับ ไม่ดึงเนื้อข่าว | ⚠️ ลิขสิทธิ์เป็นของสำนักข่าว |

### ข้อจำกัดที่ต้องรู้

- **Open-Meteo เป็นตัวที่เข้มที่สุด** ถ้อยคำในเงื่อนไข: *"You may only use the free API services for
  non-commercial purposes."* กระทบไฟล์ `rain-daily`, `rain-forecast`, `weather-province`,
  `weather-forecast`, `disease-risk` และทุก layer ที่คำนวณต่อจากนั้น (รวมเตือนน้ำท่วม)
- **ข่าว** — เก็บแค่หัวข้อกับลิงก์โดยตั้งใจ ไม่ทำสำเนาเนื้อข่าว ลิขสิทธิ์ยังเป็นของสำนักข่าวเจ้าของ
- **ที่พิจารณาแล้วยังไม่นำเข้า:** เขตความเหมาะสมที่ดินปลูกข้าว (LDD/Agri-Map) เป็น **CC BY-NC-ND**
  ซึ่งห้ามทั้งการใช้เชิงพาณิชย์และการดัดแปลง (การรวมยอดตำบล→จังหวัดเข้าข่ายดัดแปลง)
  จึงยังไม่ดึงเข้ามา รอสอบถามสิทธิ์จาก `lpd_1@ldd.go.th` ก่อน

> เอกสารนี้เป็นการรวบรวมเพื่อความโปร่งใส **ไม่ใช่คำแนะนำทางกฎหมาย** ถ้าจะใช้เชิงพาณิชย์
> ควรตรวจสอบกับเจ้าของข้อมูลแต่ละรายโดยตรง

---

_ปรับปรุงล่าสุด: สิงหาคม 2569 · ดู [CHANGELOG.md](CHANGELOG.md) สำหรับประวัติการพัฒนา_
