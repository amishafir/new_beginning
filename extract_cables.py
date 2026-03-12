#!/usr/bin/env python3
"""
Extract submarine cable data from TeleGeography API into the Marine Regions database.

Entities created:
  - Cable (type='Cable', tier=8) — each submarine cable system
  - Landing Point (type='Landing Point', tier=8) — each cable landing station

Relationships created:
  - cable connects nation (via landing points)
  - cable lands_at landing_point
  - landing_point located_in nation

Usage:
    python3 extract_cables.py                # Full extraction
    python3 extract_cables.py --stats        # Show cable stats in DB
    python3 extract_cables.py --resume       # Resume from checkpoint
"""

import json
import re
import sqlite3
import sys
import time
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data" / "marine_regions"
DB_PATH = DATA_DIR / "global_map.db"
CABLE_DIR = Path(__file__).parent / "data" / "cables"
CHECKPOINT_PATH = CABLE_DIR / "extraction_checkpoint.json"
BASE_URL = "https://www.submarinecablemap.com/api/v3"
REQUEST_DELAY = 0.5
REQUEST_TIMEOUT = 20
MAX_RETRIES = 3

CABLE_MRGID_START = 800000
LP_MRGID_START = 850000

# ─── Country name aliases: TeleGeography → Marine Regions DB ─────────────────

COUNTRY_ALIASES = {
    "france": "frankrijk",
    "comoros": "comores",
    "congo, dem. rep.": "democratic republic of the congo",
    "congo, rep.": "republic of the congo",
    "somalia": "federal republic of somalia",
    "netherlands": "nederland",
    "belgium": "belgië",
    "turkey": "türkiye",
    "luxembourg": "groothertogdom luxemburg",
    "suriname": "surinam",
    "mauritius": "republic of mauritius",
    # Territory name variations
    "virgin islands (u.k.)": "british virgin islands",
    "virgin islands (u.s.)": "united states virgin islands",
    "timor-leste": "east timor",
    "saint martin": "collectivity of saint martin",
    "sint maarten": "sint-maarten",
    "cocos (keeling) islands": "cocos islands",
    "saint pierre and miquelon": "saint-pierre and miquelon",
    # Not in MR — skip (small territories)
    "curaçao": None,
    "bonaire, sint eustatius and saba": None,
    "faroe islands": None,
    "saint barthélemy": None,
    "british indian ocean territory": None,
}


def api_get(endpoint):
    """Fetch JSON from TeleGeography API with retry."""
    url = f"{BASE_URL}/{endpoint}"
    for attempt in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers={
                "Accept": "application/json",
                "User-Agent": "CableExtractor/1.0"
            })
            resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
            data = resp.read().decode("utf-8")
            if data.startswith("{") or data.startswith("["):
                return json.loads(data)
            else:
                # Got HTML instead of JSON
                return None
        except (TimeoutError, OSError) as e:
            if attempt < MAX_RETRIES - 1:
                time.sleep((attempt + 1) * 3)
            continue
        except Exception:
            return None
    return None


def parse_length_km(length_str):
    """Parse '45,000 km' → 45000.0"""
    if not length_str:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)", length_str)
    if m:
        return float(m.group(1).replace(",", ""))
    return None


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def build_nation_index(conn):
    """Build lowercase name → mrgid index for nations and territories."""
    index = {}
    rows = conn.execute(
        "SELECT mrgid, name FROM entities WHERE type IN ('Nation', 'Territory')"
    ).fetchall()
    for mrgid, name in rows:
        index[name.lower().strip()] = mrgid
    return index


def resolve_country(name, nation_index):
    """Resolve a TeleGeography country name to an MR nation MRGID."""
    nl = name.lower().strip()

    # Check alias
    if nl in COUNTRY_ALIASES:
        al = COUNTRY_ALIASES[nl]
        if al is None:
            return None
        nl = al.lower()

    if nl in nation_index:
        return nation_index[nl]

    return None


def load_checkpoint():
    """Load extraction checkpoint."""
    if CHECKPOINT_PATH.exists():
        with open(CHECKPOINT_PATH) as f:
            return json.load(f)
    return {"completed_cables": [], "phase": "not_started"}


def save_checkpoint(cp):
    """Save extraction checkpoint."""
    CABLE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHECKPOINT_PATH, "w") as f:
        json.dump(cp, f, indent=2)


def extract(conn, resume=False):
    """Main extraction: fetch all cables, then per-cable details."""

    # Ensure source column exists
    try:
        conn.execute("ALTER TABLE entities ADD COLUMN source TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass

    nation_index = build_nation_index(conn)

    # Load checkpoint
    cp = load_checkpoint() if resume else {"completed_cables": [], "phase": "not_started"}
    completed = set(cp["completed_cables"])

    # ─── Phase 1: Fetch cable list ───────────────────────────────────────

    print("\n╔══════════════════════════════════════╗")
    print("║  Phase 1: Fetch Cable List           ║")
    print("╚══════════════════════════════════════╝")

    cables = api_get("cable/all.json")
    if not cables:
        print("  ERROR: Could not fetch cable list")
        return
    print(f"  Total cables in API: {len(cables)}")

    # ─── Phase 2: Fetch landing point coordinates ────────────────────────

    print("\n╔══════════════════════════════════════╗")
    print("║  Phase 2: Fetch Landing Points       ║")
    print("╚══════════════════════════════════════╝")

    lp_geo = api_get("landing-point/landing-point-geo.json")
    lp_coords = {}
    if lp_geo and "features" in lp_geo:
        for f in lp_geo["features"]:
            lp_id = f["properties"]["id"]
            coords = f["geometry"]["coordinates"]
            lp_coords[lp_id] = (coords[1], coords[0])  # lat, lon
        print(f"  Landing points with coordinates: {len(lp_coords)}")
    else:
        print("  WARNING: Could not fetch landing point coordinates")

    # ─── Phase 3: Fetch per-cable details ────────────────────────────────

    print("\n╔══════════════════════════════════════╗")
    print("║  Phase 3: Fetch Cable Details        ║")
    print("╚══════════════════════════════════════╝")

    to_fetch = [c for c in cables if c["id"] not in completed]
    print(f"  To fetch: {len(to_fetch)} ({len(completed)} already done)")

    # Track MRGID assignments
    next_cable_mrgid = CABLE_MRGID_START
    next_lp_mrgid = LP_MRGID_START

    # Check existing synthetic IDs
    existing_cable_max = conn.execute(
        "SELECT MAX(mrgid) FROM entities WHERE mrgid >= ? AND mrgid < ?",
        (CABLE_MRGID_START, LP_MRGID_START)
    ).fetchone()[0]
    if existing_cable_max:
        next_cable_mrgid = existing_cable_max + 1

    existing_lp_max = conn.execute(
        "SELECT MAX(mrgid) FROM entities WHERE mrgid >= ?",
        (LP_MRGID_START,)
    ).fetchone()[0]
    if existing_lp_max:
        next_lp_mrgid = existing_lp_max + 1

    # Track landing points we've already created (avoid duplicates)
    existing_lps = {}
    for row in conn.execute(
        "SELECT mrgid, name FROM entities WHERE type='Landing Point'"
    ).fetchall():
        existing_lps[row[1].lower()] = row[0]

    cables_added = 0
    lps_added = 0
    rels_added = 0
    failed = []
    unmatched_countries = set()

    for i, cable in enumerate(to_fetch):
        cable_id = cable["id"]

        if i > 0 and i % 50 == 0:
            print(f"    Progress: {i}/{len(to_fetch)} "
                  f"(cables: {cables_added}, lps: {lps_added}, rels: {rels_added})")
            conn.commit()
            cp["completed_cables"] = list(completed)
            save_checkpoint(cp)

        # Fetch cable detail
        detail = api_get(f"cable/{cable_id}.json")
        time.sleep(REQUEST_DELAY)

        if not detail:
            failed.append(cable_id)
            continue

        # Parse fields
        length_km = parse_length_km(detail.get("length"))
        rfs_year = detail.get("rfs_year")
        is_planned = detail.get("is_planned", False)
        owners = detail.get("owners", "")
        suppliers = detail.get("suppliers", "")
        cable_url = detail.get("url")
        notes = detail.get("notes")
        landing_points = detail.get("landing_points", [])

        # Create cable entity
        cable_mrgid = next_cable_mrgid
        next_cable_mrgid += 1

        # Get representative coordinates from first landing point
        cable_lat, cable_lon = None, None
        if landing_points:
            first_lp_id = landing_points[0].get("id", "")
            if first_lp_id in lp_coords:
                cable_lat, cable_lon = lp_coords[first_lp_id]

        conn.execute("""
            INSERT OR REPLACE INTO entities
                (mrgid, name, type, tier, latitude, longitude, source, area_km2)
            VALUES (?, ?, 'Cable', 8, ?, ?, 'TeleGeography', ?)
        """, (cable_mrgid, detail["name"], cable_lat, cable_lon,
              length_km))
        cables_added += 1

        # Track countries this cable connects
        cable_countries = set()

        # Process landing points
        for lp in landing_points:
            lp_id = lp.get("id", "")
            lp_name = lp.get("name", "")
            lp_country = lp.get("country", "")

            # Get or create landing point entity
            lp_key = lp_name.lower().strip()
            if lp_key in existing_lps:
                lp_mrgid = existing_lps[lp_key]
            else:
                lp_mrgid = next_lp_mrgid
                next_lp_mrgid += 1

                lat, lon = lp_coords.get(lp_id, (None, None))
                conn.execute("""
                    INSERT OR REPLACE INTO entities
                        (mrgid, name, type, tier, latitude, longitude, source)
                    VALUES (?, ?, 'Landing Point', 8, ?, ?, 'TeleGeography')
                """, (lp_mrgid, lp_name, lat, lon))
                existing_lps[lp_key] = lp_mrgid
                lps_added += 1

            # Relationship: cable lands_at landing_point
            conn.execute("""
                INSERT INTO relationships
                    (source_mrgid, relationship, target_mrgid,
                     target_name, target_type, source_data)
                VALUES (?, 'lands_at', ?, ?, 'Landing Point', 'telegeography')
            """, (cable_mrgid, lp_mrgid, lp_name))
            rels_added += 1

            # Relationship: landing_point located_in nation
            if lp_country:
                nation_mrgid = resolve_country(lp_country, nation_index)
                if nation_mrgid:
                    # Only add if not already there for this LP
                    existing = conn.execute("""
                        SELECT 1 FROM relationships
                        WHERE source_mrgid = ? AND target_mrgid = ?
                            AND relationship = 'located_in'
                    """, (lp_mrgid, nation_mrgid)).fetchone()
                    if not existing:
                        nation_name = conn.execute(
                            "SELECT name FROM entities WHERE mrgid = ?",
                            (nation_mrgid,)
                        ).fetchone()[0]
                        conn.execute("""
                            INSERT INTO relationships
                                (source_mrgid, relationship, target_mrgid,
                                 target_name, target_type, source_data)
                            VALUES (?, 'located_in', ?, ?, 'Nation', 'telegeography')
                        """, (lp_mrgid, nation_mrgid, nation_name))
                        rels_added += 1

                    cable_countries.add((nation_mrgid, lp_country))
                else:
                    unmatched_countries.add(lp_country)

        # Relationship: cable connects nation (one per unique country)
        for nation_mrgid, country_name in cable_countries:
            nation_name = conn.execute(
                "SELECT name FROM entities WHERE mrgid = ?",
                (nation_mrgid,)
            ).fetchone()[0]
            conn.execute("""
                INSERT INTO relationships
                    (source_mrgid, relationship, target_mrgid,
                     target_name, target_type, source_data)
                VALUES (?, 'connects', ?, ?, 'Nation', 'telegeography')
            """, (cable_mrgid, nation_mrgid, nation_name))
            rels_added += 1

        completed.add(cable_id)

    # Final commit and checkpoint
    conn.commit()
    cp["completed_cables"] = list(completed)
    cp["phase"] = "done"
    save_checkpoint(cp)

    # ─── Report ──────────────────────────────────────────────────────────

    print(f"\n═══ Extraction Results ═══")
    print(f"  Cables added: {cables_added}")
    print(f"  Landing points added: {lps_added}")
    print(f"  Relationships added: {rels_added}")
    if failed:
        print(f"  Failed fetches: {len(failed)}")
        for f_id in failed[:10]:
            print(f"    {f_id}")
    if unmatched_countries:
        print(f"  Unmatched countries ({len(unmatched_countries)}):")
        for c in sorted(unmatched_countries):
            print(f"    {c}")


def print_stats(conn):
    """Show cable data in the database."""
    print("\n═══ Cable Data Statistics ═══")

    cables = conn.execute(
        "SELECT COUNT(*) FROM entities WHERE type='Cable'"
    ).fetchone()[0]
    lps = conn.execute(
        "SELECT COUNT(*) FROM entities WHERE type='Landing Point'"
    ).fetchone()[0]
    print(f"  Cable entities: {cables}")
    print(f"  Landing point entities: {lps}")

    print("\n  Relationships:")
    for row in conn.execute("""
        SELECT relationship, COUNT(*) FROM relationships
        WHERE source_data = 'telegeography'
        GROUP BY relationship ORDER BY COUNT(*) DESC
    """).fetchall():
        print(f"    {row[0]}: {row[1]}")

    # Countries with most cables
    print("\n  Top 15 countries by cable count:")
    for row in conn.execute("""
        SELECT r.target_name, COUNT(*) as c
        FROM relationships r
        WHERE r.relationship = 'connects' AND r.source_data = 'telegeography'
        GROUP BY r.target_name
        ORDER BY c DESC LIMIT 15
    """).fetchall():
        print(f"    {row[0]}: {row[1]} cables")

    # Largest cables
    print("\n  Top 10 cables by landing points:")
    for row in conn.execute("""
        SELECT e.name, COUNT(*) as c
        FROM relationships r
        JOIN entities e ON r.source_mrgid = e.mrgid
        WHERE r.relationship = 'lands_at' AND r.source_data = 'telegeography'
        GROUP BY e.name
        ORDER BY c DESC LIMIT 10
    """).fetchall():
        print(f"    {row[0]}: {row[1]} landing points")

    # Total entities and relationships in DB
    total_e = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    total_r = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    print(f"\n  Total DB entities: {total_e:,}")
    print(f"  Total DB relationships: {total_r:,}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Extract submarine cables from TeleGeography")
    parser.add_argument("--stats", action="store_true", help="Show cable stats")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = parser.parse_args()

    conn = get_db()

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    extract(conn, resume=args.resume)
    print_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
