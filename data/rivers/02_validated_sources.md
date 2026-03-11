# Validated Sources: Cross-Border Rivers

## Validation Results

| # | Source | Authority | Currency | Coverage | Structured Data? | Has Countries? | Verdict |
|---|--------|-----------|----------|----------|-------------------|----------------|---------|
| 1 | OSU TFDD Spatial Database | 5/5 | 5/5 (2024) | 5/5 (313 basins) | Yes (Shapefile) | YES — Basin Country Units explicitly map basin→country | **APPROVED — PRIMARY** |
| 2 | OSU Spatial Downloads | — | — | — | — | — | **SKIP — Duplicate of #1** |
| 3 | TFDD Explorer (GitHub) | 5/5 | 4/5 | 3/5 | Partial (CSV for events, TopoJSON for basins) | Yes (in attribute tables) | **APPROVED — SUPPLEMENTARY** for treaties/events data |
| 4 | UNESCO IHP-WINS | 5/5 | 3/5 | 4/5 (151 countries) | Yes (Shapefile) | Likely but unverified | **INSPECT FURTHER** — need to download and check fields |
| 5 | GRDC Major River Basins | 5/5 | 4/5 | 4/5 (520 basins, 250+ transboundary) | Yes (GeoJSON + Shapefile) | NO — has basin names but NOT which countries each crosses | **APPROVED — SUPPLEMENTARY** for basin names/geometry only |
| 6 | TWAP Rivers (UNEP-DHI) | 5/5 | 3/5 | 3/5 | Unverified (portal timed out) | Unverified | **SKIP — Unreachable portal** |
| 7 | World Bank Major Basins | 4/5 | 3/5 (last updated 2019) | 3/5 | Yes (Shapefile) | Not explicit | **SKIP — API endpoint is DOWN (ECONNREFUSED). Data outdated (2019).** |
| 8 | HydroRIVERS (WWF) | 5/5 | 4/5 | 2/5 | Yes (Shapefile + GDB) | NO — no river names, no country field | **SKIP — Wrong type of data. River geometry only, not transboundary analysis.** |
| 9 | Water Action Hub | — | — | — | — | — | **SKIP — Site is DOWN** |

## Key Conclusion

**Only one source has the exact field we need (basin → countries mapping): OSU TFDD (#1).**

- TFDD's "Basin Country Units" (BCUs) are the area of a basin within a specific country — this is the direct mapping of river basin to countries
- 313 international river basins identified in the 2024 update
- Shapefile format — requires download and parsing (no API)
- GRDC (#5) supplements with basin names and GeoJSON format but lacks the country field
- All other sources are either down, duplicates, or missing the country mapping

## Data Access Challenge

Unlike the cable research (which had a JSON API), river data is primarily in **Shapefile format** — a GIS binary format that requires:
- Python libraries (`geopandas`, `fiona`, or `pyshp`) to parse
- Or conversion to GeoJSON/CSV before analysis
