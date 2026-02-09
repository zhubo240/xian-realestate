#!/usr/bin/env python3
"""
Scrape all pages of 高新区 二手房小区 data from fang.com.
URL pattern: https://xian.esf.fang.com/housing/482__0_3_0_0_{page}_0_0_0/
Pages 1..56, 20 items per page, ~1100 communities total.
"""

import urllib.request
import gzip
import re
import csv
import time
import sys

BASE_URL = "https://xian.esf.fang.com/housing/482__0_3_0_0_{}_0_0_0/"
TOTAL_PAGES = 56
OUTPUT_CSV = "/Users/bozhu/.openclaw/workspace/xian-realestate/data/gaoxin_esf_all.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Referer": "https://xian.esf.fang.com/",
}

# Property types to skip (non-residential)
SKIP_TYPES = {"写字楼", "商铺", "车位", "商业", "办公", "工业", "厂房", "仓库"}


def fetch_page(page_num):
    """Fetch a single page and return decoded HTML. Returns None on failure."""
    url = BASE_URL.format(page_num)
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=20)
        data = resp.read()
        try:
            html = gzip.decompress(data).decode("utf-8", errors="replace")
        except Exception:
            html = data.decode("utf-8", errors="replace")
        return html
    except Exception as e:
        print(f"  [WARN] Page {page_num} fetch error: {e}")
        return None


def parse_page(html):
    """Parse one page of HTML and return list of community dicts."""
    communities = []

    # Each listing block: <div id="houselist_B09_XX" ...>...(dl block)...(price div)...</div>
    # We split by the listing div boundaries
    blocks = re.findall(
        r'<div\s+id="houselist_B09_\d+"[^>]*>.*?</div>\s*</div>',
        html,
        re.DOTALL,
    )

    # If the above doesn't work well, try alternative: split on the B09 pattern
    if not blocks:
        # Fallback: extract everything between consecutive houselist_B09 markers
        parts = re.split(r'(?=<div\s+id="houselist_B09_)', html)
        blocks = [p for p in parts if "houselist_B09" in p]

    for block in blocks:
        entry = {}

        # Community name: <a ... class="plotTit">NAME</a>
        m = re.search(r'class="plotTit"[^>]*>([^<]+)</a>', block)
        if not m:
            continue
        entry["小区名称"] = m.group(1).strip()

        # Property type: <span class="plotFangType">TYPE</span>
        m_type = re.search(r'class="plotFangType"[^>]*>([^<]+)</span>', block)
        if m_type:
            ftype = m_type.group(1).strip()
            if ftype in SKIP_TYPES:
                continue

        # Price: <p class="priceAverage"><span> 33439 </span>...元/㎡
        m_price = re.search(
            r'class="priceAverage"[^>]*>\s*<span>\s*(\d+)\s*</span>', block
        )
        if m_price:
            entry["均价(元/㎡)"] = m_price.group(1).strip()
        else:
            # Check for "暂无均价"
            entry["均价(元/㎡)"] = ""

        # Address: the second <p> inside <dd>, containing area links and address text
        # Pattern: <a ...>高新</a>-<a ...>SUBAREA</a> ADDRESS_TEXT
        m_addr = re.search(
            r'<dd>.*?<p>.*?</p>\s*<p>(.*?)</p>',
            block,
            re.DOTALL,
        )
        full_addr = ""
        bankuai = ""
        if m_addr:
            addr_html = m_addr.group(1)
            # Extract 板块 (sub-area): the second <a> in address line
            addr_links = re.findall(r'<a[^>]*>([^<]+)</a>', addr_html)
            if len(addr_links) >= 2:
                bankuai = addr_links[1].strip()
            elif len(addr_links) == 1:
                bankuai = addr_links[0].strip()

            # Full address: strip tags
            full_addr = re.sub(r'<[^>]+>', '', addr_html).strip()
            # Clean up extra whitespace
            full_addr = re.sub(r'\s+', ' ', full_addr).strip()
            # Remove leading dash if present
            full_addr = full_addr.strip("- ")

        entry["地址"] = full_addr
        entry["板块"] = bankuai

        # Year built: YYYY年建成
        m_year = re.search(r'(\d{4})年建成', block)
        entry["建成年份"] = m_year.group(1) if m_year else ""

        # Units for sale: <a ...> 168 </a>套在售
        m_units = re.search(r'<a[^>]*>\s*(\d+)\s*</a>\s*套在售', block)
        entry["在售套数"] = m_units.group(1) if m_units else ""

        communities.append(entry)

    return communities


def main():
    all_communities = []
    failed_pages = []

    print(f"Starting scrape of {TOTAL_PAGES} pages from fang.com...")
    print(f"Output: {OUTPUT_CSV}")
    print()

    for page in range(1, TOTAL_PAGES + 1):
        html = fetch_page(page)

        # Retry once on failure
        if html is None or len(html) < 1000:
            print(f"  [RETRY] Page {page} - waiting 5s before retry...")
            time.sleep(5)
            html = fetch_page(page)

        if html is None or len(html) < 1000:
            print(f"  [SKIP] Page {page} - failed after retry")
            failed_pages.append(page)
        else:
            communities = parse_page(html)
            all_communities.extend(communities)

            if page % 5 == 0 or page == 1:
                print(
                    f"  Page {page}/{TOTAL_PAGES}: {len(communities)} communities "
                    f"(total so far: {len(all_communities)})"
                )

        # Delay between requests
        if page < TOTAL_PAGES:
            time.sleep(2)

    # Write CSV
    fieldnames = ["小区名称", "均价(元/㎡)", "地址", "板块", "建成年份", "在售套数"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_communities)

    print()
    print("=" * 60)
    print(f"Scraping complete!")
    print(f"Total communities scraped: {len(all_communities)}")
    print(f"Failed pages: {failed_pages if failed_pages else 'None'}")
    print(f"CSV saved to: {OUTPUT_CSV}")
    print("=" * 60)


if __name__ == "__main__":
    main()
