#!/usr/bin/env python3
"""Build a mixed official rice dataset for the provincial Thailand map.

Sources used in this build:
- OAE Agricultural Statistics of Thailand 2024 edition (published in 2025)
  Table 1.4 Major Rice Classified by Plant varieties: province rows, years 2565-2567
- Thai Rice Millers Association daily nationwide paddy price reports
  - 26 December 2568
  - 17 April 2569

Outputs:
- rice-data.csv
- rice-data.js

The resulting dataset intentionally mixes different availability windows:
- production / yield / harvested area: direct province-level OAE data for 2565-2567
- price: partial province coverage from daily millers association reports for 2568 and 2569
"""

from __future__ import annotations

import csv
import json
import re
import subprocess
import tempfile
import unicodedata
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "rice-data.csv"
JS_PATH = ROOT / "rice-data.js"
OAE_STATS_PATH = ROOT / "oae_stats_latest.pdf"

OAE_STATS_URL = (
    "https://catalog.oae.go.th/dataset/ba103542-830f-418a-b614-9645ebbe1a93/"
    "resource/4d5d1421-bb3b-4635-a43d-f6167d619db1/download/fd747711b82231d4.pdf"
)

PRICE_REPORTS = {
    "2568": {
        "date": "26 ธันวาคม 2568",
        "url": "http://www.thairicemillers.org/images/introc_1429264173/Pricerice26122568.pdf",
        "filename": "Pricerice26122568.pdf",
    },
    "2569": {
        "date": "17 เมษายน 2569",
        "url": "http://www.thairicemillers.org/images/introc_1429264173/Pricerice17042569.pdf",
        "filename": "Pricerice17042569.pdf",
    },
}

ALL_YEARS = ["2565", "2566", "2567", "2568", "2569"]
RICE_TYPES = ["white", "jasmine"]


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    replacements = {
        "\x00": "",
        "\ufeff": "",
        "ำา": "ำ",
        "กํา": "กำ",
        "ลํา": "ลำ",
        "คํา": "คำ",
        "จํา": "จำ",
        "นํา": "นำ",
        "สํา": "สำ",
        "ทํา": "ทำ",
        "ปี\u200b": "ปี",
        "\t": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_key(text: str) -> str:
    text = normalize_text(text)
    text = re.sub(r"[^0-9A-Za-zก-๙]", "", text)
    return text


def load_province_meta() -> dict[str, dict[str, str]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"Missing province metadata source: {CSV_PATH}")
    province_meta: dict[str, dict[str, str]] = {}
    with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            en = row["province_en"].strip()
            province_meta.setdefault(
                en,
                {
                    "province_th": row["province_th"].strip(),
                    "region": row["region"].strip(),
                },
            )
    if not province_meta:
        raise RuntimeError("Province metadata could not be loaded from current rice-data.csv")
    return province_meta


def build_thai_alias_map(province_meta: dict[str, dict[str, str]]) -> dict[str, str]:
    aliases = {
        normalize_key(meta["province_th"]): en for en, meta in province_meta.items()
    }
    aliases[normalize_key("กรุงเทพ")] = "Bangkok Metropolis"
    aliases[normalize_key("อยุธยา")] = "Phra Nakhon Si Ayutthaya"
    aliases[normalize_key("บึงกาฬ")] = "Bueng Kan"
    return aliases


def match_province(line: str, alias_map: dict[str, str]) -> str | None:
    key = normalize_key(line)
    for alias in sorted(alias_map, key=len, reverse=True):
        if key.startswith(alias):
            return alias_map[alias]
    return None


def extract_ints(line: str) -> list[int]:
    return [int(part.replace(",", "")) for part in re.findall(r"\d[\d,]*", line)]


def seed_metric_map(province_meta: dict[str, dict[str, str]]) -> dict[str, dict[str, dict[str, int]]]:
    return {
        en: {
            year: {
                "production": 0,
                "yield": 0,
                "area": 0,
                "area_planted": 0,
                "yield_planted": 0,
            }
            for year in ("2565", "2566", "2567")
        }
        for en in province_meta
    }


def parse_oae_table_1_4(
    province_meta: dict[str, dict[str, str]],
) -> tuple[dict[str, dict[str, dict[str, int]]], dict[str, dict[str, dict[str, int]]]]:
    if not OAE_STATS_PATH.exists():
        raise FileNotFoundError(f"Missing source PDF: {OAE_STATS_PATH}")

    alias_map = build_thai_alias_map(province_meta)
    white = seed_metric_map(province_meta)
    jasmine_parts = {
        en: {
            year: {"production": 0, "area": 0, "area_planted": 0}
            for year in ("2565", "2566", "2567")
        }
        for en in province_meta
    }

    reader = PdfReader(str(OAE_STATS_PATH))
    current_province: str | None = None
    for page_no in range(36, 45):
        lines = (reader.pages[page_no - 1].extract_text() or "").splitlines()
        for raw_line in lines:
            line = normalize_text(raw_line)
            if not line:
                continue

            province_en = match_province(line, alias_map)
            numbers = extract_ints(line)
            if province_en and len(numbers) >= 12:
                current_province = province_en
                continue

            if current_province is None or len(numbers) < 12:
                continue

            if normalize_key(line).startswith(normalize_key("ข้าวเจ้าอื่นๆ")):
                yearly = {
                    "2565": [numbers[0], numbers[3], numbers[6], numbers[9]],
                    "2566": [numbers[1], numbers[4], numbers[7], numbers[10]],
                    "2567": [numbers[2], numbers[5], numbers[8], numbers[11]],
                }
                for year, (planted, area, production, yield_value) in yearly.items():
                    white[current_province][year]["area_planted"] = planted
                    white[current_province][year]["area"] = area
                    white[current_province][year]["production"] = production
                    white[current_province][year]["yield"] = yield_value
                    white[current_province][year]["yield_planted"] = (
                        round((production * 1000) / planted) if planted else 0
                    )
                continue

            if normalize_key(line).startswith(normalize_key("ข้าวเจ้าหอมมะลิในพื้นที่")) or normalize_key(line).startswith(
                normalize_key("ข้าวเจ้าหอมมะลินอกพื้นที่")
            ):
                for year, planted, area, production in (
                    ("2565", numbers[0], numbers[3], numbers[6]),
                    ("2566", numbers[1], numbers[4], numbers[7]),
                    ("2567", numbers[2], numbers[5], numbers[8]),
                ):
                    jasmine_parts[current_province][year]["area_planted"] += planted
                    jasmine_parts[current_province][year]["area"] += area
                    jasmine_parts[current_province][year]["production"] += production

    jasmine = seed_metric_map(province_meta)
    for province_en, years in jasmine_parts.items():
        for year, metric in years.items():
            area_planted = metric["area_planted"]
            area = metric["area"]
            production = metric["production"]
            jasmine[province_en][year]["area_planted"] = area_planted
            jasmine[province_en][year]["area"] = area
            jasmine[province_en][year]["production"] = production
            jasmine[province_en][year]["yield"] = round((production * 1000) / area) if area else 0
            jasmine[province_en][year]["yield_planted"] = (
                round((production * 1000) / area_planted) if area_planted else 0
            )

    return white, jasmine


def download_report(url: str, filename: str) -> Path:
    target = Path(tempfile.gettempdir()) / filename
    result = subprocess.run(
        ["curl", "-L", "-A", "Mozilla/5.0", "-s", "-o", str(target), url],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 or not target.exists() or target.stat().st_size < 1000:
        raise RuntimeError(f"Failed to download report: {url}")
    return target


def parse_range_pairs(line: str) -> list[tuple[int, int]]:
    pairs = []
    for low, high in re.findall(r"(\d[\d,]*)\s*-\s*(\d[\d,]*)", line):
        pairs.append((int(low.replace(",", "")), int(high.replace(",", ""))))
    return pairs


def parse_price_reports(
    province_meta: dict[str, dict[str, str]]
) -> dict[str, dict[str, dict[str, int | str]]]:
    alias_map = build_thai_alias_map(province_meta)
    price_rows: dict[str, dict[str, dict[str, int | str]]] = defaultdict(dict)

    for year, meta in PRICE_REPORTS.items():
        pdf_path = download_report(meta["url"], meta["filename"])
        reader = PdfReader(str(pdf_path))

        # Page 2: white paddy, 15% and 25% moisture ranges.
        for raw_line in (reader.pages[1].extract_text() or "").splitlines():
            line = normalize_text(raw_line)
            province_en = match_province(line, alias_map)
            ranges = parse_range_pairs(line)
            if not province_en or len(ranges) < 2:
                continue
            (low15, high15), (low25, high25) = ranges[:2]
            price_rows[province_en][f"white:{year}"] = {
                "price": round((low15 + high15) / 2),
                "price_low": low15,
                "price_high": high15,
                "price_low_alt": low25,
                "price_high_alt": high25,
                "price_basis": "moisture_15_pct",
                "source_date": meta["date"],
                "source_title": f"รายงานราคาข้าวเปลือกทั่วประเทศ ประจำวันที่ {meta['date']}",
                "source_url": meta["url"],
                "source": "thai_rice_millers_daily",
                "source_note": (
                    "province price range from Thai Rice Millers Association daily nationwide paddy report; "
                    "map uses midpoint of the 15% moisture range; alternate range is 25% moisture"
                ),
            }

        # Page 3: jasmine 67/68 section only; it is the comparable multi-province section.
        lines = [normalize_text(line) for line in (reader.pages[2].extract_text() or "").splitlines()]
        in_section = False
        for line in lines:
            compact = normalize_key(line)
            if "หอมมะลิ6768" in compact:
                in_section = True
                continue
            if not in_section:
                continue
            if "หอมมะลิ6869" in compact or "ขาวกข79" in compact:
                break
            province_en = match_province(line, alias_map)
            ranges = parse_range_pairs(line)
            if not province_en or not ranges:
                continue
            low15, high15 = ranges[0]
            price_rows[province_en][f"jasmine:{year}"] = {
                "price": round((low15 + high15) / 2),
                "price_low": low15,
                "price_high": high15,
                "price_low_alt": "",
                "price_high_alt": "",
                "price_basis": "moisture_15_pct",
                "source_date": meta["date"],
                "source_title": (
                    f"รายงานราคาข้าวเปลือกทั่วประเทศ ประจำวันที่ {meta['date']} "
                    "· หมวดข้าวเปลือกเจ้าหอมมะลิ (67/68)"
                ),
                "source_url": meta["url"],
                "source": "thai_rice_millers_daily",
                "source_note": (
                    "province price range from Thai Rice Millers Association daily nationwide paddy report; "
                    "uses the comparable multi-province section 'ข้าวเปลือกเจ้าหอมมะลิ (67/68)'; "
                    "map uses midpoint of the 15% moisture range"
                ),
            }

    return price_rows


def build_rows() -> list[dict[str, object]]:
    province_meta = load_province_meta()
    white_metrics, jasmine_metrics = parse_oae_table_1_4(province_meta)
    price_metrics = parse_price_reports(province_meta)

    rows: list[dict[str, object]] = []
    for province_en, meta in province_meta.items():
        province_th = meta["province_th"]
        region = meta["region"]
        for rice_type in RICE_TYPES:
            for year in ALL_YEARS:
                row: dict[str, object] = {
                    "province_th": province_th,
                    "province_en": province_en,
                    "region": region,
                    "rice_type": rice_type,
                    "year": year,
                    "production": 0,
                    "yield": 0,
                    "area": 0,
                    "area_planted": 0,
                    "yield_planted": 0,
                    "price": 0,
                    "price_low": "",
                    "price_high": "",
                    "price_low_alt": "",
                    "price_high_alt": "",
                    "price_basis": "",
                    "source": "",
                    "source_title": "",
                    "source_url": "",
                    "source_note": "",
                    "source_date": "",
                }

                if year in {"2565", "2566", "2567"}:
                    metrics = white_metrics if rice_type == "white" else jasmine_metrics
                    metric_row = metrics[province_en][year]
                    row.update(metric_row)
                    row["source"] = "oae_stats_table_1_4"
                    row["source_title"] = "สถิติการเกษตรของประเทศไทย ปี 2567 · ตารางที่ 1.4 ข้าวนาปีแยกพันธุ์"
                    row["source_url"] = OAE_STATS_URL
                    row["source_note"] = (
                        "direct province row from OAE Agricultural Statistics 2024 Table 1.4, rice type = ข้าวเจ้าอื่นๆ"
                        if rice_type == "white"
                        else "sum of OAE Agricultural Statistics 2024 Table 1.4 province rows: ข้าวเจ้าหอมมะลิในพื้นที่ + ข้าวเจ้าหอมมะลินอกพื้นที่"
                    )

                price_key = f"{rice_type}:{year}"
                if price_key in price_metrics[province_en]:
                    row.update(price_metrics[province_en][price_key])

                rows.append(row)

    return rows


def write_outputs(rows: list[dict[str, object]]) -> None:
    fieldnames = [
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
        "price",
        "price_low",
        "price_high",
        "price_low_alt",
        "price_high_alt",
        "price_basis",
        "source",
        "source_title",
        "source_url",
        "source_note",
        "source_date",
    ]
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    js_payload = json.dumps(rows, ensure_ascii=False, separators=(",", ":"))
    JS_PATH.write_text(f"window.RICE_DATA_ROWS={js_payload};\n", encoding="utf-8")


def main() -> None:
    rows = build_rows()
    write_outputs(rows)
    print(f"Wrote {len(rows)} rows to {CSV_PATH.name} and {JS_PATH.name}")


if __name__ == "__main__":
    main()
