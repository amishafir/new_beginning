#!/usr/bin/env python3
"""
Merge TFDD transboundary river basins into the Marine Regions database.

For rivers that exist in MR: add flows_through relationships.
For rivers not in MR: create new entities (synthetic MRGIDs) + flows_through relationships.

Usage:
    python3 merge_tfdd_rivers.py              # Dry run — show what would happen
    python3 merge_tfdd_rivers.py --apply      # Apply changes to the database
    python3 merge_tfdd_rivers.py --stats      # Show merge statistics
"""

import json
import sqlite3
import sys
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "marine_regions"
DB_PATH = DATA_DIR / "global_map.db"
TFDD_PATH = Path(__file__).parent / "data" / "rivers" / "05_raw_rivers_data.json"

SYNTHETIC_MRGID_START = 900000

# ─── TFDD country name → MR nation name ─────────────────────────────────────

COUNTRY_ALIASES = {
    # Dutch/local names in MR
    "turkey": "türkiye",
    "belgium": "belgië",
    "france": "frankrijk",
    "netherlands": "nederland",
    "luxembourg": "groothertogdom luxemburg",
    "suriname": "surinam",
    "somalia": "federal republic of somalia",
    # TFDD formal names → MR names
    "brunei darussalam": "brunei",
    "eswatini": "swaziland",
    "lao people's democratic republic": "laos",
    "moldova, republic of": "moldova",
    "rep. of congo": "republic of the congo",
    "the former yugoslav republic of macedonia": "north macedonia",
    "timor-leste": "east timor",
    "u.k. of great britain and northern ireland": "united kingdom",
    "dr congo": "democratic republic of the congo",
    "french guiana": "french guiana",  # Territory in MR (mrgid 8683)
    # Disputed territories / sub-national — no MR nation match
    "abyei": None,
    "aksai chin": None,
    "arunachal pradesh": None,
    "china/india": None,
    "hala'ib triangle": None,
    "ilemi triangle": None,
    "jammu and kashmir": None,
    "ma'tan al-sarra": None,
    "west bank": None,
}

# ─── TFDD basin name → MR river name (for the ~57 that match) ───────────────

RIVER_ALIASES = {
    # Slash names → pick the MR match
    "congo/zaire": "congo",
    "douro/duero": "duero",
    "ems/eems": "ems",
    "ganges-brahmaputra-meghna": "ganges river",
    "mino": "miño",
    "st. john (africa)": "st. john's river",
    "st. john (north america)": "saint john river",
    "rio grande (north america)": "rio grande",
    "rio grande (south america)": "rio grande",
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def build_river_index(conn):
    """Build name → mrgid index for MR rivers."""
    index = {}
    rows = conn.execute("SELECT mrgid, name FROM entities WHERE type='River'").fetchall()
    for mrgid, name in rows:
        nl = name.lower().strip()
        index[nl] = mrgid
        # Also index without suffix
        for suffix in [" river", " stream", " creek"]:
            if nl.endswith(suffix):
                index[nl[:-len(suffix)]] = mrgid
    return index


def build_nation_index(conn):
    """Build name → mrgid index for MR nations."""
    index = {}
    rows = conn.execute(
        "SELECT mrgid, name FROM entities WHERE type IN ('Nation', 'Territory')"
    ).fetchall()
    for mrgid, name in rows:
        index[name.lower().strip()] = mrgid
    return index


def match_river(basin_name, river_index):
    """Try to match a TFDD basin name to an existing MR river entity."""
    bl = basin_name.lower().strip()

    # Check alias first
    if bl in RIVER_ALIASES:
        al = RIVER_ALIASES[bl].lower()
        if al in river_index:
            return river_index[al]

    # Exact match
    if bl in river_index:
        return river_index[bl]

    # Try with " river" suffix
    if bl + " river" in river_index:
        return river_index[bl + " river"]

    # Try first part of slash/dash names
    for sep in ["/", "-"]:
        if sep in bl:
            parts = [p.strip() for p in bl.split(sep)]
            for p in parts:
                if p in river_index:
                    return river_index[p]
                if p + " river" in river_index:
                    return river_index[p + " river"]

    return None


def match_country(country_name, nation_index):
    """Try to match a TFDD country name to an MR nation entity."""
    cl = country_name.lower().strip()

    # Check alias
    if cl in COUNTRY_ALIASES:
        al = COUNTRY_ALIASES[cl]
        if al is None:
            return None  # Known unmatchable
        cl = al.lower()

    if cl in nation_index:
        return nation_index[cl]

    return None


def get_existing_flows(conn):
    """Get existing flows_through pairs to avoid duplicates."""
    rows = conn.execute("""
        SELECT source_mrgid, target_mrgid FROM relationships
        WHERE relationship = 'flows_through'
    """).fetchall()
    return {(r[0], r[1]) for r in rows}


def merge(conn, dry_run=True):
    """Merge TFDD basins into the database."""
    with open(TFDD_PATH) as f:
        basins = json.load(f)

    river_index = build_river_index(conn)
    nation_index = build_nation_index(conn)
    existing_flows = get_existing_flows(conn)

    # Continent → tier mapping (rivers are tier 3)
    TIER = 3

    matched_rivers = 0
    new_rivers = 0
    new_relationships = 0
    skipped_duplicate = 0
    unmatched_countries = set()
    next_synthetic = SYNTHETIC_MRGID_START

    # Check what synthetic IDs already exist
    existing_synthetic = conn.execute(
        "SELECT MAX(mrgid) FROM entities WHERE mrgid >= ?",
        (SYNTHETIC_MRGID_START,)
    ).fetchone()[0]
    if existing_synthetic:
        next_synthetic = existing_synthetic + 1

    for basin in basins:
        basin_name = basin["basin_name"]
        countries = basin["countries"]
        area_km2 = basin.get("total_area_km2")

        # Try to match to existing MR river
        mrgid = match_river(basin_name, river_index)

        if mrgid:
            matched_rivers += 1
        else:
            # Create new entity
            new_rivers += 1
            mrgid = next_synthetic
            next_synthetic += 1

            if not dry_run:
                conn.execute("""
                    INSERT INTO entities (mrgid, name, type, tier, source, area_km2)
                    VALUES (?, ?, 'River', ?, 'TFDD', ?)
                """, (mrgid, basin_name, TIER, area_km2))

        # Add flows_through for each country
        for country in countries:
            nation_mrgid = match_country(country, nation_index)
            if nation_mrgid is None:
                unmatched_countries.add(country)
                continue

            pair = (mrgid, nation_mrgid)
            if pair in existing_flows:
                skipped_duplicate += 1
                continue

            new_relationships += 1
            existing_flows.add(pair)

            if not dry_run:
                # Get nation name for target_name field
                nation_name = conn.execute(
                    "SELECT name FROM entities WHERE mrgid = ?",
                    (nation_mrgid,)
                ).fetchone()[0]

                conn.execute("""
                    INSERT INTO relationships
                        (source_mrgid, relationship, target_mrgid,
                         target_name, target_type, source_data)
                    VALUES (?, 'flows_through', ?, ?, 'Nation', 'tfdd')
                """, (mrgid, nation_mrgid, nation_name))

    if not dry_run:
        conn.commit()

    # Report
    mode = "DRY RUN" if dry_run else "APPLIED"
    print(f"\n═══ TFDD Merge Results ({mode}) ═══")
    print(f"  Total TFDD basins: {len(basins)}")
    print(f"  Matched to existing MR rivers: {matched_rivers}")
    print(f"  New river entities to create: {new_rivers}")
    print(f"  New flows_through relationships: {new_relationships}")
    print(f"  Skipped (already exist): {skipped_duplicate}")
    if unmatched_countries:
        print(f"  Unmatched countries ({len(unmatched_countries)}):")
        for c in sorted(unmatched_countries):
            print(f"    {c}")

    return new_rivers, new_relationships


def print_stats(conn):
    """Show TFDD-sourced data in the DB."""
    print("\n═══ TFDD Data in Database ═══")

    tfdd_entities = conn.execute(
        "SELECT COUNT(*) FROM entities WHERE source = 'TFDD'"
    ).fetchone()[0]
    print(f"  TFDD entities: {tfdd_entities}")

    tfdd_rels = conn.execute(
        "SELECT COUNT(*) FROM relationships WHERE source_data = 'tfdd'"
    ).fetchone()[0]
    print(f"  TFDD relationships: {tfdd_rels}")

    # Total flows_through
    total_flows = conn.execute(
        "SELECT COUNT(*) FROM relationships WHERE relationship = 'flows_through'"
    ).fetchone()[0]
    print(f"  Total flows_through (all sources): {total_flows}")

    # Sample
    print("\n  Sample TFDD flows_through:")
    rows = conn.execute("""
        SELECT e.name, r.target_name
        FROM relationships r
        JOIN entities e ON r.source_mrgid = e.mrgid
        WHERE r.source_data = 'tfdd'
        ORDER BY e.name
        LIMIT 20
    """).fetchall()
    for name, target in rows:
        print(f"    {name} → {target}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Merge TFDD rivers into Marine Regions DB")
    parser.add_argument("--apply", action="store_true", help="Apply changes (default is dry run)")
    parser.add_argument("--stats", action="store_true", help="Show TFDD data stats")
    args = parser.parse_args()

    conn = get_db()

    # Ensure source column exists on entities
    try:
        conn.execute("ALTER TABLE entities ADD COLUMN source TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Already exists

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    new_rivers, new_rels = merge(conn, dry_run=not args.apply)

    if not args.apply and (new_rivers > 0 or new_rels > 0):
        print(f"\n  Run with --apply to write these changes.")

    conn.close()


if __name__ == "__main__":
    main()
