#!/usr/bin/env python3
"""
Validate our dataset against Gaode (Amap) POI data.
Categorizes each record into:
1. Both have, location accurate (distance < 100m)
2. Both have, location inaccurate (distance >= 100m)
3. We have, Amap doesn't
4. Amap has, we don't

Outputs: data/validation_report.md + data/validation_detail.csv
"""

import csv
import math
import os
import re

BASE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
OUR_FILE = os.path.join(BASE_DIR, "gaoxin_merged_all.csv")
AMAP_FILE = os.path.join(BASE_DIR, "gaoxin_amap_pois.csv")
DETAIL_CSV = os.path.join(BASE_DIR, "validation_detail.csv")
REPORT_FILE = os.path.join(BASE_DIR, "validation_report.md")

# Distance threshold in meters
ACCURATE_THRESHOLD = 100
MATCH_THRESHOLD = 500  # max distance to consider a coordinate match


def haversine(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two WGS-84 points."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1-a))


def normalize_name(name):
    """Normalize community name for fuzzy matching."""
    # Remove common punctuation and whitespace
    name = re.sub(r'[·\-—\s·•．.()（）\[\]【】「」『』""\'\'\"\"]', '', name)
    # Remove common suffixes
    name = re.sub(r'(小区|花园|家园|社区|公寓|苑|居|庭|府|院|城|里|境|湾|阁|轩|第)$', '', name)
    return name.lower()


def load_our_data():
    """Load our merged dataset."""
    records = []
    with open(OUR_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lng = float(row["经度"]) if row.get("经度") else None
            lat = float(row["纬度"]) if row.get("纬度") else None
            records.append({
                "name": row.get("名称", "").strip(),
                "price": row.get("均价(元/㎡)", ""),
                "zone": row.get("片区", ""),
                "type": row.get("类型", ""),
                "lng": lng,
                "lat": lat,
                "normalized": normalize_name(row.get("名称", "")),
            })
    return records


def load_amap_data():
    """Load Amap POI dataset."""
    pois = []
    with open(AMAP_FILE, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            lng = float(row["经度_wgs84"]) if row.get("经度_wgs84") else None
            lat = float(row["纬度_wgs84"]) if row.get("纬度_wgs84") else None
            pois.append({
                "poi_id": row.get("poi_id", ""),
                "name": row.get("名称", "").strip(),
                "type_name": row.get("类型名", ""),
                "address": row.get("地址", ""),
                "lng": lng,
                "lat": lat,
                "normalized": normalize_name(row.get("名称", "")),
            })
    return pois


def find_best_match(record, amap_pois, amap_norm_index):
    """Find best matching Amap POI for one of our records."""
    norm = record["normalized"]
    best = None
    best_score = 0
    best_dist = None

    # Strategy 1: exact normalized name match
    candidates = amap_norm_index.get(norm, [])
    for poi in candidates:
        if record["lng"] and record["lat"] and poi["lng"] and poi["lat"]:
            dist = haversine(record["lat"], record["lng"], poi["lat"], poi["lng"])
        else:
            dist = None
        return poi, "exact_name", dist

    # Strategy 2: substring match (one contains the other)
    for poi in amap_pois:
        if len(norm) >= 2 and len(poi["normalized"]) >= 2:
            if norm in poi["normalized"] or poi["normalized"] in norm:
                if record["lng"] and record["lat"] and poi["lng"] and poi["lat"]:
                    dist = haversine(record["lat"], record["lng"], poi["lat"], poi["lng"])
                    if dist < MATCH_THRESHOLD:
                        return poi, "substring", dist
                else:
                    return poi, "substring_nocoord", None

    # Strategy 3: coordinate proximity (within 50m, different name)
    if record["lng"] and record["lat"]:
        closest_dist = float("inf")
        closest_poi = None
        for poi in amap_pois:
            if poi["lng"] and poi["lat"]:
                dist = haversine(record["lat"], record["lng"], poi["lat"], poi["lng"])
                if dist < 50 and dist < closest_dist:
                    closest_dist = dist
                    closest_poi = poi
        if closest_poi:
            return closest_poi, "coord_proximity", closest_dist

    return None, None, None


def main():
    print("Loading datasets...")
    our_data = load_our_data()
    amap_data = load_amap_data()
    print(f"Our data: {len(our_data)} records")
    print(f"Amap POIs: {len(amap_data)} records")

    # Build normalized name index for Amap
    amap_norm_index = {}
    for poi in amap_data:
        norm = poi["normalized"]
        if norm not in amap_norm_index:
            amap_norm_index[norm] = []
        amap_norm_index[norm].append(poi)

    # Match our records against Amap
    cat1_accurate = []      # both have, location accurate
    cat2_inaccurate = []    # both have, location inaccurate
    cat3_only_ours = []     # we have, Amap doesn't
    matched_amap_ids = set()

    detail_rows = []

    for rec in our_data:
        poi, match_type, dist = find_best_match(rec, amap_data, amap_norm_index)

        row = {
            "our_name": rec["name"],
            "our_lng": rec["lng"] or "",
            "our_lat": rec["lat"] or "",
            "our_zone": rec["zone"],
            "our_type": rec["type"],
            "our_price": rec["price"],
        }

        if poi:
            matched_amap_ids.add(poi["poi_id"])
            row["amap_name"] = poi["name"]
            row["amap_lng"] = poi["lng"] or ""
            row["amap_lat"] = poi["lat"] or ""
            row["amap_address"] = poi["address"]
            row["match_type"] = match_type
            row["distance_m"] = f"{dist:.0f}" if dist is not None else ""

            if dist is not None and dist < ACCURATE_THRESHOLD:
                row["category"] = "both_accurate"
                cat1_accurate.append(rec["name"])
            elif dist is not None:
                row["category"] = "both_inaccurate"
                cat2_inaccurate.append((rec["name"], dist))
            else:
                row["category"] = "both_nocoord"
                cat1_accurate.append(rec["name"])
        else:
            row["amap_name"] = ""
            row["amap_lng"] = ""
            row["amap_lat"] = ""
            row["amap_address"] = ""
            row["match_type"] = ""
            row["distance_m"] = ""
            row["category"] = "only_ours"
            cat3_only_ours.append(rec["name"])

        detail_rows.append(row)

    # Category 4: Amap has, we don't
    cat4_only_amap = []
    for poi in amap_data:
        if poi["poi_id"] not in matched_amap_ids:
            cat4_only_amap.append(poi)

    # Write detail CSV
    detail_fields = ["category", "our_name", "our_lng", "our_lat", "our_zone", "our_type",
                     "our_price", "amap_name", "amap_lng", "amap_lat", "amap_address",
                     "match_type", "distance_m"]
    with open(DETAIL_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=detail_fields)
        writer.writeheader()
        for row in sorted(detail_rows, key=lambda x: x["category"]):
            writer.writerow(row)
        # Add Amap-only records
        for poi in sorted(cat4_only_amap, key=lambda x: x["name"]):
            writer.writerow({
                "category": "only_amap",
                "our_name": "",
                "our_lng": "",
                "our_lat": "",
                "our_zone": "",
                "our_type": "",
                "our_price": "",
                "amap_name": poi["name"],
                "amap_lng": poi["lng"] or "",
                "amap_lat": poi["lat"] or "",
                "amap_address": poi["address"],
                "match_type": "",
                "distance_m": "",
            })

    # Write report
    total_ours = len(our_data)
    total_amap = len(amap_data)

    # Sort inaccurate by distance descending
    cat2_inaccurate.sort(key=lambda x: x[1], reverse=True)

    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("# 数据校准报告：我们的数据 vs 高德 POI\n\n")
        f.write(f"**生成时间**: 2026-02-10\n\n")
        f.write("---\n\n")
        f.write("## 总览\n\n")
        f.write(f"- 我们的数据：{total_ours} 条\n")
        f.write(f"- 高德住宅 POI：{total_amap} 条\n\n")
        f.write(f"| 分类 | 数量 | 占我们数据比例 |\n")
        f.write(f"|------|------|---------------|\n")
        f.write(f"| 双方都有，位置准确（<100m） | {len(cat1_accurate)} | {len(cat1_accurate)*100/total_ours:.1f}% |\n")
        f.write(f"| 双方都有，位置不准确（≥100m） | {len(cat2_inaccurate)} | {len(cat2_inaccurate)*100/total_ours:.1f}% |\n")
        f.write(f"| 仅我们有，高德没有 | {len(cat3_only_ours)} | {len(cat3_only_ours)*100/total_ours:.1f}% |\n")
        f.write(f"| 仅高德有，我们没有 | {len(cat4_only_amap)} | — |\n\n")

        f.write("---\n\n")
        f.write("## 1. 双方都有，位置准确（<100m）\n\n")
        f.write(f"共 {len(cat1_accurate)} 条，坐标偏差在100米以内，数据可靠。\n\n")

        f.write("---\n\n")
        f.write("## 2. 双方都有，位置不准确（≥100m）\n\n")
        f.write(f"共 {len(cat2_inaccurate)} 条，需要用高德坐标修正。\n\n")
        if cat2_inaccurate:
            # Show top 20 worst
            show = cat2_inaccurate[:30]
            for name, dist in show:
                if dist > 10000:
                    f.write(f"- **{name}** — 偏差 {dist/1000:.0f} km（严重错误）\n")
                elif dist > 1000:
                    f.write(f"- **{name}** — 偏差 {dist/1000:.1f} km\n")
                else:
                    f.write(f"- **{name}** — 偏差 {dist:.0f} m\n")
            if len(cat2_inaccurate) > 30:
                f.write(f"- ... 还有 {len(cat2_inaccurate) - 30} 条\n")

        f.write("\n---\n\n")
        f.write("## 3. 仅我们有，高德没有\n\n")
        f.write(f"共 {len(cat3_only_ours)} 条，可能是：名称变体未匹配、非住宅类（土地/商业）、或已拆除。\n\n")
        if cat3_only_ours:
            for name in sorted(cat3_only_ours):
                f.write(f"- {name}\n")

        f.write("\n---\n\n")
        f.write("## 4. 仅高德有，我们没有\n\n")
        f.write(f"共 {len(cat4_only_amap)} 条，fang.com 未收录的住宅小区。\n\n")
        if cat4_only_amap:
            for poi in sorted(cat4_only_amap, key=lambda x: x["name"])[:50]:
                f.write(f"- {poi['name']}（{poi['address']}）\n")
            if len(cat4_only_amap) > 50:
                f.write(f"- ... 还有 {len(cat4_only_amap) - 50} 条\n")

        f.write("\n---\n\n")
        f.write("## 详细数据\n\n")
        f.write(f"完整匹配明细见 `validation_detail.csv`\n\n")
        f.write("---\n\n")
        f.write("*报告由 Claude Code 自动生成*\n")

    print()
    print("=" * 60)
    print("Validation complete!")
    print(f"  Both + accurate:   {len(cat1_accurate)}")
    print(f"  Both + inaccurate: {len(cat2_inaccurate)}")
    print(f"  Only ours:         {len(cat3_only_ours)}")
    print(f"  Only Amap:         {len(cat4_only_amap)}")
    print(f"Detail CSV: {DETAIL_CSV}")
    print(f"Report: {REPORT_FILE}")
    print("=" * 60)


if __name__ == "__main__":
    main()
