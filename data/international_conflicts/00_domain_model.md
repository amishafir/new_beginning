# Domain Model: International Conflicts

## 1. Interaction Map

| # | Interaction | What moves | From → To | Properties |
|---|---|---|---|---|
| 1 | **Claim territory** | Sovereignty assertion | State → Territory/Resource | Claim type (sovereignty, resource, maritime), legal basis, date asserted |
| 2 | **Threaten/Display force** | Coercive signal | State → State | Type (threat, display, use of force), MID hostility level (1-5) |
| 3 | **Wage armed conflict** | Military force | State/Armed group → State/Armed group | Type (interstate, intrastate, non-state, one-sided), intensity, casualties, duration |
| 4 | **Impose sanctions** | Economic/diplomatic restriction | State/Coalition → State | Scope (targeted/comprehensive), type (economic, arms, travel), duration |
| 5 | **Transfer arms** | Weapons systems | State → State | System type, quantity, TIV value, delivery year |
| 6 | **Provide external support** | Military/economic/political aid | State → Conflict party | Support type (troops, weapons, funding, intelligence, sanctuary), direction (pro-government/pro-rebel) |
| 7 | **Mediate** | Facilitation of dialogue | Mediator → Conflict parties | Mediator type (state, IO, individual), mandate, outcome |
| 8 | **Negotiate/Sign agreement** | Binding commitment to peace | State group → Agreement | Scope (ceasefire, peace, framework), signatories, enforcement, date |
| 9 | **Deploy peacekeepers** | Military/police personnel | Intl org → Conflict zone | Troop count, mandate type, contributing countries, budget |
| 10 | **Adjudicate** | Ruling | Court/Tribunal → Parties | Binding/advisory, legal basis, outcome |
| 11 | **Ally** | Security commitment | State → Alliance | Treaty type (defense pact, non-aggression, entente), obligations |
| 12 | **Displace population** | Forced movement | Conflict zone → Host states | Refugee count, IDP count, year |

### Lifecycle

```
Claim → Threaten/Display force → [BRANCH]
  ├─ Peaceful path: Mediate → Negotiate → Sign agreement → Monitor compliance
  ├─ Escalation path: Armed conflict → (External support / Intervention) → Stalemate → Mediate → Ceasefire → Peace agreement → Peacekeepers
  ├─ Frozen conflict: Low-level violence → Indefinite stalemate (never reaches resolution)
  └─ Relapse: Agreement → Compliance failure → Re-escalation → Armed conflict

Parallel throughout:
  - Ally/Align (shapes escalation calculus at every stage)
  - Transfer arms (fuels or constrains conflict capacity)
  - Impose sanctions (coercive tool at any escalation stage)
  - Displace population (consequence at any stage involving violence)
```

**Key lifecycle insight:** Many conflicts are **stuck** — they never reach the resolution stages. Where a conflict sits in the lifecycle tells you what's missing: no mediator? no agreement? no enforcement? no political will? The lifecycle position is itself a diagnostic.

**Relapse is the norm, not the exception.** ~40% of post-conflict states return to violence within a decade. The lifecycle is a cycle, not a line.

## 2. Strategic Decisions

| # | Decision | Who makes it | What they need to know | What's at stake |
|---|---|---|---|---|
| 1 | Whether to intervene in a conflict | National Security Council | Parties, alliances, precedent, force requirements, legal basis | Lives, geopolitical position |
| 2 | Where to deploy peacekeepers and with what mandate | UN Security Council / regional org | Conflict intensity, parties, agreements, past mission outcomes | Mission success, institutional credibility |
| 3 | Which conflicts to prioritize for mediation | Mediation envoy / Intl org | Ripeness, parties' positions, spoilers, regional dynamics | Resolution probability |
| 4 | Whether sanctions will be effective on target state | Foreign ministry / sanctions committee | Target's trade dependencies, alliance network, past sanctions outcomes | Policy tool credibility |
| 5 | Which alliance to join or maintain | Head of state / defense ministry | Threat landscape, alliance obligations, member reliability | National security, sovereignty |
| 6 | How to allocate humanitarian resources | UNHCR / OCHA | Displacement flows, host country capacity, conflict trajectory | Refugee welfare |
| 7 | Whether a conflict risks escalation or regional spillover | Intelligence analyst | Alliances, arms flows, ethnic ties across borders, contiguity | Early warning |
| 8 | Whether to refer a dispute to international court | Foreign ministry / legal advisors | Legal merit, precedent, enforcement likelihood | Sovereignty, precedent |
| 9 | Which frozen conflicts are most likely to reignite | Defense/intelligence planner | Military capability shifts, alliance changes, unresolved claims | Force posture |
| 10 | Whether a peace agreement will hold | Post-conflict planner | Agreement terms, enforcement mechanism, spoiler capacity | Reconstruction investment |

## 3. Entity-Relationship Schema

### 3a. Entity Types (9)

| Entity type | Appears in interactions | Examples | Stability |
|---|---|---|---|
| **State** | 1-12 (all) | Russia, Ukraine, Israel, Ethiopia, USA | Decades |
| **Armed group** | 3, 6, 7, 8 | Houthis, Wagner Group, FARC, Taliban, Hezbollah | Years-decades |
| **Conflict** | 3, 6, 7, 8, 9, 12 | Russia-Ukraine War, Syrian Civil War, Tigray War | Years-decades |
| **Agreement** | 8 | Dayton Accords, Camp David, Minsk II, Good Friday | Decades |
| **Alliance** | 11 | NATO, CSTO, AUKUS, Quad, AU | Decades |
| **Peacekeeping mission** | 9 | UNIFIL, MINUSMA, UNMISS, KFOR | Years-decades |
| **International organization** | 7, 9, 10 | UN, AU, OSCE, EU, ASEAN, Arab League | Decades-permanent |
| **Court/Tribunal** | 10 | ICJ, ICC, ICTY, PCA, ECHR | Permanent |
| **Disputed territory** | 1 | Crimea, Kashmir, Western Sahara, Golan Heights, South China Sea islands | Decades |

Notes:
- **Armed group** is critical — UCDP's core architecture distinguishes state-based, non-state, and one-sided violence. Many modern conflicts involve non-state actors.
- **State** overlaps 100% with existing DB (196 nations with ISO codes).
- **Conflict** is the central node — most relationships pass through it.

### 3b. Relationship Types (14)

| Relationship | From → To | Derived from interaction | Properties |
|---|---|---|---|
| **party_to** | State/Armed group → Conflict | Wage armed conflict | role (side_a/side_b), start_year, end_year, battle_deaths |
| **claims** | State → Disputed territory | Claim territory | legal_basis, date_asserted, recognition_count |
| **allied_with** | State → Alliance | Ally | joined_year, type (defense/non-aggression/entente), role (founding/member/partner) |
| **signed** | State → Agreement | Sign agreement | date_signed, role (signatory/guarantor/witness) |
| **resolves** | Agreement → Conflict | Sign agreement | scope (ceasefire/comprehensive_peace/framework), compliance_status |
| **deployed_to** | Peacekeeping mission → Conflict | Deploy peacekeepers | troop_count, mandate, start_year, end_year, fatalities |
| **mandated_by** | Peacekeeping mission → Intl org | Deploy peacekeepers | resolution_number, date |
| **supports** | State → State/Armed group (in conflict) | External support | support_type (troops/arms/funding/sanctuary), direction (pro-gov/pro-rebel), conflict_id |
| **sanctioned** | State/Coalition → State | Impose sanctions | type (economic/arms/travel/diplomatic), scope, start_year, end_year, legal_basis |
| **arms_transfer** | State → State | Transfer arms | system_type, TIV_value, quantity, year |
| **adjudicated** | Court → Conflict/Dispute | Adjudicate | case_name, year, binding, outcome, legal_basis |
| **displaced_to** | Conflict → State | Displace population | refugee_count, year, source (UNHCR) |
| **member_of** | State → Intl org | (structural) | joined_year, role (member/observer/non-member_state) |
| **contiguous_to** | State → State | (structural, geographic) | type (land/sea), distance_class (COW 1-5) |

### 3c. Four Problems Assessment

| Problem | Difficulty | Why |
|---|---|---|
| **Enumeration** | **Easy** | States in DB (196). Conflicts cataloged by UCDP (1946-present) and COW (1816-present). Alliances in COW. Armed groups in UCDP Actor dataset. Peacekeeping in SIPRI. |
| **Placement** | **Easy** | States already placed. Conflicts have location via UCDP GED (georeferenced events) and COW MIDLOC. Disputed territories need boundaries. |
| **Relationships** | **Moderate** | `party_to` well-documented (UCDP dyadic dataset). `allied_with` in COW alliances. `arms_transfer` in SIPRI. `supports` in UCDP External Support. `sanctioned` scattered across multiple sources. |
| **Properties** | **Moderate-Hard** | Casualty figures contested (UCDP provides best/low/high estimates). Agreement compliance subjective. Sanctions effectiveness debated. TIV values are SIPRI estimates, not actual prices. |
| **Sequence** | **Moderate** | Conflict onset/termination in UCDP. Peace agreements dated. But "current lifecycle stage" requires judgment — no single dataset classifies where a conflict sits today. |

## 4. Personas and Questions

### National Security Advisor (Government)
| # | Question | Data needed | Decision |
|---|---|---|---|
| 1 | What alliance obligations would be triggered if conflict X escalates? | allied_with + alliance properties + party_to | Force commitment decision |
| 2 | Which states are party to the most active conflicts simultaneously? | party_to + conflict status | Threat assessment, overstretched actors |
| 3 | What is the historical outcome when external powers intervene in conflicts like X? | supports + conflict type + outcomes | Intervention decision |
| 4 | Which disputed territories involve nuclear-armed states on opposite sides? | claims + state nuclear status + allied_with | Escalation risk ranking |

### UN Mediation Envoy (International organization)
| # | Question | Data needed | Decision |
|---|---|---|---|
| 1 | Which active conflicts have no mediation and no peace agreement? | Conflict status + signed gaps + mediation gaps | Where to focus effort |
| 2 | What mediation approaches succeeded for conflicts with similar structure? | Conflict properties + mediation history + outcomes | Strategy design |
| 3 | Which active conflicts have the most external parties with leverage? | supports + allied_with + sanctioned + arms_transfer | Who to bring to table |

### Sanctions Policy Analyst (Government / think tank)
| # | Question | Data needed | Decision |
|---|---|---|---|
| 1 | Full sanctions history of target state — who sanctioned, what type, did it work? | sanctioned + outcomes + duration | Sanctions design |
| 2 | How dependent is the target state on trade with the sanctioning coalition? | Trade data + alliance network | Effectiveness prediction |
| 3 | Does the target state have alternative arms suppliers outside the coalition? | arms_transfer network | Sanctions circumvention risk |

### Conflict Early Warning Analyst (Intelligence / ICG-type org)
| # | Question | Data needed | Decision |
|---|---|---|---|
| 1 | Which frozen conflicts have seen recent alliance shifts or arms buildup? | Conflict status + allied_with changes + arms_transfer trends | Early warning priority |
| 2 | Which pairs of contiguous states have unresolved territorial claims AND are in rival alliances? | claims + contiguous_to + allied_with | Spillover risk mapping |
| 3 | Which peace agreements are oldest without compliance monitoring? | resolves + deployed_to gaps + agreement age | Relapse risk ranking |
| 4 | Where do arms transfer networks and active conflict zones overlap? | arms_transfer + party_to + geography | Fueling risk |

### Peacekeeping Mission Planner (UN DPKO / regional org)
| # | Question | Data needed | Decision |
|---|---|---|---|
| 1 | What peacekeeping missions are active, where, with what troop strength? | deployed_to + mandated_by + troop contributors | Resource landscape |
| 2 | Which post-agreement conflicts have NO peacekeeping presence? | resolves + deployed_to gaps | Where missions are needed |
| 3 | Which troop contributors are in the most missions and most overstretched? | deployed_to → contributing countries | Burden-sharing negotiation |

### Humanitarian Coordinator (UNHCR / OCHA)
| # | Question | Data needed | Decision |
|---|---|---|---|
| 1 | Which conflicts produce the most displacement, and to which neighbors? | displaced_to + refugee counts + host state | Resource allocation |
| 2 | Which host states bear disproportionate refugee burden relative to capacity? | displaced_to + state GDP/population | Where to direct aid |
| 3 | Which escalating conflicts are likely to produce NEW displacement? | Conflict trajectory + contiguity + displacement history | Contingency planning |

## 5. Validation Notes

### UCDP — Uppsala Conflict Data Program (data backbone)
- **Confirmed:** State-based, non-state, and one-sided violence typology. Actor dataset with armed groups. Dyadic dataset with conflict pairs. GED with georeferenced events. Peace Agreement dataset. Conflict Termination dataset. External Support dataset.
- **Model update:** Added **Armed group** as entity type — UCDP's architecture requires it. Added **supports** relationship from External Support dataset.
- **Coverage:** 1946-present. ~2,500 actors. Annual releases (v25.1 current).

### SIPRI — Stockholm International Peace Research Institute (arms + peacekeeping)
- **Confirmed:** Arms Transfers Database (since 1950, TIV values). Multilateral Peace Operations Database (since 2000, troop counts, budgets). Military Expenditure Database. Arms Industry top 100.
- **Model update:** Validates `arms_transfer` and `deployed_to` relationships with rich properties.
- **Gap:** Arms embargo data exists but is less structured.

### Correlates of War (historical depth + alliances)
- **Confirmed:** Formal Alliances (1816-2012, defense/non-aggression/entente). MIDs (1816-2014, hostility levels 1-5, with geo locations). War data (4 types). Territorial Change. Direct Contiguity. Trade. Diplomatic Exchange. IGO membership.
- **Model update:** COW's MID hostility levels (1-5) map to `threaten/display force` interaction. Contiguity already in our DB as `borders`. Diplomatic Exchange suggests a `diplomatic_ties` relationship but deprioritized (changes frequently).
- **Gap:** COW data ends 2007-2014 depending on dataset. UCDP is more current.

### ICG — International Crisis Group (qualitative validation)
- **Confirmed:** Monitors 70+ conflicts monthly via CrisisWatch. Covers state-based, non-state, organized crime, climate-related conflicts.
- **Model insight:** ICG categorizes situations as "deteriorated," "improved," or "unchanged" monthly — this is essentially lifecycle stage tracking, but qualitative rather than structured. Validates that lifecycle position is a useful attribute.

## 6. Stakeholder Map

### Tier 1 — Conflict parties
- **States** (196 in DB) — Party to conflicts, alliance members, sanctions senders/targets, arms importers/exporters
- **Armed groups** — FARC, Taliban, Houthis, Wagner, Hezbollah — Party to intrastate/non-state conflicts, receive external support

### Tier 2 — Governance and mediation
- **International organizations** — UN (Security Council, DPKO, UNHCR), AU, EU, OSCE, ASEAN, Arab League — Mandate peacekeeping, mediate, set norms
- **Courts and tribunals** — ICJ, ICC, ICTY, PCA — Adjudicate disputes, prosecute war crimes
- **Alliances** — NATO, CSTO, AUKUS, Quad — Collective defense, deterrence, intervention

### Tier 3 — Enabling infrastructure
- **Data/research institutions** — UCDP (Uppsala), SIPRI, COW (Penn State), ACLED, ICG — Track, measure, analyze conflicts
- **Humanitarian agencies** — UNHCR, ICRC, WFP, MSF — Respond to displacement, casualties
- **Arms industry** — SIPRI Top 100 companies (Lockheed Martin, BAE Systems, Raytheon) — Supply arms that shape conflict capacity

## 7. Data Archetypes

| Archetype | Example questions | Availability | Hardest part |
|---|---|---|---|
| **Who fights whom** | Conflict parties, dyads, coalitions | **Easy** — UCDP dyadic dataset, COW war data | Classifying non-state actors consistently |
| **Who arms whom** | Arms transfer networks, military aid | **Easy-Moderate** — SIPRI arms transfers | Values are estimates (TIV), not actual prices |
| **Who allies with whom** | Alliance networks, defense pacts | **Easy** — COW formal alliances | COW ends 2012; recent alliances (AUKUS, I2U2) need updating |
| **Who sanctions whom** | Sanctions networks, embargo lists | **Moderate** — scattered across UN, US OFAC, EU | No single comprehensive structured database |
| **Who supports whom in conflict** | External support to conflict parties | **Moderate** — UCDP External Support dataset | Support is often covert; dataset captures what's known |
| **Where are the unresolved claims** | Territorial disputes, frozen conflicts | **Moderate** — COW Territorial Change + qualitative sources | "Frozen" status requires judgment call |
| **What agreements govern what conflicts** | Peace agreements, ceasefires, compliance | **Moderate** — UCDP Peace Agreements, PA-X database | Compliance status is subjective and time-varying |
| **Who is displaced where** | Refugee flows, host country burden | **Easy** — UNHCR statistical database | Counts are snapshots; flow data harder than stock |

**Hardest data archetype:** **Who supports whom in conflict** — external support (arms, funding, intelligence, sanctuary) is often covert, denied, or ambiguous. UCDP's External Support dataset is the best structured source but covers only what's publicly known. This is the most guarded data in the domain.

**Second hardest:** **Sanctions effectiveness** — not just who sanctioned whom, but whether it worked. Requires linking sanctions to outcomes, which involves causal judgment.

## 8. Build-vs-Layer Verdict

### 8a. Entity overlap with existing DB

| Entity type | In existing DB? | Notes |
|---|---|---|
| State | **YES** — 196 nations with ISO codes | Direct join on ISO alpha-3 |
| Armed group | **NO** | ~2,500 in UCDP Actor dataset |
| Conflict | **NO** | ~2,000+ in UCDP (1946-present) |
| Agreement | **NO** | ~350 in UCDP Peace Agreements |
| Alliance | **NO** | ~650 in COW Formal Alliances (1816-2012) |
| Peacekeeping mission | **NO** | ~100+ in SIPRI Peace Operations |
| International organization | **NO** | IGO membership in COW |
| Court/Tribunal | **NO** | Small set (~10 major) |
| Disputed territory | **NO** | ~100+ in COW Territorial Change |

**Count:** 1 of 9 entity types exist. 8 are new.

### 8b. Verdict

> **VERDICT: HYBRID.**
>
> One entity type (State) already exists with full coverage and ISO codes — this is the universal join point. But 8 entity types are new to the DB. The core graph (conflicts, armed groups, alliances, agreements) must be built from scratch.
>
> **Routing:** Use the **forward pipeline** for new entity types (Conflict, Armed group, Alliance, Agreement, Peacekeeping mission). Use the **backwards pipeline** for relationships that connect new entities to existing States (party_to, allied_with, sanctioned, arms_transfer, displaced_to).

### 8c. Cross-domain comparison

| Dimension | Existing geographic DB | Water governance layer | International conflicts (new) |
|---|---|---|---|
| Shared entities | Countries (196) | Countries, Rivers | Countries |
| Join key | ISO alpha-3 | ISO alpha-3 + basin name | ISO alpha-3 + COW country codes |
| New entities | — | Treaties, RBOs, Infrastructure | Conflicts, Armed groups, Alliances, Agreements, PKOs |
| Key relationship | borders, flows_through | shares, signed, governs | party_to, allied_with, arms_transfer |
| Analogous patterns | `flows_through(country, river)` | `signed(country, treaty)` | `party_to(state, conflict)`, `allied_with(state, alliance)` |

**Cross-domain links:**
- `borders` (geographic DB) → `contiguous_to` (conflicts) — contiguous states are more likely to fight
- `maritime_border` → territorial disputes at sea (South China Sea, Aegean)
- `flows_through` with rank → water conflict potential (upstream position = leverage)
- Water governance `disputed_by` → subset of broader conflict data
- `eez_overlaps` → maritime disputes over economic zones

### 8d. Minimum new data needed

**What the existing DB can already answer:**
- Which states border each other (contiguity — from `borders`)
- Which states share maritime boundaries (from `maritime_border`)
- Which states share rivers and in what position (from `flows_through` + rank)

**Minimum new data for a functional conflict graph:**

| Priority | New entity type | New relationship type | Source | Records (est.) |
|---|---|---|---|---|
| 1 | Conflict | party_to | UCDP Armed Conflict + Dyadic | ~2,500 conflicts, ~5,000 dyads |
| 2 | Alliance | allied_with | COW Formal Alliances | ~650 alliances, ~3,000 memberships |
| 3 | (none — uses existing States) | arms_transfer | SIPRI Arms Transfers | ~50,000+ transfers |
| 4 | Agreement | signed, resolves | UCDP Peace Agreements | ~350 agreements |
| 5 | Armed group | party_to (non-state) | UCDP Actor Dataset | ~2,500 actors |
| 6 | Peacekeeping mission | deployed_to | SIPRI Peace Operations | ~100+ missions |
| 7 | (none) | sanctioned | UN + regional sanctions lists | ~200+ regimes |
| 8 | Disputed territory | claims | COW Territorial Change | ~800+ claims |

**Phase 1 (graph skeleton):** Conflicts + party_to + Alliances + allied_with → who fights whom, who backs whom
**Phase 2 (enrichment):** Arms transfers + sanctions + external support → what fuels and constrains conflicts
**Phase 3 (resolution layer):** Agreements + peacekeeping + adjudication → what resolves conflicts

## 9. Recommended Next Steps

### Priority 1: UCDP Armed Conflict Dataset + Dyadic Dataset
- **Why first:** Creates the conflict graph skeleton. Every other relationship (support, sanctions, agreements) references a conflict.
- **Pipeline:** Forward — source-scout → source-validator → data-inspector → extract → merge
- **Expected yield:** ~2,500 conflicts, ~5,000 dyads with party_to relationships, battle deaths, start/end years

### Priority 2: COW Formal Alliances Dataset
- **Why second:** Alliances are the structural backbone that explains intervention patterns, deterrence, and escalation. Static data (decades-stable).
- **Pipeline:** Forward — same as above
- **Expected yield:** ~650 alliances, ~3,000 state-alliance memberships with type (defense/non-aggression/entente)

### Priority 3: SIPRI Arms Transfers Database
- **Why third:** Arms transfers are the clearest structural indicator of strategic alignment and conflict enablement. Publicly available, well-structured.
- **Pipeline:** Forward — extract from SIPRI
- **Expected yield:** 50,000+ transfers with TIV values, system types, years

### Priority 4: UCDP Peace Agreements + Termination
- **Why fourth:** Resolution data completes the lifecycle. Which conflicts ended, how, and whether agreements held.
- **Pipeline:** Forward
- **Expected yield:** ~350 agreements, ~2,000 termination records

### Priority 5: UCDP External Support Dataset
- **Why fifth:** Reveals the shadow relationships — who backs whom in conflicts. The hardest-to-get archetype.
- **Pipeline:** Forward
- **Expected yield:** External support flows for state-based conflicts (1975-present)

### Source survey before extraction:
- **UCDP** — survey all datasets before committing to one (lesson from Sessions 3, 7b, 8b)
- **COW** — survey all datasets; some (trade, diplomatic exchange, IGO membership) may be lower priority but easy to extract alongside alliances
- **SIPRI** — survey databases page; peace operations database is easy alongside arms transfers

### Existing DB contributions (no sourcing needed):
- `borders` → contiguity for conflict risk analysis
- `maritime_border` → maritime dispute identification
- `flows_through(country, river, rank)` → water conflict potential
- Country ISO codes → universal join key for all conflict data sources
- COW uses its own country codes but provides ISO mappings
