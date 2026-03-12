#!/usr/bin/env python3
"""
Spot-check the Marine Regions global database against known facts.
Verifies entity counts, key relationships, and flags anomalies.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "marine_regions" / "global_map.db"


def verify():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    passed = 0
    failed = 0
    warnings = 0

    def check(description, condition, detail=""):
        nonlocal passed, failed
        if condition:
            print(f"  PASS: {description}")
            passed += 1
        else:
            print(f"  FAIL: {description} — {detail}")
            failed += 1

    def warn(description, detail=""):
        nonlocal warnings
        print(f"  WARN: {description} — {detail}")
        warnings += 1

    # ─── Entity count checks ─────────────────────────────────────────────

    print("\n═══ Entity Count Checks ═══")

    n_nations = conn.execute("SELECT COUNT(*) FROM entities WHERE type='Nation'").fetchone()[0]
    check("Nations count ~196", 190 <= n_nations <= 200, f"got {n_nations}")

    n_continents = conn.execute("SELECT COUNT(*) FROM entities WHERE type='Continent'").fetchone()[0]
    check("Continents count ~7-8", 7 <= n_continents <= 8, f"got {n_continents}")

    n_oceans = conn.execute("SELECT COUNT(*) FROM entities WHERE type='Ocean'").fetchone()[0]
    check("Oceans count >= 1", n_oceans >= 1, f"got {n_oceans}")

    n_seas = conn.execute("SELECT COUNT(*) FROM entities WHERE type='Sea'").fetchone()[0]
    check("Seas count >= 100", n_seas >= 100, f"got {n_seas}")

    n_lme = conn.execute("SELECT COUNT(*) FROM entities WHERE type='LME'").fetchone()[0]
    check("LMEs count = 66", n_lme == 66, f"got {n_lme}")

    n_eez = conn.execute("SELECT COUNT(*) FROM entities WHERE type='EEZ'").fetchone()[0]
    check("EEZs count >= 200", n_eez >= 200, f"got {n_eez}")

    # ─── Key entities exist ──────────────────────────────────────────────

    print("\n═══ Key Entity Checks ═══")

    key_entities = [
        ("Pacific Ocean", "Ocean"),
        ("Mediterranean Sea", "Sea"),
        ("Strait of Gibraltar", None),  # typed as "Sea" in MR
        ("Suez Canal", "Canal"),
        ("Panama Canal", "Canal"),
        ("Amazon River", None),
        ("Nile", None),
        ("Mariana Trough", "Trough"),  # MR classifies as Trough, not Trench
        ("Medio-Atlantica Ridge", "Ridge"),  # MR uses Latin name
    ]

    for name, etype in key_entities:
        if etype:
            row = conn.execute("SELECT mrgid FROM entities WHERE name LIKE ? AND type=?",
                               (f"%{name}%", etype)).fetchone()
        else:
            row = conn.execute("SELECT mrgid FROM entities WHERE name LIKE ?",
                               (f"%{name}%",)).fetchone()
        check(f"{name} exists", row is not None, "not found")

    # ─── Relationship checks ─────────────────────────────────────────────

    print("\n═══ Relationship Checks ═══")

    # Turkey borders
    turkey = conn.execute("SELECT mrgid FROM entities WHERE name='Türkiye'").fetchone()
    if turkey:
        borders = conn.execute("""
            SELECT COUNT(DISTINCT CASE WHEN source_mrgid = ? THEN target_mrgid ELSE source_mrgid END)
            FROM relationships
            WHERE (source_mrgid = ? OR target_mrgid = ?) AND relationship = 'borders'
        """, (turkey[0], turkey[0], turkey[0])).fetchone()[0]
        check("Turkey has borders", borders >= 5, f"got {borders} (expected 8)")

    # Mediterranean adjacency
    med = conn.execute("SELECT mrgid FROM entities WHERE name='Mediterranean Sea' AND type='Sea' LIMIT 1").fetchone()
    if med:
        adj = conn.execute("""
            SELECT COUNT(*) FROM relationships
            WHERE (source_mrgid = ? OR target_mrgid = ?) AND relationship = 'adjacent_to'
        """, (med[0], med[0])).fetchone()[0]
        check("Mediterranean has adjacent nations", adj >= 5, f"got {adj}")

    # Part_of hierarchy
    part_ofs = conn.execute("SELECT COUNT(*) FROM relationships WHERE relationship='part_of'").fetchone()[0]
    check("Part_of relationships exist", part_ofs >= 100, f"got {part_ofs}")

    # River flows_through
    flows = conn.execute("SELECT COUNT(*) FROM relationships WHERE relationship='flows_through'").fetchone()[0]
    check("flows_through relationships exist", flows >= 50, f"got {flows}")

    # ─── Data quality checks ─────────────────────────────────────────────

    print("\n═══ Data Quality Checks ═══")

    # Entities with no name
    no_name = conn.execute("SELECT COUNT(*) FROM entities WHERE name IS NULL OR name = ''").fetchone()[0]
    check("No unnamed entities", no_name == 0, f"got {no_name}")

    # Entities with coordinates
    with_coords = conn.execute("SELECT COUNT(*) FROM entities WHERE latitude IS NOT NULL").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
    pct = with_coords / total * 100 if total else 0
    check(f"Most entities have coordinates (>50%)", pct > 50, f"{pct:.0f}%")

    # Duplicate names within same type
    dupes = conn.execute("""
        SELECT name, type, COUNT(*) as c FROM entities
        GROUP BY name, type HAVING c > 1
        ORDER BY c DESC LIMIT 5
    """).fetchall()
    if dupes:
        for d in dupes:
            warn(f"Duplicate: {d[0]} ({d[1]})", f"{d[2]} copies")

    # Landlocked nations with sea adjacency (potential false positives)
    landlocked_test = ["Bolivia", "Paraguay", "Chad", "Niger"]
    for nation in landlocked_test:
        row = conn.execute("SELECT mrgid FROM entities WHERE name=? AND type='Nation'", (nation,)).fetchone()
        if row:
            sea_adj = conn.execute("""
                SELECT r.target_name FROM relationships r
                JOIN entities e ON r.source_mrgid = e.mrgid
                WHERE r.target_mrgid = ? AND r.relationship = 'adjacent_to'
                  AND e.type IN ('Sea', 'Ocean', 'Gulf')
            """, (row[0],)).fetchall()
            if sea_adj:
                names = [r[0] for r in sea_adj]
                warn(f"Landlocked {nation} has sea adjacency (false positive)", ", ".join(names))

    # ─── Summary ─────────────────────────────────────────────────────────

    print(f"\n═══ Summary ═══")
    print(f"  Total entities: {total:,}")
    rels = conn.execute("SELECT COUNT(*) FROM relationships").fetchone()[0]
    print(f"  Total relationships: {rels:,}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Warnings: {warnings}")

    conn.close()
    return failed == 0


if __name__ == "__main__":
    import sys
    success = verify()
    sys.exit(0 if success else 1)
