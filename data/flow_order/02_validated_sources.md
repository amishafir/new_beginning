# Source Validation: River Flow Order

## Task
Validate candidate sources for computing upstream/downstream country ordering on transboundary rivers.

## Validation Results

| Source | Authority | Currency | Coverage | Structured? | Verdict | Reasoning |
|--------|-----------|----------|----------|-------------|---------|-----------|
| **HydroRIVERS v10** | 5/5 | 4/5 | 5/5 | ✅ Shapefile/GDB | **APPROVED** | See detailed assessment below |
| **RiverATLAS v10** | 5/5 | 4/5 | 5/5 | ✅ Shapefile/GDB | **APPROVED (backup)** | Same reaches as HydroRIVERS + `gad` country code field. Use if spatial intersection with country polygons proves problematic |
| **HydroBASINS** | 5/5 | 4/5 | 3/5 | ✅ Shapefile/GDB | SKIP | Sub-basin level, not river-reach level. Pfafstetter codes help with up/down navigation but don't give per-country flow order directly |
| **GRIT** | 3/5 | 4/5 | 4/5 | ✅ GeoPackage | SKIP | 27.6 GB download, CC BY-NC license (non-commercial only), academic source with no long-term maintenance guarantee. Overkill |
| **MERIT Hydro** | 4/5 | 3/5 | 2/5 | ⚠️ Raster GeoTIFF | SKIP | Raster format requires heavy GIS processing to convert to vector. Wrong tool for this job |
| **TWAP River Basins** | 4/5 | 2/5 | 1/5 | ⚠️ Portal timed out | SKIP | Uses TFDD/HydroBASINS as base — no additional flow order data. Risk indicators, not hydrological topology. Portal unreliable |
| **TFDD Spatial Database** | 5/5 | 5/5 | 0/5 | ✅ Shapefile | SKIP | Already in repo. Confirmed: **no flow order attribute**. Has BCU polygons (useful for intersection step) |

---

## Detailed Assessment: HydroRIVERS v10

### Authority: 5/5
- **Data originator**: WWF in partnership with McGill University (Global HydroLAB), led by Prof. Bernhard Lehner
- **Derived from**: NASA SRTM elevation data (the gold standard for global elevation)
- **Institutional backing**: WWF, USGS, DLR, McGill — not going away
- **Cited in**: 10,000+ scientific publications
- **Used by TFDD itself**: The TWAP assessment (which TFDD contributes to) uses HydroBASINS as its spatial base. HydroRIVERS and HydroBASINS share the same underlying hydrological grid. This means HydroRIVERS reaches will align spatially with TFDD basin polygons — they're derived from the same elevation model.

### Currency: 4/5
- **Version**: v10 (current)
- **v2 in development**: Based on TanDEM-X (12m resolution, full global coverage including high latitudes). Not yet released.
- **Last file upload**: April 2022 (from HTTP headers: `x-bz-info-src_last_modified_millis`)
- **Not stale**: River networks don't change. The underlying SRTM data is from 2000, but rivers are geologically stable. v10 is fit for purpose.
- Deducted 1 point because v2 exists in development and v10 is 4+ years old, though this doesn't affect our use case.

### Coverage: 5/5
- **8.5 million river reaches** globally
- **35.9 million km** of rivers
- Includes all rivers with catchment ≥10 km² or discharge ≥0.1 m³/s
- All 313 TFDD transboundary basins contain rivers well above this threshold
- Covers endorheic basins (flagged via `ENDORHEIC` field)
- Every continent except Antarctica

### Data accessibility: Excellent
- **No registration required** — direct HTTP download confirmed
- **Response**: HTTP 200, `content-type: application/zip`, served via Cloudflare CDN
- **File sizes**: 68 MB (Europe) to 544 MB (Global) — manageable
- **Formats**: ESRI Shapefile and Geodatabase
- **Regional downloads available**: Can download just the continents we need

### License: Free
- "Freely available for scientific, educational and commercial use"
- Citation required: Lehner & Grill (2013), Hydrological Processes, 27(15): 2171–2186
- Product-specific terms apply but no restrictive clauses found

### Key fields confirmed (from ESRI feature service schema)
| Field | Type | Confirmed? |
|-------|------|------------|
| `hyriv_id` | Integer | ✅ |
| `next_down` | Integer | ✅ |
| `main_riv` | Integer | ✅ |
| `length_km` | Double | ✅ |
| `dist_dn_km` | Double | ✅ |
| `dist_up_km` | Double | ✅ |
| `catch_skm` | Double | ✅ |
| `upland_skm` | Double | ✅ |
| `endorheic` | SmallInt | ✅ |
| `dis_av_cms` | Double | ✅ |
| `ord_stra` | SmallInt | ✅ |
| `ord_clas` | SmallInt | ✅ |
| `ord_flow` | SmallInt | ✅ |
| `hybas_l12` | Double | ✅ |

All fields confirmed via live ESRI FeatureServer hosting HydroRIVERS_v10.

### What HydroRIVERS CANNOT provide
- **Country codes per reach** — reaches are river lines, not political units. We need to spatially intersect them with country polygons (from TFDD BCU or Natural Earth).
- **River names** — HydroRIVERS has no river name field. We match to TFDD basins via spatial overlap, not by name.
- **Basin-level grouping matching TFDD** — `MAIN_RIV` groups by hydrological basin, which may not perfectly align with TFDD's political basin definitions.

---

## Detailed Assessment: RiverATLAS v10 (backup)

### Why it's a backup, not primary
RiverATLAS contains the **same 8.5M river reaches** as HydroRIVERS, with the same geometry and topology fields (`NEXT_DOWN`, `DIST_DN_KM`, etc.), PLUS 281 additional attributes including a `gad` field (Global Administrative Areas — likely country/admin codes per reach).

If `gad` provides country codes per reach, it would **eliminate the need for spatial intersection** with country polygons — we'd just read the country directly from the attribute table. This would be simpler and faster.

**However**: RiverATLAS is ~6 GB (vs 544 MB for HydroRIVERS). The `gad` field contents are unverified — it might be a sub-basin admin code, not a country code. We should inspect HydroRIVERS first; if spatial intersection proves problematic, fall back to RiverATLAS.

### Verdict: APPROVED as backup
- Same authority, currency, coverage as HydroRIVERS
- Adds potentially useful `gad` country field
- Much larger download for one potentially useful field
- Use only if HydroRIVERS + spatial intersection doesn't work

---

## Recommendation

**Primary source: HydroRIVERS v10**
- Download regional shapefiles (not global — saves bandwidth, can test with one region first)
- Start with Europe (68 MB) — has well-known rivers (Danube, Rhine, Elbe) for validation against known flow orders
- The `DIST_DN_KM` field is the key: it directly encodes how far upstream each reach is

**Backup: RiverATLAS v10**
- Only if spatial intersection with country polygons fails or is too slow
- The `gad` field might provide country codes directly, avoiding spatial computation

**Next step**: `/data-inspector` in enrichment mode — download a regional HydroRIVERS file, test spatial intersection with TFDD BCU polygons for 3-5 known rivers, verify that `DIST_DN_KM` produces correct country ordering.
