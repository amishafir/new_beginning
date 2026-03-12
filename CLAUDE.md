# Data Research Project

## Purpose
Build verified, source-backed datasets on any research topic using a disciplined process: inventory → discover → validate → inspect → extract → verify.

## Project Structure
```
.claude/commands/
├── source-scout.md       # Find and classify candidate data sources
├── source-validator.md   # Validate source authority, currency, and fitness
├── data-inspector.md     # Probe sources against the three problems
├── data-merger.md        # Combine data from multiple sources with entity matching
├── data-verifier.md      # Spot-check results against independent primary sources
data/{topic}/             # Outputs organized by research topic
```

## Workflow
0. **Inventory** — check what data already exists in the repo (`ls`, `head`, `wc -l`). Prior sessions may have left curated datasets.
1. `/source-scout <topic>` — find sources, classify as primary/secondary, probe availability
2. `/source-validator` — validate each source: who maintains it, does it have what we need?
3. `/data-inspector` — probe sources against the three problems (see below), build capability matrix. **If existing data is present**, also test overlap with the new source.
4. **Plan** — design extraction strategy based on what inspector actually found, not assumptions
5. Extract data (method depends on what inspector finds: script, API calls, etc.)
6. `/data-merger` — if combining with existing data: overlap analysis → name resolution → dry run → apply
7. `/data-verifier` — spot-check output against independent primary sources

## The Three Problems

Every data project that builds structured/relational output needs to solve three problems. A single source rarely handles all three. **Test each one before committing to a plan.**

| # | Problem | Question | How to test |
|---|---------|----------|-------------|
| 1 | **Enumeration** | "What exists?" | Fetch a list endpoint. Count records. Check fields. |
| 2 | **Placement** | "Where is it?" | Check for coordinates/geometry. If entities have lat/lon and containers have bounding boxes, `located_in` is free. |
| 3 | **Relationships** | "How are things connected?" | Fetch relationships for 5-10 entities. Count per entity. If avg <3, this source can't be your relationship backbone. |

For any gap, the inspector should propose how to fill it:
- Missing relationships → curated dataset? spatial computation? name parsing? polygon intersection?
- Missing coordinates → different source? geocoding?
- Missing entities → different source? different endpoint?

## Principles
- **Primary sources only**: operator websites, intergovernmental bodies, industry databases
- **Never use Wikipedia** as a data source
- **Inventory before scouting**: check what's already in the repo
- **Test before planning**: never write a plan that depends on an untested assumption about a source
- **Validate before fetching**: inspect data structure before building extraction logic
- **Verify after fetching**: spot-check results against independent authoritative sources
- **Be transparent about gaps**: flag what's missing rather than guessing
- **Define done by questions, not counts**: write the queries the dataset must answer, then build until they work

### Design for Integration
Most projects end up combining multiple sources. Plan for this from day 1:
- **Add a `source` column** to every table at creation time, not retroactively
- **Use reference IDs** (ISO country codes, standard identifiers) alongside names — matching on IDs is trivial, matching on names is painful
- **Build name normalization as shared infrastructure** — a single alias/lookup system, not per-script dictionaries
- **Test overlap early** — when inspecting a new source, check how many of its entities already exist in your dataset before building extraction logic
