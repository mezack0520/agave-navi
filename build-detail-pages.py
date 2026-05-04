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
CSS_VERSION = '20260504b'
JS_VERSION = '20260504b'

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



def make_event_jsonld(ev):
    """schema.org Event JSON-LD. Skip entirely if no date (avoid invalid empty startDate)."""
    if not ev.get('date'):
        return ''
    name = html_escape(ev.get('name', ''))
    date = ev.get('date', '')
    end = ev.get('dateEnd') or date
    venue = html_escape(ev.get('venue', '') or '')
    pref = ev.get('prefecture', '') or ev.get('region', '')
    desc = html_escape(make_meta_description(ev))
    return f'''  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "{name}",
    "startDate": "{date}",
    "endDate": "{end}",
    "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
    "eventStatus": "https://schema.org/EventScheduled",
    "location": {{
      "@type": "Place",
      "name": "{venue}",
      "address": {{
        "@type": "PostalAddress",
        "addressRegion": "{pref}",
        "addressCountry": "JP"
      }}
    }},
    "description": "{desc}",
    "organizer": {{
      "@type": "Organization",
      "name": "{name}"
    }}
  }}
  </script>'''

def make_official_links_rows(ev):
    """公式情報の info-row(複数可)。サイドバー EVENT INFO 内に表示。
    url/sourceUrl/instagramUrl がなければ Google検索リンクをフォールバック。"""
    items = []  # list of (url, label)
    seen = set()

    def add(url, label):
        if not url or url in seen:
            return
        seen.add(url)
        items.append((url, label))

    if ev.get('url'):
        u = ev['url']
        if 'instagram.com' in u:
            label = '公式Instagram'
        elif 'facebook.com' in u:
            label = 'Facebook'
        elif 'twitter.com' in u or '://x.com/' in u:
            label = 'X (Twitter)'
        else:
            label = '公式サイト'
        add(u, label)

    if ev.get('sourceUrl'):
        s = ev['sourceUrl']
        if 'instagram.com' in s:
            add(s, '公式Instagram')
        elif 'facebook.com' in s:
            add(s, '公式Facebook')
        elif 'twitter.com' in s or '://x.com/' in s:
            add(s, '公式X')
        else:
            add(s, '公式サイト')

    if ev.get('instagramUrl'):
        add(ev['instagramUrl'], 'Instagram投稿')

    if not items:
        # Google検索フォールバック
        name = ev.get('name', '')
        if not name:
            return ''
        venue = ev.get('venue', '')
        q = quote(f'{name} {venue} 2026'.strip())
        items.append((f'https://www.google.com/search?q={q}', 'Googleで検索'))

    rows = []
    for u, label in items:
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
        '{{officialLinksRows}}': make_official_links_rows(ev),
        '{{instagramSection}}': make_instagram_section(ev),
        '{{mapSection}}': make_map_section(ev),
        '{{admissionRow}}': make_admission_row(ev),
        '{{timeRow}}': make_time_row(ev),
    }

    html = template
    for key, value in replacements.items():
        html = html.replace(key, value)

    return html


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
