# Data licenses

The code in this repo is MIT-licensed (see `LICENSE`). The *data* it fetches
and displays comes from four government sources, each under its own terms.
This file states what those terms actually are — checked against the
publishers' own license pages, not assumed.

## United States — EIA

U.S. federal government data is not subject to domestic copyright (17 U.S.C.
§ 105) — it's public domain. No attribution is legally required, though it's
good practice and this project credits EIA in the UI and README anyway.
EIA's API terms ask that you not hammer the API (a free key + reasonable
polling, which is what this project does, is fine).

## European Union — Weekly Oil Bulletin

Licensed under the Commission's reuse policy (**Commission Decision
2011/833/EU**), implemented as **Creative Commons Attribution 4.0
International (CC BY 4.0)**. This means:
- Reuse, including commercial reuse, is allowed.
- You must give appropriate credit and indicate if changes were made.
- EU logos/emblems are excluded from this license (we don't use any).

Source: https://data.europa.eu/en/legal-notice

## United Kingdom — DESNZ

Published under the **Open Government Licence (OGL)**, which permits
copying, adapting, and commercial or non-commercial redistribution, subject
to acknowledging the source.

Source: https://www.nationalarchives.gov.uk/doc/open-government-licence/

## Canada — Statistics Canada

Published under the **Statistics Canada Open Licence**, which grants a
worldwide, royalty-free, non-exclusive right to use, reproduce, publish,
distribute, or sell the information and derived products, for commercial or
non-commercial purposes, provided you:
- reproduce the information accurately,
- don't imply Statistics Canada endorses you or your product,
- don't misrepresent the information or its source, and
- don't use Government of Canada symbols/wordmarks/crests without separate
  written authorization (this project doesn't use any).

Source: https://www.statcan.gc.ca/en/terms-conditions/open-licence

## What this project does to comply

- Each data panel and the README name the source and, for CC BY/OGL-covered
  data, the license.
- No government logos, crests, or wordmarks are used anywhere in the UI.
- Nothing here claims or implies endorsement by EIA, the European
  Commission, DESNZ, or Statistics Canada.
- Automated requests (the EU/UK page-scraping steps, in particular) send an
  honest, identifying `User-Agent` rather than pretending to be a browser —
  update the placeholder repo URL in `scripts/fetch_eu.py`,
  `scripts/fetch_uk.py`, and `scripts/fetch_canada.py` to your actual repo
  once it's live.

## Map tiles: two iterations to get right

**Iteration 1** used CARTO's hosted dark basemap tiles (`basemaps.cartocdn.com`).
CARTO's current terms restrict free use of that hosted tile service to their
own platform users and non-profit grantees — public/commercial use requires
an Enterprise license. Wrong fit for a public FOSS site.

**Iteration 2** switched to plain OpenStreetMap tiles (free, no key, under
OSM's Tile Usage Policy) with the dark look faked via a CSS `filter: invert()`
on the tile layer. This turned out to trigger a real GPU-compositor bug on
at least one Linux system — the `filter`/`backdrop-filter` combination
caused an entire floating panel to render invisibly (correct layout, correct
z-index, correct hit-testing, just not actually painted) unless hardware
acceleration was disabled browser-wide, which is a bad tradeoff for one
site's visual style.

**Iteration 3 (current)** uses Stadia Maps' **Alidade Smooth Dark** style —
a genuinely dark-designed tileset (not a CSS filter), so it doesn't touch
the codepath that caused the bug. Terms, confirmed directly against Stadia's
docs:
- Free for non-commercial and personal-project use, no credit card.
- **No API key needed for `localhost` development** (rate-limited, but
  sufficient for testing).
- For a public deploy, no key is needed in the code either — you add your
  domain once at https://client.stadiamaps.com/dashboard/ (free), and Stadia
  authenticates requests by browser `Origin`/`Referer` headers instead.
- Required attribution (already wired into both the Leaflet attribution
  control and the page footer):
  `© Stadia Maps © OpenMapTiles © OpenStreetMap`

If you ever want the tiles to look different, that's a one-line style-name
swap in `js/app.js` (Stadia has other styles — see
https://docs.stadiamaps.com/themes/) rather than a provider migration.
