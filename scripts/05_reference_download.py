"""Download the reference data that needs no account.

  * OCHA COD-AB DRC administrative boundaries (HDX `cod-ab-cod`, levels 0-3)
      -> data/raw/boundaries/ocha/cod_admin{0,1,2,3}.shp ...
  * UCDP Georeferenced Event Dataset, GED v26.1 (used to validate ACLED)
      -> data/raw/ucdp/GEDEvent_v26_1.csv
"""
import io
import zipfile

try:  # Windows certificate store (CGIAR TLS proxy)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
import requests

import config as C

HDX = "https://data.humdata.org/api/3/action/package_show?id=cod-ab-cod"
UCDP = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"


def unzip(url, dest):
    dest.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, timeout=900)
    r.raise_for_status()
    zipfile.ZipFile(io.BytesIO(r.content)).extractall(dest)
    print(f"  {url.rsplit('/', 1)[1]} -> {dest.relative_to(C.ROOT)}")


def main():
    ocha = C.RAW / "boundaries" / "ocha"
    if not (ocha / "cod_admin3.shp").exists():
        res = requests.get(HDX, timeout=120).json()["result"]["resources"]
        url = next(r["url"] for r in res if r["name"] == "cod_admin_boundaries.shp.zip")
        unzip(url, ocha)
    else:
        print("OCHA boundaries: already present")
    ucdp = C.RAW / "ucdp"
    if not any(ucdp.glob("GEDEvent_v26*.csv")):
        unzip(UCDP, ucdp)
    else:
        print("UCDP GED: already present")


if __name__ == "__main__":
    main()
