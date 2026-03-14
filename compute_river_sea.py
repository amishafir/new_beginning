#!/usr/bin/env python3
"""
Compute flows_into(river, sea) relationships.

Strategy: For each river with coordinates, find which IHO Sea Area's bounding box
contains the river's coordinate point. Pick the smallest (most specific) sea.

Covers: 84 MR-sourced rivers that have coordinates.
Gap: 256 TFDD rivers have no coordinates in DB (would need shapefile mouth coords).

Usage:
    python3 compute_river_sea.py              # dry run
    python3 compute_river_sea.py --apply      # write to DB
"""

import csv
import sqlite3
import sys

DB_PATH = "data/marine_regions/global_map.db"
IHO_CSV = "/tmp/iho_seas.csv"


def load_iho_seas():
    """Load IHO sea areas with bounding boxes."""
    seas = []
    with open(IHO_CSV) as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                seas.append({
                    "name": row["name"],
                    "mrgid": int(row["mrgid"]),
                    "min_x": float(row["min_x"]),
                    "min_y": float(row["min_y"]),
                    "max_x": float(row["max_x"]),
                    "max_y": float(row["max_y"]),
                    "area": float(row["area"]) if row["area"] else 0,
                })
            except (ValueError, KeyError):
                pass
    return seas


def point_in_bbox(lat, lon, sea):
    """Check if a point falls within a sea's bounding box."""
    return (sea["min_x"] <= lon <= sea["max_x"] and
            sea["min_y"] <= lat <= sea["max_y"])


def find_containing_sea(lat, lon, iho_seas, max_area=None):
    """Find the smallest IHO sea whose bbox contains the point."""
    containing = []
    for sea in iho_seas:
        if point_in_bbox(lat, lon, sea):
            # Skip overly large seas (oceans) — they overlap entire continents
            if max_area and sea["area"] > max_area:
                continue
            containing.append(sea)

    if not containing:
        return None

    # Pick smallest by area (most specific)
    containing.sort(key=lambda s: s["area"])
    return containing[0]


# Manual overrides for rivers whose coordinates are midstream, not at the mouth.
# These rivers are well-known — the sea they empty into is authoritative knowledge.
MANUAL_OVERRIDES = {
    "Zambezi": "Mozambique Channel",
    "Sozh": None,           # Tributary of Dnieper — doesn't reach a sea directly
    "Snov River": None,     # Tributary of Desna — doesn't reach a sea
    "semliki": None,        # Flows into Lake Albert — endorheic/lake
    "Okavango River": None, # Endorheic — flows into Okavango Delta
    "Sava River": None,     # Tributary of Danube
    "Sangha ": None,        # Tributary of Congo
    "Oubangui River": None, # Tributary of Congo
    "Orontes ": "Mediterranean Sea - Eastern Basin",
    "Vardar ": "Aegean Sea",
    "Paraguay": "Rio de La Plata",  # Via Paraná
    "Rio Negro ": "South Atlantic Ocean",  # Via Amazon
    "Nile": "Mediterranean Sea - Eastern Basin",
    "Danube": "Black Sea",
    "Rhine": "North Sea",
    "Dnieper": "Black Sea",
    "Don River": "Black Sea",
    "Ganges": "Bay of Bengal",
    "Brahmaputra": "Bay of Bengal",
    "Mekong": "South China Sea",
    "Irrawaddy": "Andaman or Burma Sea",
    "Indus": "Arabian Sea",
    "Euphrates": "Persian Gulf",
    "Niger River": "Gulf of Guinea",
    "Congo River": "South Atlantic Ocean",
    "Amazon": "South Atlantic Ocean",
    "Volga": "Caspian Sea",
    "Jordan River": None,     # Flows into Dead Sea (endorheic)
    "Drava River ": None,     # Tributary of Danube
    "Dan River ": None,       # Tributary of Jordan
    "Kupa River": None,       # Tributary of Sava (→ Danube)
    "Moselle River": None,    # Tributary of Rhine
    "Leie": None,             # Tributary of Scheldt
    "Meta River": None,       # Tributary of Orinoco
    "Kasai River": None,      # Tributary of Congo
    "Luapula": None,          # Tributary of Congo
    "Guadiana": "North Atlantic Ocean",
    "Mira": "North Atlantic Ocean",
    "Indus River": "Arabian Sea",
    "Ganges River": "Bay of Bengal",
    "Tana River": "Indian Ocean",
    "Senegal": "North Atlantic Ocean",
    "Orange River": "South Atlantic Ocean",
    "Kunene River": "South Atlantic Ocean",
    "Madeira": "North Atlantic Ocean",   # River on Madeira island
    "Hondo": "North Pacific Ocean",
    "Colorado River": "Gulf of California",
    "Fly River": "Coral Sea",
    "Republic of the Congo": None,  # Not a river — entity mismatch
    "Chu River": None,              # Endorheic (disappears in Kazakhstan steppe)
    "Chari": None,                  # Flows into Lake Chad (endorheic)
    "Brahmaputra river": "Bay of Bengal",
    "Argun ": None,                 # Tributary of Amur
    "Congo": "South Atlantic Ocean",
    "Han River": "South China Sea",
    "Green River": None,            # Tributary of Ohio/Mississippi
    "Duero": "North Atlantic Ocean",
    "Lima": "North Atlantic Ocean",
    "Po": "Adriatic Sea",
    "Schelde": "North Sea",
    "Tagus": "North Atlantic Ocean",
    "Columbia River": "North Pacific Ocean",
    "Connecticut River": "North Atlantic Ocean",
    "Mississippi River": "Gulf of Mexico",
    "Tijuana River": "North Pacific Ocean",
    "Amazon River": "South Atlantic Ocean",
    "Essequibo River": "North Atlantic Ocean",
    "Orinoco River": "Caribbean Sea",
}


def main():
    conn = sqlite3.connect(DB_PATH)
    iho_seas = load_iho_seas()

    # Get rivers that have flows_through AND coordinates
    rivers = conn.execute("""
        SELECT DISTINCT e.mrgid, e.name, e.latitude, e.longitude
        FROM entities e
        JOIN relationships r ON e.mrgid = r.source_mrgid
        WHERE r.relationship = 'flows_through'
        AND e.latitude IS NOT NULL AND e.longitude IS NOT NULL
    """).fetchall()

    # Load existing flows_into to avoid duplicates
    existing = set()
    rows = conn.execute("SELECT source_mrgid, target_mrgid FROM relationships WHERE relationship='flows_into'").fetchall()
    for r in rows:
        existing.add((r[0], r[1]))

    new_rels = []
    no_sea = []
    skipped_dup = 0

    for mrgid, name, lat, lon in rivers:
        # Check manual override
        if name in MANUAL_OVERRIDES:
            sea_name = MANUAL_OVERRIDES[name]
            if sea_name is None:
                # Tributary or endorheic — skip
                continue
            # Try IHO list first, then DB lookup
            sea = next((s for s in iho_seas if s["name"] == sea_name), None)
            if not sea:
                # Look up in DB directly
                db_sea = conn.execute("SELECT mrgid, name FROM entities WHERE name=?", (sea_name,)).fetchone()
                if db_sea:
                    sea = {"mrgid": db_sea[0], "name": db_sea[1]}
        else:
            # Use max_area filter to avoid matching entire oceans for inland rivers
            # 2,000,000 km² threshold excludes the major oceans but keeps regional seas
            sea = find_containing_sea(lat, lon, iho_seas, max_area=2_000_000)

        if not sea:
            no_sea.append((name, lat, lon))
            continue

        if (mrgid, sea["mrgid"]) in existing:
            skipped_dup += 1
            continue

        # Check sea exists in DB
        sea_info = conn.execute("SELECT name, type FROM entities WHERE mrgid=?", (sea["mrgid"],)).fetchone()
        if not sea_info:
            no_sea.append((name, lat, lon))
            continue

        new_rels.append({
            "source_mrgid": mrgid,
            "relationship": "flows_into",
            "target_mrgid": sea["mrgid"],
            "target_name": sea_info[0],
            "target_type": sea_info[1],
            "source_data": "spatial_iho",
        })
        existing.add((mrgid, sea["mrgid"]))

    print(f"Rivers with flows_through + coordinates: {len(rivers)}")
    print(f"New flows_into relationships: {len(new_rels)}")
    print(f"No containing sea found: {len(no_sea)}")
    print(f"Skipped (duplicate): {skipped_dup}")

    if no_sea:
        print(f"\nRivers with no matching IHO sea:")
        for name, lat, lon in no_sea[:15]:
            print(f"  {name} ({lat:.2f}, {lon:.2f})")

    print(f"\nSample flows_into:")
    for r in new_rels[:20]:
        src = conn.execute("SELECT name FROM entities WHERE mrgid=?", (r["source_mrgid"],)).fetchone()[0]
        print(f"  {src} --flows_into--> {r['target_name']}")

    # Count rivers still missing (TFDD without coords)
    tfdd_no_coords = conn.execute("""
        SELECT COUNT(DISTINCT e.mrgid) FROM entities e
        JOIN relationships r ON e.mrgid = r.source_mrgid
        WHERE r.relationship = 'flows_through' AND e.source = 'TFDD' AND e.latitude IS NULL
    """).fetchone()[0]
    print(f"\nGap: {tfdd_no_coords} TFDD rivers have no coordinates (need shapefile mouth coords)")

    if "--apply" in sys.argv:
        print(f"\nApplying {len(new_rels)} relationships...")
        cursor = conn.cursor()
        for r in new_rels:
            cursor.execute(
                """INSERT INTO relationships
                   (source_mrgid, relationship, target_mrgid, target_name, target_type, source_data)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (r["source_mrgid"], r["relationship"], r["target_mrgid"],
                 r["target_name"], r["target_type"], r["source_data"])
            )
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM relationships WHERE relationship='flows_into'").fetchone()[0]
        print(f"Total 'flows_into' relationships now: {total}")
    else:
        print(f"\n--- DRY RUN --- Run with --apply to write to DB.")

    conn.close()


if __name__ == "__main__":
    main()
