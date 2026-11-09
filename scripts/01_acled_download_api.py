"""Download all ACLED events for DR Congo through the ACLED API (OAuth, 2025+).

Credentials: set the environment variables ACLED_EMAIL and ACLED_PASSWORD (your
myACLED login), or the script will prompt for them.

Output: data/raw/acled/acled_drc_<start>_<end>.csv
"""
import getpass
import os
import sys
import time

import pandas as pd
import requests

import config as C

TOKEN_URL = "https://acleddata.com/oauth/token"
DATA_URL = "https://acleddata.com/api/acled/read"
PAGE_SIZE = 5000


def get_token() -> str:
    email = os.environ.get("ACLED_EMAIL") or input("myACLED email: ")
    pwd = os.environ.get("ACLED_PASSWORD") or getpass.getpass("myACLED password: ")
    r = requests.post(TOKEN_URL, data={
        "username": email, "password": pwd, "grant_type": "password",
        "client_id": "acled", "scope": "authenticated"}, timeout=60)
    if r.status_code != 200:
        sys.exit(f"Authentication failed ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def main():
    headers = {"Authorization": f"Bearer {get_token()}"}
    rows, page = [], 1
    while True:
        params = {"_format": "json", "iso": C.ACLED_ISO,
                  "event_date": f"{C.ACLED_START}|{C.ACLED_END}",
                  "event_date_where": "BETWEEN",
                  "limit": PAGE_SIZE, "page": page}
        for attempt in range(5):
            r = requests.get(DATA_URL, params=params, headers=headers, timeout=300)
            if r.status_code == 200:
                break
            print(f"  page {page}: HTTP {r.status_code}, retrying...")
            time.sleep(5 * (attempt + 1))
        r.raise_for_status()
        payload = r.json()
        if payload.get("status") not in (200, None) and not payload.get("success", True):
            sys.exit(f"API error: {payload}")
        data = payload.get("data", [])
        rows.extend(data)
        print(f"page {page}: {len(data)} events (total {len(rows)})")
        if len(data) < PAGE_SIZE:
            break
        page += 1

    if not rows:
        sys.exit("No events returned. Check that your account has API access.")
    df = pd.DataFrame(rows).drop_duplicates("event_id_cnty")
    for col in ("latitude", "longitude", "fatalities", "geo_precision", "year"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["event_date"] = pd.to_datetime(df["event_date"])
    out = C.ACLED_DIR / f"acled_drc_{C.ACLED_START[:4]}_{C.ACLED_END[:4]}.csv"
    df.sort_values("event_date").to_csv(out, index=False)
    print(f"\nSaved {len(df):,} events ({df.event_date.min():%Y-%m-%d} to "
          f"{df.event_date.max():%Y-%m-%d}) -> {out}")
    print(df.event_type.value_counts().to_string())


if __name__ == "__main__":
    main()
