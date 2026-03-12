#!/usr/bin/env python3
"""
Marine Regions Global Database Extractor

Builds a structured SQLite graph database from the Marine Regions gazetteer API.
Entities + relationships across political, water, seafloor, ecological tiers.

Usage:
    python3 extract_marine_regions.py              # Run all phases
    python3 extract_marine_regions.py --phase 1    # Run specific phase
    python3 extract_marine_regions.py --resume      # Resume from last checkpoint
"""

import json
import os
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ─── Configuration ───────────────────────────────────────────────────────────

BASE_URL = "https://www.marineregions.org/rest"
DATA_DIR = Path(__file__).parent / "data" / "marine_regions"
DB_PATH = DATA_DIR / "global_map.db"
CHECKPOINT_PATH = DATA_DIR / "checkpoint.json"

# Rate limiting: be respectful to the API
REQUEST_DELAY = 1.0  # seconds between requests
REQUEST_TIMEOUT = 30  # seconds per request
MAX_RETRIES = 3

# ─── Entity type mapping: plan tier → API type names → our normalized type ──

ENTITY_TYPES = {
    # Tier 1: Political & Land
    "Nation":           {"api_names": ["Nation"], "tier": 1},
    "Territory":        {"api_names": ["Dependent State", "Disputed Territory",
                                        "Union Territory", "Possession", "Territory",
                                        "Occupied Territory", "Dependency",
                                        "Overseas Territory"], "tier": 1},
    "Continent":        {"api_names": ["Continent"], "tier": 1},
    "Island":           {"api_names": ["Island"], "tier": 1},
    "Island Group":     {"api_names": ["Island Group", "Archipelago"], "tier": 1},
    "Peninsula":        {"api_names": ["Peninsula"], "tier": 1},
    "Isthmus":          {"api_names": ["Isthmus"], "tier": 1},
    "Cape":             {"api_names": ["Cape"], "tier": 1},
    "Coast":            {"api_names": ["Coast"], "tier": 1},

    # Tier 2: Water Bodies
    "Ocean":            {"api_names": ["Ocean"], "tier": 2},
    "Sea":              {"api_names": ["Sea", "IHO Sea Area", "General Sea Area"], "tier": 2},
    "Gulf":             {"api_names": ["Gulf"], "tier": 2},
    "Bay":              {"api_names": ["Bay", "Bight"], "tier": 2},
    "Strait":           {"api_names": ["Strait"], "tier": 2},
    "Channel":          {"api_names": ["Channel"], "tier": 2},
    "Sound":            {"api_names": ["Sound"], "tier": 2},
    "Fjord":            {"api_names": ["Fjord"], "tier": 2},
    "Lagoon":           {"api_names": ["Lagoon"], "tier": 2},

    # Tier 3: Fresh Water
    "River":            {"api_names": ["River", "Stream"], "tier": 3},
    "Lake":             {"api_names": ["Lake"], "tier": 3},
    "Estuary":          {"api_names": ["Estuary"], "tier": 3},
    "Delta":            {"api_names": ["Delta"], "tier": 3},
    "Canal":            {"api_names": ["Canal"], "tier": 3},

    # Tier 4: Seafloor
    "Ridge":            {"api_names": ["Ridge"], "tier": 4},
    "Trench":           {"api_names": ["Trench"], "tier": 4},
    "Basin":            {"api_names": ["Basin"], "tier": 4},
    "Seamount":         {"api_names": ["Seamount(s)", "Seamount Chain"], "tier": 4},
    "Abyssal Plain":    {"api_names": ["Abyssal Plain"], "tier": 4},
    "Plateau":          {"api_names": ["Plateau"], "tier": 4},
    "Canyon":           {"api_names": ["Canyon(s)"], "tier": 4},
    "Fracture Zone":    {"api_names": ["Fracture Zone"], "tier": 4},
    "Trough":           {"api_names": ["Trough"], "tier": 4},
    "Rise":             {"api_names": ["Rise"], "tier": 4},
    "Fan":              {"api_names": ["Fan"], "tier": 4},
    "Valley":           {"api_names": ["Valley"], "tier": 4},
    "Deep":             {"api_names": ["Deep"], "tier": 4},
    "Hill":             {"api_names": ["Hill(s)"], "tier": 4},
    "Knoll":            {"api_names": ["Knoll(s)"], "tier": 4},
    "Guyot":            {"api_names": ["Guyot"], "tier": 4},
    "Caldera":          {"api_names": ["Caldera"], "tier": 4},
    "Spur":             {"api_names": ["Spur"], "tier": 4},
    "Escarpment":       {"api_names": ["Escarpment"], "tier": 4},
    "Sill":             {"api_names": ["Sill"], "tier": 4},
    "Saddle":           {"api_names": ["Saddle"], "tier": 4},
    "Reef":             {"api_names": ["Reef"], "tier": 4},
    "Bank":             {"api_names": ["Bank"], "tier": 4},
    "Shoal":            {"api_names": ["Shoal"], "tier": 4},
    "Continental Shelf": {"api_names": ["Continental Shelf (Physical)"], "tier": 4},
    "Continental Slope": {"api_names": ["Continental Slope"], "tier": 4},
    "Continental Margin": {"api_names": ["Continental Margin"], "tier": 4},

    # Tier 6: Maritime Zones
    "EEZ":              {"api_names": ["EEZ"], "tier": 6},
    "Territorial Sea":  {"api_names": ["Territorial Sea"], "tier": 6},
    "High Seas":        {"api_names": ["High Seas"], "tier": 6},
    "Extended Continental Shelf": {
        "api_names": ["Extended Continental Shelf (CLCS Submission)",
                      "Extended Continental Shelf (CLCS Recommendation)",
                      "Extended Continental Shelf (DOALOS Deposit)"],
        "tier": 6
    },

    # Tier 7: Ecological & Protected
    "LME":              {"api_names": ["Large Marine Ecosystem"], "tier": 7},
    "Marine Ecoregion":  {"api_names": ["Marine Ecoregion of the World (MEOW)"], "tier": 7},
    "Longhurst Province": {"api_names": ["Longhurst Province"], "tier": 7},
    "Freshwater Ecoregion": {"api_names": ["Freshwater Ecoregion of the World (FEOW)"], "tier": 7},
    "FAO Fishing Area":  {"api_names": ["FAO fishing area", "FAO Major Marine Fishing Areas",
                                          "FAO Subareas", "FAO Divisions", "FAO Subdivisions"], "tier": 7},
    "ICES Area":         {"api_names": ["ICES Ecoregion", "ICES Areas", "ICES Statistical Rectangles"], "tier": 7},
    "NAFO Area":         {"api_names": ["NAFO Area"], "tier": 7},
    "MPA":               {"api_names": ["Marine Protected Area (MPA)"], "tier": 7},
    "Natura 2000":       {"api_names": [
        "Natura 2000 Special Protection Area (SPA, EU Birds Directive)",
        "Natura 2000 Site of Community Importance (SCI, EU Habitats Directive)",
        "Natura 2000 Special Protection Area and Site of Community Importance (SPA and SCI, EU Birds and Habitats Directive)"
    ], "tier": 7},
    "World Heritage Marine": {"api_names": ["World Marine Heritage Site"], "tier": 7},
    "National Park":     {"api_names": ["National Park"], "tier": 7},
    "Natural Reserve":   {"api_names": ["Natural Reserve"], "tier": 7},
    "Marine Park":       {"api_names": ["Marine Park"], "tier": 7},
    "OSPAR Region":      {"api_names": ["OSPAR Boundary", "OSPAR Region"], "tier": 7},
}


# ─── API Client ──────────────────────────────────────────────────────────────

class MarineRegionsAPI:
    """Thin wrapper around the Marine Regions REST API."""

    def __init__(self):
        self.request_count = 0
        self.last_request_time = 0

    def _rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

    def _get(self, endpoint, retries=MAX_RETRIES):
        """Make a GET request with rate limiting and retries."""
        self._rate_limit()
        url = f"{BASE_URL}/{endpoint}"

        for attempt in range(retries):
            try:
                req = urllib.request.Request(url, headers={
                    "Accept": "application/json",
                    "User-Agent": "MarineRegionsExtractor/1.0 (research project)"
                })
                self.last_request_time = time.time()
                self.request_count += 1
                resp = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
                data = resp.read().decode("utf-8")
                if not data.strip():
                    return []
                return json.loads(data)
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return []
                if e.code == 503 and attempt < retries - 1:
                    wait = (attempt + 1) * 5
                    print(f"    503 — retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                raise
            except (TimeoutError, OSError) as e:
                if attempt < retries - 1:
                    wait = (attempt + 1) * 3
                    print(f"    Timeout — retrying in {wait}s...")
                    time.sleep(wait)
                    continue
                print(f"    Failed after {retries} attempts: {e}")
                return []
        return []

    def get_records_by_type(self, type_name, offset=0, count=100):
        """Get gazetteer records by type name. Returns list of records."""
        encoded = urllib.parse.quote(type_name)
        return self._get(f"getGazetteerRecordsByType.json/{encoded}/?offset={offset}&count={count}")

    def get_all_records_by_type(self, type_name):
        """Paginate through all records of a type."""
        all_records = []
        offset = 0
        page_size = 100
        while True:
            batch = self.get_records_by_type(type_name, offset=offset, count=page_size)
            if not batch:
                break
            all_records.extend(batch)
            if len(batch) < page_size:
                break
            offset += page_size
        return all_records

    def get_relationships(self, mrgid):
        """Get all relationships for an entity by MRGID."""
        return self._get(f"getGazetteerRelationsByMRGID.json/{mrgid}/")

    def get_record(self, mrgid):
        """Get a single record by MRGID."""
        return self._get(f"getGazetteerRecordByMRGID.json/{mrgid}/")

    def get_names(self, mrgid):
        """Get all names for an entity."""
        return self._get(f"getGazetteerNamesByMRGID.json/{mrgid}/")


# ─── Database ────────────────────────────────────────────────────────────────

def init_db(db_path):
    """Create SQLite database with schema."""
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS entities (
            mrgid INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            tier INTEGER,
            latitude REAL,
            longitude REAL,
            min_lat REAL,
            min_lon REAL,
            max_lat REAL,
            max_lon REAL,
            source TEXT,
            iso_code TEXT,
            area_km2 REAL,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS relationships (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_mrgid INTEGER REFERENCES entities(mrgid),
            relationship TEXT NOT NULL,
            target_mrgid INTEGER REFERENCES entities(mrgid),
            target_name TEXT,
            target_type TEXT,
            attr_name TEXT,
            attr_value TEXT
        );

        CREATE TABLE IF NOT EXISTS entity_names (
            mrgid INTEGER REFERENCES entities(mrgid),
            name TEXT,
            language TEXT,
            is_preferred BOOLEAN
        );

        CREATE INDEX IF NOT EXISTS idx_entities_type ON entities(type);
        CREATE INDEX IF NOT EXISTS idx_entities_tier ON entities(tier);
        CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationships(source_mrgid);
        CREATE INDEX IF NOT EXISTS idx_relationships_target ON relationships(target_mrgid);
        CREATE INDEX IF NOT EXISTS idx_relationships_type ON relationships(relationship);
        CREATE INDEX IF NOT EXISTS idx_entity_names_mrgid ON entity_names(mrgid);
    """)
    conn.commit()
    return conn


def insert_entity(conn, record, normalized_type, tier):
    """Insert or update an entity record."""
    conn.execute("""
        INSERT OR REPLACE INTO entities
            (mrgid, name, type, tier, latitude, longitude,
             min_lat, min_lon, max_lat, max_lon, source, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        record["MRGID"],
        record.get("preferredGazetteerName", ""),
        normalized_type,
        tier,
        record.get("latitude"),
        record.get("longitude"),
        record.get("minLatitude"),
        record.get("minLongitude"),
        record.get("maxLatitude"),
        record.get("maxLongitude"),
        record.get("gazetteerSource"),
        record.get("status"),
    ))


def insert_relationship(conn, source_mrgid, rel_type, target):
    """Insert a relationship record."""
    conn.execute("""
        INSERT INTO relationships
            (source_mrgid, relationship, target_mrgid, target_name, target_type)
        VALUES (?, ?, ?, ?, ?)
    """, (
        source_mrgid,
        rel_type,
        target.get("MRGID"),
        target.get("preferredGazetteerName"),
        target.get("placeType"),
    ))


# ─── Checkpoint ──────────────────────────────────────────────────────────────

def load_checkpoint():
    if CHECKPOINT_PATH.exists():
        return json.loads(CHECKPOINT_PATH.read_text())
    return {"completed_types": [], "completed_relationships": [], "phase": 0}


def save_checkpoint(state):
    CHECKPOINT_PATH.write_text(json.dumps(state, indent=2))


# ─── Phase 1: Entity Extraction ─────────────────────────────────────────────

def extract_entities(conn, api, tiers=None, resume_state=None):
    """Extract all entities from specified tiers (or all)."""
    state = resume_state or load_checkpoint()
    completed = set(state.get("completed_types", []))

    total_inserted = 0

    for norm_type, config in ENTITY_TYPES.items():
        if tiers and config["tier"] not in tiers:
            continue

        for api_name in config["api_names"]:
            key = f"{norm_type}::{api_name}"
            if key in completed:
                continue

            print(f"  Fetching {api_name} → {norm_type} (tier {config['tier']})...")
            records = api.get_all_records_by_type(api_name)

            if not records:
                print(f"    No records found")
            else:
                count = 0
                for rec in records:
                    if rec.get("MRGID") and rec.get("preferredGazetteerName"):
                        insert_entity(conn, rec, norm_type, config["tier"])
                        count += 1
                conn.commit()
                print(f"    Inserted {count} entities")
                total_inserted += count

            completed.add(key)
            state["completed_types"] = list(completed)
            save_checkpoint(state)

    return total_inserted


# ─── Phase 2: Relationship Extraction ───────────────────────────────────────

def extract_relationships(conn, api, tiers=None, resume_state=None):
    """For each entity, fetch its relationships from the API."""
    state = resume_state or load_checkpoint()
    completed = set(state.get("completed_relationships", []))

    # Get entities to process
    if tiers:
        placeholders = ",".join("?" * len(tiers))
        rows = conn.execute(
            f"SELECT mrgid, name, type FROM entities WHERE tier IN ({placeholders})",
            tiers
        ).fetchall()
    else:
        rows = conn.execute("SELECT mrgid, name, type FROM entities").fetchall()

    total = len(rows)
    inserted = 0

    for i, (mrgid, name, etype) in enumerate(rows):
        if str(mrgid) in completed:
            continue

        if i % 50 == 0:
            print(f"  Relationships: {i}/{total} entities processed, {inserted} relationships found...")

        rels = api.get_relationships(mrgid)
        if rels:
            for rel in rels:
                rel_type = rel.get("placeType", "related_to")
                # The relationship endpoint returns the related entity info
                # The relationship type is encoded in how the records relate
                insert_relationship(conn, mrgid, rel_type, rel)
                inserted += 1
            conn.commit()

        completed.add(str(mrgid))
        if i % 20 == 0:
            state["completed_relationships"] = list(completed)
            save_checkpoint(state)

    state["completed_relationships"] = list(completed)
    save_checkpoint(state)
    return inserted


# ─── Phase 2b: Classify relationships from API response ─────────────────────

def classify_relationship(source_type, target_type, target_name):
    """
    The Marine Regions relationship API returns related entities but doesn't
    explicitly label the relationship type. We infer it from context.
    """
    # Part-of hierarchies
    hierarchy_parents = {"Ocean", "Sea", "IHO Sea Area", "General Sea Area",
                         "Continent", "Nation", "EEZ"}
    if target_type in hierarchy_parents:
        return "part_of"

    # Contains
    if source_type in hierarchy_parents:
        return "contains"

    return "related_to"


# ─── Main ────────────────────────────────────────────────────────────────────

def print_stats(conn):
    """Print database statistics."""
    print("\n═══ Database Statistics ═══")
    total = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    print(f"Total entities: {total}")

    print("\nBy tier:")
    for row in conn.execute(
        "SELECT tier, COUNT(*) FROM entities GROUP BY tier ORDER BY tier"
    ).fetchall():
        print(f"  Tier {row[0]}: {row[1]} entities")

    print("\nBy type (top 20):")
    for row in conn.execute(
        "SELECT type, COUNT(*) FROM entities GROUP BY type ORDER BY COUNT(*) DESC LIMIT 20"
    ).fetchall():
        print(f"  {row[0]}: {row[1]}")

    rel_count = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    print(f"\nTotal relationships: {rel_count}")

    if rel_count > 0:
        print("\nRelationship types:")
        for row in conn.execute(
            "SELECT relationship, COUNT(*) FROM relationships GROUP BY relationship ORDER BY COUNT(*) DESC LIMIT 15"
        ).fetchall():
            print(f"  {row[0]}: {row[1]}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Marine Regions Global Database Extractor")
    parser.add_argument("--phase", type=int, help="Run specific phase (1-8)")
    parser.add_argument("--tier", type=int, action="append", help="Process specific tier(s)")
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    parser.add_argument("--stats", action="store_true", help="Print DB stats and exit")
    parser.add_argument("--relationships-only", action="store_true",
                        help="Only extract relationships for existing entities")
    args = parser.parse_args()

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = init_db(DB_PATH)
    api = MarineRegionsAPI()
    state = load_checkpoint() if args.resume else None

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    tiers = args.tier if args.tier else None

    # Determine which phases to run
    if args.relationships_only:
        phases = [2]
    elif args.phase:
        phases = [args.phase]
    else:
        phases = [1, 2]

    for phase in phases:
        if phase == 1:
            print("\n╔══════════════════════════════════════╗")
            print("║  Phase 1: Entity Extraction          ║")
            print("╚══════════════════════════════════════╝")
            count = extract_entities(conn, api, tiers=tiers, resume_state=state)
            print(f"\nPhase 1 complete: {count} entities inserted")
            print(f"API requests made: {api.request_count}")

        elif phase == 2:
            print("\n╔══════════════════════════════════════╗")
            print("║  Phase 2: Relationship Extraction    ║")
            print("╚══════════════════════════════════════╝")
            count = extract_relationships(conn, api, tiers=tiers, resume_state=state)
            print(f"\nPhase 2 complete: {count} relationships inserted")
            print(f"API requests made: {api.request_count}")

    print_stats(conn)
    conn.close()
    print(f"\nDatabase saved to: {DB_PATH}")
    print(f"Total API requests: {api.request_count}")


if __name__ == "__main__":
    main()
