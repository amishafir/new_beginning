# Inspection Results: TeleGeography Submarine Cable API

## Step 0: Existing Data
No cable data exists in the repo. Starting fresh.

## Step 1: Three Problems Assessment

### Problem 1: Enumeration ✓ EXCELLENT
- `all.json` returns **690 cable IDs** (curl) / **1,312** (WebFetch — possible pagination or caching difference)
- Each cable has a stable slug ID (e.g., `2africa`, `marea`, `grace-hopper`)
- All records are consistent: `{id, name}` only in listing endpoint

### Problem 2: Placement ✓ EXCELLENT
- `landing-point-geo.json` returns **1,907 landing points** with coordinates
- **100% have coordinates** (GeoJSON Point geometry)
- Country embedded in name string: "Osterby, Denmark" — parseable but not a separate field
- `cable-geo.json` has route geometry (MultiLineString) for cable paths

### Problem 3: Relationships ✓ BUILT-IN
- Per-cable endpoint `cable/{id}.json` returns landing_points array with **explicit `country` field**
- Each cable IS a relationship: cable → connects → [country1, country2, ...]
- Average landing points per cable: 2-53 (median likely ~4-6)
- Relationship type is inherent: "this cable lands in these countries"
- **No need for spatial inference or name parsing — relationships are in the source data**

> **Verdict: This source solves all three problems. 690+ cables, 1,907 landing points with 100% coordinates, and cable→country relationships built into the per-cable response.**

## Step 2: API Inspection

### Endpoints tested

| Endpoint | Works? | Records | Fields |
|---|---|---|---|
| `/api/v3/cable/all.json` | ✓ | 690 | id, name |
| `/api/v3/cable/{id}.json` | ✓ (20/20 random test) | 1 per call | id, name, length, rfs, rfs_year, is_planned, owners, suppliers, url, notes, landing_points[] |
| `/api/v3/landing-point/landing-point-geo.json` | ✓ | 1,907 | id, name, is_tbd, coordinates |
| `/api/v3/cable/cable-geo.json` | ✓ | ~150+ features | id, name, color, coordinates |

### Per-cable fields (consistent across all 8 tested cables)

| Field | Type | Example | Nullable? |
|---|---|---|---|
| `id` | string | `"2africa"` | No |
| `name` | string | `"2Africa"` | No |
| `length` | string | `"45,000 km"` | No |
| `rfs` | string | `"2024"` or `"2018 May"` | No |
| `rfs_year` | int | `2024` | No |
| `is_planned` | bool | `false` | No |
| `owners` | string (comma-sep) | `"Google"` or `"Meta, Microsoft, Telxius"` | No |
| `suppliers` | string | `"SubCom"` | Yes (null on some) |
| `url` | string | `"https://www.2africacable.net/"` | Yes (null on some) |
| `notes` | string | (branch details, ownership notes) | Yes (null on most) |
| `landing_points` | array | see below | No |

### Landing point fields (per cable, consistent)

| Field | Type | Example | Notes |
|---|---|---|---|
| `id` | string | `"luanda-angola"` | Slug format |
| `name` | string | `"Luanda, Angola"` | City, Country format |
| `country` | string | `"Angola"` | **Explicit country field** |
| `is_tbd` | bool/null | `null` | Rarely non-null |

### Sample records

**Large cable (2Africa):** 50 landing points, 34 countries, length 45,000 km, RFS 2024
**Medium cable (AAE-1):** 20 landing points, 15 countries, length 25,000 km, RFS 2017
**Small cable (Aden-Djibouti):** 2 landing points, 2 countries, length 269 km, RFS 1994
**Planned cable (Cadmos-2):** 2 landing points, 2 countries, length 250 km, RFS 2026, is_planned=true
**Domestic cable (Bodø-Røst):** 2 landing points, 1 country (Norway), length 109 km

### Gotchas discovered
- `length` is a **string** with comma formatting and "km" suffix — needs parsing
- `owners` is a **comma-separated string**, not an array — needs splitting
- `rfs` format varies: `"1994"`, `"2018 May"`, `"2022 September"` — `rfs_year` (int) is more reliable
- `all.json` returned 690 via curl vs 1,312 via WebFetch — unclear cause. Extraction should use `all.json` and count what we get.
- Slug IDs have no hyphens for slash-names: `havfrueaec-2` not `havfrue-aec-2`
- No authentication, no rate limiting observed (tested 28 requests in ~30 seconds)
- Domestic cables (landing in only 1 country) exist — need to decide: include or filter?

## Step 2b: Overlap with Marine Regions DB

Tested 46 country names from TeleGeography against MR nation entities:
- **41/46 exact match** (89%)
- **5 need aliases** (all resolvable):
  - "France" → "Frankrijk" (already in build_relationships.py)
  - "Somalia" → "Federal Republic of Somalia" (already aliased)
  - "Comoros" → "Comores"
  - "Congo, Dem. Rep." → "Democratic Republic of the Congo"
  - "Congo, Rep." → "Republic of the Congo"

**Integration cost: trivial.** ~5 new aliases needed. No language/suffix issues. Country names are standard English.

With 186 unique countries across all landing points, we can expect ~10-15 aliases total (including the 5 already known).

## Step 3: Capability Matrix

| Source | Entities | Coordinates | Relationships | Notes |
|---|---|---|---|---|
| TeleGeography `all.json` | ✓ 690 cable IDs | ✗ | ✗ | Enumeration only |
| TeleGeography `{id}.json` | ✓ full detail per cable | ✗ | ✓ landing_points with country | **Primary extraction endpoint** |
| TeleGeography `landing-point-geo.json` | ✓ 1,907 points | ✓ 100% have coordinates | ✗ | Join with per-cable data for full picture |
| TeleGeography `cable-geo.json` | ✓ route geometry | ✓ MultiLineString routes | ✗ | Nice to have, not essential |
| Marine Regions DB (existing) | ✓ 37.4K entities incl. nations | ✓ | ✓ 21K relationships | **Merge target** for cable→country edges |

### Gaps: NONE for submarine cables
This source provides everything needed:
- Cable enumeration (all.json)
- Cable details with countries (per-cable endpoint)
- Landing point coordinates (landing-point-geo.json)
- Cable route geometry (cable-geo.json)

### Known limitation: No terrestrial cables
TeleGeography is submarine-only. Terrestrial cables (TEA, EPEG, JADI, WorldLink) are not included.

## Step 4: Extraction Strategy

### Recommended approach
1. Fetch `all.json` → get all cable IDs (690+)
2. For each cable ID, fetch `{id}.json` → get full detail including landing_points with country
3. Fetch `landing-point-geo.json` once → get all landing point coordinates
4. Join landing points by ID to add coordinates
5. Parse `length` string → numeric, parse `owners` string → list
6. Store in SQLite: `cables` table + `cable_landing_points` table + `cable_countries` relationship table

### Estimated API calls: ~691 (1 for all.json + 690 per-cable)
At 0.5s delay per call: ~6 minutes total extraction time.

### Integration with Marine Regions DB
Two options:
- **Option A**: Separate SQLite database for cables (simpler, standalone)
- **Option B**: Merge into global_map.db with cable entities + `connects` relationships to nations

Recommend **Option B** — cables become entities in the graph, connected to nations via landing points. This answers questions like "Which cables connect France to the US?" or "How many submarine cables does Kenya have?"
