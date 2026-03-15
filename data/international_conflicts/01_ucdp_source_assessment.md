# Source Assessment: UCDP (Uppsala Conflict Data Program)

**URL:** https://ucdp.uu.se
**License:** CC BY 4.0
**Last surveyed:** 2026-03-15

## 1. Data Infrastructure

| Mechanism | URL | Format | Access | Scope |
|---|---|---|---|---|
| **Bulk downloads** | ucdp.uu.se/downloads/ | CSV, Excel, R, Stata | Open (no registration) | All datasets |
| **REST API** | ucdpapi.pcr.uu.se/api/ | JSON | **Requires access token** (email request) | GED events, conflicts, dyads, non-state, one-sided, battle deaths |
| **Encyclopedia** | ucdp.uu.se/encyclopedia | HTML (JS-rendered) | Open | Browse conflicts, actors interactively |

**Recommendation:** Use bulk CSV downloads. API requires token and has 5K/day rate limit. CSV downloads are immediate, open, and contain the same data.

## 2. Dataset Catalog

### Tier 1 — Core (highest graph value for our project)

| Dataset | Version | Coverage | Records | Entity types | Granularity | Format |
|---|---|---|---|---|---|---|
| **UCDP/PRIO Armed Conflict** | v25.1 | 1946-2024 | 2,753 rows, **303 unique conflicts** | Conflicts | Conflict-year | CSV |
| **Dyadic Dataset** | v25.1 | 1946-2024 | 3,433 rows, **684 unique dyads** | Dyads (opposing pairs) | Dyad-year | CSV |
| **Actor Dataset** | v25.1 | All actors | **1,878 actors** (164 gov, 1,714 non-state) | Actors (states + armed groups) | Actor | CSV |
| **Peace Agreements** | v22.1 | 1975-2021 | **374 agreements** | Agreements | Agreement | Excel |
| **Conflict Termination** | v4-2024 | 1975-2024 | 2,752 rows | Conflict episodes | Episode | CSV |
| **External Support (ESD)** | v18.1 | 1975-2017 | **10,852 triad-years**, 354 supporters | Support triads | Triad-year | Excel |

### Tier 2 — Supplementary

| Dataset | Version | Coverage | Records | Value for us |
|---|---|---|---|---|
| **GED (Georeferenced Events)** | v25.1 | 1989-2024 | ~300K+ events | Low priority — too granular for graph, but useful for placement |
| **One-sided Violence** | v25.1 | 1989-2024 | Subset | Civilian targeting — properties on conflict |
| **Non-State Conflict** | v25.1 | 1989-2024 | Subset | Conflicts with no government party |
| **Battle-Related Deaths** | v25.1 | 1989-2023 | Dyad-year | Casualty properties (best/low/high estimates) |
| **Conflict Issues** | v23.2 | 1989-2017 | Dyad-issue-year | Rebel group stated goals — properties on party_to |
| **Candidate Events** | v26.0.X | Monthly | Monthly release | Near-real-time events — out of scope (too operational) |

### Tier 3 — Specialized / Narrow

| Dataset | Coverage | Notes |
|---|---|---|
| Country-Year Organized Violence | 1989+ | Aggregation of GED — less useful than conflict-level |
| Onset Dataset | 1946-2024 | Derived — conflict start indicators |
| CACE (Cities) | 1989-2017 | Urban vs rural coding |
| DECO (Electoral) | 1989-2017 | Electoral violence subset |
| EOSV (Ethnic) | 1989-2013 | Ethnic targeting subset |
| MIC/MILC (Mediation) | 1993-2007 | Third-party interventions (Africa only) |
| PAR (Peacekeepers at Risk) | 1989-2009 | Peacekeeper casualties (Africa only) |
| External Support in Non-State | 1989-2011 | Africa-only non-state support |

## 3. Schema Mapping

### 3a. Four Problems Assessment

| Dataset | Enumeration | Placement | Relationships | Properties |
|---|---|---|---|---|
| **Armed Conflict** | 303 conflicts with IDs, names, types, dates | Country location (GW codes) | Side A vs Side B per conflict | Intensity, incompatibility, type, dates |
| **Dyadic** | 684 dyads linking actors to conflicts | Same as ACD | **Core relationship source** — who fights whom | Same + dyad-level |
| **Actor** | 1,878 actors with IDs, names, aliases | Location by country | Links to conflicts and dyads via IDs | Gov vs non-state, alliances, splinters |
| **Peace Agreements** | 374 agreements | Linked to conflict/dyad | **Resolves** conflicts, **signed by** actors | 67 columns: ceasefire, DDR, elections, amnesty, justice, gender, PKO, autonomy, territory provisions |
| **Termination** | ~300 conflict episodes | Via conflict ID | Episode → conflict | How it ended (outcome codes), duration |
| **External Support** | 354 supporters | Via GW codes | **Supports** — who backs whom in which conflict | 12 support type flags (troops, weapons, funding, intel, sanctuary, etc.) |

### 3b. DB Integration Mapping

#### New entity types from UCDP

| Entity type | Source dataset | Count | Join to existing DB |
|---|---|---|---|
| **Conflict** | Armed Conflict | 303 | Location → GW country codes → ISO codes via mapping |
| **Armed group** | Actor (non-state) | 1,714 | Location by country → GW → ISO |
| **Agreement** | Peace Agreements | 374 | Linked to conflict_id |

Note: Government actors (164) map to existing States — not new entities.

#### New relationship types from UCDP

| Relationship | From → To | Source dataset | Est. records | Properties |
|---|---|---|---|---|
| **party_to** | State/Armed group → Conflict | Dyadic | ~3,400 dyad-years (684 unique) | role (side_a/side_b), year, intensity |
| **resolves** | Agreement → Conflict | Peace Agreements | 374 | scope (67 provision columns), date, outcome |
| **signed** | State/Armed group → Agreement | Peace Agreements (pa_sign field) | ~1,000+ | date, signatory role |
| **supports** | External state → Conflict party | External Support | 10,852 triad-years | 12 support type flags, alleged flag |
| **terminated_by** | Conflict → Outcome | Termination | ~300 episodes | outcome type, duration, end date |

#### Attributes on existing entities (States)

| Attribute | Source | Value |
|---|---|---|
| GW country code | All datasets (gwno_a, gwno_loc) | 121 unique state codes in ACD |
| Conflict involvement count | Derived from party_to | Per-state count of conflicts |
| External support given/received | ESD | Per-state support profile |

#### Join method

**GW (Gleditsch-Ward) country codes → ISO 3166 alpha-3:**
- UCDP uses GW country codes (numeric). Our DB uses ISO alpha-3.
- A GW→ISO mapping table exists (publicly available from COW). ~215 GW codes map to ~196 ISO codes.
- Some GW codes map to historical states (Yugoslavia, USSR, South Vietnam) — need handling.
- **Integration ease: HIGH** — straightforward lookup table.

### 3c. Query Potential

**From Armed Conflict + Dyadic:**
- "Which countries have been party to the most armed conflicts since 1946?"
- "Which conflicts are currently active (2024) and who are the parties?"
- "Which dyads have the longest continuous conflict?"

**From Peace Agreements:**
- "Which active conflicts have NO peace agreement?"
- "Which agreements include DDR provisions? Elections? Autonomy?"
- "What is the success rate of agreements with vs without PKO provisions?"

**From External Support:**
- "Which states provide the most external support to conflict parties?"
- "Which conflicts receive external support from both sides (proxy wars)?"
- "What types of support (troops vs weapons vs funding) are most common?"

**Cross-dataset:**
- "For conflicts that terminated, which had prior peace agreements and which didn't?"
- "Which non-state actors receive external support from the most states?"
- "Which conflicts have agreements but still received external support after signing?"

## 4. Value Ranking

| Dataset | Integration ease | Uniqueness | Graph value | Query potential | Priority |
|---|---|---|---|---|---|
| **Dyadic** | HIGH (GW→ISO) | Only structured dyadic conflict data | **HIGH** — creates party_to edges | Core conflict graph | **1** |
| **Armed Conflict** | HIGH | Definitive conflict list since 1946 | **HIGH** — creates conflict nodes | Foundation for all queries | **1** |
| **Actor** | HIGH | Comprehensive actor registry with IDs | **HIGH** — creates armed group nodes | Actor identification | **1** |
| **External Support** | HIGH | Only structured external support data | **HIGH** — creates supports edges (who backs whom) | Proxy war analysis | **2** |
| **Peace Agreements** | MEDIUM (Excel, 67 cols) | Rich provision coding | **HIGH** — creates agreement nodes + resolves/signed edges | Resolution analysis | **2** |
| **Termination** | HIGH (CSV) | Conflict lifecycle endpoints | **MEDIUM** — properties on conflicts | Lifecycle analysis | **3** |
| **Battle-Related Deaths** | HIGH | Best/low/high casualty estimates | **LOW** — attributes on dyads | Severity analysis | **3** |
| **Conflict Issues** | MEDIUM | Rebel group goals | **LOW** — attributes on dyads | Motivation analysis | **4** |
| **GED Events** | LOW (300K+ rows) | Village-level geo events | **LOW** — too granular | Event-level queries | **5** |

## 5. Gaps — What UCDP Does NOT Cover

| Gap | What's missing | Alternative source |
|---|---|---|
| **Alliances** | No formal alliance data | COW Formal Alliances |
| **Arms transfers** | No who-sells-what-to-whom | SIPRI Arms Transfers DB |
| **Sanctions** | No sanctions data | GSDB (Global Sanctions DB), UN sanctions committees |
| **Territorial claims** | No disputed territory registry | COW Territorial Change, Issue Correlates of War (ICOW) |
| **Peacekeeping missions** | Only PAR (Africa, peacekeepers at risk) | SIPRI Multilateral Peace Operations |
| **ICJ/tribunal cases** | No adjudication data | ICJ website, PCA case registry |
| **Refugee flows** | No displacement data | UNHCR statistical database |
| **Post-2017 external support** | ESD stops at 2017 | No structured alternative |
| **Post-2021 peace agreements** | PA dataset stops at 2021 | Manual updating needed |

## 6. Recommended Next Steps

### Phase 1: Extract conflict graph skeleton (this session)
1. **Extract conflicts** from Armed Conflict dataset → new Conflict entities (303)
2. **Extract actors** from Actor dataset → new Armed group entities (~1,714) + map government actors to existing States
3. **Extract dyads** from Dyadic dataset → party_to relationships (~684 unique)
4. **Build GW→ISO mapping** to join UCDP states to existing DB

### Phase 2: Enrich with resolution and support
5. **Extract agreements** from Peace Agreements → Agreement entities + resolves/signed relationships
6. **Extract external support** from ESD → supports relationships (who backs whom)
7. **Extract termination** → lifecycle properties on conflicts

### Phase 3: Fill gaps from other sources
8. **COW Formal Alliances** → Alliance entities + allied_with relationships
9. **SIPRI Arms Transfers** → arms_transfer relationships
10. **SIPRI Peace Operations** → Peacekeeping mission entities + deployed_to relationships

## Key Identifiers

| ID type | Used in | Example | Mapping to our DB |
|---|---|---|---|
| conflict_id | All datasets | 11342 | New — becomes entity ID |
| dyad_id | Dyadic, ESD, PA | 10006 | Internal link |
| actor_id (ActorId) | Actor, Dyadic | 141 (India gov) | Gov actors → ISO code; non-state → new entity |
| gwno | All datasets | 750 (India) | → ISO alpha-3 via mapping table |
| paid | Peace Agreements | 1-374 | New — becomes entity ID |

## UCDP Classification Codes

| Field | Values |
|---|---|
| type_of_conflict | 1=extrasystemic, 2=interstate, 3=intrastate, 4=internationalized intrastate |
| incompatibility | 1=territory, 2=government, 3=both |
| intensity_level | 1=minor (25-999 deaths/yr), 2=war (1000+ deaths/yr) |
| termination outcome | 1=peace agreement, 2=ceasefire, 3=victory, 4=low activity, 5=other |
