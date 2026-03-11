# Data Inspection Results: Cross-Border Rivers

## Primary Source: OSU TFDD 2024 Spatial Database

### What we downloaded
- URL: `https://transboundarywaters.ceoas.oregonstate.edu/sites/transboundarywaters.ceoas.oregonstate.edu/files/2024-08/TFDDSpatialDatabase_20240807.zip`
- Size: 64.8 MB
- Contains 3 shapefiles + codebook PDF

### Shapefile 1: Basin Country Units (BCUMaster313_20240807.shp)
**This is the key file — it maps each basin to each country it's in.**

- **Records:** 818 (one row per basin-country pair)
- **Key fields:**
  - `Basin_Name` — river basin name (e.g., "Amazon", "Danube")
  - `adm0_name` — country name (e.g., "Brazil", "Germany")
  - `BCODE` — basin identifier code
  - `CCODE` — ISO3 country code (e.g., "BRA", "DEU")
  - `BCCODE` — basin-country unit code (e.g., "AMZN_BRA")
  - `Continent_` — continent code (AF, AS, EU, NA, SA)
  - `Riparian_C` — comma-separated list of ALL riparian countries for that basin
  - `NumberRipa` — number of riparian countries
  - `Area_km2` — area of this BCU in km²
  - `Pop_2022` — population in this BCU
  - Plus: dams, runoff, withdrawal, consumption, hydropolitical tension, etc.

### Shapefile 2: International River Basins (BasinMaster313_20240807.shp)
- **Records:** 313 (one row per basin)
- **Key fields:** Same as BCU but aggregated at basin level (no country breakdown)

### Data Quality
- **316 unique basins** found in BCU data (vs 313 in basin file — minor discrepancy)
- **157 unique countries** represented
- **818 basin-country pairs** — this IS our table
- Country names are full names (not ISO codes), some use formal names (e.g., "Iran (Islamic Republic of)")
- `Riparian_C` field provides a pre-built comma-separated country list per basin

### Field Mapping to Requirements

| Our Requirement | TFDD Field | Available? |
|----------------|------------|------------|
| River/basin name | `Basin_Name` | YES |
| Countries connected | `adm0_name` (per BCU row) or `Riparian_C` (comma list) | YES |
| Country code | `CCODE` (ISO3) | YES |
| Region/continent | `Continent_` | YES (AF, AS, EU, NA, SA) |
| Number of countries | `NumberRipa` | YES |
| Area | `Area_km2` | YES |
| Population | `Pop_2022` | YES |

### What's Missing
- **River type** (not a concept here — all are rivers/basins)
- **River length** (not in this dataset)
- **Flow direction / source-to-mouth** (not in this dataset)

## Conclusion
**The TFDD BCU shapefile provides EVERYTHING we need in a single file.** No supplementary sources required for the core table (basin name → countries). The data is already parsed locally.
