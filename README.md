# 🌾 Thailand Rice Map — Interactive Dashboard

แผนที่ choropleth ข้าวนาปีไทยรายจังหวัด 77 จังหวัด  
**Thailand Paddy Rice Intelligence** — Provincial choropleth map

[![Live Demo](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-brightgreen)](https://ton-munoi99.github.io/rice-map/)

---

## ✨ Features

- 🗺️ **แผนที่ Choropleth** — 77 จังหวัด, ซูม/แพน/คลิกเลือกได้, drill-down รายอำเภอ
- 📊 **21 Data Layers** — ผลผลิต/ผลผลิตต่อไร่/เนื้อที่/ราคา/กำไร, ฝน+พยากรณ์ (รวม TMD 48 ชม.),
  ความชื้นดิน, สภาพนาข้าว (EVI), เขื่อน, ระดับน้ำ, เตือนน้ำท่วม, **น้ำท่วมวัดจริงจากสถานีวัดน้ำ**,
  โรงสี, โรงไฟฟ้าชีวมวล, ฟางข้าว
- 🌾 **2 ประเภทข้าว** — ข้าวขาว (Other Indica) และหอมมะลิ (Jasmine) · ข้อมูลนาปี + นาปรัง
- 👨‍🌾 **หน้าสำหรับชาวนา** (`farmer.html`) — มุมมองจังหวัดเดียว ภาษาเข้าใจง่าย
- 🌐 **Bilingual** — ภาษาไทย / English · 🔗 แชร์สถานะแผนที่ผ่าน URL hash
- 🤖 **อัปเดตอัตโนมัติ** — GitHub Actions cron 19 workflow ดึงข้อมูลสดรายวัน/รายสัปดาห์

> รายละเอียดครบทุก layer (ใช้ข้อมูลอะไร คำนวณอย่างไร ลิงก์ต้นทาง) อยู่ใน
> **[DATA_SOURCES.md](DATA_SOURCES.md)** · สถาปัตยกรรมโค้ดและคำสั่ง dev อยู่ใน
> **[CLAUDE.md](CLAUDE.md)** · ประวัติการพัฒนาอยู่ใน **[CHANGELOG.md](CHANGELOG.md)**

---

## 🚀 Run Locally

ต้องเสิร์ฟผ่าน HTTP — เปิดไฟล์ตรงๆ ด้วย `file://` ไม่ได้ เพราะ `fetch()` จะถูกบล็อก

```bash
python -m http.server 8888
# แล้วเปิด http://localhost:8888
```

ไม่มี build step / npm / bundler

---

## 🌐 Live Demo

https://ton-munoi99.github.io/rice-map/

---

## 📄 License

**โค้ด** (`index.html`, `farmer.html`, `scripts/`, `.github/`) — [MIT](LICENSE)

**ข้อมูล** (`data/`, `rice-data.*`, `thailand-data.js`, `naprang-data.js`) — **ไม่ใช่ MIT**
แต่ละชุดเป็นของหน่วยงานต้นทางและมีสัญญาอนุญาตของตัวเอง ดูรายแหล่งได้ที่
**[DATA_SOURCES.md](DATA_SOURCES.md#สัญญาอนุญาตรายแหล่ง)**

> ⚠️ **ก่อนใช้เชิงพาณิชย์** — ข้อมูลพยากรณ์อากาศมาจาก Open-Meteo Free API ซึ่ง
> **อนุญาตเฉพาะการใช้ที่ไม่แสวงหากำไร** (CC BY 4.0 + non-commercial) ถ้าจะใช้
> เชิงพาณิชย์ต้องสมัครแพ็กเกจกับ Open-Meteo เอง และตรวจสัญญาอนุญาตของแหล่งอื่นด้วย
