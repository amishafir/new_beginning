#!/usr/bin/env python3
"""
Compute river flow order (upstream/downstream country ranking) for all TFDD
transboundary basins using HydroRIVERS topology data.

Algorithm:
1. For each TFDD basin, spatially intersect with HydroRIVERS reaches
2. Identify the main river network (largest upstream area)
3. Trace the main stem via NEXT_DOWN chain (follow largest UPLAND_SKM at junctions)
4. For each country's BCU polygon, find main-stem reaches and compute median DIST_DN_KM
5. Rank countries by descending DIST_DN_KM (highest = source = Rank 0)
6. Countries in the network but not on main stem → tributary_only

Sources:
- HydroRIVERS v10 (WWF/McGill): river reach topology with DIST_DN_KM, NEXT_DOWN, MAIN_RIV
- TFDD BCU shapefile (OSU, 2024): basin-country unit polygons

Output: JSON file with flow order per basin, ready for DB update.

Usage:
    python compute_flow_order.py                    # Dry run (compute + report)
    python compute_flow_order.py --apply            # Apply to database
    python compute_flow_order.py --basin "Danube"   # Single basin test
"""

import argparse
import geopandas as gpd
import json
import sqlite3
import sys
import time
from collections import defaultdict
from pathlib import Path

# --- Configuration ---

PROJECT_ROOT = Path(__file__).parent
BCU_PATH = PROJECT_ROOT / "data/rivers/raw/BCUMaster313_20240807.shp"
DB_PATH = PROJECT_ROOT / "data/marine_regions/global_map.db"
OUTPUT_PATH = PROJECT_ROOT / "data/flow_order/flow_order_results.json"

# TFDD continent code → HydroRIVERS region(s)
# Include fallback regions for boundary cases:
# - AS: Middle East rivers are in EU region, PNG/Indonesia rivers in AU region
# - NA: Alaska/Yukon rivers are in AR (Arctic) region
CONTINENT_TO_REGIONS = {
    "AF": ["af"],
    "AS": ["as", "si", "eu", "au"],
    "EU": ["eu"],
    "NA": ["na", "ar"],
    "SA": ["sa"],
}

HR_DIR = PROJECT_ROOT / "data/flow_order/raw"


def find_hr_shapefile(region_code):
    """Find the HydroRIVERS shapefile for a given region code."""
    # Pattern: HydroRIVERS_{region}/HydroRIVERS_v10_{region}_shp/HydroRIVERS_v10_{region}.shp
    candidates = list(HR_DIR.glob(f"HydroRIVERS_{region_code}/**/HydroRIVERS_v10_{region_code}.shp"))
    if candidates:
        return candidates[0]
    return None


def load_hr_region(region_code):
    """Load and return a HydroRIVERS regional shapefile."""
    shp = find_hr_shapefile(region_code)
    if shp is None:
        # Try to unzip first
        zipfile = HR_DIR / f"HydroRIVERS_v10_{region_code}_shp.zip"
        if zipfile.exists():
            import zipfile as zf
            outdir = HR_DIR / f"HydroRIVERS_{region_code}"
            outdir.mkdir(exist_ok=True)
            with zf.ZipFile(zipfile) as z:
                z.extractall(outdir)
            shp = find_hr_shapefile(region_code)
        if shp is None:
            print(f"  WARNING: HydroRIVERS region '{region_code}' not found")
            return None
    return gpd.read_file(shp)


def compute_basin_flow_order(basin_name, basin_bcu, hr_data):
    """
    Compute country flow order for a single basin.

    Returns:
        dict with keys:
            'main_stem_order': [(country, median_dist_dn, n_reaches), ...] sorted source→mouth
            'tributary_only': [country, ...] countries in network but not on main stem
            'no_reaches': [country, ...] countries with no HR reaches at all
            'stats': dict with metadata
    """
    basin_union = basin_bcu.union_all()
    if basin_union is None or basin_union.is_empty:
        return None

    bounds = basin_union.bounds  # (minx, miny, maxx, maxy)

    # Broad bbox filter on HydroRIVERS
    hr_area = hr_data[
        (hr_data.geometry.bounds['minx'] <= bounds[2]) &
        (hr_data.geometry.bounds['maxx'] >= bounds[0]) &
        (hr_data.geometry.bounds['miny'] <= bounds[3]) &
        (hr_data.geometry.bounds['maxy'] >= bounds[1])
    ]

    if len(hr_area) == 0:
        return None

    # Fine intersection with basin polygon
    in_basin = hr_area[hr_area.intersects(basin_union)]
    if len(in_basin) == 0:
        return None

    # Find main river network (largest upstream area)
    main_riv_id = in_basin.loc[in_basin['UPLAND_SKM'].idxmax(), 'MAIN_RIV']
    main_net = in_basin[in_basin['MAIN_RIV'] == main_riv_id]

    # --- Trace main stem via NEXT_DOWN chain ---
    mouth = main_net[main_net['NEXT_DOWN'] == 0]
    if len(mouth) == 0:
        mouth = main_net.nsmallest(1, 'DIST_DN_KM')

    # Build reverse lookup: downstream_id → list of upstream reaches
    upstream_of = defaultdict(list)
    for _, row in main_net.iterrows():
        if row['NEXT_DOWN'] != 0:
            upstream_of[row['NEXT_DOWN']].append(row)

    # Trace from mouth upstream, always following largest UPLAND_SKM
    main_stem_ids = set()
    current_id = mouth.iloc[0]['HYRIV_ID']
    main_stem_ids.add(current_id)
    while current_id in upstream_of:
        upstreams = upstream_of[current_id]
        best = max(upstreams, key=lambda r: r['UPLAND_SKM'])
        main_stem_ids.add(best['HYRIV_ID'])
        current_id = best['HYRIV_ID']

    main_stem = main_net[main_net['HYRIV_ID'].isin(main_stem_ids)]

    # --- Compute per-country ordering ---
    all_countries = set(basin_bcu['adm0_name'])
    main_stem_results = []
    network_countries = set()

    for _, crow in basin_bcu.iterrows():
        cname = crow['adm0_name']
        cgeom = crow.geometry

        # Check main stem presence
        on_stem = main_stem[main_stem.intersects(cgeom)]
        if len(on_stem) > 0:
            main_stem_results.append((
                cname,
                float(on_stem['DIST_DN_KM'].median()),
                int(len(on_stem))
            ))
            network_countries.add(cname)
            continue

        # Check full network presence (catches source countries with low-order headwaters)
        in_network = main_net[main_net.intersects(cgeom)]
        if len(in_network) > 0:
            network_countries.add(cname)

    # Sort main stem countries by median DIST_DN_KM descending (source first)
    main_stem_results.sort(key=lambda x: -x[1])

    # Countries in network but not on main stem
    stem_countries = {r[0] for r in main_stem_results}
    tributary_only = sorted(network_countries - stem_countries)
    no_reaches = sorted(all_countries - network_countries)

    return {
        'main_stem_order': [(c, d, n) for c, d, n in main_stem_results],
        'tributary_only': tributary_only,
        'no_reaches': no_reaches,
        'stats': {
            'total_reaches_in_basin': int(len(in_basin)),
            'main_network_reaches': int(len(main_net)),
            'main_stem_reaches': int(len(main_stem)),
            'main_stem_km': float(main_stem['DIST_DN_KM'].max()) if len(main_stem) > 0 else 0,
            'endorheic': bool(main_net['ENDORHEIC'].max() > 0),
        }
    }


def apply_to_database(results, db_path, dry_run=True):
    """Update flows_through relationships with Rank values."""
    conn = sqlite3.connect(db_path)

    # Build river name → MRGID lookup from DB
    river_lookup = {}
    rows = conn.execute("""
        SELECT DISTINCT e.name, e.mrgid
        FROM entities e
        JOIN relationships r ON e.mrgid = r.source_mrgid
        WHERE r.relationship = 'flows_through'
    """).fetchall()
    for name, mrgid in rows:
        river_lookup[name] = mrgid

    # Build TFDD basin name → DB river name mapping
    # Explicit aliases for names that differ between TFDD and DB
    BASIN_TO_DB_ALIASES = {
        'Shu/Chu': 'Chu River',
        'Douro/Duero': 'Duero',
        'Rio Grande (North America)': 'Rio Grande',
        'St. John (North America)': None,  # No match in DB (different from Africa)
        'Rio Grande (South America)': None,  # Ambiguous with North America
        'Vanimo-Green': 'Green River',
    }

    updates = []
    matched = 0
    unmatched_basins = []

    for basin_name, data in results.items():
        if data is None:
            continue

        # Find matching river in DB
        mrgid = None

        # Check explicit aliases first
        if basin_name in BASIN_TO_DB_ALIASES:
            alias = BASIN_TO_DB_ALIASES[basin_name]
            if alias is None:
                unmatched_basins.append(basin_name)
                continue
            if alias in river_lookup:
                mrgid = river_lookup[alias]

        # Try exact match
        if mrgid is None and basin_name in river_lookup:
            mrgid = river_lookup[basin_name]

        if mrgid is None:
            # Try with common suffixes/variations
            for db_name, db_mrgid in river_lookup.items():
                # Strip "River", "river" suffix from DB name for matching
                db_base = db_name.replace(' River', '').replace(' river', '').strip()
                tfdd_base = basin_name.split('/')[0].split('-')[0].strip()
                if db_base.lower() == tfdd_base.lower():
                    mrgid = db_mrgid
                    break

        if mrgid is None:
            unmatched_basins.append(basin_name)
            continue

        matched += 1
        order = data['main_stem_order']

        for rank, (country, median_dist, n_reaches) in enumerate(order):
            updates.append({
                'river_mrgid': mrgid,
                'river_name': basin_name,
                'country': country,
                'rank': rank,
                'median_dist_dn_km': round(median_dist, 1),
                'position': 'source' if rank == 0 else ('mouth' if rank == len(order) - 1 else 'middle'),
            })

        # Tributary-only countries get rank = -1 (or a special marker)
        for country in data.get('tributary_only', []):
            updates.append({
                'river_mrgid': mrgid,
                'river_name': basin_name,
                'country': country,
                'rank': -1,  # tributary_only marker
                'median_dist_dn_km': None,
                'position': 'tributary_only',
            })

    print(f"\n=== Database update summary ===")
    print(f"Basins with flow order computed: {len([v for v in results.values() if v])}")
    print(f"Basins matched to DB rivers: {matched}")
    print(f"Basins unmatched: {len(unmatched_basins)}")
    print(f"Relationship updates to apply: {len(updates)}")

    if unmatched_basins and len(unmatched_basins) <= 20:
        print(f"\nUnmatched basins (sample): {unmatched_basins[:20]}")

    if dry_run:
        print("\n[DRY RUN] No changes applied. Use --apply to update the database.")
        # Save updates to JSON for review
        with open(OUTPUT_PATH.with_suffix('.updates.json'), 'w') as f:
            json.dump(updates, f, indent=2)
        print(f"Updates saved to {OUTPUT_PATH.with_suffix('.updates.json')}")
    else:
        # Apply updates
        applied = 0
        for u in updates:
            # Find the existing relationship
            rows = conn.execute("""
                SELECT id FROM relationships
                WHERE source_mrgid = ? AND relationship = 'flows_through' AND target_name = ?
            """, (u['river_mrgid'], u['country'])).fetchall()

            if not rows:
                # Try partial country name match
                rows = conn.execute("""
                    SELECT id, target_name FROM relationships
                    WHERE source_mrgid = ? AND relationship = 'flows_through'
                    AND target_name LIKE ?
                """, (u['river_mrgid'], f"%{u['country'][:10]}%")).fetchall()

            for (rel_id, *_) in rows:
                conn.execute("""
                    UPDATE relationships
                    SET attr_name = 'Rank', attr_value = ?
                    WHERE id = ?
                """, (str(u['rank']), rel_id))
                applied += 1

        conn.commit()
        print(f"\nApplied {applied} updates to database.")

    conn.close()
    return updates


def main():
    parser = argparse.ArgumentParser(description='Compute river flow order from HydroRIVERS')
    parser.add_argument('--apply', action='store_true', help='Apply results to database (default: dry run)')
    parser.add_argument('--basin', type=str, help='Process a single basin by name')
    parser.add_argument('--continent', type=str, help='Process a single continent (AF, AS, EU, NA, SA)')
    args = parser.parse_args()

    print("=== River Flow Order Computation ===")
    print(f"Source: HydroRIVERS v10 (WWF/McGill)")
    print(f"Target: {DB_PATH}")
    print()

    # Load BCU data
    print("Loading TFDD BCU shapefile...")
    t0 = time.time()
    bcu = gpd.read_file(BCU_PATH).to_crs(epsg=4326)
    print(f"  {len(bcu)} BCU polygons loaded in {time.time()-t0:.1f}s")

    # Group basins by continent
    basins_by_continent = defaultdict(list)
    for basin_name in bcu['Basin_Name'].unique():
        continent = bcu[bcu['Basin_Name'] == basin_name].iloc[0]['Continent_']
        basins_by_continent[continent].append(basin_name)

    if args.basin:
        # Single basin mode
        basin_bcu = bcu[bcu['Basin_Name'] == args.basin]
        if len(basin_bcu) == 0:
            print(f"Basin '{args.basin}' not found. Available basins:")
            for name in sorted(bcu['Basin_Name'].unique()):
                if args.basin.lower() in name.lower():
                    print(f"  {name}")
            sys.exit(1)

        continent = basin_bcu.iloc[0]['Continent_']
        regions = CONTINENT_TO_REGIONS.get(continent, [])

        hr_frames = []
        for region in regions:
            print(f"Loading HydroRIVERS {region}...")
            hr = load_hr_region(region)
            if hr is not None:
                hr_frames.append(hr)

        if not hr_frames:
            print("No HydroRIVERS data available")
            sys.exit(1)

        import pandas as pd
        hr_combined = pd.concat(hr_frames, ignore_index=True)
        hr_combined = gpd.GeoDataFrame(hr_combined, crs=hr_frames[0].crs)

        result = compute_basin_flow_order(args.basin, basin_bcu, hr_combined)
        if result:
            print(f"\n=== {args.basin} ===")
            print(f"Main stem: {result['stats']['main_stem_reaches']} reaches, {result['stats']['main_stem_km']:.0f} km")
            print(f"Endorheic: {result['stats']['endorheic']}")
            print(f"\nFlow order (source → mouth):")
            for i, (country, dist, n) in enumerate(result['main_stem_order']):
                label = "SOURCE" if i == 0 else ("MOUTH" if i == len(result['main_stem_order'])-1 else "")
                print(f"  Rank {i}: {country:35s} (median {dist:.0f} km from outlet, {n} reaches) {label}")
            if result['tributary_only']:
                print(f"\nTributary-only: {result['tributary_only']}")
            if result['no_reaches']:
                print(f"No reaches: {result['no_reaches']}")
        else:
            print(f"No results for {args.basin}")
        return

    # Full run: process all continents
    continents_to_process = [args.continent] if args.continent else list(CONTINENT_TO_REGIONS.keys())

    all_results = {}
    total_basins = 0
    total_computed = 0
    total_failed = 0

    for continent in continents_to_process:
        basins = basins_by_continent.get(continent, [])
        if not basins:
            continue

        regions = CONTINENT_TO_REGIONS.get(continent, [])
        print(f"\n{'='*60}")
        print(f"Continent: {continent} ({len(basins)} basins)")
        print(f"HydroRIVERS regions: {regions}")

        # Load HR data for this continent
        hr_frames = []
        for region in regions:
            print(f"  Loading HydroRIVERS {region}...", end=" ", flush=True)
            t0 = time.time()
            hr = load_hr_region(region)
            if hr is not None:
                hr_frames.append(hr)
                print(f"{len(hr):,} reaches in {time.time()-t0:.1f}s")
            else:
                print("NOT FOUND")

        if not hr_frames:
            print(f"  No HydroRIVERS data for {continent}")
            for basin in basins:
                all_results[basin] = None
                total_failed += 1
            continue

        import pandas as pd
        hr_combined = pd.concat(hr_frames, ignore_index=True)
        hr_combined = gpd.GeoDataFrame(hr_combined, crs=hr_frames[0].crs)
        print(f"  Combined: {len(hr_combined):,} reaches")

        # Process each basin
        for basin_name in sorted(basins):
            total_basins += 1
            basin_bcu = bcu[bcu['Basin_Name'] == basin_name]

            t0 = time.time()
            try:
                result = compute_basin_flow_order(basin_name, basin_bcu, hr_combined)
            except Exception as e:
                print(f"  ERROR {basin_name}: {e}")
                all_results[basin_name] = None
                total_failed += 1
                continue

            elapsed = time.time() - t0

            if result:
                order = result['main_stem_order']
                order_str = " → ".join(c for c, _, _ in order)
                trib = f" +{len(result['tributary_only'])} trib" if result['tributary_only'] else ""
                print(f"  {basin_name:40s} {order_str}{trib}  ({elapsed:.1f}s)")
                all_results[basin_name] = result
                total_computed += 1
            else:
                print(f"  {basin_name:40s} NO RESULT ({elapsed:.1f}s)")
                all_results[basin_name] = None
                total_failed += 1

    # Save results
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"  Total basins: {total_basins}")
    print(f"  Computed: {total_computed}")
    print(f"  Failed: {total_failed}")

    # Serialize results (convert tuples to lists for JSON)
    serializable = {}
    for basin, data in all_results.items():
        if data is not None:
            serializable[basin] = {
                'main_stem_order': [{'country': c, 'median_dist_dn_km': round(d, 1), 'n_reaches': n}
                                    for c, d, n in data['main_stem_order']],
                'tributary_only': data['tributary_only'],
                'no_reaches': data['no_reaches'],
                'stats': data['stats'],
            }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(serializable, f, indent=2)
    print(f"\nResults saved to {OUTPUT_PATH}")

    # Apply to database
    apply_to_database(all_results, DB_PATH, dry_run=not args.apply)


if __name__ == '__main__':
    main()
