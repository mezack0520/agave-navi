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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import is_generic_image_url as _sitelib_is_generic
from sitelib import DESC_MIN_CHARS, now_jst

REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
EVENTS_PATH = os.path.join(REPO_ROOT, 'events.json')
EVENTS_DIR = os.path.join(REPO_ROOT, 'events')
REPORT_PATH = '/tmp/enrich-report.md'

# 短文(70字未満)の開催予定イベントで説明文を差し替えなかった理由の記録。
# 標準出力だけだと CI ログに埋もれ、翌週も同じ推測をやり直すことになるため
# 週次レポート(Issue)に出す。形: (slug, 現在の字数, 候補の字数, 理由)
DESC_SKIPS = []
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

# --- Aggregator/blocklist (used by image, url and field acceptance) ---
AGGREGATOR_DOMAINS = (
    'nextmeet.app', 'botanical-zone.tokyo', 'leaf-laboratory.com',
    'tochinavi.net', 'pukubook.jp', 'fukuoka-now.com', 'churatoku.net', 'agavemaniacs.com',
)
_GENERIC_IMG_RE = re.compile(
    r'/(ogp|og_image|og-image|default|logo|share|thumb|main)\.(png|jpg|jpeg|webp|gif)(\?|$)',
    re.I
)

def _url_contains_aggregator(url):
    """Detect aggregator anywhere in the URL (host or CDN-proxied path)."""
    if not url: return False
    u = url.lower()
    return any(ag in u for ag in AGGREGATOR_DOMAINS)

def is_aggregator_url(url):
    """Reject URLs whose host or path contains a known aggregator domain."""
    return _url_contains_aggregator(url)

_PLACEHOLDER_VALUES = {
    '', '調整中', '未定', 'TBD', 'TBA', '-', '−', '—', '?', '？', '不明', '未発表',
}

def _is_empty(v):
    """Treat placeholder strings ('調整中', '未定' etc.) as effectively empty
    so enrichment can overwrite them."""
    if v is None: return True
    if isinstance(v, str):
        return v.strip() in _PLACEHOLDER_VALUES
    return not bool(v)


def is_quality_image_url(img_url):
    """Image URL acceptance: reject aggregator-sourced AND generic-named images."""
    if not img_url:
        return False
    if _url_contains_aggregator(img_url):
        return False
    if _GENERIC_IMG_RE.search(img_url):
        return False
    # サイト共通アセット(themes/ 配下・common/images/ 配下等)。
    # _GENERIC_IMG_RE はファイル名しか見ないため、
    # /wp-content/themes/.../common/images/facebook.png を通してしまう。
    # 判定は sitelib が単一情報源(2026-08-20)。
    if _sitelib_is_generic(img_url):
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
        # Encoding selection: trust HTTP Content-Type charset if present,
        # otherwise default to UTF-8 (most modern Japanese sites are UTF-8).
        # `apparent_encoding` was previously used but chardet often
        # misidentifies UTF-8 Japanese pages as Windows-1252/Latin → mojibake.
        ct = resp.headers.get('Content-Type', '').lower()
        if 'charset=' in ct:
            cs = ct.split('charset=', 1)[1].split(';')[0].strip()
            if cs:
                resp.encoding = cs
            else:
                resp.encoding = 'utf-8'
        else:
            resp.encoding = 'utf-8'
        # If we still got mojibake-looking bytes, fall back to letting
        # BeautifulSoup sniff from raw bytes (handles BOM + meta charset).
        soup = BeautifulSoup(resp.content, 'html.parser')
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

    # --- Time extraction (HH:MM〜HH:MM, accepts various separators) ---
    time_pattern = r'(\d{1,2})\s*[：:]\s*(\d{2})\s*[～〜~ー−–-]\s*(\d{1,2})\s*[：:]\s*(\d{2})'
    times = re.findall(time_pattern, text)
    if times:
        # dedupe preserving order
        seen = set(); uniq = []
        for tm in times:
            key = (tm[0], tm[1], tm[2], tm[3])
            if key not in seen:
                seen.add(key); uniq.append(tm)
        info['times_found'] = [f"{t[0]}:{t[1]}〜{t[2]}:{t[3]}" for t in uniq[:3]]

    # --- Admission/Price extraction ---
    price_patterns = [
        # 'ラベル: 値' 形式
        r'(入場[料金]?\s*[：:]\s*[^\n]{3,50})',
        # 'ラベル\n値' (HTMLテーブル)
        r'(?:^|\n)\s*入場[料金]?\s*\n([^\n]{3,80})',
        r'(一般入?場?\s*[：:]?\s*[\d,]+円(?:[^\n]{0,40})?)',
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
        # 'ラベル: 値' 形式
        r'(?:会場|開催場所|場所)\s*[：:]\s*([^\n]{3,80})',
        # 'ラベル\n値' 形式(HTMLテーブル由来)
        r'(?:^|\n)\s*(?:会場|開催場所|場所)\s*\n([^\n]{3,80})',
        # 郵便番号始まりの住所
        r'(〒\d{3}-\d{4}[^\n]{5,80})',
    ]
    venues_raw = []
    for pat in venue_patterns:
        for m in re.finditer(pat, text, re.MULTILINE):
            v = m.group(1) if m.lastindex else m.group(0)
            v = v.strip()
            if v and v not in venues_raw:
                venues_raw.append(v)
    venues = []
    for v in venues_raw:
        # filter out generic placeholders / TOC labels
        if any(bad in v for bad in ['詳しくは', '公式サイト', 'ご参照', 'クリック']):
            continue
        venues.append(v)
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
        # Instagram は post / reel / profile を valid source として許可
        # (画像取得はIG認証要なので諦めるが、URL自体は instagramUrl として保存できる)
        if 'agave-navi.com' in domain:
            return False
        if 'instagram.com' in domain:
            return True
        if any(skip in domain for skip in SKIP_DOMAINS):
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
    # events.json にプレースホルダー('調整中'/'未定'等)があれば常に enrichment 対象
    has_placeholders = any(
        _is_empty(event.get(f, '')) and event.get(f) is not None
        and str(event.get(f, '')).strip() not in ('', None)
        for f in ('venue', 'mapQuery', 'admission', 'time', 'access')
    )
    # Or simpler: check if any of those fields has a placeholder string
    placeholder_fields = []
    for f in ('venue', 'mapQuery', 'admission', 'time', 'access'):
        v = event.get(f)
        if isinstance(v, str) and v.strip() in _PLACEHOLDER_VALUES and v.strip():
            placeholder_fields.append(f)

    # 開催予定で説明文が70字未満なら、詳細ページ側が整っていても対象にする。
    # これが無いと _priority が先頭に並べた短文イベントのうち、OGP画像を持つものが
    # 毎週 'Already enriched, skipping' で落ち、監査の short_descriptions が動かない。
    # (2026-08-18: 18件中5件がこの経路で9週間ぶん取りこぼされていた)
    short_upcoming_desc = (
        event.get('status') == 'upcoming'
        and len((event.get('description') or '').strip()) < 70
    )

    needs_update = (
        page_state.get('has_generic_desc', False) or
        page_state.get('has_template_text', False) or
        not page_state.get('has_ogp_image', False) or
        bool(placeholder_fields) or
        short_upcoming_desc
    )
    if placeholder_fields:
        print(f"  Placeholders detected in: {placeholder_fields}")

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

    # === Section 3: 短文のまま残ったイベントと、その理由 ===
    if DESC_SKIPS:
        report += "### ✍️ 説明文が短いまま残った開催予定イベント\n\n"
        report += "監査の `short_descriptions` が動かない原因はここに出る。"
        report += "`candidate identical` が続く回は出典側に本文が無い。\n\n"
        report += "| slug | 現在 | 候補 | 差し替えなかった理由 |\n|---|---|---|---|\n"
        for slug, cur_n, cand_n, why in DESC_SKIPS:
            report += f"| `{slug}` | {cur_n}字 | {cand_n}字 | {why} |\n"
        report += "\n"

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
    print(f"Started at: {now_jst().isoformat()}")

    events = load_events()
    print(f"Total events: {len(events)}")

    if args.slug:
        events = [e for e in events if e['slug'] == args.slug]
        if not events:
            print(f"Event not found: {args.slug}")
            sys.exit(1)

    # 優先順: 開催予定かつdescription70字未満(SERPスニペット枠を使い切れないページ)を先に、
    # 次いでその他の開催予定、最後に過去分。同群内は開催日が近い順。
    # --limit で先頭から打ち切られるため、この並びが実質的な処理対象の選択になる。
    # (2026-07-27 要判断 health-check:upcoming-meta-description-too-short の恒久対応)
    def _priority(e):
        upcoming = e.get('status') == 'upcoming'
        short_desc = len((e.get('description') or '').strip()) < 70
        group = 0 if (upcoming and short_desc) else (1 if upcoming else 2)
        return (group, e.get('date') or '9999-12-31')
    events.sort(key=_priority)

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
            # If the search hit was an aggregator, do not trust ANY of its fields
            # (those pages often list multiple events and we'd cross-contaminate).
            if best_url and is_aggregator_url(best_url):
                print(f"    SKIP-ALL for {ev['slug']}: source is aggregator — {best_url[:70]}")
                continue
            changed_fields = []

            # IG投稿URLの場合は instagramUrl / instagramPostId として保存(画像は取れないが
            # 公式source として有効)。post/reel/tv パターンを判定。
            ig_post_match = None
            if best_url and 'instagram.com' in best_url.lower():
                m = re.search(r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', best_url)
                if m:
                    ig_post_match = m.group(1)
            if ig_post_match:
                if _is_empty(ev.get('instagramUrl')):
                    ev['instagramUrl'] = best_url
                    changed_fields.append('instagramUrl')
                if _is_empty(ev.get('instagramPostId')):
                    ev['instagramPostId'] = ig_post_match
                    changed_fields.append('instagramPostId')
            elif best_url and 'instagram.com' in best_url.lower():
                # IG profile URL — sourceUrl として保存
                if _is_empty(ev.get('sourceUrl')):
                    ev['sourceUrl'] = best_url
                    changed_fields.append('sourceUrl')
            elif best_url and _is_empty(ev.get('url')):
                # 通常のwebサイト — url として保存(aggregator拒否)
                if is_aggregator_url(best_url):
                    print(f"    URL-REJECTED for {ev['slug']}: aggregator — {best_url[:70]}")
                else:
                    ev['url'] = best_url
                    changed_fields.append('url')

            # imageUrl (only if empty, with HEAD verification)
            ogp_image = info.get('ogp_image')
            if ogp_image and _is_empty(ev.get('imageUrl')):
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
                # 下限は sitelib.DESC_MIN_CHARS。ここを120字にしていたため、
                # 現状より明確に長い候補まで 'too short' で捨てていた
                # (2026-08-20: narabikakufes 60→112字、greensnap横浜 43→69字)。
                # 短すぎる断片を弾くのが目的で、長さの優劣は下の long_enough が見る。
                if not cand or len(cand) < DESC_MIN_CHARS:
                    return False, f'too short (<{DESC_MIN_CHARS}字)'
                # 改行を含む候補は「段落を切り出せていない」= ページ全文の貼り付け。
                # long_description は空行(\n{2,})で段落を割るため、単一改行だけで
                # 組まれた1枚もののサイトではナビ・見出し・フッタごと1段落になる。
                # そのまま入ると description に改行が残り、詳細ページの JSON-LD が
                # 制御文字で壊れる(2026-08-18 souransai-koshigaya-2026-10 で発生)
                if '\n' in cand or '\t' in cand:
                    return False, 'multi-line (page dump, not a paragraph)'
                # 改行を空白に潰してから渡してくる経路があり、\n の検査だけでは抜ける
                # (2026-08-27: note.com の本文が2連続スペース入りで通り、
                #  手で書いた説明文を296字のページ全文で上書きした)。
                # 段落として書かれた文に2連続スペースは出ない。
                if '  ' in cand:
                    return False, 'joined lines (2連続スペース)'
                # 段落を正しく切り出せていれば文の終わりで終わる。
                # 途中で切れている候補は本文の一部をつかんだだけ
                if cand[-1] not in '。！？!?':
                    return False, 'does not end with sentence terminator'
                # Reject aggregator/boilerplate phrases
                blocklist = [
                    'イベント情報をまとめ', '次回のイベント', '関連するタグ',
                    '実際の情報が変更', '各リンクよりご確認', '記事は執筆時の情報',
                    '当サイトでは', '公開：', 'クッキーを使用',
                    # 下限を50字に下げた結果、会場名+イベント名+定型文だけの
                    # アグリゲータ見出しが通った(2026-08-20 greensnap横浜。
                    # 43字の実のある説明文を69字の定型文で上書きしてしまった)
                    '詳細情報をご紹介', 'の詳細をご紹介', '情報をお届け', '詳細はこちら',
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
            # 現状より長いことを必ず要求する。cur_desc < 80 だけで通していたため、
            # 短い現状を さらに短い候補で 上書きできる穴があった。
            long_enough = len(candidate_desc) > len(cur_desc) and (
                len(cur_desc) < 80 or len(candidate_desc) >= int(len(cur_desc) * 1.2))
            # 直近に人が書いた説明文はスクレイパで上書きしない。
            # 2026-08-27、掲載直後の PLANTS SHOW 桐生で、手で書いた145字が
            # note.com のページ全文296字に置き換わった。長さで勝てば通る設計だと、
            # 裏取りして書いた文が機械的な貼り付けに負ける。
            # 判定は sitelib.desc_is_protected が単一情報源。
            # ここに条件を書くと、検出側(audit.py)と食い違って気づけない。
            # updatedAt が無い回は addedDate で守る(登録時の入れ忘れが常態のため)。
            from sitelib import desc_is_protected as _desc_is_protected
            _recent_hand_written = _desc_is_protected(ev)
            _upd = (ev.get('updatedAt') or ev.get('addedDate') or '').strip()

            if ok and candidate_desc != cur_desc and long_enough and not _recent_hand_written:
                ev['description'] = candidate_desc[:500]
                changed_fields.append('description')
            elif _recent_hand_written and ok and long_enough:
                print(f"    DESC-KEPT for {ev['slug']}: {_upd} は14日以内。"
                      f"手で書いた本文を優先して上書きしない")
            elif len(cur_desc) < 70 and ev.get('status') == 'upcoming':
                # 短文のまま残る回は理由を残す。ok=True でも差し替わらない経路
                # (候補が現状と同一・伸び幅不足)があり、理由を分けないと原因を追えない
                if not ok:
                    why = reason or 'quality check failed'
                elif candidate_desc == cur_desc:
                    why = 'candidate identical to current'
                else:
                    why = 'candidate not longer than current'
                DESC_SKIPS.append((ev['slug'], len(cur_desc), len(candidate_desc), why))
                print(f"    DESC-REJECTED for {ev['slug']}: {why}")

            # time (only if empty)
            times_found = info.get('times_found') or []
            if times_found and _is_empty(ev.get('time')):
                ev['time'] = times_found[0]
                changed_fields.append('time')

            # admission (only if empty)
            prices = info.get('prices_found') or []
            if prices and _is_empty(ev.get('admission')):
                # pick the shortest non-trivial entry as the headline price
                pick = sorted(prices, key=lambda s: (len(s) > 60, len(s)))[0]
                if pick:
                    ev['admission'] = pick[:80]
                    changed_fields.append('admission')

            # access (new field, only if empty)
            access_lines = info.get('access_found') or []
            if access_lines and _is_empty(ev.get('access')):
                ev['access'] = ' / '.join(access_lines)[:300]
                changed_fields.append('access')

            # venue (only if empty/placeholder; pick the first venue extracted)
            venues = info.get('venues_found') or []
            if venues and _is_empty(ev.get('venue')):
                # venues_found entries may contain prefix like '会場：' — strip
                v = venues[0]
                import re as _re
                v = _re.sub(r'^(会場|開催場所|場所)\s*[：:]\s*', '', v).strip()
                if 3 < len(v) < 120:
                    ev['venue'] = v[:100]
                    changed_fields.append('venue')
                    # mapQuery を venue で更新(plaheolderだった場合)
                    if _is_empty(ev.get('mapQuery')):
                        ev['mapQuery'] = v[:100]
                        changed_fields.append('mapQuery')

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
