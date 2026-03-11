# Candidate Sources: Cross-Border Rivers

## Summary
9 sources probed. 8 reachable, 1 down. 3 top picks identified.

## Source Table

| # | Source Name | URL | Tier | Type | Format | Scope | Maintainer | Reachable |
|---|------------|-----|------|------|--------|-------|------------|-----------|
| 1 | OSU TFDD Spatial Database | [transboundarywaters.ceoas.oregonstate.edu](https://transboundarywaters.ceoas.oregonstate.edu/transboundary-freshwater-spatial-database) | Primary | Database | Shapefile | 313 transboundary river basins worldwide (2024 update) | Oregon State University, Program in Water Conflict Management | YES |
| 2 | OSU Spatial Datasets Downloads | [oregonstate.edu/spatial-datasets](https://transboundarywaters.ceoas.oregonstate.edu/spatial-datasets) | Primary | Database | Shapefile | Same as #1 (duplicate page) | Oregon State University | YES |
| 3 | TFDD Explorer | [tfddmgmt.github.io/tfdd](https://tfddmgmt.github.io/tfdd/index.html) | Primary | Interactive Map | TopoJSON/CSV (in GitHub repo) | Interactive view of 313 basins + treaties + events | Oregon State University | YES |
| 4 | UNESCO IHP-WINS | [ihp-wins.unesco.org](https://ihp-wins.unesco.org/dataset/transboundary-river-basins-around-the-world) | Primary | Database | Shapefile | Transboundary basins across 151 countries | UNESCO Intergovernmental Hydrological Programme | YES |
| 5 | GRDC Major River Basins | [mrb.grdc.bafg.de](https://mrb.grdc.bafg.de/) | Primary | Database | GeoJSON + Shapefile | 520 major river/lake basins, 250+ transboundary | Global Runoff Data Centre, Germany Federal Institute of Hydrology | YES |
| 6 | TWAP River Basins (UNEP-DHI) | [unepdhi.org/twap-rivers](https://unepdhi.org/twap-rivers/) | Primary | Database | GIS (unverified) | 286 transboundary basins with indicators | UNEP-DHI Centre | PARTIAL (portal timed out) |
| 7 | World Bank Major River Basins | [datacatalog.worldbank.org](https://datacatalog.worldbank.org/search/dataset/0041426) | Primary | Database | Shapefile + ArcGIS FeatureServer API | Major and largest basins worldwide | World Bank Group | YES |
| 8 | HydroRIVERS (WWF) | [hydrosheds.org](https://www.hydrosheds.org/products/hydrorivers) | Primary | Database | Shapefile + Geodatabase | 8.5M river reaches globally | WWF / HydroSHEDS | YES |
| 9 | Water Action Hub | [riverbasins.wateractionhub.org](http://riverbasins.wateractionhub.org/) | Unknown | Interactive Map | Unknown | Unknown | Unknown | DOWN |

## Key Findings

- **Best for our needs (river name + countries):** OSU TFDD (#1), GRDC (#5), World Bank (#7)
- **Only source with a live API:** World Bank (#7) — ArcGIS FeatureServer
- **Best format for programmatic use:** GRDC (#5) — offers GeoJSON
- **Most purpose-built for transboundary analysis:** OSU TFDD (#1) — Basin Country Units explicitly link basins to countries
- **Limitation:** HydroRIVERS (#8) has detailed geometry but NO river names or country fields
- **Dead:** Water Action Hub (#9) is down
