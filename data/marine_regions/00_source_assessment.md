# Marine Regions Source Assessment (Retrospective)

**Source**: Flanders Marine Institute (VLIZ) — Marine Regions
**URL**: https://marineregions.org/
**Date assessed**: 2026-03-14
**Purpose**: Retrospective survey — what did we miss by going straight to the REST API in Session 3?

---

## 1. Data Infrastructure Map

### What we used (Sessions 3-5)
| Method | What we extracted | Limitations |
|--------|------------------|-------------|
| REST API (`/rest/getGazetteerRecordsByType`) | 37,149 entities | Type names not IDs, undocumented |
| REST API (`/rest/getGazetteerRelationsByMRGID`) | 407 parent hierarchy links | Returns ~1 per entity, some wrong |
| REST API (`/rest/getGazetteerNamesByMRGID`) | Not used until now | Could have built alias index |

### What we DIDN'T use

| Method | URL | Format | What it offers |
|--------|-----|--------|---------------|
| **WFS (Web Feature Service)** | `https://geo.vliz.be/geoserver/MarineRegions/wfs` | GeoJSON, CSV, Shapefile | **55 layers** with polygon geometries, attribute queries, spatial filters |
| **GeoPackage/Shapefile downloads** | `https://marineregions.org/downloads.php` | GeoPackage, SHP | Pre-built boundary datasets with full polygons |
| **WMS (Web Map Service)** | `https://geo.vliz.be/geoserver/MarineRegions/wms` | Map images | Visualization only, low data value |
| **CSW (Catalogue Service)** | `http://geonetwork.vliz.be/geonetwork/srv/eng/csw` | XML | Metadata discovery |

---

## 2. Critical Datasets We Missed

### 2a. EEZ Boundaries (`MarineRegions:eez_boundaries`) — **THE BIG MISS**

**2,349 maritime boundary lines**, each with:
- `mrgid_sov1`, `sovereign1` — nation on one side
- `mrgid_sov2`, `sovereign2` — nation on the other side
- `line_type` — Treaty, Median, Unsettled median line, etc.
- `length_km` — boundary length
- `source1`, `url1`, `doc_date` — legal provenance (treaty documents!)

**This is authoritative maritime adjacency with legal sourcing.** Each line is a shared maritime border between two nations, with the specific treaty or legal basis documented.

**What we did instead**: Computed `adjacent_to` from bounding box overlap in Session 3 (482 relationships), then manually excluded landlocked nations and overly broad regions. Got false positives (Bolivia "adjacent to" seas).

**What this would have given us**: ~2,349 precise maritime boundary relationships with MRGIDs already matching our DB, zero false positives, legal provenance per relationship.

**Impact**: Would have replaced the entire spatial inference step and the landlocked-nation exclusion hack. Clean, authoritative, pre-computed.

### 2b. EEZ-IHO Intersection (`MarineRegions:eez_iho`)

**572 pre-computed features**, each mapping:
- `iho_mrgid`, `iho_sea` — which IHO Sea
- `mrgid_sov1`, `sovereign1`, `iso_ter1` — which nation
- `area_km2` — intersection area

**This is exactly the "which country borders which sea" relationship we computed from bounding boxes.**

**What we did instead**: Point-in-bbox computation (Session 3b) — 17,210 `located_in` relationships. Works but is crude (smallest-bbox heuristic, no polygon precision).

**What this would have given us**: 572 authoritative nation↔sea relationships with area measurements, MRGIDs matching our DB, ISO codes included.

### 2c. Alternate Names API (`getGazetteerNamesByMRGID`)

Returns alternate names per entity. For België (MRGID 14): `["Belgium", "Bélgica"]`.

**What we did instead**: Built alias dictionaries manually over 5 sessions, adding names one by one as matching failures appeared. Five rounds of additions for Session 3 alone.

**What this would have given us**: Automated English↔Dutch name resolution for all nations. One API call per entity × 196 nations = 196 calls = ~3 minutes. Would have eliminated the name-matching problem from Session 3 onward.

### 2d. Global Oceans and Seas (`MarineRegions:goas`)

10 features — a clean, authoritative list of the world's major oceans and seas with polygons.

Useful as a reference hierarchy, though we already have the IHO sea areas via the API.

### 2e. WFS Layers We Never Explored

| Layer | Features | What it provides |
|-------|----------|-----------------|
| `eez` | 285 | Full EEZ polygons with sovereign nation MRGIDs + ISO codes |
| `eez_12nm` | ~280 | Territorial sea polygons |
| `eez_24nm` | ~280 | Contiguous zone polygons |
| `eez_internal_waters` | ~280 | Internal waters polygons |
| `eez_land` | 328 | Union of EEZ + land area per nation, with area_km2 |
| `iho` | 101 | IHO Sea Area polygons with area |
| `lme` | ~66 | Large Marine Ecosystems polygons |
| `fao` | ~20 | FAO Fishing Areas |
| `eca_reg13_nox` / `eca_reg14_sox_pm` | ~10 | Emission Control Areas |
| `high_seas` | ~10 | International waters polygons |
| `ecs` | ~80 | Extended Continental Shelf claims |
| `gazetteer_polygon` | ~39,931 | All gazetteer entries with polygons |
| `gazetteer_line` | ? | Gazetteer line features (rivers, coasts) |

---

## 3. Schema Mapping

### 3a: Four Problems Assessment

| Dataset | Enumeration | Placement | Relationships | Properties |
|---------|------------|-----------|---------------|------------|
| **EEZ Boundaries** | 2,349 boundary lines | Line geometries | ✓ Nation↔Nation maritime borders | ✓ Type (treaty/median/unsettled), length_km, legal source |
| **EEZ-IHO Intersection** | 572 intersections | Point + polygon | ✓ Nation↔Sea adjacency | ✓ area_km2 |
| **EEZ polygons** | 285 EEZs | Full polygons | ✓ EEZ→Nation (sovereign MRGID) | ✓ area_km2 |
| **EEZ-Land union** | 328 zones | Polygons | ✓ Land+Sea area per nation | ✓ area_km2 |
| **Alternate Names** | Per-entity | N/A | N/A | N/A — infrastructure, not data |
| **Gazetteer polygons** | 39,931 features | Full polygons | Via containment | ✓ area |

### 3b: What each dataset would add to our DB

**EEZ Boundaries → `maritime_border` relationship**
- 2,349 nation-pair edges with legal provenance
- Join: direct MRGID match (already in our DB)
- Properties: line_type, length_km, treaty source, date
- **Replaces**: our 482 spatial-inference `adjacent_to` relationships + landlocked exclusion hack
- **Graph value: HIGH**

**EEZ-IHO Intersection → improved `adjacent_to(nation, sea)` with area**
- 572 authoritative nation↔sea edges
- Join: direct MRGID match
- Properties: area_km2 (weighted adjacency!)
- **Replaces/enriches**: subset of our 17,210 located_in relationships
- **Graph value: HIGH**

**EEZ polygons → `area_km2` attribute on EEZ entities + polygon spatial queries**
- Would enable precise point-in-polygon containment (instead of point-in-bbox)
- **Graph value: MEDIUM** (improves existing relationships, doesn't create new ones)

**Alternate Names → infrastructure for name matching**
- Eliminates the multilingual matching problem permanently
- **Graph value: N/A** (infrastructure, not data — but saves hours per session)

---

## 4. Value Ranking

| # | Dataset | Integration Ease | Uniqueness | Graph Value | Priority |
|---|---------|-----------------|-----------|-------------|----------|
| 1 | **EEZ Boundaries** | Trivial (WFS CSV, MRGIDs match) | Authoritative — legal treaty sources | **HIGH** — 2,349 maritime border edges | **HIGH** |
| 2 | **EEZ-IHO Intersection** | Trivial (WFS CSV, MRGIDs match) | Pre-computed by MR itself | **HIGH** — 572 nation↔sea edges with area | **HIGH** |
| 3 | **Alternate Names API** | Easy (196 API calls) | Only available from MR | Infrastructure — eliminates name matching | **HIGH** |
| 4 | **EEZ polygons** | Easy (WFS/download) | Standard | **MEDIUM** — enables polygon queries | **MEDIUM** |
| 5 | **Gazetteer polygons** | Medium (39K features, large) | Unique compilation | **MEDIUM** — precise containment | **MEDIUM** |
| 6 | **EEZ-Land union** | Trivial | Derived | **LOW** — area attribute | **LOW** |

---

## 5. What This Tells Us About Session 3

### The cost of not surveying

| What we did (Session 3) | What was available | Time cost |
|--------------------------|-------------------|-----------|
| Computed `adjacent_to` from bounding boxes (482 rels, false positives, landlocked exclusion) | EEZ Boundaries: 2,349 precise maritime borders with legal provenance | ~2 hours vs ~10 minutes |
| Computed `located_in` from point-in-bbox (17,210 rels, crude heuristic) | EEZ-IHO Intersection: 572 authoritative nation↔sea links with area | ~1 hour vs ~5 minutes |
| Built alias dictionaries over 5 rounds of manual additions | Alternate Names API: automated English aliases for all entities | ~3 hours cumulative vs ~5 minutes |
| Used `getGazetteerRelationsByMRGID` (407 sparse, some wrong) | WFS layers with full relational data and MRGIDs | Entire Session 3b was a workaround |

**Total estimated savings: 6+ hours of work across Sessions 3-6.**

The WFS service was available the entire time. The EEZ Boundaries dataset has MRGIDs that match our DB directly — no name matching, no spatial heuristics, no false positive filtering. And it comes with legal provenance (which treaty established each boundary) — data quality we couldn't dream of from bounding box overlap.

### Root cause
We went straight to the REST API because that's what we found first. We never asked "what else does this organization provide?" The REST API is designed for single-record lookups in a web interface — it's the worst way to build a bulk database. The WFS and downloads are designed for exactly what we were trying to do.

---

## 6. Gaps (what MR still doesn't cover)

- **No strait connectivity**: Which seas does a strait connect? Not in any MR dataset.
- **No land borders**: EEZ Boundaries only covers maritime borders. Land borders still need an external source.
- **No river-sea connections**: Which rivers empty into which seas? Not explicitly in MR.
- **No shipping/trade data**: MR is geographic, not economic. Need UNCTAD for that layer.
- **Relationship API remains useless**: Only returns ~1 parent per entity. Use WFS instead.

---

## 7. Recommended Next Steps

1. **Extract EEZ Boundaries** via WFS CSV — 2,349 maritime border relationships with legal provenance. Direct MRGID join, zero name matching needed. Could be done in 15 minutes.
2. **Extract EEZ-IHO Intersection** — 572 nation↔sea relationships with area. Same ease.
3. **Build alternate names index** via `getGazetteerNamesByMRGID` for all 196 nations — permanent fix for the multilingual matching problem.
4. **Consider**: replacing our bounding-box `located_in` relationships with polygon-based containment from `gazetteer_polygon` WFS layer (39K features — larger effort).
