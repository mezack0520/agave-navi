#!/usr/bin/env python3
"""
Weekly event crawler for agave-navi.com
Checks 17 crawl sources for new plant events and generates a report.
Designed to run as a GitHub Actions workflow.
"""

# Aggregator handling:
# - crawl-sources.json で discovery_only:true がついたソースは "発見専用" 扱い
# - 抽出した候補は Issue に "発見元: aggregator" と注記
# - ユーザーが手動レビューして new-events.json に追加するときに、
#   実際の公式URLは別途確認する流れ
# - sanity-check-new-events.py が aggregator URL を url/sourceUrl に
#   採用しないように最終チェック


import json
import os
import re
import sys
from datetime import datetime, timedelta
from urllib.parse import urljoin

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import today_jst, now_jst   # noqa: E402

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
    """Generic event extraction from HTML pages — improved precision version.

    Requires for each candidate:
      - Date pattern (YYYY/MM/DD or YYYY年MM月DD日 or MM月DD日)
      - At least one plant-related keyword in title or surrounding text
      - At least one event-related keyword in title or surrounding text
      - Title is NOT a known noise pattern (privacy, contact, archive, etc.)
      - Year is not in the past
    """
    if not html:
        return []

    CURRENT_YEAR = int(today_jst()[:4])

    soup = BeautifulSoup(html, 'lxml')
    events = []

    # Noise title patterns (clearly non-event pages/sections)
    noise_pats = [
        r'^プライバシー', r'^お問い合わせ', r'^利用規約', r'^免責',
        r'^運営者', r'^サイト[マポ]', r'^関連記事', r'^おすすめ',
        r'^カテゴリ', r'^アーカイブ', r'^ホーム$', r'^Home$',
        r'まとめ$', r'^新着', r'^記事一覧', r'^最新記事',
        r'コメント', r'ログイン', r'^登録', r'^検索',
        r'^第\d+章', r'^Chapter', r'^Page',
        r'^20\d{2}年.*植物イベントまとめ',
        r'^全国の.*専門店',
        r'の特徴$', r'の育て方$', r'^どう育て', r'の作り方$', r'の手入れ',
        r'^ニュース$', r'^お知らせ$', r'^イベント$', r'^Event$',
        r'^トップ$', r'^Top$',
    ]
    noise_re = re.compile('|'.join(noise_pats))

    # Event keywords
    event_kw = [
        '即売会', 'マルシェ', 'イベント', 'フェス', 'バザール',
        '展示会', '販売会', '即売', 'フェア', '祭', '楽市',
        'ワークショップ', '体験会', '勉強会', '交換会',
        'パーティ', 'MEETING', 'meeting', 'MARKET', 'market',
        'BAZAAR', 'bazaar', 'FES', 'fes', 'EXPO', 'expo',
        'コレクション', 'COLLECTION', 'collection',
    ]

    # Plant keywords
    plant_kw = [
        'アガベ', 'agave', 'AGAVE', '多肉', 'タニク',
        'コーデックス', 'caudex', 'CAUDEX', '塊根',
        'サボテン', 'cactus', 'cacti', 'CACTUS',
        '珍奇', 'ビザール', 'bizarre', 'BIZARRE',
        'プランツ', 'plant', 'PLANT', 'PLANTS',
        'BOTANICAL', 'botanical', 'ボタニカル',
        '植物', 'グリーン', 'green', 'GREEN',
        'ハオルチア', 'エケベリア', 'パキポ', 'グラキリス',
        'ユーフォルビア', 'ブロメリア', 'チランジア',
        '園芸', 'ガーデン', 'garden', 'GARDEN',
    ]

    date_patterns = [
        r'(\d{4})[./年-](\d{1,2})[./月-](\d{1,2})',  # 2026.04.15 / 2026年4月15日 / 2026-04-15
        r'(\d{1,2})[./月](\d{1,2})[日]',                # 4月15日 (year unknown)
    ]

    pref_re = re.compile(
        r'(北海道|青森|岩手|宮城|秋田|山形|福島|茨城|栃木|群馬|埼玉|千葉|東京|神奈川|'
        r'新潟|富山|石川|福井|山梨|長野|岐阜|静岡|愛知|三重|滋賀|京都|大阪|兵庫|奈良|和歌山|'
        r'鳥取|島根|岡山|広島|山口|徳島|香川|愛媛|高知|福岡|佐賀|長崎|熊本|大分|宮崎|鹿児島|沖縄)'
    )

    def is_noise(title):
        if not title or len(title) < 3 or len(title) > 120:
            return True
        return bool(noise_re.search(title))

    def has_any(text, kws):
        return any(k in text for k in kws)

    def extract_date(text):
        """Return (iso_date, has_year_explicit). Filters out past years."""
        for pat in date_patterns:
            for m in re.finditer(pat, text):
                g = m.groups()
                try:
                    if len(g) == 3:
                        y, mo, d = int(g[0]), int(g[1]), int(g[2])
                        if 2020 <= y <= CURRENT_YEAR + 3 and 1 <= mo <= 12 and 1 <= d <= 31:
                            if y < CURRENT_YEAR:
                                continue  # past year, keep looking for newer date
                            return f"{y:04d}-{mo:02d}-{d:02d}", True
                    elif len(g) == 2:
                        mo, d = int(g[0]), int(g[1])
                        if 1 <= mo <= 12 and 1 <= d <= 31:
                            return f"{CURRENT_YEAR:04d}-{mo:02d}-{d:02d}", False
                except Exception:
                    continue
        return None, False

    # Strategy 1: article/li/div blocks with event-related class
    blocks = soup.find_all(['article', 'li', 'div'],
                            class_=re.compile(r'event|post|item|card|news', re.I))

    for block in blocks:
        title_el = block.find(['h1', 'h2', 'h3', 'h4', 'a', 'strong'])
        if not title_el:
            continue

        title = title_el.get_text(strip=True)
        if is_noise(title):
            continue

        block_text = block.get_text(' ', strip=True)[:1500]
        combined = title + ' ' + block_text

        # All three required
        if not has_any(combined, plant_kw):
            continue
        if not has_any(combined, event_kw):
            continue

        date_str, has_year = extract_date(combined)
        if not date_str:
            continue

        # Get link
        link = None
        link_el = block.find('a', href=True)
        if link_el:
            link = urljoin(source_url, link_el['href'])

        # Get location
        location = None
        pm = pref_re.search(combined)
        if pm:
            location = pm.group(1)

        events.append({
            'name': title,
            'date': date_str,
            'location': location,
            'source': source_name,
            'source_url': link or source_url,
            'has_year': has_year,
        })

    # Strategy 2 (fallback): bare headings if Strategy 1 found nothing
    if not events:
        for h in soup.find_all(['h2', 'h3', 'h4']):
            title = h.get_text(strip=True)
            if is_noise(title):
                continue
            if not has_any(title, event_kw):
                continue

            # Look around for context (next 6 siblings)
            ctx = title
            try:
                cur = h.next_sibling
                cnt = 0
                while cur is not None and cnt < 6:
                    if hasattr(cur, 'get_text'):
                        ctx += ' ' + cur.get_text(' ', strip=True)
                    elif isinstance(cur, str):
                        ctx += ' ' + cur
                    cur = cur.next_sibling
                    cnt += 1
            except Exception:
                pass

            if not has_any(ctx, plant_kw):
                continue

            date_str, has_year = extract_date(ctx)
            if not date_str:
                continue

            link_el = h.find('a', href=True)
            link = urljoin(source_url, link_el['href']) if link_el else None

            location = None
            pm = pref_re.search(ctx)
            if pm:
                location = pm.group(1)

            events.append({
                'name': title,
                'date': date_str,
                'location': location,
                'source': source_name,
                'source_url': link or source_url,
                'has_year': has_year,
            })

    # Dedupe by (name, date)
    seen = set()
    uniq = []
    for e in events:
        k = (e['name'], e.get('date'))
        if k in seen:
            continue
        seen.add(k)
        uniq.append(e)

    return uniq


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
        return event_date >= datetime.strptime(today_jst(), '%Y-%m-%d') - timedelta(days=7)
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
    print(f"Started at: {now_jst().isoformat()}")

    # Load sources
    try:
        with open(SOURCES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        sources = data['sources']
    except Exception as e:
        print(f"Error loading sources: {e}")
        sys.exit(1)

    # 自動導出ウォッチリスト(watch-sources.json)の公式サイト候補を追加巡回
    # (generate-watchlist.py が events.json から毎日再生成する。手動管理不要)
    watch_path = os.path.join(os.path.dirname(SOURCES_PATH), 'watch-sources.json')
    try:
        with open(watch_path, 'r', encoding='utf-8') as f:
            watch = json.load(f)
        existing_urls = {s.get('url') for s in sources}
        added = 0
        for c in watch.get('officialSiteCandidates', []):
            if c.get('url') and c['url'] not in existing_urls:
                sources.append({
                    'name': f"[auto] {c.get('eventName','')} 公式",
                    'url': c['url'],
                    'type': 'auto-organizer',
                    'discovery_only': True,
                    'notes': 'watch-sources.json由来の自動候補',
                })
                added += 1
        print(f"watch-sources: {added} auto-organizer sources added")
    except FileNotFoundError:
        pass
    except Exception as e:
        print(f"watch-sources load skipped: {e}")

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
