"""
Extract COW Formal Alliances v4.1 into global_map.db
Creates Alliance entities and allied_with relationships to existing Nations.

Source: Correlates of War, Formal Alliances dataset v4.1 (1816-2012)
Downloaded from correlatesofwar.org
"""

import csv
import sqlite3
import sys
from pathlib import Path

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.country_resolver import GW_TO_ISO as COW_TO_ISO, get_iso_to_mrgid

DB_PATH = Path(__file__).parent.parent / "marine_regions" / "global_map.db"
MEMBER_PATH = "/tmp/cow_alliances/version4.1_csv/alliance_v4.1_by_member.csv"

# Alliance type codes
TYPE_MAP = {
    "Type I: Defense Pact": "defense_pact",
    "Type IIa: Non-Aggression Pact": "non_aggression",
    "Type IIb: Non-Aggression Pact": "non_aggression",
    "Type II: Neutrality": "neutrality",
    "Type III: Entente": "entente",
}

# Known alliance names for major alliances (COW doesn't name them)
KNOWN_ALLIANCE_NAMES = {
    "210": "Inter-American Treaty of Reciprocal Assistance (Rio Pact)",
    "199": "Arab League Collective Defence",
    "230": "Arab League Collective Defence (renewed)",
    "165": "Organization of American States",
    # We'll name the rest generically
}


def get_next_mrgid(conn):
    cur = conn.execute("SELECT MAX(mrgid) FROM entities")
    return (cur.fetchone()[0] or 0) + 1


def main():
    conn = sqlite3.connect(DB_PATH)
    iso_to_mrgid = get_iso_to_mrgid(conn)
    next_id = get_next_mrgid(conn)

    # ── Step 1: Parse alliances from member file ──
    print("Parsing alliances...")
    alliances = {}
    with open(MEMBER_PATH) as f:
        reader = csv.DictReader(f)
        for row in reader:
            aid = row["version4id"]
            ccode = int(row["ccode"])
            iso = COW_TO_ISO.get(ccode)

            if aid not in alliances:
                # Build end year string
                end_year = row["all_end_year"] if row["all_end_year"] else None
                right_censor = row["right_censor"] == "1"

                alliances[aid] = {
                    "id": aid,
                    "type": TYPE_MAP.get(row["ss_type"], row["ss_type"]),
                    "type_full": row["ss_type"],
                    "start_year": row["all_st_year"],
                    "end_year": end_year,
                    "active": right_censor,  # still active at 2012
                    "defense": row["defense"] == "1",
                    "neutrality": row["neutrality"] == "1",
                    "nonaggression": row["nonaggression"] == "1",
                    "entente": row["entente"] == "1",
                    "members": [],
                }

            if iso:
                alliances[aid]["members"].append({
                    "ccode": ccode,
                    "iso": iso,
                    "name": row["state_name"],
                    "joined_year": row["mem_st_year"],
                    "left_year": row["mem_end_year"] if row["mem_end_year"] else None,
                })

    print(f"  {len(alliances)} alliances parsed")
    active = sum(1 for a in alliances.values() if a["active"])
    print(f"  {active} active at dataset end (2012)")

    # ── Step 2: Insert alliance entities ──
    print("\nInserting alliance entities...")
    alliance_mrgid = {}
    entity_rows = []

    for aid, a in sorted(alliances.items(), key=lambda x: int(x[0])):
        mrgid = next_id
        next_id += 1
        alliance_mrgid[aid] = mrgid

        # Build name
        if aid in KNOWN_ALLIANCE_NAMES:
            name = KNOWN_ALLIANCE_NAMES[aid]
        else:
            member_names = [m["name"] for m in a["members"][:4]]
            if len(a["members"]) > 4:
                name = f"{a['type_full']}: {', '.join(member_names)} +{len(a['members'])-4} more"
            else:
                name = f"{a['type_full']}: {', '.join(member_names)}"
        if len(name) > 200:
            name = name[:197] + "..."

        status = "active" if a["active"] else f"ended_{a['end_year']}"

        entity_rows.append((
            mrgid, name, "Alliance", None,
            None, None, None, None, None, None,
            "cow_alliances_v4.1", None, None, status
        ))

    conn.executemany(
        "INSERT INTO entities (mrgid, name, type, tier, latitude, longitude, min_lat, min_lon, max_lat, max_lon, source, iso_code, area_km2, status) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        entity_rows
    )
    print(f"  Inserted {len(entity_rows)} alliance entities")

    # ── Step 3: Insert alliance properties ──
    print("Inserting alliance properties...")
    prop_rows = []
    for aid, a in alliances.items():
        mrgid = alliance_mrgid[aid]
        props = {
            "cow_alliance_id": aid,
            "alliance_type": a["type"],
            "start_year": a["start_year"],
            "member_count": str(len(a["members"])),
        }
        if a["end_year"]:
            props["end_year"] = a["end_year"]
        if a["defense"]:
            props["has_defense_pact"] = "true"
        if a["nonaggression"]:
            props["has_nonaggression"] = "true"
        if a["entente"]:
            props["has_entente"] = "true"

        for attr_name, attr_value in props.items():
            prop_rows.append((mrgid, "has_property", mrgid, None, None, attr_name, attr_value, "cow_alliances_v4.1"))

    conn.executemany(
        "INSERT INTO relationships (source_mrgid, relationship, target_mrgid, target_name, target_type, attr_name, attr_value, source_data) VALUES (?,?,?,?,?,?,?,?)",
        prop_rows
    )
    print(f"  Inserted {len(prop_rows)} alliance properties")

    # ── Step 4: Insert allied_with relationships (State → Alliance) ──
    print("\nBuilding allied_with relationships...")
    rel_rows = []
    matched = 0
    unmatched_isos = set()

    for aid, a in alliances.items():
        if aid not in alliance_mrgid:
            continue
        alliance_entity = alliance_mrgid[aid]

        for member in a["members"]:
            iso = member["iso"]
            if iso in iso_to_mrgid:
                state_mrgid = iso_to_mrgid[iso]
                rel_rows.append((
                    state_mrgid, "allied_with", alliance_entity, None, None,
                    "joined_year", member["joined_year"], "cow_alliances_v4.1"
                ))
                if member["left_year"]:
                    rel_rows.append((
                        state_mrgid, "allied_with", alliance_entity, None, None,
                        "left_year", member["left_year"], "cow_alliances_v4.1"
                    ))
                rel_rows.append((
                    state_mrgid, "allied_with", alliance_entity, None, None,
                    "cow_ccode", str(member["ccode"]), "cow_alliances_v4.1"
                ))
                matched += 1
            else:
                unmatched_isos.add(iso)

    conn.executemany(
        "INSERT INTO relationships (source_mrgid, relationship, target_mrgid, target_name, target_type, attr_name, attr_value, source_data) VALUES (?,?,?,?,?,?,?,?)",
        rel_rows
    )
    print(f"  Inserted {len(rel_rows)} allied_with relationship rows")
    print(f"  Matched {matched} member-alliance links")
    if unmatched_isos:
        print(f"  Unmatched ISO codes (no nation in DB): {sorted(unmatched_isos)}")

    conn.commit()

    # ── Summary ──
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)

    cur = conn.execute("SELECT type, COUNT(*) FROM entities WHERE source='cow_alliances_v4.1' GROUP BY type")
    print("\nNew entities:")
    for row in cur:
        print(f"  {row[0]}: {row[1]}")

    cur = conn.execute("SELECT relationship, COUNT(*) FROM relationships WHERE source_data='cow_alliances_v4.1' GROUP BY relationship")
    print("\nNew relationships:")
    for row in cur:
        print(f"  {row[0]}: {row[1]}")

    # Example: most allied nations
    cur = conn.execute("""
        SELECT e.name, e.iso_code, COUNT(DISTINCT r.target_mrgid) as alliance_count
        FROM entities e
        JOIN relationships r ON e.mrgid = r.source_mrgid
        WHERE r.relationship='allied_with' AND e.type='Nation'
        GROUP BY e.mrgid
        ORDER BY alliance_count DESC
        LIMIT 10
    """)
    print("\nMost allied nations:")
    for row in cur:
        print(f"  {row[0]} ({row[1]}): {row[2]} alliances")

    cur = conn.execute("SELECT COUNT(*) FROM entities")
    print(f"\nTotal entities in DB: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM relationships")
    print(f"Total relationships in DB: {cur.fetchone()[0]}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
