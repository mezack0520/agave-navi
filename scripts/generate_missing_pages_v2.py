#!/usr/bin/env python3
"""
Generate missing event detail pages using a proper placeholder-based template.
Reads events.json and index.html to find events that need pages,
then generates HTML with correct data per event.
Conditional rendering: sections with no data are omitted.
"""
import json
import os
import re
import urllib.parse
from datetime import datetime

# --- Helper functions ---

WEEKDAY_JP = ['月', '火', '水', '木', '金', '土', '日']

REGION_MAP = {
    '北海道': '北海道', '青森': '東北', '岩手': '東北', '宮城': '東北',
    '秋田': '東北', '山形': '東北', '福島': '東北',
    '茨城': '関東', '栃木': '関東', '群馬': '関東', '埼玉': '関東',
    '千葉': '関東', '東京': '関東', '神奈川': '関東',
    '新潟': '中部', '富山': '中部', '石川': '中部', '福井': '中部',
    '山梨': '中部', '長野': '中部', '岐阜': '中部', '静岡': '中部', '愛知': '中部',
    '三重': '近畿', '滋賀': '近畿', '京都': '近畿', '大阪': '近畿',
    '兵庫': '近畿', '奈良': '近畿', '和歌山': '近畿',
    '鳥取': '中国', '島根': '中国', '岡山': '中国', '広島': '中国', '山口': '中国',
    '徳島': '四国', '香川': '四国', '愛媛': '四国', '高知': '四国',
    '福岡': '九州', '佐賀': '九州', '長崎': '九州', '熊本': '九州',
    '大分': '九州', '宮崎': '九州', '鹿児島': '九州', '沖縄': '九州',
}

def format_date_jp(date_str):
    """Format date like '2026年4月4日（土）'"""
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        wd = WEEKDAY_JP[dt.weekday()]
        return f'{dt.year}年{dt.month}月{dt.day}日（{wd}）'
    except ValueError:
        return date_str

def format_date_range_jp(date_str, date_end_str):
    """Format date range like '2026年4月4日（土）〜 4月5日（日）'"""
    start = format_date_jp(date_str)
    if not date_end_str or date_end_str == date_str:
        return start
    try:
        dt_end = datetime.strptime(date_end_str, '%Y-%m-%d')
        wd_end = WEEKDAY_JP[dt_end.weekday()]
        return f'{start} 〜 {dt_end.month}月{dt_end.day}日（{wd_end}）'
    except ValueError:
        return start

def make_gcal_url(name, date_str, date_end_str, location):
    """Generate Google Calendar add event URL"""
    try:
        dt_start = datetime.strptime(date_str, '%Y-%m-%d')
        start_str = dt_start.strftime('%Y%m%d')
        if date_end_str and date_end_str != date_str:
            dt_end = datetime.strptime(date_end_str, '%Y-%m-%d')
            from datetime import timedelta
            end_str = (dt_end + timedelta(days=1)).strftime('%Y%m%d')
        else:
            from datetime import timedelta
            end_str = (dt_start + timedelta(days=1)).strftime('%Y%m%d')
        params = urllib.parse.urlencode({
            'action': 'TEMPLATE',
            'text': name,
            'dates': f'{start_str}/{end_str}',
            'location': location or '',
        })
        return f'https://calendar.google.com/calendar/render?{params}'
    except ValueError:
        return ''

def make_maps_query(location, prefecture):
    """Generate Google Maps search URL"""
    query = location or prefecture or ''
    if query:
        return f'https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(query)}'
    return ''

def make_maps_embed(location, prefecture):
    """Generate Google Maps embed URL"""
    query = location or prefecture or ''
    if query:
        return f'https://www.google.com/maps?q={urllib.parse.quote(query)}&output=embed'
    return ''

def escape_html(s):
    """Escape HTML special characters"""
    if not s:
        return ''
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


# --- Template ---

def get_html_template():
    return '''<!DOCTYPE html>
<html lang="ja">
<head>
  <!-- Google tag (gtag.js) -->
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-MKY0V1H0HY"></script>
  <script>
    window.dataLayer = window.dataLayer || [];
    function gtag(){{dataLayer.push(arguments);}}
    gtag('js', new Date());
    gtag('config', 'G-MKY0V1H0HY');
  </script>
  <meta charset="UTF-8">
  <link rel="canonical" href="https://agave-navi.com/events/{slug}.html">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{name} | アガベイベントナビ</title>
  <meta name="description" content="{meta_description}">
  <meta name="keywords" content="{name},{tags_text},アガベ,多肉植物,塊根植物,コーデックス,ビザールプランツ,即売会,イベント">
  <meta property="og:title" content="{name} | アガベイベントナビ">
  <meta property="og:description" content="{meta_description}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="https://agave-navi.com/events/{slug}.html">
  <meta property="og:image" content="https://agave-navi.com/images/ogp-default.jpg">
  <link rel="icon" type="image/svg+xml" href="../favicon.svg">
  <link rel="icon" type="image/x-icon" href="../favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="../apple-touch-icon.png">
  <link rel="stylesheet" href="../style.css?v=20260329c">
  <script type="application/ld+json">
  {{
    "@context": "https://schema.org",
    "@type": "Event",
    "name": "{name}",
    "startDate": "{date}",
    "endDate": "{date_end_or_start}",
    "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
    "eventStatus": "https://schema.org/EventScheduled",
    "location": {{
      "@type": "Place",
      "name": "{location}",
      "address": {{
        "@type": "PostalAddress",
        "addressRegion": "{prefecture}",
        "addressCountry": "JP"
      }}
    }},
    "description": "{description_escaped}",
    "organizer": {{
      "@type": "Organization",
      "name": "{organizer_or_name}"
    }}{offers_block}
  }}
  </script>
</head>
<body>

  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo">
        <span class="logo-en">AGAVE EVENT NAVI</span>
        <span class="logo-jp">アガベイベントナビ</span>
      </a>
      <a href="/listing.html" class="fav-link" id="favLink">
        <span class="fav-icon">&#10084;</span> 行きたい
        <span class="fav-count" id="favCount">0</span>
      </a>
    </div>
  </header>

  <nav class="breadcrumb" aria-label="パンくずリスト">
    <a href="/">ホーム</a> &gt;
    <a href="../{cat_slug}">{cat_label}</a> &gt;
    <span>{name}</span>
  </nav>

  <main class="detail-page">
    <div class="detail-header">
      <h1>{name}</h1>
      <div class="detail-meta">
        <span class="detail-status-badge" data-date="{date}" data-date-end="{date_end_or_start}"></span>
        <span class="detail-meta-dot"></span>
        <span class="detail-meta-item">{date_jp}</span>
        <span class="detail-meta-dot"></span>
        <span class="detail-meta-item">{prefecture}</span>
      </div>
      <div class="detail-header-actions">
        <button class="detail-fav-btn" id="favBtn" onclick="toggleFav()">
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
          </svg>
          <span id="favLabel">行きたい</span>
        </button>
      </div>
    </div>

    <div class="detail-body">
      <div class="detail-main">
        <div class="detail-section">
          <h2 class="detail-section-title">概要</h2>
          <p>{description}</p>
        </div>

{map_section}

        <div class="detail-back">
          <a href="../{cat_slug}" class="detail-back-link">{cat_label}に戻る</a>
        </div>
      </div>

      <div class="detail-sidebar">
        <div class="detail-info-card">
          <h3>EVENT INFO</h3>
          <div class="info-row">
            <span class="info-label">日時</span>
            <span class="info-value">{date_range_jp}{time_line}</span>
          </div>
{location_row}
{admission_row}
          <div class="info-row">
            <span class="info-label">カテゴリ</span>
            <span class="info-value">{tags_text}</span>
          </div>
          <div class="info-row">
            <span class="info-label">開催地域</span>
            <span class="info-value">{region}</span>
          </div>
{source_url_row}
{gcal_row}
        </div>

{instagram_section}

      </div>

      <div class="affiliate-section" id="affiliateSection"></div>
    </div>
  </main>

  <div class="ad-slot ad-slot-article-bottom" data-ad="article-bottom">
  </div>

  <div class="ad-affiliate-area" style="max-width:960px;margin:0 auto;padding:0 1rem;">
    <div class="aff-slot" data-count="5"></div>
    <div class="ad-slot">
      <span class="ad-slot-label">広告</span>
    </div>
  </div>

{correction_notice}

  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-logo">
        <span class="logo-en">AGAVE EVENT NAVI</span>
      </div>
      <nav class="footer-nav">
        <a href="/">イベント一覧</a>
        <a href="/about.html">このサイトについて</a>
        <a href="/contact.html">お問い合わせ</a>
        <a href="/disclaimer.html">免責事項</a>
        <a href="/privacy.html">プライバシーポリシー</a>
        <a href="/operator.html">運営者情報</a>
      </nav>
      <p class="footer-copy">&copy; 2025-2026 アガベイベントナビ</p>
    </div>
  </footer>

  <script src="../affiliate.js"></script>
  <script src="../status-auto.js?v=20260330b"></script>
  <script src="../ads.js"></script>
  <script>
    const SLUG = '{slug}';
    function toggleFav() {{
      let favs = JSON.parse(localStorage.getItem('favEvents') || '[]');
      const idx = favs.indexOf(SLUG);
      if (idx >= 0) {{ favs.splice(idx, 1); }}
      else {{ favs.push(SLUG); }}
      localStorage.setItem('favEvents', JSON.stringify(favs));
      updateFavUI();
    }}
    function updateFavUI() {{
      const favs = JSON.parse(localStorage.getItem('favEvents') || '[]');
      const btn = document.getElementById('favBtn');
      const label = document.getElementById('favLabel');
      if (favs.includes(SLUG)) {{
        btn.classList.add('is-fav');
        label.textContent = '行きたい！';
      }} else {{
        btn.classList.remove('is-fav');
        label.textContent = '行きたい';
      }}
      const countEl = document.getElementById('favCount');
      if (countEl) countEl.textContent = favs.length;
    }}
    updateFavUI();
  </script>
</body>
</html>'''


def generate_page(ev):
    """Generate HTML for a single event using clean placeholder template."""
    slug = ev.get('slug', '')
    name = ev.get('name', slug)
    date = ev.get('date', '')
    date_end = ev.get('dateEnd', '') or date
    date_display = ev.get('dateDisplay', '')
    location = ev.get('location', '')
    prefecture = ev.get('prefecture', '')
    region = ev.get('region', '') or REGION_MAP.get(prefecture, '')
    tags = ev.get('tags', [])
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(',')]
    tags_text = ','.join(tags) if tags else ''
    description = ev.get('description', f'{name}のイベント情報です。')
    source_url = ev.get('sourceUrl', '')
    admission = ev.get('admission', '')
    time_str = ev.get('time', '')
    organizer = ev.get('organizer', '')
    organizer_url = ev.get('organizerUrl', '')

    # Date formatting
    date_jp = format_date_jp(date)
    date_range_jp = format_date_range_jp(date, date_end if date_end != date else '')

    # Category for breadcrumb
    cat_slug = 'category/sokubai.html'
    cat_label = '即売会イベント一覧'
    if tags:
        first_tag = tags[0]
        if first_tag in ['マルシェ']:
            cat_slug = 'category/marche.html'
            cat_label = 'マルシェイベント一覧'
        elif first_tag in ['展示会']:
            cat_slug = 'category/exhibition.html'
            cat_label = '展示会一覧'
        elif first_tag in ['大型']:
            cat_slug = 'category/large.html'
            cat_label = '大型イベント一覧'

    # Meta description (truncated)
    meta_description = description[:120] if description else f'{name}のイベント情報'

    # Time line
    time_line = f'\n            {time_str}' if time_str else ''

    # Location row (conditional)
    if location:
        location_row = f'''          <div class="info-row">
            <span class="info-label">会場</span>
            <span class="info-value">{escape_html(location)}</span>
          </div>'''
    else:
        location_row = ''

    # Admission row (conditional)
    if admission:
        admission_row = f'''          <div class="info-row">
            <span class="info-label">入場料</span>
            <span class="info-value">{escape_html(admission)}</span>
          </div>'''
    else:
        admission_row = ''

    # Source URL row (conditional) - Instagram links are shown only in the
    # dedicated 公式Instagram block below, so skip them here.
    if source_url and 'instagram.com' not in source_url:
        source_label = '公式サイト'
        source_display = '公式サイト →'
        source_url_row = f'''          <div class="info-row">
            <span class="info-label">{source_label}</span>
            <span class="info-value"><a href="{escape_html(source_url)}" target="_blank" rel="noopener" style="color:var(--accent-pop);text-decoration:none">{source_display}</a></span>
          </div>'''
    else:
        source_url_row = ''

    # Google Calendar row
    gcal_url = make_gcal_url(name, date, date_end, location or prefecture)
    if gcal_url:
        gcal_row = f'''          <a href="{gcal_url}" target="_blank" rel="noopener" class="gcal-btn">
            &#128197; Googleカレンダーに追加
          </a>'''
    else:
        gcal_row = ''

    # Map section (conditional - only if location is available)
    if location:
        maps_embed = make_maps_embed(location, prefecture)
        maps_query = make_maps_query(location, prefecture)
        map_section = f'''        <div class="detail-map">
          <h2 class="detail-section-title">会場</h2>
          <div class="map-container">
            <a href="{maps_query}" target="_blank" rel="noopener" class="map-open-link">マップで開く &#8599;</a>
            <iframe src="{maps_embed}" width="100%" height="300" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
          </div>
        </div>'''
    else:
        map_section = ''

    # Instagram section (conditional - only if sourceUrl is Instagram)
    if source_url and 'instagram.com' in source_url:
        ig_handle = ''
        ig_match = re.search(r'instagram\.com/([^/?]+)', source_url)
        if ig_match:
            ig_handle = ig_match.group(1)
        if ig_handle:
            instagram_section = f'''        <div class="detail-instagram-card">
          <h3><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg> 公式Instagram</h3>
          <a href="{escape_html(source_url)}" target="_blank" rel="noopener" class="instagram-account-link">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="20" height="20" rx="5" ry="5"></rect><path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z"></path><line x1="17.5" y1="6.5" x2="17.51" y2="6.5"></line></svg>
            <span class="ig-gradient">@{escape_html(ig_handle)}</span>
          </a>
        </div>'''
        else:
            instagram_section = ''
    else:
        instagram_section = ''

    # Offers block for JSON-LD
    if admission:
        offers_block = f''',
    "offers": {{
      "@type": "Offer",
      "price": "0",
      "priceCurrency": "JPY",
      "availability": "https://schema.org/InStock",
      "description": "{escape_html(admission)}"
    }}'''
    else:
        offers_block = ''

    # Correction notice
    correction_notice = '''  <div class="correction-notice">
    <p>掲載情報はなるべく精査しておりますが、万が一誤りがある場合は申し訳ございません。お手数をおかけいたしますが、<a href="../contact.html">お問い合わせフォーム</a>からご連絡いただけますと幸いです。</p>
  </div>'''

    # Fill template
    template = get_html_template()
    html = template.format(
        slug=slug,
        name=escape_html(name),
        date=date,
        date_end_or_start=date_end or date,
        location=escape_html(location or prefecture),
        prefecture=escape_html(prefecture),
        region=escape_html(region),
        tags_text=escape_html(tags_text),
        description=escape_html(description),
        description_escaped=escape_html(description).replace('\n', ' '),
        meta_description=escape_html(meta_description),
        date_jp=date_jp,
        date_range_jp=date_range_jp,
        time_line=time_line,
        cat_slug=cat_slug,
        cat_label=cat_label,
        organizer_or_name=escape_html(organizer or name),
        offers_block=offers_block,
        map_section=map_section,
        location_row=location_row,
        admission_row=admission_row,
        source_url_row=source_url_row,
        gcal_row=gcal_row,
        instagram_section=instagram_section,
        correction_notice=correction_notice,
    )
    return html


def get_card_data(index_html, slug):
    """Extract event data from index.html card for slugs not in events.json"""
    pos = index_html.find(f'data-slug="{slug}"')
    if pos < 0:
        return None
    card_start = index_html.rfind('<div class="event-card"', 0, pos)
    attr_chunk = index_html[card_start:pos + len(slug) + 2]
    chunk = index_html[pos:pos + 2500]

    texts = []
    i = 0
    while i < len(chunk):
        gt = chunk.find('>', i)
        if gt < 0:
            break
        lt = chunk.find('<', gt)
        if lt < 0:
            break
        txt = chunk[gt + 1:lt].strip()
        if txt:
            texts.append(txt)
        i = lt

    date_m = re.search(r'data-date="([^"]+)"', attr_chunk)
    date_end_m = re.search(r'data-date-end="([^"]+)"', attr_chunk)
    pref_m = re.search(r'data-pref="([^"]+)"', attr_chunk)
    tags_m = re.search(r'data-tags="([^"]+)"', attr_chunk)

    return {
        'slug': slug,
        'name': texts[1] if len(texts) > 1 else slug,
        'date': date_m.group(1) if date_m else '',
        'dateEnd': date_end_m.group(1) if date_end_m else '',
        'dateDisplay': texts[0] if texts else '',
        'description': texts[2] if len(texts) > 2 else '',
        'prefecture': pref_m.group(1) if pref_m else '',
        'region': REGION_MAP.get(pref_m.group(1), '') if pref_m else '',
        'tags': tags_m.group(1).split(',') if tags_m else [],
    }


def main():
    # Load data
    with open('events.json', 'r', encoding='utf-8') as f:
        events = json.load(f)

    with open('index.html', 'r', encoding='utf-8') as f:
        index_html = f.read()

    # Find all slugs with cards in index.html
    card_slugs = re.findall(r'data-slug="([^"]+)"', index_html)

    # Find existing event page files
    existing_files = set()
    if os.path.isdir('events'):
        existing_files = set(
            fn.replace('.html', '')
            for fn in os.listdir('events')
            if fn.endswith('.html')
        )

    # Find missing slugs
    missing_slugs = [s for s in card_slugs if s not in existing_files]
    print(f'Missing slugs: {len(missing_slugs)}')

    if not missing_slugs:
        print('No missing pages to generate.')
        return

    os.makedirs('events', exist_ok=True)

    for slug in missing_slugs:
        # Try events.json first, then fall back to index.html card data
        ev = next((e for e in events if e['slug'] == slug), None)
        if not ev:
            ev = get_card_data(index_html, slug)
        if not ev:
            print(f'  Skipping {slug}: no data found')
            continue

        html = generate_page(ev)
        out_path = os.path.join('events', f'{slug}.html')
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'  Created: {out_path}')

    print('Done!')


if __name__ == '__main__':
    main()
