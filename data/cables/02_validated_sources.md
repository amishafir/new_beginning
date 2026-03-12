# Validated Sources: Cross-Border Communication Cables

## Validation Matrix

| Source | Authority | Currency | Coverage | Structured? | Verdict | Reasoning |
|---|---|---|---|---|---|---|
| **TeleGeography API (free)** | 5/5 | 5/5 | 5/5 (submarine) | ✓ JSON API | **APPROVED** | Industry standard. CC BY-SA 4.0. Per-cable endpoint has all fields we need. |
| **TeleGeography Licensed** | 5/5 | 5/5 | 5/5 | ✓ JSON via S3 | **SKIP** | Same data as free API — paid license adds nothing for our scope. |
| **TeleGeography GitHub Crawl** | 2/5 | 2/5 | 3/5 | ✓ GeoJSON | **SKIP** | Stale crawl (last updated Jul 2024) of the same free API. Use the live API directly. |
| **ArcGIS FeatureServer** | 2/5 | 2/5 | 3/5 | ✓ JSON | **SKIP** | Repackages TeleGeography data. Unknown maintainer. Use original source. |
| **AfTerFibre** | 3/5 | 2/5 | 1/5 | ✓ GeoJSON/CSV | **SKIP** | Africa-only terrestrial. Last updated 2020. Too narrow and stale for a global project. |
| **UNESCAP Reports** | 4/5 | 3/5 | 1/5 | ✗ PDF only | **SKIP** | Asia-Pacific PDF reports. No structured data. Would require manual extraction. |
| **InfraNav** | 4/5 | 4/5 | 5/5 | ✓ (paid) | **SKIP** | Requires commercial license. No free data access. |
| **ITU BBmaps** | 4/5 | 3/5 | 3/5 | ✗ Visualization | **SKIP** | Interactive map with no download/API. Angular app — data not extractable. |
| **ICPC** | 4/5 | 4/5 | 2/5 | ✗ No data | **SKIP** | Links to TeleGeography for cable data. No independent structured dataset. |

## TeleGeography: Detailed Validation

### Authority (5/5)
- Industry research firm since 1999, subsidiary of PriMetrica
- Directly contacts cable operators worldwide for system data
- Used as the reference source by ICPC, ITU, ArcGIS, and every other cable mapping project
- There is no independent alternative — TeleGeography IS the primary source for submarine cable data

### Currency (5/5)
- Actively maintained — includes cables with RFS dates through 2027+
- Team of analysts track new deployments, landing points, topology changes, retirements
- API reflects current state (tested: 2Africa shows 2024 RFS, SeaMeWe-6 shows 2027 planned)

### Coverage (5/5 for submarine, 0/5 for terrestrial)
- 1,261 submarine cable systems globally
- 1,076 landing points
- Covers planned, under construction, and operational cables
- Does NOT cover terrestrial/overland cables (TEA, EPEG, JADI, etc.)

### Data accessibility
- Free API, no authentication required
- CC BY-SA 4.0 license for map images/data
- Per-cable endpoint provides all fields: name, length, RFS, owners, suppliers, landing_points with country

### Limitations
- **Submarine only** — no terrestrial cables
- **No cable capacity data** in free API (requires paid subscription)
- **Landing point coordinates not in per-cable response** — need `landing-point-geo.json` for coordinates
- **Owners field is a comma-separated string**, not structured array — needs parsing

## Terrestrial Cable Gap

No free, structured, global source for terrestrial communication cables exists. This is a **known gap** we must flag:
- AfTerFibre covers Africa only (stale, 2020)
- UNESCAP covers Asia-Pacific only (PDF, not structured)
- InfraNav is global but commercial
- Major terrestrial cables (TEA, EPEG, JADI, WorldLink, TAE) would require operator website scraping

**Decision**: Proceed with submarine cables only from TeleGeography. Document terrestrial as an open gap.

## Approved Sources

| Purpose | Source | Access |
|---|---|---|
| **Primary extraction** | TeleGeography free API | `submarinecablemap.com/api/v3/` |
| **Verification** | Cable operator websites (per cable's `url` field) | Per-cable URLs in API data |
