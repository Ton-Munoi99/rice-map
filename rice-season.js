/**
 * ปฏิทินข้าวไทย — เดือน + ภาค → ข้าวอยู่ระยะไหน
 *
 * ใช้ร่วมกันระหว่าง index.html (แผนที่) และ farmer.html (หน้าชาวนา)
 * ก่อนหน้านี้อยู่ใน index.html ที่เดียว หน้าชาวนาจึงไม่รู้ระยะข้าว และให้
 * คำแนะนำเดียวกันหมดไม่ว่าข้าวจะเพิ่งหว่านหรือใกล้เกี่ยว
 *
 * `stage` เป็นค่าสำหรับให้โค้ดตัดสินใจ (ไม่ใช่ข้อความ) — ข้อความอาจแก้คำได้
 * โดยไม่กระทบตรรกะที่อ้างอิงมัน
 */
(function (root) {
  "use strict";

  var REGION_TH = {
    north: "เหนือ",
    northeast: "อีสาน",
    central: "กลาง",
    east: "ตะวันออก",
    west: "ตะวันตก",
    south: "ใต้",
  };

  var SOUTH = {
    calendar: {
      th: "🌧️ ภาคใต้ · นาปี: ปลูก ก.ย.–พ.ย. → เก็บ มี.ค.–พ.ค. (มรสุม ต.อ.น.)",
      en: "🌧️ South · Main: plant Sep–Nov → harvest Mar–May (NE monsoon)",
    },
    cropType: { th: "นาปี (rain-fed)", en: "Main season (rain-fed)" },
  };

  // ภาคใต้รับมรสุมตะวันออกเฉียงเหนือ ฤดูปลูกจึงกลับทางกับภาคอื่นทั้งประเทศ
  function southSituation(mon) {
    if (mon >= 3 && mon <= 5) return { stage: "harvest", th: "ช่วงเก็บเกี่ยวนาปี", en: "Main crop harvest season" };
    if (mon >= 9 && mon <= 11) return { stage: "planting", th: "ช่วงปลูกนาปี", en: "Main crop planting season" };
    if (mon >= 6 && mon <= 8) return { stage: "prep", th: "เตรียมดิน / รอฝนมรสุม", en: "Land prep / awaiting monsoon" };
    return { stage: "growing", th: "ข้าวกำลังเจริญเติบโต (นาปี)", en: "Rice growing (main crop)" };
  }

  function mainSituation(mon) {
    if (mon >= 5 && mon <= 8)
      return {
        stage: "planting",
        th: "ช่วงปลูกนาปี (rain-fed)",
        en: "Main crop planting season",
        crop: { th: "นาปี (rain-fed)", en: "Main season (rain-fed)" },
      };
    if (mon >= 11 || mon <= 1)
      return {
        stage: "harvest",
        th: "เก็บเกี่ยวนาปี / เริ่มนาปรัง",
        en: "Main harvest / off-season start",
        crop: { th: "นาปี→นาปรัง", en: "Main→Off-season" },
      };
    if (mon >= 2 && mon <= 4)
      return {
        stage: "offseason",
        th: "นาปรังกำลังโต / เก็บเกี่ยว",
        en: "Off-season growing / harvest",
        crop: { th: "นาปรัง (irrigated)", en: "Off-season (irrigated)" },
      };
    return {
      stage: "growing",
      th: "ข้าวนาปีกำลังเจริญเติบโต",
      en: "Main crop growing",
      crop: { th: "นาปี (rain-fed)", en: "Main season (rain-fed)" },
    };
  }

  /**
   * @param {string} region  north | northeast | central | east | west | south
   * @param {number} [mon]   เดือน 1–12 — ไม่ใส่ = เดือนปัจจุบัน
   */
  function of(region, mon) {
    if (mon == null) mon = new Date().getMonth() + 1;

    if (region === "south") {
      var s = southSituation(mon);
      return {
        calendar: SOUTH.calendar,
        situation: { th: s.th, en: s.en },
        cropType: SOUTH.cropType,
        stage: s.stage,
      };
    }

    var regTh = REGION_TH[region] || REGION_TH.central;
    var regEn = region.charAt(0).toUpperCase() + region.slice(1);
    var m = mainSituation(mon);
    return {
      calendar: {
        th:
          "🗓️ ภาค" + regTh + " · นาปี: ปลูก พ.ค.–ส.ค. → เก็บ พ.ย.–ม.ค. · นาปรัง: ปลูก ธ.ค.–ก.พ. → เก็บ มี.ค.–พ.ค.",
        en:
          "🗓️ " + regEn + " · Main: plant May–Aug → harvest Nov–Jan · Off-season: plant Dec–Feb → harvest Mar–May",
      },
      situation: { th: m.th, en: m.en },
      cropType: m.crop,
      stage: m.stage,
    };
  }

  root.RiceSeason = { of: of, REGION_TH: REGION_TH };

  // ตรวจตัวเอง: node rice-season.js
  if (typeof module !== "undefined" && require.main === module) {
    var assert = require("assert");
    var stages = function (reg) {
      var out = [];
      for (var m = 1; m <= 12; m++) out.push(of(reg, m).stage);
      return out.join(",");
    };
    // ทุกเดือนต้องได้ระยะ ไม่มีหลุดเป็น undefined
    ["north", "northeast", "central", "east", "south"].forEach(function (r) {
      for (var m = 1; m <= 12; m++) {
        var c = of(r, m);
        assert.ok(c.stage, r + " เดือน " + m + " ไม่มี stage");
        assert.ok(c.situation.th && c.calendar.th && c.cropType.th, r + " เดือน " + m + " ข้อความไม่ครบ");
      }
    });
    // ใต้ต้องกลับทางกับภาคอื่น: ใต้เก็บเกี่ยว มี.ค.–พ.ค. ส่วนอีสานปลูก พ.ค.
    assert.strictEqual(of("south", 4).stage, "harvest");
    assert.strictEqual(of("northeast", 4).stage, "offseason");
    assert.strictEqual(of("northeast", 5).stage, "planting");
    assert.strictEqual(of("south", 10).stage, "planting");
    // เดือนคาบเกี่ยวปี (พ.ย.–ม.ค.) ต้องเป็นเก็บเกี่ยวทั้งช่วง
    [11, 12, 1].forEach(function (m) {
      assert.strictEqual(of("central", m).stage, "harvest", "เดือน " + m + " ควรเป็น harvest");
    });
    // ภาคที่ไม่รู้จักต้องไม่พัง
    assert.ok(of("atlantis", 6).situation.th);
    console.log("north     :", stages("north"));
    console.log("south     :", stages("south"));
    console.log("ok — ผ่านทุกเดือน 5 ภาค");
  }
})(typeof window !== "undefined" ? window : globalThis);
