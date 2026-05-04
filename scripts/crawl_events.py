#!/usr/bin/env python3
"""
Weekly event crawler for agave-navi.com
Checks 17 crawl sources for new plant events and generates a report.
Designed to run as a GitHub Actions workflow.
"""

import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Load crawl sources
SOURCES_PATH = os.path.join(os.path.dirname(__file__), '..', 'crawl-sources.json')
EVENTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'events.json')
REPORT_PATH = '/tmp/crawl-report.md'

AGGREGATOR_BLOCKLIST = (
    'nextmeet.app', 'botanical-zone.tokyo', 'leaf-laboratory.com',
    'tochinavi.net', 'pukubook.jp', 'fukuoka-now.com', 'churatoku.net', 'agavemaniacs.com',
)


def is_aggregator(url):
    if not url: return False
    return any(ag in url.lower() for ag in AGGREGATOR_BLOCKLIST)


HEADERS = {
    'User-Agent': 'AgaveNaviBot/1.0 (+https://agave-navi.com/about.html)',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'ja,en;q=0.5',
}

# Known event slugs (to avoid duplicates)
def load_known_events():
    try:
        with open(EVENTS_PATH, 'r', encoding='utf-8') as f:
            events = json.load(f)
        return {e['slug'] for e in events}, {e['name'] for e in events}
    except Exception:
        return set(), set()


def fetch_page(url, timeout=15):
    """Fetch a web page with error handling"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or 'utf-8'
        return resp.text
    except Exception as e:
        return None


def extract_events_from_html(html, source_name, source_url):
    """Generic event extraction from HTML pages"""
    if not html:
        return []

    soup = BeautifulSoup(html, 'lxml')
    events = []

    # Common date patterns in Japanese event pages
    date_patterns = [
        r'(\d{4})[./年](\d{1,2})[./月](\d{1,2})',  # 2026.04.15 or 2026年4月15日
        r'(\d{1,2})[./月](\d{1,2})[日]',             # 4月15日
    ]

    # Look for event-like content blocks
    # Strategy 1: Look for articles/cards with dates and event names
    for article in soup.find_all(['article', 'li', 'div'], class_=re.compile(r'event|post|item|card', re.I)):
        title_el = article.find(['h2', 'h3', 'h4', 'a', 'strong'])
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if len(title) < 3 or len(title) > 100:
            continue

        # Extract link
        link = None
        link_el = article.find('a', href=True)
        if link_el:
            link = urljoin(source_url, link_el['href'])

        # Extract date from text
        text = article.get_text()
        date_str = None
        for pat in date_patterns:
            m = re.search(pat, text)
            if m:
                groups = m.groups()
                if len(groups) == 3:
                    date_str = f"{groups[0]}-{int(groups[1]):02d}-{int(groups[2]):02d}"
                break

        # Extract location hints
        location = None
        loc_patterns = [
            r'(東京|大阪|名古屋|福岡|札幌|横浜|神戸|京都|埼玉|千葉|広島|仙台)',
            r'([\u4e00-\u9fff]{2,4}[県府都道])',
        ]
        for lp in loc_patterns:
            lm = re.search(lp, text)
            if lm:
                location = lm.group(1)
                break

        events.append({
            'name': title,
            'date': date_str,
            'location': location,
            'source': source_name,
            'source_url': link or source_url,
        })

    # Strategy 2: Look for links containing event-related keywords
    if not events:
        for a in soup.find_all('a', href=True):
            text = a.get_text(strip=True)
            if any(kw in text for kw in ['即売会', 'マルシェ', 'イベント', 'フェス', 'バザール', '展示']):
                if len(text) >= 5 and len(text) <= 80:
                    events.append({
                        'name': text,
                        'date': None,
                        'location': None,
                        'source': source_name,
                        'source_url': urljoin(source_url, a['href']),
                    })

    return events


def crawl_source(source):
    """Crawl a single source and return found events"""
    name = source['name']
    url = source['url']
    source_type = source.get('type', 'unknown')

    print(f"  Crawling: {name} ({source_type})")

    # Skip Instagram and other non-scrapable sources
    if 'instagram.com' in url or source_type == 'sns':
        return [], f"Skipped (SNS/non-scrapable)"

    html = fetch_page(url)
    if not html:
        return [], f"Failed to fetch"

    events = extract_events_from_html(html, name, url)
    return events, f"Found {len(events)} potential events"


def is_new_event(event, known_slugs, known_names):
    """Check if an event is likely new (not already in our database)"""
    name = event['name'].lower().strip()

    # Check exact name match
    for known in known_names:
        if name == known.lower():
            return False
        # Fuzzy match: check if significant overlap
        if len(name) > 5 and (name in known.lower() or known.lower() in name):
            return False

    return True


def is_future_event(event):
    """Check if event date is in the future"""
    if not event.get('date'):
        return True  # Unknown date, include for review

    try:
        event_date = datetime.strptime(event['date'], '%Y-%m-%d')
        return event_date >= datetime.now() - timedelta(days=7)
    except ValueError:
        return True


def generate_report(results, new_events):
    """Generate a markdown report"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    report = f"""## 自動巡回レポート
**実行日時**: {now} (UTC)
**巡回サイト数**: {len(results)}

### 巡回結果サマリー

| サイト名 | ステータス |
|---------|-----------|
"""
    for name, status in results:
        report += f"| {name} | {status} |\n"

    if new_events:
        report += f"\n### 新規イベント候補 ({len(new_events)}件)\n\n"
        report += "以下のイベントが新規と思われます。確認の上、events.jsonに追加してください。\n\n"

        for i, ev in enumerate(new_events, 1):
            report += f"#### {i}. {ev['name']}\n"
            if ev.get('date'):
                report += f"- **日時**: {ev['date']}\n"
            if ev.get('location'):
                report += f"- **場所**: {ev['location']}\n"
            report += f"- **情報源**: [{ev['source']}]({ev['source_url']})\n\n"
    else:
        report += "\n### 新規イベント候補\n\n新しいイベント情報は見つかりませんでした。\n"

    report += "\n---\n*このレポートはGitHub Actionsによる自動巡回で生成されました。*\n"
    return report


def main():
    print("=== agave-navi.com Event Crawler ===")
    print(f"Started at: {datetime.now().isoformat()}")

    # Load sources
    try:
        with open(SOURCES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sources = data['sources']
    except Exception as e:
        print(f"Error loading sources: {e}")
        sys.exit(1)

    # Load known events
    known_slugs, known_names = load_known_events()
    print(f"Known events: {len(known_slugs)}")

    # Crawl each source
    results = []
    all_events = []

    for source in sources:
        # コメント用エントリ（_comment のみ等）をスキップ
        if 'name' not in source or 'url' not in source:
            continue
        try:
            events, status = crawl_source(source)
            results.append((source['name'], status))
            all_events.extend(events)
        except Exception as e:
            results.append((source.get('name', 'unknown'), f"Error: {str(e)[:50]}"))

    print(f"\nTotal events found across all sources: {len(all_events)}")

    # Filter for new events
    new_events = []
    seen_names = set()

    for ev in all_events:
        if not is_future_event(ev):
            continue
        if not is_new_event(ev, known_slugs, known_names):
            continue

        # Deduplicate within results
        name_key = ev['name'].lower().strip()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)

        new_events.append(ev)

    print(f"New event candidates: {len(new_events)}")

    # Generate report
    report = generate_report(results, new_events)

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\nReport saved to {REPORT_PATH}")
    print("=== Crawl complete ===")


if __name__ == '__main__':
    main()
