#!/usr/bin/env python3
"""
Fetch the UK national average petrol & diesel price from DESNZ's Weekly Road
Fuel Prices statistics (published on gov.uk, sourced from the CMA Road Fuel
Prices Scheme).

No API key required. Like the EU bulletin, the CSV is republished under a
new URL each week, so this scrapes the statistics page for the current CSV
link rather than hardcoding one.

Source page: https://www.gov.uk/government/statistics/weekly-road-fuel-prices
CSV columns (confirmed from a live file): Date, ULSP pump price
(pence/litre), ULSD pump price (pence/litre), plus duty/VAT columns we don't
need.
"""

import csv
import io
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT / "data" / "uk.json"
STATS_PAGE = "https://www.gov.uk/government/statistics/weekly-road-fuel-prices"
HEADERS = {"User-Agent": "pump-fuelmap/1.0 (open-source fuel price map; github.com/YOUR_USERNAME/YOUR_REPO)"}

# Centre-of-UK-ish point for a single national marker
UK_LAT, UK_LON = 54.0, -2.5


def fetch_text(url: str) -> str | None:
    try:
        req = Request(url, headers=HEADERS)
        with urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except (HTTPError, URLError) as e:
        print(f"  request failed: {e}", file=sys.stderr)
        return None


def find_csv_url(html: str) -> str | None:
    matches = re.findall(r'href="([^"]+weekly_road_fuel_prices[^"]*\.csv)"', html, re.IGNORECASE)
    if not matches:
        return None
    url = matches[0]
    return url if url.startswith("http") else f"https://www.gov.uk{url}"


def main() -> int:
    print("Fetching DESNZ weekly road fuel prices page...")
    html = fetch_text(STATS_PAGE)
    if not html:
        return 0

    csv_url = find_csv_url(html)
    if not csv_url:
        print("Could not find the weekly road fuel prices CSV link.", file=sys.stderr)
        return 0

    print(f"Downloading {csv_url}")
    csv_text = fetch_text(csv_url)
    if not csv_text:
        return 0

    reader = list(csv.reader(io.StringIO(csv_text)))
    if len(reader) < 2:
        print("CSV had no data rows.", file=sys.stderr)
        return 0

    header = [h.strip() for h in reader[0]]
    last_row = reader[-1]

    def find_col(keyword_all: list[str]):
        for i, h in enumerate(header):
            hu = h.upper()
            if all(k in hu for k in keyword_all):
                return i
        return None

    date_col = 0
    petrol_col = find_col(["ULSP", "PUMP"])
    diesel_col = find_col(["ULSD", "PUMP"])

    if petrol_col is None or diesel_col is None:
        print("Could not identify petrol/diesel columns in the CSV header.", file=sys.stderr)
        return 0

    try:
        petrol_pence = float(last_row[petrol_col])
        diesel_pence = float(last_row[diesel_col])
        date = last_row[date_col]
    except (ValueError, IndexError) as e:
        print(f"Could not parse the latest row: {e}", file=sys.stderr)
        return 0

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": "DESNZ, Weekly Road Fuel Prices (gov.uk / CMA Road Fuel Prices Scheme)",
        "unit": "GBP/L",
        "regions": [
            {
                "id": "GB",
                "name": "United Kingdom national average",
                "level": "country",
                "lat": UK_LAT,
                "lon": UK_LON,
                "gasoline": {"value": round(petrol_pence / 100, 3), "date": date},
                "diesel": {"value": round(diesel_pence / 100, 3), "date": date},
            }
        ],
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote UK national average to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
