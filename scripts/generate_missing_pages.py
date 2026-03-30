#!/usr/bin/env python3
"""
events.json内のイベントでHTMLファイルが存在しないものを一括生成するスクリプト
"""
import json
import os
import sys
import re
import urllib.parse
from datetime import datetime

def format_date_japanese(date_str, end_date_str=None):
    days = ['月', '火', '水', '木', '金', '土', '日']
    d = datetime.strptime(date_str, '%Y-%m-%d')
    day_name = days[d.weekday()]
    result = f'{d.year}年{d.month}月{d.day}日（{day_name}）'
    if end_date_str and end_date_str != date_str:
        d2 = datetime.strptime(end_date_str, '%Y-%m-%d')
        day_name2 = days[d2.weekday()]
        result += f'-{d2.day}日（{day_name2}）'
    return result

def get_region_from_prefecture(pref):
    mapping = {
        '北海道': '北海道', '青森': '東北', '岩手': '東北', '宮城': '東北',
        '秋田': '東北', '山形': '東北', '福島': '東北', '茨城': '関東',
        '栃木': '関東', '群馬': '関東', '埼玉': '関東', '千葉': '関東',
        '東京': '関東', '神奈川': '関東', '新潟': '中部', '富山': '中部',
        '石川': '中部', '福井': '中部', '山梨': '中部', '長野': '中部',
        '岐阜': '中部', '静岡': '中部', '愛知': '中部', '三重': '関西',
        '滋賀': '関西', '京都': '関西', '大阪': '関西', '兵庫': '関西',
        '奈良': '関西', '和歌山': '関西', '鳥取': '中国', '島根': '中国',
        '岡山': '中国', '広島': '中国', '山口': '中国', '徳島': '四国',
        '香川': '四国', '愛媛': '四国', '高知': '四国', '福岡': '九州',
        '佐賀': '九州', '長崎': '九州', '熊本': '九州', '大分': '九州',
        '宮崎': '九州', '鹿児島': '九州', '沖縄': '九州',
    }
    for key, region in mapping.items():
        if key in pref:
            return region
    return '関東'

def generate_detail_page(event):
    slug = event['slug']
    name = event['name']
    date_str = event['date']
    end_date = event.get('dateEnd', date_str)
    prefecture = event.get('prefecture', '')
    location = event.get('location', prefecture)
    description = event.get('description', f'{name}は{prefecture}で開催される植物イベントです。')
    tags_list = event.get('tags', ['即売会'])
    tags_str = ','.join(tags_list) if isinstance(tags_list, list) else tags_list
    primary_tag = tags_list[0] if isinstance(tags_list, list) and tags_list else '即売会'
    admission = event.get('admission', '詳細は公式サイトをご確認ください')
    source_url = event.get('sourceUrl', '')

    date_jp = format_date_japanese(date_str, end_date if end_date != date_str else None)
    meta_desc = description[:120] if len(description) > 120 else description

    cat_map = {
        '即売会': ('sokubaikai', '即売会一覧'),
        '大型': ('large', '大型イベント一覧'),
        'マルシェ': ('marche', 'マルシェ一覧'),
        '展示会': ('exhibition', '展示会一覧'),
    }
    cat_slug, cat_label = cat_map.get(primary_tag, ('sokubaikai', '即売会一覧'))

    address = f'{prefecture}県 {location}' if prefecture and location != prefecture else (prefecture or location or '')
    maps_q = urllib.parse.quote(address)
    maps_embed = f'https://maps.google.com/maps?q={maps_q}&output=embed'

    start_iso = f'{date_str}T10:00:00+09:00'
    end_iso = f'{end_date or date_str}T18:00:00+09:00'

    gcal_params = urllib.parse.urlencode({
        'action': 'TEMPLATE',
        'text': name,
        'dates': f'{date_str.replace("-","")}T090000/{(end_date or date_str).replace("-","")}T170000',
        'location': address,
        'details': f'{name} - アガベイベントナビ https://agave-navi.com/'
    })
    gcal_url = f'https://calendar.google.com/calendar/render?{gcal_params}'

    official_link = ''
    if source_url:
        official_link = f"""
            <div class="info-row">
              <span class="info-label">公式</span>
              <span class="info-value"><a href="{source_url}" target="_blank" rel="noopener" style="color:var(--accent-pop);text-decoration:none">公式サイト →</a></span>
            </div>"""

    instagram_block = ''

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-NKY8V1H8HY"></script>
<script>
window.dataLayer = window.dataLayer || [];
function gtag(){{dataLayer.push(arguments);}}
gtag('js', new Date());
gtag('config', 'G-NKY8V1H8HY');
</script>
<meta name="google-site-verification" content="23j_bxcczlGhWRVrlfh94HO0hYGk9qxQzfbew60oWB0" />
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{name} | アガベイベントナビ</title>
<meta name="description" content="{meta_desc}">
<meta property="og:title" content="{name}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="https://agave-navi.com/events/{slug}.html">
<meta property="og:image" content="https://agave-navi.com/images/ogp-default.jpg">
<link rel="icon" type="image/svg+xml" href="../favicon.svg">
<link rel="icon" type="image/x-icon" href="../favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="../apple-touch-icon.png">
<link rel="stylesheet" href="../style.css?v=20260329c">
</head>
<body>
<header class="header">
  <div class="header-inner">
    <a href="/" class="logo">
      <span class="logo-en">AGAVE EVENT NAVI</span>
      <span class="logo-jp">アガベイベントナビ</span>
    </a>
    <div class="header-actions">
      <a href="../ikitai.html" class="ikitai-blob-btn" id="ikitaiBlobBtn">
        <span class="blob-bg"></span>
        <svg class="ikitai-heart" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
        <span class="ikitai-label">行きたい</span>
        <span class="ikitai-badge" id="ikitaiBadge"></span>
      </a>
      <button class="menu-toggle" id="menuToggle" aria-label="メニュー">
        <span></span><span></span><span></span>
      </button>
    </div>
  </div>
</header>
<nav class="nav-overlay" id="navOverlay">
  <div class="nav-overlay-inner">
    <a href="/">ホーム</a>
    <a href="../calendar.html">カレンダー</a>
    <a href="../map.html">マップ</a>
    <a href="../about.html">サイトについて</a>
    <a href="../contact.html">お問い合わせ</a>
    <a href="../listing.html">掲載申請</a>
    <a href="https://www.instagram.com/m.z.plants/" target="_blank">INSTAGRAM</a>
    <a href="../ikitai.html" class="nav-ikitai-link"><svg class="ikitai-heart" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg> 行きたいリスト</a>
  </div>
</nav>
<div class="breadcrumb">
  <a href="/">ホーム</a> &gt; <a href="../category/{cat_slug}.html">{cat_label}</a> &gt; {name}
</div>
<main class="detail-page">
  <div class="detail-header">
    <h1>{name}</h1>
    <div class="detail-meta">
      <span class="detail-status-badge" data-date="{date_str}">開催予定</span>
      <span class="detail-meta-dot"></span>
      <span class="detail-meta-item">{date_jp}</span>
      <span class="detail-meta-dot"></span>
      <span class="detail-meta-item">{prefecture}</span>
    </div>
    <div class="detail-header-actions">
      <button class="detail-fav-btn" id="favBtn" onclick="toggleFav()">
        <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
        <span id="favLabel">行きたい</span>
      </button>
    </div>
  </div>
  <div class="detail-body">
    <div class="detail-main">
      <div class="detail-section">
        <h2 class="detail-section-title">イベント概要</h2>
        <p>{description}</p>
        <p>詳細な日程や出店者情報は、主催者の公式情報をご確認ください。</p>
      </div>
      <div class="detail-map">
        <h2 class="detail-section-title">会場</h2>
        <iframe src="{maps_embed}" width="100%" height="280" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
      </div>
      <div class="detail-back">
        <a href="../category/{cat_slug}.html" class="detail-back-link">← {cat_label}に戻る</a>
      </div>
    </div>
    <div class="detail-sidebar">
      <div class="detail-info-card">
        <h3>EVENT INFO</h3>
        <div class="info-row">
          <span class="info-label">日時</span>
          <span class="info-value">{date_jp}</span>
        </div>
        <div class="info-row">
          <span class="info-label">会場</span>
          <span class="info-value">{location}</span>
        </div>
        <div class="info-row">
          <span class="info-label">入場料</span>
          <span class="info-value">{admission}</span>
        </div>
        <div class="info-row">
          <span class="info-label">カテゴリ</span>
          <span class="info-value">{primary_tag}</span>
        </div>{official_link}
        <a href="{gcal_url}" target="_blank" rel="noopener" class="gcal-btn">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
          Googleカレンダーに追加
        </a>
      </div>{instagram_block}
      <div class="affiliate-section" data-tags="{primary_tag}"></div>
    </div>
  </div>
</main>
<div class="ad-slot ad-slot-article-bottom" data-ad="article-bottom"></div>
<div class="ad-affiliate-area" style="max-width:960px;margin:0 auto;padding:0 1rem;">
  <div class="aff-slot" data-count="5"></div>
</div>
<div class="correction-notice">
  <p>掲載情報はなるべく精査しておりますが、万が一誤りがある場合は申し訳ございません。お手数をおかけいたしますが、<a href="../contact.html">お問い合わせフォーム</a>からご連絡いただけますと幸いです。</p>
</div>
<footer class="footer">
  <div class="footer-inner">
    <div class="footer-logo"><span class="logo-en">AGAVE EVENT NAVI</span></div>
    <nav class="footer-nav">
      <a href="../about.html">サイトについて</a>
      <a href="../calendar.html">カレンダー</a>
      <a href="../map.html">マップ</a>
      <a href="../privacy.html">プライバシーポリシー</a>
      <a href="../terms.html">利用規約</a>
      <a href="../disclaimer.html">免責事項</a>
      <a href="../operator.html">運営者情報</a>
      <a href="../contact.html">お問い合わせ</a>
      <a href="../listing.html">掲載申請</a>
      <a href="https://www.instagram.com/m.z.plants/" target="_blank">INSTAGRAM</a>
    </nav>
    <p class="footer-copy">&copy; 2026 AGAVE EVENT NAVI</p>
  </div>
</footer>
<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "Event",
  "name": "{name}",
  "description": "{meta_desc}",
  "startDate": "{start_iso}",
  "endDate": "{end_iso}",
  "location": {{
    "@type": "Place",
    "name": "{location}",
    "address": {{
      "@type": "PostalAddress",
      "addressCountry": "JP",
      "addressRegion": "{prefecture}"
    }}
  }},
  "eventStatus": "https://schema.org/EventScheduled",
  "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
  "isAccessibleForFree": true
}}
</script>
<script>
const toggle = document.getElementById('menuToggle');
const overlay = document.getElementById('navOverlay');
toggle.addEventListener('click', () => {{
  toggle.classList.toggle('active');
  overlay.classList.toggle('active');
  document.body.classList.toggle('no-scroll');
}});
overlay.querySelectorAll('a').forEach(link => {{
  link.addEventListener('click', () => {{
    toggle.classList.remove('active');
    overlay.classList.remove('active');
    document.body.classList.remove('no-scroll');
  }});
}});
</script>
<script>
const slug = location.pathname.split('/').pop().replace('.html','');
function getFavs() {{ try {{ return JSON.parse(localStorage.getItem('aen_favs') || '[]'); }} catch(e) {{ return []; }} }}
function toggleFav() {{
  let favs = getFavs();
  const idx = favs.indexOf(slug);
  if (idx > -1) {{ favs.splice(idx, 1); }} else {{ favs.push(slug); }}
  localStorage.setItem('aen_favs', JSON.stringify(favs));
  updateFavBtn();
}}
function updateFavBtn() {{
  const btn = document.getElementById('favBtn');
  const label = document.getElementById('favLabel');
  if (!btn || !label) return;
  const isFav = getFavs().includes(slug);
  btn.classList.toggle('is-fav', isFav);
  label.textContent = isFav ? '行きたい登録済み' : '行きたい';
  var b = document.getElementById('ikitaiBadge');
  if (b) {{ var favs = getFavs(); b.textContent = favs.length > 0 ? favs.length : ''; b.classList.toggle('has-count', favs.length > 0); }}
}}
updateFavBtn();
</script>
<script>
(function(){{
  var b = document.getElementById('ikitaiBadge');
  if (!b) return;
  try {{ var favs = JSON.parse(localStorage.getItem('aen_favs') || '[]');
    if (favs.length > 0) {{ b.textContent = favs.length; b.classList.add('has-count'); }}
  }} catch(e) {{}}
}})();
</script>
<script src="../affiliate.js"></script>
<script src="../status-auto.js?v=20260328"></script>
<script src="../ads.js"></script>
</body>
</html>"""
    return html

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    events_json = os.path.join(base_dir, 'events.json')
    events_dir = os.path.join(base_dir, 'events')

    with open(events_json, 'r', encoding='utf-8') as f:
        events = json.load(f)

    existing = set(f.replace('.html', '') for f in os.listdir(events_dir) if f.endswith('.html'))
    missing = [e for e in events if e['slug'] not in existing]

    print(f'Total events: {len(events)}')
    print(f'Existing pages: {len(existing)}')
    print(f'Missing pages: {len(missing)}')

    for event in missing:
        slug = event['slug']
        html = generate_detail_page(event)
        path = os.path.join(events_dir, f'{slug}.html')
        with open(path, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f'  Created: events/{slug}.html')

    print(f'\nDone! Generated {len(missing)} pages.')

if __name__ == '__main__':
    main()
