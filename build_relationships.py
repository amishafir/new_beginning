#!/usr/bin/env python3
"""
Build relationships for the Marine Regions global database.

Sources:
1. Relationship.csv — curated relationships (borders, adjacency, hierarchy, rivers)
2. API hierarchy — parent relationships from getGazetteerRelationsByMRGID
3. Spatial inference — bounding box overlap for additional adjacency

Usage:
    python3 build_relationships.py                  # Import CSV + API hierarchy
    python3 build_relationships.py --csv-only       # Only import CSV
    python3 build_relationships.py --api-only       # Only fetch API hierarchy
    python3 build_relationships.py --spatial         # Also compute spatial relationships
    python3 build_relationships.py --stats           # Print relationship stats
"""

import csv
import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "marine_regions"
DB_PATH = DATA_DIR / "global_map.db"
CSV_PATH = Path(__file__).parent / "Relationship.csv"
BASE_URL = "https://www.marineregions.org/rest"
REQUEST_DELAY = 1.0
REQUEST_TIMEOUT = 30
MAX_RETRIES = 3

# ─── Name normalization for matching CSV names to DB entities ────────────────

# Map CSV Tag types to DB entity types
TAG_TO_TYPE = {
    "Nation": "Nation",
    "Country": "Nation",
    "IHO_Sea_Area": "Sea",
    "IHO Sea Area": "Sea",
    "General_Sea_Area": "Sea",
    "Sea": "Sea",
    "Ocean": "Ocean",
    "Strait": "Strait",
    "Seachannel": "Channel",
    "River": "River",
    "Delta": "Delta",
}

# Normalize relationship names
REL_NORMALIZE = {
    "Part_of": "part_of",
    "Part of": "part_of",
    "Adjacent_to": "adjacent_to",
    "Adjacent to": "adjacent_to",
    "Land_border_with": "borders",
    "Runthrough": "flows_through",
    "Similar_to": "similar_to",
    "Flows_out": "flows_into",
    "Flows out": "flows_into",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ─── Name aliases for CSV → DB matching ─────────────────────────────────────

NAME_ALIASES = {
    # Nations: CSV name → DB name (Marine Regions uses local/older names)
    "luxembourg": "groothertogdom luxemburg",
    "belgium": "belgië",
    "korea, democratic people's repu": "north korea",
    "korea, republic of": "south korea",
    "macedonia": "north macedonia",
    "dhekelia": None,  # UK sovereign base area, not in gazetteer
    "scotland": None,  # Sub-national, not separate nation in MR
    "akrotiri": None,  # UK sovereign base area
    "congo, democratic republic of": "democratic republic of the congo",
    "congo, republic of": "republic of the congo",
    "holy see": "vatican city",
    "bosnia-herzegovina": "bosnia and herzegovina",
    "myanmar (burma)": "myanmar",
    "ivory coast": "côte d'ivoire",
    "cape verde": "cabo verde",
    "gambia, the": "gambia",
    "byelarus": "belarus",
    "russia (kaliningrad)": "russia",
    "kosovo": None,  # Not recognized as separate nation in MR
    "netherlands": "nederland",
    "turkey": "türkiye",
    "france": "frankrijk",
    "congo": "republic of the congo",
    "somalia": "federal republic of somalia",
    "suriname": "surinam",
    "tanzania, united republic of": "tanzania",
    "burma": "myanmar",
    "uk": "united kingdom",
    "botswana 0.": "botswana",
    # Not in gazetteer as nations, or sub-national:
    "sint maarten": None,
    "european union": None,
    "akrotiri": None,
    "alaska": None,
    "gaza strip": None,
    "west bank": None,
    "us naval base at guantanamo bay 28.": None,
    "saint martin": None,
    "netherlands antilles": None,
    "barentsz sea": "barentszee",
    "eastern china sea": "east china sea",
}

# For rivers: the CSV often has just the river name, DB has "X River"
RIVER_SUFFIX_MATCH = True


# ─── CSV Import ──────────────────────────────────────────────────────────────

def build_name_index(conn):
    """Build a lookup: (name_lower, type) → mrgid for fuzzy matching."""
    index = {}
    rows = conn.execute("SELECT mrgid, name, type FROM entities").fetchall()
    for mrgid, name, etype in rows:
        key = name.lower().strip()
        # Store by name alone (for cross-type matching)
        if key not in index:
            index[key] = mrgid
        # Also store by (name, type) for precise matching
        index[(key, etype)] = mrgid

        # For rivers: also index without " River" / " Stream" suffix
        if etype == "River" and key.endswith(" river"):
            short = key[:-6]  # strip " river"
            if (short, "River") not in index:
                index[(short, "River")] = mrgid
        if etype == "River" and key.endswith(" stream"):
            short = key[:-7]
            if (short, "River") not in index:
                index[(short, "River")] = mrgid

    return index


def resolve_entity(name_index, name, tag):
    """Resolve a CSV entity name + tag to an MRGID."""
    name_lower = name.lower().strip()
    db_type = TAG_TO_TYPE.get(tag, tag)

    # Check alias first
    if name_lower in NAME_ALIASES:
        aliased = NAME_ALIASES[name_lower]
        if aliased is None:
            return None  # Known unmatchable
        name_lower = aliased

    # Try exact (name, type) match first
    key = (name_lower, db_type)
    if key in name_index:
        return name_index[key]

    # Try name-only match
    if name_lower in name_index:
        return name_index[name_lower]

    # For rivers: try "X River" if just "X" was given
    if db_type == "River":
        river_key = (name_lower + " river", "River")
        if river_key in name_index:
            return name_index[river_key]

    # For nations: also try Territory type
    if db_type == "Nation":
        territory_key = (name_lower, "Territory")
        if territory_key in name_index:
            return name_index[territory_key]

    return None


def import_csv_relationships(conn):
    """Import relationships from Relationship.csv."""
    if not CSV_PATH.exists():
        print("  Relationship.csv not found, skipping")
        return 0

    name_index = build_name_index(conn)
    inserted = 0
    unresolved_a = set()
    unresolved_b = set()

    # Clear existing CSV-sourced relationships
    conn.execute("DELETE FROM relationships WHERE source_data = 'csv'")
    conn.commit()

    with open(CSV_PATH, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name_a = row["Attr_A_Value"]
            tag_a = row["Tag_A"]
            rel = row["Relationship"]
            name_b = row["Attr_B_Value"]
            tag_b = row["Tag_B"]

            mrgid_a = resolve_entity(name_index, name_a, tag_a)
            mrgid_b = resolve_entity(name_index, name_b, tag_b)

            norm_rel = REL_NORMALIZE.get(rel, rel.lower())

            # Build attribute dict from CSV
            attr_name = row.get("Rel_Att_Name_1", "")
            attr_value = row.get("Rel_Att_Value_1", "")

            if mrgid_a and mrgid_b:
                conn.execute("""
                    INSERT INTO relationships
                        (source_mrgid, relationship, target_mrgid,
                         target_name, target_type, attr_name, attr_value, source_data)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 'csv')
                """, (mrgid_a, norm_rel, mrgid_b, name_b,
                      TAG_TO_TYPE.get(tag_b, tag_b), attr_name or None, attr_value or None))
                inserted += 1
            else:
                if not mrgid_a:
                    unresolved_a.add((name_a, tag_a))
                if not mrgid_b:
                    unresolved_b.add((name_b, tag_b))

    conn.commit()

    if unresolved_a or unresolved_b:
        total_unresolved = len(unresolved_a) + len(unresolved_b)
        print(f"  Could not resolve {total_unresolved} entity references")
        # Show top unresolved
        for name, tag in list(unresolved_a)[:5]:
            print(f"    Source: {name} ({tag})")
        for name, tag in list(unresolved_b)[:5]:
            print(f"    Target: {name} ({tag})")

    return inserted


# ─── API Hierarchy Import ────────────────────────────────────────────────────

def api_get(endpoint):
    """Simple API GET with retry."""
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "MarineRegionsExtractor/1.0"
            })
            resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
            data = resp.read().decode("utf-8")
            return json.loads(data) if data.strip() else []
        except (TimeoutError, OSError):
            if attempt < MAX_RETRIES - 1:
                time.sleep((attempt + 1) * 3)
            continue
        except urllib.error.HTTPError:
            return []
    return []


def import_api_hierarchy(conn, tiers=None):
    """Fetch parent relationships from API for each entity."""
    # Get entities to process
    if tiers:
        placeholders = ",".join("?" * len(tiers))
        rows = conn.execute(
            f"SELECT mrgid, name, type, tier FROM entities WHERE tier IN ({placeholders})",
            tiers
        ).fetchall()
    else:
        rows = conn.execute("SELECT mrgid, name, type, tier FROM entities").fetchall()

    # Check which ones already have API relationships
    existing = set(r[0] for r in conn.execute(
        "SELECT DISTINCT source_mrgid FROM relationships WHERE source_data = 'api'"
    ).fetchall())

    to_process = [(m, n, t, ti) for m, n, t, ti in rows if m not in existing]
    total = len(to_process)
    inserted = 0

    print(f"  {total} entities to fetch relationships for ({len(existing)} already done)")

    for i, (mrgid, name, etype, tier) in enumerate(to_process):
        if i % 100 == 0 and i > 0:
            print(f"    Progress: {i}/{total} ({inserted} relationships)")
            conn.commit()

        rels = api_get(f"getGazetteerRelationsByMRGID.json/{mrgid}/")
        time.sleep(REQUEST_DELAY)

        if rels:
            for rel in rels:
                target_mrgid = rel.get("MRGID")
                target_name = rel.get("preferredGazetteerName")
                target_type = rel.get("placeType")

                if target_mrgid:
                    conn.execute("""
                        INSERT INTO relationships
                            (source_mrgid, relationship, target_mrgid,
                             target_name, target_type, source_data)
                        VALUES (?, 'part_of', ?, ?, ?, 'api')
                    """, (mrgid, target_mrgid, target_name, target_type))
                    inserted += 1

    conn.commit()
    return inserted


# ─── Spatial Relationship Inference ──────────────────────────────────────────

def compute_spatial_relationships(conn):
    """
    Infer adjacency relationships from bounding box overlap.
    Only for entities with valid bounding boxes.
    Focus on Nation ↔ Sea/Ocean adjacency.
    """
    # Get nations with bounding boxes
    nations = conn.execute("""
        SELECT mrgid, name, min_lat, min_lon, max_lat, max_lon
        FROM entities
        WHERE type = 'Nation'
          AND min_lat IS NOT NULL AND max_lat IS NOT NULL
    """).fetchall()

    # Get water bodies with bounding boxes — only specific named seas/gulfs/straits
    # Exclude overly broad regions (General Sea Area, Marine Ecoregion, etc.)
    # and filter by bounding box size to avoid giant regions matching everything
    waters = conn.execute("""
        SELECT mrgid, name, type, min_lat, min_lon, max_lat, max_lon
        FROM entities
        WHERE type IN ('Sea', 'Gulf', 'Bay', 'Strait', 'Channel', 'Sound', 'Fjord')
          AND min_lat IS NOT NULL AND max_lat IS NOT NULL
          AND (max_lat - min_lat) < 50
          AND (max_lon - min_lon) < 80
    """).fetchall()

    # Also include oceans separately with a higher threshold
    oceans = conn.execute("""
        SELECT mrgid, name, type, min_lat, min_lon, max_lat, max_lon
        FROM entities
        WHERE type = 'Ocean'
          AND min_lat IS NOT NULL AND max_lat IS NOT NULL
    """).fetchall()

    # Clear existing spatial relationships (we recompute each time)
    conn.execute("DELETE FROM relationships WHERE source_data = 'spatial'")

    # Track what we've already added this run
    added = set()

    # Get existing CSV adjacencies to avoid exact duplicates
    for row in conn.execute(
        "SELECT source_mrgid, target_mrgid FROM relationships WHERE relationship = 'adjacent_to'"
    ).fetchall():
        added.add((row[0], row[1]))
        added.add((row[1], row[0]))

    inserted = 0
    OVERLAP_THRESHOLD = 0.5  # degrees of overlap needed

    for n_mrgid, n_name, n_minlat, n_minlon, n_maxlat, n_maxlon in nations:
        for w_mrgid, w_name, w_type, w_minlat, w_minlon, w_maxlat, w_maxlon in waters:
            if (w_mrgid, n_mrgid) in added or (n_mrgid, w_mrgid) in added:
                continue

            # Check bounding box overlap
            overlap_lat = min(n_maxlat, w_maxlat) - max(n_minlat, w_minlat)
            overlap_lon = min(n_maxlon, w_maxlon) - max(n_minlon, w_minlon)

            if overlap_lat > OVERLAP_THRESHOLD and overlap_lon > OVERLAP_THRESHOLD:
                conn.execute("""
                    INSERT INTO relationships
                        (source_mrgid, relationship, target_mrgid,
                         target_name, target_type, source_data)
                    VALUES (?, 'adjacent_to', ?, ?, ?, 'spatial')
                """, (w_mrgid, n_mrgid, n_name, "Nation"))
                added.add((w_mrgid, n_mrgid))
                inserted += 1

    conn.commit()
    return inserted


# ─── Stats ───────────────────────────────────────────────────────────────────

def print_stats(conn):
    """Print relationship statistics."""
    print("\n═══ Relationship Statistics ═══")

    total = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    print(f"Total relationships: {total}")

    print("\nBy type:")
    for row in conn.execute(
        "SELECT relationship, COUNT(*) FROM relationships GROUP BY relationship ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nBy source:")
    for row in conn.execute(
        "SELECT source_data, COUNT(*) FROM relationships GROUP BY source_data ORDER BY COUNT(*) DESC"
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    print("\nSample relationships:")
    for row in conn.execute("""
        SELECT e1.name, r.relationship, r.target_name
        FROM relationships r
        JOIN entities e1 ON r.source_mrgid = e1.mrgid
        ORDER BY RANDOM() LIMIT 15
    """).fetchall():
        print(f"  {row[0]} → {row[1]} → {row[2]}")

    # Entity coverage
    entities_with_rels = conn.execute("""
        SELECT COUNT(DISTINCT source_mrgid) FROM relationships
    """).fetchone()[0]
    total_entities = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    print(f"\nEntities with relationships: {entities_with_rels}/{total_entities}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Build relationships for Marine Regions DB")
    parser.add_argument("--csv-only", action="store_true")
    parser.add_argument("--api-only", action="store_true")
    parser.add_argument("--spatial", action="store_true")
    parser.add_argument("--stats", action="store_true")
    parser.add_argument("--tier", type=int, action="append", help="API: process specific tier(s)")
    args = parser.parse_args()

    # Need to add source_data column if not exists
    conn = get_db()
    try:
        conn.execute("ALTER TABLE relationships ADD COLUMN source_data TEXT DEFAULT 'unknown'")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Column already exists

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    if not args.api_only:
        print("\n╔══════════════════════════════════════╗")
        print("║  Import CSV Relationships            ║")
        print("╚══════════════════════════════════════╝")
        count = import_csv_relationships(conn)
        print(f"  Imported {count} relationships from CSV")

    if not args.csv_only:
        print("\n╔══════════════════════════════════════╗")
        print("║  Import API Hierarchy                ║")
        print("╚══════════════════════════════════════╝")
        tiers = args.tier if args.tier else None
        count = import_api_hierarchy(conn, tiers=tiers)
        print(f"  Imported {count} relationships from API")

    if args.spatial:
        print("\n╔══════════════════════════════════════╗")
        print("║  Compute Spatial Relationships       ║")
        print("╚══════════════════════════════════════╝")
        count = compute_spatial_relationships(conn)
        print(f"  Inferred {count} spatial relationships")

    print_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
