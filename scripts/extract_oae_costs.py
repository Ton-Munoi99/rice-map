import pandas as pd
import json
import os

# =====================================================================
# สคริปต์นี้ถูกสร้างขึ้นมาเพื่อให้เป็นเทมเพลต (Template) สำหรับการดึงข้อมูล
# "ต้นทุนการผลิตข้าว" รายจังหวัด จากไฟล์ Excel ของสำนักงานเศรษฐกิจการเกษตร (OAE)
# 
# ข้อแนะนำการใช้งาน:
# 1. ดาวน์โหลดไฟล์รายงานต้นทุนการผลิตรายจังหวัด (รูปแบบ .xlsx) จากเว็บไซต์ www.oae.go.th
# 2. ปรับปรุงตัวแปร `FILE_PATH`, `SHEET_NAME` ให้ตรงกับชื่อไฟล์จริง
# 3. รันสคริปต์เพื่อประมวลผลให้เป็นไฟล์ `data/cost-data.js` สำหรับใช้งานบนแผนที่
# =====================================================================

FILE_PATH = "ต้นทุนการผลิตข้าว_สศก_2567.xlsx"
SHEET_NAME = "รายงานรายจังหวัด"

def extract_costs():
    if not os.path.exists(FILE_PATH):
        print(f"⚠️ ไม่พบไฟล์ {FILE_PATH} (นี่คือสคริปต์ตัวอย่าง กรุณาดาวน์โหลดไฟล์จริงมาไว้ในโฟลเดอร์)")
        return

    # สมมติฐานโครงสร้างคอลัมน์ของไฟล์ Excel สศก.
    # Column A: "จังหวัด", Column B: "ค่าปุ๋ย", Column C: "ค่าแรง", Column D: "ค่าเมล็ดพันธุ์", ...
    df = pd.read_excel(FILE_PATH, sheet_name=SHEET_NAME, header=1) # สมมติว่า header อยู่บรรทัด 2
    
    cost_data = {}
    
    for index, row in df.iterrows():
        prov = str(row.get('จังหวัด', '')).strip()
        if not prov or prov == 'NaN':
            continue
            
        fertilizer = float(row.get('ค่าปุ๋ยเคมี', 0)) + float(row.get('ค่าปุ๋ยอินทรีย์', 0))
        labor = float(row.get('ค่าจ้างแรงงาน', 0))
        seed = float(row.get('ค่าเมล็ดพันธุ์', 0))
        machine = float(row.get('ค่าจ้างเครื่องจักร', 0))
        others = float(row.get('ค่าน้ำมันเชื้อเพลิง', 0)) + float(row.get('ค่าเสื่อมราคา', 0)) + float(row.get('ค่าเช่าที่ดิน', 0))
        
        total = fertilizer + labor + seed + machine + others
        
        cost_data[prov] = {
            "total": total,
            "fertilizer": fertilizer,
            "labor": labor,
            "seed": seed,
            "machine": machine,
            "others": others
        }
        
    js_content = f"window.COST_DATA = {json.dumps(cost_data, ensure_ascii=False, indent=2)};"

    with open("../data/cost-data.js", "w", encoding="utf-8") as f:
        f.write(js_content)

    print("✅ ประมวลผลและสร้าง data/cost-data.js สำเร็จ!")

if __name__ == "__main__":
    extract_costs()
