#!/usr/bin/env python3
"""
Event Information Enrichment Script for agave-navi.com

Searches for official event pages via Google, extracts OGP metadata,
event details (dates, venue, admission, organizer), and generates
a structured report for manual review and update.

Usage:
  python scripts/enrich_events.py                    # Check all events
  python scripts/enrich_events.py --slug <slug>      # Check specific event
  python scripts/enrich_events.py --missing-only      # Only events missing info

Output: /tmp/enrich-report.md (Markdown report for GitHub Issue)
        /tmp/enrich-data.json (Machine-readable enrichment data)
"""

import json
import os
import re
import sys
import time
import argparse
from datetime import datetime
from urllib.parse import urljoin, urlparse, quote_plus

import requests
from bs4 import BeautifulSoup

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
EVENTS_PATH = os.path.join(REPO_ROOT, 'events.json')
EVENTS_DIR = os.path.join(REPO_ROOT, 'events')
REPORT_PATH = '/tmp/enrich-report.md'
DATA_PATH = '/tmp/enrich-data.json'

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                   '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ja,en;q=0.5',
}

# Domains to skip (SNS, generic platforms - won't have good OGP for our purposes)
SKIP_DOMAINS = {'instagram.com', 'twitter.com', 'x.com', 'facebook.com',
                'tiktok.com', 'youtube.com', 'line.me'}

# Preferred domains (official event sites, venues)
PREFERRED_DOMAINS = {
    'sunshinecity.jp', 'makuhari-messe.com', 'tokyo-dome.co.jp',
    'nagashima-onsen.co.jp', 'greensnap.jp', 'peatix.com',
    'teket.jp', 'passmarket.yahoo.co.jp',
}


def load_events():
    """Load events from events.json"""
    with open(EVENTS_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def check_detail_page(slug):
    """Check current state of event detail page"""
    fpath = os.path.join(EVENTS_DIR, f'{slug}.html')
    if not os.path.exists(fpath):
        return {'exists': False}

    with open(fpath, 'r', encoding='utf-8') as f:
        html = f.read()

    return {
        'exists': True,
        'has_generic_desc': 'このイベントは植物愛好家にとって重要な機会' in html,
        'has_template_text': '詳細な日程や出店者情報は、直接主催者にお問い合わせ' in html,
        'has_ogp_image': ('og:image' in html and 'default.jpg' not in html),
        'has_real_venue': '県' not in html.split('info-value')[1].split('</span>')[0]
                          if 'info-value' in html else False,
    }


def _filter_url(url):
    """Check if a URL should be skipped (SNS, self-domain)"""
    domain = urlparse(url).netloc.lower()
    if any(skip in domain for skip in SKIP_DOMAINS):
        return False
    if 'agave-navi.com' in domain:
        return False
    return True


def _search_duckduckgo(query, num_results=5):
    """Search using DuckDuckGo HTML version (no JS required, bot-friendly)"""
    encoded_query = quote_plus(query)
    url = f'https://html.duckduckgo.com/html/?q={encoded_query}'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        for result in soup.find_all('div', class_='result'):
            link = result.find('a', class_='result__a', href=True)
            if not link:
                continue

            href = link['href']
            # DuckDuckGo sometimes uses redirect URLs
            if '//duckduckgo.com/l/' in href:
                from urllib.parse import parse_qs
                parsed = urlparse(href)
                qs = parse_qs(parsed.query)
                if 'uddg' in qs:
                    href = qs['uddg'][0]

            if not href.startswith('http'):
                continue

            if not _filter_url(href):
                continue

            title = link.get_text(strip=True)
            snippet_el = result.find('a', class_='result__snippet')
            snippet = snippet_el.get_text(strip=True) if snippet_el else ''
            results.append({
                'url': href,
                'title': title,
                'snippet': snippet,
            })

        print(f"    DuckDuckGo results: {len(results)}")
        return results[:num_results]
    except Exception as e:
        print(f"    DuckDuckGo error: {e}")
        return []


def _search_bing(query, num_results=5):
    """Fallback: Search using Bing"""
    encoded_query = quote_plus(query)
    url = f'https://www.bing.com/search?q={encoded_query}&setlang=ja'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        for li in soup.find_all('li', class_='b_algo'):
            link = li.find('a', href=True)
            if not link or not link['href'].startswith('http'):
                continue
            if not _filter_url(link['href']):
                continue
            title = link.get_text(strip=True)
            snippet_el = li.find('p')
            snippet = snippet_el.get_text(strip=True) if snippet_el else ''
            results.append({
                'url': link['href'],
                'title': title,
                'snippet': snippet,
            })

        print(f"    Bing results: {len(results)}")
        return results[:num_results]
    except Exception as e:
        print(f"    Bing error: {e}")
        return []


def _search_google(query, num_results=5):
    """Search using Google (may be blocked from server IPs)"""
    encoded_query = quote_plus(query)
    url = f'https://www.google.com/search?q={encoded_query}&hl=ja&num={num_results}'

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        for g in soup.find_all('div', class_='g'):
            link = g.find('a', href=True)
            if link and link['href'].startswith('http') and _filter_url(link['href']):
                title = g.find('h3')
                title_text = title.get_text(strip=True) if title else ''
                results.append({
                    'url': link['href'],
                    'title': title_text,
                    'snippet': '',
                })

        # Fallback: /url?q= links
        if not results:
            for a in soup.find_all('a', href=True):
                href = a['href']
                if href.startswith('/url?q='):
                    actual_url = href.split('/url?q=')[1].split('&')[0]
                    if actual_url.startswith('http') and _filter_url(actual_url):
                        results.append({
                            'url': actual_url,
                            'title': a.get_text(strip=True),
                            'snippet': '',
                        })

        print(f"    Google results: {len(results)}")
        return results[:num_results]
    except Exception as e:
        print(f"    Google error: {e}")
        return []


def web_search(query, num_results=5):
    """
    Multi-engine search: tries DuckDuckGo first, then Bing, then Google.
    Returns top results from the first engine that succeeds.
    """
    print(f"    Trying DuckDuckGo...")
    results = _search_duckduckgo(query, num_results)
    if results:
        for i, r in enumerate(results[:3]):
            print(f"      [{i}] {r['url'][:80]}")
        return results

    print(f"    Trying Bing...")
    time.sleep(1)
    results = _search_bing(query, num_results)
    if results:
        for i, r in enumerate(results[:3]):
            print(f"      [{i}] {r['url'][:80]}")
        return results

    print(f"    Trying Google...")
    time.sleep(1)
    results = _search_google(query, num_results)
    if results:
        for i, r in enumerate(results[:3]):
            print(f"      [{i}] {r['url'][:80]}")
        return results

    print(f"    All search engines returned 0 results")
    return []


def select_best_url(results, event_name):
    """Select the most relevant official URL from search results"""
    if not results:
        return None

    # Filter out agave-navi.com itself and SNS domains
    filtered = []
    for r in results:
        domain = urlparse(r['url']).netloc.lower()
        if 'agave-navi.com' in domain:
            continue
        if any(skip in domain for skip in SKIP_DOMAINS):
            continue
        filtered.append(r)

    if not filtered:
        return None

    # Prefer results from known venue/ticketing domains
    for r in filtered:
        domain = urlparse(r['url']).netloc.lower()
        if any(pref in domain for pref in PREFERRED_DOMAINS):
            return r['url']

    # Prefer results whose title closely matches the event name
    for r in filtered:
        title_lower = r['title'].lower()
        name_parts = event_name.lower().split()
        matches = sum(1 for p in name_parts if p in title_lower)
        if matches >= len(name_parts) * 0.6:
            return r['url']

    # Return first non-SNS result
    return filtered[0]['url'] if filtered else None


def extract_page_info(url):
    """Extract comprehensive event info from a web page"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        return {'error': str(e)}

    info = {'url': url}

    # --- OGP Metadata ---
    for meta_name, key in [
        ('og:image', 'ogp_image'),
        ('og:title', 'ogp_title'),
        ('og:description', 'ogp_description'),
        ('og:site_name', 'ogp_site_name'),
    ]:
        el = soup.find('meta', property=meta_name) or soup.find('meta', attrs={'name': meta_name})
        if el and el.get('content'):
            content = el['content']
            # Make relative URLs absolute
            if key == 'ogp_image' and not content.startswith('http'):
                content = urljoin(url, content)
            info[key] = content

    # Twitter image as fallback
    if 'ogp_image' not in info:
        tw = soup.find('meta', attrs={'name': 'twitter:image'})
        if tw and tw.get('content'):
            img = tw['content']
            if not img.startswith('http'):
                img = urljoin(url, img)
            info['ogp_image'] = img

    # --- Page text for analysis ---
    text = soup.get_text(separator='\n', strip=True)
    info['page_text_preview'] = text[:3000]  # First 3000 chars for analysis

    # --- Date extraction ---
    date_patterns = [
        r'(\d{4})[./年](\d{1,2})[./月](\d{1,2})[日]?\s*[（(]?[月火水木金土日][）)]?\s*[～〜~ー−-]\s*(\d{4})?[./年]?(\d{1,2})[./月](\d{1,2})',
        r'(\d{4})[./年](\d{1,2})[./月](\d{1,2})',
    ]
    dates_found = []
    for pat in date_patterns:
        for m in re.finditer(pat, text):
            dates_found.append(m.group())
    if dates_found:
        info['dates_found'] = dates_found[:5]

    # --- Time extraction ---
    time_pattern = r'(\d{1,2})[：:](\d{2})\s*[～〜~ー−-]\s*(\d{1,2})[：:](\d{2})'
    times = re.findall(time_pattern, text)
    if times:
        info['times_found'] = [f"{t[0]}:{t[1]}〜{t[2]}:{t[3]}" for t in times[:3]]

    # --- Admission/Price extraction ---
    price_patterns = [
        r'(入場[料金]?\s*[：:]\s*[^\n]{3,50})',
        r'(一般\s*[：:]?\s*[\d,]+円)',
        r'(前売[りり]?\s*[：:]?\s*[\d,]+円)',
        r'(入場無料)',
        r'([\d,]+円\s*[（(].*?[）)])',
    ]
    prices = []
    for pat in price_patterns:
        for m in re.finditer(pat, text):
            prices.append(m.group().strip())
    if prices:
        info['prices_found'] = list(set(prices))[:5]

    # --- Venue extraction ---
    venue_patterns = [
        r'(会場|開催場所|場所)\s*[：:]\s*([^\n]{3,80})',
        r'(〒\d{3}-\d{4}[^\n]{5,50})',
    ]
    venues = []
    for pat in venue_patterns:
        for m in re.finditer(pat, text):
            venues.append(m.group().strip())
    if venues:
        info['venues_found'] = venues[:3]

    # --- Organizer extraction ---
    org_patterns = [
        r'(主催|運営)\s*[：:]\s*([^\n]{2,50})',
    ]
    orgs = []
    for pat in org_patterns:
        for m in re.finditer(pat, text):
            orgs.append(m.group().strip())
    if orgs:
        info['organizers_found'] = orgs[:2]

    return info


def process_event(event, force=False):
    """Process a single event: search, extract, return enrichment data"""
    slug = event['slug']
    name = event['name']
    source_url = event.get('sourceUrl', '')

    print(f"\n--- {name} ({slug}) ---")

    # Check current state
    page_state = check_detail_page(slug)
    needs_update = (
        page_state.get('has_generic_desc', False) or
        page_state.get('has_template_text', False) or
        not page_state.get('has_ogp_image', False)
    )

    if not needs_update and not force:
        print(f"  → Already has good content, skipping")
        return None

    result = {
        'slug': slug,
        'name': name,
        'current_source_url': source_url,
        'page_state': page_state,
        'search_results': [],
        'best_url': None,
        'extracted_info': None,
    }

    # Step 1: Search for the event across multiple engines
    search_query = f'{name} 2026 植物 イベント'
    print(f"  Searching: {search_query}")
    search_results = web_search(search_query)
    result['search_results'] = search_results

    # Step 2: Select best URL
    # sourceUrlがSNSの場合はGoogle検索結果を優先
    source_is_sns = False
    if source_url:
        source_domain = urlparse(source_url).netloc.lower()
        source_is_sns = any(skip in source_domain for skip in SKIP_DOMAINS)

    if source_url and not source_is_sns:
        best_url = source_url
    else:
        best_url = select_best_url(search_results, name)
        if not best_url and source_url:
            # SNSでも見つからない場合は元のURLをフォールバック
            best_url = source_url
    result['best_url'] = best_url

    if not best_url:
        print(f"  → No suitable URL found")
        return result

    print(f"  Best URL: {best_url}")

    # Step 3: Extract info from the page
    print(f"  Extracting info...")
    info = extract_page_info(best_url)
    result['extracted_info'] = info

    if info.get('ogp_image'):
        print(f"  → OGP image: {info['ogp_image'][:80]}...")
    if info.get('venues_found'):
        print(f"  → Venue: {info['venues_found'][0][:50]}")
    if info.get('prices_found'):
        print(f"  → Price: {info['prices_found'][0][:50]}")

    # If source_url was empty but we found a good URL, also try that
    if source_url and best_url != source_url:
        print(f"  Also checking source URL: {source_url}")
        source_info = extract_page_info(source_url)
        # Merge: prefer source_url for text, search result for image
        if source_info.get('ogp_image') and not info.get('ogp_image'):
            info['ogp_image'] = source_info['ogp_image']
        if source_info.get('venues_found') and not info.get('venues_found'):
            info['venues_found'] = source_info['venues_found']
        result['extracted_info'] = info

    # Rate limiting
    time.sleep(2)

    return result


def generate_report(results):
    """Generate markdown report from enrichment results"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    found = [r for r in results if r and r.get('extracted_info')]
    not_found = [r for r in results if r and not r.get('extracted_info')]
    skipped = len([r for r in results if r is None])

    report = f"""## イベント情報エンリッチメントレポート
**実行日時**: {now} (UTC)
**対象**: {len(results) + skipped}件中 {len(found)}件で情報取得成功 / {len(not_found)}件未発見 / {skipped}件スキップ

"""

    if found:
        report += "### 情報取得成功\n\n"
        for r in found:
            info = r['extracted_info']
            report += f"#### {r['name']} (`{r['slug']}`)\n"
            report += f"- **公式URL**: {r['best_url']}\n"

            if info.get('ogp_image'):
                report += f"- **サムネイル**: `{info['ogp_image'][:100]}`\n"
            else:
                report += f"- **サムネイル**: ❌ 取得できず\n"

            if info.get('venues_found'):
                report += f"- **会場**: {info['venues_found'][0]}\n"
            if info.get('dates_found'):
                report += f"- **日程**: {', '.join(info['dates_found'][:2])}\n"
            if info.get('times_found'):
                report += f"- **時間**: {', '.join(info['times_found'][:2])}\n"
            if info.get('prices_found'):
                report += f"- **入場料**: {', '.join(info['prices_found'][:3])}\n"
            if info.get('organizers_found'):
                report += f"- **主催**: {info['organizers_found'][0]}\n"

            state = r['page_state']
            issues = []
            if state.get('has_generic_desc'):
                issues.append("テンプレ概要文")
            if not state.get('has_ogp_image'):
                issues.append("OGP画像なし")
            if issues:
                report += f"- **現在の問題**: {', '.join(issues)}\n"
            report += "\n"

    if not_found:
        report += "### 情報未発見\n\n"
        for r in not_found:
            report += f"- **{r['name']}** (`{r['slug']}`): "
            if r.get('search_results'):
                report += f"検索結果あるが適切なURL見つからず\n"
            else:
                report += f"検索結果なし\n"
        report += "\n"

    report += "\n---\n*このレポートは自動エンリッチメントスクリプトで生成されました。*\n"
    report += "*情報の正確性を確認の上、手動でイベント詳細ページを更新してください。*\n"
    return report


def main():
    parser = argparse.ArgumentParser(description='Enrich event information')
    parser.add_argument('--slug', help='Process specific event by slug')
    parser.add_argument('--missing-only', action='store_true',
                        help='Only process events with missing info')
    parser.add_argument('--force', action='store_true',
                        help='Force re-check even if info exists')
    parser.add_argument('--limit', type=int, default=0,
                        help='Limit number of events to process (0=all)')
    args = parser.parse_args()

    print("=== agave-navi.com Event Enrichment ===")
    print(f"Started at: {datetime.now().isoformat()}")

    events = load_events()
    print(f"Total events: {len(events)}")

    # Filter events
    if args.slug:
        events = [e for e in events if e['slug'] == args.slug]
        if not events:
            print(f"Event not found: {args.slug}")
            sys.exit(1)

    # Process events
    results = []
    count = 0
    for event in events:
        result = process_event(event, force=args.force)
        results.append(result)
        count += 1
        if args.limit and count >= args.limit:
            break

    # Generate report
    report = generate_report(results)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to {REPORT_PATH}")

    # Save machine-readable data
    serializable = [r for r in results if r is not None]
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"Data saved to {DATA_PATH}")

    # Summary
    found = len([r for r in results if r and isinstance(r.get('extracted_info'), dict) and r['extracted_info'].get('ogp_image')])
    print(f"\n=== Summary: {found} events with OGP images found ===")


if __name__ == '__main__':
    main()
