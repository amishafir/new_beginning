# Data Research Project

## Purpose
Build verified, source-backed datasets on any research topic using a disciplined process: discover → validate → inspect → extract → verify.

## Project Structure
```
.claude/commands/
├── source-scout.md       # Find and classify candidate data sources
├── source-validator.md   # Validate source authority, currency, and fitness
├── data-inspector.md     # Download/probe actual data, check fields and structure
├── data-verifier.md      # Spot-check results against independent primary sources
data/{topic}/             # Outputs organized by research topic
```

## Workflow
1. `/source-scout <topic>` — find sources, classify as primary/secondary, probe availability
2. `/source-validator` — validate each source: who maintains it, does it have what we need?
3. `/data-inspector` — download/fetch sample data, check actual fields vs requirements
4. Extract data (method depends on what inspector finds: script, API calls, etc.)
5. `/data-verifier` — spot-check output against independent primary sources

## Principles
- **Primary sources only**: operator websites, intergovernmental bodies, industry databases
- **Never use Wikipedia** as a data source
- **Validate before fetching**: always inspect data structure before building extraction logic
- **Verify after fetching**: spot-check results against independent authoritative sources
- **Be transparent about gaps**: flag what's missing rather than guessing
