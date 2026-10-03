"""Resolve each sample address to its legal jurisdiction with the Census Geocoder.

Postal city is not the legal city ("Van Nuys" is inside Los Angeles, "Dorchester"
is inside Boston), so we geocode every address to coordinates and then ask the
Census which incorporated place and county contain that point.

Output: work/geocoded.json, keyed by address_id.
"""

import csv
import io
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import requests

from navigator.paths import ADDRESSES, GEOCODED

BATCH_URL = "https://geocoding.geo.census.gov/geocoder/locations/addressbatch"
COORD_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
ONELINE_URL = "https://geocoding.geo.census.gov/geocoder/locations/address"
BENCHMARK = "Public_AR_Current"
VINTAGE = "Current_Current"

# ZIP prefixes that belong to each state. The NJ rows carry some New York owner
# mailing ZIPs, which send the geocoder to Brooklyn, so we drop ZIPs that don't fit.
STATE_ZIP_PREFIX = {"CA": ("9",), "NJ": ("07", "08"), "MA": ("01", "02")}


def clean_street(street):
    """'1031-1035 CLINTON ST' -> '1031 CLINTON ST'; '322-322.5 Western Ave' -> '322 Western Ave'."""
    return re.sub(r"^(\d+)[A-Z]?\s*-\s*[\d.]+[A-Z]?\b", r"\1", street.strip())


def usable_zip(row):
    z = row["zip"].strip()
    return z if z and z.startswith(STATE_ZIP_PREFIX[row["state"]]) else ""


def batch_locate(rows):
    """Census batch geocode: returns {address_id: (lon, lat, matched_address)}."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    for r in rows:
        writer.writerow([r["address_id"], clean_street(r["street_address"]), r["postal_city"], r["state"], usable_zip(r)])
    resp = requests.post(
        BATCH_URL,
        files={"addressFile": ("addresses.csv", buf.getvalue(), "text/csv")},
        data={"benchmark": BENCHMARK},
        timeout=600,
    )
    resp.raise_for_status()
    found = {}
    for rec in csv.reader(io.StringIO(resp.text)):
        if len(rec) >= 6 and rec[2] == "Match":
            lon, lat = rec[5].split(",")
            found[rec[0]] = (float(lon), float(lat), rec[4])
    return found


def oneline_locate(row):
    """Retry a single address without the ZIP (bad ZIPs are the usual cause of a miss)."""
    params = {
        "street": clean_street(row["street_address"]),
        "city": row["postal_city"],
        "state": row["state"],
        "benchmark": BENCHMARK,
        "format": "json",
    }
    data = get_json(ONELINE_URL, params)
    matches = data["result"]["addressMatches"]
    if not matches:
        return None
    m = matches[0]
    return (m["coordinates"]["x"], m["coordinates"]["y"], m["matchedAddress"])


def get_json(url, params, tries=4):
    for attempt in range(tries):
        try:
            resp = requests.get(url, params=params, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError):
            if attempt == tries - 1:
                raise
            time.sleep(2 * (attempt + 1))


def jurisdiction_at(lon, lat):
    """Incorporated place and county containing a point."""
    data = get_json(
        COORD_URL,
        {
            "x": lon,
            "y": lat,
            "benchmark": BENCHMARK,
            "vintage": VINTAGE,
            "layers": "Incorporated Places,Counties,States",
            "format": "json",
        },
    )
    geos = data["result"]["geographies"]
    places = geos.get("Incorporated Places", [])
    counties = geos.get("Counties", [])
    states = geos.get("States", [])
    return {
        "place": places[0]["BASENAME"] if places else None,
        "place_name": places[0]["NAME"] if places else None,
        "place_geoid": places[0]["GEOID"] if places else None,
        "county": counties[0]["NAME"] if counties else None,
        "state_abbr": states[0]["STUSAB"] if states else None,
    }


def main():
    with open(ADDRESSES) as f:
        rows = list(csv.DictReader(f))
    by_id = {r["address_id"]: r for r in rows}

    print(f"batch geocoding {len(rows)} addresses", file=sys.stderr)
    located = batch_locate(rows)
    missing = [r for r in rows if r["address_id"] not in located]
    print(f"batch matched {len(located)}; retrying {len(missing)} one by one", file=sys.stderr)
    with ThreadPoolExecutor(max_workers=6) as pool:
        for row, hit in zip(missing, pool.map(oneline_locate, missing), strict=True):
            if hit:
                located[row["address_id"]] = hit

    ids = sorted(located)
    with ThreadPoolExecutor(max_workers=8) as pool:
        juris = dict(zip(ids, pool.map(lambda i: jurisdiction_at(*located[i][:2]), ids), strict=True))

    out = {}
    for aid, row in by_id.items():
        if aid in located:
            lon, lat, matched = located[aid]
            out[aid] = {"lon": lon, "lat": lat, "matched_address": matched, "method": "census", **juris[aid]}
        else:
            out[aid] = {"lon": None, "lat": None, "matched_address": None, "method": "unmatched",
                        "place": None, "place_name": None, "place_geoid": None, "county": None,
                        "state_abbr": row["state"]}
    GEOCODED.write_text(json.dumps(out, indent=1, sort_keys=True))
    print(f"wrote {GEOCODED}: {len(located)}/{len(rows)} located", file=sys.stderr)


if __name__ == "__main__":
    main()
