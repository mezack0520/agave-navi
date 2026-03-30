#!/usr/bin/env python3
import json
import os
from datetime import datetime
from pathlib import Path

# Events to add
new_events_data = [
    {
        "name": "実生畑でつかまえて 2026",
        "date": "2026-04-04",
        "dateEnd": None,
        "location": "Toky (日本橋久松町)",
        "prefecture": "東京",
        "region": "関東",
        "tags": ["即売会"],
        "description": "東京・日本橋で開催される植物即売会。実生から育成した珍奇植物が集まるイベント。",
    },
    {
        "name": "植縁祭 5th",
        "date": "2026-04-04",
        "dateEnd": "2026-04-05",
        "location": "なかやまフラワーハウス",
        "prefecture": "愛媛",
        "region": "四国",
        "tags": ["即売会", "マルシェ"],
        "description": "愛媛県伊予市で開催される植物イベント。多肉植物やサボテンの即売会。",
    },
    {
        "name": "BROMELIAD FESTA 'SPRING' 2026",
        "date": "2026-04-05",
        "dateEnd": None,
        "location": "ビジョンセンター西新宿",
        "prefecture": "東京",
        "region": "関東",
        "tags": ["即売会"],
        "description": "東京・新宿で開催されるブロメリア専門の春の即売会。ブロメリア愛好家が集結。",
    },
    {
        "name": "オキボタ Spring 2026 in サンシャインシティー",
        "date": "2026-04-10",
        "dateEnd": "2026-04-12",
        "location": "サンシャインシティ",
        "prefecture": "東京",
        "region": "関東",
        "tags": ["即売会"],
        "description": "東京・池袋のサンシャインシティで開催される植物即売会。多様な植物が揃うイベント。",
    },
    {
        "name": "第26回 花宇宙ドリームガーデン",
        "date": "2026-04-10",
        "dateEnd": "2026-04-12",
        "location": "株式会社 花宇宙",
        "prefecture": "兵庫",
        "region": "関西",
        "tags": ["即売会", "マルシェ"],
        "description": "兵庫県川西市で開催される大型植物イベント。多肉植物やサボテンの専門店が集結。",
    },
    {
        "name": "JUNGLE PLANTS MARKET",
        "date": "2026-04-12",
        "dateEnd": None,
        "location": "ナフコ鷲宮店 駐車場",
        "prefecture": "埼玉",
        "region": "関東",
        "tags": ["マルシェ"],
        "description": "埼玉県久喜市で開催されるジャングルプランツのマルシェ。アロイドやジャングルプランツが揃う。",
    },
    {
        "name": "Our Plants ver.2.03",
        "date": "2026-04-25",
        "dateEnd": None,
        "location": "梅小路公園内 緑の館",
        "prefecture": "京都",
        "region": "関西",
        "tags": ["即売会"],
        "description": "京都・梅小路公園で開催される植物即売会。珍奇植物や多肉植物が集まるイベント。",
    },
    {
        "name": "わっしょいマルシェ",
        "date": "2026-04-25",
        "dateEnd": None,
        "location": "四国山香りの森公園 香りドーム",
        "prefecture": "岐阜",
        "region": "中部",
        "tags": ["マルシェ"],
        "description": "岐阜県山県市で開催されるマルシェ。植物や地域の特産品が揃うイベント。",
    },
    {
        "name": "AICHI植フェス Vol.1",
        "date": "2026-04-25",
        "dateEnd": "2026-04-26",
        "location": "すいとぴあ江南",
        "prefecture": "愛知",
        "region": "中部",
        "tags": ["即売会", "大型"],
        "description": "愛知県江南市で開催される植物フェスティバル。多種多様な植物の即売会。",
    },
    {
        "name": "Hobby Plants Freaks Vol5",
        "date": "2026-04-25",
        "dateEnd": "2026-04-26",
        "location": "ナガサコファーム",
        "prefecture": "岡山",
        "region": "中国",
        "tags": ["即売会"],
        "description": "岡山県笠岡市で開催されるホビープランツのイベント。レアな植物が集まる。",
    },
    {
        "name": "KISARAZU C&S FAIR",
        "date": "2026-04-26",
        "dateEnd": None,
        "location": "スパークルシティ木更津",
        "prefecture": "千葉",
        "region": "関東",
        "tags": ["即売会"],
        "description": "千葉県木更津市で開催されるカクタス&サボテンのフェア。サボテン愛好家が集結。",
    },
    {
        "name": "THE PLANTS - Episode 9",
        "date": "2026-04-26",
        "dateEnd": None,
        "location": "Gori House",
        "prefecture": "香川",
        "region": "四国",
        "tags": ["即売会"],
        "description": "香川県観音寺市で開催されるプランツイベント。珍奇植物の即売会。",
    },
    {
        "name": "FUJISAN FESTA",
        "date": "2026-05-03",
        "dateEnd": None,
        "location": "ふじさんめっせ",
        "prefecture": "静岡",
        "region": "中部",
        "tags": ["即売会", "大型"],
        "description": "静岡県富士市で開催される大型植物フェスタ。多肉植物やサボテンが豊富。",
    },
    {
        "name": "ボタニカルマルシェ金沢2026",
        "date": "2026-05-09",
        "dateEnd": None,
        "location": "金沢（会場未確定）",
        "prefecture": "石川",
        "region": "中部",
        "tags": ["マルシェ"],
        "description": "石川県金沢で開催されるボタニカルマルシェ。珍奇植物や多肉植物が揃うマルシェ。",
    },
    {
        "name": "伏見大作戦 vol.2",
        "date": "2026-05-16",
        "dateEnd": None,
        "location": "三谷商事株式会社 屋外スペース",
        "prefecture": "京都",
        "region": "関西",
        "tags": ["即売会"],
        "description": "京都・伏見で開催される植物即売会。地域の植物愛好家が集まるイベント。",
    },
    {
        "name": "仙台竜舌露店 Vol.2",
        "date": "2026-06-27",
        "dateEnd": None,
        "location": "虹色路店前 ガレージスペース",
        "prefecture": "宮城",
        "region": "東北",
        "tags": ["マルシェ"],
        "description": "宮城県仙台市で開催されるアガベやリュウゼツランの専門マルシェ。",
    },
]

def slugify(text):
    """Convert Japanese text to a URL-friendly slug using romanization"""
    import unicodedata

    # Mapping for common Japanese names and phrases
    slug_map = {
        "実生畑でつかまえて 2026": "seiseihatake-2026",
        "植縁祭 5th": "shokuenseisai-5th",
        "BROMELIAD FESTA 'SPRING' 2026": "bromeliad-festa-spring-2026",
        "オキボタ Spring 2026 in サンシャインシティー": "okibota-spring-2026-sunshine",
        "第26回 花宇宙ドリームガーデン": "hanauchu-dream-garden-26",
        "JUNGLE PLANTS MARKET": "jungle-plants-market",
        "Our Plants ver.2.03": "our-plants-2-03",
        "わっしょいマルシェ": "wasshoi-marche",
        "AICHI植フェス Vol.1": "aichi-plants-fes-vol1",
        "Hobby Plants Freaks Vol5": "hobby-plants-freaks-vol5",
        "KISARAZU C&S FAIR": "kisarazu-cs-fair",
        "THE PLANTS - Episode 9": "the-plants-episode-9",
        "FUJISAN FESTA": "fujisan-festa",
        "ボタニカルマルシェ金沢2026": "botanical-marche-kanazawa-2026",
        "伏見大作戦 vol.2": "fushimi-daisakusen-vol2",
        "仙台竜舌露店 Vol.2": "sendai-agave-shop-vol2",
    }

    # Use map if available, otherwise generate a simple slug
    if text in slug_map:
        return slug_map[text]

    # Fallback: romanize using basic rules
    # Remove special characters and convert spaces to hyphens
    slug = text.lower().replace(' ', '-').replace('_', '-')
    # Keep ASCII letters, numbers, and hyphens
    slug = ''.join(c if c.isalnum() or c == '-' else '' for c in slug)
    # Remove multiple consecutive hyphens
    while '--' in slug:
        slug = slug.replace('--', '-')
    # Remove trailing/leading hyphens
    slug = slug.strip('-')
    return slug if slug else "event-unnamed"

def format_date_display(date_str, date_end_str=None):
    """Format dates for display"""
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    date_display = date_obj.strftime('%Y.%m.%d')

    if date_end_str:
        end_obj = datetime.strptime(date_end_str, '%Y-%m-%d')
        end_display = end_obj.strftime('%m.%d')
        return f"{date_display}-{end_display}"
    return date_display

def create_event_dict(data):
    """Create event dict with all required fields"""
    slug = slugify(data["name"])
    date_display = format_date_display(data["date"], data.get("dateEnd"))

    event = {
        "slug": slug,
        "name": data["name"],
        "date": data["date"],
        "dateDisplay": date_display,
        "location": data["location"],
        "prefecture": data["prefecture"],
        "region": data["region"],
        "tags": data["tags"],
        "status": "upcoming",
        "admission": "無料",
        "description": data["description"],
        "sourceUrl": "",
        "eventStatus": "confirmed"
    }

    if data.get("dateEnd"):
        event["dateEnd"] = data["dateEnd"]

    return event

def load_events():
    """Load existing events"""
    with open('/sessions/serene-dreamy-galileo/repo/events.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def save_events(events):
    """Save events to JSON"""
    with open('/sessions/serene-dreamy-galileo/repo/events.json', 'w', encoding='utf-8') as f:
        json.dump(events, f, ensure_ascii=False, indent=2)

def create_event_html(event):
    """Create HTML detail page for event"""
    slug = event["slug"]
    name = event["name"]
    location = event["location"]
    prefecture = event["prefecture"]
    date_display = event["dateDisplay"]
    description = event["description"]
    tags = event.get("tags", [])

    # Format date for meta
    date_obj = datetime.strptime(event["date"], '%Y-%m-%d')
    formatted_date = date_obj.strftime('%Y年%m月%d日（%a）').replace('Mon', '月').replace('Tue', '火').replace('Wed', '水').replace('Thu', '木').replace('Fri', '金').replace('Sat', '土').replace('Sun', '日')

    # Get Japanese day of week
    days_jp = ['月', '火', '水', '木', '金', '土', '日']
    day_of_week = days_jp[date_obj.weekday()]
    formatted_date = date_obj.strftime(f'%Y年%m月%d日（{day_of_week}）')

    # Build breadcrumb category
    category_slug = "sokubai.html" if "即売会" in tags else "marche.html"
    category_name = "即売会イベント一覧" if "即売会" in tags else "マルシェイベント一覧"

    # Build tags HTML
    tags_html = '\n                            '.join([f'<span class="tag">{tag}</span>' for tag in tags])

    # Prepare schema.org data
    schema_date = event["date"]
    schema_location = location

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
    <meta name="description" content="{description}">
    <meta property="og:title" content="{name}">
    <meta property="og:description" content="{description}">
    <meta property="og:type" content="website">
    <meta property="og:url" content="https://agave-navi.com/events/{slug}.html">
    <link rel="icon" type="image/svg+xml" href="../favicon.svg">
    <link rel="icon" type="image/x-icon" href="../favicon.ico">
    <link rel="apple-touch-icon" sizes="180x180" href="../apple-touch-icon.png">
    <link rel="stylesheet" href="../style.css?v=20260327">
<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-XXXXXXXXXXXXXXXX" crossorigin="anonymous"></script>
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
        <a href="/">ホーム</a> &gt; <a href="../category/{category_slug}">{category_name}</a> &gt; {name}</div>

    <main class="detail-page">
        <div class="detail-header">
            <h1>{name}</h1>
            <div class="detail-meta">
                <span class="detail-status-badge" data-date="{schema_date}">開催予定</span>
                <span class="detail-meta-dot"></span>
                <span class="detail-meta-item">{formatted_date}</span>
                <span class="detail-meta-dot"></span>
                <span class="detail-meta-item">{prefecture}県</span>
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
                    <p>{name}は{prefecture}県で開催される植物イベントです。{description}</p>
                    <p>このイベントは植物愛好家にとって重要な機会となります。珍しい品種の発見や、植物の購入、そして愛好家同士の交流の場として機能しています。</p>
                    <p>詳細な日程や出店者情報は、直接主催者にお問い合わせいただくことをお勧めします。</p>
                </div>

                <div class="detail-map">
                    <h2 class="detail-section-title">会場</h2>
                    <iframe src="https://maps.google.com/maps?q={prefecture}%E7%9C%8C&output=embed" width="100%" height="280" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
                </div>

                <div class="detail-back">
                    <a href="../category/{category_slug}" class="detail-back-link">{category_name}に戻る</a>
                </div>
            </div>

            <div class="detail-sidebar">
                <div class="detail-info-card">
                    <h3>Event Info</h3>
                    <div class="info-row">
                        <span class="info-label">日時</span>
                        <span class="info-value">{formatted_date}</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">会場</span>
                        <span class="info-value">{prefecture}県</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">入場料</span>
                        <span class="info-value">無料</span>
                    </div>
                    <div class="info-row">
                        <span class="info-label">カテゴリ</span>
                        <span class="info-value">{tags[0] if tags else '即売会'}</span>
                    </div>
                    <a href="https://calendar.google.com/calendar/render?action=TEMPLATE&text={name}&dates={schema_date.replace('-', '')}%2F{(datetime.strptime(event.get('dateEnd', event['date']), '%Y-%m-%d') + __import__('datetime').timedelta(days=1)).strftime('%Y%m%d')}&location={prefecture}&details={name}+-+%E3%82%A2%E3%82%AC%E3%83%99%E3%82%A4%E3%83%99%E3%83%B3%E3%83%88%E3%83%8A%E3%83%93+https%3A%2F%2Fagave-navi.com%2F" target="_blank" rel="noopener" class="gcal-btn">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
                        Googleカレンダーに追加
                    </a>
                </div>


            </div>

            <div class="affiliate-section" data-tags="{tags[0] if tags else '即売会'}"></div>
        </div>
    </main>

    <div class="ad-slot ad-slot-article-bottom" data-ad="article-bottom">
        <!-- Google AdSense: 記事下レスポンシブ広告 -->
        <!-- TODO: パブリッシャーID取得後にアドセンスコードを挿入 -->
    </div>


    <!-- 広告・アフィリエイトエリア -->
    <div class="ad-affiliate-area" style="max-width:960px;margin:0 auto;padding:0 1rem;">
        <div class="aff-slot" data-count="5"></div>
        <div class="ad-slot">
            <span class="ad-slot-label">広告</span>
            <ins class="adsbygoogle"
                 style="display:block"
                 data-ad-client="ca-pub-XXXXXXXXXXXXXXXX"
                 data-ad-slot="0987654321"
                 data-ad-format="auto"
                 data-full-width-responsive="true"></ins>
        </div>
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
    "description": "{description}",
    "startDate": "{schema_date}",
    "location": {{
        "@type": "Place",
        "name": "{schema_location}",
        "address": {{
            "@type": "PostalAddress",
            "addressCountry": "JP",
            "addressRegion": "{prefecture}県",
            "addressLocality": "{location}"
        }}
    }},
    "eventStatus": "https://schema.org/EventScheduled",
    "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
    "isAccessibleForFree": true,
    "image": "https://agave-navi.com/images/ogp/default.jpg",
    "organizer": {{
        "@type": "Organization",
        "name": "{name}"
    }},
    "offers": {{
        "@type": "Offer",
        "price": "0",
        "priceCurrency": "JPY",
        "availability": "https://schema.org/InStock",
        "url": "https://agave-navi.com/events/{slug}.html"
    }}
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
            const favs = getFavs();
            const isFav = favs.includes(slug);
            if (isFav) {{
                btn.classList.add('is-fav');
                label.textContent = '行きたい登録済み';
            }} else {{
                btn.classList.remove('is-fav');
                label.textContent = '行きたい';
            }}
            // Real-time badge count update
            var b = document.getElementById('ikitaiBadge');
            if (b) {{
                if (favs.length > 0) {{
                    b.textContent = favs.length;
                    b.classList.add('has-count');
                }} else {{
                    b.textContent = '';
                    b.classList.remove('has-count');
                }}
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

<script src="../status-auto.js?v=20260328"></script>
<script src="../ads.js"></script>
</body>
</html>
'''

    return html

def generate_event_card_html(event):
    """Generate HTML card for event in index.html"""
    slug = event["slug"]
    date_display = event["dateDisplay"]
    title = event["name"]
    description = event["description"]
    region = event["region"]
    tags = event.get("tags", [])
    date_str = event["date"]

    # Determine prefecture
    pref = event["prefecture"]

    # Build tags string
    tags_str = ",".join(tags)

    # Build tags HTML
    tags_html = "\n                            ".join([f'<span class="tag">{tag}</span>' for tag in tags])

    # Check if no image
    image_html = '<div class="event-thumb event-no-image"></div>'

    html = f'''<div class="event-card" data-tags="{tags_str}" data-status="upcoming" data-region="{region}" data-pref="{pref}" data-date="{date_str}" data-slug="{slug}">
                        {image_html}
                        <button class="fav-btn" onclick="toggleFav(event, '{slug}')" aria-label="行きたい">
                            <svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>
                        </button>
                        <div class="swipe-hint"><div class="swipe-hint-icon"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg></div></div>
                        <div class="event-card-body">
                        <div class="event-header">
                            <span class="event-date">{date_display}</span>
                        </div>
                        <h3 class="event-title">{title}</h3>
                        <p class="event-description">{description}</p>
                        <div class="event-meta-row">
                            <span class="event-region">{pref}</span>
                        </div>
                        <div class="event-tags">
                            {tags_html}
                        </div>
                        <a href="events/{slug}.html" class="event-link">詳細を見る</a>
                        </div>
                                            <div class="card-fav-bar" onclick="event.stopPropagation()"><svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg><span>行きたい</span></div>
</div>
'''

    return html

def main():
    print("Loading existing events...")
    events = load_events()
    print(f"Current event count: {len(events)}")

    # Create new events
    new_events = []
    for event_data in new_events_data:
        event = create_event_dict(event_data)
        new_events.append(event)

        # Create HTML detail page
        html_content = create_event_html(event)
        html_path = f'/sessions/serene-dreamy-galileo/repo/events/{event["slug"]}.html'
        with open(html_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"Created: {html_path}")

    # Add new events to the main list (insert them in date order)
    all_events = events + new_events
    # Sort by date
    all_events.sort(key=lambda e: e["date"])

    # Save updated events.json
    save_events(all_events)
    print(f"Updated events.json with {len(new_events)} new events")
    print(f"Total events now: {len(all_events)}")

    # Update index.html
    print("\nUpdating index.html...")
    with open('/sessions/serene-dreamy-galileo/repo/index.html', 'r', encoding='utf-8') as f:
        index_content = f.read()

    # Find the eventsGrid section and add new cards
    import re

    # Generate cards for new events
    new_cards_html = ""
    for event in sorted(new_events, key=lambda e: e["date"]):
        new_cards_html += generate_event_card_html(event) + "\n\n                    "

    # Find where to insert - after the last existing event card
    # We need to insert new events in chronological order

    # For simplicity, we'll regenerate the entire events grid from events.json
    # Find the eventsGrid div
    match = re.search(r'<div class="events-grid" id="eventsGrid">(.*?)</div>\s*<div class="load-more-wrap">', index_content, re.DOTALL)

    if match:
        # Build new grid with all events sorted by date
        grid_content = '\n                    <!-- March 2026 -->\n'

        # Group events by month
        from collections import defaultdict
        events_by_month = defaultdict(list)
        for e in all_events:
            month_year = e["date"][:7]  # YYYY-MM
            events_by_month[month_year].append(e)

        # Generate cards in chronological order
        for month in sorted(events_by_month.keys()):
            month_obj = datetime.strptime(month, '%Y-%m')
            month_name = month_obj.strftime('%B %Y')

            # Add month header comment if different from previous
            grid_content += f"                    <!-- {month_obj.strftime('%B %Y')} -->\n"

            for event in sorted(events_by_month[month], key=lambda e: e["date"]):
                grid_content += generate_event_card_html(event) + "\n\n                    "

        # Replace the grid content
        old_grid = match.group(0)
        new_grid = f'<div class="events-grid" id="eventsGrid">{grid_content}</div>\n                <div class="load-more-wrap">'
        index_content = index_content.replace(old_grid, new_grid)

    # Update event count
    event_count = len([e for e in all_events if e["status"] == "upcoming"])
    index_content = re.sub(
        r'<span class="event-count" id="eventCount">\d+件</span>',
        f'<span class="event-count" id="eventCount">{event_count}件</span>',
        index_content
    )

    # Save updated index.html
    with open('/sessions/serene-dreamy-galileo/repo/index.html', 'w', encoding='utf-8') as f:
        f.write(index_content)

    print(f"Updated index.html with {event_count} upcoming events")
    print("\nDone!")

if __name__ == "__main__":
    main()
