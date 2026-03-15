# Data Research Project

## Purpose
Build verified, source-backed datasets on any research topic using a disciplined process: inventory → discover → validate → inspect → extract → verify.

## Project Structure
```
.claude/commands/
├── domain-modeler.md     # Map an unfamiliar industry: stakeholders, personas, questions, E-R schema
├── source-scout.md       # Find and classify candidate data sources
├── source-surveyor.md    # Map an organization's full data offerings against our DB
├── source-validator.md   # Validate source authority, currency, and fitness
├── data-inspector.md     # Probe sources against the four problems
├── data-merger.md        # Combine data from multiple sources with entity matching
├── data-verifier.md      # Spot-check results against independent primary sources
data/{topic}/             # Outputs organized by research topic
```

## Workflow

### Domain modeling (entering a new domain)
When starting research in an unfamiliar domain (industry, governance system, competitive ecosystem):
- `/domain-modeler <domain>` — map interactions, lifecycle, decisions, E-R schema, personas, questions
- Output includes a **build-vs-layer verdict**: is this a new database or a layer on existing data?
- **LAYER verdict** → use backwards pipeline (define queries → source only the missing layer)
- **NEW BUILD verdict** → use forward pipeline (scout → validate → inspect → extract → merge)
- Entity types become source-scout search terms, relationship types become inspector test criteria, questions become acceptance criteria for "done"
- Skip this if you already know the entities and relationships you want

### Source survey (mapping an organization's offerings)
When you already know the source but need to discover what it offers:
- `/source-surveyor <url>` — catalog all data products, map to entities/relationships/attributes, rank by integration value
- Then pick the highest-value datasets and run them through the forward or backwards pipeline below

### Forward pipeline (building a new dataset)
0. **Inventory** — check what data already exists in the repo (`ls`, `head`, `wc -l`). Prior sessions may have left curated datasets.
1. `/source-scout <topic>` — find sources, classify as primary/secondary, probe availability
2. `/source-validator` — validate each source: who maintains it, does it have what we need?
2b. **Survey before extracting** — before extracting from any source, run `/source-surveyor` on the organization. This has been skipped 3 times (MR in Session 3, TFDD in Session 2, TFDD again in Session 8) and each time we missed high-value datasets sitting on the same site.
3. `/data-inspector` — probe sources against the four problems (see below), build capability matrix. **If existing data is present**, also test overlap with the new source.
4. **Plan** — design extraction strategy based on what inspector actually found, not assumptions
5. Extract data (method depends on what inspector finds: script, API calls, etc.)
6. `/data-merger` — if combining with existing data: overlap analysis → name resolution → dry run → apply
7. `/data-verifier` — spot-check output against independent primary sources

### Backwards pipeline (enriching an existing dataset)
When you start from a question the DB can't answer yet, work backwards:
1. **Define the query** — write the exact SQL/question the dataset must answer
2. **Model the gap** — what entity, relationship, or attribute is missing? Is it a new relationship type, a new attribute on existing relationships, or new entities entirely?
3. **Assess existing data** — can the gap be filled by computation on data already in the DB? (spatial inference, name parsing, etc.) If yes, skip to extraction.
4. **Source if needed** — only if existing data can't fill the gap: `/source-scout` → `/source-validator` → `/data-inspector` (use enrichment mode — test whether the source has the specific attribute, not the three problems)
5. **Extract & compute** — download source, compute the missing attribute (often involves spatial joins between the new source and existing data)
6. `/data-merger` (attribute augmentation mode) — update existing entities/relationships with the computed attribute
7. `/data-verifier` — spot-check against independent sources

## The Four Problems

Every data project that builds structured/relational output needs to solve up to four problems. A single source rarely handles all of them. **Test each one before committing to a plan.**

| # | Problem | Question | How to test |
|---|---------|----------|-------------|
| 1 | **Enumeration** | "What exists?" | Fetch a list endpoint. Count records. Check fields. |
| 2 | **Placement** | "Where is it?" | Check for coordinates/geometry. If entities have lat/lon and containers have bounding boxes, `located_in` is free. |
| 3 | **Relationships** | "How are things connected?" | Fetch relationships for 5-10 entities. Count per entity. If avg <3, this source can't be your relationship backbone. |
| 4 | **Properties** | "What qualities do the connections have?" | Do relationships have direction, weight, ordering, or capacity? Rivers flow (upstream→downstream). Cables have bandwidth. Trade routes have volume. A relationship without properties is a line without an arrow — structure exists but you can't navigate it. |

Problems 1-3 get you a graph. Problem 4 makes it useful. You often discover Problem 4 only when you try to answer a real query against the data.

For any gap, the inspector should propose how to fill it:
- Missing relationships → curated dataset? spatial computation? name parsing? polygon intersection?
- Missing coordinates → different source? geocoding?
- Missing entities → different source? different endpoint?
- Missing properties → topology dataset? attribute enrichment? computation from existing geometry?

## Principles
- **Primary sources only**: operator websites, intergovernmental bodies, industry databases
- **Never use Wikipedia** as a data source
- **Inventory before scouting**: check what's already in the repo
- **Test before planning**: never write a plan that depends on an untested assumption about a source
- **Validate before fetching**: inspect data structure before building extraction logic
- **Verify after fetching**: spot-check results against independent authoritative sources
- **Be transparent about gaps**: flag what's missing rather than guessing
- **Define done by questions, not counts**: write the queries the dataset must answer, then build until they work

### Default to Layering, Not Building
When entering a new domain, first check whether its core entities already exist in the DB. If countries, rivers, seas, or ports are the backbone, the new domain is probably a governance/commercial/competitive **layer** on existing geographic data — not a separate database. Layers are cheaper to build (backwards pipeline) and immediately benefit from existing relationships.

### The Five Problems
The Four Problems framework (Enumeration, Placement, Relationships, Properties) applies to every dataset. For domains with process/governance structure, add:

| # | Problem | Question | How to test |
|---|---------|----------|-------------|
| 5 | **Sequence** | "In what order do things happen?" | Map the lifecycle. Which interactions are prerequisites for others? Where in the lifecycle are entities created? Where does the process break down? |

Sequence is central in governance (treaty before allocation), commercial (trade before settlement), and competitive (qualification before competition) domains. It reveals which entities are "stuck" at early stages — a basin with no treaty is stuck at step 1 of the water governance lifecycle.

### Curate the Head, Compute the Tail
When deriving relationships from existing data (spatial joins, name parsing, type inference):
- **Curate the top N entities** where errors are visible and costly — use domain knowledge
- **Compute the long tail** where errors are tolerable — use automation
- **Define N before starting** and verify the boundary between curated and computed
- This pattern appears in every session: alias dictionaries + fuzzy matching, strait connections + bbox overlap, river overrides + spatial join

### Spatial Computation Guard Rails
Bounding box overlap is a starting point, not an answer:
- **Always apply an area filter** — exclude overly broad regions (oceans' bboxes cover entire continents)
- **Domain-validate the top N results** — landlocked nations shouldn't border seas, tributaries don't reach oceans, inland coordinates don't map to distant seas
- **Never filter by entity type alone** — sources misclassify entities (Strait of Gibraltar typed as "Sea", seafloor basins typed as "Basin"). Always add name-pattern fallbacks.

### Design for Integration
Most projects end up combining multiple sources. Plan for this from day 1:
- **Add a `source` column** to every table at creation time, not retroactively
- **Use reference IDs** (ISO country codes, standard identifiers) alongside names — matching on IDs is trivial, matching on names is painful
- **Build name normalization as shared infrastructure** — a single alias/lookup system, not per-script dictionaries. Use `data/shared/country_resolver.py` for country code/name resolution across all extraction scripts.
- **Test overlap early** — when inspecting a new source, check how many of its entities already exist in your dataset before building extraction logic

### Always Prefer Structured IDs Over Name Matching
When a data source provides both a code field (GW number, ISO code, COW code) and a name field, **always join on the code**. Never loop through names as a fallback when codes are available. Name matching produces false positives (Session 9: North Korea matched to Ethiopia's conflicts via government actor name iteration). Each source uses a different ID system — map it to ISO alpha-3 once via `data/shared/country_resolver.py`, then join on ISO codes throughout.

### Country Code Systems
Different conflict/governance/trade sources use different country identifiers:
- **ISO 3166 alpha-3** (our DB standard): USA, GBR, FRA
- **Gleditsch-Ward (GW)** (UCDP): numeric, e.g., 2=USA, 200=GBR
- **COW** (Correlates of War): same numbers as GW, different abbreviations
- **SIPRI**: country names with modern variants (Turkiye, Czechia)
- **Historical states**: Yugoslavia→Serbia, USSR→Russia, GDR→Germany

Always identify the source's ID system during source survey and build the mapping table BEFORE extraction.

### Don't Skip Verification
The pipeline ends with `/data-verifier`, not with extraction. Even when extraction runs cleanly, spot-check at least 10 records per source against an independent primary source. Session 9 extracted from 3 sources and skipped verification — casualty figures, alliance dates, and arms transfer values are all contested data.
