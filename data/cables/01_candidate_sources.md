# Candidate Sources: Cross-Border Communication Cables

## Source Matrix

| Source Name | URL | Tier | Type | Format | Scope | Maintainer | Reachable |
|---|---|---|---|---|---|---|---|
| **TeleGeography Submarine Cable Map API** | submarinecablemap.com/api/v3/ | Primary | api | json_api | Global submarine cables (1,261 cables, 1,076 landing points) | TeleGeography (industry research firm, est. 1999) | ✓ Yes |
| **TeleGeography GitHub Crawl** | github.com/lintaojlu/submarine_cable_information | Secondary | file_download | geojson | Crawled TeleGeography data (cable routes + landing points) | Community (lintaojlu) | ✓ Yes |
| **ArcGIS SubmarineCables FeatureServer** | services.arcgis.com/.../SubmarineCables/FeatureServer | Secondary | api | json_api | Global submarine cables + landing cities | Unknown (sources from TeleGeography) | ✓ Yes |
| **AfTerFibre** | afterfibre.opentelecomdata.org | Primary | file_download | geojson, csv, shp, kml | Terrestrial fiber in **Africa only** | Network Startup Resource Center (NSRC) | ✓ Yes (redirect) |
| **UNESCAP Terrestrial Fibre Reports** | unescap.org/resources/ | Primary | report | pdf | Terrestrial fiber in **Asia-Pacific only** | UN ESCAP | ✓ Yes |
| **InfraNav** | infranav.com/data | Primary | database | commercial | Global terrestrial + submarine (140 countries, 4M+ fiber km) | InfraNav | ✓ Yes (paid license) |
| **ITU Infrastructure Connectivity Map** | bbmaps.itu.int/bbmaps/ | Primary | interactive_map | interactive | Global telecom infrastructure | ITU | ✓ Yes (visualization only) |
| **ICPC (Int'l Cable Protection Committee)** | iscpc.org | Primary | report | html/pdf | Cable protection data, links to TeleGeography for cable data | ICPC | ✓ Yes (no structured download) |
| **TeleGeography Licensed Dataset** | www2.telegeography.com/license-geocoded-map-data | Primary | api | json_api (S3) | Full geocoded dataset with all fields | TeleGeography | ✓ Yes (paid annual license) |

## Source Analysis

### Submarine cables: TeleGeography is the single authoritative source

Every other source (ArcGIS, GitHub crawl, ICPC, ITU map) ultimately sources from TeleGeography. There is no independent alternative for structured submarine cable data.

**TeleGeography API (free)** — Three endpoints tested:

| Endpoint | Records | Fields | Usefulness |
|---|---|---|---|
| `/api/v3/cable/all.json` | 1,261 cables | id, name **only** | Enumeration only — no details |
| `/api/v3/cable/{id}.json` | 1 cable per call | id, name, length, rfs, rfs_year, is_planned, owners, suppliers, url, notes, **landing_points[]** (id, name, **country**) | **This is the gold mine** — full detail per cable |
| `/api/v3/landing-point/landing-point-geo.json` | 1,076 points | id, name (includes country in string), is_tbd, coordinates | Placement data — country embedded in name, not a separate field |
| `/api/v3/cable/cable-geo.json` | ~150+ features | id, name, color, coordinates | Route geometry only — no metadata |

**Strategy**: Fetch `all.json` for 1,261 cable IDs → fetch each `{id}.json` for full details including landing points with explicit country field.

### Terrestrial cables: No single structured source exists

| Region | Source | Status |
|---|---|---|
| Africa | AfTerFibre (NSRC) | Open data, GeoJSON/CSV/SHP. Africa only. |
| Asia-Pacific | UNESCAP reports | PDF reports, not structured data. |
| Europe | No open source found | TeleGeography licensed data or InfraNav (paid). |
| Global | InfraNav | Commercial license required. 4M+ fiber km. |

Terrestrial cables lack the equivalent of TeleGeography's free API. The best free option is AfTerFibre for Africa.

## Recommendation

1. **Start with TeleGeography API** — 1,261 submarine cables with per-cable detail (landing points, countries, owners, length, RFS). Free, structured, complete.
2. **Probe AfTerFibre** for African terrestrial cables — inspect actual data fields before committing.
3. **Skip terrestrial cables globally** for now — no free structured source covers them. Flag as a known gap.

## Three-Problem Assessment (Submarine Cables via TeleGeography)

| Problem | Status | Evidence |
|---|---|---|
| **Enumeration** | ✓ Excellent | 1,261 cables from `all.json` |
| **Placement** | ✓ Good | Landing point coordinates from `landing-point-geo.json`, cable route geometry from `cable-geo.json` |
| **Relationships** | ✓ Built-in | Each cable's `{id}.json` has `landing_points[]` with explicit `country` field — cable→country relationships are free |

This is the rare source that solves all three problems. Unlike Marine Regions (where relationships required 4 separate strategies), TeleGeography gives us cable→landing_point→country in a single API call per cable.
