#!/usr/bin/env python3
"""
One-shot migration over events/*.html:

1. Category-based breadcrumb -> area (region) breadcrumb (visible HTML + JSON-LD).
2. Drop the "カテゴリ" info-row from the sidebar.
3. Drop the "{cat}に戻る" detail-back link, replace with area-based back link.
4. Inject an Instagram <iframe> embed when events.json provides an instagramUrl
   matching /p/ or /reel/ for that slug.

Idempotent: rerunning is safe.
"""
import json
import re
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVENTS_JSON = ROOT / 'events.json'
EVENTS_DIR = ROOT / 'events'

REGION_BY_PREF = {
    '北海道': '北海道',
    '青森': '東北', '岩手': '東北', '宮城': '東北', '秋田': '東北', '山形': '東北', '福島': '東北',
    '茨城': '関東', '栃木': '関東', '群馬': '関東', '埼玉': '関東', '千葉': '関東', '東京': '関東', '神奈川': '関東',
    '愛知': '東海', '静岡': '東海', '岐阜': '東海', '三重': '東海',
    '新潟': '北陸', '富山': '北陸', '石川': '北陸', '福井': '北陸', '山梨': '北陸', '長野': '北陸',
    '滋賀': '関西', '京都': '関西', '大阪': '関西', '兵庫': '関西', '奈良': '関西', '和歌山': '関西',
    '鳥取': '中国', '島根': '中国', '岡山': '中国', '広島': '中国', '山口': '中国',
    '徳島': '四国', '香川': '四国', '愛媛': '四国', '高知': '四国',
    '福岡': '九州', '佐賀': '九州', '長崎': '九州', '熊本': '九州', '大分': '九州', '宮崎': '九州', '鹿児島': '九州', '沖縄': '九州',
}

IG_POST_RE = re.compile(r'^https?://(?:www\.)?instagram\.com/(?:p|reel)/[^/?#]+/?', re.IGNORECASE)


def html_escape(s: str) -> str:
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def load_events():
    with open(EVENTS_JSON, 'r', encoding='utf-8') as f:
        events = json.load(f)
    by_slug = {e['slug']: e for e in events if 'slug' in e}
    return by_slug


def get_region(event):
    if event.get('region'):
        return event['region']
    pref = (event.get('prefecture') or '').strip()
    for k, v in REGION_BY_PREF.items():
        if k in pref:
            return v
    return ''


def area_link(region):
    if region:
        return (
            f'{region}のイベント',
            f'/?region={urllib.parse.quote(region)}',
            f'https://agave-navi.com/?region={urllib.parse.quote(region)}',
        )
    return ('イベント一覧', '/', 'https://agave-navi.com/')


def fallback_region_from_html(html: str) -> str:
    m = re.search(r'<span class="info-label">開催地域</span>\s*<span class="info-value">([^<]+)</span>', html)
    if m:
        return m.group(1).strip()
    return ''


def replace_visible_breadcrumb(html: str, area_label: str, area_href: str) -> str:
    """Replace the category breadcrumb anchor with an area anchor."""
    pattern = re.compile(
        r'(<nav class="breadcrumb"[^>]*>\s*<a[^>]*>ホーム</a>\s*&gt;\s*)<a href="\.\./category/[^"]+"[^>]*>[^<]+</a>'
    )
    new_html, n = pattern.subn(
        lambda m: m.group(1) + f'<a href="{html_escape(area_href)}">{html_escape(area_label)}</a>',
        html,
        count=1,
    )
    if n:
        return new_html

    # Older-style single-line breadcrumb (from generate_event_page.py)
    pattern2 = re.compile(
        r'(<div class="breadcrumb">\s*<a href="/">ホーム</a>\s*&gt;\s*)<a href="\.\./category/[^"]+\.html">[^<]+</a>'
    )
    new_html, n = pattern2.subn(
        lambda m: m.group(1) + f'<a href="{html_escape(area_href)}">{html_escape(area_label)}</a>',
        html,
        count=1,
    )
    return new_html


def replace_jsonld_breadcrumb(html: str, area_label: str, area_url: str) -> str:
    """Update position-2 of the BreadcrumbList structured data."""
    pattern = re.compile(
        r'("@type":\s*"ListItem",\s*"position":\s*2,\s*"name":\s*")[^"]+(",\s*"item":\s*")https://agave-navi\.com/category/[^"]+(")',
        re.DOTALL,
    )
    return pattern.sub(rf'\g<1>{area_label}\g<2>{area_url}\g<3>', html, count=1)


def replace_detail_back(html: str, area_label: str, area_href: str) -> str:
    pattern = re.compile(
        r'<a href="\.\./category/[^"]+" class="detail-back-link">[^<]+</a>'
    )
    return pattern.sub(
        f'<a href="{html_escape(area_href)}" class="detail-back-link">{html_escape(area_label)}に戻る</a>',
        html,
        count=1,
    )


CATEGORY_INFO_ROW_RE = re.compile(
    r'\n\s*<div class="info-row">\s*<span class="info-label">カテゴリ</span>\s*<span class="info-value">[^<]*</span>\s*</div>'
)


def remove_category_info_row(html: str) -> str:
    return CATEGORY_INFO_ROW_RE.sub('', html)


def inject_instagram_embed(html: str, instagram_url: str) -> str:
    """Insert an Instagram embed iframe block before the detail-back div, if missing."""
    if not instagram_url or not IG_POST_RE.match(instagram_url):
        return html
    if 'detail-instagram-embed' in html:  # already injected
        return html
    embed_url = instagram_url.rstrip('/') + '/embed/'
    block = (
        f'\n        <div class="detail-section detail-instagram-embed">\n'
        f'          <h2 class="detail-section-title">Instagram投稿</h2>\n'
        f'          <div class="instagram-embed-wrap">\n'
        f'            <iframe src="{html_escape(embed_url)}" loading="lazy" frameborder="0" '
        f'scrolling="no" allowtransparency="true" allowfullscreen></iframe>\n'
        f'          </div>\n'
        f'          <p class="instagram-embed-link"><a href="{html_escape(instagram_url)}" '
        f'target="_blank" rel="noopener">Instagramで見る ↗</a></p>\n'
        f'        </div>\n'
    )
    # Prefer to insert before the detail-back container so it sits at the bottom of main content.
    needle = '<div class="detail-back">'
    idx = html.find(needle)
    if idx >= 0:
        # back up to start of preceding line of whitespace
        line_start = html.rfind('\n', 0, idx)
        if line_start < 0:
            line_start = idx
        return html[:line_start] + block + html[line_start:]
    # Fallback: append before closing of detail-main
    return html.replace('</div>\n      </div>\n\n      <div class="detail-sidebar">', block + '      </div>\n\n      <div class="detail-sidebar">', 1)


def migrate_file(path: Path, by_slug: dict) -> bool:
    slug = path.stem
    original = path.read_text(encoding='utf-8')
    html = original

    event = by_slug.get(slug, {})
    region = get_region(event) or fallback_region_from_html(html)
    area_label, area_href, area_url = area_link(region)

    html = replace_visible_breadcrumb(html, area_label, area_href)
    html = replace_jsonld_breadcrumb(html, area_label, area_url)
    html = replace_detail_back(html, area_label, area_href)
    html = remove_category_info_row(html)

    instagram_url = event.get('instagramUrl', '')
    html = inject_instagram_embed(html, instagram_url)

    if html != original:
        path.write_text(html, encoding='utf-8')
        return True
    return False


def main():
    by_slug = load_events()
    pages = sorted(EVENTS_DIR.glob('*.html'))
    changed = 0
    for p in pages:
        if migrate_file(p, by_slug):
            changed += 1
    print(f'Migrated {changed} / {len(pages)} event pages')


if __name__ == '__main__':
    main()
