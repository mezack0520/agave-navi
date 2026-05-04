#!/usr/bin/env python3
"""
Event Information Enrichment Script for agave-navi.com

Strategy:
1. Events with official (non-SNS) sourceUrl → extract OGP/details directly
2. Events with SNS-only sourceUrl → try web search, report for manual review
3. Generate actionable report with Google search links for manual research

Usage:
  python scripts/enrich_events.py                    # Check all events
  python scripts/enrich_events.py --slug <slug>      # Check specific event
  python scripts/enrich_events.py --limit 10         # Limit to 10 events

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

# Domains to skip (SNS, generic platforms)
SKIP_DOMAINS = {'instagram.com', 'twitter.com', 'x.com', 'facebook.com',
                'tiktok.com', 'youtube.com', 'line.me'}

# --- Image quality validation ---
_BAD_IMAGE_DOMAINS = {
    'nextmeet.app',           # generic OGP API
    'botanical-zone.tokyo',   # aggregator
    'leaf-laboratory.com',    # plants news/blog aggregator
    'tochinavi.net',          # regional events aggregator
    'pukubook.jp',            # plant directory
    'fukuoka-now.com',        # general info site
    'churatoku.net',          # coupon aggregator
}
_GENERIC_IMG_RE = re.compile(
    r'/(ogp|og_image|og-image|default|logo|share|thumb|main)\.(png|jpg|jpeg|webp|gif)(\?|$)',
    re.I
)

def is_quality_image_url(img_url):
    """Return False if the image URL looks like a sitewide-generic OGP or comes
    from a known aggregator/news domain. Used to gate write-back."""
    if not img_url:
        return False
    m = re.match(r'https?://([^/]+)', img_url)
    if m and any(d in m.group(1).lower() for d in _BAD_IMAGE_DOMAINS):
        return False
    if _GENERIC_IMG_RE.search(img_url):
        return False
    return True



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

    info_value_parts = html.split('info-value')
    has_real_venue = False
    if len(info_value_parts) > 1:
        venue_section = info_value_parts[1].split('</span>')[0]
        # 「東京県」のような架空の地名が含まれていないか
        has_real_venue = '県' not in venue_section

    return {
        'exists': True,
        'has_generic_desc': 'このイベントは植物愛好家にとって重要な機会' in html,
        'has_template_text': '詳細な日程や出店者情報は、直接主催者にお問い合わせ' in html,
        'has_ogp_image': ('og:image' in html and 'default.jpg' not in html),
        'has_real_venue': has_real_venue,
    }


def is_sns_url(url):
    """Check if URL is from a social media domain"""
    if not url:
        return False
    domain = urlparse(url).netloc.lower()
    return any(skip in domain for skip in SKIP_DOMAINS)


def extract_page_info(url):
    """Extract comprehensive event info from a web page"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
    except Exception as e:
        print(f"    Extract error: {e}")
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

    # --- Access extraction ---
    access_patterns = [
        r'(アクセス|交通)\s*[：:]\s*([^\n]{10,200})',
        r'((?:JR|地下鉄|私鉄|東京メトロ|都営|京急|京王|小田急|東急|東武|西武|京成)[^\n]{5,80}徒歩\d+[分秒])',
        r'(最寄駅?\s*[：:]?\s*[^\n]{5,80})',
    ]
    access_lines = []
    for pat in access_patterns:
        for m in re.finditer(pat, text):
            line = m.group().strip().replace('\n', ' ')
            if 5 < len(line) < 250:
                access_lines.append(line)
    if access_lines:
        # dedupe preserve order
        seen = set(); uniq = []
        for line in access_lines:
            if line not in seen:
                seen.add(line); uniq.append(line)
        info['access_found'] = uniq[:3]


    # --- Exhibitor count hint ---
    m = re.search(r'(?:出店者?数?|出展者?数?|参加[店者]+数?)\s*[：:]?\s*(?:約\s*)?(\d{2,3})', text)
    if m:
        info['exhibitor_count'] = int(m.group(1))

    # --- Long description: prefer first substantial paragraph ---
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if 80 <= len(p.strip()) <= 400]
    if paragraphs:
        info['long_description'] = paragraphs[0]


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


def try_web_search(query, num_results=5):
    """
    Search backends in priority order:
      1. Brave Search API (BRAVE_API_KEY)         — primary (Google CSE deprecated 2026)
      2. Google Custom Search API (GOOGLE_API_KEY + GOOGLE_CSE_ID) — kept for compat
      3. DuckDuckGo HTML scraping                 — last-resort fallback
    """
    def _filter_url(url):
        domain = urlparse(url).netloc.lower()
        if any(skip in domain for skip in SKIP_DOMAINS):
            return False
        if 'agave-navi.com' in domain:
            return False
        return True

    # Primary: Brave Search API
    brave_key = os.environ.get('BRAVE_API_KEY', '')
    if brave_key:
        try:
            params = {
                'q': query,
                'count': min(num_results, 20),
                'country': 'JP',
                'search_lang': 'jp',
            }
            headers = {
                'Accept': 'application/json',
                'X-Subscription-Token': brave_key,
            }
            resp = requests.get(
                'https://api.search.brave.com/res/v1/web/search',
                params=params, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                items = (data.get('web') or {}).get('results', []) or []
                results = []
                for item in items:
                    url = item.get('url', '')
                    if url and _filter_url(url):
                        results.append({'url': url, 'title': item.get('title', '')})
                if results:
                    print(f"    Brave: {len(results)} results for '{query[:40]}'")
                    return results[:num_results]
                else:
                    print(f"    Brave: 0 results after filtering")
            else:
                print(f"    Brave error: HTTP {resp.status_code}: {resp.text[:120]}")
        except Exception as e:
            print(f"    Brave error: {e}")

    # Fallback 1: Google Custom Search API
    api_key = os.environ.get('GOOGLE_API_KEY', '')
    cse_id = os.environ.get('GOOGLE_CSE_ID', '')

    if api_key and cse_id:
        try:
            params = {
                'key': api_key,
                'cx': cse_id,
                'q': query,
                'num': min(num_results, 10),
                'lr': 'lang_ja',
                'gl': 'jp',
            }
            resp = requests.get(
                'https://www.googleapis.com/customsearch/v1',
                params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            results = []
            for item in data.get('items', []):
                url = item.get('link', '')
                if url and _filter_url(url):
                    results.append({
                        'url': url,
                        'title': item.get('title', ''),
                    })
            if results:
                print(f"    Google CSE: {len(results)} results for '{query[:40]}'")
                return results[:num_results]
            else:
                print(f"    Google CSE: 0 results after filtering")
                return []
        except Exception as e:
            print(f"    Google CSE error: {e}")

    # Fallback 2: DuckDuckGo HTML scraping (last resort)
    try:
        encoded = quote_plus(query)
        resp = requests.get(
            f'https://html.duckduckgo.com/html/?q={encoded}',
            headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        results = []
        for div in soup.find_all('div', class_='result'):
            link = div.find('a', class_='result__a', href=True)
            if not link:
                continue
            href = link['href']
            if '//duckduckgo.com/l/' in href:
                from urllib.parse import parse_qs
                qs = parse_qs(urlparse(href).query)
                if 'uddg' in qs:
                    href = qs['uddg'][0]
            if _filter_url(href):
                results.append({
                    'url': href,
                    'title': link.get_text(strip=True),
                })
        if results:
            print(f"    DuckDuckGo fallback: {len(results)} results")
            return results[:num_results]
    except Exception as e:
        print(f"    DuckDuckGo fallback error: {e}")

    return []

def _is_relevant_result(result, event_name):
    """Check if a search result is actually relevant to the event"""
    import re as _re
    title = (result.get('title', '') or '').lower()
    url = (result.get('url', '') or '').lower()
    combined = title + ' ' + url

    # Tokenize event name by spaces and common delimiters
    tokens = _re.split(r'[\s\u3000\u30FB\u2606\u2605\xd7\-]+', event_name)
    # Keep meaningful tokens (2+ chars)
    tokens = [t.lower() for t in tokens if len(t) >= 2]

    if not tokens:
        return True

    # At least one significant token must appear in title or URL
    for token in tokens:
        if token in combined:
            return True

    # Also reject if URL domain is clearly non-Japanese / non-event
    domain = urlparse(url).netloc.lower()
    reject_tlds = ['.mx', '.com.br', '.com.ar']
    for tld in reject_tlds:
        if domain.endswith(tld):
            return False

    return False


def _build_search_query(event):
    """Build an optimized search query using event metadata"""
    name = event['name']
    parts = [name]

    # Add location/venue for context
    location = event.get('location', '')
    if location:
        parts.append(location)

    # Add prefecture if no specific location
    if not location:
        prefecture = event.get('prefecture', '')
        if prefecture:
            parts.append(prefecture)

    # Add organizer if available
    organizer = event.get('organizer', '')
    if organizer and not organizer.startswith('@'):
        parts.append(organizer)

    # Add year for relevance
    date = event.get('date', '')
    if date:
        year = date[:4]
        if year not in name:
            parts.append(year)

    parts.append('イベント')
    return ' '.join(parts)


def process_event(event, force=False):
    """Process a single event and return enrichment data"""
    slug = event['slug']
    name = event['name']
    source_url = event.get('sourceUrl', '')

    print(f"\n--- {name} ({slug}) ---")

    # Check current state of detail page
    page_state = check_detail_page(slug)
    needs_update = (
        page_state.get('has_generic_desc', False) or
        page_state.get('has_template_text', False) or
        not page_state.get('has_ogp_image', False)
    )

    if not needs_update and not force:
        print(f"  → Already enriched, skipping")
        return None

    result = {
        'slug': slug,
        'name': name,
        'current_source_url': source_url,
        'page_state': page_state,
        'category': 'unknown',  # 'enriched', 'needs_manual', 'no_source'
        'best_url': None,
        'extracted_info': None,
        'search_link': f"https://www.google.com/search?q={quote_plus(name + ' イベント 公式')}",
    }

    source_sns = is_sns_url(source_url)

    # === Category A: Has official (non-SNS) source URL ===
    if source_url and not source_sns:
        print(f"  Official source: {source_url}")
        result['best_url'] = source_url
        info = extract_page_info(source_url)
        result['extracted_info'] = info
        result['category'] = 'enriched' if not info.get('error') else 'extract_failed'

        if info.get('ogp_image'):
            print(f"  ✓ OGP image found")
        if info.get('venues_found'):
            print(f"  ✓ Venue: {info['venues_found'][0][:50]}")

    # === Category B: SNS-only source → try search, else SNS OGP fallback ===
    elif source_url and source_sns:
        print(f"  SNS source: {source_url} → trying web search...")
        # Build a richer search query using event metadata
        search_query = _build_search_query(event)
        search_results = try_web_search(search_query)

        # Filter for relevance
        if search_results:
            search_results = [r for r in search_results if _is_relevant_result(r, name)]
            if not search_results:
                print(f"    All results filtered as irrelevant")

        # If first query fails, try a simpler variant
        if not search_results:
            alt_query = f'{name} 公式'
            print(f"    Retrying with: {alt_query}")
            search_results = try_web_search(alt_query)
            if search_results:
                search_results = [r for r in search_results if _is_relevant_result(r, name)]

        if search_results:
            best = search_results[0]
            result['best_url'] = best['url']
            print(f"  Found: {best['url'][:80]}")
            info = extract_page_info(best['url'])
            result['extracted_info'] = info
            result['category'] = 'enriched'
        else:
            # Fallback: try to get OGP from the SNS URL itself
            print(f"  Trying OGP from SNS source: {source_url}")
            info = extract_page_info(source_url)
            if info and not info.get('error') and (info.get('ogp_image') or info.get('ogp_title')):
                result['best_url'] = source_url
                result['extracted_info'] = info
                result['category'] = 'enriched'
                print(f"  ✓ Got info from SNS source")
            else:
                result['category'] = 'needs_manual'
                result['best_url'] = source_url
                print(f"  → Needs manual research")

    # === Category C: No source URL at all ===
    else:
        print(f"  No source URL → trying web search...")
        search_query = _build_search_query(event)
        search_results = try_web_search(search_query)

        # Filter for relevance
        if search_results:
            search_results = [r for r in search_results if _is_relevant_result(r, name)]
            if not search_results:
                print(f"    All results filtered as irrelevant")

        if search_results:
            best = search_results[0]
            result['best_url'] = best['url']
            info = extract_page_info(best['url'])
            result['extracted_info'] = info
            result['category'] = 'enriched'
        else:
            result['category'] = 'needs_manual'
            print(f"  → Needs manual research")

    time.sleep(1)
    return result


def generate_report(results, removed_names=None):
    """Generate actionable markdown report"""
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    removed_names = removed_names or []

    enriched = [r for r in results if r and r.get('category') == 'enriched']
    needs_manual = [r for r in results if r and r.get('category') == 'needs_manual']
    no_source = [r for r in results if r and r.get('category') == 'no_source']
    skipped = len([r for r in results if r is None])
    total = len(results) + skipped

    report = f"""## イベント情報エンリッチメントレポート
**実行日時**: {now} (UTC)
**対象**: {total}件中 ✅{len(enriched)}件自動取得 / 🗑️{len(needs_manual)}件削除 / ⏭️{skipped}件スキップ

"""

    # === Section 1: Successfully enriched ===
    if enriched:
        report += "### ✅ 情報自動取得成功\n\n"
        for r in enriched:
            info = r.get('extracted_info', {})
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
                report += f"- **要修正**: {', '.join(issues)}\n"
            report += "\n"

    # === Section 2: Removed events ===
    if removed_names:
        report += "### 🗑️ 削除済み（公式情報なし）\n\n"
        report += "以下のイベントは公式サイトが見つからなかったため、`events.json` と詳細ページを削除しました。\n\n"
        for name in removed_names:
            report += f"- {name}\n"
        report += "\n"
        report += "※ 復元する場合は、公式サイトURLを見つけた上でイベントを再登録してください。\n\n"

    report += "\n---\n"
    report += "*このレポートは自動エンリッチメントスクリプトで生成されました。*\n"
    report += "*✅の情報は自動抽出のため、正確性を確認の上で更新してください。*\n"
    return report


def main():
    parser = argparse.ArgumentParser(description='Enrich event information')
    parser.add_argument('--write-back', action='store_true',
        help='Write discovered imageUrl/url back to events.json (for empty fields only)')
    parser.add_argument('--no-remove', action='store_true',
        help='Do not remove events that have no findings (default: remove them)')
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

    if args.slug:
        events = [e for e in events if e['slug'] == args.slug]
        if not events:
            print(f"Event not found: {args.slug}")
            sys.exit(1)

    results = []
    count = 0
    for event in events:
        result = process_event(event, force=args.force)
        results.append(result)
        count += 1
        if args.limit and count >= args.limit:
            break

    # === Remove events with no official info ===
    needs_manual_slugs = {r['slug'] for r in results
                          if r and r.get('category') == 'needs_manual'}


    # === Write-back: populate fields from enrichment to events.json ===
    # Only upcoming events get write-back (per user preference).
    if args.write_back:
        all_events = load_events()
        slug_to_result = {r['slug']: r for r in results if r}
        write_count = 0
        for ev in all_events:
            if ev.get('status') != 'upcoming':
                continue
            r = slug_to_result.get(ev.get('slug'))
            if not r or r.get('category') != 'enriched':
                continue
            info = r.get('extracted_info') or {}
            best_url = r.get('best_url')
            changed_fields = []

            # url (only if empty)
            if best_url and not ev.get('url'):
                ev['url'] = best_url
                changed_fields.append('url')

            # imageUrl (only if empty, with HEAD verification)
            ogp_image = info.get('ogp_image')
            if ogp_image and not ev.get('imageUrl'):
                if not is_quality_image_url(ogp_image):
                    print(f"    IMG-REJECTED for {ev['slug']}: aggregator/generic — {ogp_image[:70]}")
                else:
                    try:
                        h = requests.head(ogp_image, headers=HEADERS, timeout=8, allow_redirects=True)
                        if h.status_code < 400:
                            ev['imageUrl'] = ogp_image
                            changed_fields.append('imageUrl')
                    except requests.RequestException:
                        pass

            # description: replace ONLY if extracted is meaningfully richer AND
            # passes quality checks (event relevance + boilerplate rejection).
            ogp_desc = (info.get('ogp_description') or '').strip()
            long_desc = (info.get('long_description') or '').strip()
            candidate_desc = ogp_desc if len(ogp_desc) >= len(long_desc) else long_desc
            cur_desc = (ev.get('description') or '').strip()

            def _quality_ok(cand, ev_name, ev_venue):
                if not cand or len(cand) < 120:
                    return False, 'too short'
                # Reject aggregator/boilerplate phrases
                blocklist = [
                    'イベント情報をまとめ', '次回のイベント', '関連するタグ',
                    '実際の情報が変更', '各リンクよりご確認', '記事は執筆時の情報',
                    '当サイトでは', '公開：', 'クッキーを使用',
                ]
                for bad in blocklist:
                    if bad in cand:
                        return False, f'boilerplate: {bad}'
                # Must be predominantly Japanese (>=40% non-ASCII)
                non_ascii = sum(1 for c in cand if ord(c) > 127)
                if non_ascii / max(len(cand), 1) < 0.4:
                    return False, 'mostly ASCII (probably wrong language)'
                # Must overlap with event name OR venue (>=2 char substring of name)
                # to ensure it's about THIS event, not a generic site description.
                name_clean = re.sub(r'\s+', '', ev_name).lower()
                venue_clean = re.sub(r'\s+', '', (ev_venue or '')).lower()
                cand_clean = cand.lower()
                # Pick a few representative tokens from the name
                # (skip generic words like "vol", numbers, year)
                tokens = re.findall(r'[\u3040-\u30ff\u3400-\u9fffA-Za-z]{2,}', ev_name)
                tokens = [tk for tk in tokens if not re.match(r'^(vol|the|in|of|and|2026|2025)$', tk, re.I) and len(tk) >= 2]
                if not any(tk.lower() in cand_clean for tk in tokens) and (
                        not venue_clean or venue_clean[:4] not in cand_clean):
                    return False, 'no name/venue overlap'
                return True, None

            ok, reason = _quality_ok(candidate_desc, ev.get('name',''), ev.get('venue',''))
            if (ok and candidate_desc != cur_desc
                    and (len(cur_desc) < 80 or len(candidate_desc) >= int(len(cur_desc) * 1.2))):
                ev['description'] = candidate_desc[:500]
                changed_fields.append('description')
            elif not ok and len(cur_desc) < 80:
                # Log skipped but don't write
                print(f"    DESC-REJECTED for {ev['slug']}: {reason}")

            # time (only if empty)
            times_found = info.get('times_found') or []
            if times_found and not ev.get('time'):
                ev['time'] = times_found[0]
                changed_fields.append('time')

            # admission (only if empty)
            prices = info.get('prices_found') or []
            if prices and not ev.get('admission'):
                # pick the shortest non-trivial entry as the headline price
                pick = sorted(prices, key=lambda s: (len(s) > 60, len(s)))[0]
                if pick:
                    ev['admission'] = pick[:80]
                    changed_fields.append('admission')

            # access (new field, only if empty)
            access_lines = info.get('access_found') or []
            if access_lines and not ev.get('access'):
                ev['access'] = ' / '.join(access_lines)[:300]
                changed_fields.append('access')

            if changed_fields:
                write_count += 1
                print(f"  WRITE-BACK: {ev['slug']} ← {', '.join(changed_fields)}")

        if write_count:
            with open(EVENTS_PATH, 'w', encoding='utf-8') as f:
                json.dump(all_events, f, ensure_ascii=False, indent=2)
                f.write('\n')
            print(f"  events.json: write-back {write_count} event(s)")
        else:
            print('  No new fields to write back.')

    if needs_manual_slugs and not args.no_remove:
        print(f"\n=== Removing {len(needs_manual_slugs)} events with no official info ===")
        original_count = len(events)

        # Reload full events list to include ones we didn't process
        all_events = load_events()
        filtered_events = [e for e in all_events if e['slug'] not in needs_manual_slugs]

        # Save updated events.json
        with open(EVENTS_PATH, 'w', encoding='utf-8') as f:
            json.dump(filtered_events, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f"  events.json: {original_count} → {len(filtered_events)} events")

        # Remove corresponding detail pages
        for slug in needs_manual_slugs:
            html_path = os.path.join(EVENTS_DIR, f'{slug}.html')
            if os.path.exists(html_path):
                os.remove(html_path)
                print(f"  Removed: events/{slug}.html")

        removed_names = [r['name'] for r in results
                         if r and r.get('category') == 'needs_manual']
    else:
        removed_names = []

    report = generate_report(results, removed_names)
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"\nReport saved to {REPORT_PATH}")

    serializable = [r for r in results if r is not None]
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)
    print(f"Data saved to {DATA_PATH}")

    enriched = len([r for r in results if r and r.get('category') == 'enriched'])
    removed = len(needs_manual_slugs)
    print(f"\n=== Summary: ✅{enriched} enriched / 🗑️{removed} removed ===")


if __name__ == '__main__':
    main()
