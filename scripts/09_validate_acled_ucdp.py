"""External validation: ACLED vs UCDP GED (v26.1) for DR Congo.

UCDP GED only records lethal organised violence (state-based, non-state, one-sided)
in conflicts that reach 25 battle deaths per year. To compare like with like, ACLED is
restricted to Battles / Violence against civilians / Explosions with fatalities > 0.
Both sources keep only events precise enough for 10-50 km buffers
(ACLED geo_precision <= 2; UCDP where_prec <= 3, i.e. up to second-order admin unit).

Outputs in output/validation/:
  annual_comparison.csv      events and deaths per year, both sources
  type_comparison.csv        by violence type
  grid_comparison.csv        0.5 deg cell totals 1997-2025
  match_rates.csv            share of events with a counterpart within 25 km / +-7 days
"""
import numpy as np
import pandas as pd
from sklearn.neighbors import BallTree

import config as C

R = 6371.0088
OUT = C.OUT / "validation"
OUT.mkdir(parents=True, exist_ok=True)
Y0, Y1 = 1997, 2025

# ---------------------------------------------------------------- load
a = pd.read_csv(C.ACLED_DIR / "acled_drc_1997_2025.csv", parse_dates=["event_date"], low_memory=False)
a = a[(a.dup_flag == 0) & a.event_type.isin(C.VIOLENT_TYPES)]
a_all = a.copy()
a = a[(a.fatalities > 0) & (a.geo_precision <= 2)]
a = a.rename(columns={"event_date": "date", "fatalities": "deaths", "latitude": "lat", "longitude": "lon"})

u = pd.read_csv(next((C.RAW / "ucdp").glob("GEDEvent_v26*.csv")), low_memory=False,
                usecols=["country", "type_of_violence", "where_prec", "date_prec", "latitude",
                         "longitude", "date_start", "year", "best", "adm_1"])
u = u[u.country.str.startswith("DR Congo")]
u = u.assign(date=pd.to_datetime(u.date_start)).rename(
    columns={"best": "deaths", "latitude": "lat", "longitude": "lon"})
u_all = u.copy()
u = u[(u.where_prec <= 3) & u.year.between(Y0, Y1)]
print(f"UCDP DRC: {len(u_all):,} events {u_all.year.min()}-{u_all.year.max()}, "
      f"{len(u):,} with where_prec<=3 in {Y0}-{Y1}")
print(f"ACLED comparable (lethal, precise, violent): {len(a):,}")

# ------------------------------------------------------- 1. annual
ann = pd.DataFrame({
    "acled_events": a.groupby(a.date.dt.year).size(),
    "ucdp_events": u.groupby("year").size(),
    "acled_deaths": a.groupby(a.date.dt.year).deaths.sum(),
    "ucdp_deaths": u.groupby("year").deaths.sum(),
}).reindex(range(Y0, Y1 + 1)).fillna(0).astype(int)
ann["event_ratio_acled_ucdp"] = (ann.acled_events / ann.ucdp_events.replace(0, np.nan)).round(2)
ann["death_ratio_acled_ucdp"] = (ann.acled_deaths / ann.ucdp_deaths.replace(0, np.nan)).round(2)
ann.rename_axis("year").to_csv(OUT / "annual_comparison.csv")

# -------------------------------------------------------- 2. type
amap = {"Battles": "Battles / state & non-state", "Violence against civilians": "Against civilians / one-sided",
        "Explosions/Remote violence": "Battles / state & non-state"}
umap = {1: "Battles / state & non-state", 2: "Battles / state & non-state", 3: "Against civilians / one-sided"}
typ = pd.DataFrame({
    "acled_events": a.event_type.map(amap).value_counts(),
    "ucdp_events": u.type_of_violence.map(umap).value_counts(),
    "acled_deaths": a.groupby(a.event_type.map(amap)).deaths.sum(),
    "ucdp_deaths": u.groupby(u.type_of_violence.map(umap)).deaths.sum()})
typ.rename_axis("type").to_csv(OUT / "type_comparison.csv")

# -------------------------------------------------------- 3. grid
def cell(df):
    return (np.floor(df.lat / .5) * .5).round(1).astype(str) + "_" + (np.floor(df.lon / .5) * .5).round(1).astype(str)

g = pd.DataFrame({"acled_events": a.groupby(cell(a)).size(), "ucdp_events": u.groupby(cell(u)).size(),
                  "acled_deaths": a.groupby(cell(a)).deaths.sum(), "ucdp_deaths": u.groupby(cell(u)).deaths.sum()}
                 ).fillna(0)
g.rename_axis("cell_lat_lon").to_csv(OUT / "grid_comparison.csv")
cy = pd.DataFrame({"a": a.groupby([cell(a), a.date.dt.year]).size(),
                   "u": u.groupby([cell(u), u.year]).size()}).fillna(0)

# -------------------------------------------------------- 4. matching
def match_rate(src, ref, km=25, days=7):
    tree = BallTree(np.radians(ref[["lat", "lon"]].values), metric="haversine")
    idx = tree.query_radius(np.radians(src[["lat", "lon"]].values), r=km / R)
    rd = ref.date.values
    sd = src.date.values
    hit = np.array([len(i) > 0 and (np.abs(rd[i] - d) <= np.timedelta64(days, "D")).any()
                    for i, d in zip(idx, sd)])
    return hit

rows = []
for lab, (y0, y1) in {"1997-2025": (Y0, Y1), "1997-2009": (1997, 2009),
                      "2010-2017": (2010, 2017), "2018-2025": (2018, 2025)}.items():
    aa, uu = a[a.date.dt.year.between(y0, y1)], u[u.year.between(y0, y1)]
    if len(uu) == 0:
        continue
    rows.append({"period": lab, "ucdp_events": len(uu), "acled_events": len(aa),
                 "share_ucdp_found_in_acled": match_rate(uu, aa).mean().round(3),
                 "share_acled_found_in_ucdp": match_rate(aa, uu).mean().round(3)})
mr = pd.DataFrame(rows)
mr.to_csv(OUT / "match_rates.csv", index=False)

# -------------------------------------------------------- report
pd.set_option("display.width", 200)
print("\n=== Annual (lethal violent events, precise locations) ===")
print(ann.to_string())
common = ann.loc[(ann.ucdp_events > 0)]
print(f"\ncorrelation of annual events: {common.acled_events.corr(common.ucdp_events):.2f}"
      f" | annual deaths: {common.acled_deaths.corr(common.ucdp_deaths):.2f}"
      f" (years {common.index.min()}-{common.index.max()})")
print(f"Spearman, annual events: {common.acled_events.corr(common.ucdp_events, method='spearman'):.2f}")
print("\n=== By type ===\n" + typ.to_string())
print(f"\n=== 0.5 deg grid ({len(g)} cells with any event) ===")
print(f"cell totals corr (log1p): {np.log1p(g.acled_events).corr(np.log1p(g.ucdp_events)):.2f}")
print(f"cell-year corr (log1p): {np.log1p(cy.a).corr(np.log1p(cy.u)):.2f}")
print(f"cells with UCDP events that also have ACLED events: {((g.ucdp_events>0)&(g.acled_events>0)).sum()}/{(g.ucdp_events>0).sum()}")
print(f"cells with ACLED events that also have UCDP events: {((g.ucdp_events>0)&(g.acled_events>0)).sum()}/{(g.acled_events>0).sum()}")
print("\n=== Event matching (25 km, +-7 days) ===\n" + mr.to_string(index=False))
