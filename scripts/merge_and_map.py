#!/usr/bin/env python3
"""
Merge ESF and new house data, then generate an updated interactive HTML map.
"""

import csv
import json

ESF_GEO = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_esf_all_geo.csv"
NEWHOUSE_GEO = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_newhouse_all_geo.csv"
MERGED_CSV = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_merged_all.csv"
MAP_HTML = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_map.html"


def reclassify_zone(addr, bankuai=""):
    """Improved zone classification using address + bankuai."""
    text = f"{addr} {bankuai}"
    if not text.strip():
        return "其他"

    # 高新一期: 科技路以北, 南二环以南, 丈八北路以东
    if any(kw in text for kw in ["高新路", "高新四路", "太白立交", "电子城",
                                  "公交五公司", "科技路西口", "大寨路",
                                  "团结南路", "沣惠南路"]):
        return "高新一期"

    # 高新二期: 科技路以南到绕城
    if any(kw in text for kw in ["锦业路", "唐延路", "高新一中", "CID",
                                  "徐家庄", "西万路口", "西沣路"]):
        return "高新二期"

    # 高新三期/CID
    if any(kw in text for kw in ["中央创新区", "未来之瞳", "兴隆", "丝路科学城",
                                  "纬二十", "纬三十", "经二十", "经三十",
                                  "西太路", "规划", "星虹", "兴昌", "成业大道",
                                  "创智路", "大学城", "郭杜"]):
        return "高新三期"

    # 软件新城
    if any(kw in text for kw in ["软件", "天谷", "云水"]):
        return "软件新城"

    # 国际社区
    if any(kw in text for kw in ["国际社区", "灵秀", "灵韵", "北张"]):
        return "国际社区"

    # 科技路沿线 (use specific road names)
    if any(kw in text for kw in ["科技六路", "科技七路", "科技八路",
                                  "科技五路", "科技四路", "化龙",
                                  "绍文路", "鱼化"]):
        return "高新二期"

    if any(kw in text for kw in ["科技路", "科技一路", "科技二路", "科技三路",
                                  "高新六路", "高新三路", "高新二路"]):
        return "高新一期"

    return "其他"


def main():
    # Load ESF data
    esf_entries = []
    with open(ESF_GEO, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row.get("经度") or not row.get("纬度"):
                continue
            zone = reclassify_zone(row.get("地址", ""), row.get("板块", ""))
            esf_entries.append({
                "name": row["小区名称"],
                "price": row.get("均价(元/㎡)", ""),
                "addr": row.get("地址", ""),
                "lng": row["经度"],
                "lat": row["纬度"],
                "zone": zone,
                "type": "二手房",
                "year": row.get("建成年份", ""),
                "units": row.get("在售套数", ""),
            })

    # Load new house data (exclude those already in ESF)
    esf_names = {e["name"] for e in esf_entries}
    newhouse_entries = []
    with open(NEWHOUSE_GEO, "r", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if not row.get("经度") or not row.get("纬度"):
                continue
            name = row["楼盘名称"]
            if name in esf_names:
                continue  # skip duplicates
            zone = row.get("片区分类", "其他")
            newhouse_entries.append({
                "name": name,
                "price": row.get("参考均价(元/㎡)", ""),
                "addr": row.get("地址/位置", ""),
                "lng": row["经度"],
                "lat": row["纬度"],
                "zone": zone,
                "type": "新房",
                "year": "",
                "units": "",
            })

    all_entries = esf_entries + newhouse_entries
    print(f"ESF with coords: {len(esf_entries)}")
    print(f"New house (unique, with coords): {len(newhouse_entries)}")
    print(f"Total merged: {len(all_entries)}")

    # Write merged CSV
    fieldnames = ["名称", "均价(元/㎡)", "地址", "经度", "纬度", "片区", "类型", "建成年份", "在售套数"]
    with open(MERGED_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for e in all_entries:
            writer.writerow({
                "名称": e["name"],
                "均价(元/㎡)": e["price"],
                "地址": e["addr"],
                "经度": e["lng"],
                "纬度": e["lat"],
                "片区": e["zone"],
                "类型": e["type"],
                "建成年份": e["year"],
                "在售套数": e["units"],
            })
    print(f"Merged CSV: {MERGED_CSV}")

    # Zone stats
    from collections import Counter
    zone_counts = Counter(e["zone"] for e in all_entries)
    type_counts = Counter(e["type"] for e in all_entries)
    print("\nZone distribution:")
    for z in ["高新一期", "高新二期", "高新三期", "软件新城", "国际社区", "其他"]:
        print(f"  {z}: {zone_counts.get(z, 0)}")
    print(f"\nType distribution:")
    for t, c in type_counts.items():
        print(f"  {t}: {c}")

    # Generate map data
    map_data = []
    for e in all_entries:
        try:
            lng = float(e["lng"])
            lat = float(e["lat"])
        except (ValueError, TypeError):
            continue

        price = None
        if e["price"]:
            try:
                price = int(float(e["price"]))
            except (ValueError, TypeError):
                pass

        year = None
        if e["year"]:
            try:
                year = int(e["year"])
            except (ValueError, TypeError):
                pass

        units = None
        if e["units"]:
            try:
                units = int(e["units"])
            except (ValueError, TypeError):
                pass

        map_data.append({
            "n": e["name"],
            "p": price,
            "lng": lng,
            "lat": lat,
            "z": e["zone"],
            "t": e["type"],
            "y": year,
            "u": units,
        })

    print(f"\nMap data points: {len(map_data)}")

    # Generate HTML
    generate_map_html(map_data, zone_counts, MAP_HTML)
    print(f"Map HTML: {MAP_HTML}")


def generate_map_html(data, zone_counts, output_path):
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    total = len(data)

    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>西安高新区房地产地图（{total}个项目）</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        html, body {{ margin: 0; padding: 0; width: 100%; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
        #map {{ width: 100%; height: 100%; }}
        .panel {{
            position: absolute; top: 10px; right: 10px; z-index: 1000;
            background: white; padding: 12px 15px; border-radius: 8px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.15); max-width: 280px;
            font-size: 13px;
        }}
        .panel h3 {{ margin: 0 0 8px 0; font-size: 15px; }}
        .legend-item {{ display: flex; align-items: center; margin: 3px 0; font-size: 12px; }}
        .legend-dot {{ width: 12px; height: 12px; border-radius: 50%; margin-right: 8px; flex-shrink: 0; border: 1px solid rgba(0,0,0,0.1); }}
        .btn {{
            display: inline-block; padding: 4px 10px; margin: 2px;
            border: 1px solid #ddd; border-radius: 4px; cursor: pointer;
            font-size: 12px; background: white; user-select: none;
        }}
        .btn:hover {{ background: #f5f5f5; }}
        .btn.active {{ background: #1890ff; color: white; border-color: #1890ff; }}
        .stats {{ color: #666; font-size: 12px; margin: 4px 0; }}
        .popup-name {{ font-weight: bold; font-size: 14px; margin-bottom: 4px; }}
        .popup-price {{ color: #e74c3c; font-size: 16px; font-weight: bold; margin-bottom: 4px; }}
        .popup-detail {{ font-size: 12px; color: #666; line-height: 1.6; }}
        .popup-type {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; color: white; margin-left: 6px; }}
        .zone-label {{
            background: rgba(255,255,255,0.85) !important; border: none !important;
            box-shadow: 0 1px 4px rgba(0,0,0,0.15) !important;
            font-size: 13px !important; font-weight: bold !important;
            padding: 3px 8px !important; border-radius: 4px !important;
        }}
        .price-filter {{ margin-top: 8px; border-top: 1px solid #eee; padding-top: 8px; }}
        .price-filter label {{ font-size: 12px; color: #666; display: block; margin-bottom: 4px; }}
        .price-range {{ display: flex; gap: 4px; align-items: center; font-size: 12px; }}
        .price-range input {{ width: 60px; padding: 3px 6px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px; }}
        .type-filter {{ margin-top: 6px; }}
    </style>
</head>
<body>
<div id="map"></div>
<div class="panel">
    <h3>西安高新区房地产地图</h3>
    <div class="stats" id="stats">共 {total} 个项目</div>
    <div style="font-size: 11px; color: #999; margin-bottom: 6px;">点击标记查看详情</div>
    <div id="legend"></div>
    <div style="margin-top: 6px;">
        <div class="btn active" onclick="setZone('all')">全部</div>
        <div class="btn" onclick="setZone('高新一期')">一期</div>
        <div class="btn" onclick="setZone('高新二期')">二期</div>
        <div class="btn" onclick="setZone('高新三期')">三期</div>
        <div class="btn" onclick="setZone('软件新城')">软件</div>
        <div class="btn" onclick="setZone('国际社区')">社区</div>
        <div class="btn" onclick="setZone('其他')">其他</div>
    </div>
    <div class="type-filter">
        <div class="btn active" onclick="setType('all')">全部</div>
        <div class="btn" onclick="setType('二手房')">二手房</div>
        <div class="btn" onclick="setType('新房')">新房</div>
    </div>
    <div class="price-filter">
        <label>价格筛选 (元/㎡)</label>
        <div class="price-range">
            <input type="number" id="priceMin" placeholder="最低" oninput="applyFilters()">
            <span>-</span>
            <input type="number" id="priceMax" placeholder="最高" oninput="applyFilters()">
        </div>
    </div>
</div>

<script>
const data = {data_json};

const colorMap = {{
    '高新一期': '#e74c3c',
    '高新二期': '#3498db',
    '高新三期': '#2ecc71',
    '软件新城': '#f39c12',
    '国际社区': '#9b59b6',
    '其他': '#95a5a6'
}};

const map = L.map('map').setView([34.20, 108.87], 12);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap',
    maxZoom: 19
}}).addTo(map);

// Zone boundaries
const zones = [
    {{
        name: '高新一期', color: '#e74c3c',
        coords: [[34.248,108.866],[34.248,108.895],[34.220,108.895],[34.227,108.866],[34.248,108.866]]
    }},
    {{
        name: '高新二期', color: '#3498db',
        coords: [[34.227,108.862],[34.220,108.895],[34.163,108.882],[34.163,108.862],[34.227,108.862]]
    }},
    {{
        name: '高新三期', color: '#2ecc71',
        coords: [[34.170,108.810],[34.170,108.840],[34.155,108.850],[34.130,108.830],[34.130,108.810],[34.155,108.798],[34.170,108.810]]
    }},
    {{
        name: '软件新城', color: '#f39c12',
        coords: [[34.232,108.812],[34.232,108.866],[34.199,108.862],[34.199,108.812],[34.232,108.812]]
    }},
    {{
        name: '国际社区', color: '#9b59b6',
        coords: [[34.185,108.888],[34.185,108.920],[34.160,108.920],[34.160,108.888],[34.185,108.888]]
    }}
];

let zoneLayers = [];
function renderZones(filter) {{
    zoneLayers.forEach(l => map.removeLayer(l));
    zoneLayers = [];
    const show = filter === 'all' ? zones : zones.filter(z => z.name === filter);
    show.forEach(z => {{
        const poly = L.polygon(z.coords, {{
            color: z.color, weight: 2, opacity: 0.5,
            fillColor: z.color, fillOpacity: 0.06, dashArray: '6,4'
        }}).addTo(map);
        poly.bindTooltip(z.name, {{ permanent: filter === 'all', direction: 'center', className: 'zone-label' }});
        zoneLayers.push(poly);
    }});
}}

function makeIcon(color, isNew) {{
    const size = isNew ? 'width="20" height="30" viewBox="0 0 20 30"' : 'width="18" height="27" viewBox="0 0 18 27"';
    const r = isNew ? 4 : 3.5;
    const cx = isNew ? 10 : 9;
    const cy = isNew ? 10 : 9;
    const path = isNew
        ? '<path d="M10 0C4.5 0 0 4.5 0 10c0 7.5 10 20 10 20s10-12.5 10-20C20 4.5 15.5 0 10 0z"'
        : '<path d="M9 0C4 0 0 4 0 9c0 6.75 9 18 9 18s9-11.25 9-18C18 4 14 0 9 0z"';
    const shape = isNew ? 'rect' : 'circle';
    const inner = isNew
        ? `<rect x="6" y="6" width="8" height="8" fill="#fff" opacity="0.9" rx="1"/>`
        : `<circle cx="${{cx}}" cy="${{cy}}" r="${{r}}" fill="#fff" opacity="0.9"/>`;
    return L.divIcon({{
        className: '',
        html: `<svg ${{size}} xmlns="http://www.w3.org/2000/svg">
            ${{path}} fill="${{color}}" stroke="#fff" stroke-width="1.2"/>
            ${{inner}}
        </svg>`,
        iconSize: isNew ? [20, 30] : [18, 27],
        iconAnchor: isNew ? [10, 30] : [9, 27],
        popupAnchor: [0, isNew ? -30 : -27]
    }});
}}

let markers = [];
let currentZone = 'all';
let currentType = 'all';

function applyFilters() {{
    markers.forEach(m => map.removeLayer(m));
    markers = [];

    const minP = parseInt(document.getElementById('priceMin').value) || 0;
    const maxP = parseInt(document.getElementById('priceMax').value) || Infinity;

    let filtered = data;
    if (currentZone !== 'all') filtered = filtered.filter(d => d.z === currentZone);
    if (currentType !== 'all') filtered = filtered.filter(d => d.t === currentType);
    if (minP > 0) filtered = filtered.filter(d => d.p && d.p >= minP);
    if (maxP < Infinity) filtered = filtered.filter(d => d.p && d.p <= maxP);

    filtered.forEach(d => {{
        const color = colorMap[d.z] || '#95a5a6';
        const isNew = d.t === '新房';
        const marker = L.marker([d.lat, d.lng], {{ icon: makeIcon(color, isNew) }}).addTo(map);

        const priceText = d.p ? d.p.toLocaleString() + ' 元/㎡' : '暂无';
        const typeColor = isNew ? '#e67e22' : '#27ae60';
        const typeLabel = isNew ? '新房' : '二手房';
        const yearText = d.y || '未知';
        const unitsText = d.u ? d.u + ' 套' : '-';

        marker.bindPopup(`
            <div class="popup-name">${{d.n}}<span class="popup-type" style="background:${{typeColor}}">${{typeLabel}}</span></div>
            <div class="popup-price">${{priceText}}</div>
            <div class="popup-detail">
                片区: ${{d.z}}<br>
                ${{d.t === '二手房' ? '在售: ' + unitsText + '<br>建成: ' + yearText + '年' : ''}}
            </div>
        `);
        markers.push(marker);
    }});

    document.getElementById('stats').textContent = `显示 ${{filtered.length}} / ${{data.length}} 个项目`;
}}

function setZone(zone) {{
    currentZone = zone;
    document.querySelectorAll('.panel > div:nth-child(5) .btn').forEach(b => {{
        b.classList.toggle('active', (zone === 'all' && b.textContent === '全部') || b.textContent.includes(zone.replace('高新','').replace('新城','').replace('社区','')));
    }});
    renderZones(zone);
    applyFilters();
}}

function setType(type) {{
    currentType = type;
    document.querySelectorAll('.type-filter .btn').forEach(b => {{
        b.classList.toggle('active', (type === 'all' && b.textContent === '全部') || b.textContent === type);
    }});
    applyFilters();
}}

// Build legend
const zoneCounts = {{}};
data.forEach(d => {{ zoneCounts[d.z] = (zoneCounts[d.z] || 0) + 1; }});
const legendHtml = Object.entries(colorMap).map(([z, c]) => {{
    const count = zoneCounts[z] || 0;
    if (count === 0) return '';
    return `<div class="legend-item"><div class="legend-dot" style="background:${{c}}"></div>${{z}} (${{count}})</div>`;
}}).join('');
document.getElementById('legend').innerHTML = legendHtml;

renderZones('all');
applyFilters();
</script>
</body>
</html>'''

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
