/**
 * estimate_2568_2569.js
 * ─────────────────────
 * คำนวณ Trend Estimation สำหรับปี 2568–2569
 * โดยใช้ค่าเฉลี่ย YoY growth rate จากปี 2565→2566→2567
 *
 * วิธีใช้:
 *   node scripts/estimate_2568_2569.js
 *
 * จะเขียนทับ rice-data.js ด้วยข้อมูลที่มี source = "estimated_trend"
 */

const fs = require('fs');
const path = require('path');

// ─────────────── CONFIG ───────────────
const DATA_FILE  = path.join(__dirname, '..', 'rice-data.js');
const OUT_FILE   = DATA_FILE;  // เขียนทับเลย (backup ก่อน)
const BACKUP     = DATA_FILE.replace('.js', '_bak_' + Date.now() + '.js');

// ข้อมูลกรมการข้าว ปี 2568/69 (ณ 2 มี.ค. 2569) — ระดับภาค (ไร่)
// ใช้เป็น calibration ratio เทียบกับยอดรวม OAE_2567 เพื่อ scale area_planted_2568
const RD_2568_NATIONAL_PLANTED = 58_550_783; // ไร่ (กรมการข้าว)
const RD_2568_REGIONAL = {
  northeast: 36_509_155,
  north:     14_115_202,
  central:    7_477_548,
  south:        448_878,
  east:               0, // ไม่แยกรายงาน รวมในกลาง
};

// CAGR cap: จำกัดไม่ให้ growth rate เกิน ±30% ต่อปี เพื่อป้องกัน outlier
const MAX_RATE = 0.30;
const MIN_RATE = -0.30;

// ─────────────── READ DATA ───────────────
console.log('📖 Reading', DATA_FILE);
const raw = fs.readFileSync(DATA_FILE, 'utf-8');

// ดึง array JSON ออกจากไฟล์ JS
const match = raw.match(/window\.RICE_DATA_ROWS\s*=\s*(\[[\s\S]*?\]);?\s*$/);
if (!match) {
  console.error('❌ ไม่พบ RICE_DATA_ROWS ใน', DATA_FILE);
  process.exit(1);
}

const rows = JSON.parse(match[1]);
console.log(`✅ โหลดข้อมูล ${rows.length.toLocaleString()} rows`);

// ─────────────── BUILD INDEX ───────────────
// key: `${province_en}|${rice_type}` → { year → row_object }
const idx = new Map();
for (const row of rows) {
  const key = `${row.province_en}|${row.rice_type}`;
  if (!idx.has(key)) idx.set(key, {});
  idx.get(key)[row.year] = row;
}

// ─────────────── COMPUTE OAE 2567 REGIONAL TOTALS ───────────────
// ใช้สำหรับคำนวณ ratio กับ กรมการข้าว
const oae2567AreaByRegion = {};
for (const [key, yearMap] of idx.entries()) {
  const row2567 = yearMap['2567'];
  if (!row2567 || row2567.area_planted <= 0) continue;
  const reg = row2567.region || 'central';
  oae2567AreaByRegion[reg] = (oae2567AreaByRegion[reg] || 0) + row2567.area_planted;
}

// คำนวณ regional scale factor (กรมการข้าว / OAE 2567)
const areaScaleFactor = {};
for (const reg of Object.keys(RD_2568_REGIONAL)) {
  if (RD_2568_REGIONAL[reg] > 0 && oae2567AreaByRegion[reg] > 0) {
    areaScaleFactor[reg] = RD_2568_REGIONAL[reg] / oae2567AreaByRegion[reg];
  } else {
    areaScaleFactor[reg] = 1.0;
  }
}

console.log('\n📊 Regional Area Scale Factor (กรมการข้าว_2568 / OAE_2567_planted):');
for (const [reg, factor] of Object.entries(areaScaleFactor)) {
  console.log(`  ${reg.padEnd(12)}: ${factor.toFixed(4)} (OAE_2567=${(oae2567AreaByRegion[reg]||0).toLocaleString()} ไร่  →  RD_2568=${(RD_2568_REGIONAL[reg]||0).toLocaleString()} ไร่)`);
}

// ─────────────── HELPER FUNCTIONS ───────────────
function clampRate(r) {
  if (!isFinite(r)) return 0;
  return Math.max(MIN_RATE, Math.min(MAX_RATE, r));
}

function yoyRate(prev, curr) {
  if (!prev || prev <= 0) return NaN;
  return (curr - prev) / prev;
}

function avgGrowthRate(y65, y66, y67) {
  const r1 = yoyRate(y65, y66);
  const r2 = yoyRate(y66, y67);
  const valid = [r1, r2].filter(isFinite);
  if (!valid.length) return 0;
  return clampRate(valid.reduce((s, v) => s + v, 0) / valid.length);
}

function estimate(base, rate, steps) {
  if (!base || base <= 0) return 0;
  return Math.round(base * Math.pow(1 + rate, steps));
}

// ─────────────── APPLY ESTIMATES ───────────────
let estimated = 0;
let alreadyHasData = 0;

for (const [key, yearMap] of idx.entries()) {
  const row65 = yearMap['2565'];
  const row66 = yearMap['2566'];
  const row67 = yearMap['2567'];

  if (!row67) continue; // ต้องมีข้อมูล 2567 อย่างน้อย

  const region = row67.region || 'central';

  // คำนวณ avg growth rate สำหรับแต่ละ metric
  const r_prod = avgGrowthRate(row65?.production, row66?.production, row67.production);
  const r_yield = avgGrowthRate(row65?.yield, row66?.yield, row67.yield);
  const r_area  = avgGrowthRate(row65?.area, row66?.area, row67.area);
  const r_area_p = avgGrowthRate(row65?.area_planted, row66?.area_planted, row67.area_planted);
  const r_yp    = avgGrowthRate(row65?.yield_planted, row66?.yield_planted, row67.yield_planted);

  // scale factor สำหรับ area_planted (กรมการข้าว calibration)
  const sf = areaScaleFactor[region] || 1.0;

  for (const yrStr of ['2568', '2569']) {
    const row = yearMap[yrStr];
    if (!row) continue;

    // ถ้ามีข้อมูล production จริงแล้ว ข้ามไป
    if (row.production > 0 || row.area > 0 || row.yield > 0) {
      alreadyHasData++;
      continue;
    }

    const steps = parseInt(yrStr) - 2567;  // 1 หรือ 2
    const base67 = row67;

    // คำนวณค่า trend
    const est_prod  = estimate(base67.production,   r_prod,  steps);
    const est_yield = estimate(base67.yield,          r_yield, steps);
    const est_area  = estimate(base67.area,           r_area,  steps);

    // area_planted ปี 2568 ใช้ scale factor จากกรมการข้าว
    let est_area_p, est_yp;
    if (yrStr === '2568') {
      est_area_p = Math.round((base67.area_planted || base67.area) * sf);
      est_yp     = est_area_p > 0
        ? Math.round((est_prod * 1000) / est_area_p)  // กก./ไร่ จาก estimated production
        : 0;
    } else {
      est_area_p = estimate(base67.area_planted, r_area_p, steps);
      est_yp     = estimate(base67.yield_planted, r_yp, steps);
    }

    // กรณีที่ base ทุกตัวเป็น 0 (จังหวัดไม่มีข้าวประเภทนั้น) ไม่ต้องใส่ estimate
    if (est_prod === 0 && est_area === 0) continue;

    // อัพเดตแถว
    row.production   = est_prod;
    row.yield        = est_yield;
    row.area         = est_area;
    row.area_planted = est_area_p;
    row.yield_planted= est_yp;

    row.source       = 'estimated_trend';
    row.source_title = yrStr === '2568'
      ? 'ประมาณการแนวโน้ม (avg YoY 2565–2567) + กรมการข้าว planted area calibration 2568'
      : 'ประมาณการแนวโน้ม (avg YoY 2565–2567)';
    row.source_url   = yrStr === '2568'
      ? 'https://www.ricethailand.go.th'
      : '';
    row.source_note  = `Trend estimation: production×(1+${r_prod.toFixed(4)})^${steps}, yield×(1+${r_yield.toFixed(4)})^${steps}, area×(1+${r_area.toFixed(4)})^${steps}${yrStr==='2568'?' + area_planted scaled by กรมการข้าว regional factor ' + sf.toFixed(4):''}`;
    row.source_date  = yrStr === '2568' ? '2 มีนาคม 2569 (กรมการข้าว)' : '';

    estimated++;
  }
}

console.log(`\n✅ ประมาณการแล้ว: ${estimated} rows`);
console.log(`ℹ️  rows ที่มีข้อมูลจริงอยู่แล้ว (ข้ามไป): ${alreadyHasData}`);

// ─────────────── WRITE OUTPUT ───────────────
// backup ก่อน
fs.copyFileSync(DATA_FILE, BACKUP);
console.log(`\n💾 Backup ไว้ที่: ${path.basename(BACKUP)}`);

// เขียนไฟล์ใหม่
const newContent = 'window.RICE_DATA_ROWS=' + JSON.stringify(rows, null, 0) + ';';
fs.writeFileSync(OUT_FILE, newContent, 'utf-8');

const sz = (fs.statSync(OUT_FILE).size / 1024).toFixed(0);
console.log(`✅ เขียน rice-data.js สำเร็จ (${sz} KB)`);

// ─────────────── SUMMARY STATS ───────────────
console.log('\n📋 สรุปตัวอย่างค่าที่ประมาณการ (ภาคเหนือ ข้าวขาว):');
const samples = [
  'Chiang Mai|white', 'Phitsanulok|white', 'Sukhothai|white',
  'Udon Thani|jasmine', 'Roi Et|jasmine', 'Surin|jasmine'
];
for (const key of samples) {
  const ym = idx.get(key);
  if (!ym) continue;
  console.log(`\n  ${key}`);
  for (const yr of ['2565','2566','2567','2568','2569']) {
    const r = ym[yr];
    if (!r) continue;
    const src = r.source === 'estimated_trend' ? ' [EST]' : '';
    console.log(`    ${yr}: prod=${r.production.toLocaleString().padStart(9)}, yield=${String(r.yield).padStart(4)}, area=${r.area.toLocaleString().padStart(9)}${src}`);
  }
}
