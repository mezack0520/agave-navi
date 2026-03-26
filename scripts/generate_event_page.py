#!/usr/bin/env python3
"""
自動イベントページ生成スクリプト
Google Form → GitHub Actions → このスクリプト → events/*.html + index.html カード追加
"""

import json
import os
import re
import sys
import urllib.parse
from datetime import datetime


def slugify(text):
    """日本語テキストからURL用スラッグを生成"""
    # 英数字とハイフン以外を除去、スペースをハイフンに
    slug = re.sub(r'[^\w\s-]', '', text.lower())
    slug = re.sub(r'[\s_]+', '-', slug).strip('-')
    # 日本語の場合はローマ字変換せず、年月を使ったスラッグを生成
    if not slug or len(slug) < 3:
        slug = f"event-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    return slug


def make_gcal_url(name, start_date, end_date, venue, address, url):
    """Googleカレンダー追加URLを生成"""
    start = start_date.replace('-', '') + 'T090000'
    end = (end_date or start_date).replace('-', '') + 'T170000'
    params = {
        'action': 'TEMPLATE',
        'text': name,
        'dates': f'{start}/{end}',
        'location': f'{venue}, {address}',
        'details': f'{name} - アガベイベントナビ https://agave-navi.com/'
    }
    return 'https://calendar.google.com/calendar/render?' + urllib.parse.urlencode(params)


def make_maps_embed(address):
    """Google Maps埋め込みURLを生成"""
    return f'https://maps.google.com/maps?q={urllib.parse.quote(address)}&output=embed'


def format_date_japanese(date_str, end_date_str=None):
    """日付を日本語表記にフォーマット"""
    days = ['月', '火', '水', '木', '金', '土', '日']
    d = datetime.strptime(date_str, '%Y-%m-%d')
    day_name = days[d.weekday()]
    result = f'{d.year}年{d.month}月{d.day}日（{day_name}）'
    if end_date_str and end_date_str != date_str:
        d2 = datetime.strptime(end_date_str, '%Y-%m-%d')
        day_name2 = days[d2.weekday()]
        result += f'-{d2.day}日（{day_name2}）'
    return result


def format_date_short(date_str, end_date_str=None):
    """日付を短縮表記（カード用）"""
    d = datetime.strptime(date_str, '%Y-%m-%d')
    result = f'{d.year}.{d.month:02d}.{d.day:02d}'
    if end_date_str and end_date_str != date_str:
        d2 = datetime.strptime(end_date_str, '%Y-%m-%d')
        result += f'-{d2.day:02d}'
    return result


def get_region_from_prefecture(pref):
    """都道府県から地域を判定"""
    mapping = {
        '北海道': '北海道', '青森': '東北', '岩手': '東北', '宮城': '東北',
        '秋田': '東北', '山形': '東北', '福島': '東北',
        '茨城': '関東', '栃木': '関東', '群馬': '関東', '埼玉': '関東',
        '千葉': '関東', '東京': '関東', '神奈川': '関東',
        '新潟': '中部', '富山': '中部', '石川': '中部', '福井': '中部',
        '山梨': '中部', '長野': '中部', '岐阜': '中部', '静岡': '中部', '愛知': '中部',
        '三重': '関西', '滋賀': '関西', '京都': '関西', '大阪': '関西',
        '兵庫': '関西', '奈良': '関西', '和歌山': '関西',
        '鳥取': '中国', '島根': '中国', '岡山': '中国', '広島': '中国', '山口': '中国',
        '徳島': '四国', '香川': '四国', '愛媛': '四国', '高知': '四国',
        '福岡': '九州', '佐賀': '九州', '長崎': '九州', '熊本': '九州',
        '大分': '九州', '宮崎': '九州', '鹿児島': '九州', '沖縄': '九州',
    }
    for key, region in mapping.items():
        if key in pref:
            return region
    return '関東'


def get_short_pref(address):
    """住所から短い都道府県名を取得"""
    m = re.match(r'(..?[都道府県])', address)
    if m:
        return m.group(1).replace('県', '').replace('府', '').replace('都', '')
    return ''


def generate_detail_page(data):
    """イベント詳細ページHTMLを生成"""
    name = data['name']
    slug = data.get('slug') or slugify(name)
    date_str = data['date']
    end_date = data.get('end_date', date_str)
    venue = data['venue']
    address = data['address']
    prefecture = data.get('prefecture', '')
    description = data['description']
    admission = data.get('admission', '詳細は公式サイトをご確認ください')
    category = data.get('category', '即売会')
    tags = data.get('tags', category)
    official_url = data.get('official_url', '')
    organizer = data.get('organizer', '')

    date_jp = format_date_japanese(date_str, end_date)
    region = get_region_from_prefecture(prefecture or address)
    short_pref = get_short_pref(prefecture or address)
    gcal_url = make_gcal_url(name, date_str, end_date, venue, address, official_url)
    maps_embed = make_maps_embed(address)
    meta_desc = description[:120] if len(description) > 120 else description

    # カテゴリからパンくず用のカテゴリスラッグを推定
    cat_map = {
        '即売会': ('sokubaikai', '即売会一覧'),
        '大型': ('large', '大型イベント一覧'),
        'マルシェ': ('marche', 'マルシェ一覧'),
        '展示会': ('exhibition', '展示会一覧'),
    }
    primary_cat = category.split(',')[0].strip() if ',' in category else category
    cat_slug, cat_label = cat_map.get(primary_cat, ('sokubaikai', '即売会一覧'))

    # 構造化データ用の日時
    start_iso = f'{date_str}T10:00:00+09:00'
    end_iso = f'{end_date}T18:00:00+09:00'

    # 住所分解
    addr_region = prefecture or ''
    addr_local = address.replace(addr_region, '').strip() if addr_region else address

    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<!-- Google tag (gtag.js) -->
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
    <link rel="stylesheet" href="../style.css?v=20260326">
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
        <a href="/">ホーム</a> &gt; <a href="../category/{cat_slug}.html">{cat_label}</a> &gt; {name}</div>

    <main class="detail-page">
        <div class="detail-hero">
            <img src="../images/events/{slug}-hero.jpg" onerror="this.onerror=null;this.src='../images/ogp-default.jpg'" alt="{name}" class="detail-hero-img">
        </div>
        <div class="detail-header">
            <h1>{name}</h1>
            <div class="detail-meta">
                <span class="detail-status-badge">開催予定</span>
                <span class="detail-meta-dot"></span>
                <span class="detail-meta-item">{date_jp}</span>
                <span class="detail-meta-dot"></span>
                <span class="detail-meta-item">{prefecture or short_pref}</span>
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
                    {"".join(f"<p>{p.strip()}</p>" for p in description.split("\\n") if p.strip())}
                </div>

                <div class="detail-map">
                    <h2 class="detail-section-title">会場</h2>
                    <iframe src="{maps_embed}" width="100%" height="280" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                </div>

                <div class="detail-back">
                    <a href="../category/{cat_slug}.html" class="detail-back-link">{cat_label}に戻る</a>
                </div>
            </div>

            <div class="detail-sidebar">
                <div class="detail-info-card">
                    <h3>Event Info</h3>
                    <div class="info-row">
                        <span class="info-label">日時</span>
                        <span class="info-value">{date_jp}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">会場</span>
                        <span class="info-value">{venue}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">エリア</span>
                        <span class="info-value">{address}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">入場料</span>
                        <span class="info-value">{admission}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">カテゴリ</span>
                        <span class="info-value">{tags}</span>
                    </div>'''

    if official_url:
        html += f'''
                    <div class="info-row">
                        <span class="info-label">公式</span>
                        <span class="info-value"><a href="{official_url}" target="_blank" rel="noopener" style="color:var(--accent-pop);text-decoration:none">公式サイト →</a></span>
                    </div>'''

    html += f'''
                    <a href="{gcal_url}" target="_blank" rel="noopener" class="gcal-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                        Googleカレンダーに追加
                    </a>
                </div>
                <div class="affiliate-section" data-tags="{tags}"></div>

            </div>
        </div>
    </main>

    <div class="ad-slot ad-slot-article-bottom" data-ad="article-bottom">
        <!-- Google AdSense: 記事下レスポンシブ広告 -->
    </div>

    <div class="correction-notice">
        <p>掲載情報はなるべく精査しておりますが、万が一誤りがある場合は申し訳ございません。お手数をおかけいたしますが、<a href="../contact.html">お問い合わせフォーム</a>からご連絡いただけますと幸いです。</p>
    </div>

    <footer class="footer">
        <div class="footer-inner">
            <div class="footer-logo">
                <span class="logo-en">AGAVE EVENT NAVI</span>
            </div>
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
            "name": "{venue}",
            "address": {{
                "@type": "PostalAddress",
                "addressCountry": "JP",
                "addressRegion": "{addr_region}",
                "addressLocality": "{addr_local}"
            }}
        }},
        "eventStatus": "https://schema.org/EventScheduled",
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode"
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
        // 行きたい (favorite) functionality
        const slug = location.pathname.split('/').pop().replace('.html','');
        function getFavs() {{
            try {{ return JSON.parse(localStorage.getItem('aen_favs') || '[]'); }} catch(e) {{ return []; }}
        }}
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
            if (isFav) {{
                btn.classList.add('is-fav');
                label.textContent = '行きたい登録済み';
            }} else {{
                btn.classList.remove('is-fav');
                label.textContent = '行きたい';
            }}
        }}
        updateFavBtn();
    </script>
    <script>
    // Ikitai badge count
    (function(){{
        var b = document.getElementById('ikitaiBadge');
        if (!b) return;
        try {{
            var favs = JSON.parse(localStorage.getItem('aen_favs') || '[]');
            if (favs.length > 0) {{
                b.textContent = favs.length;
                b.classList.add('has-count');
            }}
        }} catch(e) {{}}
    }})();
    </script>
    <script src="../affiliate.js"></script>

<script src="../status-auto.js"></script>
</body>
</html>'''

    return slug, html


def generate_index_card(data, slug):
    """index.html用イベントカードHTMLを生成"""
    name = data['name']
    date_str = data['date']
    end_date = data.get('end_date', date_str)
    description = data['description']
    category = data.get('category', '即売会')
    tags = data.get('tags', category)
    prefecture = data.get('prefecture', '')
    address = data.get('address', '')

    date_short = format_date_short(date_str, end_date)
    region = get_region_from_prefecture(prefecture or address)
    short_pref = get_short_pref(prefecture or address)
    short_desc = description[:80] + '...' if len(description) > 80 else description

    tag_items = ''.join(f'<span class="tag">{t.strip()}</span>' for t in tags.split(','))

    card = f'''
                    <div class="event-card" data-tags="{tags}" data-status="upcoming" data-region="{region}" data-date="{date_str}" data-slug="{slug}">
                        <img src="images/events/{slug}-thumb.jpg?v=20260326" alt="{name}" class="event-thumb" loading="lazy">
                        <button class="fav-btn" onclick="toggleFav(event, '{slug}')" aria-label="行きたい">
                            <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                        </button>
                        <div class="swipe-hint"><div class="swipe-hint-icon"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></div></div>
                        <div class="event-card-body">
                        <div class="event-header">
                            <span class="event-date">{date_short}</span>
                            <span class="event-status status-upcoming">開催予定</span>
                        </div>
                        <h3 class="event-title">{name}</h3>
                        <p class="event-description">{short_desc}</p>
                        <div class="event-meta-row">
                            <span class="event-region">{short_pref}</span>
                        </div>
                        <div class="event-tags">
                            {tag_items}
                        </div>
                        <a href="events/{slug}.html" class="event-link">詳細を見る</a>
                        </div>
                                            <div class="card-fav-bar" onclick="event.stopPropagation()"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg><span>行きたい</span></div>
</div>
'''
    return card


def add_card_to_index(card_html, index_path='index.html'):
    """index.htmlのeventsGridにカードを追加（日付順に挿入）"""
    with open(index_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # eventsGridの直後（最初のevent-cardの前）に挿入
    marker = '<div class="events-grid" id="eventsGrid">'
    if marker in content:
        insert_pos = content.index(marker) + len(marker)
        content = content[:insert_pos] + card_html + content[insert_pos:]

        with open(index_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def create_placeholder_thumb(slug, name, output_dir='images/events'):
    """プレースホルダーサムネイル画像を生成（800x600 ダークグレー背景）"""
    try:
        from PIL import Image, ImageDraw
        os.makedirs(output_dir, exist_ok=True)
        img = Image.new('RGB', (800, 600), color=(34, 34, 34))
        draw = ImageDraw.Draw(img)
        # シンプルなプレースホルダー（日本語フォントがなくてもOK）
        img.save(os.path.join(output_dir, f'{slug}-thumb.jpg'), 'JPEG', quality=92)
        print(f'Created placeholder thumbnail: {slug}-thumb.jpg')
        return True
    except ImportError:
        print('Pillow not available, skipping thumbnail generation')
        return False


def main():
    """メイン処理: JSONファイルからイベントデータを読み込んでページ生成"""
    if len(sys.argv) < 2:
        print('Usage: python generate_event_page.py <event_data.json>')
        print('')
        print('JSON format:')
        print(json.dumps({
            'name': 'イベント名',
            'date': '2026-06-01',
            'end_date': '2026-06-02',
            'venue': '会場名',
            'address': '東京都渋谷区...',
            'prefecture': '東京都',
            'description': 'イベントの説明文。\\n改行で段落分け。',
            'admission': '入場無料',
            'category': '即売会',
            'tags': '即売会,マルシェ',
            'official_url': 'https://example.com',
            'organizer': '主催者名',
            'slug': 'custom-slug-optional'
        }, ensure_ascii=False, indent=2))
        sys.exit(1)

    data_path = sys.argv[1]
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # イベント詳細ページ生成
    slug, detail_html = generate_detail_page(data)
    os.makedirs('events', exist_ok=True)
    detail_path = f'events/{slug}.html'
    with open(detail_path, 'w', encoding='utf-8') as f:
        f.write(detail_html)
    print(f'Generated detail page: {detail_path}')

    # index.htmlにカード追加
    card_html = generate_index_card(data, slug)
    if add_card_to_index(card_html):
        print(f'Added card to index.html')
    else:
        print('WARNING: Could not find eventsGrid in index.html')

    # プレースホルダーサムネイル
    create_placeholder_thumb(slug, data['name'])

    print(f'\nDone! Event slug: {slug}')
    print(f'Detail page: events/{slug}.html')
    print(f'Remember to replace images/events/{slug}-thumb.jpg with actual image')


if __name__ == '__main__':
    main()
