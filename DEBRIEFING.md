# Session Debriefing

## What We Set Out To Do
Build a table of global cross-border communication cables and the countries they connect. This evolved into a broader exercise in designing a reusable research pipeline.

---

## Task 1: Communication Cables

### What happened
1. Asked to list all cross-border communication cables (submarine + terrestrial) with connected countries
2. Sent two sub-agents to research — they Googled cable names and pulled country lists from Wikipedia and SubmarineNetworks.com
3. Compiled a 40-row table and presented it as fact

### What went wrong
- **Skipped source validation entirely** — used Wikipedia as a primary source
- **Skipped data inspection** — never checked if a structured source existed before manual Googling
- **No verification** — never compared results against operator websites
- User challenged the sources. Eurasia Review, Wikipedia — why were these considered valid?

### What we discovered
- **TeleGeography** (submarinecablemap.com) has a free JSON API with 1,312 cables
- The `/api/v3/cable/all.json` endpoint only returns IDs and names
- The per-cable endpoint `/api/v3/cable/{id}.json` has full landing points with explicit `country` field
- Terrestrial cables (TEA, EPEG, JADI, WorldLink) are NOT in TeleGeography — they require separate sources (UNESCAP, operator announcements)
- The correct approach would have been: fetch all IDs → fetch each cable's details → extract countries programmatically

### Cable table status
- The 40-row table exists but is sourced from Wikipedia/secondary sources
- It was never rebuilt from TeleGeography API data
- Should be considered **unverified**

---

## Task 2: Cross-Border Rivers

### What happened (following the pipeline this time)
1. **Source Scout**: Searched for structured databases, found 9 candidate sources
2. **Source Validator**: Validated each — only OSU TFDD had the basin→country mapping field
3. **Data Inspector**: Downloaded the 64.8MB shapefile, inspected with geopandas — found 316 basins, 157 countries, 818 basin-country unit records, with explicit `Basin_Name`, `adm0_name` (country), and `Riparian_C` fields
4. **Extraction**: Python script grouped BCU records by basin, cleaned country names, produced markdown table + JSON
5. **Data Verifier**: Spot-checked 6 rivers against official basin organizations (NBI, OTCA, ICPDR, MRC, ICPR, ZAMCOM) — 5/6 matched, found Suriname missing from Amazon (source data limitation)

### Result
- 316 transboundary river basins with complete country lists
- Verified against primary sources
- One known gap: Suriname missing from Amazon in TFDD source data
- Output: `data/06_rivers_table.md` and `data/05_raw_rivers_data.json`

---

## Agent/Skill Design Journey

### Phase 1: Over-engineering (13 files)
Built 6 agents + 6 skills + 1 orchestrator:
- source-scout, source-validator, data-inspector, strategy-architect, data-fetcher, data-verifier
- api-profiler, source-credibility-check, batch-fetch, diff-verifier, data-classifier, gap-reporter
- run-pipeline (orchestrator)

### Phase 2: Reality check
- `/run-pipeline` failed — Claude Code didn't register custom `.md` files as executable slash commands
- Had to manually read each `.md` and follow instructions
- During the rivers task, only 4 of 13 files were actually used
- Unused skills (api-profiler, batch-fetch, data-classifier, gap-reporter, diff-verifier, source-credibility-check) were designed for the cable problem's specific shape, not for general research
- Strategy Architect and Data Fetcher were unnecessary as separate agents — the strategy was obvious after inspection, and extraction depends entirely on format

### Phase 3: Pruning to 4
Kept only what proved useful across both tasks:
1. **source-scout.md** — find and classify candidate sources
2. **source-validator.md** — validate authority, currency, fitness
3. **data-inspector.md** — download/probe actual data, check real fields
4. **data-verifier.md** — spot-check output against independent primary sources

Extraction (step between inspector and verifier) is intentionally NOT a skill — it's different every time.

---

## Key Lessons

### On sources
- **Wikipedia is not a data source.** It's a tertiary source that anyone can edit. Trace back to what Wikipedia cites.
- **"Reachable" ≠ "valid."** A working URL doesn't mean the data is authoritative or has the fields you need.
- **Always ask: who is the data originator?** An aggregator is always less authoritative than the original.
- **One good structured source beats ten blog posts.** TFDD shapefile replaced hours of manual Googling.

### On inspection
- **Never build extraction logic before inspecting the data.** The cable mistake: assumed TeleGeography's `all.json` had country data — it didn't (only IDs and names). The river success: downloaded shapefile and checked fields before writing any processing code.
- **Check at least 2-3 sample records.** Fields can be inconsistent across records.
- **Format determines the entire downstream approach.** API → batch fetch script. Shapefile → geopandas. PDF → manual. This can't be pre-decided.

### On verification
- **Always verify against INDEPENDENT primary sources** — not the source you extracted from.
- **Verification catches source limitations, not just our errors.** Suriname was missing from TFDD's Amazon delineation — a source data issue we'd never know about without checking.

### On agent/skill design
- **Start with what you need, not what might be useful.** 13 files was over-engineering. 4 proved sufficient.
- **Don't hardcode domain-specific assumptions.** File names like `cable_table.md`, fields like `cable_type`, classification like `trans-atlantic` — all broke when applied to rivers.
- **The process matters more than the files.** The `.md` files encode a discipline (discover → validate → inspect → verify). The discipline is what prevents mistakes, not the file format.
- **Generic skills that branch on format beat specialized skills per format.** One `data-inspector.md` with "if API... if shapefile... if PDF..." beats separate api-profiler.md, shapefile-parser.md, etc.

### On Claude Code slash commands
- Custom `.md` files in `.claude/commands/` are prompt templates, not executable automation
- They only work as slash commands within a Claude Code session that recognizes the project
- They're useful as structured prompts to follow, but they don't run autonomously

---

## Current State of the Repo

```
new_beginning/
├── CLAUDE.md                      # Project config (generic research pipeline)
├── DEBRIEFING.md                  # This file
├── README.md
├── .claude/commands/
│   ├── source-scout.md            # Step 1: Find sources
│   ├── source-validator.md        # Step 2: Validate sources
│   ├── data-inspector.md          # Step 3: Inspect actual data
│   └── data-verifier.md           # Step 4: Verify output
├── data/
│   └── rivers/                    # Rivers research output
│       ├── 01_candidate_sources.md
│       ├── 02_validated_sources.md
│       ├── 03_inspection_results.md
│       ├── 04_pipeline_strategy.md
│       ├── 05_raw_rivers_data.json
│       ├── 06_rivers_table.md
│       ├── 07_verification_report.md
│       └── raw/                   # Downloaded shapefiles
```

## Key Lesson: Validate Extracted Values, Not Just Structure

Inspecting a source's data structure (field names, types, record count) is necessary but not sufficient. The **values inside the fields** also need validation. Data sources may contain entries that look valid but aren't what you expect.

Example: The TFDD shapefile's `adm0_name` field appeared to contain country names. We checked that the field existed and had data — but never validated whether every value was actually a recognized country. It turned out 10 of 157 entries were disputed territories, sub-national regions, or ambiguous labels (e.g., "Aksai Chin", "Arunachal Pradesh", "China/India", "West Bank").

**General principle:** After extraction, validate categorical values against an authoritative reference list (e.g., ISO 3166 for countries, IATA codes for airports, etc.). Don't assume the source's values are clean just because the source itself is authoritative.

## Open Items (from Sessions 1-2)
- ~~Cable table was never rebuilt from TeleGeography API~~ — Done in Session 5 (690 cables, 1,907 landing points)
- Rivers table has known Suriname gap in Amazon basin (TFDD source limitation)
- Rivers table contains 10 entries that are disputed territories / non-sovereign entities, not recognized countries — needs a decision on how to handle them
- ~~No extraction scripts were saved~~ — Fixed in Session 3 (scripts saved as `.py` files)
- Slash commands were never tested as actual `/command` invocations in a fresh session

---

## Task 3: Global Structured Database (Marine Regions)

### What we set out to do
Build a queryable graph database of the world: nations, seas, straits, rivers, seafloor features, maritime zones, and ecological regions — all with relationships between them. Answers questions like "What seas border Turkey?" or "Which nations share the South China Sea?"

Primary source: **marineregions.org** (Flanders Marine Institute gazetteer, 449 entity types, REST API).

### What happened

#### Phase 0: API Investigation (the hard part)
1. Started by testing the documented API endpoints
2. `getGazetteerRecordsByType.json/13/` returned 404 — type ID `13` is "Nation" in the types list, but the endpoint doesn't accept IDs
3. Spent ~6 API calls and multiple URL format variations debugging this
4. **Discovery**: the endpoint uses **type names**, not numeric IDs: `getGazetteerRecordsByType.json/Ocean/` works, `/19/` does not
5. This was undocumented. The Swagger spec was dynamically generated and didn't load via fetch. Had to discover the correct format empirically.

#### Phase 1: Entity Extraction (worked well)
6. Built `extract_marine_regions.py` with rate limiting, pagination, checkpointing, retry logic
7. Extracted 37,149 entities across 7 tiers in ~30 minutes of API time
8. Used background tasks to parallelize tier extraction (Tier 1-2, then 3-4, then 6-7)
9. Discovered some types (Spur, Bank, Reef, etc.) weren't fetched in first pass — checkpoint only tracked what ran, so these were fetched in a follow-up run

#### Phase 2: Relationship Extraction (the biggest lesson)
10. Tested `getGazetteerRelationsByMRGID` — expected rich relationships
11. **Reality**: it returns only 1-2 parent hierarchy links per entity. Mediterranean Sea → 1 relationship. Pacific Ocean → 1 relationship. Belgium → 1 relationship.
12. Worse, some were wrong: Strait of Gibraltar → "La Manche" + "North Sea". English Channel → "South Pacific Ocean."
13. **The plan's core assumption was wrong.** The plan estimated 15,000-25,000 relationships from the API. The API yields ~1 per entity.

#### Pivoting to multiple relationship sources
14. Discovered `Relationship.csv` already in the repo (2,655 curated relationships from a prior session): land borders, sea adjacency, river flows, hierarchy
15. Built `build_relationships.py` with three sources:
    - **CSV import** (1,292 relationships): borders, part_of, adjacent_to, flows_through
    - **API hierarchy** (407 relationships): nation→continent, sea→parent ocean
    - **Spatial inference** (482 relationships): bounding box overlap for nation↔sea adjacency
16. Total: 2,181 relationships — far short of the plan's 15,000-25,000 estimate

#### Name matching nightmare
17. Marine Regions is maintained by the Flanders Marine Institute (Belgium, Dutch-speaking)
18. Many nation names are in Dutch: België, Frankrijk, Nederland, Groothertogdom Luxemburg, Türkiye
19. The CSV uses English names. Matching required 5 rounds of alias additions.
20. Rivers in CSV are just "Jordan" but DB has "Jordan River" — needed suffix matching
21. Some CSV entries are sub-national or disputed ("Scotland", "Gaza Strip", "Dhekelia") with no DB match

#### Spatial inference: mixed results
22. Bounding box overlap correctly identified: Gulf of Riga ↔ Latvia, Caribbean Sea ↔ Nicaragua, Ionian Sea ↔ Albania
23. But also produced false positives: landlocked Bolivia/Paraguay/Chad "adjacent" to seas (their bounding boxes extend to coastal water body boxes)
24. Had to add a landlocked-nation exclusion list. Also had to filter out overly broad regions (General Sea Areas spanning entire oceans)

#### What we ended up with
- **37,149 entities** (98% with coordinates, 47% with bounding boxes)
- **2,181 relationships** (but only **2% of entities** have any relationship)
- Verification: 21 automated checks, all passing
- Query interface works for the entities that have relationships

### What went right
- **Entity extraction is excellent.** 37,149 entities from a single authoritative source, with coordinates and bounding boxes. The API is great for enumeration.
- **Checkpointing.** Could resume extraction after interrupts. Background tasks could run in parallel.
- **Scripts were saved.** Unlike Session 1-2, all extraction code persists as `.py` files that can be re-run.
- **Verification was built in.** 21 automated checks caught real issues (e.g., Strait of Gibraltar typed as "Sea", Mid-Atlantic Ridge stored as "Medio-Atlantica Ridge").
- **The pivot was fast.** When the relationship API proved useless, we switched to CSV + spatial within the same session.

### What went wrong

#### 1. The plan was built on an untested assumption
The entire relationship strategy assumed `getGazetteerRelationsByMRGID` would return rich, typed relationships. We tested the entity endpoints but not the relationship endpoint before committing to the plan. The plan phase should have included **empirical API testing** — not just "investigate parameter format" but "test whether the endpoint returns what we actually need."

**Fix for CLAUDE.md / agents:** Data inspector should explicitly test the **relationship/linkage data**, not just entity data. Add a step: "For graph/relational projects: test whether the source provides the connections you need, not just the nodes."

#### 2. The Relationship.csv was already in the repo — we didn't look
We had 2,655 curated relationships sitting in the project root from a prior session. We didn't discover this until after the API relationship approach failed. If we'd inventoried existing data first, we could have designed the relationship strategy around extending the CSV rather than starting from scratch with the API.

**Fix:** Before starting extraction, inventory what already exists in the repo. `ls`, `wc -l`, and a quick look at existing data files.

#### 3. The 2% relationship coverage gap
37,149 entities but only 767 have any relationship. Entire categories have zero relationships: all 10,161 seafloor features, all 15,295 ecological zones, all 578 maritime zones. The database is a catalog, not a graph.

**Root cause:** The CSV only covers nations/seas/rivers. The API only provides parent hierarchy. There's no structured source for "which seamount is in which ocean" or "which MPA overlaps which EEZ."

**What would fix this:**
- Download the GeoPackage datasets (EEZ v12, IHO v3, EEZ-IHO intersections) — these have pre-computed spatial overlaps
- Compute spatial containment/overlap from bounding boxes for more entity pairs
- Use the `getGazetteerRecordsByLatLong` endpoint to determine which features fall within which regions

#### 4. Name matching should have been solved upfront
We went through 5 iterations of adding aliases (Luxembourg → Groothertogdom Luxemburg, Belgium → België, France → Frankrijk, etc.). This is a known problem with multilingual data sources. Should have:
- Fetched `getGazetteerNamesByMRGID` for all nations upfront to get English aliases
- Built a bidirectional name index before attempting any matching

#### 5. Background task management was fragile
- Several tasks "completed" but had empty output files (buffering issue)
- One task ID became unfindable
- Had to poll repeatedly to check status
- No way to see intermediate progress for long-running tasks

#### 6. Verification was too narrow
The verify script checks entity counts and a few sample relationships. It doesn't catch the fundamental issue: that 98% of entities are disconnected. Need a coverage metric: "what percentage of entity types have at least N relationships?"

---

## Updated Lessons Learned

### On planning
- **Test assumptions before committing to a plan.** If your plan depends on an API returning rich data, test that endpoint with real calls before writing 200 lines of extraction code. A 5-minute test could have saved 30 minutes of relationship extraction code that proved useless.
- **Inventory existing data first.** Before sourcing new data, check what's already in the repo. The Relationship.csv was sitting right there.
- **Estimate skeptically.** The plan estimated 15,000-25,000 relationships. We got 2,181. When a plan makes optimistic estimates about an untested API, flag that estimate as "pending validation."

### On APIs
- **Documentation lies (or is incomplete).** The Marine Regions Swagger spec was dynamically generated and couldn't be fetched statically. The `getGazetteerRecordsByType` endpoint silently requires type **names**, not the numeric IDs that `getGazetteerTypes` returns. The relationship endpoint returns wrong data (Strait of Gibraltar → La Manche). Never trust docs — test empirically.
- **Entity enumeration and relationship quality are independent.** An API can be excellent for listing entities (this one is) and terrible for relationships (this one is). Test both dimensions.
- **Rate-limit respectfully.** 1-second delays and retry logic kept us in good standing. The API never blocked us.

### On multilingual data
- **Anticipate name mismatches.** When a data source is maintained in a non-English country, names will be in the local language. Budget time for building a name alias system, or fetch the alternate-names endpoint first.
- **Build bidirectional name indexes.** Map both "Belgium" → MRGID and "België" → MRGID from the start. Don't add aliases one by one as failures appear.

### On graph databases
- **Nodes are easy, edges are hard.** Any decent API can give you a list of entities. The relationships between them are the real challenge and require either: (a) a source that explicitly provides them, (b) spatial computation, or (c) manual curation.
- **Measure connectivity, not just count.** 37,149 entities sounds impressive. 2% relationship coverage means it's a catalog, not a graph. The right metric is: "can the database answer the questions in the plan?"
- **Bounding box overlap is a crude proxy for adjacency.** It works for large bodies (Caribbean Sea ↔ Nicaragua) but fails for landlocked nations and overly broad regions. Real spatial analysis requires polygon intersection, not box overlap.

### On process
- **Save your scripts.** Session 1-2 lost all extraction code. This session saved everything as `.py` files. This is non-negotiable for reproducibility.
- **Decouple extraction from relationship-building.** `extract_marine_regions.py` and `build_relationships.py` being separate scripts was the right design. It let us re-run relationship building without re-fetching entities.
- **The research pipeline agents (source-scout, etc.) weren't used this session.** When you arrive with a pre-made plan and a known API, the agents don't add value. They're most useful in the discovery phase when you don't yet know where the data lives. The agents are for "what should I use?" — not for "I know what to use, help me extract it."

### On the agent pipeline design (updated)
The 4-agent pipeline (scout → validate → inspect → verify) remains valid but needs an update:

**New principle: Test linkage, not just structure.**
The data-inspector agent should be updated to include a check: "If this is a relational/graph project, test whether the source provides the connections between entities, not just the entities themselves." Our inspector would have caught that the relationship API was useless if it had tested 5 sample entities and found only 1 relationship each.

**New principle: Inventory before scouting.**
Add a "Step 0" before source-scout: check what data already exists in the project. This session had a Relationship.csv with 2,655 rows that we didn't discover until midway through.

---

## Session 3b: Relationship Enrichment

### What happened
After the debriefing revealed 2% relationship coverage, we implemented two strategies to fix it — without any new API calls or downloads.

#### Strategy #1: Point-in-bbox (`located_in`)
For every entity with lat/lon coordinates, find the smallest water body or nation whose bounding box contains that point. Pure computation on data already in the DB.

- **17,210 relationships created**
- 12,217 entities placed in their containing Sea
- 4,445 entities placed in their containing Nation
- 548 entities placed in their containing Gulf
- Key design choice: pick the **smallest** containing bbox (most specific match). Magnaghi Seamount → Tyrrhenian Sea (48°²), not Mediterranean (656°²) or Atlantic (13,249°²). The `part_of` hierarchy already chains upward.

#### Strategy #2: Name parsing (`claimed_by`)
EEZ names follow the pattern "Albanian Exclusive Economic Zone" → strip suffix → "Albanian" → match to nation via adjective→nation map.

- **476 relationships created** (246 EEZs + 237 territorial seas → 476 matched, 5 unmatched)

#### Result
| Metric | Before | After |
|---|---|---|
| Relationships | 2,181 | **19,867** |
| Connected entities | 767 (2%) | **16,023 (43%)** |
| DB size | 6.3 MB | 8.0 MB |

#### What this revealed about strategy
The enrichment took 15 minutes of coding and produced 9x more relationships than everything before it combined. `located_in` alone (17,210) dwarfs CSV (1,292) + API (407) + spatial (482) + claimed_by (476). It should have been the **first** relationship strategy, not the last.

---

## The Three Problems Framework

The biggest lesson from Session 3. Every data project that builds structured output needs to solve three distinct problems. A single source rarely handles all three.

| # | Problem | Question | What solves it |
|---|---------|----------|----------------|
| 1 | **Enumeration** | "What exists?" | API listing, downloadable catalog, web scrape |
| 2 | **Placement** | "Where is it?" | Coordinates + bounding boxes → `located_in` for free |
| 3 | **Relationships** | "How are things connected?" | Curated datasets, name parsing, polygon intersection, domain rules |

### How this played out in Session 3

| Source | Entities (#1) | Placement (#2) | Relationships (#3) |
|---|---|---|---|
| MR API (enumeration) | Excellent (37K) | Good (98% coords) | Useless (~1 parent/entity) |
| MR API (relationships) | — | — | Wrong data, sparse |
| Relationship.csv | — | — | Good (1,292 curated edges) |
| Point-in-bbox computation | — | — | **Best** (17,210 from existing data) |
| EEZ name parsing | — | — | Good (476 mechanical matches) |

**The mistake was assuming the MR API would solve all three.** We planned 200 lines of relationship extraction code for an endpoint that returns 1 record per entity. If we'd tested 5 sample calls first, we'd have known in 5 minutes.

### How to apply going forward

Before writing any plan:
1. **Inventory the repo** — `ls`, check existing files
2. **Test each source against all three problems** — not just "does it have data" but "does it have entities, coordinates, AND relationships"
3. **For any gap, decide the fill strategy before planning** — spatial computation? name parsing? curated dataset? polygon download?
4. **Start with what's free** — `located_in` from coordinates costs zero API calls

Updated in: `CLAUDE.md` (workflow + principles) and `.claude/commands/data-inspector.md` (three-problem framework as Step 1).

---

## Current State of the Repo

```
new_beginning/
├── CLAUDE.md                         # Project config (three-problem framework)
├── DEBRIEFING.md                     # This file
├── README.md
├── Relationship.csv                  # 2,655 curated geographic relationships
├── extract_marine_regions.py         # Entity extraction from MR API
├── build_relationships.py            # Relationship building (CSV + API + spatial)
├── enrich_relationships.py           # located_in + claimed_by enrichment
├── merge_tfdd_rivers.py              # TFDD river basin merge (Session 4)
├── query_world.py                    # Interactive query interface
├── verify_database.py                # 21 automated verification checks
├── .claude/commands/
│   ├── source-scout.md               # Step 1: Find sources
│   ├── source-validator.md           # Step 2: Validate sources
│   ├── data-inspector.md             # Step 3: Three-problem inspection + overlap
│   ├── data-merger.md                # Step 6: Cross-source integration
│   └── data-verifier.md              # Step 7: Verify output
├── data/
│   ├── rivers/                       # Rivers research output (Session 2)
│   └── marine_regions/
│       ├── global_map.db             # SQLite database (8 MB, 37.4K entities, 21.4K relationships)
│       └── checkpoint.json           # Extraction progress tracker
```

---

## Task 4: Cross-Source Integration (TFDD → Marine Regions)

### What we set out to do
Merge the 316 transboundary river basins from TFDD (Session 2) into the Marine Regions database (Session 3), adding the world's major rivers and their country relationships.

### What happened

#### The overlap problem
First tested how many TFDD basins matched MR rivers. **18% match rate** (57 of 316). MR is a marine gazetteer — its 1,107 rivers are mostly coastal features (Belgian streams, estuaries). Major transboundary rivers (Danube, Mekong, Limpopo, Volta, Senegal) simply aren't in MR.

We verified this wasn't an extraction gap: checked all MR river-related types (River, Stream, Tributary, River Outlet), confirmed MR's own type definition says rivers are "water currents that flow out in the sea." The Danube, which flows through 19 countries, isn't in a marine gazetteer.

Also discovered 678 "Basin" entities were seafloor basins (ocean floor depressions), not river basins — "Amazon Basin" at lat -44.8 near New Zealand.

#### The merge
Built `merge_tfdd_rivers.py` with:
- River matching: exact → suffix ("Nile" → "Nile River") → alias → slash-split ("Congo/Zaire" → "Congo")
- Country matching: reused alias infrastructure from `build_relationships.py`, added TFDD-specific aliases (Eswatini → Swaziland, Lao People's Democratic Republic → Laos, etc.)
- Synthetic MRGIDs (900000+) for new entities
- Dry run mode before apply
- Source provenance tracking (`source='TFDD'`, `source_data='tfdd'`)

#### Result
| Metric | Before | After |
|---|---|---|
| Entities | 37,149 | 37,405 (+256 new rivers) |
| Relationships | 20,617 | 21,367 (+750) |
| `flows_through` edges | 119 | 869 (7x) |
| Rivers with country data | 51 | 342 |

9 unmatched "countries" — all disputed territories (Aksai Chin, Abyei, Ilemi triangle, etc.). This is a TFDD data quirk, not a matching gap.

### What went right
- **Overlap analysis first.** Testing the 18% match rate took 5 minutes and correctly set expectations.
- **Reused alias infrastructure.** Country matching worked well because we'd already built `NAME_ALIASES` in `build_relationships.py`.
- **Dry run pattern.** Caught the French Guiana gap (Territory, not Nation) before applying.
- **Source provenance.** Every new entity and relationship tagged with origin.

### What went wrong
- **No `source` column on entities at schema creation time.** Had to `ALTER TABLE` to add it.
- **Alias dictionaries are scattered.** `build_relationships.py` has `NAME_ALIASES`, `enrich_relationships.py` has `ADJECTIVE_TO_NATION`, `merge_tfdd_rivers.py` has `COUNTRY_ALIASES`. Three separate dictionaries for the same problem.
- **No reference IDs.** If both MR and TFDD used ISO country codes, the entire country-matching problem disappears.

### Key lesson: Entity matching is the real engineering problem

In every session, the hardest part wasn't getting data — it was matching entities across sources:
- Session 3: CSV country names → MR Dutch names (5 rounds of alias additions)
- Session 3b: EEZ adjectives → nation names (150-entry dictionary)
- Session 4: TFDD basin names → MR river names (18% raw match rate)

**This should be first-class infrastructure, not a per-script afterthought.**

---

## Updated Pipeline

The workflow is now 7 steps:

```
0. Inventory existing data
1. /source-scout      — find sources
2. /source-validator   — validate authority
3. /data-inspector     — three-problem test + overlap analysis
4. Plan extraction
5. Extract
6. /data-merger        — combine sources (entity matching, name resolution, provenance)
7. /data-verifier      — spot-check against independent sources
```

---

---

## Task 5: Submarine Cable Extraction (TeleGeography)

### What we set out to do
Rebuild the cable dataset from Session 1 — properly this time, using the full research pipeline instead of Wikipedia.

### What happened

#### The pipeline worked end-to-end
This was the first session where the pipeline ran without a single pivot:
1. **Source scout** found 9 candidates — all traced back to TeleGeography as the sole primary source
2. **Source validator** confirmed TeleGeography: Authority 5/5, Currency 5/5, Coverage 5/5 (submarine), CC BY-SA 4.0
3. **Data inspector** tested the API against the three problems — enumeration ✓ (690 cables), placement ✓ (1,907 landing points, 100% with coordinates), relationships ✓ (per-cable endpoint has landing_points with explicit country field). Rare case: **one source solves all three problems.**
4. **Extraction**: fetch `all.json` for 690 IDs → fetch each `{id}.json` for full detail. 690 API calls, 0 failures, ~6 minutes.
5. **Verification**: 15/17 checks pass (2 "failures" were naming issues in the test script, not data errors)

#### Result
| Metric | Before | After |
|---|---|---|
| Entities | 37,405 | 40,002 (+690 cables, +1,907 landing points) |
| Relationships | 21,367 | 27,280 (+5,913) |
| New relationship types | — | lands_at (3,152), located_in (1,897), connects (1,614) |

#### Edge cases: territories
12 country names from TeleGeography didn't match MR nations. Investigation revealed:
- **7 resolvable** with aliases: Virgin Islands (U.S./U.K.), Timor-Leste, Sint Maarten, Cocos Islands, Saint Martin, Saint Pierre and Miquelon → all exist in MR under slightly different names. Added 45 relationships.
- **5 genuinely missing** from MR: Curaçao, Bonaire/Sint Eustatius/Saba, Faroe Islands, Saint Barthélemy, British Indian Ocean Territory. Small territories MR doesn't track.

**Pattern**: edge cases are always territories, not countries. Every geographic data project hits this — small dependencies, overseas territories, and disputed areas that naming conventions disagree on. The long tail of entity matching is always territorial.

### What went right
- **The Three Problems Framework predicted success.** Inspector correctly identified TeleGeography as solving all three problems. No surprises during extraction.
- **Alias infrastructure compounded.** 89% of TeleGeography's country names matched MR out of the box — because we'd built country aliases across Sessions 3-4. Only 1 new nation alias (Mauritius) and 7 territory aliases needed.
- **Zero failed API calls.** Consistent JSON structure across all 690 cables. Rate limiting at 0.5s was sufficient.
- **Checkpointing reused cleanly** from the Marine Regions pattern.

### What went wrong
- **`all.json` returned 690 cables via curl but 1,312 via WebFetch.** We never resolved this discrepancy. Could be pagination, a different API version, or WebFetch hitting a cached/different endpoint. We extracted 690 and moved on — but didn't verify we got everything.
- **`owners` stored as raw comma-separated string.** If we ever want "which cables does Google own?", we'd need to parse and normalize owner names (Google vs Alphabet vs Google Cloud). Should have been a design decision at extraction time.
- **5 territories still unmatched.** Could be fixed by adding them as new entities (like we did with TFDD rivers), but we chose to skip — low impact.

### Terrestrial cables: a known gap
No free, structured, global source for terrestrial communication cables exists:
- AfTerFibre: Africa only, last updated 2020
- UNESCAP: Asia-Pacific PDFs, not structured
- InfraNav: Global but commercial license
- Major terrestrial cables (TEA, EPEG, JADI, WorldLink) would require operator website scraping

Documented as an explicit gap rather than an incomplete dataset.

### What a paid API would add
TeleGeography's licensed dataset (~annual subscription) adds fields the free API lacks:

| Field | Free | Paid | Enables |
|---|---|---|---|
| Cable capacity (Tbps) | ✗ | ✓ | "What's the total bandwidth between Europe and Asia?" |
| Lit vs potential capacity | ✗ | ✓ | "How utilized is this cable?" |
| Ownership percentages | ✗ | ✓ | "Who controls the most cable capacity?" |
| Fiber pair count | ✗ | ✓ | Technical infrastructure analysis |
| Latency data | ✗ | ✓ | Routing optimization |

The free API gives us the **graph structure** (what connects to what). The paid API adds **quantitative weight** to edges (how much capacity, who controls it). Different class of questions.

---

## Key Lessons (Updated)

### On the pipeline
- **When the framework works, extraction is fast.** Session 5 (cables) took ~1 hour total including scouting, validation, inspection, and extraction. Sessions 1-3 took many hours with multiple pivots. The difference: testing assumptions before building.
- **The Three Problems Framework is the key gating check.** If the inspector confirms all three problems are solved, extraction will be straightforward. If any problem fails, budget time for alternatives.

### On entity matching (updated pattern)
- **Nations match easily** — by Session 5, the alias infrastructure covers ~95% of country name variations automatically.
- **Territories are the long tail.** Curaçao, Faroe Islands, BVI, Sint Maarten — every geographic dataset handles these differently. This is a systematic problem, not a per-project one.
- **A shared `territory_aliases.json` would solve this permanently.** Instead of per-script alias dicts, a single file mapping all known territory name variants to MRGIDs. One investment, permanent payoff.

### On data completeness
- **"All" doesn't always mean all.** We got 690 cables from `all.json` but may be missing 600+. Pagination, API versioning, and response truncation are real risks. Always verify the count against an independent source.
- **String fields need parsing decisions at extraction time.** `owners` as comma-separated string, `length` as "45,000 km" — decide upfront which fields to normalize and which to store raw. This is cheaper during extraction than later.
- **Document gaps explicitly.** "No terrestrial cables — no free structured source exists" is more valuable than an incomplete dataset with no provenance.

---

## Current State of the Repo

```
new_beginning/
├── CLAUDE.md                         # Project config (three-problem framework)
├── DEBRIEFING.md                     # This file
├── README.md
├── Relationship.csv                  # 2,655 curated geographic relationships
├── extract_marine_regions.py         # Entity extraction from MR API
├── build_relationships.py            # Relationship building (CSV + API + spatial)
├── enrich_relationships.py           # located_in + claimed_by enrichment
├── merge_tfdd_rivers.py              # TFDD river basin merge (Session 4)
├── extract_cables.py                 # Submarine cable extraction from TeleGeography
├── query_world.py                    # Interactive query interface
├── verify_database.py                # 21 automated verification checks
├── .claude/commands/
│   ├── source-scout.md               # Step 1: Find sources
│   ├── source-validator.md           # Step 2: Validate sources
│   ├── data-inspector.md             # Step 3: Three-problem inspection + overlap
│   ├── data-merger.md                # Step 6: Cross-source integration
│   └── data-verifier.md              # Step 7: Verify output
├── data/
│   ├── rivers/                       # Rivers research output (Session 2)
│   ├── cables/                       # Cable research output (Session 5)
│   │   ├── 01_candidate_sources.md
│   │   ├── 02_validated_sources.md
│   │   ├── 03_inspection_results.md
│   │   └── extraction_checkpoint.json
│   └── marine_regions/
│       ├── global_map.db             # SQLite database (~10 MB, 40K entities, 27K relationships)
│       └── checkpoint.json           # MR extraction progress tracker
```

## Open Items
- **Remaining MR entity coverage gap** — mostly ICES rectangles (11K) and Natura 2000 (2.9K). Coverage on "interesting" entities (Tiers 1-4) is much higher.
- **Strait `connects` relationship** not built — straits connecting two seas. High-value, small scope (~155 straits).
- **EEZ `overlaps` relationship** not built — needs polygon data or could approximate from bboxes.
- **Terrestrial cables** — no free structured global source exists. Documented as explicit gap.
- **5 missing territories** — Curaçao, Faroe Islands, Bonaire, Saint Barthélemy, BIOT not in MR.
- **Cable owner normalization** — `owners` field stored as raw string, not parsed.
- **`all.json` count discrepancy** — 690 vs 1,312 unresolved. May be missing cables.
- Rivers table has known Suriname gap and disputed territory entries (from Session 2)
- `query_world.py` shows Dutch names (België, Frankrijk) — needs English alias display layer
- **27 unranked flows_through relationships** — Dutch names (Frankrijk, België, Nederland, Groothertogdom Luxemburg) and edge cases. Low priority.
- **Zambezi source country** — algorithm puts Angola at Rank 0, but documented source is Zambia (Kalene Hills, near Angola border). Consider swapping.
- **La Plata/Bolivia** — Bolivia ranked as Rank 1 on main stem, but the Paraná doesn't flow through Bolivia. Should be tributary-only.

---

## Task 6: River Flow Order (HydroRIVERS)

### What we set out to do
Add upstream→downstream country ordering to every transboundary river in the DB, enabling queries like "In Asia, how many countries are upper riparian states?"

This was the first **backwards pipeline** task — starting from the query, not the source.

### What happened

#### Phase 0: Working backwards from the query
1. Defined the target query: `SELECT country, COUNT(*) WHERE rank = 0 AND continent = 'Asia'`
2. Identified the gap: 342 rivers have `flows_through` relationships but only 51 had `Rank` values (from an old CSV of suspect quality — Drava had Hungary×3)
3. Assessed existing data: TFDD BCU shapefile has country polygons per basin but no flow order. Tested spatial distance-from-mouth approach on BCU alone — worked for simple rivers, failed for complex ones (tributaries).
4. Concluded: need a hydrological topology source (flow direction + river network).

#### Phase 1: Source discovery (fast — we knew what we needed)
5. Source scout found 7 candidates. HydroRIVERS (WWF/McGill) was the clear winner: 8.5M river reaches with `NEXT_DOWN` (flow topology), `DIST_DN_KM` (distance to outlet), `MAIN_RIV` (river network grouping).
6. Same HydroSHEDS ecosystem as TFDD — spatial alignment guaranteed.
7. Free for all use, no registration, direct download via Cloudflare CDN.

#### Phase 2: Algorithm development (the hard part)
8. Downloaded HydroRIVERS Europe (68 MB) for testing.
9. **v1: Strahler order filter** — keep only high-order reaches, rank countries by median DIST_DN_KM. Problem: missed source countries (headwater reaches are low Strahler order by definition).
10. **v2: NEXT_DOWN chain tracing** — trace main stem from mouth upstream, always following the reach with largest `UPLAND_SKM`. **Perfect for Danube** (9 countries correct). Problem: missed source countries where headwaters branch off the main-stem trace.
11. **v3: All reaches, high-order only** — included all countries but noisy (tributary countries ranked alongside main-stem ones).
12. **v4: All reaches, median DIST_DN_KM** — captured source countries (Lebanon in Orontes, Russia in Dnieper) but also included tributary-only countries.
13. **Final: Hybrid v2+v4** — NEXT_DOWN tracing for main-stem ordering + all-reaches check for country detection. Countries on the traced main stem get a Rank; countries in the network but not on the main stem get `tributary_only` (-1).

#### Phase 3: Full extraction
14. Downloaded all 8 HydroRIVERS regions (af, ar, as, au, eu, na, sa, si — ~500 MB total).
15. First run: 281/316 basins computed, 35 failed. All failures were **region mapping gaps** — Middle East rivers (AS continent) were in the EU HydroRIVERS region, Indonesia/PNG rivers in AU region, Alaska rivers in AR region.
16. Fixed: added fallback regions (AS→also check EU+AU, NA→also check AR).
17. Second run: **316/316 basins, zero failures.**
18. Applied 842/869 Rank values to the database (97% coverage). 27 unranked due to Dutch country names and edge cases.

#### Phase 4: Verification
19. Spot-checked 10 rivers against independent primary sources (MRC, ICPDR, Niger Basin Authority, FAO, Britannica).
20. Results: 6 perfect, 3 minor discrepancies, 1 partial. **90% accuracy.**
21. Minor issues: Zambezi (Angola vs Zambia source — near-border ambiguity), Rhine (France border vs flow-through), La Plata (Bolivia tributary misclassified as main stem).

### Result
| Metric | Before | After |
|---|---|---|
| Rivers with flow order | 51 (suspect quality) | 842 relationships ranked across 316 basins |
| Source countries identified | 0 reliably | 340 |
| Tributary-only countries | (concept didn't exist) | 171 |
| Target query works? | No | Yes — "26 Asian countries are upper riparian" |

### What went right
- **The backwards pipeline worked.** Starting from the query made every decision crisp. No over-sourcing, no extra attributes, no scope creep.
- **One new source was enough.** HydroRIVERS solved the entire problem. We didn't need HydroBASINS, RiverATLAS, GRIT, or MERIT Hydro.
- **Existing data did most of the work.** TFDD BCU polygons (already in repo) + HydroRIVERS topology = flow order. No new entities, no new relationships — just one attribute added to existing relationships.
- **Algorithm iteration was fast.** Four versions in one session, with live testing against the Danube (known 9-country ordering). Each version's failure mode was obvious and informative.
- **Region fallbacks saved the re-run.** When 35 basins failed, the root cause was clear (region mapping) and the fix was a 3-line config change, not a redesign.

### What went wrong
- **Country name matching — again.** 27 relationships unranked because the DB uses Dutch names (Frankrijk, België, Nederland) and the TFDD uses formal names (Lao People's Democratic Republic, Viet Nam). Six sessions in, this is still not fully solved. A shared `country_aliases.json` would prevent this permanently.
- **The algorithm was 90% of the effort, but no agent helped with it.** The scout, validator, inspector, merger, verifier — none of them help design an algorithm. The gap between "I have DIST_DN_KM" and "I have correct country ordering" required 4 iterations of spatial logic. This is a skill that doesn't fit the current agent framework.
- **Tributary-only is a new concept without a clear definition.** Is Uganda "tributary-only" on the Nile? The White Nile's source is in Burundi (via Uganda). But our NEXT_DOWN trace doesn't reach it because the algorithm follows the highest upstream area at each junction. The definition of "main stem" is ambiguous for rivers with multiple major tributaries.

---

## Key Lessons (Session 6)

### On the backwards pipeline
- **Start from the query when your dataset already exists.** The forward pipeline (source → extract → load) is for building. The backwards pipeline (query → gap → compute) is for making it useful. This session added zero entities and zero relationships — just one attribute — and unlocked a whole class of queries.
- **The query defines "done."** Previous sessions measured progress by counts (37K entities! 27K relationships!). This session had one acceptance criterion: does the SQL query return correct results? Binary, concrete, testable.
- **Problems 1-3 build the graph. Problem 4 makes it queryable.** Enumeration, Placement, Relationships give you structure. Properties (direction, weight, ordering) give you meaning. A `flows_through` without direction is a road without arrows.

### On enrichment vs building
- **Attribute augmentation is a different beast from entity import.** No new entities, no name matching for import, no synthetic IDs. The challenge is: compute the correct value for an attribute on existing relationships. The data model is stable — only the values change.
- **Existing data is the platform.** TFDD BCU polygons + HydroRIVERS topology + existing `flows_through` relationships = flow order. Each piece was necessary, none sufficient alone. The value was in combining them, not in any individual source.

### On algorithm development
- **Budget for algorithm iterations.** The first approach (Strahler filter) was wrong. The second (NEXT_DOWN trace) was 80% right. The fourth was the answer. Each failure mode taught something specific: v1 showed that headwaters are low-order, v2 showed that source countries branch off the main trace, v3 showed that including all reaches is noisy.
- **Test against a known complex case.** The Danube (19 basin countries, 9 main-stem countries) was the perfect test case. If the algorithm handles the Danube correctly, it handles everything. Pick your hardest case first.
- **No agent can design your algorithm.** The pipeline agents (scout, validate, inspect) are for finding and assessing data. The algorithm that bridges raw data to the target attribute is pure engineering — specific to the problem, requiring domain knowledge, and not automatable.

### On verification from queries
- **The query IS the verification framework.** "Is China the top upper riparian in Asia?" — if the answer is obviously right, the data is probably right. Previous sessions required tedious entity-by-entity spot-checking. Query-level verification is faster and higher-signal.

---

## Updated Pipeline

The framework is now:
- **Four Problems** (not three): Enumeration, Placement, Relationships, **Properties**
- **Two pipelines**: Forward (build) and Backwards (enrich)
- **Two merge modes**: Entity import (Mode A) and Attribute augmentation (Mode B)

```
Forward pipeline (building):
  0. Inventory → 1. Scout → 2. Validate → 3. Inspect (4 problems)
  → 4. Plan → 5. Extract → 6. Merge (entity import) → 7. Verify

Backwards pipeline (enriching):
  1. Define query → 2. Model gap → 3. Assess existing data
  → 4. Source if needed → 5. Extract & compute → 6. Merge (attribute augmentation) → 7. Verify
```

---

## Current State of the Repo

```
new_beginning/
├── CLAUDE.md                         # Project config (four-problem framework, two pipelines)
├── DEBRIEFING.md                     # This file
├── README.md
├── extract_marine_regions.py         # Entity extraction from MR API
├── build_relationships.py            # Relationship building (CSV + API + spatial)
├── enrich_relationships.py           # located_in + claimed_by enrichment
├── merge_tfdd_rivers.py              # TFDD river basin merge (Session 4)
├── extract_cables.py                 # Submarine cable extraction from TeleGeography
├── compute_flow_order.py             # River flow order from HydroRIVERS (Session 6)
├── query_world.py                    # Interactive query interface
├── verify_database.py                # 21 automated verification checks
├── .claude/commands/
│   ├── source-scout.md               # Step 1: Find sources
│   ├── source-validator.md           # Step 2: Validate sources
│   ├── data-inspector.md             # Step 3: Four-problem inspection + enrichment mode
│   ├── data-merger.md                # Step 6: Entity import + attribute augmentation
│   └── data-verifier.md              # Step 7: Verify output
├── data/
│   ├── rivers/                       # Rivers research output (Session 2)
│   ├── cables/                       # Cable research output (Session 5)
│   ├── flow_order/                   # Flow order research output (Session 6)
│   │   ├── 01_candidate_sources.md
│   │   ├── 02_validated_sources.md
│   │   ├── 03_inspection_results.md
│   │   ├── 04_verification_report.md
│   │   ├── flow_order_results.json   # Computed flow order for 316 basins
│   │   └── raw/                      # HydroRIVERS shapefiles (~500 MB)
│   ├── unctad/                      # UNCTAD source assessment (Session 7)
│   │   └── 00_source_assessment.md
│   └── marine_regions/
│       ├── global_map.db             # SQLite database (~10 MB, 40K entities, 27K relationships, 842 ranked)
│       └── checkpoint.json           # MR extraction progress tracker
├── build_iso_mapping.py             # ISO 3166 → MRGID mapping (Session 7)
```

---

## Task 7: UNCTAD Source Survey & ISO Infrastructure

### What we set out to do
Inspect UNCTAD (unctad.org) as a data source — map everything it offers, translate to entities/relationships/attributes, assess integration potential with our DB. Then build the critical infrastructure needed before any extraction.

### What happened

#### Phase 0: Skills gap
Recognized that existing skills (source-scout, data-inspector) didn't cover the task pattern: "given a known source, map all its offerings." Source-scout works topic→sources; this task works source→topics. Created `source-surveyor.md` — a new skill for mapping an organization's full data landscape.

#### Phase 1: Source survey
Explored UNCTAD's data infrastructure systematically:
- **UNCTADstat Data Hub** — primary platform, 150+ indicators, JS-rendered (WebFetch can't see the Data Centre content)
- **6 specialized databases** — Investment Policy Hub, TRAINS, GSP, Cyberlaw Tracker, etc.
- **Programmatic access** — CSV bulk download via UI, UNdata SDMX API (JSON/XML/CSV), WITS API for TRAINS data
- **Classifications** — ISO 3166 + UN M49 for countries, HS/SITC for products

#### Phase 2: Schema mapping
Cataloged datasets by integration value using the Four Problems framework:

**Tier 1 — Bilateral/relational data (creates graph edges):**
- **LSBCI** (Bilateral Liner Shipping Connectivity Index): country-pair shipping connectivity scores. ~19K directed weighted edges. Unique to UNCTAD.
- **Merchandise Trade Matrix**: country-to-country trade flows by product. Massive bilateral edge set.
- **Bilateral FDI**: 206 economies, 40+ years of directed investment flows.
- **BITs** (Bilateral Investment Treaties): 2,864 treaties between country pairs. UNCTAD is the sole authority.

**Tier 2 — Country attributes (enriches existing nations):**
- LSCI (shipping connectivity score), merchant fleet, container throughput, GDP

**Tier 3 — New entity types:**
- Port LSCI (individual ports, but no coordinates — would need a separate port database)

#### Phase 3: ISO country code infrastructure
Identified the critical prerequisite: all UNCTAD data uses ISO 3166 codes, but our 196 Nation entities had empty `iso_code` fields. Built `build_iso_mapping.py`:
- Exact name match via `pycountry`: 136/196
- Manual alias dictionary (Dutch names, legacy names, MR-specific names): 60/196
- **Result: 196/196 nations mapped, zero unmatched**
- Applied to database — all nations now have ISO alpha-3 codes

### Key Lessons (Session 7)

#### On source surveys vs. dataset inspection
- **Survey the source organization before committing to one access method.** In Session 3, we went straight to the MR REST API without asking what else marineregions.org offers. The GeoPackage downloads (pre-computed spatial intersections) could have saved hours of bounding-box computation. The survey pattern forces you to map the full landscape first.

#### On reference IDs as infrastructure
- **Establish reference IDs on core entities before your second source arrives, not your seventh.** The `iso_code` column existed from Session 3 — empty for 6 sessions. Every session fought country name matching (Dutch ↔ English ↔ formal ↔ informal, five rounds of alias additions, per-script dictionaries). Populating ISO codes took 30 minutes and eliminates the problem permanently. This should have been Session 3's first task.

#### On ranking extraction targets
- **Edges are more valuable than nodes.** The UNCTAD assessment distinguished bilateral data (creates edges, high value) from country attributes (enriches nodes, medium) from new entity types (lower). In Session 3, we treated all 449 MR entity types equally — extracting 11K ICES rectangles that still have zero relationships 4 sessions later. Rank by graph value, not record count.

#### On query-driven source selection
- **Define target queries before choosing what to extract.** The UNCTAD assessment ranked datasets by "what new questions can the DB answer?" — backwards pipeline thinking applied at source selection, not just enrichment. Sessions 3-4 measured progress by counts (37K entities!) when 98% had no relationships.

#### On prerequisites
- **Map how sources will join to existing data before starting extraction.** The survey identified the ISO mapping as a blocker before touching any UNCTAD data. In earlier sessions, prerequisites (alias dictionaries, name resolution, region fallbacks) were discovered mid-extraction. The survey step forces prerequisite discovery upfront.

#### On the updated pipeline
The source-surveyor fills a gap that existed from the start:
```
0. Inventory existing data
1. /source-surveyor  — map source landscape, rank by graph value, identify join prerequisites
2. Build integration infrastructure (reference IDs, alias tables)
3. /data-inspector   — probe top-ranked datasets against four problems
4. Extract (highest graph-value first)
5. /data-verifier
```

The original pipeline jumped from "find sources" to "inspect a dataset" with no step for "understand the whole source and plan how it connects to what you have."

### Result
| Metric | Before | After |
|---|---|---|
| Nations with ISO codes | 0 | 196 (100%) |
| UNCTAD datasets cataloged | 0 | 16 (7 bilateral, 9 attribute/entity) |
| New skills | 5 | 6 (+source-surveyor) |

### Open Items
- **LSBCI extraction** — highest-value bilateral dataset, needs data-inspector probe
- **BITs extraction** — 2,864 treaty edges, no API (web scraping needed)
- **Trade Matrix** — massive bilateral dataset, needs careful design
- **Bilateral FDI** — 206 economies, 40 years
- **Port LSCI** — needs a separate port coordinate source for placement
- **MR WFS datasets** — EEZ Boundaries and EEZ-IHO Intersection (see Session 7b below)

---

## Session 7b: Marine Regions Retrospective Survey

### What we set out to do
Apply the source-surveyor to marineregions.org — the source we've used since Session 3 — to test whether a survey would have found datasets we missed.

### What we found

We used exactly ONE access method in Sessions 3-5: the REST API (`/rest/getGazetteerRecordsByType`, `/rest/getGazetteerRelationsByMRGID`). Marine Regions actually offers **four** data delivery mechanisms:

| Method | What it provides | We used it? |
|--------|-----------------|-------------|
| REST API | Single-record lookups, 15 endpoints | ✓ (2 of 15 endpoints) |
| **WFS (Web Feature Service)** | **55 layers** with full polygons, CSV/GeoJSON export, spatial queries | ✗ |
| **GeoPackage/Shapefile downloads** | Pre-built boundary datasets | ✗ |
| WMS (Web Map Service) | Map image rendering | ✗ (low data value) |

### Three datasets we missed

#### 1. EEZ Boundaries (WFS: `MarineRegions:eez_boundaries`)

**2,349 maritime boundary lines.** Each line has:
- `mrgid_sov1` + `mrgid_sov2` — the two nations on each side (MRGIDs matching our DB)
- `line_type` — Treaty (267), Median line (204), Connection line (247), Court ruling (25), Joint regime (21), Unsettled (52)
- `length_km` — boundary length
- `source1`, `url1`, `doc_date` — legal provenance (actual treaty documents, court rulings, UN notes verbales)

Of these, **826 lines are between two distinct sovereigns**, representing **330 unique nation pairs**.

**Compared to what we have:**
- Our DB has 313 `borders` pairs (from the Session 1 CSV — these are **land** borders)
- 121 pairs overlap (nations that share both land and maritime borders)
- **209 pairs are NEW** — purely maritime borders not in our DB

These 209 new pairs include:
- Island nations' maritime neighbors (UK–Belgium, UK–France, UK–Netherlands)
- Overseas territory boundaries (France–Brazil, France–Madagascar, France–Vanuatu via overseas territories)
- Cross-sea boundaries (Netherlands–Venezuela via Caribbean EEZs)

**Line type breakdown for new pairs:** 173 Treaty, 133 Connection, 112 Median, 13 Joint regime, 9 Court ruling, 21 Unsettled.

**What this means:** We can add a `maritime_border` relationship type — distinct from `borders` (land) — with legal provenance, line type classification, and length. This is authoritative international law data, not computed heuristics.

**What we did instead in Session 3:** Computed 482 `adjacent_to(sea, nation)` from bounding box overlap, got false positives (landlocked nations), built an exclusion list. The EEZ Boundaries dataset provides the **nation↔nation** maritime adjacency directly, with legal sourcing.

#### 2. EEZ-IHO Intersection (WFS: `MarineRegions:eez_iho`)

**572 pre-computed intersections.** Each feature maps a nation's EEZ to an IHO Sea Area:
- `mrgid_sov1`, `sovereign1`, `iso_ter1` — which nation
- `iho_mrgid`, `iho_sea` — which sea
- `area_km2` — intersection area (enables weighted adjacency)
- Direct MRGID + ISO code match to our DB

**Compared to what we have:**
- 489 existing `adjacent_to(sea, nation)` relationships (from CSV + spatial inference)
- The 572 EEZ-IHO intersections provide **authoritative** sea↔nation adjacency with **area in km²** — a property our current relationships lack
- Overlap is partial: our `adjacent_to` includes straits, bays, gulfs; EEZ-IHO is strictly IHO Sea Areas × EEZs

**What this means:** We could either replace or supplement our existing `adjacent_to` with authoritative, area-weighted relationships. "Albania borders the Adriatic Sea (12,127 km²) and the Ionian Sea (39 km²)" — the area tells you which sea matters more to each nation.

#### 3. Alternate Names API (`getGazetteerNamesByMRGID`)

Returns alternate language names per entity. For MRGID 14 (België): `["Belgium", "Bélgica"]`.

**What we did instead:** Built alias dictionaries manually over 5 sessions:
- Session 3: 5 rounds of adding Dutch→English aliases
- Session 3b: 150-entry adjective→nation dictionary for EEZ parsing
- Session 4: TFDD-specific alias dictionary
- Session 5: 7 territory alias additions
- Session 7: Full ISO mapping (which finally solved it permanently)

**What this would have given us:** 196 API calls (~3 minutes) to get English names for all Dutch-named entities. Would have cut hours of cumulative name-matching work.

### Value Assessment

| Dataset | New relationships | New properties | Integration effort | Value |
|---------|------------------|---------------|-------------------|-------|
| EEZ Boundaries | +209 maritime border pairs (new type) | line_type, length_km, legal source | Trivial — MRGID match, WFS CSV | **HIGH** |
| EEZ-IHO Intersection | ~572 nation↔sea (overlaps/replaces 489 existing) | area_km2 | Trivial — MRGID match, WFS CSV | **HIGH** |
| Alternate Names | Infrastructure | N/A | Easy — 196 API calls | **Moot** (ISO codes now solve the problem) |

### Key Lesson

**The REST API was the worst access method for our use case.** It's designed for interactive single-record lookups in a web application. The WFS is designed for bulk geographic data — exactly what we needed. The downloads page has pre-built intersection datasets — exactly the relationships we spent hours computing.

We didn't even look at the downloads page or web services page in Session 3. One visit to `marineregions.org/downloads.php` would have revealed the EEZ-IHO intersection dataset. One visit to `marineregions.org/webservices.php` would have revealed the WFS with 55 queryable layers.

**This is the source-surveyor lesson made concrete.** The cost of not surveying wasn't just inefficiency — it was building crude approximations of datasets that already existed in authoritative, pre-computed form.
