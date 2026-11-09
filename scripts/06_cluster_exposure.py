"""Build cluster-level conflict (ACLED) and temperature (ERA5-Land) exposure.

Cluster input (put ONE of these in data/clusters/):
  * a DHS GPS shapefile (e.g. CDGE81FL.shp): uses DHSCLUST, LATNUM, LONGNUM
  * a CSV with columns: cluster_id, lat, lon  [+ optional interview_date (YYYY-MM-DD)]
    An interview_date column also adds a "12 months before interview" file.

Outputs (output/, each as .csv and .dta):
  cluster_year_exposure       one row per cluster x year
  cluster_interview_exposure  one row per cluster (only if interview_date is given)

Usage:  python scripts/06_cluster_exposure.py [path_to_cluster_file]
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr
from sklearn.neighbors import BallTree

import config as C

R_EARTH = 6371.0088


# ------------------------------------------------------------------ inputs
def load_clusters(path: Path | None) -> pd.DataFrame:
    if path is None:
        cands = sorted(C.CLUSTER_DIR.glob("*.shp")) + sorted(C.CLUSTER_DIR.glob("*.csv"))
        if not cands:
            sys.exit(f"No cluster file found in {C.CLUSTER_DIR}")
        path = cands[0]
    print(f"clusters: {path.name}")
    if path.suffix.lower() == ".shp":
        import geopandas as gpd
        g = gpd.read_file(path)
        df = pd.DataFrame({"cluster_id": g["DHSCLUST"].astype(int),
                           "lat": g["LATNUM"], "lon": g["LONGNUM"]})
        if "URBAN_RURA" in g:
            df["urban_rural"] = g["URBAN_RURA"].values
    else:
        df = pd.read_csv(path)
        df.columns = [c.lower() for c in df.columns]
        if "interview_date" in df:
            df["interview_date"] = pd.to_datetime(df["interview_date"])
    # DHS codes missing GPS as (0, 0)
    bad = (df.lat.abs() < 1e-6) & (df.lon.abs() < 1e-6) | df.lat.isna() | df.lon.isna()
    if bad.any():
        print(f"  dropping {bad.sum()} clusters with missing coordinates")
    return df.loc[~bad].reset_index(drop=True)


def load_acled() -> pd.DataFrame:
    files = sorted(C.ACLED_DIR.glob("acled_drc_*.csv"))
    if not files:
        sys.exit("No ACLED file found. Run 01_acled_download_api.py or 02_acled_clean.py first.")
    ev = pd.read_csv(files[-1], parse_dates=["event_date"], low_memory=False)
    n0 = len(ev)
    ev = ev[ev.geo_precision <= C.MAX_GEO_PRECISION].reset_index(drop=True)
    print(f"ACLED: {n0:,} events, {len(ev):,} kept with geo_precision <= {C.MAX_GEO_PRECISION}")
    return ev


def load_era5() -> xr.DataArray:
    files = sorted(C.ERA5_DIR.glob("era5land_t2m_monthly_*.nc"))
    if not files:
        sys.exit("No ERA5-Land files found. Run 03_era5land_download.py first.")
    parts = []
    for f in files:
        ds = xr.open_dataset(f)
        if "valid_time" in ds.dims:
            ds = ds.rename({"valid_time": "time"})
        da = ds["t2m"]
        da = da.drop_vars([v for v in ("number", "expver") if v in da.coords])
        parts.append(da.load())
    da = xr.concat(parts, "time").sortby("time")
    da = da.isel(time=~pd.Index(da.time.values).duplicated())
    return da - 273.15  # Kelvin -> Celsius


# -------------------------------------------------------- ACLED exposure
def event_pairs(cl: pd.DataFrame, ev: pd.DataFrame) -> pd.DataFrame:
    """Every (cluster, event) pair within the largest buffer, with distance in km."""
    tree = BallTree(np.radians(ev[["latitude", "longitude"]].values), metric="haversine")
    idx, dist = tree.query_radius(np.radians(cl[["lat", "lon"]].values),
                                  r=max(C.BUFFERS_KM) / R_EARTH, return_distance=True)
    lens = [len(i) for i in idx]
    pairs = pd.DataFrame({"cl": np.repeat(np.arange(len(cl)), lens),
                          "ev": np.concatenate(idx).astype(int),
                          "dist_km": np.concatenate(dist) * R_EARTH})
    cols = ["event_date", "year", "event_type", "fatalities"]
    return pairs.join(ev[cols], on="ev")


def summarise(p: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    """Event counts by type and fatalities per buffer, grouped by `keys`."""
    out = []
    p = p.assign(violent=p.event_type.isin(C.VIOLENT_TYPES))
    for r in C.BUFFERS_KM:
        q = p[p.dist_km <= r]
        g = q.groupby(keys)
        s = pd.DataFrame({
            f"acled_events_{r}km": g.size(),
            f"acled_violent_{r}km": g.violent.sum(),
            f"acled_battles_{r}km": g.event_type.apply(lambda x: (x == "Battles").sum()),
            f"acled_vac_{r}km": g.event_type.apply(lambda x: (x == "Violence against civilians").sum()),
            f"acled_explosions_{r}km": g.event_type.apply(lambda x: (x == "Explosions/Remote violence").sum()),
            f"acled_riots_{r}km": g.event_type.apply(lambda x: (x == "Riots").sum()),
            f"acled_protests_{r}km": g.event_type.apply(lambda x: (x == "Protests").sum()),
            f"acled_fatalities_{r}km": g.fatalities.sum(),
        })
        out.append(s)
    return pd.concat(out, axis=1)


# ---------------------------------------------------- ERA5 extraction
def cluster_series(cl: pd.DataFrame, t2m: xr.DataArray) -> pd.DataFrame:
    """Monthly temperature of the nearest land grid cell for each cluster.

    ERA5-Land is land-only, so cells over lakes (Tanganyika, Kivu, Albert...) and the
    Atlantic are NaN. Each cluster gets the nearest cell that has data."""
    lat2, lon2 = np.meshgrid(t2m.latitude.values, t2m.longitude.values, indexing="ij")
    valid = np.isfinite(t2m.isel(time=0).values)
    pts = np.column_stack([lat2[valid], lon2[valid]])
    tree = BallTree(np.radians(pts), metric="haversine")
    d, i = tree.query(np.radians(cl[["lat", "lon"]].values), k=1)
    yi, xi = np.nonzero(valid)
    yi, xi = yi[i[:, 0]], xi[i[:, 0]]
    vals = t2m.values[:, yi, xi]                       # time x cluster
    m = pd.DataFrame(vals, index=pd.DatetimeIndex(t2m.time.values), columns=cl.index)
    m.index = m.index.to_period("M")
    cl["era5_cell_dist_km"] = d[:, 0] * R_EARTH
    return m


def temp_by_year(cl, m: pd.DataFrame) -> pd.DataFrame:
    long = m.stack().rename("t").reset_index()
    long.columns = ["month", "cl", "t"]
    long["year"] = long.month.dt.year
    long["mon"] = long.month.dt.month
    base = long[long.year.between(*C.BASELINE)]
    clim = base.groupby(["cl", "mon"]).t.mean().rename("clim")
    long = long.join(clim, on=["cl", "mon"])
    long["anom"] = long.t - long.clim
    base_annual = base.groupby(["cl", "year"]).t.mean().groupby("cl").std().rename("sd")
    g = long.groupby(["cl", "year"])
    ty = pd.DataFrame({"t2m_mean_c": g.t.mean(), "t2m_max_month_c": g.t.max(),
                       "t2m_anom_c": g.anom.mean(), "n_months": g.t.count()})
    ty = ty.join(base_annual, on="cl")
    ty["t2m_anom_sd"] = ty.t2m_anom_c / ty.pop("sd")
    return ty[ty.n_months == 12].drop(columns="n_months")


# ------------------------------------------------- WorldPop exposure
WP_LAYERS = {  # output name -> WorldPop layers summed
    "pop": ["pop"],
    "u5": ["m_00", "m_01", "f_00", "f_01"],
    "0_14": [f"{s}_{a}" for s in "mf" for a in ("00", "01", "05", "10")],
    "women15_49": [f"f_{a}" for a in ("15", "20", "25", "30", "35", "40", "45")],
}


def worldpop_buffers(cl: pd.DataFrame) -> pd.DataFrame | None:
    """Population within 10/25/50 km of each cluster, per year (WorldPop Global2, 1 km).

    Sums the 1 km pixels whose centre lies within r km (haversine) of the cluster."""
    import rasterio
    wp = C.RAW / "worldpop"
    years = sorted(int(p.name) for p in wp.iterdir() if p.is_dir()) if wp.exists() else []
    if not years:
        print("WorldPop not found - skipping population exposure")
        return None
    with rasterio.open(next((wp / str(years[0])).glob("cod_pop_*.tif"))) as src:
        T, (H, W) = src.transform, src.shape
    rmax = max(C.BUFFERS_KM)
    nbh = []  # per cluster: flat pixel indices and distances within rmax
    for la, lo in cl[["lat", "lon"]].values:
        r0, c0 = rasterio.transform.rowcol(T, lo, la)
        dr = int(np.ceil(rmax / 111.0 / abs(T.e))) + 1
        dc = int(np.ceil(rmax / (111.0 * np.cos(np.radians(la))) / T.a)) + 1
        rr, cc = np.mgrid[max(r0 - dr, 0):min(r0 + dr + 1, H), max(c0 - dc, 0):min(c0 + dc + 1, W)]
        plon, plat = T.c + (cc + .5) * T.a, T.f + (rr + .5) * T.e
        p1, p2 = np.radians(la), np.radians(plat)
        h = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(np.radians(plon - lo) / 2) ** 2
        d = 2 * R_EARTH * np.arcsin(np.sqrt(h))
        k = d <= rmax
        nbh.append(((rr[k] * W + cc[k]), d[k]))

    out = []
    for y in years:
        rec = {}
        for name, layers in WP_LAYERS.items():
            tot = np.zeros(H * W)
            for lay in layers:
                f = next((wp / str(y)).glob(f"cod_{lay}_{y}_*.tif"), None)
                if f is None:
                    tot = None
                    break
                with rasterio.open(f) as src:
                    a = src.read(1, masked=True).filled(0).astype("float64").ravel()
                tot += np.clip(a, 0, None)
            if tot is None:
                continue
            for r in C.BUFFERS_KM:
                rec[f"wp_{name}_{r}km"] = [tot[i[d <= r]].sum() for i, d in nbh]
        df = pd.DataFrame(rec, index=cl.index)
        df["year"] = y
        out.append(df)
    print(f"WorldPop: population within buffers for {years[0]}-{years[-1]}")
    return pd.concat(out).rename_axis("cl").reset_index().set_index(["cl", "year"]).round(0)


def add_rates(df: pd.DataFrame, suffix: str = "") -> pd.DataFrame:
    """Violent events and fatalities per 100,000 people within each buffer."""
    for r in C.BUFFERS_KM:
        pop = df.get(f"wp_pop_{r}km")
        if pop is not None:
            pop = pop.where(pop > 0)
            df[f"acled_violent_per100k_{r}km{suffix}"] = (1e5 * df[f"acled_violent_{r}km{suffix}"] / pop).round(3)
            df[f"acled_fatal_per100k_{r}km{suffix}"] = (1e5 * df[f"acled_fatalities_{r}km{suffix}"] / pop).round(3)
    return df


# ------------------------------------------------------------------ main
def save(df, name):
    df.to_csv(C.OUT / f"{name}.csv", index=False)
    df.to_stata(C.OUT / f"{name}.dta", write_index=False, version=118)
    print(f"saved output/{name}.csv/.dta  ({len(df):,} rows, {df.shape[1]} cols)")


def main():
    cl = load_clusters(Path(sys.argv[1]) if len(sys.argv) > 1 else None)
    ev = load_acled()
    pairs = event_pairs(cl, ev)
    has_era5 = any(C.ERA5_DIR.glob("era5land_t2m_monthly_*.nc"))
    m = cluster_series(cl, load_era5()) if has_era5 else None
    if not has_era5:
        print("ERA5-Land not found - temperature columns skipped")
    wp = worldpop_buffers(cl)

    # ---- cluster x year panel (ACLED 1997-2025; WorldPop from 2015; ERA5 from 1991)
    years = range(1997, int(ev.year.max()) + 1)
    acled_y = summarise(pairs, ["cl", "year"])
    grid = pd.MultiIndex.from_product([cl.index, years], names=["cl", "year"])
    panel = acled_y.reindex(grid).fillna(0).astype(int)
    if wp is not None:
        panel = add_rates(panel.join(wp))
    if m is not None:
        panel = panel.join(temp_by_year(cl, m))
    panel = panel.reset_index()
    panel = cl.drop(columns=[c for c in ["interview_date"] if c in cl]) \
              .join(panel.set_index("cl"), how="right").reset_index(drop=True)
    save(panel, "cluster_year_exposure")

    # ---- 12 months before interview
    if "interview_date" in cl:
        idate = cl.interview_date.values[pairs.cl.values]
        win = pairs[(pairs.event_date < idate) &
                    (pairs.event_date >= idate - np.timedelta64(365, "D"))]
        a12 = summarise(win.assign(k=0), ["cl", "k"]).droplevel("k")
        a12 = a12.reindex(cl.index).fillna(0).astype(int).add_suffix("_12m")
        out = cl.join(a12)
        if wp is not None:  # population in the interview year (clipped to WorldPop years)
            wy = wp.index.get_level_values("year")
            yr = cl.interview_date.dt.year.clip(wy.min(), wy.max())
            pop = wp.loc[list(zip(cl.index, yr))].set_index(cl.index).add_suffix("_12m")
            out = out.join(pop)
            for r in C.BUFFERS_KM:
                p = out[f"wp_pop_{r}km_12m"].where(out[f"wp_pop_{r}km_12m"] > 0)
                out[f"acled_violent_per100k_{r}km_12m"] = (1e5 * out[f"acled_violent_{r}km_12m"] / p).round(3)
                out[f"acled_fatal_per100k_{r}km_12m"] = (1e5 * out[f"acled_fatalities_{r}km_12m"] / p).round(3)
            out["wp_year"] = yr
        if m is not None:
            clim = m[(m.index.year >= C.BASELINE[0]) & (m.index.year <= C.BASELINE[1])]
            clim = clim.groupby(clim.index.month).mean()
            rows = []
            for k, d in cl.interview_date.items():
                p = pd.Period(d, "M")
                months = pd.period_range(p - 12, p - 1, freq="M")
                s = m.loc[m.index.isin(months), k]
                rows.append({"t2m_mean_12m_c": s.mean(),
                             "t2m_anom_12m_c": (s - clim.loc[s.index.month, k].values).mean(),
                             "t2m_int_month_c": m.loc[p, k] if p in m.index else np.nan})
            out = out.join(pd.DataFrame(rows, index=cl.index))
        save(out, "cluster_interview_exposure")


if __name__ == "__main__":
    main()
