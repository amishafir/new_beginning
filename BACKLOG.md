# Data Source Backlog

**Last updated**: 2026-03-14 (Session 7)
**DB status**: 40,002 entities | 28,345 relationships | 12 relationship types | 196 nations with ISO codes

This file tracks data sources and tasks queued for future extraction. Organized by readiness — how much prep remains before extraction can begin.

---

## Ready to Extract (surveyed, assessed, join method confirmed)

These need only a `/data-inspector` probe + extraction script.

### UNCTAD — Bilateral Liner Shipping Connectivity Index (LSBCI)
- **Source**: UNCTADstat Data Centre
- **What**: Country-to-country shipping connectivity scores
- **Value**: ~19K directed weighted edges between nations (HIGH graph value)
- **Relationship type**: `shipping_connected_to(nation, nation, score=X)`
- **Join method**: ISO country codes → MRGID (infrastructure built in Session 7)
- **Format**: CSV bulk download from Data Centre
- **Queries enabled**: "Which country pairs have the strongest shipping link?" / "Shipping connectivity vs submarine cable count between same pair"
- **Assessment**: `data/unctad/00_source_assessment.md`
- **Status**: Needs data-inspector probe to confirm CSV structure and bilateral format

### UNCTAD — Bilateral Investment Treaties (BITs)
- **Source**: https://investmentpolicy.unctad.org/international-investment-agreements
- **What**: 2,864 treaties between country pairs, with status, dates, treaty text
- **Value**: ~2,800 bilateral treaty edges (HIGH graph value). UNCTAD is the sole authority.
- **Relationship type**: `has_treaty_with(nation, nation, type=BIT, status=in_force)`
- **Join method**: Country names (English) → MRGID. May need alias matching.
- **Format**: Web portal — no API. Likely needs scraping or manual export.
- **Queries enabled**: "Which country pairs have both a shared border AND an investment treaty?" / "How many unsettled maritime borders have no investment treaty?"
- **Assessment**: `data/unctad/00_source_assessment.md`
- **Status**: Needs inspector to test scraping feasibility / export options

### UNCTAD — Merchandise Trade Matrix
- **Source**: UNCTADstat Data Centre (US.TradeMatrix)
- **What**: Bilateral trade flows between ~200 countries, by product category, annual
- **Value**: Massive bilateral edge set (HIGH graph value). Also available via UN Comtrade.
- **Relationship type**: `exports_to(nation, nation, value=USD, product=X)`
- **Join method**: ISO codes → MRGID
- **Format**: CSV bulk download
- **Queries enabled**: "Total trade volume between Mediterranean nations" / "Do river-sharing countries trade more?"
- **Assessment**: `data/unctad/00_source_assessment.md`
- **Status**: Needs inspector. Large dataset — design extraction carefully (aggregate vs product-level).

### UNCTAD — Bilateral FDI Flows & Stocks
- **Source**: UNCTADstat Data Centre
- **What**: Country-to-country FDI, 206 economies, 40+ years
- **Value**: Directed weighted investment edges (MEDIUM-HIGH graph value)
- **Relationship type**: `invests_in(nation, nation, value=USD)`
- **Join method**: ISO codes → MRGID
- **Format**: CSV bulk download
- **Queries enabled**: "Which country receives the most investment from its maritime neighbors?"
- **Assessment**: `data/unctad/00_source_assessment.md`
- **Status**: Needs inspector probe

---

## Ready to Enrich (attribute augmentation on existing entities)

### UNCTAD — Liner Shipping Connectivity Index (LSCI)
- **Source**: UNCTADstat (US.LSCI)
- **What**: Country-level shipping connectivity score (0-100+), monthly/quarterly
- **Value**: LOW graph value (node attribute), but easy win and enables cross-queries
- **Target**: `shipping_connectivity` attribute on Nation entities
- **Join method**: ISO codes → MRGID
- **Format**: CSV
- **Status**: Ready — easiest UNCTAD extraction

### UNCTAD — Merchant Fleet by Flag
- **Source**: UNCTADstat
- **What**: Fleet size by country and ship type
- **Value**: LOW graph value (node attribute)
- **Target**: `fleet_size_dwt` attribute on Nation entities
- **Format**: CSV
- **Status**: Ready

### UNCTAD — Container Port Throughput
- **Source**: UNCTADstat
- **What**: Container traffic by country (TEU)
- **Value**: LOW graph value (node attribute)
- **Target**: `container_throughput_teu` attribute on Nation entities
- **Format**: CSV
- **Status**: Ready

---

## Needs Sourcing / Inspection

### UNCTAD — Port LSCI (PLSCI)
- **What**: Individual port connectivity scores (~1,000 ports)
- **Value**: MEDIUM — could add Port entities to DB
- **Blocker**: PLSCI has no port coordinates. Need a separate port database (World Port Index? GeoNames?) for placement.
- **Status**: Needs source-scout for port coordinate data, then inspector for PLSCI

### UNCTAD — TRAINS / Non-Tariff Measures
- **Source**: WITS API (https://wits.worldbank.org/API/) serves UNCTAD TRAINS data
- **What**: Countries × products × trade measures
- **Value**: MEDIUM graph value (trade policy edges)
- **Blocker**: Complex multi-dimensional data. WITS API is JSON/XML.
- **Status**: Low priority — complex extraction for moderate graph value

### Marine Regions — Gazetteer Polygons (WFS)
- **Source**: `MarineRegions:gazetteer_polygon` WFS layer (39,931 features)
- **What**: Full polygon geometries for all gazetteer entries
- **Value**: MEDIUM — enables precise point-in-polygon containment (replaces point-in-bbox heuristic for `located_in`)
- **Blocker**: Large dataset. Would need to re-compute all `located_in` relationships.
- **Status**: Available via WFS. Worth doing but large effort.

### Marine Regions — Additional WFS Layers
- **What**: LME (Large Marine Ecosystems), FAO Fishing Areas, Emission Control Areas, Extended Continental Shelves
- **Value**: LOW-MEDIUM — adds specialized geographic zones
- **Status**: Available. Low priority unless specific queries need them.

---

## Known Gaps

### Strait Connectivity — HIGH value, no new source needed
- **Gap**: 155 straits in DB, zero `connects(strait, sea)` relationships. Strait of Gibraltar doesn't know it connects Mediterranean to Atlantic.
- **Mitigation**: Hybrid — curate top ~30 straits manually (stable geographic knowledge), compute remaining ~125 via spatial overlap (strait bbox vs IHO sea polygons from WFS).
- **Value**: Unlocks routing queries ("What straits does a ship pass through from Japan to Germany?")
- **Status**: Ready to compute. Data already in DB + IHO polygons from WFS.

### River-Sea Connections — HIGH value, no new source needed
- **Gap**: 342 rivers have `flows_through` countries, only 4 have `flows_into` a sea.
- **Mitigation**: Spatial join — for each river, find which IHO Sea Area contains its coordinate. ~342 lookups against IHO polygons (available via MR WFS).
- **Complication**: MR river coordinates aren't always at the mouth. May need manual verification for major rivers.
- **Value**: Connects river and sea graph layers ("Which rivers flow into the Mediterranean?")
- **Status**: Ready to compute. Need IHO polygons from WFS.

### Land Border Properties — LOW value, partially filled
- **Gap**: 644 `borders` relationships already have `km` (length). Missing: border type, legal provenance.
- **Mitigation**: CIA World Factbook or Natural Earth for classification. But current data is sufficient for most queries.
- **Status**: Low priority. Skip unless specific query needs it.

### Terrestrial Communication Cables — MEDIUM value, no source exists
- **Gap**: No free, structured, global source. 690 submarine cables in DB, zero terrestrial.
- **Candidates explored**: AfTerFibre (Africa only, 2020), UNESCAP (PDFs), InfraNav (commercial).
- **Mitigation**: Accept gap, or manually curate top ~20 routes (TEA, EPEG, JADI, WorldLink) from operator press releases.
- **Status**: Documented as explicit gap. No scalable solution.

---

## Not Yet Surveyed (candidate organizations)

These are major international data organizations that likely have structured data relevant to our DB. Each would need a `/source-surveyor` run.

| Organization | URL | Expected domain | Why interesting |
|-------------|-----|----------------|-----------------|
| **World Bank Open Data** | data.worldbank.org | Economy, development, infrastructure | Massive bilateral + country-level data, well-structured API |
| **UN Comtrade** | comtradeplus.un.org | Trade | Most detailed bilateral trade data (HS 6-digit), API available |
| **FAO** | fao.org/faostat | Agriculture, fisheries, land use | Country-level + bilateral agricultural trade |
| **IMO** | imo.org | Maritime regulation | Ship registration, port state control, maritime safety |
| **ITU** | itu.int | Telecommunications | Telecom infrastructure, bandwidth, connectivity |
| **ICAO** | icao.int | Aviation | Air routes, airports — would add aviation layer |
| **Natural Earth** | naturalearthdata.com | Geography | Clean boundary polygons, populated places, physical features |
| **OpenStreetMap / Overpass** | overpass-turbo.eu | Everything | Ports, airports, border crossings — entity-level with coordinates |
| **GeoNames** | geonames.org | Geographic names | 12M+ place names with coordinates — could fill entity gaps |

---

## Priority Order (when scaling becomes possible)

1. **LSBCI** — highest graph value, easiest UNCTAD extraction, ISO join ready
2. **BITs** — unique authority, high graph value, needs scraping solution
3. **Trade Matrix** — massive but needs design decisions (aggregate vs product-level)
4. **Strait connectivity** — small scope, high value, no new source needed
5. **River-sea connections** — computational, no new source needed
6. **LSCI + fleet + throughput** — easy wins, node attributes
7. **Bilateral FDI** — similar to trade matrix
8. **World Bank / UN Comtrade surveys** — expand source landscape
9. **Gazetteer polygons** — precision upgrade for existing relationships
10. **Port LSCI + port coordinates** — new entity type, needs two sources
