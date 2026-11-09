"""Conflict and population exposure around ACLED event locations (no survey clusters).

The "clusters" are the distinct ACLED event locations (unique coordinates with
geo_precision <= 2). Around each one, the script measures:
  * ACLED events, by type, and fatalities within 10 / 25 / 50 km
  * WorldPop Global2 population within 10 / 25 / 50 km (total, under-5, 0-14, women 15-49)
  * violent events and fatalities per 100,000 people

WorldPop starts in 2015. For 1997-2014 the 2015 population is used and flagged
(wp_year = 2015, wp_imputed = 1); WorldPop values are never extrapolated backwards.

Outputs (output/, .csv and .dta):
  acled_locations                  one row per location: id, coordinates, names, event totals
  acled_location_year_exposure     location x year, 1997-2025
  acled_event_exposure             one row per ACLED event, with the population around it
                                   in the event year (people exposed to the event)
"""
import importlib

import numpy as np
import pandas as pd

import config as C

X = importlib.import_module("06_cluster_exposure")
KEEP = ["event_id_cnty", "event_date", "year", "disorder_type", "event_type", "sub_event_type",
        "actor1", "actor2", "interaction", "civilian_targeting", "fatalities",
        "admin1", "admin2", "admin3", "location", "latitude", "longitude",
        "geo_precision", "time_precision", "dup_flag", "geo_fix"]


def main():
    raw = pd.read_csv(C.ACLED_DIR / "acled_drc_1997_2025.csv", parse_dates=["event_date"], low_memory=False)
    ev = X.load_acled()  # precision <= 2, duplicates removed: used for the counts

    # ---- locations = unique coordinates of precise events
    g = ev.groupby(["latitude", "longitude"])
    loc = pd.DataFrame({
        "location": g.location.agg(lambda s: s.mode().iat[0]),
        "admin1": g.admin1.agg(lambda s: s.mode().iat[0]),
        "admin2": g.admin2.agg(lambda s: s.mode().iat[0] if s.notna().any() else np.nan),
        "admin3": g.admin3.agg(lambda s: s.mode().iat[0] if s.notna().any() else np.nan),
        "n_events_1997_2025": g.size(),
        "first_year": g.year.min(), "last_year": g.year.max(),
    }).reset_index().rename(columns={"latitude": "lat", "longitude": "lon"})
    loc.insert(0, "loc_id", np.arange(1, len(loc) + 1))
    print(f"{len(loc):,} distinct event locations")
    X.save(loc, "acled_locations")

    cl = loc[["loc_id", "lat", "lon"]].copy()

    # ---- ACLED counts around each location, per year
    pairs = X.event_pairs(cl, ev)
    years = range(1997, int(ev.year.max()) + 1)
    grid = pd.MultiIndex.from_product([cl.index, years], names=["cl", "year"])
    panel = X.summarise(pairs, ["cl", "year"]).reindex(grid).fillna(0).astype(int)

    # ---- WorldPop around each location (2015-2025; 2015 used for earlier years)
    wp = X.worldpop_buffers(cl)
    wy = wp.index.get_level_values("year")
    panel = panel.reset_index()
    panel["wp_year"] = panel.year.clip(wy.min(), wy.max())
    panel["wp_imputed"] = (panel.year < wy.min()).astype(int)
    panel = panel.join(wp, on=["cl", "wp_year"])
    panel = X.add_rates(panel)
    panel = loc[["loc_id", "lat", "lon", "location", "admin1", "admin2", "admin3"]] \
        .join(panel.set_index("cl"), how="right").reset_index(drop=True)
    X.save(panel, "acled_location_year_exposure")

    # ---- event level: population around every event, in the event year
    e = raw[KEEP].merge(loc[["loc_id", "lat", "lon"]], how="left",
                        left_on=["latitude", "longitude"], right_on=["lat", "lon"]).drop(columns=["lat", "lon"])
    e["wp_year"] = e.year.clip(wy.min(), wy.max())
    e["wp_imputed"] = (e.year < wy.min()).astype(int)
    wpl = wp.reset_index()
    wpl["loc_id"] = cl.loc_id.values[wpl.cl.values]
    e = e.merge(wpl.drop(columns="cl").rename(columns={"year": "wp_year"}), on=["loc_id", "wp_year"], how="left")
    imprecise = e.geo_precision > C.MAX_GEO_PRECISION   # province centroid: population meaningless
    e.loc[imprecise, [c for c in e if c.startswith("wp_") and c not in ("wp_year", "wp_imputed")]] = np.nan
    e["event_date"] = e.event_date.dt.strftime("%Y-%m-%d")
    X.save(e, "acled_event_exposure")
    print(f"events with population: {e.wp_pop_10km.notna().sum():,} / {len(e):,} "
          f"(precision-3 events left blank: {imprecise.sum()})")


if __name__ == "__main__":
    main()
