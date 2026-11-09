# Methods

All settings are in [`scripts/config.py`](../scripts/config.py): years, buffers (`BUFFERS_KM = [10, 25, 50]`), bounding box, the 1991–2020 baseline and the ACLED precision filter.

## 1. Cluster-level exposure (`06_cluster_exposure.py`)

**Clusters.** The input is a DHS GE shapefile (`DHSCLUST`, `LATNUM`, `LONGNUM`) or a CSV with `cluster_id, lat, lon` and an optional `interview_date`. Clusters at (0, 0), which is how DHS codes missing GPS, are dropped.

### Conflict (ACLED)
- **Distances:** great-circle (haversine) distances from each cluster to every event, using a BallTree on a sphere of radius 6,371 km.
- **Precision filter:** events are kept only if `geo_precision` is 1 or 2. Precision-3 events (680, 1.6%) sit at a province centroid and would distort 10–50 km buffers. Set `MAX_GEO_PRECISION = 3` for a robustness check.
- **Counts per buffer *r*:**
  - `acled_events_{r}km`: all events
  - `acled_violent_{r}km`: battles, violence against civilians and explosions/remote violence
  - one count per event type: `acled_battles_*`, `acled_vac_*`, `acled_explosions_*`, `acled_riots_*`, `acled_protests_*`
  - `acled_fatalities_*`: fatalities
- **Time windows:** counts are given per calendar year (1997–2025) and, if interview dates are supplied, for the 365 days before the interview (`*_12m`).

### Population (WorldPop)
- **Method:** the sum of 1 km pixels whose centre is within *r* km of the cluster.
- **Groups:** `wp_pop_*` (total), `wp_u5_*` (under 5), `wp_0_14_*` (ages 0–14), `wp_women15_49_*` (women aged 15–49).
- **Years:** 2015–2025, blank before 2015. The interview file uses the interview year, clipped to 2015–2025 and recorded in `wp_year`.
- **Rates:** `acled_violent_per100k_*` and `acled_fatal_per100k_*` divide the counts by the population in the same buffer.

### Temperature (ERA5-Land)
- **Grid cell:** each cluster uses the nearest 0.1° cell that has data. ERA5-Land has no values over lakes and sea, so lakeshore clusters move to the nearest land cell, and `era5_cell_dist_km` records the distance.
- **Annual columns:**
  - `t2m_mean_c`: mean
  - `t2m_max_month_c`: warmest month
  - `t2m_anom_c`: mean of the monthly differences from the 1991–2020 average for each calendar month
  - `t2m_anom_sd`: the annual anomaly divided by the standard deviation of annual means over 1991–2020
- **Interview columns:** `t2m_mean_12m_c` and `t2m_anom_12m_c` cover the 12 calendar months before the interview month. `t2m_int_month_c` is the temperature in the interview month.

### Caveats
- **Smallest buffer:** DHS displacement is up to 5 km for rural clusters and up to 10 km for 1% of them, so 10 km is the smallest meaningful buffer.
- **Borders:** ACLED and WorldPop cover only the DRC, so buffers that cross a border leave out the events and people on the other side (Goma–Gisenyi, Bukavu–Cyangugu, Kinshasa–Brazzaville, Uvira–Bujumbura).
- **Coverage over time:** ACLED's coverage grows over time, from about 150 sources before 2010 to about 2,460 after 2018. Comparisons across years should account for this (see [validation.md](validation.md)).

## 2. Admin 3 temperature (`07_era5land_admin3.py`)
- **Weighting:** each ERA5-Land land cell is intersected with each OCHA Admin 3 polygon in an equal-area projection (EPSG:6933). The unit's value is the overlap-area-weighted mean of its cells (median 40 cells per unit). Urban communes smaller than one cell still get a value.
- **Weight file:** the weights are saved in `data/raw/boundaries/ocha/era5_admin3_weights.csv`.
- **Monthly file** (`era5land_admin3_monthly`): `t2m_c`, `t2m_anom_c` (against the 1991–2020 average for that calendar month) and `t2m_anom_sd` (the same anomaly divided by that month's standard deviation over 1991–2020).
- **Annual file** (`era5land_admin3_year`): `t2m_mean_c`, `t2m_max_month_c`, `t2m_min_month_c`, `t2m_anom_c` and `t2m_anom_sd`.

## 3. Admin 3 population (`08_worldpop_admin3.py`)
- **Zonal sums:** each 1 km pixel goes to the unit containing its centre, which keeps national totals exact. Units containing no pixel centre get an area-weighted share of the pixels they touch, flagged `pop_method = "fractional"`.
- **Columns:**
  - `pop_total`
  - `m_00` … `f_90`: the 40 age-sex groups
  - `pop_u5`, `pop_0_14`, `pop_15_64`, `pop_65p`, `women_15_49`
  - `sex_ratio`: males per 100 females
  - `dependency_ratio`: people aged 0–14 and 65+ per 100 people aged 15–64
  - `pop_density_km2`
  - `agesex_sum_check`: the sum of the age-sex groups divided by `pop_total`, which should be about 1

## 4. ACLED cleaning (`02_acled_clean.py`)
- Keep `country == "Democratic Republic of Congo"`.
- **Rusankuku (Mwenga, Sud-Kivu):** 7 events are geocoded at latitude +3.815, about 750 km north of Mwenga. The sign is wrong, so the latitude is set to −3.815 (`geo_fix = 1`).
- **Duplicates:** 41 records repeat another record's date, coordinates, type, actors and notes. They are flagged with `dup_flag = 1` and kept in the file, and `09_validate_acled_ucdp.py` excludes them.
