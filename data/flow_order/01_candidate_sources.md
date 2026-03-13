# Source Scout: River Flow Order & Upstream/Downstream Country Ordering

## Research Question
For each transboundary river basin, determine the full flow order of countries from source (upper riparian) to mouth (lower riparian).

## Existing Data in Repo
- **TFDD BCU shapefile** (Session 2): 313 basins, 818 basin-country units with polygon geometry. **No flow order attribute** — confirmed by codebook ("no preference or priority implied by the ordering of the river names"). Has `Continent_` field (AF, AS, EU, NA, SA).
- **Marine Regions DB**: 342 rivers with `flows_through` relationships to countries. Only 51 (from old CSV) have `Rank` attribute — but quality is suspect (Drava has Hungary×3, Senegal ordering likely wrong).
- **TFDD river entities in DB**: 256 entities with **0 coordinates**.

## Candidate Sources

| # | Source | URL | Tier | Type | Format | Scope | Maintainer | Reachable | Relevance |
|---|--------|-----|------|------|--------|-------|------------|-----------|-----------|
| 1 | **HydroRIVERS** | hydrosheds.org/products/hydrorivers | Primary | file_download | Shapefile/GDB | 8.5M river reaches globally | WWF / McGill Univ | ✅ | **HIGH** — has `NEXT_DOWN`, `MAIN_RIV`, `DIST_DN_KM` fields for full topology |
| 2 | **HydroBASINS** | hydrosheds.org/products/hydrobasins | Primary | file_download | Shapefile/GDB | 12 levels of nested sub-basins globally | WWF / McGill Univ | ✅ | MEDIUM — Pfafstetter codes encode upstream/downstream, `NEXT_DOWN` field |
| 3 | **RiverATLAS** (HydroATLAS) | hydrosheds.org/hydroatlas | Primary | file_download | Shapefile/GDB | 8.5M reaches + 281 attributes | WWF / McGill Univ | ✅ | HIGH — HydroRIVERS fields + 56 hydro-environmental variables including political boundaries |
| 4 | **GRIT** (Global River Topology) | zenodo.org/records/11219313 | Primary | file_download | GeoPackage | Global river network with distributaries | Lin et al. (academic) | ✅ | MEDIUM — upstream/downstream IDs, Strahler order, 30m resolution. 27.6 GB — very large |
| 5 | **MERIT Hydro** | hydro.iis.u-tokyo.ac.jp/~yamadai/MERIT_Hydro/ | Primary | file_download | GeoTIFF raster | Global flow direction at 90m | Univ of Tokyo | ✅ | LOW for our use — raster flow direction grid, not vector. Would need heavy GIS processing |
| 6 | **TWAP River Basins** | twap-rivers.org | Primary | interactive/download | Shapefile + portal | 286 transboundary basins | UNEP-DHI / OSU | ⚠️ timeout | LOW — uses TFDD/HydroBASINS as base. Indicators focus on risk, not flow order |
| 7 | **TFDD Spatial Database** | transboundarywaters.ceoas.oregonstate.edu/spatial-datasets | Primary | file_download | Shapefile | 313 transboundary basins | Oregon State Univ | ✅ | Already in repo — **no flow order data** (confirmed) |

## Analysis

### Why HydroRIVERS is the best fit

HydroRIVERS provides exactly what we need to compute country flow order:

**Key fields:**
| Field | Description | Why it matters |
|-------|-------------|----------------|
| `HYRIV_ID` | Unique reach identifier | Link reaches together |
| `NEXT_DOWN` | ID of next downstream reach | **Trace flow path from source to mouth** |
| `MAIN_RIV` | ID of the most downstream reach in the basin | **Group all reaches of the same river** |
| `DIST_DN_KM` | Distance to ocean outlet (km) | **Direct measure of upstream/downstream position** |
| `DIST_UP_KM` | Distance from headwater (km) | Complementary to DIST_DN |
| `ORD_STRA` | Strahler stream order | Identify main stem vs tributaries |
| `UPLAND_SKM` | Upstream catchment area (km²) | Identify major rivers |
| `ENDORHEIC` | Whether basin is endorheic | Handle rivers that don't reach the sea |
| `HYBAS_L12` | Link to HydroBASINS level 12 | Cross-reference with sub-basin data |
| Geometry | River reach line segments | **Spatial intersection with country polygons** |

**The computation approach:**
1. Download HydroRIVERS (544 MB shapefile, or regional ~100 MB each)
2. For each TFDD transboundary basin, find the matching HydroRIVERS reaches (spatial intersection of TFDD basin polygon with HydroRIVERS lines)
3. For each reach, the `DIST_DN_KM` value tells us exactly how far upstream it is
4. Intersect reaches with country boundaries → each country gets a range of `DIST_DN_KM` values
5. The country with the highest `DIST_DN_KM` = source country (upper riparian, Rank 0)
6. The country with the lowest `DIST_DN_KM` = mouth country (highest Rank)

**Why not the others:**
- **HydroBASINS**: Pfafstetter codes enable upstream/downstream navigation, but at sub-basin level — would need extra work to aggregate to country level. Better as a supplement.
- **RiverATLAS**: Same river reaches as HydroRIVERS but with 281 extra attributes we don't need. Much larger download for no benefit on this specific task. Could use later for enrichment.
- **GRIT**: 27.6 GB, non-commercial license, overkill for our need.
- **MERIT Hydro**: Raster — wrong format for vector spatial analysis.
- **TWAP**: Doesn't add flow order data beyond what TFDD already provides.

### Source authority
HydroSHEDS (including HydroRIVERS) is:
- Developed by **WWF** in partnership with **McGill University** (Global HydroLAB)
- Based on NASA SRTM elevation data (v1) and DLR TanDEM-X (v2, releasing 2025)
- Cited in **10,000+ scientific publications**
- Used by TFDD itself (the TWAP component uses HydroBASINS as its base)
- **Free for scientific, educational, and commercial use**

### File sizes
| Download | Size |
|----------|------|
| HydroRIVERS Global (shapefile) | 544 MB |
| HydroRIVERS Asia only | 91 MB |
| HydroRIVERS Europe+Middle East | 68 MB |
| HydroRIVERS Africa | 108 MB |

### Download URL pattern
`https://data.hydrosheds.org/file/HydroRIVERS/HydroRIVERS_v10_[region]_shp.zip`

Regions: `af` (Africa), `ar` (Arctic), `as` (Asia), `au` (Australasia), `eu` (Europe/Middle East), `gr` (Greenland), `na` (North/Central America), `sa` (South America), `si` (Siberia)

## Recommendation
**Proceed with HydroRIVERS** as the sole new source. It's from the same ecosystem as TFDD (HydroSHEDS → HydroBASINS → TFDD), primary authority, free license, manageable file size, and the `DIST_DN_KM` + `NEXT_DOWN` fields give us exactly the flow topology needed to compute country ordering.

Next step: `/source-validator` on HydroRIVERS, then `/data-inspector` to test the three problems against our specific use case.
