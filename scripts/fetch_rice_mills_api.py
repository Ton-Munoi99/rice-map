#!/usr/bin/env python3
"""
Refresh data/rice-mills-api-snapshot.xlsx from the DIT SearchRiceTrade API.

Run this when you want to pull a fresh snapshot from DIT, then run
build_rice_mills.py to regenerate data/rice-mills.json.

Usage:
    python scripts/fetch_rice_mills_api.py
"""
import os, sys, io, time, requests
import pandas as pd

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
OUTPUT = os.path.join(os.path.dirname(__file__), "..", "data", "rice-mills-api-snapshot.xlsx")
API_URL = "https://www.dit.go.th/api/RiceTradeApi/SearchRiceTrade"

# Columns to keep in the snapshot (drop PII-heavy contact fields)
KEEP_COLS = [
    "tName", "description", "millCapacity",
    "provinceName", "disctrictName", "subDisctrictName",
    "houseNo", "moo", "road", "tel", "fax",
    "licenseNo", "expireDate",
]


def fetch_all_mills() -> list[dict]:
    all_items: list[dict] = []
    r = requests.get(API_URL, params={"pageIndex": 1, "pageSize": 1000}, timeout=30)
    r.raise_for_status()
    data = r.json()
    total_pages = data.get("totalPages")
    if not total_pages:
        sys.exit("ERROR: DIT API did not return totalPages — cannot paginate safely")
    all_items.extend(data.get("items", []))
    print(f"  page 1/{total_pages}: {len(data.get('items', []))} records")

    for page in range(2, total_pages + 1):
        time.sleep(0.4)
        r = requests.get(API_URL, params={"pageIndex": page, "pageSize": 1000}, timeout=30)
        r.raise_for_status()
        items = r.json().get("items", [])
        all_items.extend(items)
        print(f"  page {page}/{total_pages}: {len(items)} records (total: {len(all_items)})")

    return [x for x in all_items if "โรงสี" in str(x.get("description", ""))]


def main() -> None:
    print("Fetching mills from DIT API...")
    mills = fetch_all_mills()
    if not mills:
        sys.exit("ERROR: API returned 0 mills — snapshot not updated")
    print(f"Mills found: {len(mills)}")

    df = pd.DataFrame(mills)
    df = df[[c for c in KEEP_COLS if c in df.columns]]
    df.to_excel(OUTPUT, index=False)
    print(f"Saved {len(df)} rows  ->  {OUTPUT}")
    print("Next: run  python scripts/build_rice_mills.py  to rebuild rice-mills.json")


if __name__ == "__main__":
    main()
