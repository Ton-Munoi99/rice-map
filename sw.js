// ติดตั้งเป็นแอปได้ + เปิดได้ตอนเน็ตหลุด — ไม่ได้ทำให้เร็วขึ้น
// network-first เสมอ: ข้อมูลอัปเดตวันละหลายรอบ ถ้า cache-first คนจะเห็นราคา/เตือนภัยเก่าค้าง
// cache ใช้เฉพาะตอนเน็ตล่ม · เก็บโดยตัด query ทิ้ง กันไฟล์เดียวกันซ้ำหลายชุด
// ponytail: ไม่จำกัดขนาด cache — ไฟล์ same-origin มีจำนวนคงที่ (~5 MB) ถ้าเพิ่มไฟล์ใหญ่แบบสุ่มชื่อค่อยใส่ LRU
const CACHE = "rice-map-v1";
const SHELL = ["./", "index.html", "farmer.html", "rice-data.js", "rice-season.js", "naprang-data.js", "thailand-data.js"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return; // ฟอนต์/API ภายนอก ปล่อยเบราว์เซอร์จัดการ
  const key = url.origin + url.pathname;
  e.respondWith(
    fetch(req)
      .then((res) => {
        if (res.ok) {
          const copy = res.clone();
          e.waitUntil(caches.open(CACHE).then((c) => c.put(key, copy)));
        }
        return res;
      })
      .catch(() => caches.match(key).then((hit) => hit || caches.match("index.html"))),
  );
});
