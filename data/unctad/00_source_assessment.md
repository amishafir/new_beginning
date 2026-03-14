# UNCTAD Source Assessment

**Source**: United Nations Conference on Trade and Development (UNCTAD)
**URL**: https://unctad.org/
**Date assessed**: 2026-03-14
**Purpose**: Map all data offerings, assess integration potential with `global_map.db`

---

## 1. Data Infrastructure Map

### Primary Platform: UNCTADstat Data Hub
- **URL**: https://unctadstat.unctad.org/
- **Format**: JavaScript-rendered web app with CSV bulk download + API (details unclear)
- **Access**: Free, no registration required
- **Scope**: 150+ indicators covering trade, investment, maritime, economy, digital
- **Limitation**: Data Centre is fully JS-rendered — WebFetch cannot see dataset contents. Must use browser or find API endpoints.

### Programmatic Access Routes

| Method | URL | Format | UNCTAD Data Available |
|--------|-----|--------|----------------------|
| UNCTADstat bulk CSV | Via Data Centre UI | CSV | All UNCTAD indicators |
| UNdata SDMX API | `http://data.un.org/ws/rest/` | JSON, XML, CSV | Subset of UNCTAD indicators |
| World Bank WITS API | `https://wits.worldbank.org/API/` | JSON, XML | UNCTAD TRAINS (tariffs/NTMs) |
| TRAINS API | `https://api-trains2.unctad.org/` | Bulk files (PDF/CSV) | Non-tariff measures |

### Specialized Databases (separate portals)

| Database | URL | Domain |
|----------|-----|--------|
| Investment Policy Hub | https://investmentpolicy.unctad.org/ | BITs, TIPs, dispute settlement, investment laws |
| TRAINS Online | https://trainsonline.unctad.org/ | Non-tariff measures |
| GSP Utilization | https://gsp.unctad.org/utilization | Trade preference utilization rates |
| Global Cyberlaw Tracker | unctad.org (e-commerce legislation) | Digital economy regulation |
| Sustainable Stock Exchanges | https://sseinitiative.org/ | Exchange sustainability activities |
| Sustainable Freight Transport | https://sft-framework.unctad.org/ | Freight transport sustainability |

### Classification Systems (critical for DB joins)

| Classification | System | Join to our DB |
|---------------|--------|---------------|
| Countries | **ISO 3166-1** (alpha-2, alpha-3) + **UN M49** | Trivial — but our DB lacks ISO codes (has MRGIDs). Need a one-time ISO→MRGID mapping table. |
| Country groups | UN M49 regions, development status codes | Maps to continent hierarchy |
| Products | HS (6-digit, editions 1992-2022), SITC Rev.3 | New dimension — products are not in our DB |
| Services | BPM6 | New dimension |
| Economic activities | ISIC Rev.3.1, ISIC Rev.4 | New dimension |

---

## 2. Dataset Catalog

### Tier 1: Bilateral/Relational Data (creates edges in our graph)

| Dataset | Domain | Entity Types | Granularity | Temporal | Format |
|---------|--------|-------------|-------------|----------|--------|
| **Bilateral Liner Shipping Connectivity Index (LSBCI)** | Maritime | Country pairs | Country-to-country | Quarterly | CSV via Data Centre |
| **Merchandise Trade Matrix** | Trade | Country pairs × products | Bilateral, annual | Annual time series | CSV via Data Centre |
| **Bilateral FDI Flows & Stocks** | Investment | Country pairs | Bilateral, annual | 40+ years, 206 economies | CSV via Data Centre |
| **Bilateral Investment Treaties (BITs)** | Legal/Investment | Country pairs | Treaty-level | 1959–present | Web portal (2,864 treaties) |
| **Treaties with Investment Provisions (TIPs)** | Legal/Investment | Country pairs + multilateral | Treaty-level | Ongoing | Web portal (518 treaties) |
| **Non-Tariff Measures (TRAINS)** | Trade policy | Country × product × measure | Measure-level | Multi-year | WITS API / bulk |
| **GSP Utilization** | Trade preferences | Preference-granter → beneficiary | Country pair × product | Annual | Web portal |

### Tier 2: Country-Level Attributes (enriches existing nation nodes)

| Dataset | Domain | Entity Types | Granularity | Temporal | Format |
|---------|--------|-------------|-------------|----------|--------|
| **Liner Shipping Connectivity Index (LSCI)** | Maritime | Countries | Country-level | Monthly/quarterly | CSV |
| **Port LSCI (PLSCI)** | Maritime | Ports | Port-level | Periodic | CSV |
| **Merchant Fleet by Flag** | Maritime | Countries × ship types | Country-level | Annual | CSV |
| **Container Port Throughput** | Maritime | Countries (ports?) | Country-level | Annual | CSV |
| **Seaborne Trade Volume** | Maritime | Countries | Country-level | Annual | CSV |
| **FDI Inflows/Outflows (aggregate)** | Investment | Countries | Country-level | Annual, 40+ years | CSV |
| **GDP and Growth** | Economy | Countries | Country-level | Annual | CSV |
| **Commodity Prices** | Economy | Commodities | Commodity-level | Monthly | CSV |
| **International Transport Costs** | Trade/transport | Countries | Country-level | Annual | CSV |

### Tier 3: Entity-Level Data (creates new entity types)

| Dataset | Domain | Entity Types | Granularity | Notes |
|---------|--------|-------------|-------------|-------|
| **Port LSCI** | Maritime | Individual ports | Port-level | Could add ports as entities |
| **Investment Dispute Cases** | Legal | Disputes (investor vs state) | Case-level | Niche |
| **National Investment Laws** | Legal | Countries × laws | Law-level | Niche |

---

## 3. Schema Mapping

### 3a: Four Problems Assessment

| Dataset | Enumeration | Placement | Relationships | Properties |
|---------|------------|-----------|---------------|------------|
| **LSBCI** | ~196 countries | No coords (country-level) | ✓ Country↔Country shipping connectivity | ✓ Connectivity score (weighted, directional) |
| **Trade Matrix** | ~200 countries × ~260 products | No coords | ✓ Country→Country exports/imports | ✓ Value in USD (weighted, directional) |
| **Bilateral FDI** | 206 economies | No coords | ✓ Country→Country investment flows | ✓ FDI value (weighted, directional) |
| **BITs** | 2,864 treaties, ~190 countries | No coords | ✓ Country↔Country treaty links | ✓ Status (in force/terminated), date, type |
| **LSCI** | ~196 countries | No coords | ✗ (single-country metric) | N/A — it's an attribute, not a relationship |
| **Port LSCI** | ~1,000 ports? | Possibly | ✗ (port-level metric) | N/A — attribute |
| **Merchant Fleet** | ~196 countries × ship types | No coords | ✗ | N/A — attribute |
| **TRAINS/NTMs** | Countries × products × measures | No coords | ✓ Country imposes measure on product from country | ✓ Measure type, affected products |

### 3b: DB Integration Mapping

#### HIGH VALUE: Bilateral Datasets → New Relationship Types

**1. LSBCI → `shipping_connected_to` relationship**
- **New relationship type**: `shipping_connected_to(country_A, country_B, score=X)`
- **Join method**: ISO country code → MRGID lookup (need to build once)
- **What it adds**: Weighted, quantitative shipping connectivity between every country pair
- **Coverage**: ~196 × 196 matrix = up to ~19,000 directed edges
- **Properties**: Connectivity score (0-1 scale), quarterly time series

**2. Trade Matrix → `trades_with` relationship**
- **New relationship type**: `exports_to(country_A, country_B, value=X, product=Y)`
- **Join method**: ISO code → MRGID
- **What it adds**: Directed, weighted trade flows between countries
- **Coverage**: ~200 × 200 × 260 products = massive, but can aggregate to country-pair level
- **Properties**: Trade value (USD), product category, year (time series)

**3. Bilateral FDI → `invests_in` relationship**
- **New relationship type**: `invests_in(country_A, country_B, value=X)`
- **Join method**: ISO code → MRGID
- **What it adds**: Directed investment flows between countries
- **Coverage**: 206 economies, ~40 years of history
- **Properties**: FDI value (USD), flow vs stock, inward vs outward

**4. BITs → `has_investment_treaty_with` relationship**
- **New relationship type**: `has_treaty_with(country_A, country_B, type=BIT, status=in_force)`
- **Join method**: Country name → MRGID (name matching, but BITs use English names)
- **What it adds**: Legal/institutional links between countries
- **Coverage**: 2,864 treaties across ~190 countries
- **Properties**: Treaty type, status, date signed, date in force

#### MEDIUM VALUE: Country Attributes → Enrich Existing Nations

**5. LSCI → attribute on Nation entities**
- **New attribute**: `shipping_connectivity_score` on nations
- **What it enables**: "Which nations are most connected to global shipping?"
- **Cross-query potential**: Combine with our Sea adjacency data — "Of countries bordering the Mediterranean, which has the highest LSCI?"

**6. Merchant Fleet → attribute on Nation entities**
- **New attribute**: `fleet_size_dwt`, `fleet_count` by ship type
- **What it enables**: "Which nations have the largest merchant fleets?"

**7. Container Port Throughput → attribute on Nation entities**
- **New attribute**: `container_throughput_teu`
- **What it enables**: "Which nations handle the most container traffic?"

#### LOWER VALUE BUT INTERESTING: New Entity Types

**8. Port LSCI → Port entities**
- **New entity type**: `Port` (~1,000 ports)
- **Relationships**: `located_in(port, country)`, potentially `serves(port, sea)`
- **Challenge**: Would need coordinates (PLSCI may not provide them — would need a separate port database for placement)
- **Value**: Ports are the link between our maritime geography and trade/shipping data

### 3c: Query Potential

**With LSBCI (shipping connectivity):**
- "Which two countries have the strongest shipping connection?"
- "Among countries bordering the South China Sea, which pair has the weakest shipping link?"
- "How does shipping connectivity correlate with the number of submarine cables between two countries?"
- "What is the average shipping connectivity for landlocked nations?" (should be near zero — good sanity check)

**With Trade Matrix:**
- "What is the total trade volume passing through the Strait of Malacca?" (combine trade data with our strait→sea→nation adjacency)
- "Which country is the biggest trading partner of every Mediterranean nation?"
- "Do countries that share a river basin trade more with each other?"

**With Bilateral FDI:**
- "Which country receives the most foreign investment from its river-sharing neighbors?"
- "Do countries with investment treaties have higher FDI flows?"

**With BITs:**
- "How many investment treaties does each country have? Map against geographic neighbors."
- "Which country pairs have both a shared border AND an investment treaty?"
- "What percentage of bilateral investment treaties are between countries that share a sea?"

---

## 4. Value Ranking

| # | Dataset | Integration Ease | Uniqueness | Graph Value | Query Potential | Priority |
|---|---------|-----------------|-----------|-------------|-----------------|----------|
| 1 | **LSBCI** (bilateral shipping) | Medium (ISO→MRGID needed, CSV download) | **High** — only global bilateral shipping connectivity source | **High** — ~19K directed weighted edges | Cross-refs with cables, seas, straits | **HIGH** |
| 2 | **BITs** (investment treaties) | Medium (web scraping or manual, name matching) | **High** — UNCTAD is the sole authority | **High** — ~2,800 bilateral treaty edges | Legal/institutional layer on geographic graph | **HIGH** |
| 3 | **Trade Matrix** | Medium (CSV bulk, ISO→MRGID) | Medium — also available via UN Comtrade | **High** — massive bilateral edge set | Trade overlaid on geography | **HIGH** |
| 4 | **Bilateral FDI** | Medium (CSV bulk, ISO→MRGID) | **High** — UNCTAD is the primary authority | **High** — directed weighted investment edges | Investment geography | **MEDIUM-HIGH** |
| 5 | **LSCI** (country-level) | Easy (CSV, ISO codes) | High — UNCTAD-proprietary index | Low — node attribute only | Enriches nations | **MEDIUM** |
| 6 | **Port LSCI** | Medium (CSV, needs port→country join) | High | Medium — could add port entities | Port-level connectivity | **MEDIUM** |
| 7 | **Merchant Fleet** | Easy (CSV, ISO codes) | Medium | Low — node attribute | Fleet statistics | **LOW** |
| 8 | **TRAINS/NTMs** | Hard (WITS API, complex dimensions) | High | Medium — trade policy edges | Trade barrier analysis | **LOW** |
| 9 | **Container Throughput** | Easy (CSV) | Medium | Low — node attribute | Port activity | **LOW** |

---

## 5. Gaps: What UNCTAD Does NOT Cover

- **No port coordinates.** PLSCI ranks ports but doesn't provide lat/lon. Would need a separate port database (World Port Index, GeoNames) to place ports on the map.
- **No shipping route geometry.** LSBCI measures connectivity between country pairs but doesn't provide the actual route (which straits, which seas). Mapping "Japan–Germany shipping connectivity" to "passes through Malacca, Suez" requires inference from our sea/strait topology.
- **No commodity-to-geography mapping.** Trade data tells you "Brazil exports $X of soybeans to China" but not "via which ports" or "through which straits."
- **No real-time data.** LSCI is monthly, trade matrix is annual. No live vessel tracking or AIS data.
- **No sub-national data.** Everything is country-level (except ports). No state/province trade data.
- **Terrestrial transport.** UNCTAD covers maritime and some air freight. No road, rail, or pipeline data.
- **Investment treaties have no API.** The IIA Navigator is web-only. Extraction would require scraping or manual download.

---

## 6. Integration Prerequisites

Before extracting ANY UNCTAD data, we need:

### One-time: ISO Country Code → MRGID Mapping Table
All UNCTAD data uses ISO 3166 codes. Our DB uses MRGIDs with no ISO codes populated. Building this mapping is the **single highest-value infrastructure investment** — it unlocks every UNCTAD dataset (and every other international dataset that uses ISO codes).

**Approach:**
1. Our DB has 196 Nation entities with names (in Dutch/mixed)
2. Fetch ISO 3166 country list (or use a standard library like `pycountry`)
3. Match via name + alias infrastructure (we've already solved this for 5 sessions)
4. Store as `iso_code` field on entities (column already exists but is empty)

**Estimated effort:** 1-2 hours. One-time. Permanent payoff.

---

## 7. Recommended Next Steps

### Phase 1: Infrastructure (do first)
1. Build ISO 3166 → MRGID mapping and populate `iso_code` on all Nation entities

### Phase 2: Highest-value extraction (pick one)
2. **LSBCI** — `/data-inspector` to probe the actual CSV structure, confirm bilateral format, test a sample download
3. **BITs** — `/data-inspector` to probe the IIA Navigator, test scraping feasibility, check if treaty list can be exported
4. **Trade Matrix** — `/data-inspector` to probe CSV bulk download, confirm bilateral dimensions

### Phase 3: Attribute enrichment
5. LSCI (country-level shipping connectivity score) — easiest win, single CSV
6. Merchant fleet, container throughput — straightforward country-level attributes

### Phase 4: Deep extraction
7. Full trade matrix (massive — design carefully)
8. Bilateral FDI
9. Port LSCI (requires separate port coordinate source)
