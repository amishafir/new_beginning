"""
Extract SIPRI Arms Transfers Database into global_map.db
Creates arms_transfer relationships between existing Nations.

Source: SIPRI Arms Transfers Database (1950-2025)
API: https://atbackend.sipri.org/api/p/trades/search
License: SIPRI Terms and Conditions (free for non-commercial use)
"""

import json
import sqlite3
import sys
import urllib.request
from pathlib import Path
from collections import defaultdict

# Add parent directory to path for shared imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from shared.country_resolver import NAME_TO_ISO as SIPRI_TO_ISO, get_iso_to_mrgid

DB_PATH = Path(__file__).parent.parent / "marine_regions" / "global_map.db"
API_URL = "https://atbackend.sipri.org/api/p/trades/search"
COUNTRIES_URL = "https://atbackend.sipri.org/api/p/countries/getAllCountriesTrimmed"
PAGE_SIZE = 30000  # API returns all in one page anyway (29917 < 30000)


def fetch_all_trades():
    """Fetch all arms transfer records from SIPRI API."""
    req = urllib.request.Request(
        API_URL,
        data=json.dumps({"filters": [], "logic": "AND", "page": 0, "pageSize": PAGE_SIZE}).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    return data


def main():
    conn = sqlite3.connect(DB_PATH)
    iso_to_mrgid = get_iso_to_mrgid(conn)

    # ── Step 1: Fetch all trades ──
    print("Fetching all SIPRI arms transfers...")
    trades = fetch_all_trades()
    print(f"  {len(trades)} individual transfer records")

    # ── Step 2: Aggregate into bilateral relationships ──
    # Key: (seller_iso, buyer_iso) → aggregated properties
    print("\nAggregating bilateral transfers...")
    bilateral = defaultdict(lambda: {
        "trade_count": 0,
        "categories": set(),
        "min_year": 9999,
        "max_year": 0,
        "sample_weapons": [],
    })

    unmapped_sellers = defaultdict(int)
    unmapped_buyers = defaultdict(int)
    non_state_skipped = 0

    for trade in trades:
        seller = trade.get("seller", "")
        buyer = trade.get("buyer", "")

        seller_iso = SIPRI_TO_ISO.get(seller)
        buyer_iso = SIPRI_TO_ISO.get(buyer)

        # Skip if we can't map either side
        if seller_iso is None:
            if seller not in SIPRI_TO_ISO:
                unmapped_sellers[seller] += 1
            else:
                non_state_skipped += 1
            continue
        if buyer_iso is None:
            if buyer not in SIPRI_TO_ISO:
                unmapped_buyers[buyer] += 1
            else:
                non_state_skipped += 1
            continue

        # Skip self-transfers
        if seller_iso == buyer_iso:
            continue

        key = (seller_iso, buyer_iso)
        b = bilateral[key]
        b["trade_count"] += 1

        category = trade.get("category", "")
        if category:
            b["categories"].add(category)

        delivery_yr = trade.get("deliveryYr")
        if delivery_yr:
            b["min_year"] = min(b["min_year"], delivery_yr)
            b["max_year"] = max(b["max_year"], delivery_yr)

        # Keep a few sample weapons
        if len(b["sample_weapons"]) < 3:
            desg = trade.get("desg", "")
            desc = trade.get("desc", "")
            if desg:
                b["sample_weapons"].append(f"{desg} ({desc})" if desc else desg)

    print(f"  {len(bilateral)} bilateral relationships")
    if unmapped_sellers:
        print(f"  Unmapped sellers: {dict(sorted(unmapped_sellers.items(), key=lambda x: -x[1])[:10])}")
    if unmapped_buyers:
        print(f"  Unmapped buyers: {dict(sorted(unmapped_buyers.items(), key=lambda x: -x[1])[:10])}")
    print(f"  Non-state/unknown skipped: {non_state_skipped}")

    # ── Step 3: Insert arms_transfer relationships ──
    print("\nInserting arms_transfer relationships...")
    rel_rows = []
    matched = 0
    unmatched = 0

    for (seller_iso, buyer_iso), props in bilateral.items():
        seller_mrgid = iso_to_mrgid.get(seller_iso)
        buyer_mrgid = iso_to_mrgid.get(buyer_iso)

        if not seller_mrgid or not buyer_mrgid:
            unmatched += 1
            continue

        matched += 1

        # Core relationship: seller → buyer
        rel_rows.append((
            seller_mrgid, "arms_transfer", buyer_mrgid, None, None,
            "trade_count", str(props["trade_count"]), "sipri_arms_v2025"
        ))
        rel_rows.append((
            seller_mrgid, "arms_transfer", buyer_mrgid, None, None,
            "categories", ", ".join(sorted(props["categories"])), "sipri_arms_v2025"
        ))
        if props["min_year"] < 9999:
            rel_rows.append((
                seller_mrgid, "arms_transfer", buyer_mrgid, None, None,
                "years", f"{props['min_year']}-{props['max_year']}", "sipri_arms_v2025"
            ))
        if props["sample_weapons"]:
            rel_rows.append((
                seller_mrgid, "arms_transfer", buyer_mrgid, None, None,
                "sample_systems", "; ".join(props["sample_weapons"]), "sipri_arms_v2025"
            ))

    conn.executemany(
        "INSERT INTO relationships (source_mrgid, relationship, target_mrgid, target_name, target_type, attr_name, attr_value, source_data) VALUES (?,?,?,?,?,?,?,?)",
        rel_rows
    )
    print(f"  Inserted {len(rel_rows)} arms_transfer relationship rows")
    print(f"  Matched {matched} bilateral pairs, {unmatched} unmatched")

    conn.commit()

    # ── Summary ──
    print("\n" + "=" * 60)
    print("EXTRACTION SUMMARY")
    print("=" * 60)

    cur = conn.execute("SELECT COUNT(DISTINCT source_mrgid || '-' || target_mrgid) FROM relationships WHERE relationship='arms_transfer'")
    print(f"\nUnique bilateral arms transfer pairs: {cur.fetchone()[0]}")

    cur = conn.execute("""
        SELECT e.name, e.iso_code, COUNT(DISTINCT r.target_mrgid) as buyer_count
        FROM entities e
        JOIN relationships r ON e.mrgid = r.source_mrgid
        WHERE r.relationship='arms_transfer' AND r.attr_name='trade_count'
        GROUP BY e.mrgid
        ORDER BY buyer_count DESC
        LIMIT 10
    """)
    print("\nTop arms exporters (by number of buyer countries):")
    for row in cur:
        print(f"  {row[0]} ({row[1]}): sells to {row[2]} countries")

    cur = conn.execute("""
        SELECT e.name, e.iso_code, COUNT(DISTINCT r.source_mrgid) as seller_count
        FROM entities e
        JOIN relationships r ON e.mrgid = r.target_mrgid
        WHERE r.relationship='arms_transfer' AND r.attr_name='trade_count'
        GROUP BY e.mrgid
        ORDER BY seller_count DESC
        LIMIT 10
    """)
    print("\nTop arms importers (by number of supplier countries):")
    for row in cur:
        print(f"  {row[0]} ({row[1]}): buys from {row[2]} countries")

    cur = conn.execute("SELECT COUNT(*) FROM entities")
    print(f"\nTotal entities in DB: {cur.fetchone()[0]}")
    cur = conn.execute("SELECT COUNT(*) FROM relationships")
    print(f"Total relationships in DB: {cur.fetchone()[0]}")

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
