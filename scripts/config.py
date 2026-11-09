"""Shared settings for the DRC conflict & temperature exposure pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # repo root (scripts/ is one level down)
RAW = ROOT / "data" / "raw"
ACLED_DIR = RAW / "acled"
ERA5_DIR = RAW / "era5land"
CLUSTER_DIR = ROOT / "data" / "clusters"
OUT = ROOT / "output"
for d in (ACLED_DIR, ERA5_DIR, CLUSTER_DIR, OUT):
    d.mkdir(parents=True, exist_ok=True)

# --- Country -------------------------------------------------------------
ACLED_ISO = 180                      # ISO numeric code, DR Congo
# DRC bounding box (+ ~0.3 deg margin) as CDS expects: [North, West, South, East]
DRC_AREA = [5.7, 11.9, -13.8, 31.6]

# --- ACLED ---------------------------------------------------------------
ACLED_START = "1997-01-01"           # ACLED coverage of DRC starts in 1997
ACLED_END = "2025-12-31"

# --- ERA5-Land -----------------------------------------------------------
ERA5_YEARS = list(range(1991, 2026))     # 1991-2025
BASELINE = (1991, 2020)                  # WMO climate normal for anomalies

# --- Exposure ------------------------------------------------------------
BUFFERS_KM = [10, 25, 50]
# ACLED geo_precision: 1 = exact town, 2 = near town / district, 3 = province centroid.
# Precision-3 events are placed at a regional centroid, so they don't belong in
# 10-50 km buffers. The main measures keep 1-2.
MAX_GEO_PRECISION = 2
VIOLENT_TYPES = ["Battles", "Violence against civilians", "Explosions/Remote violence"]
