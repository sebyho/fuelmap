**Disclaimer:** This is a personal/hobby project. Prices are broad
government averages on a several-hours-to-monthly refresh cycle, not
live pump prices — don't rely on them for actual purchasing decisions.
Coverage is intentionally partial in places (see "Coverage & honest
limitations" below) rather than filled in with guesses. Provided as-is,
with no accuracy guarantee.

# Pump — broad fuel price map

A static, GitHub Pages-hostable map showing **broad fuel price averages** —
by state/region in the US, by country in the EU, national averages for the
UK, and by city in Canada — plus a WTI / Brent crude oil ticker. This isn't
a per-station map; it's built entirely from official government statistics,
refreshed on a schedule by a GitHub Actions workflow that writes plain JSON
into `/data`. No backend, no build step.

## How it works

```
GitHub Actions (cron, every 6h)
  → scripts/fetch_us.py       (EIA, needs free key)     → data/us.json
  → scripts/fetch_eu.py       (EU Oil Bulletin, no key)  → data/eu.json
  → scripts/fetch_uk.py       (DESNZ, no key)            → data/uk.json
  → scripts/fetch_canada.py   (StatCan, no key)          → data/canada.json
  → scripts/fetch_oil.py      (EIA, needs free key)      → data/oil_benchmarks.json
  → commits the updated JSON back to the repo
  → GitHub Pages serves the updated static site automatically
```

The frontend (`index.html` / `js/app.js`) is a plain Leaflet map that reads
those JSON files client-side.

## 1. Get a free API key

Only one is needed: **EIA** (used for both the US layer and the oil
benchmarks) — register at https://www.eia.gov/opendata/register.php, just an
email address, instant.

The EU, UK, and Canada sources need no key at all — they're public
government data/statistics endpoints.

## 2. Push this to GitHub, then add the key as a secret

1. Push this folder to a new GitHub repository.
2. **Settings → Secrets and variables → Actions → New repository secret**
3. Add `EIA_API_KEY` with your EIA key.

If it's missing, the US script and the oil benchmark script just log a
message and leave their existing JSON files untouched — nothing else breaks.

## 3. Enable GitHub Pages

**Settings → Pages → Source → Deploy from a branch → `main` / `(root)`**

Your site will be live at `https://<your-username>.github.io/<repo-name>/`.

## 4. Run the data pipeline

Runs automatically every 6 hours via `.github/workflows/update-data.yml`. To
fetch immediately: **Actions tab → "Update fuel & oil price data" → Run workflow**.

To test locally:

```bash
pip install -r scripts/requirements.txt
export EIA_API_KEY=your_key_here
python scripts/fetch_us.py
python scripts/fetch_eu.py
python scripts/fetch_uk.py
python scripts/fetch_canada.py
python scripts/fetch_oil.py
```

## Coverage & honest limitations

This is the part worth reading before you assume more granularity than
actually exists:

- **United States**: EIA's free weekly *Gasoline and Diesel Fuel Update*
  only publishes a national average, 5 PADD regions (East Coast, Midwest,
  Gulf Coast, Rocky Mountain, West Coast), and **9 individual states**
  (California, Colorado, Florida, Massachusetts, Minnesota, New York, Ohio,
  Texas, Washington) for gasoline — California is also the only state with
  its own diesel number. The other 41 states + DC are genuinely not in the
  free federal dataset; this project shows what EIA publishes rather than
  inventing per-state numbers for the rest. (Full 50-state daily data exists
  commercially via AAA/GasBuddy, but not as a free public API.)
- **EU**: all 27 member states, from the European Commission's Weekly Oil
  Bulletin — national average consumer prices including taxes. The bulletin
  is only published as an .xlsx file with no stable "latest" URL, so
  `fetch_eu.py` scrapes the bulletin page each run to find the current link,
  then parses the spreadsheet defensively (by keyword/country-name matching
  rather than fixed cell positions). If the Commission changes their sheet
  layout, the script logs a warning and leaves the existing data alone
  instead of writing garbage.
- **UK**: a single national average from DESNZ's official weekly road fuel
  price statistics (same "latest CSV link changes each week" scraping
  pattern as the EU source).
- **Canada**: Statistics Canada's open Table 18-10-0001-01 — **monthly**
  (not weekly), gasoline only (no diesel), for ~15 major cities plus the
  national average. Not a full province breakdown, and not weekly, because
  that's what the free official data actually offers.
- **Oil benchmarks**: EIA's WTI/Brent spot prices, updated once per business
  day, roughly a day behind live futures markets.
- **Color scale**: "cheap ↔ expensive" is computed *within* each region
  group (US vs EU vs UK vs Canada) only. Their currencies and units differ
  (USD/gallon, EUR/litre, GBP/litre, CAD/litre), so mixing them onto one
  scale would be misleading — the UI says this explicitly.

## Adding another country or region

1. Find an official statistics source (government energy agency, national
   statistics office) and check its terms of use — avoid anything that's
   itself scraped from paid data without a license to redistribute.
2. Write `scripts/fetch_<place>.py` that outputs this schema:
   ```json
   {
     "updated_at": "ISO-8601 timestamp",
     "source": "who publishes this",
     "unit": "e.g. EUR/L",
     "regions": [
       { "id": "...", "name": "...", "level": "country|state|city|national",
         "lat": 0, "lon": 0,
         "gasoline": { "value": 1.70, "date": "..." },
         "diesel": { "value": 1.60, "date": "..." } }
     ]
   }
   ```
3. Add a fetch step (+ secret, if needed) to `.github/workflows/update-data.yml`.
4. Add the file to `DATA_FILES` / `UNIT_LABEL` / `CURRENCY_SYMBOL` in
   `js/app.js`, and a filter chip in `index.html`.

## Project structure

```
index.html               map page
css/style.css              styling
js/app.js                   map + filters + ticker logic
data/*.json                 generated data (sample data checked in as placeholders)
scripts/fetch_*.py           one script per data source
scripts/geo_*.json           centroid / name-lookup tables used while parsing
.github/workflows/           the scheduled data pipeline
```

## License / attribution

The code here is GPL-licensed (see `LICENSE`). The data is not — each source
has its own terms, all of which permit public/FOSS reuse with attribution.
**See `DATA_LICENSES.md` for the actual license of each source**, checked
against the publishers directly (EU = CC BY 4.0, UK = Open Government
Licence, Canada = Statistics Canada Open Licence, US federal data = public
domain), plus a note on why the map tiles changed from CARTO to plain
OpenStreetMap tiles.

Before making this public, update the placeholder repo URL in the
`User-Agent` header inside `scripts/fetch_eu.py`, `scripts/fetch_uk.py`, and
`scripts/fetch_canada.py` to point at your real repo — those scripts poll
government pages on a schedule and should identify themselves honestly
rather than pretend to be a browser.
