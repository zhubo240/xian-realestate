# 西安高新区房地产数据集

西安市高新区小区级房地产数据采集、地理编码与可视化项目。

## 项目概况

- **二手房小区**：523 个住宅小区（fang.com 高新区 1,107 个中过滤掉写字楼/商铺/车位等）
- **新房楼盘**：171 个（含 110 个命名项目 + 61 个土地地块）
- **合并总计**：645 个数据点（去重后）
- **地理编码覆盖率**：ESF 95%+，新房 92.4%

## 技术方案

- **数据源**：房天下 (fang.com)
- **经纬度**：高德地图 API（POI Search v5 + Geocoding v3）
- **坐标系**：WGS-84（从高德 GCJ-02 转换，西安偏移量 lng-0.0065, lat-0.0060）
- **存储格式**：CSV (UTF-8 with BOM)
- **可视化**：Leaflet.js 交互地图

## 目录结构

```
xian-realestate/
├── README.md
├── scrape_gaoxin_esf.py        # 二手房爬虫（56页，urllib+正则）
├── geocode_communities.py      # 二手房地理编码（高德 API）
├── geocode_newhouse.py         # 新房地理编码（高德 API）
├── merge_and_map.py            # 数据合并 + HTML 地图生成
├── data/
│   ├── gaoxin_esf_all.csv          # 二手房原始数据（523条）
│   ├── gaoxin_esf_all_geo.csv      # 二手房+坐标+片区（523条）
│   ├── gaoxin_esf_communities.csv  # 二手房精选版（60条，早期）
│   ├── gaoxin_newhouse.csv         # 新房早期数据（60条，3页）
│   ├── gaoxin_newhouse_all.csv     # 新房完整数据（171条，9页）
│   ├── gaoxin_newhouse_all_geo.csv # 新房+坐标+片区（171条）
│   ├── gaoxin_merged_all.csv       # 合并数据（645条）
│   ├── gaoxin_map.html             # 交互地图（645个标记）
│   ├── gaoxin_summary.md           # 数据分析报告
│   ├── gaoxin_map_screenshot.png   # 地图截图
│   └── qujiang_communities.csv     # 曲江测试数据（10条）
├── docs/
│   └── exploration.md              # 探索记录
└── *.png                           # 历史地图截图
```

## 脚本说明

| 脚本 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `scrape_gaoxin_esf.py` | 抓取二手房小区数据 | fang.com 56页 | `gaoxin_esf_all.csv` |
| `geocode_communities.py` | 二手房地理编码+片区分类 | `gaoxin_esf_all.csv` | `gaoxin_esf_all_geo.csv` |
| `geocode_newhouse.py` | 新房地理编码+片区分类 | `gaoxin_newhouse_all.csv` | `gaoxin_newhouse_all_geo.csv` |
| `merge_and_map.py` | 合并数据+生成地图 | `*_geo.csv` | `gaoxin_merged_all.csv` + `gaoxin_map.html` |

## 地图功能

`data/gaoxin_map.html` 提供以下交互功能：

- **片区筛选**：高新一期/二期/三期/软件新城/国际社区/其他
- **类型筛选**：二手房/新房
- **价格区间**：自定义最低-最高价过滤
- **标记详情**：点击查看名称、均价、片区、建成年份等
- **片区边界**：虚线多边形标注各片区范围

## 片区分布

| 片区 | 数量 | 说明 |
|------|------|------|
| 高新一期 | 217 | 科技路以北，南二环以南 |
| 高新二期 | 293 | 科技路以南，绕城以北 |
| 高新三期 | 64 | 中央创新区（CID）+ 丝路科学城 |
| 软件新城 | 50 | 天谷路/云水路一带 |
| 国际社区 | 7 | 灵秀/灵韵/北张路区域 |
| 其他 | 14 | 未明确归类 |

## 注意事项

- fang.com 快速请求 ~30 次后会触发验证码，二手房爬虫设置 2 秒间隔
- 新房页面使用客户端 JS 分页，无法用 urllib 抓取后续页面，需浏览器自动化
- 高德 API 免费额度 5,000 次/天，足够覆盖全量数据
