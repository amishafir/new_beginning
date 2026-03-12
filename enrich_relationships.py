#!/usr/bin/env python3
"""
Enrich the Marine Regions database with inferred relationships.

Strategy #1: Point-in-bbox → `located_in`
    For each entity with coordinates, find the smallest water body / nation
    whose bounding box contains that point.

Strategy #2: Name parsing → `claimed_by`
    Parse EEZ and Territorial Sea names to match them to nations.

Usage:
    python3 enrich_relationships.py             # Run both strategies
    python3 enrich_relationships.py --located   # Only point-in-bbox
    python3 enrich_relationships.py --claimed   # Only name parsing
    python3 enrich_relationships.py --stats     # Print stats
"""

import sqlite3
import sys
import re
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "marine_regions" / "global_map.db"

# Maximum bbox area (°²) for a container to be considered.
# Filters out global/hemispheric regions like "Atlantic Ocean" (13,249°²)
# that would match everything.
MAX_CONTAINER_AREA = 5000


# ─── Strategy #1: Point-in-bbox containment ──────────────────────────────────

# Which entity types should be matched to which container types
MATCH_RULES = {
    # Seafloor features → which water body are they in?
    "Seamount":           ["Sea", "Gulf", "Ocean"],
    "Canyon":             ["Sea", "Gulf", "Ocean"],
    "Ridge":              ["Sea", "Gulf", "Ocean"],
    "Trench":             ["Sea", "Gulf", "Ocean"],
    "Basin":              ["Sea", "Gulf", "Ocean"],
    "Abyssal Plain":      ["Sea", "Gulf", "Ocean"],
    "Plateau":            ["Sea", "Gulf", "Ocean"],
    "Fracture Zone":      ["Sea", "Gulf", "Ocean"],
    "Trough":             ["Sea", "Gulf", "Ocean"],
    "Rise":               ["Sea", "Gulf", "Ocean"],
    "Fan":                ["Sea", "Gulf", "Ocean"],
    "Valley":             ["Sea", "Gulf", "Ocean"],
    "Deep":               ["Sea", "Gulf", "Ocean"],
    "Hill":               ["Sea", "Gulf", "Ocean"],
    "Knoll":              ["Sea", "Gulf", "Ocean"],
    "Guyot":              ["Sea", "Gulf", "Ocean"],
    "Caldera":            ["Sea", "Gulf", "Ocean"],
    "Spur":               ["Sea", "Gulf", "Ocean"],
    "Escarpment":         ["Sea", "Gulf", "Ocean"],
    "Sill":               ["Sea", "Gulf", "Ocean"],
    "Saddle":             ["Sea", "Gulf", "Ocean"],
    "Reef":               ["Sea", "Gulf", "Ocean"],
    "Bank":               ["Sea", "Gulf", "Ocean"],
    "Shoal":              ["Sea", "Gulf", "Ocean"],
    "Continental Shelf":  ["Sea", "Gulf", "Ocean"],
    "Continental Slope":  ["Sea", "Gulf", "Ocean"],
    "Continental Margin": ["Sea", "Gulf", "Ocean"],
    # Islands → which nation AND which water body?
    "Island":             ["Nation", "Sea", "Gulf", "Ocean"],
    "Island Group":       ["Nation", "Sea", "Gulf", "Ocean"],
    # Land features → which nation?
    "Cape":               ["Nation"],
    "Peninsula":          ["Nation"],
    "Coast":              ["Nation"],
    "Isthmus":            ["Nation"],
    # Fresh water → which nation?
    "River":              ["Nation"],
    "Lake":               ["Nation"],
    "Estuary":            ["Nation", "Sea", "Gulf"],
    "Delta":              ["Nation", "Sea", "Gulf"],
    "Canal":              ["Nation"],
    "Lagoon":             ["Nation", "Sea", "Gulf"],
    # Water body sub-features → which larger water body?
    "Bay":                ["Sea", "Gulf", "Ocean"],
    "Fjord":              ["Sea", "Ocean"],
    "Sound":              ["Sea", "Ocean"],
    "Channel":            ["Sea", "Ocean"],
    "Strait":             ["Sea", "Ocean"],
    "Gulf":               ["Sea", "Ocean"],
    # Ecological → which water body?
    "MPA":                ["Sea", "Gulf", "Ocean"],
    "Marine Park":        ["Sea", "Gulf", "Ocean"],
    "World Heritage Marine": ["Sea", "Gulf", "Ocean"],
    "Natural Reserve":    ["Nation"],
    "National Park":      ["Nation"],
}


def build_container_index(conn):
    """
    Build a spatial index of potential containers.
    Returns dict: container_type → list of (mrgid, name, min_lat, min_lon, max_lat, max_lon, area)
    Sorted by area ascending (smallest first) for efficient smallest-match.
    """
    container_types = set()
    for targets in MATCH_RULES.values():
        container_types.update(targets)

    index = {}
    for ctype in container_types:
        rows = conn.execute("""
            SELECT mrgid, name, min_lat, min_lon, max_lat, max_lon,
                   (max_lat - min_lat) * (max_lon - min_lon) as area
            FROM entities
            WHERE type = ? AND min_lat IS NOT NULL
              AND (max_lat - min_lat) * (max_lon - min_lon) < ?
              AND (max_lat - min_lat) > 0.01
              AND (max_lon - min_lon) > 0.01
            ORDER BY area ASC
        """, (ctype, MAX_CONTAINER_AREA)).fetchall()
        index[ctype] = rows

    return index


def find_smallest_container(lat, lon, containers):
    """Find the smallest container bbox that contains the point."""
    for mrgid, name, min_lat, min_lon, max_lat, max_lon, area in containers:
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return mrgid, name
    return None, None


def run_located_in(conn):
    """Compute located_in relationships via point-in-bbox."""
    print("  Building container index...")
    index = build_container_index(conn)
    for ctype, containers in index.items():
        print(f"    {ctype}: {len(containers)} containers")

    # Clear previous located_in
    conn.execute("DELETE FROM relationships WHERE source_data = 'located_in'")

    # Get all entities that need matching
    total_inserted = 0
    total_processed = 0

    for entity_type, container_types in MATCH_RULES.items():
        entities = conn.execute("""
            SELECT mrgid, name, latitude, longitude
            FROM entities
            WHERE type = ? AND latitude IS NOT NULL
        """, (entity_type,)).fetchall()

        if not entities:
            continue

        type_inserted = 0

        for mrgid, name, lat, lon in entities:
            for ctype in container_types:
                containers = index.get(ctype, [])
                c_mrgid, c_name = find_smallest_container(lat, lon, containers)
                if c_mrgid and c_mrgid != mrgid:
                    conn.execute("""
                        INSERT INTO relationships
                            (source_mrgid, relationship, target_mrgid,
                             target_name, target_type, source_data)
                        VALUES (?, 'located_in', ?, ?, ?, 'located_in')
                    """, (mrgid, c_mrgid, c_name, ctype))
                    type_inserted += 1

        total_processed += len(entities)
        total_inserted += type_inserted

        if type_inserted > 0:
            print(f"    {entity_type}: {len(entities)} entities → {type_inserted} located_in")

        # Commit per type to avoid huge transactions
        conn.commit()

    return total_inserted


# ─── Strategy #2: Name parsing for EEZ/Territorial Sea → Nation ──────────────

# Adjective → Nation name mapping (for the non-obvious ones)
ADJECTIVE_TO_NATION = {
    "belgian": "België",
    "dutch": "Nederland",
    "french": "Frankrijk",
    "german": "Germany",
    "british": "United Kingdom",
    "danish": "Denmark",
    "spanish": "Spain",
    "portuguese": "Portugal",
    "italian": "Italy",
    "greek": "Greece",
    "turkish": "Türkiye",
    "swedish": "Sweden",
    "norwegian": "Norway",
    "finnish": "Finland",
    "polish": "Poland",
    "romanian": "Romania",
    "irish": "Ireland",
    "cypriot": "Cyprus",
    "maltese": "Malta",
    "icelandic": "Iceland",
    "faroese": "Faroe Islands",
    "latvian": "Latvia",
    "lithuanian": "Lithuania",
    "estonian": "Estonia",
    "slovenian": "Slovenia",
    "montenegrin": "Montenegro",
    "albanian": "Albania",
    "croatian": "Croatia",
    "bulgarian": "Bulgaria",
    "georgian": "Georgia",
    "ukrainian": "Ukraine",
    "russian": "Russia",
    "israeli": "Israel",
    "egyptian": "Egypt",
    "moroccan": "Morocco",
    "tunisian": "Tunisia",
    "algerian": "Algeria",
    "libyan": "Libya",
    "lebanese": "Lebanon",
    "syrian": "Syria",
    "saudi arabian": "Saudi Arabia",
    "emirati": "United Arab Emirates",
    "qatari": "Qatar",
    "bahraini": "Bahrain",
    "kuwaiti": "Kuwait",
    "omani": "Oman",
    "yemeni": "Yemen",
    "iranian": "Iran",
    "iraqi": "Iraq",
    "pakistani": "Pakistan",
    "indian": "India",
    "bangladeshi": "Bangladesh",
    "sri lankan": "Sri Lanka",
    "myanmarese": "Myanmar",
    "thai": "Thailand",
    "vietnamese": "Vietnam",
    "cambodian": "Cambodia",
    "malaysian": "Malaysia",
    "singaporean": "Singapore",
    "indonesian": "Indonesia",
    "filipino": "Philippines",
    "chinese": "China",
    "taiwanese": "Taiwan",
    "japanese": "Japan",
    "south korean": "South Korea",
    "north korean": "North Korea",
    "australian": "Australia",
    "new zealand": "New Zealand",  # not adjective form
    "fijian": "Fiji",
    "tongan": "Tonga",
    "samoan": "Samoa",
    "american samoan": "American Samoa",
    "papuan": "Papua New Guinea",
    "canadian": "Canada",
    "american": "United States",
    "mexican": "Mexico",
    "guatemalan": "Guatemala",
    "honduran": "Honduras",
    "salvadoran": "El Salvador",
    "nicaraguan": "Nicaragua",
    "costa rican": "Costa Rica",
    "panamanian": "Panama",
    "colombian": "Colombia",
    "venezuelan": "Venezuela",
    "ecuadorian": "Ecuador",
    "peruvian": "Peru",
    "chilean": "Chile",
    "argentinian": "Argentina",
    "brazilian": "Brazil",
    "uruguayan": "Uruguay",
    "guyanese": "Guyana",
    "surinamese": "Surinam",
    "cuban": "Cuba",
    "jamaican": "Jamaica",
    "haitian": "Haiti",
    "dominican": "Dominican Republic",
    "bahamian": "Bahamas",
    "trinidadian and tobagonian": "Trinidad and Tobago",
    "barbadian": "Barbados",
    "antiguan and barbudan": "Antigua and Barbuda",
    "vincentian": "Saint Vincent and the Grenadines",
    "grenadian": "Grenada",
    "kittitian and nevisian": "Saint Kitts and Nevis",
    "lucian": "Saint Lucia",
    "south african": "South Africa",
    "namibian": "Namibia",
    "angolan": "Angola",
    "congolese": "Republic of the Congo",
    "gabonese": "Gabon",
    "cameroonian": "Cameroon",
    "nigerian": "Nigeria",
    "ghanaian": "Ghana",
    "togolese": "Togo",
    "beninese": "Benin",
    "ivorian": "Côte d'Ivoire",
    "guinean": "Guinea",
    "sierra leonean": "Sierra Leone",
    "liberian": "Liberia",
    "senegalese": "Senegal",
    "gambian": "Gambia",
    "mauritanian": "Mauritania",
    "cape verdean": "Cabo Verde",
    "kenyan": "Kenya",
    "tanzanian": "Tanzania",
    "mozambican": "Mozambique",
    "malagasy": "Madagascar",
    "mauritian": "Mauritius",
    "comorian": "Comoros",
    "seychellois": "Seychelles",
    "somali": "Federal Republic of Somalia",
    "djiboutian": "Djibouti",
    "eritrean": "Eritrea",
    "sudanese": "Sudan",
    "gibraltarian": "Gibraltar",
    "bermudian": "Bermuda",
    "greenlandic": "Greenland",
    "irish exclusive economic zone": "Ireland",  # typo in source data (lowercase 'e')
    "irish": "Ireland",
    "timorese": "East Timor",
    "monégasque": "Monaco",
    "bissau-guinean": "Guinea-Bissau",
    "são toméan": "São Tomé and Príncipe",
    "cabo verdean": "Cabo Verde",
    # Compound names that don't use adjectives
    "united states": "United States",
    "united kingdom": "United Kingdom",
    "new zealand": "New Zealand",
    "solomon islands": "Solomon Islands",
    "marshall islands": "Marshall Islands",
    "cook islands": "Cook Islands",
    "cabo verde": "Cabo Verde",
    "são tomé and príncipe": "São Tomé and Príncipe",
    "equatorial guinean": "Equatorial Guinea",
    "guinea-bissauan": "Guinea-Bissau",
    "east timorese": "East Timor",
    "maldivian": "Maldives",
    "ni-vanuatu": "Vanuatu",
    "palauan": "Palau",
    "nauruan": "Nauru",
    "kiribati": "Kiribati",
    "tuvaluan": "Tuvalu",
    "micronesian": "Micronesia",
}


def build_nation_index(conn):
    """Build name→mrgid index for nations and territories."""
    index = {}
    rows = conn.execute("""
        SELECT mrgid, name FROM entities WHERE type IN ('Nation', 'Territory')
    """).fetchall()
    for mrgid, name in rows:
        index[name.lower()] = mrgid
        index[name] = mrgid
    return index


def parse_zone_nation(zone_name, zone_type):
    """
    Extract the nation adjective/name from an EEZ or Territorial Sea name.
    Returns the adjective string or None.
    """
    if zone_type == "EEZ":
        # "Albanian Exclusive Economic Zone" → "Albanian"
        # "Area of overlap between X and Y" → skip
        if zone_name.startswith("Area of overlap"):
            return None
        if zone_name.startswith("Joint regime"):
            return None
        if zone_name.startswith("Conflict Zone"):
            return None
        # Handle case variations in source data
        adj = re.sub(r'\s+[Ee]xclusive\s+[Ee]conomic\s+[Zz]one', '', zone_name)
        # Handle parenthetical territories: "Australian Exclusive Economic Zone (Christmas Island)"
        adj = re.sub(r'\s*\(.*\)$', '', adj).strip()
        return adj

    elif zone_type == "Territorial Sea":
        # "Albanian 12 NM" → "Albanian"
        # "Danish 12 NM (Faeroe)" → strip parens first → "Danish 12 NM" → "Danish"
        adj = re.sub(r'\s*\(.*?\)', '', zone_name).strip()
        adj = re.sub(r'\s+12\s*NM$', '', adj).strip()
        return adj

    return None


def run_claimed_by(conn):
    """Parse EEZ/Territorial Sea names to create claimed_by relationships."""
    nation_index = build_nation_index(conn)

    # Clear previous
    conn.execute("DELETE FROM relationships WHERE source_data = 'claimed_by'")

    zones = conn.execute("""
        SELECT mrgid, name, type FROM entities
        WHERE type IN ('EEZ', 'Territorial Sea')
    """).fetchall()

    inserted = 0
    unmatched = []

    for z_mrgid, z_name, z_type in zones:
        adj = parse_zone_nation(z_name, z_type)
        if not adj:
            continue

        adj_lower = adj.lower()

        # Try adjective map first
        nation_name = ADJECTIVE_TO_NATION.get(adj_lower)
        nation_mrgid = None

        if nation_name:
            nation_mrgid = nation_index.get(nation_name) or nation_index.get(nation_name.lower())

        # Fallback: try direct name match
        if not nation_mrgid:
            nation_mrgid = nation_index.get(adj) or nation_index.get(adj_lower)

        # Fallback: try the adjective as a substring of nation names
        if not nation_mrgid:
            # "Comorian" → try to match "Comoros" by checking if nation starts similarly
            for nname, nmrgid in nation_index.items():
                if isinstance(nname, str) and adj_lower[:4] == nname.lower()[:4] and len(adj_lower) > 3:
                    nation_mrgid = nmrgid
                    break

        if nation_mrgid:
            conn.execute("""
                INSERT INTO relationships
                    (source_mrgid, relationship, target_mrgid,
                     target_name, target_type, source_data)
                VALUES (?, 'claimed_by', ?, ?, 'Nation', 'claimed_by')
            """, (z_mrgid, nation_mrgid,
                  nation_name or adj))
            inserted += 1
        else:
            unmatched.append((z_name, adj))

    conn.commit()

    if unmatched:
        print(f"  Could not match {len(unmatched)} zones:")
        for z_name, adj in unmatched[:10]:
            print(f"    {z_name}  →  \"{adj}\"")

    return inserted


# ─── Stats ───────────────────────────────────────────────────────────────────

def print_stats(conn):
    total_ent = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    total_rel = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    with_rels = conn.execute("""
        SELECT COUNT(DISTINCT x) FROM (
            SELECT source_mrgid as x FROM relationships
            UNION SELECT target_mrgid as x FROM relationships
        )
    """).fetchone()[0]

    print(f"\n═══ Enriched Database Stats ═══")
    print(f"Total entities: {total_ent:,}")
    print(f"Total relationships: {total_rel:,}")
    print(f"Entities with relationships: {with_rels:,}/{total_ent:,} ({with_rels*100//total_ent}%)")

    print(f"\nBy relationship type:")
    for r in conn.execute("""
        SELECT relationship, source_data, COUNT(*) as c
        FROM relationships GROUP BY relationship, source_data ORDER BY c DESC
    """).fetchall():
        print(f"  {r[0]} ({r[1]}): {r[2]:,}")

    print(f"\nlocated_in breakdown by entity type:")
    for r in conn.execute("""
        SELECT e.type, COUNT(*) as c
        FROM relationships r
        JOIN entities e ON r.source_mrgid = e.mrgid
        WHERE r.relationship = 'located_in'
        GROUP BY e.type ORDER BY c DESC LIMIT 15
    """).fetchall():
        print(f"  {r[0]}: {r[1]:,}")

    print(f"\nlocated_in breakdown by container type:")
    for r in conn.execute("""
        SELECT r.target_type, COUNT(*) as c
        FROM relationships r
        WHERE r.relationship = 'located_in'
        GROUP BY r.target_type ORDER BY c DESC
    """).fetchall():
        print(f"  {r[0]}: {r[1]:,}")

    print(f"\nSample located_in relationships:")
    for r in conn.execute("""
        SELECT e.name, e.type, r.target_name, r.target_type
        FROM relationships r
        JOIN entities e ON r.source_mrgid = e.mrgid
        WHERE r.relationship = 'located_in'
        ORDER BY RANDOM() LIMIT 15
    """).fetchall():
        print(f"  {r[0]} ({r[1]}) → located_in → {r[2]} ({r[3]})")

    print(f"\nSample claimed_by relationships:")
    for r in conn.execute("""
        SELECT e.name, e.type, r.target_name
        FROM relationships r
        JOIN entities e ON r.source_mrgid = e.mrgid
        WHERE r.relationship = 'claimed_by'
        ORDER BY RANDOM() LIMIT 10
    """).fetchall():
        print(f"  {r[0]} ({r[1]}) → claimed_by → {r[2]}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--located", action="store_true", help="Only run located_in")
    parser.add_argument("--claimed", action="store_true", help="Only run claimed_by")
    parser.add_argument("--stats", action="store_true", help="Print stats only")
    args = parser.parse_args()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")

    if args.stats:
        print_stats(conn)
        conn.close()
        return

    run_both = not args.located and not args.claimed

    if args.located or run_both:
        print("╔══════════════════════════════════════╗")
        print("║  Strategy #1: Point-in-bbox          ║")
        print("╚══════════════════════════════════════╝")
        count = run_located_in(conn)
        print(f"\n  Total located_in relationships: {count:,}")

    if args.claimed or run_both:
        print("\n╔══════════════════════════════════════╗")
        print("║  Strategy #2: EEZ/TS Name Parsing    ║")
        print("╚══════════════════════════════════════╝")
        count = run_claimed_by(conn)
        print(f"\n  Total claimed_by relationships: {count:,}")

    print_stats(conn)
    conn.close()


if __name__ == "__main__":
    main()
