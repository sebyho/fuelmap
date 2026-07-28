/* Pump — broad fuel-price map
 * Reads static JSON built by the GitHub Actions data pipeline (see /scripts)
 * and renders country/state/region-level markers on a Leaflet map.
 */

(function () {
  "use strict";

  const DATA_FILES = {
    us: "data/us.json",
    eu: "data/eu.json",
    uk: "data/uk.json",
    ca: "data/canada.json",
    oil: "data/oil_benchmarks.json",
  };

  const UNIT_LABEL = { us: "USD/gal", eu: "EUR/L", uk: "GBP/L", ca: "CAD/L" };
  const CURRENCY_SYMBOL = { us: "$", eu: "\u20ac", uk: "\u00a3", ca: "$" };

  const state = {
    regionFilter: "all",
    fuel: "gasoline",
    datasets: {}, // key -> parsed dataset {source, unit, regions:[...]}
    markersLayer: L.layerGroup(),
  };

  const map = L.map("map", {
    zoomControl: false,
    attributionControl: true,
    minZoom: 3,
    maxZoom: 8,
    worldCopyJump: true,
    // Web Mercator has no valid tiles past ~85°N/S — none of our regions
    // are anywhere near there, so just hard-limit panning/zooming to a
    // band that always has real tiles, instead of letting the view drift
    // into the blank area above/below that cutoff.
    maxBounds: [[-58, -170], [78, 170]],
    maxBoundsViscosity: 1.0,
  }).setView([40, -30], 3);

  L.control.zoom({ position: "bottomright" }).addTo(map);

  // Stadia Maps' "Alidade Smooth Dark" — a genuinely dark-styled tileset
  // (not a CSS filter trick), so it doesn't touch the GPU compositor path
  // that caused rendering bugs on some systems. Free for non-commercial use;
  // no API key needed for localhost. For a public deploy (e.g. GitHub
  // Pages), add your domain at https://client.stadiamaps.com/dashboard/ —
  // no code change or exposed key required. See README for details.
  L.tileLayer(
    "https://tiles.stadiamaps.com/tiles/alidade_smooth_dark/{z}/{x}/{y}{r}.png",
    {
      attribution:
        '&copy; <a href="https://stadiamaps.com/" target="_blank">Stadia Maps</a> ' +
        '&copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> ' +
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors',
      maxZoom: 20,
    }
  ).addTo(map);

  state.markersLayer.addTo(map);

  // Leaflet measures its container once at init; if a later layout shift
  // (web fonts loading, window resize, etc.) changes the actual size of
  // #map, tell it to re-measure rather than silently misrendering tiles.
  new ResizeObserver(() => map.invalidateSize()).observe(document.getElementById("map"));

  async function fetchJSON(path) {
    try {
      const res = await fetch(path, { cache: "no-store" });
      if (!res.ok) throw new Error(`${path}: ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn("Could not load", path, err);
      return null;
    }
  }

  function timeAgo(iso) {
    if (!iso) return "no data yet";
    const then = new Date(iso).getTime();
    const diffMin = Math.round((Date.now() - then) / 60000);
    if (diffMin < 1) return "just now";
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffH = Math.round(diffMin / 60);
    if (diffH < 48) return `${diffH}h ago`;
    return `${Math.round(diffH / 24)}d ago`;
  }

  function setSourceMeta(key, iso, staleHours) {
    const el = document.querySelector(`[data-source-meta="${key}"]`);
    if (!el) return;
    el.textContent = timeAgo(iso);
    const ageH = iso ? (Date.now() - new Date(iso).getTime()) / 3600000 : Infinity;
    el.classList.toggle("stale", ageH > staleHours);
    el.classList.toggle("fresh", ageH <= staleHours);
  }

  function priceFor(region, fuel) {
    const v = region[fuel];
    if (!v || typeof v.value !== "number") return null;
    return v.value;
  }

  function computeTiers(values) {
    const sorted = [...values].sort((a, b) => a - b);
    const q = (p) => sorted[Math.min(sorted.length - 1, Math.floor(p * (sorted.length - 1)))];
    return { low: q(0.33), high: q(0.66) };
  }

  function tierClass(price, tiers) {
    if (price <= tiers.low) return "tier-cheap";
    if (price >= tiers.high) return "tier-pricey";
    return "tier-mid";
  }

  function escapeHtml(str) {
    return String(str).replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
    }[c]));
  }

  function renderMarkers() {
    state.markersLayer.clearLayers();

    const groups = Object.entries(state.datasets).filter(
      ([key]) => state.regionFilter === "all" || state.regionFilter === key
    );

    groups.forEach(([key, ds]) => {
      if (!ds || !Array.isArray(ds.regions)) return;

      const priced = ds.regions
        .map((r) => ({ r, p: priceFor(r, state.fuel) }))
        .filter((x) => x.p !== null);

      if (priced.length === 0) return;

      // Tiers computed WITHIN this dataset only — different currencies/units
      // aren't comparable on one scale, so "cheap/expensive" is relative to
      // that region group, not global.
      const tiers = computeTiers(priced.map((x) => x.p));
      const symbol = CURRENCY_SYMBOL[key] || "";
      const unit = UNIT_LABEL[key] || ds.unit || "";

      priced.forEach(({ r, p }) => {
        const cls = tierClass(p, tiers);
        const label = `${symbol}${p.toFixed(2)}`;
        const icon = L.divIcon({
          className: "",
          html: `<div class="led-sign"><div class="led-badge ${cls}">${label}</div><div class="led-post"></div></div>`,
          iconSize: null,
          iconAnchor: [26, 26],
        });
        const marker = L.marker([r.lat, r.lon], { icon });

        const gas = priceFor(r, "gasoline");
        const diesel = priceFor(r, "diesel");
        const rows = [
          gas !== null ? `<div class="popup-price-row"><span>Gasoline / Petrol</span><span class="p-val">${symbol}${gas.toFixed(3)}</span></div>` : "",
          diesel !== null ? `<div class="popup-price-row"><span>Diesel</span><span class="p-val">${symbol}${diesel.toFixed(3)}</span></div>` : "",
        ].join("");

        const dateStr = (r.gasoline && r.gasoline.date) || (r.diesel && r.diesel.date) || "";

        marker.bindPopup(
          `<div class="popup-station-name">${escapeHtml(r.name)}</div>
           ${rows}
           <div class="popup-meta">${escapeHtml(unit)}${dateStr ? " &middot; " + escapeHtml(dateStr) : ""}</div>`
        );

        state.markersLayer.addLayer(marker);
      });
    });
  }

  function renderTicker(oil) {
    const el = document.getElementById("ticker");
    if (!oil || !oil.series) {
      el.innerHTML = `<span class="ticker-item">benchmark data unavailable</span>`;
      return;
    }
    const items = Object.values(oil.series).map((s) => {
      const delta = s.previous ? s.latest - s.previous : 0;
      const dir = delta > 0 ? "up" : delta < 0 ? "down" : "";
      const arrow = delta > 0 ? "&#9650;" : delta < 0 ? "&#9660;" : "&#9679;";
      return `<span class="ticker-item">
        <span class="tk-name">${escapeHtml(s.name)}</span>
        <span class="tk-val">$${s.latest.toFixed(2)}</span>
        <span class="tk-delta ${dir}">${arrow} ${Math.abs(delta).toFixed(2)}</span>
      </span>`;
    });
    el.innerHTML = items.join("") + items.join("");
  }

  function wireControls() {
    document.querySelectorAll("#region-chips .chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#region-chips .chip").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.regionFilter = btn.dataset.region;
        renderMarkers();
      });
    });
    document.querySelectorAll("#fuel-chips .chip").forEach((btn) => {
      btn.addEventListener("click", () => {
        document.querySelectorAll("#fuel-chips .chip").forEach((b) => b.classList.remove("active"));
        btn.classList.add("active");
        state.fuel = btn.dataset.fuel;
        renderMarkers();
      });
    });
  }

  async function boot() {
    wireControls();
    const statusEl = document.getElementById("global-status");

    const [us, eu, uk, ca, oil] = await Promise.all([
      fetchJSON(DATA_FILES.us),
      fetchJSON(DATA_FILES.eu),
      fetchJSON(DATA_FILES.uk),
      fetchJSON(DATA_FILES.ca),
      fetchJSON(DATA_FILES.oil),
    ]);

    state.datasets = { us, eu, uk, ca };

    setSourceMeta("us", us && us.updated_at, 24 * 8);
    setSourceMeta("eu", eu && eu.updated_at, 24 * 8);
    setSourceMeta("uk", uk && uk.updated_at, 24 * 8);
    setSourceMeta("ca", ca && ca.updated_at, 24 * 40);
    setSourceMeta("oil", oil && oil.updated_at, 30);

    renderMarkers();
    renderTicker(oil);

    const totalRegions = Object.values(state.datasets)
      .filter(Boolean)
      .reduce((sum, ds) => sum + (ds.regions ? ds.regions.length : 0), 0);

    if (totalRegions === 0) {
      statusEl.innerHTML = `<span class="dot" style="background:#e6483c;box-shadow:0 0 6px #e6483c"></span> no data yet — run the fetch scripts`;
    } else {
      statusEl.innerHTML = `<span class="dot dot-live"></span> ${totalRegions} regions loaded`;
    }
  }

  boot();
})();
