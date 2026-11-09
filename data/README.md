# data/

Git does not track this folder. The scripts recreate it as follows:

| Folder | Filled by | Contents |
|---|---|---|
| `raw/acled/` | `01_acled_download_api.py` or manual export + `02_acled_clean.py` | `acled_drc_1997_2025.csv` (43,275 DRC events, 1997-02-27 to 2025-11-09) |
| `raw/era5land/` | `03_era5land_download.py` | `era5land_t2m_monthly_<y0>_<y1>.nc` (0.1°, 1991–2025) |
| `raw/worldpop/<year>/` | `04_worldpop_download.py` | 41 GeoTIFFs per year (total population + 40 age-sex groups), 1 km |
| `raw/boundaries/ocha/` | `05_reference_download.py` | OCHA COD-AB `cod_admin0`–`cod_admin3` shapefiles |
| `raw/ucdp/` | `05_reference_download.py` | `GEDEvent_v26_1.csv` |
| `clusters/` | **you** | DHS GE shapefile (e.g. `CDGE81FL.shp`) or CSV `cluster_id, lat, lon[, interview_date]` |
