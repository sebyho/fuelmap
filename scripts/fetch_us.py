#!/usr/bin/env python3
"""
Fetch broad-brush US gasoline & diesel prices: national average, the 5 PADD
regions, and the 9 states EIA tracks individually in its weekly survey.

Requires a free API key: https://www.eia.gov/opendata/register.php
Set it as the EIA_API_KEY environment variable / GitHub Actions secret.
(Same key used by fetch_oil.py for WTI/Brent.)

What EIA actually publishes weekly, geographically (Gasoline and Diesel Fuel
Update): a national average, 5 PADD regions, and only 9 individual states
(California, Colorado, Florida, Massachusetts, Minnesota, New York, Ohio,
Texas, Washington) for gasoline. Diesel is published nationally and by PADD
region, plus California individually.

There is no free weekly source with real per-state numbers for the other 41
states + DC, so this script does NOT invent state-level diesel/gasoline
figures for them — the frontend shows national/PADD/state markers only, at
the granularity EIA actually reports.

Docs: https://www.eia.gov/opendata/  (dataset: petroleum/pri/gnd)
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

ROOT = Path(__file__).resolve().parent.parent
GEO_FILE = ROOT / "scripts" / "geo_us.json"
OUTPUT_FILE = ROOT / "data" / "us.json"
API_URL = "https://api.eia.gov/v2/petroleum/pri/gnd/data/"

# EIA product codes -> our schema keys
PRODUCTS = {"EPMR": "gasoline", "EPD2D": "diesel"}


def fetch_series(api_key: str, product: str, area: str):
    series_id = f"EMM_{product}_PTE_{area}_DPG" if product == "EPMR" else f"EMD_{product}_PTE_{area}_DPG"
    params = [
        ("api_key", api_key),
        ("frequency", "weekly"),
        ("data[0]", "value"),
        ("facets[series][]", series_id),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", "1"),
    ]
    url = f"{API_URL}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as e:
        print(f"  request failed for {series_id}: {e}", file=sys.stderr)
        return None

    rows = payload.get("response", {}).get("data", [])
    # EIA returns "value" as a JSON string (e.g. "3.142"), not a number —
    # convert explicitly rather than assuming it's already numeric.
    usable = []
    for r in rows:
        try:
            r["value"] = float(r.get("value"))
            usable.append(r)
        except (TypeError, ValueError):
            continue
    rows = usable
    if not rows:
        print(f"  no data for {series_id}", file=sys.stderr)
        return None
    return {"value": round(rows[0]["value"], 3), "date": rows[0].get("period")}


def main() -> int:
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        print(
            "EIA_API_KEY is not set — skipping US fetch and leaving the "
            "existing data/us.json untouched.",
            file=sys.stderr,
        )
        return 0

    geo = json.loads(GEO_FILE.read_text(encoding="utf-8"))
    regions = []

    # National average
    print("Fetching national average...")
    nat = {"id": "US", "name": "U.S. national average", "level": "national",
           "lat": geo["national_centroid"][0], "lon": geo["national_centroid"][1]}
    for code, key in PRODUCTS.items():
        val = fetch_series(api_key, code, "NUS")
        if val:
            nat[key] = val
    regions.append(nat)

    # PADD regions
    for padd, area in geo["padd_series_area"].items():
        print(f"Fetching {padd}...")
        entry = {
            "id": padd, "name": geo["padd_labels"][padd], "level": "padd",
            "lat": geo["padd_centroid"][padd][0], "lon": geo["padd_centroid"][padd][1],
        }
        for code, key in PRODUCTS.items():
            val = fetch_series(api_key, code, area)
            if val:
                entry[key] = val
        regions.append(entry)

    # Individually-tracked states
    for abbr, info in geo["states"].items():
        series = info.get("series")
        if not series:
            continue  # this state isn't in EIA's individual weekly survey
        print(f"Fetching {info['name']}...")
        entry = {
            "id": f"US-{abbr}", "name": info["name"], "level": "state",
            "padd": info["padd"], "lat": info["lat"], "lon": info["lon"],
        }
        for code, key in PRODUCTS.items():
            val = fetch_series(api_key, code, series)
            if val:
                entry[key] = val
        regions.append(entry)

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source": "U.S. Energy Information Administration (EIA), weekly Gasoline and Diesel Fuel Update",
        "unit": "USD/gal",
        "note": (
            "EIA's free weekly survey only covers the national average, 5 PADD "
            "regions, and 9 individual states (CA, CO, FL, MA, MN, NY, OH, TX, WA "
            "for gasoline; CA additionally for diesel). Other states are not shown "
            "individually rather than guessed at."
        ),
        "regions": regions,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(regions)} regions to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
