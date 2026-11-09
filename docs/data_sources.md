# Data sources

## ACLED — Armed Conflict Location & Event Data
- **Coverage:** DR Congo (ISO 180), 1997-02-27 to 2025-11-09, 43,275 events.
- **Access:** create a free myACLED account at https://acleddata.com. Then either:
  - **API:** set `ACLED_EMAIL` and `ACLED_PASSWORD` and run `01_acled_download_api.py`. It uses OAuth (`https://acleddata.com/oauth/token`, `client_id=acled`), with paging of 5,000 rows.
  - **Manual export:** use the Data Export Tool, save the CSV in `data/raw/acled/`, and run `02_acled_clean.py`. The current file is a manual export dated 2026-11-09 that covers 20 East and Central African countries. The script keeps the DRC rows.
- **Licence:** ACLED Terms of Use. Raw event data may not be redistributed, which is why `data/` is not tracked.
- **Citation:** Raleigh, C., Kishi, R. & Linke, A. (2023). Political instability patterns are obscured by conflict dataset scope conditions, sources, and coding choices. *Humanities and Social Sciences Communications*, 10, 74. The ACLED export date must also be cited.

## ERA5-Land — monthly averaged reanalysis
- **Variable and coverage:** `2m_temperature` (K, converted to °C), 0.1° grid (about 11 km), monthly means 1991–2025.
- **Area:** the bounding box [N 5.7, W 11.9, S −13.8, E 31.6].
- **Dataset:** `reanalysis-era5-land-monthly-means`, product type `monthly_averaged_reanalysis`.
- **Access:**
  1. Create a free account at https://cds.climate.copernicus.eu.
  2. Accept the dataset licence on its Download tab.
  3. Put the following in `~/.cdsapirc`:
     ```
     url: https://cds.climate.copernicus.eu/api
     key: <PERSONAL-ACCESS-TOKEN>
     ```
- **Licence:** CC-BY 4.0.
- **Citation:** Muñoz Sabater, J. (2019). ERA5-Land monthly averaged data from 1950 to present. Copernicus Climate Change Service (C3S) Climate Data Store. doi:10.24381/cds.68d2bb30.

## WorldPop Global2 (R2025A v1)
- **Product:** constrained, UN-adjusted, 1 km resolution, 2015–2025.
  - Population counts (`G2_CN_POP_R25A_1km`): doi:10.5258/SOTON/WP00840
  - Age and sex structures (`G2_CN_Age_R25A_1km`): doi:10.5258/SOTON/WP00842
  - Age groups are `00` (<1), `01` (1–4), `05` (5–9) and so on up to `90` (90+), separately for `m` and `f`.
- **Access:** open. The files are listed through `https://hub.worldpop.org/rest/data/...?iso3=COD`.
- **Licence:** CC-BY 4.0.
- **Not used:** Global1 (2000–2020) is a different method and is not mixed in.

## OCHA COD-AB — DRC administrative boundaries
- **Source:** HDX dataset `cod-ab-cod`, version v01, valid from 2019-09-11.
- **Levels:**
  - Admin 1: 26 provinces
  - Admin 2: 164 territoires and villes
  - Admin 3: 519 communes, secteurs and chefferies
- **Encoding:** the `.cpg` file says UTF-8, but the attribute table is Latin-1, so the scripts read it with `encoding="cp1252"`.
- **Licence:** CC BY-IGO.
- **Not used:** geoBoundaries labels its DRC territoire level as "ADM3" (188 units), which is not the same as the OCHA Admin 3 level.

## UCDP GED v26.1 (validation only)
- **Source:** Uppsala Conflict Data Program, Georeferenced Event Dataset, 1989–2025. https://ucdp.uu.se/downloads/
- **Citation:** Davies, S., Pettersson, T., Sollenberg, M. & Öberg, M. (2025). Organized violence 1989–2024. *Journal of Peace Research*. Also: Sundberg, R. & Melander, E. (2013). Introducing the UCDP Georeferenced Event Dataset. *Journal of Peace Research*, 50(4).

## DHS cluster GPS (not included)
- **Source:** the DHS Program GE (geographic) dataset for the DRC survey, for example `CDGE81FL`. Access requires an approved DHS project.
- **Displacement:** points are displaced by 0–2 km in urban areas and 0–5 km in rural areas, with 1% of rural points displaced by up to 10 km.
- **Interview dates:** taken from the household recode (`hv001`, `hv006`, `hv007`, `hv008`).

## Network note
On the CGIAR network, HTTPS traffic is inspected by a proxy with its own root certificate. The scripts call `truststore.inject_into_ssl()` so that Python uses the Windows certificate store.
