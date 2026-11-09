"""Aggregate WorldPop Global2 1 km rasters (2015-2025) to DRC Admin 3 (OCHA, 519 units).

Method: zonal sums. Each 1 km pixel is assigned to the Admin 3 unit containing its
centre (keeps national totals exact). Units too small to contain any pixel centre
(some urban communes) get an area-weighted share of the pixels they touch; these are
flagged with pop_method = "fractional".

Output: output/worldpop_admin3_year.csv/.dta  (admin3 x year), with
  pop_total            WorldPop population count raster
  m_00 ... f_90        age-sex counts (00 = <1, 01 = 1-4, 05 = 5-9, ..., 90 = 90+)
  pop_u5, pop_0_14, pop_15_64, pop_65p, women_15_49
  sex_ratio (males per 100 females), dependency_ratio, pop_density_km2
"""
import re

import numpy as np
import pandas as pd
import geopandas as gpd
import rasterio
from rasterio import features
from rasterio.windows import from_bounds
from shapely.geometry import box

import config as C

ADM3 = C.RAW / "boundaries" / "ocha" / "cod_admin3.shp"
WP = C.RAW / "worldpop"
ID = ["adm3_pcode", "adm3_name", "adm2_pcode", "adm2_name", "adm1_pcode", "adm1_name"]
AGES = ["00", "01"] + [f"{a:02d}" for a in range(5, 95, 5)]


def layer_name(path):
    m = re.match(r"cod_(pop|[mf]_\d\d)_\d{4}_", path.name)
    return "pop_total" if m.group(1) == "pop" else m.group(1)


def read(path):
    with rasterio.open(path) as src:
        a = src.read(1, masked=True).filled(0).astype("float64")
    a[a < 0] = 0
    return a


def main():
    adm = gpd.read_file(ADM3, encoding="cp1252")
    adm["geometry"] = adm.geometry.make_valid()
    adm["area_km2"] = adm.to_crs("EPSG:6933").area / 1e6
    years = sorted(p.name for p in WP.iterdir() if p.is_dir())
    ref = next((WP / years[0]).glob("cod_pop_*.tif"))
    with rasterio.open(ref) as src:
        transform, shape, crs = src.transform, src.shape, src.crs
    adm = adm.to_crs(crs)

    # label raster: 1..n by pixel centre, 0 = outside
    labels = features.rasterize(((g, i + 1) for i, g in enumerate(adm.geometry)),
                                out_shape=shape, transform=transform, fill=0, dtype="int32")
    npx = np.bincount(labels.ravel(), minlength=len(adm) + 1)[1:]
    small = np.where(npx == 0)[0]
    print(f"{len(adm)} units; {len(small)} without a pixel centre -> fractional: "
          f"{list(adm.adm3_name.iloc[small])}")

    # fractional weights for the small units: (row, col, share of pixel area)
    frac = {}
    for i in small:
        g = adm.geometry.iloc[i]
        win = from_bounds(*g.bounds, transform=transform).round_offsets().round_lengths()
        r0, c0 = int(win.row_off), int(win.col_off)
        cells = []
        for r in range(r0, r0 + max(int(win.height), 1) + 1):
            for c in range(c0, c0 + max(int(win.width), 1) + 1):
                x0, y0 = transform * (c, r)
                x1, y1 = transform * (c + 1, r + 1)
                px = box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))
                s = px.intersection(g).area / px.area
                if s > 0:
                    cells.append((r, c, s))
        frac[i] = cells

    rows = []
    for y in years:
        files = sorted((WP / y).glob("*.tif"))
        rec = {}
        for f in files:
            a = read(f)
            v = np.bincount(labels.ravel(), weights=a.ravel(), minlength=len(adm) + 1)[1:]
            for i, cells in frac.items():
                v[i] = sum(a[r, c] * s for r, c, s in cells)
            rec[layer_name(f)] = v
        df = pd.DataFrame(rec)
        df.insert(0, "year", int(y))
        rows.append(pd.concat([adm[ID + ["area_km2"]].reset_index(drop=True), df], axis=1))
        print(f"{y}: {len(files)} layers, DRC total {df.pop_total.sum() / 1e6:.1f} M")
    out = pd.concat(rows, ignore_index=True)

    m = lambda ages: out[[f"m_{a}" for a in ages]].sum(axis=1)
    f = lambda ages: out[[f"f_{a}" for a in ages]].sum(axis=1)
    out["pop_u5"] = m(["00", "01"]) + f(["00", "01"])
    out["pop_0_14"] = m(AGES[:4]) + f(AGES[:4])
    out["pop_15_64"] = m(AGES[4:14]) + f(AGES[4:14])
    out["pop_65p"] = m(AGES[14:]) + f(AGES[14:])
    out["women_15_49"] = f(AGES[4:11])
    out["sex_ratio"] = 100 * m(AGES) / f(AGES)
    out["dependency_ratio"] = 100 * (out.pop_0_14 + out.pop_65p) / out.pop_15_64
    out["pop_density_km2"] = out.pop_total / out.area_km2
    out["agesex_sum_check"] = (m(AGES) + f(AGES)) / out.pop_total
    out["pop_method"] = "centre"
    out.loc[out.adm3_pcode.isin(adm.adm3_pcode.iloc[small]), "pop_method"] = "fractional"

    agesex = [f"{s}_{a}" for s in "mf" for a in AGES]
    cols = ID + ["year", "area_km2", "pop_total", "pop_density_km2", "pop_u5", "pop_0_14",
                 "pop_15_64", "pop_65p", "women_15_49", "sex_ratio", "dependency_ratio"] \
        + agesex + ["agesex_sum_check", "pop_method"]
    out = out[cols].round(2)
    out.to_csv(C.OUT / "worldpop_admin3_year.csv", index=False, encoding="utf-8-sig")
    out.to_stata(C.OUT / "worldpop_admin3_year.dta", write_index=False, version=118)
    print(f"saved output/worldpop_admin3_year.csv/.dta ({len(out):,} rows, {out.shape[1]} cols)")


if __name__ == "__main__":
    main()
