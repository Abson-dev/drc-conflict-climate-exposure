"""Aggregate ERA5-Land monthly 2 m temperature to DRC Admin 3 (OCHA COD-AB, 519 units).

Method: area-weighted mean. Each 0.1 deg ERA5-Land cell is intersected with each
Admin 3 polygon in an equal-area projection (EPSG:6933), and the unit's value is the
mean of the land cells it overlaps, weighted by overlap area. This also handles urban
communes smaller than one cell. ERA5-Land has no values over water (Lakes Tanganyika,
Kivu, Albert, Edward, Mai-Ndombe...), so only cells with data are used. A unit with no
land cell at all takes the cell nearest its centroid.

Inputs : data/raw/era5land/era5land_t2m_monthly_*.nc (03_era5land_download.py)
         data/raw/boundaries/ocha/cod_admin3.shp  (HDX cod-ab-cod, v01, 2019-09-11)
Outputs: output/era5land_admin3_monthly.csv/.dta   admin3 x month
         output/era5land_admin3_year.csv/.dta      admin3 x year
         data/raw/boundaries/ocha/era5_admin3_weights.csv  (cell weights, for checks)
"""
import numpy as np
import pandas as pd
import geopandas as gpd
from shapely.geometry import box

import config as C

ADM3 = C.RAW / "boundaries" / "ocha" / "cod_admin3.shp"
EA = "EPSG:6933"
ID = ["adm3_pcode", "adm3_name", "adm2_pcode", "adm2_name", "adm1_pcode", "adm1_name"]


def load_era5():
    # reuse the loader from the cluster script
    import importlib
    m = importlib.import_module("06_cluster_exposure")
    return m.load_era5()


def weights(t2m, adm):
    lat, lon = t2m.latitude.values, t2m.longitude.values
    dlat, dlon = abs(lat[1] - lat[0]) / 2, abs(lon[1] - lon[0]) / 2
    yy, xx = np.meshgrid(np.arange(len(lat)), np.arange(len(lon)), indexing="ij")
    valid = np.isfinite(t2m.isel(time=0).values)
    yi, xi = yy[valid], xx[valid]
    cells = gpd.GeoDataFrame(
        {"yi": yi, "xi": xi},
        geometry=[box(lon[x] - dlon, lat[y] - dlat, lon[x] + dlon, lat[y] + dlat) for y, x in zip(yi, xi)],
        crs="EPSG:4326")
    cand = gpd.sjoin(cells, adm[["adm3_pcode", "geometry"]], predicate="intersects")
    cand = cand.drop(columns="index_right")
    cg = cand.geometry.to_crs(EA).values
    ag = adm.set_index("adm3_pcode").geometry.to_crs(EA).loc[cand.adm3_pcode].values
    cand["area_km2"] = cg.intersection(ag).area / 1e6
    w = cand.loc[cand.area_km2 > 0, ["adm3_pcode", "yi", "xi", "area_km2"]].copy()

    # units with no land cell (e.g. tiny islands): nearest cell to centroid
    missing = adm.loc[~adm.adm3_pcode.isin(w.adm3_pcode)]
    if len(missing):
        from sklearn.neighbors import BallTree
        tree = BallTree(np.radians(np.column_stack([lat[yi], lon[xi]])), metric="haversine")
        cen = missing.geometry.to_crs(EA).centroid.to_crs("EPSG:4326")
        _, k = tree.query(np.radians(np.column_stack([cen.y, cen.x])), k=1)
        w = pd.concat([w, pd.DataFrame({"adm3_pcode": missing.adm3_pcode.values, "yi": yi[k[:, 0]],
                                        "xi": xi[k[:, 0]], "area_km2": 1.0})])
        print(f"  {len(missing)} unit(s) without land cell -> nearest cell: {list(missing.adm3_name)}")
    w["w"] = w.area_km2 / w.groupby("adm3_pcode").area_km2.transform("sum")
    return w


def save(df, name):
    df.to_csv(C.OUT / f"{name}.csv", index=False, encoding="utf-8-sig")
    df.to_stata(C.OUT / f"{name}.dta", write_index=False, version=118)
    print(f"saved output/{name}.csv/.dta  ({len(df):,} rows)")


def main():
    adm = gpd.read_file(ADM3, encoding="cp1252")   # .cpg says UTF-8 but file is Latin-1
    adm["geometry"] = adm.geometry.make_valid()
    t2m = load_era5()
    print(f"ERA5-Land: {t2m.sizes['time']} months, {pd.Timestamp(t2m.time.values[0]):%Y-%m} to "
          f"{pd.Timestamp(t2m.time.values[-1]):%Y-%m}; Admin 3 units: {len(adm)}")

    w = weights(t2m, adm)
    w.to_csv(C.RAW / "boundaries" / "ocha" / "era5_admin3_weights.csv", index=False)
    ncell = w.groupby("adm3_pcode").size()
    print(f"  cells per unit: median {ncell.median():.0f}, min {ncell.min()}, max {ncell.max()}")

    # weighted means: (time x cells) -> (time x units)
    vals = t2m.values[:, w.yi.values, w.xi.values]
    units = pd.Index(sorted(w.adm3_pcode.unique()))
    col = units.get_indexer(w.adm3_pcode)
    W = np.zeros((len(w), len(units)))
    W[np.arange(len(w)), col] = w.w.values
    m = pd.DataFrame(vals @ W, index=pd.DatetimeIndex(t2m.time.values), columns=units)

    # monthly panel with anomaly vs 1991-2020 calendar-month climatology
    long = m.stack().rename("t2m_c").reset_index()
    long.columns = ["date", "adm3_pcode", "t2m_c"]
    long["year"], long["month"] = long.date.dt.year, long.date.dt.month
    base = long[long.year.between(*C.BASELINE)]
    clim = base.groupby(["adm3_pcode", "month"]).t2m_c.agg(["mean", "std"])
    long = long.join(clim, on=["adm3_pcode", "month"])
    long["t2m_anom_c"] = long.t2m_c - long["mean"]
    long["t2m_anom_sd"] = long.t2m_anom_c / long["std"]
    long = long.drop(columns=["mean", "std", "date"])
    meta = adm[ID].set_index("adm3_pcode")
    monthly = meta.join(long.set_index("adm3_pcode"), how="right").reset_index()
    monthly = monthly[ID + ["year", "month", "t2m_c", "t2m_anom_c", "t2m_anom_sd"]].round(3)
    save(monthly, "era5land_admin3_monthly")

    # annual panel
    g = long.groupby(["adm3_pcode", "year"])
    yr = pd.DataFrame({"t2m_mean_c": g.t2m_c.mean(), "t2m_max_month_c": g.t2m_c.max(),
                       "t2m_min_month_c": g.t2m_c.min(), "t2m_anom_c": g.t2m_anom_c.mean(),
                       "n_months": g.t2m_c.count()}).reset_index()
    sd = yr[yr.year.between(*C.BASELINE)].groupby("adm3_pcode").t2m_mean_c.std().rename("sd")
    yr = yr.join(sd, on="adm3_pcode")
    yr["t2m_anom_sd"] = yr.t2m_anom_c / yr.pop("sd")
    yr = meta.join(yr.set_index("adm3_pcode"), how="right").reset_index()
    yr = yr[ID + ["year", "t2m_mean_c", "t2m_max_month_c", "t2m_min_month_c",
                  "t2m_anom_c", "t2m_anom_sd", "n_months"]].round(3)
    save(yr, "era5land_admin3_year")


if __name__ == "__main__":
    main()
