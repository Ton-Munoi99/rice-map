#!/usr/bin/env python3
"""Build provincial second-crop (ข้าวนาปรัง) production dataset from OAE PDFs.

Source: OAE catalog dataoae1104 — "ปริมาณการผลิตข้าวนาปรัง" (same catalog as นาปี).
The naprang PDFs use the identical 5-column table layout as the นาปี "direct"
tables, so we reuse parse_napi() from build_oae_rice_data.

Year mapping: OAE labels naprang by its harvest year ("ปี 2567"); we store it
under the matching app year key ("2567"). Provinces with no naprang crop
(no irrigation) are emitted as zero rows.

Output: naprang-data.js  (sets window.NAPRANG_DATA_ROWS)

Expected local source files in repo root:
- rice_naprang_2565.pdf
- rice_naprang_2566.pdf
- rice_naprang_2567.pdf
- rice_naprang_2568.pdf
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from build_oae_rice_data import SKIP_PREFIXES, canon, clean_text, extract_lines

ROOT = Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
OUTPUT = ROOT / "naprang-data.js"

# OAE naprang PDFs use short province forms that differ from index.html NM.
NAME_ALIASES = {
    "อยุธยา": "Phra Nakhon Si Ayutthaya",
}

# Decimal-aware: small provinces report production as "36.00" / "4.65".
NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def parse_naprang(path: Path, th_to_en: dict[str, str]) -> dict[str, dict[str, int]]:
    """One province row = exactly 5 numeric columns
    (area_planted, area_harvested, production, yield_planted, yield_harvested).
    Handles decimal production and short-form province names."""
    data: dict[str, dict[str, int]] = {}
    for raw in extract_lines(path):
        line = clean_text(raw)
        if not line or line.startswith(SKIP_PREFIXES):
            continue
        nums = NUM_RE.findall(line)
        if len(nums) != 5:
            continue
        first_num = re.search(r"\d", line)
        prefix = canon(line[: first_num.start()].strip())
        province_key = th_to_en.get(prefix) or NAME_ALIASES.get(prefix)
        if not province_key:
            continue
        values = [round(float(n.replace(",", ""))) for n in nums]
        data[province_key] = {
            "area_planted": values[0],
            "area_harvested": values[1],
            "production": values[2],
            "yield_planted": values[3],
            "yield_harvested": values[4],
        }
    return data


def parse_nm_and_regions() -> tuple[dict[str, str], dict[str, str]]:
    """Extract NM (en->th) and REG (region->[en]) from index.html, tolerant of
    whitespace/formatting changes."""
    text = INDEX.read_text(encoding="utf-8")

    nm_block = re.search(r"const NM\s*=\s*\{(.*?)\n\s*\};", text, re.DOTALL).group(1)
    nm = dict(re.findall(r'"([^"]+)"\s*:\s*"([^"]+)"', nm_block))

    reg_block = re.search(r"const REG\s*=\s*\{(.*?)\n\s*\};", text, re.DOTALL).group(1)
    region_of: dict[str, str] = {}
    for region, body in re.findall(r"(\w+)\s*:\s*\[([^\]]*)\]", reg_block):
        for province_en in re.findall(r'"([^"]+)"', body):
            region_of[province_en] = region

    return nm, region_of

# OAE naprang label year → app year key (direct match)
SOURCES = {
    "2565": ROOT / "rice_naprang_2565.pdf",
    "2566": ROOT / "rice_naprang_2566.pdf",
    "2567": ROOT / "rice_naprang_2567.pdf",
    "2568": ROOT / "rice_naprang_2568.pdf",
}

SOURCE_URL = "https://catalog.oae.go.th/dataset/dataoae1104"
SOURCE_TITLE = "ปริมาณการผลิตข้าวนาปรัง รายจังหวัด (สศก./OAE)"


def main() -> None:
    nm, region_of = parse_nm_and_regions()
    provinces_en = list(nm.keys())
    th_to_en = {canon(th): en for en, th in nm.items()}

    records: list[dict[str, object]] = []
    for year, path in SOURCES.items():
        rows = parse_naprang(path, th_to_en)
        found = sum(1 for p in provinces_en if p in rows)
        for province_en in provinces_en:
            row = rows.get(province_en)
            records.append({
                "province_th": nm[province_en],
                "province_en": province_en,
                "region": region_of[province_en],
                "rice_type": "naprang",
                "year": year,
                "production": row["production"] if row else 0,
                "yield": row["yield_harvested"] if row else 0,
                "area": row["area_harvested"] if row else 0,
                "area_planted": row["area_planted"] if row else 0,
                "yield_planted": row["yield_planted"] if row else 0,
                "source": "oae_naprang_pdf",
                "source_title": f"{SOURCE_TITLE} ปี {year}",
                "source_url": SOURCE_URL,
                "source_note": "direct province row from OAE naprang PDF; provinces with no irrigation crop = 0",
            })
        national = sum(r["production"] for r in records if r["year"] == year)
        print(f"  naprang {year}: {found}/{len(provinces_en)} provinces · national {national:,} tons")

    OUTPUT.write_text(
        f"window.NAPRANG_DATA_ROWS={json.dumps(records, ensure_ascii=False, separators=(',', ':'))};\n",
        encoding="utf-8",
    )
    print(f"\nWrote {OUTPUT.name} with {len(records)} rows")


if __name__ == "__main__":
    main()
