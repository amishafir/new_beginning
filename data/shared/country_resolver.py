"""
Shared country code resolver for GW/COW numeric codes and country name variants.

Consolidates mapping tables from:
- extract_ucdp.py (GW → ISO)
- extract_cow_alliances.py (COW → ISO)
- extract_sipri_arms.py (SIPRI names → ISO)

GW (Gleditsch-Ward) and COW (Correlates of War) use the same numeric system
with minor differences. This module merges both into a single lookup.
"""

import sqlite3


# ── Unified GW/COW numeric code → ISO 3166-1 alpha-3 ──
# Merges GW codes (UCDP) and COW codes (alliances).
# Where a numeric code maps to a historical state, we map to the modern successor.
GW_TO_ISO = {
    2: "USA", 20: "CAN", 31: "BHS", 40: "CUB", 41: "HTI", 42: "DOM",
    51: "JAM", 52: "TTO", 53: "BRB", 54: "DMA", 55: "GRD", 56: "LCA",
    57: "VCT", 58: "ATG", 60: "KNA", 70: "MEX", 80: "BLZ", 90: "GTM",
    91: "HND", 92: "SLV", 93: "NIC", 94: "CRI", 95: "PAN",
    100: "COL", 101: "VEN", 110: "GUY", 115: "SUR", 130: "ECU",
    135: "PER", 140: "BRA", 145: "BOL", 150: "PRY", 155: "CHL",
    160: "ARG", 165: "URY",
    200: "GBR", 205: "IRL", 210: "NLD", 211: "BEL", 212: "LUX",
    220: "FRA", 221: "MCO", 223: "LIE", 225: "CHE", 230: "ESP",
    232: "AND", 235: "PRT",
    240: "DEU",  # COW: Hanover → Germany
    245: "DEU",  # COW: Bavaria → Germany
    255: "DEU",  # Germany (unified)
    260: "DEU",  # GFR → Germany
    265: "DEU",  # GDR → Germany (historical)
    267: "DEU",  # COW: additional German state
    269: "DEU",  # COW: additional German state
    271: "DEU",  # COW: additional German state
    273: "DEU",  # COW: additional German state
    275: "DEU",  # COW: additional German state
    280: "DEU",  # COW: additional German state
    290: "POL",
    300: "AUT",  # Austria-Hungary → Austria
    305: "AUT", 310: "HUN",
    315: "CZE",  # Czechoslovakia → Czech Republic
    316: "CZE", 317: "SVK",
    325: "ITA",
    327: "ITA",  # COW: Papal States → Italy
    329: "ITA",  # COW: Two Sicilies → Italy
    331: "SMR",
    332: "ITA",  # COW: Modena → Italy
    335: "ITA",  # COW: Parma → Italy
    337: "ITA",  # COW: Tuscany → Italy
    338: "MLT", 339: "ALB", 341: "MNE", 343: "MKD",
    344: "HRV", 345: "SRB",  # Yugoslavia → Serbia
    346: "BIH", 347: "XKX",  # Kosovo (no ISO, use XKX)
    349: "SVN", 350: "GRC", 352: "CYP", 355: "BGR",
    359: "MDA", 360: "ROU", 365: "RUS",
    366: "EST", 367: "LVA", 368: "LTU", 369: "UKR", 370: "BLR",
    371: "ARM", 372: "GEO", 373: "AZE",
    375: "FIN", 380: "SWE", 385: "NOR", 390: "DNK", 395: "ISL",
    402: "CPV", 403: "STP", 404: "GNB", 411: "GNQ",
    420: "GMB", 432: "MLI", 433: "SEN", 434: "BEN", 435: "MRT",
    436: "NER", 437: "CIV", 438: "GIN", 439: "BFA",
    450: "LBR", 451: "SLE", 452: "GHA", 461: "TGO",
    471: "CMR", 475: "NGA", 481: "GAB", 482: "CAF", 483: "TCD",
    484: "COG", 490: "COD", 500: "UGA", 501: "KEN",
    510: "TZA",
    511: "TZA",  # COW: Zanzibar → Tanzania
    516: "BDI", 517: "RWA", 520: "SOM", 522: "DJI",
    530: "ETH", 531: "ERI", 540: "AGO", 541: "MOZ",
    551: "ZMB", 552: "ZWE", 553: "MWI", 560: "ZAF", 565: "NAM",
    570: "LSO", 571: "BWA", 572: "SWZ", 580: "MDG", 581: "COM",
    590: "MUS", 591: "SYC",
    600: "MAR", 615: "DZA", 616: "TUN", 620: "LBY",
    625: "SDN", 626: "SSD",
    630: "IRN", 640: "TUR", 645: "IRQ", 651: "EGY", 652: "SYR",
    660: "LBN", 663: "JOR", 666: "ISR",
    670: "SAU", 678: "YEM",  # YAR → Yemen
    679: "YEM", 680: "YEM",  # YPR → Yemen
    690: "KWT", 692: "BHR", 694: "QAT", 696: "ARE", 698: "OMN",
    700: "AFG", 701: "TKM", 702: "TJK", 703: "KGZ", 704: "UZB", 705: "KAZ",
    710: "CHN", 712: "MNG", 713: "TWN",
    730: "KOR",  # Korea (historical)
    731: "PRK", 732: "KOR",
    740: "JPN", 750: "IND", 760: "BTN", 770: "PAK", 771: "BGD",
    775: "MMR", 780: "LKA", 781: "MDV", 790: "NPL",
    800: "THA", 811: "KHM", 812: "LAO",
    816: "VNM",  # DRV → Vietnam
    817: "VNM",  # RVN → Vietnam (historical)
    820: "MYS", 830: "SGP", 835: "BRN", 840: "PHL",
    850: "IDN", 860: "TLS",
    900: "AUS", 910: "PNG", 920: "NZL", 935: "VUT", 940: "SLB",
    946: "KIR", 947: "TUV", 950: "FJI", 955: "TON", 970: "NRU",
    983: "MHL", 986: "PLW", 987: "FSM", 990: "WSM",
}


# ── Country name → ISO 3166-1 alpha-3 ──
# Covers SIPRI names, common variants, and historical state names.
NAME_TO_ISO = {
    "Afghanistan": "AFG", "Albania": "ALB", "Algeria": "DZA", "Angola": "AGO",
    "Argentina": "ARG", "Armenia": "ARM", "Australia": "AUS", "Austria": "AUT",
    "Azerbaijan": "AZE", "Bahamas": "BHS", "Bahrain": "BHR", "Bangladesh": "BGD",
    "Belarus": "BLR", "Belgium": "BEL", "Benin": "BEN", "Bolivia": "BOL",
    "Bosnia-Herzegovina": "BIH", "Botswana": "BWA", "Brazil": "BRA", "Brunei": "BRN",
    "Bulgaria": "BGR", "Burkina Faso": "BFA", "Burundi": "BDI",
    "Cambodia": "KHM", "Cameroon": "CMR", "Canada": "CAN", "Cape Verde": "CPV",
    "Central African Republic": "CAF", "Chad": "TCD", "Chile": "CHL", "China": "CHN",
    "Colombia": "COL", "Comoros": "COM", "Congo": "COG", "Costa Rica": "CRI",
    "Cote d'Ivoire": "CIV", "Croatia": "HRV", "Cuba": "CUB", "Cyprus": "CYP",
    "Czech Republic": "CZE", "Czechia": "CZE", "Czechoslovakia": "CZE",
    "DR Congo": "COD", "Denmark": "DNK", "Djibouti": "DJI",
    "Dominican Republic": "DOM", "Ecuador": "ECU", "Egypt": "EGY",
    "El Salvador": "SLV", "Equatorial Guinea": "GNQ", "Eritrea": "ERI",
    "Estonia": "EST", "Eswatini": "SWZ", "Ethiopia": "ETH",
    "Fiji": "FJI", "Finland": "FIN", "France": "FRA",
    "Gabon": "GAB", "Gambia": "GMB", "Georgia": "GEO", "Germany": "DEU",
    "East Germany (GDR)": "DEU", "West Germany (FRG)": "DEU",
    "Ghana": "GHA", "Greece": "GRC", "Guatemala": "GTM", "Guinea": "GIN",
    "Guinea-Bissau": "GNB", "Guyana": "GUY",
    "Haiti": "HTI", "Honduras": "HND", "Hungary": "HUN",
    "Iceland": "ISL", "India": "IND", "Indonesia": "IDN", "Iran": "IRN",
    "Iraq": "IRQ", "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA",
    "Jamaica": "JAM", "Japan": "JPN", "Jordan": "JOR",
    "Kazakhstan": "KAZ", "Kenya": "KEN", "Kuwait": "KWT", "Kyrgyzstan": "KGZ",
    "Laos": "LAO", "Latvia": "LVA", "Lebanon": "LBN", "Lesotho": "LSO",
    "Liberia": "LBR", "Libya": "LBY", "Lithuania": "LTU", "Luxembourg": "LUX",
    "North Macedonia": "MKD", "Madagascar": "MDG", "Malawi": "MWI",
    "Malaysia": "MYS", "Maldives": "MDV", "Mali": "MLI", "Malta": "MLT",
    "Mauritania": "MRT", "Mauritius": "MUS", "Mexico": "MEX", "Moldova": "MDA",
    "Mongolia": "MNG", "Montenegro": "MNE", "Morocco": "MAR", "Mozambique": "MOZ",
    "Myanmar": "MMR", "Namibia": "NAM", "Nepal": "NPL", "Netherlands": "NLD",
    "New Zealand": "NZL", "Nicaragua": "NIC", "Niger": "NER", "Nigeria": "NGA",
    "North Korea": "PRK", "Norway": "NOR",
    "Oman": "OMN", "Pakistan": "PAK", "Panama": "PAN", "Papua New Guinea": "PNG",
    "Paraguay": "PRY", "Peru": "PER", "Philippines": "PHL", "Poland": "POL",
    "Portugal": "PRT", "Qatar": "QAT",
    "Romania": "ROU", "Russia": "RUS", "Soviet Union": "RUS",
    "Rwanda": "RWA",
    "Saudi Arabia": "SAU", "Senegal": "SEN", "Serbia": "SRB", "Seychelles": "SYC",
    "Yugoslavia": "SRB", "Sierra Leone": "SLE",
    "Singapore": "SGP", "Slovakia": "SVK", "Slovenia": "SVN",
    "Solomon Islands": "SLB", "Somalia": "SOM", "South Africa": "ZAF",
    "South Korea": "KOR", "South Sudan": "SSD", "Spain": "ESP",
    "Sri Lanka": "LKA", "Sudan": "SDN", "Suriname": "SUR",
    "Sweden": "SWE", "Switzerland": "CHE", "Syria": "SYR",
    "Taiwan": "TWN", "Tajikistan": "TJK", "Tanzania": "TZA",
    "Thailand": "THA", "Timor-Leste": "TLS", "Togo": "TGO",
    "Tonga": "TON", "Trinidad and Tobago": "TTO", "Tunisia": "TUN",
    "Turkey": "TUR", "Turkiye": "TUR", "Turkmenistan": "TKM",
    "UAE": "ARE", "United Arab Emirates": "ARE",
    "Uganda": "UGA", "Ukraine": "UKR", "United Kingdom": "GBR",
    "United States": "USA", "Uruguay": "URY", "Uzbekistan": "UZB",
    "Vanuatu": "VUT", "Venezuela": "VEN", "Viet Nam": "VNM", "Vietnam": "VNM",
    "North Vietnam": "VNM", "South Vietnam": "VNM",
    "Yemen": "YEM", "North Yemen": "YEM", "South Yemen": "YEM",
    "Yemen Arab Republic (North Yemen)": "YEM", "Yemen PDR (South Yemen)": "YEM",
    "Zambia": "ZMB", "Zimbabwe": "ZWE",
    # Non-state actors and special entities → skip
    "Unknown country": None,
}

# Build case-insensitive lookup (lowercase key → ISO)
_NAME_TO_ISO_LOWER = {k.lower(): v for k, v in NAME_TO_ISO.items()}


# ── Historical GW/COW codes that map to states that no longer exist ──
# Maps code → (modern_iso, note) for provenance tracking
HISTORICAL_TO_MODERN = {
    240: ("DEU", "Hanover → Germany"),
    245: ("DEU", "Bavaria → Germany"),
    260: ("DEU", "GFR (West Germany) → Germany"),
    265: ("DEU", "GDR (East Germany) → Germany"),
    267: ("DEU", "COW German state → Germany"),
    269: ("DEU", "COW German state → Germany"),
    271: ("DEU", "COW German state → Germany"),
    273: ("DEU", "COW German state → Germany"),
    275: ("DEU", "COW German state → Germany"),
    280: ("DEU", "COW German state → Germany"),
    300: ("AUT", "Austria-Hungary → Austria"),
    315: ("CZE", "Czechoslovakia → Czech Republic"),
    327: ("ITA", "Papal States → Italy"),
    329: ("ITA", "Two Sicilies → Italy"),
    332: ("ITA", "Modena → Italy"),
    335: ("ITA", "Parma → Italy"),
    337: ("ITA", "Tuscany → Italy"),
    345: ("SRB", "Yugoslavia → Serbia"),
    511: ("TZA", "Zanzibar → Tanzania"),
    678: ("YEM", "YAR (North Yemen) → Yemen"),
    680: ("YEM", "YPR (South Yemen) → Yemen"),
    730: ("KOR", "Korea (historical) → South Korea"),
    816: ("VNM", "DRV (North Vietnam) → Vietnam"),
    817: ("VNM", "RVN (South Vietnam) → Vietnam"),
}

# Set of historical GW codes (for quick membership test)
HISTORICAL_GW = set(HISTORICAL_TO_MODERN.keys())


def resolve_gwno(gwno_str: str) -> list[str]:
    """Convert a comma-separated GW/COW number string to a list of unique ISO codes.

    Examples:
        resolve_gwno("2") → ["USA"]
        resolve_gwno("260, 265") → ["DEU"]
        resolve_gwno("invalid") → []
    """
    codes = []
    for gw in gwno_str.split(","):
        gw = gw.strip()
        if gw:
            try:
                iso = GW_TO_ISO.get(int(gw))
                if iso and iso not in codes:
                    codes.append(iso)
            except ValueError:
                pass
    return codes


def resolve_name(name: str) -> str | None:
    """Resolve a country name to ISO alpha-3 (case-insensitive).

    Tries exact match first, then strips "Government of " prefix.
    Returns None if no match found.
    """
    if not name:
        return None

    # Try exact match (case-insensitive)
    result = _NAME_TO_ISO_LOWER.get(name.lower())
    if result is not None:
        return result

    # Strip "Government of " prefix (common in UCDP actor names)
    if name.lower().startswith("government of "):
        stripped = name[len("Government of "):]
        result = _NAME_TO_ISO_LOWER.get(stripped.lower())
        if result is not None:
            return result

    return None


def get_iso_to_mrgid(conn: sqlite3.Connection) -> dict[str, int]:
    """Build ISO code → mrgid mapping for existing nations in the DB."""
    cur = conn.execute(
        "SELECT mrgid, iso_code FROM entities "
        "WHERE type='Nation' AND iso_code IS NOT NULL AND iso_code != ''"
    )
    return {row[1]: row[0] for row in cur.fetchall()}
