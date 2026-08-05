# 🌾 Thailand Rice Map — Interactive Dashboard

แผนที่ choropleth ข้าวนาปีไทยรายจังหวัด 77 จังหวัด  
**Thailand Paddy Rice Intelligence** — Provincial choropleth map

[![Live Demo](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-brightgreen)](https://ton-munoi99.github.io/rice-map/)

---

## ✨ Features

- 🗺️ **แผนที่ Choropleth** — 77 จังหวัด, ซูม/แพน/คลิกเลือกได้, drill-down รายอำเภอ
- 📊 **~20 Data Layers** — ผลผลิต/ผลผลิตต่อไร่/เนื้อที่/ราคา/กำไร, ฝน+พยากรณ์, ความชื้นดิน,
  NDVI, สภาพนาข้าว, เขื่อน, ระดับน้ำ, เตือนน้ำท่วม, โรค/แมลง, โรงสี, โรงไฟฟ้าชีวมวล, ฟางข้าว
- 🌾 **2 ประเภทข้าว** — ข้าวขาว (Other Indica) และหอมมะลิ (Jasmine) · ข้อมูลนาปี + นาปรัง
- 👨‍🌾 **หน้าสำหรับชาวนา** (`farmer.html`) — มุมมองจังหวัดเดียว ภาษาเข้าใจง่าย + แจ้งเตือน Telegram
- 🌐 **Bilingual** — ภาษาไทย / English · 🔗 แชร์สถานะแผนที่ผ่าน URL hash
- 🤖 **อัปเดตอัตโนมัติ** — GitHub Actions cron ~16 workflow ดึงข้อมูลสดรายวัน/รายสัปดาห์

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

MIT License — ข้อมูลจาก OAE และกรมการข้าว กระทรวงเกษตรและสหกรณ์
