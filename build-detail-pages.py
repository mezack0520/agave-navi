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
CSS_VERSION = '20260507e'
JS_VERSION = '20260507e'

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
    venue = ev.get('venue') or ev.get('location') or ''

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
    venue = html_escape(ev.get('venue') or ev.get('location') or '')
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
        venue = ev.get('venue') or ev.get('location') or ''
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
    venue = ev.get('venue') or ev.get('location') or ''

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
        '{{enrichedContent}}': make_enriched_content(ev),
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


# ---------------------------------------------------------------------------
# Enriched content (AdSense / SEO 向け本文増強セクション)
# ---------------------------------------------------------------------------
# 目的: 各イベントページが「概要1文 + 地図 + EVENT INFO」だけだとコンテンツが薄く
#       AdSense の「有用性の低いコンテンツ」判定の原因になるため、
#       カテゴリ・地域・タグなどイベント固有のデータから生成した独自コンテンツを
#       挿入する。完全な定型文ではなく、イベントごとに表示が変わるよう設計。

GUIDE_LINKS = [
    ('agave-winter-hardiness.html', 'アガベの耐寒性ガイド: 屋外越冬できる品種と室内必須種の見分け方', 'アガベ'),
    ('agave-titanota-care.html',    'アガベ チタノタ系の管理: 美観を保ちながら長く育てるコツ',       'アガベ'),
    ('pachypodium-gracilius.html',  'パキポディウム グラキリスを枯らさない: 実生株と現地球の管理差', 'コーデックス'),
    ('caudex-intro.html',           '塊根植物(コーデックス)入門: 夏型・冬型の見分け方と選び方',     'コーデックス'),
    ('adenium-wintering.html',      'アデニウム(砂漠の薔薇)の冬越し完全ガイド: 種類別の温度管理',   'コーデックス'),
    ('wintering-tokyo.html',        '東京近郊での冬越し: 練馬から学ぶ屋外・軒下・不織布・室内の使い分け', '管理'),
    ('failure-analysis.html',       '失敗から学ぶ塊根管理: 過去に枯らした植物と原因分析',           '管理'),
    ('sokubaikai-tips.html',        '植物即売会で失敗しないチェックリスト: 当日の流れと買付けのコツ', '購入'),
]

CATEGORY_INTROS = {
    '即売会': (
        '即売会は、複数の生産者・販売店が一堂に集まり、その場で植物を購入できる '
        'スタイルのイベントです。通信販売では出会えない一点物の選抜株や、'
        '生産者と直接話しながら株の特徴・育成歴を聞ける機会として、'
        'アガベ・塊根植物・多肉植物の愛好家にとって重要な仕入れの場になっています。'
        '希少な株は開場前の整理券配布で先着順になることが多く、'
        '人気生産者のブース前は開場直後から行列ができる傾向があります。'
    ),
    'マルシェ': (
        '植物マルシェは、即売会よりもカジュアルな雰囲気で、'
        '飲食やワークショップなどと併催されることが多いイベント形式です。'
        '出店者は園芸店、生産者、個人作家、鉢メーカーなど多彩で、'
        '植物本体だけでなく鉢・用土・小物・園芸書まで一度に揃えられるのが魅力。'
        '家族連れでも立ち寄りやすく、はじめて多肉植物・塊根植物に触れる人の'
        '入り口としても向いています。'
    ),
    '展示会': (
        '展示会は販売よりも「観賞」と「情報交換」が中心のイベントです。'
        '長年の愛好家が育てた銘品株、コンテスト出品株、稀少な分類群の'
        '実物を見られる貴重な機会で、写真では伝わらないサイズ感・葉の質感・'
        '株姿の作り込みを学ぶ場として活用できます。会期中に行われる'
        '解説会・分類トークも、栽培知識を深めるきっかけになります。'
    ),
    '大型イベント': (
        '大型イベントは複数日にわたって開催される、出店者数・来場者数とも'
        '最大級のイベントです。1日では回り切れない規模のため、'
        '事前に出店者一覧と会場マップを確認して目的のブースをマーキングしておくと'
        '効率的に回れます。海外バイヤーや遠方の生産者が出店することも多く、'
        '通常の即売会では入手しづらい選抜株・輸入株に出会える可能性が高まります。'
    ),
    '展示販売会': (
        '展示販売会は、観賞向けの展示と即売を組み合わせた中規模イベントです。'
        '見て学べる + その場で買える、というハイブリッドな構成で、'
        '初心者から中・上級者まで幅広く楽しめます。'
        '銘品株の解説を聞きながら、近い系統の入手可能株を探せるのが大きな利点です。'
    ),
    '講演': (
        '講演・トークイベントは、生産者や愛好家が長年の栽培・採集経験を'
        '直接共有する場です。本やネット記事には載らない「現場の知見」'
        '— 失敗事例、地域別の管理差、流通の裏側 — を聞ける貴重な機会で、'
        '中・上級者の栽培レベルを一段引き上げてくれます。'
    ),
}

def detect_primary_category(ev):
    """tags から主カテゴリを判定して、CATEGORY_INTROS のキーを返す。"""
    tags = ev.get('tags') or []
    priority = ['大型イベント', '展示販売会', '展示会', '講演', 'マルシェ', '即売会']
    for p in priority:
        if p in tags:
            return p
    return '即売会'

def make_category_intro(ev):
    cat = detect_primary_category(ev)
    intro = CATEGORY_INTROS.get(cat, CATEGORY_INTROS['即売会'])
    return (
        f'        <div class="detail-section detail-enriched">\n'
        f'          <h2 class="detail-section-title">{html_escape(cat)}とは — このイベントの楽しみ方</h2>\n'
        f'          <p>{html_escape(intro)}</p>\n'
        f'        </div>\n'
    )

def make_visit_tips(ev):
    """カテゴリ + admission/time/会場で来場時のヒントを動的生成。"""
    cat = detect_primary_category(ev)
    region = ev.get('region') or ''
    pref = ev.get('prefecture') or ''
    venue = ev.get('venue') or ''
    admission = (ev.get('admission') or '').strip()
    time_str = (ev.get('time') or '').strip()
    is_free = '無料' in admission

    tips = []

    if cat == '即売会':
        tips.append('開場前に整理券配布や入場列が発生することが多い即売会形式です。目当ての生産者がある場合は、開場の60〜90分前到着を見込んでおくと安心です。')
        tips.append('株を運ぶ大きめのトートバッグ・苗運搬用の段ボール・即時会計に備えた小銭/小額紙幣・財布の準備をおすすめします。人気株は即決が必要なため、価格帯の上限を事前に決めておくと迷いません。')
    elif cat == 'マルシェ':
        tips.append('カジュアルな雰囲気のマルシェは、滞在時間が長くなる傾向があります。飲食ブースが併設されることも多いので、空きスケジュールで半日確保しておくとゆっくり回れます。')
        tips.append('鉢・用土・小物などの周辺アイテムも豊富に揃うため、欲しい鉢のサイズメモや既存株の写真を持参すると、組み合わせ買いがスムーズです。')
    elif cat == '展示会':
        tips.append('展示中心のイベントは販売株が限られる場合があるため、購入目的というよりは「銘品を観察する・育成のヒントを得る」視点で時間を確保するのがおすすめです。')
        tips.append('カメラ・メモ帳・スマホの十分な空き容量を準備し、気になる株のラベル(品種名・出品者)を必ず控えておくと、後日の調査・購入検討に役立ちます。')
    elif cat == '大型イベント':
        tips.append('複数日開催・出店者多数の大型イベントは、事前に公式の出店者一覧・会場マップを確認して、回るルートを決めてから来場するのが効率的です。')
        tips.append('1日では回り切れない規模が多いため、初日午前で全体を俯瞰 → 2日目で目的の株を購入、という2回入場プランも有効です。半券・リストバンドの保管にご注意ください。')
    else:
        tips.append('開場時間・閉場時間・整理券の有無は主催者の公式情報を直前に再確認することをおすすめします。雨天や天候による会期変更にも備えて、当日朝の最新告知をチェックしてください。')

    if region:
        tips.append(
            f'会場は{html_escape(pref or region)}({html_escape(venue or "会場")})です。'
            '公共交通機関でのアクセスを基本に、休日の駐車場混雑・周辺道路の規制情報も'
            '合わせて確認しておくと当日のスケジュールが組みやすくなります。'
        )

    if is_free:
        tips.append('入場料は無料の予定ですが、会場運営費・出店者への支援としての協賛・カンパ箱が設置されることもあります。気持ちのよい形で楽しめるよう、小銭を多めに用意しておくのがおすすめです。')
    elif admission:
        tips.append(f'入場料は「{html_escape(admission)}」の予定です。前売り・当日券の差や、リピート入場のルールも公式情報でご確認ください。')

    if time_str:
        tips.append(f'開催時間は{html_escape(time_str)}の予定です。人気株は開場直後に流通することが多いため、購入目的の場合は開場時刻を基準にスケジュールを組んでください。')

    lis = '\n'.join(f'          <li>{t}</li>' for t in tips)
    return (
        f'        <div class="detail-section detail-enriched">\n'
        f'          <h2 class="detail-section-title">来場前のチェックリスト</h2>\n'
        f'          <ul class="visit-tips-list">\n{lis}\n          </ul>\n'
        f'        </div>\n'
    )

def make_related_guides(ev):
    """タグ + イベント名から関連度を付けて、関連ガイド記事を 4件選定。"""
    tags = ev.get('tags') or []
    name = ev.get('name', '')

    scored = []
    for path, title, gcat in GUIDE_LINKS:
        score = 0
        if gcat in tags:
            score += 10
        if 'アガベ' in name and 'アガベ' in gcat:
            score += 5
        if ('パキポ' in name or 'グラキリス' in name) and 'パキポ' in title:
            score += 8
        if 'アデニウム' in name and 'アデニウム' in title:
            score += 8
        if ('コーデックス' in name or '塊根' in name) and gcat == 'コーデックス':
            score += 5
        if '即売' in name and '即売' in title:
            score += 6
        scored.append((score, path, title))
    scored.sort(reverse=True)
    top = scored[:4]
    if all(s == 0 for s, _, _ in top):
        slug = ev.get('slug', '')
        offset = (sum(ord(c) for c in slug) % len(GUIDE_LINKS))
        rotated = GUIDE_LINKS[offset:] + GUIDE_LINKS[:offset]
        top = [(0, p, t) for p, t, _ in rotated[:4]]

    items = []
    for _, path, title in top:
        items.append(f'            <li><a href="/guides/{path}">{html_escape(title)}</a></li>')
    items_html = '\n'.join(items)

    return (
        f'        <div class="detail-section detail-enriched">\n'
        f'          <h2 class="detail-section-title">あわせて読みたい栽培ガイド</h2>\n'
        f'          <p>このイベントで出会える植物の管理に役立つ、本サイト独自の栽培ガイド記事をピックアップしています。'
        f'購入後の長期管理を見据えて、来場前に目を通しておくとイベント当日の判断がスムーズになります。</p>\n'
        f'          <ul class="related-guides-list">\n{items_html}\n          </ul>\n'
        f'          <p class="related-guides-more"><a href="/guides/">栽培ガイド一覧を見る →</a></p>\n'
        f'        </div>\n'
    )

def make_site_mission_section():
    return (
        '        <div class="detail-section detail-enriched detail-mission">\n'
        '          <h2 class="detail-section-title">アガベイベントナビについて</h2>\n'
        '          <p>本サイトは、アガベ・塊根植物(コーデックス)・多肉植物・ビザールプランツの即売会・マルシェ・大型展示会の情報を、'
        '東京・練馬を拠点とする一個人愛好家(栽培歴8年/参加歴6年)が一次情報を中心に確認・編集してまとめています。'
        '掲載情報は主催者公式・SNS・直接確認を経て掲載しており、日付・会場・入場料に変更があった場合は速やかに更新するよう運営しています。'
        '誤りを発見された場合は<a href="/contact.html">お問い合わせフォーム</a>からご連絡いただけますと幸いです。</p>\n'
        '        </div>\n'
    )

def make_enriched_content(ev):
    return (
        make_category_intro(ev)
        + make_visit_tips(ev)
        + make_related_guides(ev)
        + make_site_mission_section()
    )


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
