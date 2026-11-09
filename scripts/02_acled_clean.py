"""Clean a manual ACLED export (from acleddata.com Data Export Tool) for DR Congo.

Input : the newest data/raw/acled/ACLED Data_*.csv (may contain several countries)
Output: data/raw/acled/acled_drc_1997_2025.csv  (read by 06_cluster_exposure.py)

Fixes / flags (documented from the consistency check of the 2026-11-09 export):
  1. Keep country == DR Congo only.
  2. Rusankuku (Mwenga, Sud-Kivu) is geocoded at lat +3.815, which is in Haut-Uele,
     ~750 km north of Mwenga. The latitude sign is wrong; set to -3.815.
  3. Flag pairs with identical date, location, type, actors and notes
     (`dup_flag` = 1 on the second record). Most are 1997-2002 reports split into
     two events. They are flagged, not dropped.
"""
import pandas as pd

import config as C

src = sorted(C.ACLED_DIR.glob("ACLED Data_*.csv"))[-1]
d = pd.read_csv(src, low_memory=False)
d = d[d.country == "Democratic Republic of Congo"].copy()
d["event_date"] = pd.to_datetime(d.event_date)

fix = (d.location == "Rusankuku") & (d.admin1 == "Sud-Kivu") & (d.latitude > 0)
d.loc[fix, "latitude"] *= -1
d["geo_fix"] = fix.astype(int)

key = ["event_date", "latitude", "longitude", "event_type", "sub_event_type",
       "actor1", "actor2", "notes"]
d["dup_flag"] = d.duplicated(key, keep="first").astype(int)

out = C.ACLED_DIR / "acled_drc_1997_2025.csv"
d.sort_values("event_date").to_csv(out, index=False)
print(f"{src.name}: {len(d):,} DRC events, {d.event_date.min():%Y-%m-%d} to "
      f"{d.event_date.max():%Y-%m-%d}; latitude fixed: {fix.sum()}; "
      f"flagged duplicates: {d.dup_flag.sum()} -> {out.name}")
