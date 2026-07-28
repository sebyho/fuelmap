#!/usr/bin/env python3
"""
Fetch monthly average retail gasoline prices for Canada from Statistics
Canada's Web Data Service (WDS) — table 18-10-0001-01, "Monthly average
retail prices for gasoline and fuel oil, by geography".

No API key required — this is a fully public government API.

Note this table is MONTHLY (not weekly like the other sources here) and
covers regular unleaded gasoline in ~10-15 major cities plus the national
average; it does not include diesel or a province-by-province breakdown.
That's the real shape of StatCan's free published data, so that's what we
show rather than extrapolating.

Docs: https://www.statcan.gc.ca/en/developers/wds/user-guide
"""

import csv
import io
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
GEO_FILE = ROOT / "scripts" / "geo_canada.json"
OUTPUT_FILE = ROOT / "data" / "canada.json"
PRODUCT_ID = "18100001"  # table 18-10-0001-01
WDS_URL = f"https://www150.statcan.gc.ca/t1/wds/rest/getFullTableDownloadCSV/{PRODUCT_ID}/en"
HEADERS = {"User-Agent": "pump-fuelmap/1.0 (open-source fuel price map; https://github.com/sebyho/fuelmap)"}


def fetch_bytes(url: str) -> bytes | None:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=60) as resp:
            return resp.read()
    except (HTTPError, URLError) as e:
        print(f"  request failed: {e}", file=sys.stderr)
        return None


def normalize(s: str) -> str:
    return s.strip().upper()


def main() -> int:
    geo = json.loads(GEO_FILE.read_text(encoding="utf-8"))

    print("Asking StatCan WDS for the table download link...")
    meta_raw = fetch_bytes(WDS_URL)
    if not meta_raw:
        return 0

    try:
        meta = json.loads(meta_raw.decode("utf-8"))
        zip_url = meta["object"]
    except (KeyError, ValueError) as e:
        print(f"Unexpected WDS response shape: {e}", file=sys.stderr)
        return 0

    print(f"Downloading {zip_url}")
    zip_bytes = fetch_bytes(zip_url)
    if not zip_bytes:
        return 0

    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            csv_name = next(n for n in zf.namelist() if n.endswith(".csv") and "MetaData" not in n)
            with zf.open(csv_name) as f:
                text = f.read().decode("utf-8-sig", errors="ignore")
    except (zipfile.BadZipFile, StopIteration) as e:
        print(f"Could not read the table zip: {e}", file=sys.stderr)
        return 0

    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []

    geo_col = next((c for c in fieldnames if "GEO" in c.upper()), None)
    type_col = next((c for c in fieldnames if "TYPE" in c.upper() and "FUEL" in c.upper()), None)
    if type_col is None:
        type_col = next((c for c in fieldnames if "PRODUCT" in c.upper()), None)
    ref_col = next((c for c in fieldnames if "REF_DATE" in c.upper()), None)
    val_col = next((c for c in fieldnames if c.upper() == "VALUE"), None)

    if not all([geo_col, ref_col, val_col]):
        print(f"Could not identify expected columns in {fieldnames}", file=sys.stderr)
        return 0

    # Keep only "Regular unleaded gasoline at self service filling stations"
    # rows if a fuel-type column exists; otherwise take everything (older
    # vintages of this table sometimes split this differently).
    latest_by_geo = {}
    for row in reader:
        geo_label = normalize(row.get(geo_col, ""))
        if type_col and "REGULAR" not in normalize(row.get(type_col, "")):
            continue
        ref_date = row.get(ref_col, "")
        value = row.get(val_col, "")
        if not value:
            continue
        try:
            value_f = float(value)
        except ValueError:
            continue

        # match against our known city list (strip province suffix e.g. ", Ont.")
        city_key = geo_label.split(",")[0].strip()
        prev = latest_by_geo.get(city_key)
        if not prev or ref_date > prev["date"]:
            latest_by_geo[city_key] = {"date": ref_date, "value": value_f}

    regions = []
    for city_key, rec in latest_by_geo.items():
        info = geo["cities"].get(city_key)
        if not info:
            continue
        regions.append({
            "id": f"CA-{city_key.replace(' ', '-')}",
            "name": info["display"],
            "level": "national" if info["province"] is None else "city",
            "province": info["province"],
            "lat": info["lat"],
            "lon": info["lon"],
            "gasoline": {"value": round(rec["value"] / 100, 3), "date": rec["date"]},
        })

    if not regions:
        print("No matching Canadian cities found in the table; leaving existing data/canada.json untouched.", file=sys.stderr)
        return 0

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": "Statistics Canada, Table 18-10-0001-01 (monthly average retail gasoline prices)",
        "unit": "CAD/L",
        "note": "Monthly (not weekly) data, regular unleaded gasoline only, for major cities StatCan tracks — not a full province breakdown.",
        "regions": regions,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(regions)} Canadian regions to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
