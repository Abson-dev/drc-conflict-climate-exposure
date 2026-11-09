# DRC conflict, temperature and population exposure

This repository builds conflict, temperature and population exposure measures for the Democratic Republic of the Congo, at two levels:

1. **Survey clusters**, using 10, 25 and 50 km buffers around each cluster's GPS point:
   - conflict from ACLED, 1997–2025
   - population from WorldPop, 2015–2025
   - temperature from ERA5-Land, 1991–2025
2. **Admin 3 units**, the 519 OCHA communes, secteurs and chefferies:
   - temperature from ERA5-Land
   - population and age-sex structure from WorldPop

Every table is saved as both `.csv` and Stata `.dta`.

## Repository layout

```
├── scripts/                     pipeline, run in numerical order
│   ├── config.py                years, buffers, bounding box, paths
│   ├── 01_acled_download_api.py ACLED through the API (OAuth)          ┐ choose one
│   ├── 02_acled_clean.py        clean a manual ACLED export             ┘
│   ├── 03_era5land_download.py  ERA5-Land monthly 2 m temperature (CDS)
│   ├── 04_worldpop_download.py  WorldPop Global2 1 km population + age/sex
│   ├── 05_reference_download.py OCHA Admin boundaries + UCDP GED
│   ├── 06_cluster_exposure.py   cluster-level exposure (10/25/50 km)
│   ├── 07_era5land_admin3.py    temperature by Admin 3
│   ├── 08_worldpop_admin3.py    population by Admin 3
│   ├── 09_validate_acled_ucdp.py ACLED vs UCDP GED comparison
│   └── 10_acled_location_exposure.py exposure around ACLED event locations (no survey needed)
├── docs/
│   ├── data_sources.md          sources, versions, licences, access steps
│   ├── methods.md               how each measure is built, variable list
│   └── validation.md            ACLED consistency checks and UCDP comparison
├── data/                        not tracked by git (see data/README.md)
│   ├── raw/{acled,era5land,worldpop,ucdp,boundaries}/
│   └── clusters/                survey cluster GPS file goes here
├── output/                      not tracked by git: generated tables
└── environment.yml
```

## Setup

```bash
conda env create -f environment.yml
conda activate drc-exposure
```

You need three things for data access. Full steps are in [docs/data_sources.md](docs/data_sources.md).

| Source | Account | Credentials |
|---|---|---|
| ACLED | myACLED, free for research | `ACLED_EMAIL`, `ACLED_PASSWORD` environment variables, or a manual export |
| Copernicus CDS (ERA5-Land) | free | `~/.cdsapirc` with your Personal Access Token |
| DHS cluster GPS | DHS Program, approved project | the GE shapefile goes in `data/clusters/` |

WorldPop, OCHA boundaries and UCDP need no account.

## Run

```bash
python scripts/02_acled_clean.py          # or 01_acled_download_api.py
python scripts/03_era5land_download.py
python scripts/04_worldpop_download.py
python scripts/05_reference_download.py
python scripts/06_cluster_exposure.py     # needs data/clusters/<file>
python scripts/07_era5land_admin3.py
python scripts/08_worldpop_admin3.py
python scripts/09_validate_acled_ucdp.py
python scripts/10_acled_location_exposure.py
```
Script 06 needs survey clusters. Script 10 does not: it uses the 5,268 distinct ACLED event locations as its points.

## Outputs (`output/`)

| File | Unit | Content |
|---|---|---|
| `cluster_year_exposure` | cluster × year, 1997–2025 | ACLED counts by type and fatalities; WorldPop population (all ages, under-5, 0–14, women 15–49) and events per 100k; ERA5 temperature mean, anomaly and SD anomaly. Each measure is given for 10, 25 and 50 km. |
| `cluster_interview_exposure` | cluster | The same measures for the 12 months before the interview. Produced only if interview dates are supplied. |
| `acled_locations` | ACLED location (5,268) | `loc_id`, coordinates, place and admin names, event totals |
| `acled_location_year_exposure` | location × year, 1997–2025 | ACLED counts by type and fatalities, WorldPop population and events per 100k, for 10, 25 and 50 km |
| `acled_event_exposure` | ACLED event (43,275) | Event attributes and the population within 10, 25 and 50 km in the event year, i.e. the people exposed |
| `era5land_admin3_monthly` | Admin 3 × month, 1991–2025 | Temperature (°C), anomaly against 1991–2020, SD anomaly |
| `era5land_admin3_year` | Admin 3 × year | Mean, warmest month, coolest month, anomaly, SD anomaly |
| `worldpop_admin3_year` | Admin 3 × year, 2015–2025 | Population, 40 age-sex groups, under-5, 0–14, 15–64, 65+, women 15–49, sex ratio, dependency ratio, density |
| `validation/*` | | ACLED vs UCDP GED comparison tables |

Merge Admin 3 tables on `adm3_pcode`, not on names. The variable definitions and methodological choices are in [docs/methods.md](docs/methods.md).

## Data licences

The raw data and the generated outputs are **not** included in this repository. ACLED's terms of use do not allow redistributing its event data, and DHS GPS data may be used only by the approved project. The sources and their citations are listed in [docs/data_sources.md](docs/data_sources.md).
