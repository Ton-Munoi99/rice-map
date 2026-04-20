# 🌾 Thailand Rice Map — Interactive Dashboard

แผนที่ choropleth ข้าวนาปีไทยรายจังหวัด 77 จังหวัด  
**Thailand Paddy Rice Intelligence** — Provincial choropleth map

[![Live Demo](https://img.shields.io/badge/Live%20Demo-GitHub%20Pages-brightgreen)](https://ton-munoi99.github.io/rice-map/)

---

## ✨ Features

- 🗺️ **แผนที่ Choropleth** — 77 จังหวัด, ซูม/แพน/คลิกเลือกได้
- 📊 **4 Data Layers** — ผลผลิต (ตัน), ผลผลิตต่อไร่, เนื้อที่เก็บเกี่ยว, ราคา
- 🌾 **2 ประเภทข้าว** — ข้าวขาว (Other Indica) และหอมมะลิ (Jasmine)
- 📅 **ปี 2565–2569** — ข้อมูลจริง OAE (2565–2567) + ประมาณการแนวโน้ม (2568–2569)
- 🌐 **Bilingual** — ภาษาไทย / English
- 📥 **Import/Export CSV** — นำเข้าหรือส่งออกข้อมูลได้
- 📱 **Responsive** — รองรับทุกขนาดหน้าจอ

---

## 📁 File Structure

```
rice-map/
├── index.html          ← Main app (HTML + CSS + JS)
├── rice-data.js        ← ข้อมูลผลผลิตข้าวรายจังหวัด
├── thailand-data.js    ← SVG paths แผนที่ 77 จังหวัด
└── scripts/
    ├── estimate_2568_2569.js   ← Trend estimation script
    └── check_syntax.js        ← JS syntax checker
```

---

## 📊 Data Sources

| ข้อมูล | แหล่งที่มา | ปี |
|---|---|---|
| ผลผลิต / ผลผลิตต่อไร่ / เนื้อที่เก็บเกี่ยว | OAE (สศก.) รายจังหวัด | 2565–2567 |
| ราคาข้าวเปลือก | สมาคมโรงสีข้าวไทย | 2568–2569 |
| เนื้อที่เพาะปลูก (calibration) | กรมการข้าว | 2568 |
| ประมาณการ (📊 EST) | avg YoY growth 2565–2567 | 2568–2569 |

---

## 🚀 How to Use

เปิด `index.html` ในเบราว์เซอร์ได้เลย — ไม่ต้องติดตั้ง dependencies ใดๆ

---

## 🌐 Live Demo

https://ton-munoi99.github.io/rice-map/

---

## 📄 License

MIT License — ข้อมูลจาก OAE และกรมการข้าว กระทรวงเกษตรและสหกรณ์
