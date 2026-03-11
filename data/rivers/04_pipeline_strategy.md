# Pipeline Strategy: Cross-Border Rivers

## Summary
Unlike the cable research, **we already have all the data locally**. The TFDD shapefile was downloaded and contains 316 basins across 157 countries with direct basin→country mapping. No further API calls needed.

## Tasks

### Task 1: Extract and Transform (LOCAL)
- **Source:** `data/raw/BCUMaster313_20240807.shp`
- **Method:** Python script with geopandas
- **Action:** Group by `Basin_Name`, aggregate `adm0_name` into country lists, include `Continent_`, `NumberRipa`, `Area_km2`
- **Output:** `data/06_cable_table.md` (markdown table)
- **Fallback:** If geopandas fails, use `Riparian_C` field which has pre-built country lists

### Task 2: Classify by Continent (LOCAL)
- **Source:** `Continent_` field in shapefile
- **Method:** Direct mapping: AF→Africa, AS→Asia, EU→Europe, NA→North America, SA→South America
- **No computation needed — field exists**

### Task 3: Clean Country Names (LOCAL)
- **Method:** Normalize formal names to common names:
  - "Iran (Islamic Republic of)" → "Iran"
  - "Dem People's Rep of Korea" → "North Korea"
  - "Syrian Arab Republic" → "Syria"
  - "Russian Federation" → "Russia"
  - "Turkiye" → "Turkey"
  - etc.

### Task 4: Verify (SPOT CHECK)
- **Method:** Pick 5-10 well-known rivers (Nile, Amazon, Danube, Mekong, Rhine)
- **Verify against:** UN Water, river basin organization official websites
- **Check:** Are the country lists correct and complete?

## No Gaps
The primary source covers all requirements. No supplementary sources needed.

## Verification Sources
| River | Verification Source |
|-------|-------------------|
| Nile | Nile Basin Initiative (nilebasin.org) |
| Amazon | OTCA (otca-oficial.info) |
| Danube | ICPDR (icpdr.org) |
| Mekong | Mekong River Commission (mrcmekong.org) |
| Rhine | ICPR (iksr.org) |
