"""
Extract UCDP conflict data into global_map.db
Phase 1: Conflicts, Actors, Dyads (party_to relationships)

Sources:
- UCDP/PRIO Armed Conflict Dataset v25.1 (1946-2024)
- UCDP Dyadic Dataset v25.1 (1946-2024)
- UCDP Actor Dataset v25.1

All data CC BY 4.0, downloaded from ucdp.uu.se/downloads/
"""

import csv
import sqlite3
import json
import sys
from pathlib import Path

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.country_resolver import GW_TO_ISO, HISTORICAL_GW, resolve_gwno, get_iso_to_mrgid

DB_PATH = Path(__file__).parent.parent / "marine_regions" / "global_map.db"
ACD_PATH = "/tmp/ucdp_acd/UcdpPrioConflict_v25_1.csv"
DYAD_PATH = "/tmp/ucdp_dyad/Dyadic_v25_1.csv"
ACTOR_PATH = "/tmp/ucdp_actor/Actor_v25_1.csv"

# Alias for backward compatibility within this script
gwno_to_iso = resolve_gwno


def get_next_mrgid(conn):
    """Get the next available mrgid."""
    cur = conn.execute("SELECT MAX(mrgid) FROM entities")
    max_id = cur.fetchone()[0] or 0
    return max_id + 1


def parse_conflicts(path):
    """Parse Armed Conflict dataset into unique conflicts with aggregated properties."""
    conflicts = {}  # conflict_id → dict
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row["conflict_id"]
            year = int(row["year"])

            if cid not in conflicts:
                conflicts[cid] = {
                    "conflict_id": cid,
                    "location": row["location"],
                    "side_a": row["side_a"],
                    "side_b": row["side_b"],
                    "incompatibility": row["incompatibility"],
                    "territory_name": row["territory_name"],
                    "type_of_conflict": row["type_of_conflict"],
                    "start_date": row["start_date"],
                    "min_year": year,
                    "max_year": year,
                    "max_intensity": int(row["intensity_level"]),
                    "gwno_loc": row["gwno_loc"],
                    "region": row["region"],
                }
            else:
                c = conflicts[cid]
                c["min_year"] = min(c["min_year"], year)
                c["max_year"] = max(c["max_year"], year)
                c["max_intensity"] = max(c["max_intensity"], int(row["intensity_level"]))
                # Update side_b if it changes over time (coalitions shift)
                if year > c["max_year"] - 1:
                    c["side_b"] = row["side_b"]
                    c["type_of_conflict"] = row["type_of_conflict"]

    return conflicts


def parse_actors(path):
    """Parse Actor dataset."""
    actors = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            actors[row["ActorId"]] = {
                "actor_id": row["ActorId"],
                "name": row["NameData"],
                "name_orig": row["NameOrig"],
                "is_government": row["NameData"].startswith("Government of"),
                "location": row["Location"],
                "gwno_loc": row["GWNOLoc"],
                "conflict_ids": [c.strip() for c in row["ConflictId"].split(",") if c.strip()],
                "dyad_ids": [d.strip() for d in row["DyadId"].split(",") if d.strip()],
            }
    return actors


def parse_dyads(path):
    """Parse Dyadic dataset into unique dyads with aggregated properties."""
    dyads = {}  # dyad_id → dict
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            did = row["dyad_id"]
            year = int(row["year"])

            if did not in dyads:
                dyads[did] = {
                    "dyad_id": did,
                    "conflict_id": row["conflict_id"],
                    "side_a": row["side_a"],
                    "side_a_id": row["side_a_id"],
                    "side_b": row["side_b"],
                    "side_b_id": row["side_b_id"],
                    "gwno_a_2nd": row.get("gwno_a_2nd", ""),
                    "gwno_b_2nd": row.get("gwno_b_2nd", ""),
                    "type_of_conflict": row["type_of_conflict"],
                    "location": row["location"],
                    "gwno_a": row["gwno_a"],
                    "gwno_b": row["gwno_b"],
                    "gwno_loc": row["gwno_loc"],
                    "min_year": year,
                    "max_year": year,
                    "max_intensity": int(row["intensity_level"]),
                }
            else:
                d = dyads[did]
                d["min_year"] = min(d["min_year"], year)
                d["max_year"] = max(d["max_year"], year)
                d["max_intensity"] = max(d["max_intensity"], int(row["intensity_level"]))
                # Accumulate secondary party GW codes across years
                for field in ("gwno_a_2nd", "gwno_b_2nd"):
                    if row.get(field, ""):
                        existing = set(d[field].split(",")) if d[field] else set()
                        new_codes = set(row[field].split(","))
                        merged = ",".join(sorted(existing | new_codes))
                        d[field] = merged

    return dyads


def main():
    conn = sqlite3.connect(DB_PATH)
    iso_to_mrgid = get_iso_to_mrgid(conn)
    next_id = get_next_mrgid(conn)

    type_map = {"1": "extrasystemic", "2": "interstate", "3": "intrastate", "4": "internationalized_intrastate"}
    incomp_map = {"1": "territory", "2": "government", "3": "both"}
    intensity_map = {1: "minor", 2: "war"}

    # ── Step 1: Parse all source data ──
    print("Parsing conflicts...")
    conflicts = parse_conflicts(ACD_PATH)
    print(f"  {len(conflicts)} unique conflicts")

    print("Parsing actors...")
    actors = parse_actors(ACTOR_PATH)
    gov_actors = {k: v for k, v in actors.items() if v["is_government"]}
    nonstate_actors = {k: v for k, v in actors.items() if not v["is_government"]}
    print(f"  {len(gov_actors)} government actors, {len(nonstate_actors)} non-state actors")

    print("Parsing dyads...")
    dyads = parse_dyads(DYAD_PATH)
    print(f"  {len(dyads)} unique dyads")

    # ── Step 2: Insert conflict entities ──
    print("\nInserting conflicts...")
    conflict_mrgid = {}  # conflict_id → mrgid
    conflict_rows = []

    for cid, c in sorted(conflicts.items(), key=lambda x: x[0]):
        mrgid = next_id
        next_id += 1
        conflict_mrgid[cid] = mrgid

        # Get location coordinates from GW codes
        loc_isos = gwno_to_iso(c["gwno_loc"])
        lat, lon = None, None
        if loc_isos:
            # Use first location country's coordinates as approximate
            for iso in loc_isos:
                if iso in iso_to_mrgid:
                    cur = conn.execute("SELECT latitude, longitude FROM entities WHERE mrgid=?", (iso_to_mrgid[iso],))
                    row = cur.fetchone()
                    if row and row[0]:
                        lat, lon = row
                        break

        # Build name: "Location: Side A vs Side B"
        name = f"{c['location']}: {c['side_a']} vs {c['side_b']}"
        if len(name) > 200:
            name = name[:197] + "..."

        conflict_type = type_map.get(c["type_of_conflict"], c["type_of_conflict"])

        conflict_rows.append((
            mrgid, name, f"Conflict ({conflict_type})", None,
            lat, lon, None, None, None, None,
            "ucdp_acd_v25.1", None, None,
            f"active_{c['min_year']}_{c['max_year']}"
        ))

    conn.executemany(
        "INSERT INTO entities (mrgid, name, type, tier, latitude, longitude, min_lat, min_lon, max_lat, max_lon, source, iso_code, area_km2, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        conflict_rows
    )
    print(f"  Inserted {len(conflict_rows)} conflict entities")

    # ── Step 3: Insert conflict properties as relationships (self-referencing attributes) ──
    print("Inserting conflict properties...")
    prop_rows = []
    for cid, c in conflicts.items():
        mrgid = conflict_mrgid[cid]
        conflict_type = type_map.get(c["type_of_conflict"], c["type_of_conflict"])
        incompatibility = incomp_map.get(c["incompatibility"], c["incompatibility"])

        props = {
            "ucdp_conflict_id": cid,
            "conflict_type": conflict_type,
            "incompatibility": incompatibility,
            "start_date": c["start_date"],
            "start_year": str(c["min_year"]),
            "last_active_year": str(c["max_year"]),
            "max_intensity": intensity_map.get(c["max_intensity"], str(c["max_intensity"])),
            "territory_name": c["territory_name"] if c["territory_name"] else None,
            "region": c["region"],
        }

        for attr_name, attr_value in props.items():
            if attr_value:
                prop_rows.append((mrgid, "has_property", mrgid, None, None, attr_name, attr_value, "ucdp_acd_v25.1"))

    conn.executemany(
        "INSERT INTO relationships (source_mrgid, relationship, target_mrgid, target_name, target_type, attr_name, attr_value, source_data) VALUES (?,?,?,?,?,?,?,?)",
        prop_rows
    )
    print(f"  Inserted {len(prop_rows)} conflict properties")

    # ── Step 4: Insert non-state actor entities ──
    print("\nInserting non-state actors...")
    actor_mrgid = {}  # actor_id → mrgid
    actor_rows = []

    for aid, a in sorted(nonstate_actors.items(), key=lambda x: x[0]):
        mrgid = next_id
        next_id += 1
        actor_mrgid[aid] = mrgid

        # Get coordinates from location
        loc_isos = gwno_to_iso(a["gwno_loc"])
        lat, lon = None, None
        if loc_isos:
            for iso in loc_isos:
                if iso in iso_to_mrgid:
                    cur = conn.execute("SELECT latitude, longitude FROM entities WHERE mrgid=?", (iso_to_mrgid[iso],))
                    row = cur.fetchone()
                    if row and row[0]:
                        lat, lon = row
                        break

        actor_rows.append((
            mrgid, a["name"], "Armed Group", None,
            lat, lon, None, None, None, None,
            "ucdp_actor_v25.1", None, None, None
        ))

    conn.executemany(
        "INSERT INTO entities (mrgid, name, type, tier, latitude, longitude, min_lat, min_lon, max_lat, max_lon, source, iso_code, area_km2, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        actor_rows
    )
    print(f"  Inserted {len(actor_rows)} armed group entities")

    # Store actor properties (ucdp_actor_id, location)
    actor_prop_rows = []
    for aid, a in nonstate_actors.items():
        if aid in actor_mrgid:
            mrgid = actor_mrgid[aid]
            actor_prop_rows.append((mrgid, "has_property", mrgid, None, None, "ucdp_actor_id", aid, "ucdp_actor_v25.1"))
            if a["location"]:
                actor_prop_rows.append((mrgid, "has_property", mrgid, None, None, "location", a["location"], "ucdp_actor_v25.1"))

    conn.executemany(
        "INSERT INTO relationships (source_mrgid, relationship, target_mrgid, target_name, target_type, attr_name, attr_value, source_data) VALUES (?,?,?,?,?,?,?,?)",
        actor_prop_rows
    )
    print(f"  Inserted {len(actor_prop_rows)} actor properties")

    # ── Step 5: Map government actors to existing nations ──
    print("\nMapping government actors to existing nations...")
    gov_actor_mrgid = {}  # actor_id → mrgid (existing nation)
    mapped = 0
    unmapped = []

    for aid, a in gov_actors.items():
        loc_isos = gwno_to_iso(a["gwno_loc"])
        found = False
        for iso in loc_isos:
            if iso in iso_to_mrgid:
                gov_actor_mrgid[aid] = iso_to_mrgid[iso]
                mapped += 1
                found = True
                break
        if not found:
            unmapped.append((aid, a["name"], a["gwno_loc"]))

    print(f"  Mapped {mapped}/{len(gov_actors)} government actors to existing nations")
    if unmapped:
        print(f"  Unmapped: {unmapped[:10]}")

    # ── Step 6: Build party_to relationships from dyads ──
    print("\nBuilding party_to relationships...")
    party_rows = []
    skipped = 0

    for did, d in dyads.items():
        cid = d["conflict_id"]
        if cid not in conflict_mrgid:
            skipped += 1
            continue

        conflict_entity = conflict_mrgid[cid]

        # Side A (usually government)
        side_a_id = d["side_a_id"]
        side_a_mrgid = gov_actor_mrgid.get(side_a_id) or actor_mrgid.get(side_a_id)

        if side_a_mrgid:
            party_rows.append((
                side_a_mrgid, "party_to", conflict_entity, None, None,
                "role", "side_a", "ucdp_dyadic_v25.1"
            ))
            party_rows.append((
                side_a_mrgid, "party_to", conflict_entity, None, None,
                "years", f"{d['min_year']}-{d['max_year']}", "ucdp_dyadic_v25.1"
            ))
            party_rows.append((
                side_a_mrgid, "party_to", conflict_entity, None, None,
                "max_intensity", intensity_map.get(d["max_intensity"], str(d["max_intensity"])), "ucdp_dyadic_v25.1"
            ))
            party_rows.append((
                side_a_mrgid, "party_to", conflict_entity, None, None,
                "ucdp_dyad_id", did, "ucdp_dyadic_v25.1"
            ))

        # Side B
        side_b_id = d["side_b_id"]
        side_b_mrgid = gov_actor_mrgid.get(side_b_id) or actor_mrgid.get(side_b_id)

        if side_b_mrgid:
            party_rows.append((
                side_b_mrgid, "party_to", conflict_entity, None, None,
                "role", "side_b", "ucdp_dyadic_v25.1"
            ))
            party_rows.append((
                side_b_mrgid, "party_to", conflict_entity, None, None,
                "years", f"{d['min_year']}-{d['max_year']}", "ucdp_dyadic_v25.1"
            ))
            party_rows.append((
                side_b_mrgid, "party_to", conflict_entity, None, None,
                "max_intensity", intensity_map.get(d["max_intensity"], str(d["max_intensity"])), "ucdp_dyadic_v25.1"
            ))
            party_rows.append((
                side_b_mrgid, "party_to", conflict_entity, None, None,
                "ucdp_dyad_id", did, "ucdp_dyadic_v25.1"
            ))

        # Secondary parties — use gwno_a_2nd/gwno_b_2nd (GW country codes)
        for gwno_field, role in [(d["gwno_a_2nd"], "side_a_secondary"), (d["gwno_b_2nd"], "side_b_secondary")]:
            if gwno_field:
                sec_isos = gwno_to_iso(gwno_field)
                for iso in sec_isos:
                    if iso in iso_to_mrgid:
                        sec_mrgid = iso_to_mrgid[iso]
                        party_rows.append((
                            sec_mrgid, "party_to", conflict_entity, None, None,
                            "role", role, "ucdp_dyadic_v25.1"
                        ))
                        party_rows.append((
                            sec_mrgid, "party_to", conflict_entity, None, None,
                            "ucdp_dyad_id", did, "ucdp_dyadic_v25.1"
                        ))

    conn.executemany(
        "INSERT INTO relationships (source_mrgid, relationship, target_mrgid, target_name, target_type, attr_name, attr_value, source_data) VALUES (?,?,?,?,?,?,?,?)",
        party_rows
    )
    print(f"  Inserted {len(party_rows)} party_to relationship rows")
    print(f"  Skipped {skipped} dyads (no matching conflict)")

    # ── Step 7: Add located_in relationships (conflict → country) ──
    print("\nBuilding conflict location relationships...")
    loc_rows = []
    for cid, c in conflicts.items():
        if cid not in conflict_mrgid:
            continue
        conflict_entity = conflict_mrgid[cid]
        loc_isos = gwno_to_iso(c["gwno_loc"])
        for iso in loc_isos:
            if iso in iso_to_mrgid:
                loc_rows.append((
                    conflict_entity, "located_in", iso_to_mrgid[iso], None, None,
                    None, None, "ucdp_acd_v25.1"
                ))

    conn.executemany(
        "INSERT INTO relationships (source_mrgid, relationship, target_mrgid, target_name, target_type, attr_name, attr_value, source_data) VALUES (?,?,?,?,?,?,?,?)",
        loc_rows
    )
    print(f"  Inserted {len(loc_rows)} conflict-location relationships")

    conn.commit()

    # ── Summary ──
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)

    cur = conn.execute("SELECT type, COUNT(*) FROM entities WHERE source LIKE 'ucdp%' GROUP BY type")
    print("\nNew entities by type:")
    total_entities = 0
    for row in cur:
        print(f"  {row[0]}: {row[1]}")
        total_entities += row[1]
    print(f"  TOTAL: {total_entities}")

    cur = conn.execute("SELECT relationship, COUNT(*) FROM relationships WHERE source_data LIKE 'ucdp%' GROUP BY relationship")
    print("\nNew relationships by type:")
    total_rels = 0
    for row in cur:
        print(f"  {row[0]}: {row[1]}")
        total_rels += row[1]
    print(f"  TOTAL: {total_rels}")

    cur = conn.execute("SELECT COUNT(*) FROM entities")
    print(f"\nTotal entities in DB: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM relationships")
    print(f"Total relationships in DB: {cur.fetchone()[0]}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
