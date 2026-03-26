#!/usr/bin/env python3
"""
Discover new crawl sources for agave-navi.com

Searches DuckDuckGo for plant event keywords, collects unique domains,
compares with existing crawl-sources.json, and reports new candidates
as a GitHub Issue for human review.

Designed to run weekly via GitHub Actions.
"""

import json
import os
import re
import sys
import time
from datetime import datetime
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

# Paths
SOURCES_PATH = os.path.join(os.path.dirname(__file__), '..', 'crawl-sources.json')
REPORT_PATH = '/tmp/discover-report.md'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja,en;q=0.5',
}

# ---------------------------------------------------------------------------
# Search keywords — edit this list to adjust discovery scope
# ---------------------------------------------------------------------------
SEARCH_QUERIES = [
    "アガベ イベント 2026",
    "アガベ 即売会 2026",
    "塊根植物 イベント 2026",
    "多肉植物 即売会 2026",
    "ビザールプランツ イベント",
    "多肉植物 マルシェ 2026",
    "サボテン 即売会 2026",
    "珍奇植物 イベント 一覧",
    "植物 イベント カレンダー 2026",
    "アガベ フェス 2026",
    "コーデックス イベント 2026",
    "植物即売会 まとめ 2026",
]

# Domains to always ignore (generic / social / our own)
IGNORE_DOMAINS = {
    'agave-navi.com',
    'google.com', 'google.co.jp', 'goo.gl',
    'youtube.com', 'youtu.be',
    'twitter.com', 'x.com',
    'instagram.com',
    'facebook.com', 'fb.com',
    'amazon.co.jp', 'amazon.com',
    'mercari.com',
    'yahoo.co.jp', 'auctions.yahoo.co.jp',
    'rakuten.co.jp',
    'pinterest.com', 'pinterest.jp',
    'tiktok.com',
    'note.com',        # too generic
    'ameblo.jp',       # too generic
    'livedoor.jp',
    'fc2.com',
    'wikipedia.org',
    'reddit.com',
    'duckduckgo.com',
    'bing.com',
}


def load_known_domains():
    """Load existing crawl source domains."""
    try:
        with open(SOURCES_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        domains = set()
        for src in data.get('sources', []):
            parsed = urlparse(src['url'])
            # Store with and without www
            d = parsed.netloc.lower().replace('www.', '')
            domains.add(d)
        return domains
    except Exception as e:
        print(f"Warning: Could not load sources: {e}")
        return set()


def get_root_domain(url):
    """Extract root domain from URL, stripping www."""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower().replace('www.', '')
    except Exception:
        return None


def search_ddg(query, max_results=20):
    """
    Search DuckDuckGo HTML version and extract result URLs.
    Uses the lite/html endpoint to avoid JS rendering.
    """
    results = []
    url = 'https://html.duckduckgo.com/html/'
    params = {'q': query, 'kl': 'jp-jp'}

    try:
        resp = requests.post(url, data=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'lxml')

        for link in soup.select('a.result__a'):
            href = link.get('href', '')
            # DDG wraps URLs in redirects — extract actual URL
            if 'uddg=' in href:
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(href).query)
                href = qs.get('uddg', [''])[0]

            if href and href.startswith('http'):
                title = link.get_text(strip=True)
                results.append({'url': href, 'title': title})

            if len(results) >= max_results:
                break

    except Exception as e:
        print(f"  Search error for '{query}': {e}")

    return results


def analyze_page(url):
    """
    Fetch a candidate page and assess its relevance as an event source.
    Returns a dict with analysis results.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or 'utf-8'
        html = resp.text
    except Exception:
        return None

    soup = BeautifulSoup(html, 'lxml')
    text = soup.get_text(separator=' ', strip=True).lower()

    # Score relevance
    score = 0
    signals = []

    # Event keywords
    event_kw = {
        'イベント': 2, '即売会': 3, 'マルシェ': 3, '展示会': 2,
        'フェス': 2, 'バザール': 3, '植物園': 1, 'ワークショップ': 1,
    }
    for kw, pts in event_kw.items():
        count = text.count(kw)
        if count > 0:
            score += min(count, 5) * pts
            signals.append(f"{kw}×{count}")

    # Plant keywords
    plant_kw = {
        'アガベ': 3, '塊根植物': 3, 'コーデックス': 2, '多肉植物': 2,
        'サボテン': 1, 'ビザールプランツ': 3, '珍奇植物': 2,
        'パキポディウム': 2, 'ユーフォルビア': 1, 'チタノタ': 2,
    }
    for kw, pts in plant_kw.items():
        count = text.count(kw)
        if count > 0:
            score += min(count, 5) * pts
            signals.append(f"{kw}×{count}")

    # Date patterns (indicates event listings)
    date_matches = len(re.findall(r'\d{4}[./年]\d{1,2}[./月]\d{1,2}', text))
    if date_matches >= 3:
        score += date_matches * 2
        signals.append(f"日付×{date_matches}")

    # Multiple event names pattern
    event_name_patterns = len(re.findall(
        r'(即売会|マルシェ|フェスタ?|展示会|ボタニカル|プランツ).{0,20}(開催|参加|出店)',
        text
    ))
    if event_name_patterns >= 2:
        score += event_name_patterns * 3
        signals.append(f"イベント告知×{event_name_patterns}")

    # Page type hints
    page_type = 'unknown'
    if any(kw in text for kw in ['イベント一覧', 'イベントカレンダー', 'イベントスケジュール']):
        page_type = 'event-list'
        score += 10
    elif any(kw in text for kw in ['まとめ', '一覧', 'カレンダー']):
        page_type = 'summary'
        score += 5
    elif any(kw in text for kw in ['公式サイト', '主催', '出店者募集']):
        page_type = 'official'
        score += 5
    elif re.search(r'\d{4}年.*イベント', text):
        page_type = 'blog-summary'
        score += 3

    # Meta description
    meta_desc = ''
    meta = soup.find('meta', attrs={'name': 'description'})
    if meta:
        meta_desc = meta.get('content', '')

    # Site title
    title_el = soup.find('title')
    site_title = title_el.get_text(strip=True) if title_el else ''

    return {
        'score': score,
        'signals': signals,
        'page_type': page_type,
        'site_title': site_title,
        'meta_desc': meta_desc[:120],
    }


def main():
    print("=== agave-navi.com Source Discovery ===")
    print(f"Started at: {datetime.now().isoformat()}")

    known_domains = load_known_domains()
    print(f"Known source domains: {len(known_domains)}")
    print(f"Search queries: {len(SEARCH_QUERIES)}")

    # Phase 1: Collect URLs from searches
    all_results = {}  # domain -> {urls, titles, queries}

    for i, query in enumerate(SEARCH_QUERIES):
        print(f"\n[{i+1}/{len(SEARCH_QUERIES)}] Searching: {query}")
        results = search_ddg(query)
        print(f"  Got {len(results)} results")

        for r in results:
            domain = get_root_domain(r['url'])
            if not domain:
                continue
            if domain in IGNORE_DOMAINS:
                continue
            if domain in known_domains:
                continue

            if domain not in all_results:
                all_results[domain] = {
                    'urls': [],
                    'titles': set(),
                    'queries': set(),
                    'hit_count': 0,
                }

            all_results[domain]['urls'].append(r['url'])
            all_results[domain]['titles'].add(r['title'])
            all_results[domain]['queries'].add(query)
            all_results[domain]['hit_count'] += 1

        # Polite delay between searches
        if i < len(SEARCH_QUERIES) - 1:
            time.sleep(3)

    print(f"\n--- Phase 1 complete: {len(all_results)} unique candidate domains ---")

    # Phase 2: Analyze top candidates (sort by hit count)
    candidates = sorted(all_results.items(), key=lambda x: x[1]['hit_count'], reverse=True)
    # Analyze top 20 most-hit domains
    analyzed = []

    for domain, info in candidates[:20]:
        # Pick the most representative URL (first one found)
        url = info['urls'][0]
        print(f"\n  Analyzing: {domain} (hits: {info['hit_count']})")

        analysis = analyze_page(url)
        if analysis and analysis['score'] >= 5:
            analyzed.append({
                'domain': domain,
                'url': url,
                'hit_count': info['hit_count'],
                'queries': list(info['queries']),
                'titles': list(info['titles'])[:3],
                **analysis,
            })
            print(f"    Score: {analysis['score']} | Type: {analysis['page_type']} | {', '.join(analysis['signals'][:5])}")
        elif analysis:
            print(f"    Score too low: {analysis['score']}")
        else:
            print(f"    Could not fetch")

        time.sleep(2)

    # Sort by score
    analyzed.sort(key=lambda x: x['score'], reverse=True)

    print(f"\n--- Phase 2 complete: {len(analyzed)} qualified candidates ---")

    # Phase 3: Generate report
    report = generate_report(analyzed, known_domains, all_results)

    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)

    print(f"\nReport saved to {REPORT_PATH}")
    print("=== Discovery complete ===")


def generate_report(analyzed, known_domains, all_results):
    """Generate markdown report for GitHub Issue."""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    report = f"""## 巡回先 自動発掘レポート
**実行日時**: {now} (UTC)
**検索クエリ数**: {len(SEARCH_QUERIES)}
**発見ドメイン数**: {len(all_results)}（既知 {len(known_domains)} 件を除外済み）
**分析済み候補**: {len(analyzed)} 件

---

"""

    if analyzed:
        report += "### 新規巡回先候補（スコア順）\n\n"
        report += "以下のサイトが新しい巡回先として有望です。確認のうえ `crawl-sources.json` に追加してください。\n\n"

        for i, c in enumerate(analyzed, 1):
            stars = '⭐' * min(c['score'] // 10, 5) if c['score'] >= 10 else ''
            report += f"#### {i}. {c['domain']} {stars}\n\n"
            report += f"- **スコア**: {c['score']} | **タイプ**: {c['page_type']}\n"
            report += f"- **URL**: {c['url']}\n"
            report += f"- **サイトタイトル**: {c['site_title'][:60]}\n"
            if c['meta_desc']:
                report += f"- **説明**: {c['meta_desc']}\n"
            report += f"- **検出キーワード**: {', '.join(c['signals'][:8])}\n"
            report += f"- **ヒットしたクエリ**: {', '.join(c['queries'][:4])}\n"

            # Suggest crawl-sources.json entry
            report += f"\n<details><summary>crawl-sources.json 追加テンプレート</summary>\n\n"
            report += "```json\n"
            report += json.dumps({
                "name": c['site_title'][:40] or c['domain'],
                "url": c['url'],
                "type": c['page_type'],
                "coverage": "未確認",
                "focus": "未確認",
                "frequency": "weekly",
                "notes": f"自動発掘 ({now}). スコア: {c['score']}."
            }, ensure_ascii=False, indent=2)
            report += "\n```\n</details>\n\n"

    else:
        report += "### 結果\n\n新しい巡回先候補は見つかりませんでした。\n\n"

    # Also list domains that were found but didn't pass analysis threshold
    low_score = [d for d in all_results if d not in {c['domain'] for c in analyzed}]
    if low_score:
        report += "<details><summary>スコア不足 / 未分析のドメイン一覧</summary>\n\n"
        for d in sorted(low_score):
            report += f"- `{d}` (ヒット数: {all_results[d]['hit_count']})\n"
        report += "\n</details>\n\n"

    report += "---\n"
    report += "*このレポートは GitHub Actions による自動発掘で生成されました。*\n"
    report += "*検索クエリの追加・変更は `scripts/discover_sources.py` の `SEARCH_QUERIES` を編集してください。*\n"

    return report


if __name__ == '__main__':
    main()
