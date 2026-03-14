#!/usr/bin/env python3
"""
Compute strait-sea connections: which seas does each strait connect?

Strategy:
1. Curated list for ~30 major straits (authoritative, high-confidence)
2. Spatial computation for remaining ~125 (strait bbox overlaps with IHO sea bboxes)

Output: connects(strait, sea) relationships in global_map.db
"""

import csv
import sqlite3
import sys

DB_PATH = "data/marine_regions/global_map.db"
IHO_CSV = "/tmp/iho_seas.csv"

# Curated connections for major straits.
# Format: strait name -> [sea1, sea2, ...]
# These are stable geographic facts — a strait connects exactly the seas on either side.
CURATED = {
    "Strait of Gibraltar": ["Mediterranean Sea - Western Basin", "North Atlantic Ocean"],
    "Bosporus": ["Sea of Marmara", "Black Sea"],
    "Dardanelles": ["Sea of Marmara", "Aegean Sea"],
    "Strait of Malacca": ["Andaman or Burma Sea", "South China Sea"],
    "Strait of Hormuz": ["Persian Gulf", "Gulf of Oman"],
    "Bab al Mandab": ["Red Sea", "Gulf of Aden"],
    "Pas de Calais": ["La Manche", "North Sea"],  # Dover Strait
    "Strait of Messina": ["Tyrrhenian Sea", "Mediterranean Sea - Eastern Basin"],
    "Strait of Otranto": ["Adriatic Sea", "Mediterranean Sea - Eastern Basin"],
    "Strait of Sicily": ["Mediterranean Sea - Western Basin", "Mediterranean Sea - Eastern Basin"],
    "Bering Strait": ["Bering Sea", "Arctic Ocean"],
    "Denmark Strait": ["North Atlantic Ocean", "Arctic Ocean"],
    "Strait of Magellan": ["South Atlantic Ocean", "South Pacific Ocean"],
    "Strait of Juan de Fuca": ["North Pacific Ocean", "Strait of Georgia"],
    "Tsugaru Strait": ["Japan Sea/East Sea", "North Pacific Ocean"],
    "Korea Strait": ["Japan Sea/East Sea", "Eastern China Sea"],
    "Taiwan Strait": ["Eastern China Sea", "South China Sea"],
    "Mozambique Channel": ["Indian Ocean", "Indian Ocean"],  # same ocean both sides
    "Yucatán, Canal de": ["Caribbean Sea", "Gulf of Mexico"],
    "Florida, Straits of": ["Gulf of Mexico", "North Atlantic Ocean"],
    "Great Belt": ["Kattegat", "Baltic Sea"],
    "Little Belt": ["Kattegat", "Baltic Sea"],
    "Bornholm Strait": ["Baltic Proper", "Baltic Sea"],
    "Skagerrak": ["North Sea", "Kattegat"],
    "Kattegat": ["Skagerrak", "Baltic Sea"],
    "Strait of Bonifacio": ["Tyrrhenian Sea", "Mediterranean Sea - Western Basin"],
    "Luzon Strait": ["South China Sea", "Philippine Sea"],
    "Sunda Strait": ["Indian Ocean", "Java Sea"],
    "Lombok Strait": ["Indian Ocean", "Bali Sea"],
    "Makassar Strait": ["Celebes Sea", "Java Sea"],
    "Torres Strait": ["Coral Sea", "Arafura Sea"],
    "Cook Strait": ["Tasman Sea", "South Pacific Ocean"],
    "Bass Strait": ["Tasman Sea", "Great Australian Bight"],
    # Entities typed as 'Sea' in MR but are actually straits:
    "Malacca Strait": ["Andaman or Burma Sea", "South China Sea"],
    "Singapore Strait": ["South China Sea", "Malacca Strait"],
    "Makassar Strait": ["Celebes Sea", "Java Sea"],
    "Davis Strait": ["Baffin Bay", "Labrador Sea"],
    "Hudson Strait": ["Labrador Sea", "Hudson Bay"],
}


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


def bbox_overlaps(a, b):
    """Check if two bounding boxes overlap."""
    return (a["min_x"] <= b["max_x"] and a["max_x"] >= b["min_x"] and
            a["min_y"] <= b["max_y"] and a["max_y"] >= b["min_y"])


def compute_spatial_connections(strait, iho_seas):
    """Find IHO seas whose bbox overlaps the strait's bbox, pick the 2 smallest."""
    if not strait["min_lat"]:
        return []

    strait_box = {
        "min_x": strait["min_lon"],
        "min_y": strait["min_lat"],
        "max_x": strait["max_lon"],
        "max_y": strait["max_lat"],
    }

    overlapping = []
    for sea in iho_seas:
        if bbox_overlaps(strait_box, sea):
            overlapping.append(sea)

    # Sort by area (smallest = most specific)
    overlapping.sort(key=lambda s: s["area"])

    # Return up to 2 smallest overlapping seas
    return overlapping[:2]


def main():
    conn = sqlite3.connect(DB_PATH)

    # Load straits from DB — include type='Strait' AND any entity named 'Strait of...' or '...Strait'
    # MR classifies some major straits as 'Sea' (Gibraltar, Malacca, Makassar, etc.)
    straits = conn.execute("""
        SELECT mrgid, name, latitude, longitude, min_lat, min_lon, max_lat, max_lon
        FROM entities
        WHERE type='Strait'
           OR (name LIKE '%Strait%' AND type IN ('Sea','Channel'))
    """).fetchall()
    strait_data = []
    for s in straits:
        strait_data.append({
            "mrgid": s[0], "name": s[1],
            "lat": s[2], "lon": s[3],
            "min_lat": s[4], "min_lon": s[5],
            "max_lat": s[6], "max_lon": s[7],
        })

    # Load IHO seas
    iho_seas = load_iho_seas()

    # Build name -> MRGID lookup for IHO seas (check DB first, fall back to IHO CSV)
    sea_name_to_mrgid = {}
    for s in iho_seas:
        sea_name_to_mrgid[s["name"]] = s["mrgid"]
    # Also check DB for sea entities (broader set)
    db_seas = conn.execute("SELECT mrgid, name FROM entities WHERE type IN ('Sea','Strait','Gulf','Bay')").fetchall()
    db_sea_lookup = {name: mrgid for mrgid, name in db_seas}

    # Load existing connects relationships to avoid duplicates
    existing = set()
    rows = conn.execute("SELECT source_mrgid, target_mrgid FROM relationships WHERE relationship='connects'").fetchall()
    for r in rows:
        existing.add((r[0], r[1]))

    new_rels = []
    curated_count = 0
    computed_count = 0
    no_match = []

    for strait in strait_data:
        name = strait["name"]

        if name in CURATED:
            # Use curated connections
            for sea_name in CURATED[name]:
                sea_mrgid = sea_name_to_mrgid.get(sea_name) or db_sea_lookup.get(sea_name)
                if sea_mrgid and (strait["mrgid"], sea_mrgid) not in existing:
                    sea_info = conn.execute("SELECT name, type FROM entities WHERE mrgid=?", (sea_mrgid,)).fetchone()
                    if sea_info:
                        new_rels.append({
                            "source_mrgid": strait["mrgid"],
                            "relationship": "connects",
                            "target_mrgid": sea_mrgid,
                            "target_name": sea_info[0],
                            "target_type": sea_info[1],
                            "source_data": "curated",
                        })
                        existing.add((strait["mrgid"], sea_mrgid))
                        curated_count += 1
                elif not sea_mrgid:
                    no_match.append((name, sea_name))
        else:
            # Compute from spatial overlap
            connections = compute_spatial_connections(strait, iho_seas)
            for sea in connections:
                if (strait["mrgid"], sea["mrgid"]) not in existing:
                    sea_info = conn.execute("SELECT name, type FROM entities WHERE mrgid=?", (sea["mrgid"],)).fetchone()
                    if sea_info:
                        new_rels.append({
                            "source_mrgid": strait["mrgid"],
                            "relationship": "connects",
                            "target_mrgid": sea["mrgid"],
                            "target_name": sea_info[0],
                            "target_type": sea_info[1],
                            "source_data": "spatial_iho",
                        })
                        existing.add((strait["mrgid"], sea["mrgid"]))
                        computed_count += 1

    print(f"Straits in DB: {len(strait_data)}")
    print(f"Curated connections: {curated_count}")
    print(f"Computed connections: {computed_count}")
    print(f"Total new 'connects' relationships: {len(new_rels)}")
    if no_match:
        print(f"\nUnmatched sea names in curated list:")
        for strait_name, sea_name in no_match:
            print(f"  {strait_name} -> '{sea_name}' NOT FOUND")

    # Samples
    print(f"\nSample curated:")
    for r in new_rels:
        if r["source_data"] == "curated":
            src = conn.execute("SELECT name FROM entities WHERE mrgid=?", (r["source_mrgid"],)).fetchone()[0]
            print(f"  {src} --connects--> {r['target_name']}")
        if sum(1 for x in new_rels if x["source_data"] == "curated" and new_rels.index(x) < new_rels.index(r)) >= 9:
            break

    print(f"\nSample computed:")
    count = 0
    for r in new_rels:
        if r["source_data"] == "spatial_iho" and count < 10:
            src = conn.execute("SELECT name FROM entities WHERE mrgid=?", (r["source_mrgid"],)).fetchone()[0]
            print(f"  {src} --connects--> {r['target_name']}")
            count += 1

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
        total = conn.execute("SELECT COUNT(*) FROM relationships WHERE relationship='connects'").fetchone()[0]
        print(f"Total 'connects' relationships now: {total}")
    else:
        print(f"\n--- DRY RUN --- Run with --apply to write to DB.")

    conn.close()


if __name__ == "__main__":
    main()
