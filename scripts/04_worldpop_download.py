"""Download WorldPop Global2 (R2025A v1) demographic rasters for DR Congo.

Product: constrained, UN-adjusted, 1 km
  * population counts      (G2_CN_POP_R25A_1km,  doi:10.5258/SOTON/WP00840)
  * age & sex structures   (G2_CN_Age_R25A_1km,  doi:10.5258/SOTON/WP00842)
    m_/f_ x age groups 00 (<1), 01 (1-4), 05 (5-9) ... 85 (85-89), 90 (90+).
    The t_ (male + female) layers are skipped: they equal m_ + f_.
Files are listed through the WorldPop REST API, so URLs are never hard-coded.

Output: data/raw/worldpop/<year>/*.tif
"""
from concurrent.futures import ThreadPoolExecutor

try:  # Windows certificate store (CGIAR TLS proxy)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass
import requests

import config as C

API = "https://hub.worldpop.org/rest/data"
PRODUCTS = ["pop/G2_CN_POP_R25A_1km", "age_structures/G2_CN_Age_R25A_1km"]
YEARS = [str(y) for y in range(2015, 2026)]
DEST = C.RAW / "worldpop"


def file_list():
    urls = []
    for p in PRODUCTS:
        recs = requests.get(f"{API}/{p}", params={"iso3": "COD"}, timeout=120).json()["data"]
        for r in recs:
            if r["popyear"] in YEARS:
                urls += [(r["popyear"], f) for f in r["files"] if "/cod_t_" not in f]
    return urls


def fetch(item):
    year, url = item
    out = DEST / year / url.rsplit("/", 1)[1]
    out.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=600) as r:
        r.raise_for_status()
        size = int(r.headers.get("Content-Length", 0))
        if out.exists() and out.stat().st_size == size:
            return "skip"
        tmp = out.with_suffix(".part")
        with open(tmp, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
        if size and tmp.stat().st_size != size:
            raise IOError(f"incomplete: {out.name}")
        tmp.replace(out)
    return "ok"


def main():
    items = file_list()
    print(f"{len(items)} files for {YEARS[0]}-{YEARS[-1]}")
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(fetch, items))
    print({k: res.count(k) for k in set(res)})


if __name__ == "__main__":
    main()
