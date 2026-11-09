"""Download ERA5-Land monthly mean 2 m temperature for DR Congo from the Copernicus CDS.

Setup (once):
  1. Create a free account at https://cds.climate.copernicus.eu
  2. Accept the dataset licence: open the ERA5-Land monthly means page ->
     'Download' tab -> 'Terms of use' -> Accept.
  3. Put your Personal Access Token (from your CDS profile page) in
     %USERPROFILE%\\.cdsapirc :
         url: https://cds.climate.copernicus.eu/api
         key: <PERSONAL-ACCESS-TOKEN>
  4. pip install "cdsapi>=0.7.7"

Output: data/raw/era5land/era5land_t2m_monthly_<y0>_<y1>.nc  (one file per 5-yr chunk)
"""
try:  # use the Windows certificate store (needed behind the CGIAR TLS proxy)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

import cdsapi

import config as C

DATASET = "reanalysis-era5-land-monthly-means"


def chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i:i + n]


def main():
    client = cdsapi.Client()
    for years in chunks(C.ERA5_YEARS, 5):
        target = C.ERA5_DIR / f"era5land_t2m_monthly_{years[0]}_{years[-1]}.nc"
        if target.exists():
            print(f"skip (exists): {target.name}")
            continue
        print(f"requesting {years[0]}-{years[-1]} ...")
        client.retrieve(DATASET, {
            "product_type": ["monthly_averaged_reanalysis"],
            "variable": ["2m_temperature"],
            "year": [str(y) for y in years],
            "month": [f"{m:02d}" for m in range(1, 13)],
            "time": ["00:00"],
            "area": C.DRC_AREA,
            "data_format": "netcdf",
            "download_format": "unarchived",
        }, str(target))
        print(f"  saved {target.name}")


if __name__ == "__main__":
    main()
