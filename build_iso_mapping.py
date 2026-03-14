#!/usr/bin/env python3
"""
Build ISO 3166 country code mapping for all Nation entities in global_map.db.

Strategy:
1. Exact name match against pycountry
2. Manual alias dictionary for known mismatches (Dutch names, alternate spellings)
3. Fuzzy search as fallback
4. Report unmatched for manual review

Output: Updates iso_code column on entities table.
"""

import sqlite3
import pycountry

DB_PATH = "data/marine_regions/global_map.db"

# Manual aliases: DB name -> ISO alpha-3 code
# Built from known mismatches across 6 sessions
MANUAL_ALIASES = {
    # Dutch names (Marine Regions is Flemish)
    "België": "BEL",
    "Frankrijk": "FRA",
    "Nederland": "NLD",
    "Groothertogdom Luxemburg": "LUX",

    # Alternate/legacy names
    "East Timor": "TLS",          # Timor-Leste
    "Swaziland": "SWZ",           # now Eswatini
    "Comores": "COM",             # Comoros
    "Surinam": "SUR",             # Suriname
    "Cape Verde": "CPV",          # Cabo Verde
    "Czech Republic": "CZE",      # Czechia
    "Brunei": "BRN",              # Brunei Darussalam
    "North Macedonia": "MKD",
    "Côte d'Ivoire": "CIV",
    "Türkiye": "TUR",
    "North Korea": "PRK",
    "South Korea": "KOR",
    "Iran": "IRN",
    "Syria": "SYR",
    "Russia": "RUS",
    "Bolivia": "BOL",
    "Venezuela": "VEN",
    "Vietnam": "VNM",
    "Taiwan": "TWN",
    "Laos": "LAO",
    "Moldova": "MDA",
    "Tanzania": "TZA",
    "Micronesia": "FSM",
    "Palestine": "PSE",
    "South Sudan": "SSD",

    # MR-specific names
    "Republic of Mauritius": "MUS",
    "Republic of the Congo": "COG",
    "Democratic Republic of the Congo": "COD",
    "Federal Republic of Somalia": "SOM",
    "Vatican City": "VAT",
    "San Marino": "SMR",
    "Montenegro": "MNE",
    "Serbia": "SRB",
    "Mongolia": "MNG",
    "Cuba": "CUB",
    "Dominican Republic": "DOM",
    "Haiti": "HTI",
    "Jamaica": "JAM",
    "Dominica": "DMA",
    "Grenada": "GRD",
    "Saint Kitts and Nevis": "KNA",
    "Saint Lucia": "LCA",
    "Saint Vincent and the Grenadines": "VCT",
    "Antigua and Barbuda": "ATG",
    "Barbados": "BRB",
    "Belize": "BLZ",
    "Guinea-Bissau": "GNB",
    "Samoa": "WSM",
    "Tonga": "TON",
    "Nauru": "NRU",
    "Palau": "PLW",
    "Kiribati": "KIR",
    "Solomon Islands": "SLB",
    "Marshall Islands": "MHL",
    "Togo": "TGO",
    "Madagascar": "MDG",
}


def match_country(name):
    """Try to match a DB nation name to an ISO alpha-3 code."""
    # 1. Manual alias
    if name in MANUAL_ALIASES:
        return MANUAL_ALIASES[name], "alias"

    # 2. Exact match by name
    try:
        c = pycountry.countries.lookup(name)
        return c.alpha_3, "exact"
    except LookupError:
        pass

    # 3. Fuzzy search
    try:
        results = pycountry.countries.search_fuzzy(name)
        if results:
            return results[0].alpha_3, "fuzzy"
    except LookupError:
        pass

    return None, "unmatched"


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all nations
    nations = cursor.execute(
        "SELECT mrgid, name FROM entities WHERE type='Nation' ORDER BY name"
    ).fetchall()

    print(f"Total nations in DB: {len(nations)}")
    print()

    matched = []
    unmatched = []

    for mrgid, name in nations:
        code, method = match_country(name)
        if code:
            matched.append((mrgid, name, code, method))
        else:
            unmatched.append((mrgid, name))

    # Check for duplicate ISO codes
    code_to_nations = {}
    for mrgid, name, code, method in matched:
        if code not in code_to_nations:
            code_to_nations[code] = []
        code_to_nations[code].append((mrgid, name))

    duplicates = {k: v for k, v in code_to_nations.items() if len(v) > 1}

    # Report
    print(f"Matched: {len(matched)}/{len(nations)}")
    print(f"  - by alias:  {sum(1 for _, _, _, m in matched if m == 'alias')}")
    print(f"  - by exact:  {sum(1 for _, _, _, m in matched if m == 'exact')}")
    print(f"  - by fuzzy:  {sum(1 for _, _, _, m in matched if m == 'fuzzy')}")
    print(f"Unmatched: {len(unmatched)}")
    print()

    if unmatched:
        print("UNMATCHED NATIONS:")
        for mrgid, name in unmatched:
            print(f"  {mrgid} | {name}")
        print()

    if duplicates:
        print("DUPLICATE ISO CODES (need resolution):")
        for code, entries in duplicates.items():
            print(f"  {code}: {', '.join(f'{n} ({m})' for m, n in entries)}")
        print()

    # Dry run output
    print("Sample mappings:")
    for mrgid, name, code, method in matched[:20]:
        # Look up the official name for verification
        try:
            official = pycountry.countries.get(alpha_3=code).name
        except:
            official = "?"
        print(f"  {name:40s} -> {code} ({official}) [{method}]")

    print(f"\n--- DRY RUN COMPLETE ---")
    print(f"Run with --apply to update the database.")

    # Apply if requested
    import sys
    if "--apply" in sys.argv:
        print("\nApplying to database...")
        for mrgid, name, code, method in matched:
            cursor.execute(
                "UPDATE entities SET iso_code = ? WHERE mrgid = ?",
                (code, mrgid)
            )
        conn.commit()

        # Verify
        filled = cursor.execute(
            "SELECT COUNT(*) FROM entities WHERE type='Nation' AND iso_code IS NOT NULL"
        ).fetchone()[0]
        print(f"Updated: {filled} nations now have ISO codes.")

    conn.close()


if __name__ == "__main__":
    main()
