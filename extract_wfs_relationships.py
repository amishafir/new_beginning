#!/usr/bin/env python3
"""
Extract relationships from Marine Regions WFS layers:
1. EEZ Boundaries -> maritime_border(nation, nation) with line_type, length_km, legal source
2. EEZ-IHO Intersection -> eez_overlaps(nation, sea) with area_km2

These datasets were identified by the source-surveyor (Session 7b) as pre-computed
relationship data we missed in Session 3.

Usage:
    python3 extract_wfs_relationships.py              # dry run
    python3 extract_wfs_relationships.py --apply       # write to DB
"""

import csv
import sqlite3
import sys

DB_PATH = "data/marine_regions/global_map.db"
EEZ_BOUNDARIES_CSV = "/tmp/eez_boundaries.csv"
EEZ_IHO_CSV = "/tmp/eez_iho.csv"


def load_db_entities(conn):
    """Load all entity MRGIDs for validation."""
    rows = conn.execute("SELECT mrgid, name, type FROM entities").fetchall()
    return {r[0]: (r[1], r[2]) for r in rows}


def load_existing_relationships(conn):
    """Load existing relationships to avoid duplicates."""
    rows = conn.execute(
        "SELECT source_mrgid, relationship, target_mrgid FROM relationships"
    ).fetchall()
    return set((r[0], r[1], r[2]) for r in rows)


def extract_maritime_borders(entities, existing_rels):
    """Extract maritime_border relationships from EEZ Boundaries."""
    new_rels = []
    skipped_missing = 0
    skipped_self = 0
    skipped_empty = 0
    skipped_duplicate = 0

    with open(EEZ_BOUNDARIES_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            sov1 = row.get("mrgid_sov1", "").strip()
            sov2 = row.get("mrgid_sov2", "").strip()

            # Skip empty or self-references
            if not sov1 or not sov2:
                skipped_empty += 1
                continue
            try:
                sov1 = int(sov1)
                sov2 = int(sov2)
            except ValueError:
                skipped_empty += 1
                continue

            if sov1 == 0 or sov2 == 0:
                skipped_empty += 1
                continue
            if sov1 == sov2:
                skipped_self += 1
                continue

            # Check both nations exist in DB
            if sov1 not in entities or sov2 not in entities:
                skipped_missing += 1
                continue

            # Check not already in DB (either direction)
            if (sov1, "maritime_border", sov2) in existing_rels or \
               (sov2, "maritime_border", sov1) in existing_rels:
                skipped_duplicate += 1
                continue

            line_type = row.get("line_type", "").strip()
            length_km = row.get("length_km", "").strip()
            source1 = row.get("source1", "").strip()
            doc_date = row.get("doc_date", "").strip()

            # Create relationship in both directions
            target_name_2 = entities[sov2][0]
            target_type_2 = entities[sov2][1]
            target_name_1 = entities[sov1][0]
            target_type_1 = entities[sov1][1]

            new_rels.append({
                "source_mrgid": sov1,
                "relationship": "maritime_border",
                "target_mrgid": sov2,
                "target_name": target_name_2,
                "target_type": target_type_2,
                "attr_name": "line_type",
                "attr_value": line_type,
                "source_data": "mr_wfs_eez_boundaries",
            })
            # Store length as a second relationship entry
            if length_km:
                new_rels.append({
                    "source_mrgid": sov1,
                    "relationship": "maritime_border",
                    "target_mrgid": sov2,
                    "target_name": target_name_2,
                    "target_type": target_type_2,
                    "attr_name": "length_km",
                    "attr_value": length_km,
                    "source_data": "mr_wfs_eez_boundaries",
                })

            # Mark as seen to deduplicate within this dataset
            existing_rels.add((sov1, "maritime_border", sov2))

    print(f"Maritime Borders:")
    print(f"  New relationships: {len(new_rels)}")
    print(f"  Skipped (empty/invalid): {skipped_empty}")
    print(f"  Skipped (self-boundary): {skipped_self}")
    print(f"  Skipped (nation not in DB): {skipped_missing}")
    print(f"  Skipped (duplicate): {skipped_duplicate}")

    return new_rels


def extract_eez_iho(entities, existing_rels):
    """Extract eez_overlaps(nation, sea) from EEZ-IHO Intersection."""
    new_rels = []
    skipped_missing = 0
    skipped_duplicate = 0

    with open(EEZ_IHO_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            iho_mrgid = row.get("iho_mrgid", "").strip()
            sov1 = row.get("mrgid_sov1", "").strip()
            area = row.get("area_km2", "").strip()
            iho_sea = row.get("iho_sea", "").strip()

            if not iho_mrgid or not sov1:
                continue
            try:
                iho_mrgid = int(iho_mrgid)
                sov1 = int(sov1)
            except ValueError:
                continue

            if sov1 == 0 or iho_mrgid == 0:
                continue

            # Check entities exist
            if sov1 not in entities:
                skipped_missing += 1
                continue
            if iho_mrgid not in entities:
                skipped_missing += 1
                continue

            # Check not duplicate
            if (sov1, "eez_overlaps", iho_mrgid) in existing_rels:
                skipped_duplicate += 1
                continue

            target_name = entities[iho_mrgid][0] if iho_mrgid in entities else iho_sea
            target_type = entities[iho_mrgid][1] if iho_mrgid in entities else "Sea"

            new_rels.append({
                "source_mrgid": sov1,
                "relationship": "eez_overlaps",
                "target_mrgid": iho_mrgid,
                "target_name": target_name,
                "target_type": target_type,
                "attr_name": "area_km2",
                "attr_value": area,
                "source_data": "mr_wfs_eez_iho",
            })

            existing_rels.add((sov1, "eez_overlaps", iho_mrgid))

    print(f"\nEEZ-IHO Intersection:")
    print(f"  New relationships: {len(new_rels)}")
    print(f"  Skipped (entity not in DB): {skipped_missing}")
    print(f"  Skipped (duplicate): {skipped_duplicate}")

    return new_rels


def main():
    conn = sqlite3.connect(DB_PATH)
    entities = load_db_entities(conn)
    existing_rels = load_existing_relationships(conn)

    print(f"DB: {len(entities)} entities, {len(existing_rels)} relationships\n")

    border_rels = extract_maritime_borders(entities, existing_rels)
    iho_rels = extract_eez_iho(entities, existing_rels)

    all_new = border_rels + iho_rels
    print(f"\n{'='*50}")
    print(f"Total new relationships: {len(all_new)}")

    # Show samples
    print(f"\nSample maritime borders:")
    seen_borders = set()
    for r in border_rels:
        if r["attr_name"] == "line_type":
            key = (r["source_mrgid"], r["target_mrgid"])
            if key not in seen_borders:
                src_name = entities[r["source_mrgid"]][0]
                print(f"  {src_name} --[{r['attr_value']}]--> {r['target_name']}")
                seen_borders.add(key)
            if len(seen_borders) >= 10:
                break

    print(f"\nSample EEZ-IHO overlaps:")
    for r in iho_rels[:10]:
        src_name = entities[r["source_mrgid"]][0]
        print(f"  {src_name} --eez_overlaps--> {r['target_name']} ({r['attr_value']} km²)")

    if "--apply" in sys.argv:
        print(f"\nApplying {len(all_new)} relationships to database...")
        cursor = conn.cursor()
        for r in all_new:
            cursor.execute(
                """INSERT INTO relationships
                   (source_mrgid, relationship, target_mrgid, target_name, target_type,
                    attr_name, attr_value, source_data)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["source_mrgid"], r["relationship"], r["target_mrgid"],
                 r["target_name"], r["target_type"], r["attr_name"], r["attr_value"],
                 r["source_data"])
            )
        conn.commit()

        # Verify
        total = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
        mb = conn.execute("SELECT COUNT(*) FROM relationships WHERE relationship='maritime_border'").fetchone()[0]
        eo = conn.execute("SELECT COUNT(*) FROM relationships WHERE relationship='eez_overlaps'").fetchone()[0]
        print(f"\nDB now has {total} total relationships")
        print(f"  maritime_border: {mb}")
        print(f"  eez_overlaps: {eo}")
    else:
        print(f"\n--- DRY RUN --- Run with --apply to write to DB.")

    conn.close()


if __name__ == "__main__":
    main()
