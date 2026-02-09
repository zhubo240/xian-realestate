#!/usr/bin/env python3
"""
Geocode new house listings from gaoxin_newhouse_all.csv using Gaode (Amap) APIs.
Reuses logic from geocode_communities.py.
"""

import csv
import json
import time
import urllib.request
import urllib.parse
import sys

API_KEY = "d7901bb0f8ce80c2326da1baaa5e810c"
INPUT_FILE = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_newhouse_all.csv"
OUTPUT_FILE = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_newhouse_all_geo.csv"
DELAY = 0.3


def gcj02_to_wgs84(lng, lat):
    return lng - 0.0065, lat - 0.0060


def classify_zone(addr):
    if not addr:
        return "其他"
    if any(kw in addr for kw in ["科技路", "科技一路", "科技二路", "科技三路", "高新路",
                                  "太白", "团结南路", "大寨路", "沣惠南路",
                                  "高新六路", "高新三路", "高新二路"]):
        return "高新一期"
    if any(kw in addr for kw in ["锦业", "唐延", "丈八", "科技四路", "科技五路",
                                  "科技六路", "科技七路", "科技八路", "化龙",
                                  "绍文路", "西沣", "鱼化", "雁环"]):
        return "高新二期"
    if any(kw in addr for kw in ["中央创新区", "CID", "未来之瞳", "兴隆", "纬二十",
                                  "纬三十", "经二十", "经三十", "丝路科学城",
                                  "西太路", "规划"]):
        return "高新三期"
    if any(kw in addr for kw in ["软件", "天谷", "云水"]):
        return "软件新城"
    if any(kw in addr for kw in ["国际社区", "灵秀", "灵韵", "北张"]):
        return "国际社区"
    return "其他"


def poi_search(name):
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
                if isinstance(loc, dict):
                    return float(loc["lng"]), float(loc["lat"])
                elif isinstance(loc, str) and "," in loc:
                    parts = loc.split(",")
                    return float(parts[0]), float(parts[1])
    except Exception as e:
        print(f"  POI error '{name}': {e}", file=sys.stderr)
    return None


def geocode(address):
    params = urllib.parse.urlencode({
        "key": API_KEY,
        "address": f"{address} 西安 高新区",
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
                return float(parts[0]), float(parts[1])
    except Exception as e:
        print(f"  Geocode error '{address}': {e}", file=sys.stderr)
    return None


def main():
    # Load existing ESF geo data for overlap
    esf_coords = {}
    try:
        with open("/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_esf_all_geo.csv",
                  "r", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                if row.get("经度") and row.get("纬度"):
                    esf_coords[row["小区名称"]] = (row["经度"], row["纬度"])
        print(f"Loaded {len(esf_coords)} ESF coordinates for reuse")
    except Exception:
        print("No ESF geo data found, geocoding all entries")

    # Read new house data
    rows = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    total = len(rows)
    print(f"Total new house entries: {total}")
    print(f"Starting geocoding...")

    stats = {"ESF复用": 0, "POI精确": 0, "地理编码": 0, "默认": 0}
    start_time = time.time()

    for i, row in enumerate(rows):
        name = row.get("楼盘名称", "").strip()
        addr = row.get("地址/位置", "").strip()

        # Classify zone based on address
        row["片区分类"] = classify_zone(addr)

        # Check ESF overlap first
        if name in esf_coords:
            row["经度"], row["纬度"] = esf_coords[name]
            row["坐标精度"] = "ESF复用"
            stats["ESF复用"] += 1
        else:
            # Try POI search by name
            result = poi_search(name)
            accuracy = ""

            if result:
                accuracy = "POI精确"
            else:
                time.sleep(DELAY)
                # Try geocoding by address
                result = geocode(addr if addr else name)
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

            time.sleep(DELAY)

        idx = i + 1
        if idx % 20 == 0 or idx == total:
            elapsed = time.time() - start_time
            print(f"  {idx}/{total} ({idx*100//total}%) - {elapsed:.1f}s - "
                  f"ESF: {stats['ESF复用']}, POI: {stats['POI精确']}, "
                  f"Geo: {stats['地理编码']}, Fail: {stats['默认']}")

    # Write output
    fieldnames = ["楼盘名称", "参考均价(元/㎡)", "地址/位置", "状态", "数据来源",
                  "页码", "经度", "纬度", "坐标精度", "片区分类"]
    with open(OUTPUT_FILE, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    elapsed_total = time.time() - start_time
    print()
    print("=" * 60)
    print(f"Geocoding complete! {elapsed_total:.1f}s")
    print(f"Output: {OUTPUT_FILE}")
    geocoded = stats["ESF复用"] + stats["POI精确"] + stats["地理编码"]
    print(f"Geocoded: {geocoded}/{total} ({geocoded*100/total:.1f}%)")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
