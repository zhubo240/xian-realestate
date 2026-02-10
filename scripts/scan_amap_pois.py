#!/usr/bin/env python3
"""
Scan all residential POIs in Gaoxin district using Gaode (Amap) v3 around search.
Divides the area into grid cells, queries the center of each cell with a radius.
Outputs: data/gaoxin_amap_pois.csv
"""

import csv
import json
import time
import urllib.request
import urllib.parse
import sys
import os
import math

API_KEY = "d7901bb0f8ce80c2326da1baaa5e810c"
OUTPUT_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "gaoxin_amap_pois.csv")

# Gaoxin district bounding box (GCJ-02 coordinates, slightly enlarged)
MIN_LNG = 108.820
MAX_LNG = 108.980
MIN_LAT = 34.130
MAX_LAT = 34.280

# Grid cell size in degrees (~1km)
CELL_SIZE = 0.01

# Search radius in meters (covers the diagonal of a 1km cell ~ 707m, round up)
SEARCH_RADIUS = 750

# POI type: 120000 = 商务住宅 (residential)
POI_TYPE = "120000"
PAGE_SIZE = 25  # max per page for v3 API
DELAY = 0.2  # seconds between API calls


def search_around(center_lng, center_lat, page=1):
    """Search POIs around a center point using v3 around API."""
    params = urllib.parse.urlencode({
        "key": API_KEY,
        "location": f"{center_lng:.4f},{center_lat:.4f}",
        "radius": SEARCH_RADIUS,
        "types": POI_TYPE,
        "offset": PAGE_SIZE,
        "page": page,
    }, quote_via=urllib.parse.quote)
    url = f"https://restapi.amap.com/v3/place/around?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data
    except Exception as e:
        print(f"  [ERROR] API call failed: {e}", file=sys.stderr)
        return None


def parse_pois(data):
    """Extract POI info from v3 API response."""
    pois = []
    if not data or data.get("status") != "1":
        return pois
    for poi in data.get("pois", []):
        loc = poi.get("location", "")
        if not loc or "," not in loc:
            continue
        parts = loc.split(",")
        lng, lat = float(parts[0]), float(parts[1])
        pois.append({
            "poi_id": poi.get("id", ""),
            "名称": poi.get("name", ""),
            "类型": poi.get("typecode", ""),
            "类型名": poi.get("type", ""),
            "地址": poi.get("address", "") if isinstance(poi.get("address"), str) else "",
            "经度_gcj02": f"{lng:.6f}",
            "纬度_gcj02": f"{lat:.6f}",
            "经度_wgs84": f"{lng - 0.0065:.6f}",
            "纬度_wgs84": f"{lat - 0.0060:.6f}",
        })
    return pois


def main():
    # Generate grid cell centers
    centers = []
    lng = MIN_LNG + CELL_SIZE / 2
    while lng < MAX_LNG:
        lat = MIN_LAT + CELL_SIZE / 2
        while lat < MAX_LAT:
            centers.append((lng, lat))
            lat += CELL_SIZE
        lng += CELL_SIZE

    total_cells = len(centers)
    print(f"Gaoxin POI scan (v3 around API)")
    print(f"Area: ({MIN_LNG},{MIN_LAT}) to ({MAX_LNG},{MAX_LAT})")
    print(f"Grid: {CELL_SIZE}° cells = {total_cells} centers, radius={SEARCH_RADIUS}m")
    print(f"Output: {OUTPUT_FILE}")
    print()

    all_pois = {}  # keyed by poi_id for dedup
    api_calls = 0
    start_time = time.time()

    for i, (clng, clat) in enumerate(centers):
        # First page
        data = search_around(clng, clat, page=1)
        api_calls += 1

        if data and data.get("status") == "1":
            pois = parse_pois(data)
            for p in pois:
                all_pois[p["poi_id"]] = p

            # Check if more pages needed
            total_count = int(data.get("count", "0"))
            if total_count > PAGE_SIZE:
                total_pages = (total_count + PAGE_SIZE - 1) // PAGE_SIZE
                for page in range(2, min(total_pages + 1, 20)):
                    time.sleep(DELAY)
                    data = search_around(clng, clat, page=page)
                    api_calls += 1
                    if data:
                        pois = parse_pois(data)
                        for p in pois:
                            all_pois[p["poi_id"]] = p

        # Progress every 50 cells
        idx = i + 1
        if idx % 50 == 0 or idx == total_cells:
            elapsed = time.time() - start_time
            print(f"  [{idx}/{total_cells}] {elapsed:.0f}s | "
                  f"API calls: {api_calls} | "
                  f"Unique POIs: {len(all_pois)}")

        time.sleep(DELAY)

    # Write CSV
    fieldnames = ["poi_id", "名称", "类型", "类型名", "地址", "经度_gcj02", "纬度_gcj02", "经度_wgs84", "纬度_wgs84"]
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for poi in sorted(all_pois.values(), key=lambda x: x["名称"]):
            writer.writerow(poi)

    elapsed_total = time.time() - start_time
    print()
    print("=" * 60)
    print(f"POI scan complete!")
    print(f"Total time: {elapsed_total:.0f}s")
    print(f"API calls: {api_calls}")
    print(f"Unique residential POIs found: {len(all_pois)}")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
