#!/usr/bin/env python3
"""
Fetch WTI and Brent crude spot prices from the U.S. EIA (Energy Information
Administration) open data API v2.

Requires a free API key: https://www.eia.gov/opendata/register.php
Set it as the EIA_API_KEY environment variable / GitHub Actions secret.

Series used (EIA "petroleum/pri/spt" spot price dataset):
  RWTC  = Cushing, OK WTI Spot Price FOB (USD/barrel)
  RBRTE = Europe Brent Spot Price FOB (USD/barrel)

Note: EIA publishes daily spot prices with roughly a one-business-day lag —
this is a benchmark reference, not a live futures tick.
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
OUTPUT_FILE = ROOT / "data" / "oil_benchmarks.json"
API_URL = "https://api.eia.gov/v2/petroleum/pri/spt/data/"

SERIES = {
    "RWTC": {"key": "wti", "name": "WTI Crude (Cushing)"},
    "RBRTE": {"key": "brent", "name": "Brent Crude"},
}


def fetch_series(api_key: str, series_id: str) -> list[dict]:
    params = [
        ("api_key", api_key),
        ("frequency", "daily"),
        ("data[0]", "value"),
        ("facets[series][]", series_id),
        ("sort[0][column]", "period"),
        ("sort[0][direction]", "desc"),
        ("length", "5"),
    ]
    url = f"{API_URL}?{urlencode(params)}"
    try:
        with urlopen(url, timeout=20) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError) as e:
        print(f"  request failed for {series_id}: {e}", file=sys.stderr)
        return []

    return payload.get("response", {}).get("data", [])


def main() -> int:
    api_key = os.environ.get("EIA_API_KEY")
    if not api_key:
        print(
            "EIA_API_KEY is not set — skipping oil benchmark fetch and "
            "leaving the existing data/oil_benchmarks.json untouched.",
            file=sys.stderr,
        )
        return 0

    series_out = {}
    for series_id, meta in SERIES.items():
        print(f"Fetching {meta['name']} ({series_id})...")
        rows = fetch_series(api_key, series_id)
        # rows are sorted newest-first. EIA returns "value" as a JSON
        # string (e.g. "66.42"), not a number — convert explicitly rather
        # than assuming it's already numeric.
        usable = []
        for r in rows:
            try:
                r["value"] = float(r.get("value"))
                usable.append(r)
            except (TypeError, ValueError):
                continue
        rows = usable
        if not rows:
            print(f"  no usable rows for {series_id}", file=sys.stderr)
            continue

        latest = rows[0]
        previous = rows[1] if len(rows) > 1 else None

        series_out[meta["key"]] = {
            "name": meta["name"],
            "unit": "USD/bbl",
            "latest": round(float(latest["value"]), 2),
            "previous": round(float(previous["value"]), 2) if previous else None,
            "date": latest.get("period"),
        }

    if not series_out:
        print("No benchmark series were fetched successfully; leaving file untouched.", file=sys.stderr)
        return 0

    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "series": series_out,
    }

    OUTPUT_FILE.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote benchmark data to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
