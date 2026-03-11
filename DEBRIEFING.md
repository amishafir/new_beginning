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

## Open Items
- Cable table was never rebuilt from TeleGeography API — still based on Wikipedia/secondary sources
- Rivers table has known Suriname gap in Amazon basin (TFDD source limitation)
- Rivers table contains 10 entries that are disputed territories / non-sovereign entities, not recognized countries — needs a decision on how to handle them
- No extraction scripts were saved — Python code was run inline during the session and lost. If re-extraction is needed, the code must be rewritten.
- Slash commands were never tested as actual `/command` invocations in a fresh session
