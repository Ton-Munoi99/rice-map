#!/usr/bin/env python3
"""Build official provincial rice datasets from local OAE PDF files.

Outputs:
- rice-data.csv
- rice-data.js

Expected local source files in the project root:
- rice_napi_2565.pdf
- rice_napi_2566.pdf
- jasmine_2565.pdf
- jasmine_2566.pdf
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"


SOURCE_META = {
    ("napi", "2565/66"): {
        "path": ROOT / "rice_napi_2565.pdf",
        "title": "ข้าวนาปี : เนื้อที่เพาะปลูก เนื้อที่เก็บเกี่ยว ผลผลิต และผลผลิตต่อไร่ ระดับประเทศ ภาค และจังหวัด ปีเพาะปลูก 2565/66 ที่ความชื้น 15%",
        "url": "https://catalog.oae.go.th/dataset/2446c264-3f68-4c79-ac44-dd9db8f07ebf/resource/111da0f3-9703-4469-85cf-4087642f1abe/download/untitled.pdf",
        "mode": "direct",
    },
    ("napi", "2566/67"): {
        "path": ROOT / "rice_napi_2566.pdf",
        "title": "ข้าวนาปี : เนื้อที่เพาะปลูก เนื้อที่เก็บเกี่ยว ผลผลิต และผลผลิตต่อไร่ ปีเพาะปลูก 2566/67 ที่ความชื้น 15%",
        "url": "https://catalog.oae.go.th/dataset/2446c264-3f68-4c79-ac44-dd9db8f07ebf/resource/3af01ad7-bfd9-497d-9446-c2ea5e58e58a/download/untitled.pdf",
        "mode": "direct",
    },
    ("jasmine", "2565/66"): {
        "path": ROOT / "jasmine_2565.pdf",
        "title": "ข้าวนาปี : จําแนกรายพันธุ์ 5 พันธุ์ รายจังหวัด ปีเพาะปลูก 2565/66 ที่ความชื้น 15%",
        "url": "https://catalog.oae.go.th/dataset/2d949230-33ba-4ffc-be18-04d2d779ec64/resource/415736c7-1027-4712-8fcd-f0c41d6c7f08/download/2565.pdf",
        "mode": "sum_in_out",
    },
    ("jasmine", "2566/67"): {
        "path": ROOT / "jasmine_2566.pdf",
        "title": "ข้าวนาปี : จําแนกรายพันธุ์ 5 พันธุ์ รายจังหวัด ปีเพาะปลูก 2566/67 ที่ความชื้น 15%",
        "url": "https://catalog.oae.go.th/dataset/2d949230-33ba-4ffc-be18-04d2d779ec64/resource/a0e1a68f-270f-4605-83ba-b70fbd5b87a0/download/2566.pdf",
        "mode": "sum_in_out",
    },
}

CSV_FIELDS = [
    "province_th",
    "province_en",
    "region",
    "rice_type",
    "year",
    "production",
    "yield",
    "area",
    "area_planted",
    "yield_planted",
    "source",
    "source_title",
    "source_url",
    "source_note",
]

PRIVATE_USE_REPLACEMENTS = {
    "\uf70a": "่",
    "\uf70b": "้",
    "\uf70c": "๊",
    "\uf70d": "๋",
    "\uf70e": "์",
    "\uf70f": "ํ",
    "\uf710": "ั",
    "\uf711": "ี",
    "\uf712": "ึ",
    "\uf713": "ื",
    "\uf714": "ุ",
    "\uf715": "ู",
    "\uf716": "ฺ",
    "\uf717": "็",
    "\uf718": "ำ",
}

SPACE_FIXES = {
    "ล า": "ลำ",
    "ก า": "กำ",
    "น า": "นำ",
    "ท า": "ทำ",
    "ค า": "คำ",
    "ร า": "รำ",
    "อ า": "อำ",
    "ย า": "ยำ",
    "ล ํา": "ลำ",
}

SKIP_PREFIXES = (
    "รวมทั้งประเทศ",
    "ภาคเหนือ",
    "ภาคตะวันออกเฉียงเหนือ",
    "ภาคกลาง",
    "ภาคใต้",
    "ประเทศ/ภาค",
    "/จังหวัด",
    "ภาค/จังหวัด",
    "เนื้อที่เพาะปลูก",
    "(ไร่)",
    "( ไร่)",
    "(ตัน)",
    "ผลผลิต",
    "ที่ความชื้น",
)


def clean_text(value: str) -> str:
    for old, new in PRIVATE_USE_REPLACEMENTS.items():
        value = value.replace(old, new)
    value = unicodedata.normalize("NFC", value)
    value = value.replace("ํา", "ำ")
    value = re.sub(r"\s+", " ", value).strip()
    for old, new in SPACE_FIXES.items():
        value = value.replace(old, new)
    return value


def canon(value: str) -> str:
    return clean_text(value).replace(" ", "")


def parse_nm_and_regions() -> tuple[dict[str, str], dict[str, str]]:
    text = INDEX.read_text(encoding="utf-8")

    nm_start = text.index("const NM={") + len("const NM={")
    nm_end = text.index("\n};\n\nconst REG={", nm_start)
    nm_obj = text[nm_start:nm_end]
    nm = dict(re.findall(r'"([^"]+)":"([^"]+)"', nm_obj))

    reg_start = text.index("const REG={") + len("const REG={")
    reg_end = text.index("\n};\n\nconst YEARS=", reg_start)
    reg_obj = text[reg_start:reg_end]
    region_of: dict[str, str] = {}
    for match in re.finditer(r"(\w+):\[([^\]]*)\]", reg_obj):
        region = match.group(1)
        for province_en in re.findall(r'"([^"]+)"', match.group(2)):
            region_of[province_en] = region

    return nm, region_of


def extract_lines(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing source PDF: {path}")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)
    return text.splitlines()


def parse_napi(path: Path, th_to_en: dict[str, str]) -> dict[str, dict[str, int]]:
    data: dict[str, dict[str, int]] = {}
    for raw in extract_lines(path):
        line = clean_text(raw)
        if not line or line.startswith(SKIP_PREFIXES):
            continue
        nums = re.findall(r"\d[\d,]*", line)
        if len(nums) != 5:
            continue
        first_num = re.search(r"\d", line)
        assert first_num is not None
        province_key = th_to_en.get(canon(line[: first_num.start()].strip()))
        if not province_key:
            continue
        values = [int(num.replace(",", "")) for num in nums]
        data[province_key] = {
            "area_planted": values[0],
            "area_harvested": values[1],
            "production": values[2],
            "yield_planted": values[3],
            "yield_harvested": values[4],
        }
    return data


def parse_jasmine(path: Path, th_to_en: dict[str, str], provinces_en: list[str]) -> dict[str, dict[str, int | bool]]:
    grouped: dict[str, dict[str, dict[str, int] | None]] = {}
    current_province: str | None = None

    for raw in extract_lines(path):
        line = clean_text(raw)
        if not line or line.startswith(SKIP_PREFIXES):
            continue
        nums = re.findall(r"\d[\d,]*", line)
        if len(nums) != 5:
            continue
        first_num = re.search(r"\d", line)
        assert first_num is not None
        prefix = line[: first_num.start()].strip()
        province_key = th_to_en.get(canon(prefix))
        if province_key:
            current_province = province_key
            grouped.setdefault(province_key, {"in": None, "out": None})
            continue
        if not current_province:
            continue

        values = [int(num.replace(",", "")) for num in nums]
        row = {
            "area_planted": values[0],
            "area_harvested": values[1],
            "production": values[2],
            "yield_planted": values[3],
            "yield_harvested": values[4],
        }
        label = canon(prefix)
        if "ข้าวเจ้าหอมมะลิในพื้นที่" in label:
            grouped[current_province]["in"] = row
        elif "ข้าวเจ้าหอมมะลินอกพื้นที่" in label:
            grouped[current_province]["out"] = row

    final: dict[str, dict[str, int | bool]] = {}
    for province_en in provinces_en:
        parts = grouped.get(province_en, {"in": None, "out": None})
        in_row = parts.get("in")
        out_row = parts.get("out")
        if not in_row and not out_row:
            final[province_en] = {
                "area_planted": 0,
                "area_harvested": 0,
                "production": 0,
                "yield_planted": 0,
                "yield_harvested": 0,
                "has_in_area": False,
                "has_out_area": False,
            }
            continue

        area_planted = (in_row["area_planted"] if in_row else 0) + (out_row["area_planted"] if out_row else 0)
        area_harvested = (in_row["area_harvested"] if in_row else 0) + (out_row["area_harvested"] if out_row else 0)
        production = (in_row["production"] if in_row else 0) + (out_row["production"] if out_row else 0)

        final[province_en] = {
            "area_planted": area_planted,
            "area_harvested": area_harvested,
            "production": production,
            "yield_planted": round((production * 1000) / area_planted) if area_planted else 0,
            "yield_harvested": round((production * 1000) / area_harvested) if area_harvested else 0,
            "has_in_area": bool(in_row),
            "has_out_area": bool(out_row),
        }
    return final


def main() -> None:
    nm, region_of = parse_nm_and_regions()
    provinces_en = list(nm.keys())
    th_to_en = {canon(th): en for en, th in nm.items()}

    records: list[dict[str, object]] = []
    for (rice_type, year), meta in SOURCE_META.items():
        parser = parse_napi if meta["mode"] == "direct" else parse_jasmine
        rows = parser(meta["path"], th_to_en) if meta["mode"] == "direct" else parser(meta["path"], th_to_en, provinces_en)

        if meta["mode"] == "direct":
          missing = sorted(set(provinces_en) - set(rows))
          if missing:
              raise RuntimeError(f"Missing provinces in {meta['path'].name}: {missing}")

        for province_en in provinces_en:
            row = rows[province_en]
            records.append(
                {
                    "province_th": nm[province_en],
                    "province_en": province_en,
                    "region": region_of[province_en],
                    "rice_type": rice_type,
                    "year": year,
                    "production": row["production"],
                    "yield": row["yield_harvested"],
                    "area": row["area_harvested"],
                    "area_planted": row["area_planted"],
                    "yield_planted": row["yield_planted"],
                    "source": "oae_pdf_direct" if meta["mode"] == "direct" else "oae_pdf_sum_in_out",
                    "source_title": meta["title"],
                    "source_url": meta["url"],
                    "source_note": (
                        "direct province row from official OAE PDF"
                        if meta["mode"] == "direct"
                        else "sum of official OAE jasmine in-area and out-area province rows; yields recalculated from summed production and area"
                    ),
                }
            )

    csv_path = ROOT / "rice-data.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(records)

    js_path = ROOT / "rice-data.js"
    js_path.write_text(
        f"window.RICE_DATA_ROWS={json.dumps(records, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )

    print(f"Wrote {csv_path.name} with {len(records)} rows")
    print(f"Wrote {js_path.name} with {len(records)} rows")


if __name__ == "__main__":
    main()
