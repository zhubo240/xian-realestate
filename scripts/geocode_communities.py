#!/usr/bin/env python3
"""
Batch geocode 523 communities from gaoxin_esf_all.csv using Gaode (Amap) APIs.
- POI Search API v5 (primary)
- Geocoding API v3 (fallback)
- Converts GCJ-02 to WGS-84
- Classifies communities into 片区
"""

import csv
import json
import time
import urllib.request
import urllib.parse
import sys
import io

# ── Config ──────────────────────────────────────────────────────────────
API_KEY = "d7901bb0f8ce80c2326da1baaa5e810c"
INPUT_FILE = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_esf_all.csv"
DELAY = 0.3  # seconds between API calls

# ── GCJ-02 → WGS-84 (approximate for Xi'an area) ──────────────────────
def gcj02_to_wgs84(lng, lat):
    return lng - 0.0065, lat - 0.0060

# ── 片区分类 ────────────────────────────────────────────────────────────
def classify_zone(bankuai):
    if not bankuai:
        return "其他"
    # 高新一期
    if any(kw in bankuai for kw in ["高新路", "高新四路", "太白立交", "电子城", "公交五公司"]):
        return "高新一期"
    # 高新二期
    if any(kw in bankuai for kw in ["锦业路", "唐延路", "高新一中", "CID", "徐家庄"]):
        return "高新二期"
    # 高新三期
    if any(kw in bankuai for kw in ["西万路口", "大学城", "郭杜", "西沣路"]):
        return "高新三期"
    # 软件新城
    if "软件" in bankuai:
        return "软件新城"
    # 其他
    return "其他"

# ── POI Search (Gaode v5) ──────────────────────────────────────────────
def poi_search(name):
    """Search for a community by name using Gaode POI Search API v5."""
    params = urllib.parse.urlencode({
        "key": API_KEY,
        "keywords": name,
        "region": "西安",
        "types": "120000",
        "show_fields": "geo",
    }, quote_via=urllib.parse.quote)
    url = f"https://restapi.amap.com/v5/place/text?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("pois") and len(data["pois"]) > 0:
            poi = data["pois"][0]
            loc = poi.get("location")
            if loc:
                # v5 API: location can be object {"lng": "...", "lat": "..."} or string "lng,lat"
                if isinstance(loc, dict):
                    lng = float(loc["lng"])
                    lat = float(loc["lat"])
                elif isinstance(loc, str) and "," in loc:
                    parts = loc.split(",")
                    lng = float(parts[0])
                    lat = float(parts[1])
                else:
                    return None
                return (lng, lat)
    except Exception as e:
        print(f"  POI search error for '{name}': {e}", file=sys.stderr)
    return None

# ── Geocoding (Gaode v3) ──────────────────────────────────────────────
def geocode(name):
    """Geocode a community using Gaode Geocoding API v3 as fallback."""
    address = f"{name} 西安 高新区"
    params = urllib.parse.urlencode({
        "key": API_KEY,
        "address": address,
        "city": "西安",
    }, quote_via=urllib.parse.quote)
    url = f"https://restapi.amap.com/v3/geocode/geo?{params}"
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("geocodes") and len(data["geocodes"]) > 0:
            loc_str = data["geocodes"][0].get("location", "")
            if "," in loc_str:
                parts = loc_str.split(",")
                lng = float(parts[0])
                lat = float(parts[1])
                return (lng, lat)
    except Exception as e:
        print(f"  Geocode error for '{name}': {e}", file=sys.stderr)
    return None

# ── Main ───────────────────────────────────────────────────────────────
def main():
    print(f"Reading CSV: {INPUT_FILE}")

    # Read CSV (UTF-8 with BOM)
    rows = []
    with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        original_fields = reader.fieldnames[:]
        for row in reader:
            rows.append(row)

    total = len(rows)
    print(f"Total communities: {total}")
    print(f"Original columns: {original_fields}")
    print(f"Starting geocoding with {DELAY}s delay between calls...")
    print()

    # Stats
    stats = {"POI精确": 0, "地理编码": 0, "默认": 0}
    zone_stats = {}

    start_time = time.time()

    for i, row in enumerate(rows):
        name = row.get("小区名称", "").strip()
        bankuai = row.get("板块", "").strip()

        # Classify zone
        zone = classify_zone(bankuai)
        row["片区分类"] = zone
        zone_stats[zone] = zone_stats.get(zone, 0) + 1

        # Try POI search first
        result = poi_search(name)
        accuracy = ""

        if result:
            accuracy = "POI精确"
        else:
            # Wait before fallback call
            time.sleep(DELAY)
            result = geocode(name)
            if result:
                accuracy = "地理编码"
            else:
                accuracy = "默认"

        if result:
            gcj_lng, gcj_lat = result
            wgs_lng, wgs_lat = gcj02_to_wgs84(gcj_lng, gcj_lat)
            row["经度"] = f"{wgs_lng:.6f}"
            row["纬度"] = f"{wgs_lat:.6f}"
        else:
            row["经度"] = ""
            row["纬度"] = ""

        row["坐标精度"] = accuracy
        stats[accuracy] += 1

        # Progress
        idx = i + 1
        if idx % 50 == 0 or idx == total:
            elapsed = time.time() - start_time
            print(f"  Progress: {idx}/{total} ({idx*100//total}%) - "
                  f"Elapsed: {elapsed:.1f}s - "
                  f"POI: {stats['POI精确']}, Geocode: {stats['地理编码']}, Failed: {stats['默认']}")

        # Delay between API calls
        time.sleep(DELAY)

    elapsed_total = time.time() - start_time

    # Write updated CSV (UTF-8 with BOM)
    output_fields = original_fields + ["经度", "纬度", "坐标精度", "片区分类"]
    with open(INPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(rows)

    # Final statistics
    print()
    print("=" * 60)
    print(f"Geocoding complete! Total time: {elapsed_total:.1f}s")
    print(f"Output: {INPUT_FILE}")
    print(f"Total communities: {total}")
    print()
    print("── 坐标精度 breakdown ──")
    for acc in ["POI精确", "地理编码", "默认"]:
        count = stats[acc]
        pct = count * 100 / total if total > 0 else 0
        print(f"  {acc}: {count} ({pct:.1f}%)")

    geocoded = stats["POI精确"] + stats["地理编码"]
    print(f"  Total geocoded: {geocoded}/{total} ({geocoded*100/total:.1f}%)")
    print()
    print("── 片区分类 distribution ──")
    for zone in ["高新一期", "高新二期", "高新三期", "软件新城", "其他"]:
        count = zone_stats.get(zone, 0)
        pct = count * 100 / total if total > 0 else 0
        print(f"  {zone}: {count} ({pct:.1f}%)")
    print("=" * 60)

if __name__ == "__main__":
    main()
