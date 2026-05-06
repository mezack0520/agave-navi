#!/usr/bin/env python3
"""
build-detail-pages.py
events.json + templates/detail.html → events/*.html

Usage:
  python3 build-detail-pages.py                 # Generate all pages
  python3 build-detail-pages.py --slug foo-2026  # Generate one page
  python3 build-detail-pages.py --dry-run        # Preview without writing
"""

import json
import os
import sys
import argparse
from datetime import datetime, timedelta
from urllib.parse import quote

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_JSON = os.path.join(SCRIPT_DIR, 'events.json')
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, 'templates', 'detail.html')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'events')
CSS_VERSION = '20260504d'
JS_VERSION = '20260504d'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

WEEKDAYS_JA = ['月', '火', '水', '木', '金', '土', '日']

def date_to_japanese(date_str):
    """2026-05-03 → 2026年5月3日（日）"""
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        wd = WEEKDAYS_JA[dt.weekday()]
        return f'{dt.year}年{dt.month}月{dt.day}日（{wd}）'
    except ValueError:
        return date_str

def make_date_display_full(ev):
    """sidebar用のフル日時表示を生成"""
    date_str = ev.get('date', '')
    date_end = ev.get('dateEnd', '')
    time_str = ev.get('time', '')

    if not date_str:
        return ev.get('dateDisplay', '未定')

    start_ja = date_to_japanese(date_str)

    if date_end and date_end != date_str:
        try:
            end_dt = datetime.strptime(date_end, '%Y-%m-%d')
            wd = WEEKDAYS_JA[end_dt.weekday()]
            end_display = f'{end_dt.month}月{end_dt.day}日（{wd}）'
            display = f'{start_ja} 〜 {end_display}'
        except ValueError:
            display = start_ja
    else:
        display = start_ja

    if time_str:
        display += f' {time_str}'

    return display

def make_date_display_short(ev):
    """header meta用の短い日付表示"""
    date_str = ev.get('date', '')
    if not date_str:
        return ev.get('dateDisplay', '未定')
    return date_to_japanese(date_str)

def make_gcal_url(ev):
    """Google Calendar追加URL"""
    name = ev.get('name', '')
    date_str = ev.get('date', '')
    date_end = ev.get('dateEnd', date_str)
    venue = ev.get('venue', '')

    if not date_str:
        return '#'

    start = date_str.replace('-', '')
    # Google Calendar uses exclusive end date
    try:
        end_dt = datetime.strptime(date_end or date_str, '%Y-%m-%d') + timedelta(days=1)
        end = end_dt.strftime('%Y%m%d')
    except ValueError:
        end = start

    name_enc = quote(name)
    venue_enc = quote(venue)
    return f'https://calendar.google.com/calendar/render?action=TEMPLATE&text={name_enc}&dates={start}%2F{end}&location={venue_enc}'

def make_meta_description(ev):
    """OG description / meta description"""
    desc = ev.get('description', '')
    if len(desc) > 160:
        desc = desc[:157] + '...'
    return desc

def make_instagram_section(ev):
    """Instagram embed section (if instagramPostId exists)"""
    post_id = ev.get('instagramPostId', '')
    ig_url = ev.get('instagramUrl', '')
    if not post_id and not ig_url:
        return ''

    if not post_id and ig_url:
        # Extract post ID from URL
        import re
        m = re.search(r'/p/([A-Za-z0-9_-]+)', ig_url)
        if m:
            post_id = m.group(1)
        else:
            return ''

    if not ig_url:
        ig_url = f'https://www.instagram.com/p/{post_id}/'

    return f'''        <div class="detail-section detail-instagram-embed">
          <h2 class="detail-section-title">Instagram投稿</h2>
          <div class="instagram-embed-wrap">
            <iframe src="https://www.instagram.com/p/{post_id}/embed/" loading="lazy" frameborder="0" scrolling="no" allowtransparency="true" allowfullscreen></iframe>
          </div>
          <p class="instagram-embed-link"><a href="{ig_url}" target="_blank" rel="noopener">Instagramで見る ↗</a></p>
        </div>
'''

def make_map_section(ev):
    """Map section (if mapQuery exists)"""
    map_query = ev.get('mapQuery', '')
    if not map_query:
        return ''

    map_query_enc = quote(map_query)
    return f'''        <div class="detail-map">
          <h2 class="detail-section-title">会場</h2>
          <div class="map-container">
            <a href="https://www.google.com/maps/search/?api=1&query={map_query_enc}" target="_blank" rel="noopener" class="map-open-link">マップで開く &#8599;</a>
            <iframe src="https://www.google.com/maps?q={map_query_enc}&output=embed" width="100%" height="300" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
          </div>
        </div>
'''



def make_hero_section(ev):
    """Hero image section (only if imageUrl exists). Rendered at top of <main> outside columns."""
    img = ev.get('imageUrl', '')
    if not img:
        return ''
    name = ev.get('name', '')
    alt = html_escape(name) if name else ''
    return f'''    <div class="detail-hero">
      <img src="{img}" alt="{alt}" class="detail-hero-img" referrerpolicy="no-referrer" onerror="this.parentElement.style.display='none'">
    </div>
'''



def make_access_row(ev):
    """Access info row in sidebar (only if access exists)"""
    access = ev.get('access', '')
    if not access:
        return ''
    return f'''          <div class="info-row">
            <span class="info-label">アクセス</span>
            <span class="info-value">{html_escape(access)}</span>
          </div>'''


def make_og_image(ev):
    """og:image: imageUrl があればそれ、無ければサイト共通OGP"""
    img = ev.get('imageUrl') or ''
    if img:
        return img
    return 'https://agave-navi.com/images/ogp-default.jpg'


def make_share_section(ev):
    """X(Twitter) / LINE / コピー 用シェアボタン"""
    name = ev.get('name', '') or ''
    slug = ev.get('slug', '') or ''
    page_url = f'https://agave-navi.com/events/{slug}.html'
    text = f'{name} | アガベイベントナビ'
    text_enc = quote(text)
    url_enc = quote(page_url)
    twitter_url = f'https://twitter.com/intent/tweet?text={text_enc}&url={url_enc}'
    line_url = f'https://social-plugins.line.me/lineit/share?url={url_enc}'
    return f'''        <div class="detail-share">
          <span class="detail-share-label">シェア:</span>
          <a class="share-btn share-x" href="{twitter_url}" target="_blank" rel="noopener" aria-label="Xでシェア">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg>
            <span>X</span>
          </a>
          <a class="share-btn share-line" href="{line_url}" target="_blank" rel="noopener" aria-label="LINEでシェア">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor"><path d="M19.365 9.863c.349 0 .63.285.63.631 0 .345-.281.63-.63.63H17.61v1.125h1.755c.349 0 .63.283.63.63 0 .344-.281.629-.63.629h-2.386c-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63h2.386c.346 0 .627.285.627.63 0 .349-.281.63-.63.63H17.61v1.125zm-3.855 3.016c0 .27-.174.51-.432.596-.064.021-.133.031-.199.031-.211 0-.391-.09-.51-.25l-2.443-3.317v2.94c0 .344-.279.629-.631.629-.346 0-.626-.285-.626-.629V8.108c0-.27.173-.51.43-.595.06-.023.136-.033.194-.033.195 0 .375.104.495.254l2.462 3.33V8.108c0-.345.282-.63.63-.63.345 0 .63.285.63.63zm-5.741 0c0 .344-.282.629-.631.629-.345 0-.627-.285-.627-.629V8.108c0-.345.282-.63.63-.63.346 0 .628.285.628.63zm-2.466.629H4.917c-.345 0-.63-.285-.63-.629V8.108c0-.345.285-.63.63-.63.348 0 .63.285.63.63v3.756h1.756c.348 0 .629.283.629.63 0 .344-.282.629-.629.629M24 10.314C24 4.943 18.615.572 12 .572S0 4.943 0 10.314c0 4.811 4.27 8.842 10.035 9.608.391.082.923.258 1.058.59.12.301.079.766.038 1.08l-.164 1.02c-.045.301-.24 1.186 1.049.645 1.291-.539 6.916-4.078 9.436-6.975C23.176 14.393 24 12.458 24 10.314"/></svg>
            <span>LINE</span>
          </a>
          <button class="share-btn share-copy" type="button" onclick="(function(b){{const u='{page_url}';navigator.clipboard.writeText(u).then(()=>{{const o=b.querySelector('span').textContent;b.querySelector('span').textContent='コピー済';setTimeout(()=>b.querySelector('span').textContent=o,1500);}});}})(this);" aria-label="リンクをコピー">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>リンクコピー</span>
          </button>
        </div>
'''


def make_tags_csv(ev):
    return ','.join(ev.get('tags', []) or [])


def make_robots_meta(ev):
    """終了から30日経過したイベントには noindex を付与してクロール予算を節約"""
    from datetime import datetime, timedelta
    end = ev.get('dateEnd') or ev.get('date') or ''
    if not end:
        return 'index,follow'
    try:
        end_dt = datetime.strptime(end, '%Y-%m-%d')
        if end_dt < datetime.now() - timedelta(days=30):
            return 'noindex,follow'
    except ValueError:
        pass
    return 'index,follow'


def make_breadcrumb_prefecture(ev):
    """visible breadcrumb の prefecture セグメント。
    都道府県あり: '<a href="/?region=R&pref=P">P</a> > '
    なし: 空文字列(直接イベント名にスキップ)"""
    pref = ev.get('prefecture', '') or ''
    if not pref:
        return ''
    region = ev.get('region', '') or ''
    return f'    <a href="/?region={quote(region)}&pref={quote(pref)}">{html_escape(pref)}</a> &gt;\n'


def make_breadcrumb_ld_prefecture(ev):
    """JSON-LD BreadcrumbList の prefecture ListItem(あれば)。
    あり: ',\n      {ListItem position3 ...}'
    なし: ''"""
    pref = ev.get('prefecture', '') or ''
    if not pref:
        return ''
    region = ev.get('region', '') or ''
    return (
        f',\n      {{\n'
        f'        "@type": "ListItem",\n'
        f'        "position": 3,\n'
        f'        "name": "{html_escape(pref)}",\n'
        f'        "item": "https://agave-navi.com/?region={quote(region)}&pref={quote(pref)}"\n'
        f'      }}'
    )


def make_breadcrumb_ld_last_pos(ev):
    """イベント名の position は prefecture の有無で 3 or 4"""
    return '4' if ev.get('prefecture') else '3'


def make_event_jsonld(ev):
    """schema.org Event JSON-LD. Skip entirely if no date (avoid invalid empty startDate)."""
    if not ev.get('date'):
        return ''
    from datetime import datetime, timedelta
    name = html_escape(ev.get('name', ''))
    date = ev.get('date', '')
    end = ev.get('dateEnd') or date
    venue = html_escape(ev.get('venue', '') or '')
    pref = ev.get('prefecture', '') or ev.get('region', '')
    desc = html_escape(make_meta_description(ev))
    image_url = (ev.get('imageUrl') or '').replace('"', '&quot;')
    image_field = f',\n    "image": "{image_url}"' if image_url else ''
    # eventStatus 動的判定
    status_map = {
        'confirmed': 'EventScheduled',
        'cancelled': 'EventCancelled',
        'postponed': 'EventPostponed',
        'rescheduled': 'EventRescheduled',
        'movedonline': 'EventMovedOnline',
    }
    ev_status_raw = (ev.get('eventStatus') or 'confirmed').lower()
    schema_status = status_map.get(ev_status_raw, 'EventScheduled')
    # offers (admission)
    admission = (ev.get('admission') or '').strip()
    offers_field = ''
    if admission:
        is_free = ('無料' in admission)
        # 価格抽出 (例: '500円', '1,000円', '前売¥1,600')
        import re as _re
        price_match = _re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*円', admission)
        price = price_match.group(1).replace(',', '') if price_match else ('0' if is_free else '')
        if price or is_free:
            avail_url = f'https://agave-navi.com/events/{ev.get("slug","")}.html'
            offers_field = (
                f',\n    "offers": {{\n'
                f'      "@type": "Offer",\n'
                f'      "price": "{price or 0}",\n'
                f'      "priceCurrency": "JPY",\n'
                f'      "availability": "https://schema.org/InStock",\n'
                f'      "url": "{avail_url}"\n'
                f'    }}'
            )
    return f'''  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "{name}",
    "startDate": "{date}",
    "endDate": "{end}"{image_field},
    "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
    "eventStatus": "https://schema.org/{schema_status}",
    "location": {{
      "@type": "Place",
      "name": "{venue}",
      "address": {{
        "@type": "PostalAddress",
        "addressRegion": "{pref}",
        "addressCountry": "JP"
      }}
    }}{offers_field},
    "description": "{desc}",
    "organizer": {{
      "@type": "Organization",
      "name": "{name}"
    }}
  }}
  </script>'''

def make_official_links_rows(ev):
    """公式情報の info-row。以下のルール:
    - URL を種別(公式サイト/公式Instagram/公式X/公式Facebook/Instagram投稿)に分類
    - 同じ種別は1件のみ表示(重複防止)
    - 既に main column の Instagram 埋込が出る場合は「Instagram投稿」行を省略
    - 全部なければ Google検索フォールバック"""
    items = []  # list of (url, label, kind)
    seen_kinds = set()
    seen_urls = set()

    def classify(u):
        ul = (u or '').lower()
        if not ul:
            return None
        if 'instagram.com' in ul:
            if '/p/' in ul or '/reel/' in ul or '/tv/' in ul:
                return 'ig_post'
            return 'ig_profile'
        if 'facebook.com' in ul:
            return 'facebook'
        if 'twitter.com' in ul or '://x.com/' in ul:
            return 'x'
        return 'site'

    LABELS = {
        'ig_post': 'Instagram投稿',
        'ig_profile': '公式Instagram',
        'facebook': '公式Facebook',
        'x': '公式X',
        'site': '公式サイト',
    }

    has_ig_embed = bool(ev.get('instagramPostId') or ev.get('instagramUrl'))

    def add(url):
        if not url or url in seen_urls:
            return
        kind = classify(url)
        if not kind:
            return
        if kind in seen_kinds:
            return
        # If main column already has IG iframe, skip the IG投稿 row in sidebar
        if kind == 'ig_post' and has_ig_embed:
            return
        seen_urls.add(url); seen_kinds.add(kind)
        items.append((url, LABELS[kind], kind))

    # Priority order: url, sourceUrl, instagramUrl
    add(ev.get('url') or '')
    add(ev.get('sourceUrl') or '')
    add(ev.get('instagramUrl') or '')

    if not items:
        # If IG iframe is already shown in main column, that section already has
        # an "Instagramで見る ↗" link. No need for sidebar fallback.
        if has_ig_embed:
            return ''
        # Otherwise: Google search fallback
        name = ev.get('name', '')
        if not name:
            return ''
        venue = ev.get('venue', '')
        q = quote(f'{name} {venue} 2026'.strip())
        items.append((f'https://www.google.com/search?q={q}', 'Googleで検索', 'search'))

    rows = []
    for u, label, _ in items:
        rows.append(
            f'          <div class="info-row">\n'
            f'            <span class="info-label">公式</span>\n'
            f'            <span class="info-value"><a href="{u}" target="_blank" rel="noopener">{html_escape(label)} ↗</a></span>\n'
            f'          </div>'
        )
    return '\n'.join(rows)


def make_admission_row(ev):
    """Admission info row"""
    admission = ev.get('admission', '')
    if not admission:
        return ''
    return f'''          <div class="info-row">
            <span class="info-label">入場料</span>
            <span class="info-value">{admission}</span>
          </div>'''

def make_time_row(ev):
    """Time info row"""
    time_str = ev.get('time', '')
    if not time_str:
        return ''
    return f'''          <div class="info-row">
            <span class="info-label">時間</span>
            <span class="info-value">{time_str}</span>
          </div>'''


def html_escape(text):
    """Basic HTML escaping"""
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_page(template, ev):
    """Generate one detail page from template + event data"""
    slug = ev.get('slug', '')
    name = ev.get('name', '')
    date = ev.get('date', '')
    date_end = ev.get('dateEnd', '')
    region = ev.get('region', '')
    prefecture = ev.get('prefecture', region)
    venue = ev.get('venue', '')

    replacements = {
        '{{slug}}': slug,
        '{{name}}': html_escape(name),
        '{{date}}': date,
        '{{dateEnd}}': date_end,
        '{{dateEndOrDate}}': date_end or date,
        '{{dateDisplayShort}}': make_date_display_short(ev),
        '{{dateDisplayFull}}': make_date_display_full(ev),
        '{{region}}': region,
        '{{regionEncoded}}': quote(region),
        '{{prefecture}}': prefecture,
        '{{prefectureOrRegion}}': prefecture or region,
        '{{venue}}': html_escape(venue) if venue else '会場未定',
        '{{description}}': html_escape(ev.get('description', '')),
        '{{metaDescription}}': html_escape(make_meta_description(ev)),
        '{{gcalUrl}}': make_gcal_url(ev),
        '{{cssVersion}}': CSS_VERSION,
        '{{jsVersion}}': JS_VERSION,
        '{{heroSection}}': make_hero_section(ev),
        '{{eventJsonLd}}': make_event_jsonld(ev),
        '{{accessRow}}': make_access_row(ev),
        '{{robotsMeta}}': make_robots_meta(ev),
        '{{breadcrumbPrefecture}}': make_breadcrumb_prefecture(ev),
        '{{breadcrumbLdPrefecture}}': make_breadcrumb_ld_prefecture(ev),
        '{{breadcrumbLdLastPos}}': make_breadcrumb_ld_last_pos(ev),
        '{{officialLinksRows}}': make_official_links_rows(ev),
        '{{ogImage}}': make_og_image(ev),
        '{{shareSection}}': make_share_section(ev),
        '{{tagsCsv}}': make_tags_csv(ev),
        '{{instagramSection}}': make_instagram_section(ev),
        '{{mapSection}}': make_map_section(ev),
        '{{admissionRow}}': make_admission_row(ev),
        '{{timeRow}}': make_time_row(ev),
        '{{lastUpdatedRow}}': make_last_updated_row(ev),
        '{{dataSourceRow}}': make_data_source_row(ev),
    }

    html = template
    for key, value in replacements.items():
        html = html.replace(key, value)

    return html



def make_last_updated_row(ev):
    """イベント情報の最終更新日表示。enrichedAt > addedDate を優先。"""
    last = ev.get('enrichedAt') or ev.get('addedDate')
    if not last:
        return ''
    try:
        d = last[:10]
        from datetime import datetime as _dt
        dt = _dt.strptime(d, '%Y-%m-%d')
        disp = f'{dt.year}年{dt.month}月{dt.day}日'
    except Exception:
        disp = last
    return ('\n          <div class="info-row">'
            '\n            <span class="info-label">最終更新</span>'
            f'\n            <span class="info-value">{disp}</span>'
            '\n          </div>')


def make_data_source_row(ev):
    """データソース表示。url があれば公式参照を、なければ自社収集を明記。"""
    url = (ev.get('url') or '').strip()
    if not url:
        return ('\n          <div class="info-row">'
                '\n            <span class="info-label">データソース</span>'
                '\n            <span class="info-value" style="font-size:.85em;color:#6a7855">スタッフ収集情報</span>'
                '\n          </div>')
    src_label = '公式サイト'
    if 'instagram.com' in url:
        src_label = '公式Instagram'
    elif 'facebook.com' in url:
        src_label = '公式Facebook'
    elif 'twitter.com' in url or 'x.com' in url:
        src_label = '公式X(Twitter)'
    return ('\n          <div class="info-row">'
            '\n            <span class="info-label">データソース</span>'
            f'\n            <span class="info-value" style="font-size:.85em;color:#6a7855">{src_label}を参照</span>'
            '\n          </div>')



def main():
    parser = argparse.ArgumentParser(description='Build detail pages from events.json')
    parser.add_argument('--slug', help='Generate only this slug')
    parser.add_argument('--dry-run', action='store_true', help='Preview without writing files')
    parser.add_argument('--events', default=EVENTS_JSON, help='Path to events.json')
    args = parser.parse_args()

    # Load template
    with open(TEMPLATE_FILE, 'r', encoding='utf-8') as f:
        template = f.read()

    # Load events
    with open(args.events, 'r', encoding='utf-8') as f:
        events = json.load(f)

    # Filter if slug specified
    if args.slug:
        events = [e for e in events if e['slug'] == args.slug]
        if not events:
            print(f'Error: slug "{args.slug}" not found in events.json')
            sys.exit(1)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    generated = 0
    skipped = 0
    for ev in events:
        slug = ev.get('slug', '')
        if not slug:
            skipped += 1
            continue

        # Note: events without date are still built (with dateDisplay fallback);
        # JSON-LD Event schema is omitted in that case (see make_event_jsonld).

        html = build_page(template, ev)
        output_path = os.path.join(OUTPUT_DIR, f'{slug}.html')

        if args.dry_run:
            print(f'  DRY-RUN: {slug}.html ({len(html)} bytes)')
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f'  Generated: {slug}.html')

        generated += 1

    print(f'\nDone: {generated} generated, {skipped} skipped')


if __name__ == '__main__':
    main()
