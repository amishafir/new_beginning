#!/usr/bin/env python3
"""
Query interface for the Marine Regions global database.

Answers questions like:
  - What seas border Turkey?
  - What strait connects the Mediterranean to the Black Sea?
  - Which nations share the South China Sea?
  - What rivers flow through Germany?
  - What's in the Arctic Ocean?

Usage:
    python3 query_world.py                          # Interactive mode
    python3 query_world.py "seas near Turkey"       # Single query
    python3 query_world.py --stats                  # Database overview
"""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "marine_regions" / "global_map.db"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ─── Core queries ────────────────────────────────────────────────────────────

def find_entity(conn, name, entity_type=None):
    """Find entities by name (fuzzy match)."""
    if entity_type:
        rows = conn.execute("""
            SELECT mrgid, name, type, tier, latitude, longitude
            FROM entities
            WHERE name LIKE ? AND type = ?
            ORDER BY length(name)
        """, (f"%{name}%", entity_type)).fetchall()
    else:
        rows = conn.execute("""
            SELECT mrgid, name, type, tier, latitude, longitude
            FROM entities
            WHERE name LIKE ?
            ORDER BY length(name)
        """, (f"%{name}%",)).fetchall()
    return rows


def get_relationships(conn, mrgid, rel_type=None, direction="both"):
    """Get all relationships for an entity."""
    results = []

    if direction in ("both", "outgoing"):
        if rel_type:
            rows = conn.execute("""
                SELECT r.relationship, r.target_mrgid, r.target_name, r.target_type,
                       e.name as resolved_name, e.type as resolved_type
                FROM relationships r
                LEFT JOIN entities e ON r.target_mrgid = e.mrgid
                WHERE r.source_mrgid = ? AND r.relationship = ?
            """, (mrgid, rel_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.relationship, r.target_mrgid, r.target_name, r.target_type,
                       e.name as resolved_name, e.type as resolved_type
                FROM relationships r
                LEFT JOIN entities e ON r.target_mrgid = e.mrgid
                WHERE r.source_mrgid = ?
            """, (mrgid,)).fetchall()

        for r in rows:
            results.append({
                "direction": "→",
                "relationship": r["relationship"],
                "mrgid": r["target_mrgid"],
                "name": r["resolved_name"] or r["target_name"],
                "type": r["resolved_type"] or r["target_type"],
            })

    if direction in ("both", "incoming"):
        if rel_type:
            rows = conn.execute("""
                SELECT r.relationship, r.source_mrgid,
                       e.name, e.type
                FROM relationships r
                JOIN entities e ON r.source_mrgid = e.mrgid
                WHERE r.target_mrgid = ? AND r.relationship = ?
            """, (mrgid, rel_type)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.relationship, r.source_mrgid,
                       e.name, e.type
                FROM relationships r
                JOIN entities e ON r.source_mrgid = e.mrgid
                WHERE r.target_mrgid = ?
            """, (mrgid,)).fetchall()

        for r in rows:
            results.append({
                "direction": "←",
                "relationship": r["relationship"],
                "mrgid": r["source_mrgid"],
                "name": r["name"],
                "type": r["type"],
            })

    return results


# ─── High-level queries ─────────────────────────────────────────────────────

def seas_bordering(conn, nation_name):
    """What seas/oceans border a nation?"""
    nations = find_entity(conn, nation_name, "Nation")
    if not nations:
        nations = find_entity(conn, nation_name, "Territory")
    if not nations:
        return f"Nation '{nation_name}' not found"

    nation = nations[0]
    results = []

    # Get adjacent_to relationships where water → nation
    rels = get_relationships(conn, nation["mrgid"], "adjacent_to", "incoming")
    for r in rels:
        if r["type"] in ("Sea", "Ocean", "Gulf", "Bay", "Strait", "Channel"):
            results.append(r)

    # Also check outgoing adjacent_to
    rels2 = get_relationships(conn, nation["mrgid"], "adjacent_to", "outgoing")
    for r in rels2:
        if r["type"] in ("Sea", "Ocean", "Gulf", "Bay", "Strait", "Channel"):
            results.append(r)

    if not results:
        return f"No seas found adjacent to {nation['name']}"

    lines = [f"Seas/waters adjacent to {nation['name']}:"]
    seen = set()
    for r in results:
        if r["name"] not in seen:
            lines.append(f"  {r['name']} ({r['type']})")
            seen.add(r["name"])
    return "\n".join(lines)


def nations_sharing_sea(conn, sea_name):
    """Which nations share a given sea?"""
    seas = find_entity(conn, sea_name, "Sea")
    if not seas:
        seas = find_entity(conn, sea_name, "Gulf")
    if not seas:
        seas = find_entity(conn, sea_name)
    if not seas:
        return f"Sea '{sea_name}' not found"

    sea = seas[0]
    results = []

    rels = get_relationships(conn, sea["mrgid"], "adjacent_to")
    for r in rels:
        if r["type"] in ("Nation", "Territory"):
            results.append(r)

    if not results:
        return f"No nations found adjacent to {sea['name']}"

    lines = [f"Nations adjacent to {sea['name']}:"]
    seen = set()
    for r in sorted(results, key=lambda x: x["name"]):
        if r["name"] not in seen:
            lines.append(f"  {r['name']}")
            seen.add(r["name"])
    return "\n".join(lines)


def borders_of(conn, nation_name):
    """What nations border a given nation?"""
    nations = find_entity(conn, nation_name, "Nation")
    if not nations:
        return f"Nation '{nation_name}' not found"

    nation = nations[0]
    results = []

    for direction in ("outgoing", "incoming"):
        rels = get_relationships(conn, nation["mrgid"], "borders", direction)
        results.extend(rels)

    if not results:
        return f"No land borders found for {nation['name']}"

    lines = [f"Nations bordering {nation['name']}:"]
    seen = set()
    for r in sorted(results, key=lambda x: x["name"]):
        if r["name"] not in seen:
            lines.append(f"  {r['name']}")
            seen.add(r["name"])
    return "\n".join(lines)


def rivers_through(conn, nation_name):
    """What rivers flow through a nation?"""
    nations = find_entity(conn, nation_name, "Nation")
    if not nations:
        return f"Nation '{nation_name}' not found"

    nation = nations[0]
    results = []

    # rivers → flows_through → nation
    rels = get_relationships(conn, nation["mrgid"], "flows_through", "incoming")
    results.extend(rels)

    if not results:
        return f"No rivers found flowing through {nation['name']}"

    lines = [f"Rivers flowing through {nation['name']}:"]
    for r in sorted(results, key=lambda x: x["name"]):
        lines.append(f"  {r['name']}")
    return "\n".join(lines)


def parts_of(conn, entity_name):
    """What are the parts of a given entity?"""
    entities = find_entity(conn, entity_name)
    if not entities:
        return f"Entity '{entity_name}' not found"

    entity = entities[0]
    results = []

    # Children: things that are part_of this entity
    rels = get_relationships(conn, entity["mrgid"], "part_of", "incoming")
    results.extend(rels)

    if not results:
        return f"No sub-parts found for {entity['name']}"

    lines = [f"Parts of {entity['name']} ({entity['type']}):"]
    for r in sorted(results, key=lambda x: (x["type"], x["name"])):
        lines.append(f"  {r['name']} ({r['type']})")
    return "\n".join(lines)


def parent_of(conn, entity_name):
    """What is this entity part of?"""
    entities = find_entity(conn, entity_name)
    if not entities:
        return f"Entity '{entity_name}' not found"

    entity = entities[0]
    rels = get_relationships(conn, entity["mrgid"], "part_of", "outgoing")

    if not rels:
        return f"No parent found for {entity['name']}"

    lines = [f"{entity['name']} ({entity['type']}) is part of:"]
    for r in rels:
        lines.append(f"  {r['name']} ({r['type']})")
    return "\n".join(lines)


def entity_info(conn, name):
    """Full info about an entity."""
    entities = find_entity(conn, name)
    if not entities:
        return f"Entity '{name}' not found"

    entity = entities[0]
    lines = [
        f"═══ {entity['name']} ═══",
        f"  Type: {entity['type']}",
        f"  Tier: {entity['tier']}",
        f"  MRGID: {entity['mrgid']}",
    ]
    if entity["latitude"]:
        lines.append(f"  Location: {entity['latitude']:.3f}°, {entity['longitude']:.3f}°")

    rels = get_relationships(conn, entity["mrgid"])
    if rels:
        lines.append(f"\n  Relationships ({len(rels)}):")
        grouped = {}
        for r in rels:
            key = f"{r['direction']} {r['relationship']}"
            if key not in grouped:
                grouped[key] = []
            grouped[key].append(r)

        for key in sorted(grouped.keys()):
            lines.append(f"    {key}:")
            for r in sorted(grouped[key], key=lambda x: x["name"] or ""):
                lines.append(f"      {r['name']} ({r['type']})")

    return "\n".join(lines)


def db_stats(conn):
    """Print database overview."""
    total = conn.execute("SELECT COUNT(*) as c FROM entities").fetchone()["c"]
    rels = conn.execute("SELECT COUNT(*) as c FROM relationships").fetchone()["c"]

    lines = [
        "═══ Global Map Database ═══",
        f"Total entities: {total:,}",
        f"Total relationships: {rels:,}",
        "",
        "Entities by tier:"
    ]

    for r in conn.execute("SELECT tier, COUNT(*) as c FROM entities GROUP BY tier ORDER BY tier"):
        tier_names = {1: "Political & Land", 2: "Water Bodies", 3: "Fresh Water",
                      4: "Seafloor", 6: "Maritime Zones", 7: "Ecological"}
        name = tier_names.get(r["tier"], f"Tier {r['tier']}")
        lines.append(f"  {name}: {r['c']:,}")

    lines.append("\nTop entity types:")
    for r in conn.execute("SELECT type, COUNT(*) as c FROM entities GROUP BY type ORDER BY c DESC LIMIT 20"):
        lines.append(f"  {r['type']}: {r['c']:,}")

    lines.append("\nRelationship types:")
    for r in conn.execute("SELECT relationship, COUNT(*) as c FROM relationships GROUP BY relationship ORDER BY c DESC"):
        lines.append(f"  {r['relationship']}: {r['c']:,}")

    return "\n".join(lines)


# ─── Interactive mode ────────────────────────────────────────────────────────

HELP_TEXT = """
Commands:
  seas <nation>          — What seas border a nation?
  nations <sea>          — Which nations share a sea?
  borders <nation>       — What nations border a nation?
  rivers <nation>        — What rivers flow through a nation?
  parts <entity>         — What are the sub-parts of an entity?
  parent <entity>        — What is an entity part of?
  info <entity>          — Full info about an entity
  find <name> [type]     — Search for entities by name
  stats                  — Database overview
  help                   — Show this help
  quit                   — Exit
"""


def interactive(conn):
    print("Global Map Database — Interactive Query")
    print("Type 'help' for commands, 'quit' to exit\n")

    while True:
        try:
            line = input("query> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            continue

        parts = line.split(maxsplit=1)
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit", "q"):
            break
        elif cmd == "help":
            print(HELP_TEXT)
        elif cmd == "stats":
            print(db_stats(conn))
        elif cmd == "seas":
            print(seas_bordering(conn, arg))
        elif cmd == "nations":
            print(nations_sharing_sea(conn, arg))
        elif cmd == "borders":
            print(borders_of(conn, arg))
        elif cmd == "rivers":
            print(rivers_through(conn, arg))
        elif cmd == "parts":
            print(parts_of(conn, arg))
        elif cmd == "parent":
            print(parent_of(conn, arg))
        elif cmd == "info":
            print(entity_info(conn, arg))
        elif cmd == "find":
            subparts = arg.split(maxsplit=1)
            name = subparts[0] if subparts else ""
            etype = subparts[1] if len(subparts) > 1 else None
            results = find_entity(conn, name, etype)
            if results:
                for r in results[:20]:
                    print(f"  {r['mrgid']}: {r['name']} ({r['type']})")
                if len(results) > 20:
                    print(f"  ... and {len(results) - 20} more")
            else:
                print(f"  No results for '{name}'")
        else:
            print(f"Unknown command: {cmd}. Type 'help' for commands.")

        print()


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        print("Run extract_marine_regions.py first")
        sys.exit(1)

    conn = get_db()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--stats":
            print(db_stats(conn))
        else:
            # Treat argument as a query
            query = " ".join(sys.argv[1:])
            print(entity_info(conn, query))
    else:
        interactive(conn)

    conn.close()


if __name__ == "__main__":
    main()
