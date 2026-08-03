#!/usr/bin/env python3
"""
build_static_html.py — map.html と calendar.html を再生成する。

修正内容:
1. map.html の壊れたJS構文を修正（initMap 関数の閉じカッコ位置を直す）
2. 両ページに events.json のサーバーレンダリングされた一覧を埋め込み
   （SEO 改善: クローラーから本文が見えるようにする）
3. events.json を AJAX 取得せず、HTML 内にインラインJSONで埋め込む
   （First Paint高速化、JS失敗時もデータが残る）

冪等。既に正しい状態なら何も書き換えない。
"""

import json
import re
import sys
import os
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(ROOT, 'events.json')
MAP_HTML = os.path.join(ROOT, 'map.html')
CAL_HTML = os.path.join(ROOT, 'calendar.html')

# 地域分類の単一情報源は sitelib。独自定義で山梨・長野を「中部」としていたが
# REGION_ROMAJI に中部が無くハッシュURLの頁を生むため統合した(2026-07-31)。
from sitelib import PREF_TO_REGION as REGION_FROM_PREFECTURE, today_jst


def esc(s):
    return (str(s or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def upcoming_events(events):
    today_iso = today_jst()  # JSTで判定(UTCだと06:00 JSTの日次実行で前日扱いになる)
    rows = []
    for e in events:
        if e.get('status') == 'past':
            continue
        d_end = e.get('dateEnd') or e.get('date') or ''
        if d_end and d_end < today_iso:
            continue
        rows.append(e)
    rows.sort(key=lambda e: (e.get('date') or '9999', e.get('name') or ''))
    return rows


def render_fallback_list(events_list, heading):
    """SSR fallback HTML — a semantic listing of all upcoming events."""
    items = []
    for e in events_list:
        slug = e.get('slug') or ''
        if not slug:
            continue
        name = e.get('name') or slug
        date_disp = e.get('dateDisplay') or e.get('date') or ''
        loc = e.get('location') or ''
        pref = e.get('prefecture') or ''
        tag = (e.get('tags') or ['即売会'])[0]
        region = REGION_FROM_PREFECTURE.get(pref, e.get('region') or '')
        # Place-related text helps SEO for prefecture / region queries.
        loc_text = f"{pref}・{loc}" if pref and loc else (pref or loc)
        items.append(f'''<li class="ssr-event-item">
<a href="events/{esc(slug)}.html"><time datetime="{esc(e.get('date') or '')}">{esc(date_disp)}</time> <strong>{esc(name)}</strong></a>
<span class="ssr-event-meta">{esc(tag)} / {esc(loc_text)} {("（" + esc(region) + "）") if region else ""}</span>
</li>''')

    lis = '\n'.join(items)
    return f'''<section class="ssr-event-list" aria-labelledby="ssr-event-list-h">
<h2 id="ssr-event-list-h">{esc(heading)}</h2>
<p class="ssr-event-list-intro">全国のアガベ・多肉植物・塊根植物・珍奇植物・ビザールプランツ即売会／マルシェ／展示会の開催予定。各イベントの詳細ページから日程・会場・出店者情報を確認できます。</p>
<ol class="ssr-event-list-ol">
{lis}
</ol>
</section>'''


def render_itemlist_jsonld(events_list, page_name, page_url):
    """ItemList Event JSON-LD for SEO (Google's Event rich result eligibility)."""
    items = []
    for i, e in enumerate(events_list[:30], 1):
        slug = e.get('slug', '')
        if not slug:
            continue
        item = {
            "@type": "ListItem",
            "position": i,
            "item": {
                "@type": "Event",
                "name": e.get('name', ''),
                "startDate": e.get('date', ''),
                "endDate": e.get('dateEnd') or e.get('date', ''),
                "url": f"https://agave-navi.com/events/{slug}.html",
                "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
                "eventStatus": "https://schema.org/EventScheduled",
                "location": {
                    "@type": "Place",
                    "name": e.get('venue') or e.get('location', ''),
                    "address": {
                        "@type": "PostalAddress",
                        "addressRegion": e.get('prefecture', ''),
                        "addressCountry": "JP"
                    }
                }
            }
        }
        if e.get('description'):
            item["item"]["description"] = e['description'][:300]
        items.append(item)

    obj = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": page_name,
        "url": page_url,
        "numberOfItems": len(items),
        "itemListElement": items
    }
    payload = json.dumps(obj, ensure_ascii=False, separators=(',', ':'))
    return f'<script type="application/ld+json">{payload}</script>'


def render_inline_events_json(events_list):
    """Embed events as inline JSON so JS doesn't need an AJAX round trip."""
    payload = json.dumps(events_list, ensure_ascii=False, separators=(',', ':'))
    return f'<script type="application/json" id="ssr-events-data">{payload}</script>'


# ---- map.html ----

MAP_JS_FIXED = '''<script>
        // Menu toggle
        const toggle = document.getElementById('menuToggle');
        const overlay = document.getElementById('navOverlay');
        toggle.addEventListener('click', () => {
            toggle.classList.toggle('active');
            overlay.classList.toggle('active');
            document.body.classList.toggle('no-scroll');
        });
        overlay.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                toggle.classList.remove('active');
                overlay.classList.remove('active');
                document.body.classList.remove('no-scroll');
            });
        });

        // Event data with coordinates
        const PREF_COORDS = {
            '北海道':[43.0642,141.3469],'青森':[40.8244,140.7400],'岩手':[39.7036,141.1527],
            '宮城':[38.2688,140.8721],'秋田':[39.7186,140.1024],'山形':[38.2404,140.3633],
            '福島':[37.7503,140.4677],'茨城':[36.3417,140.4467],'栃木':[36.5658,139.8836],
            '群馬':[36.3911,139.0608],'埼玉':[35.8569,139.6489],'千葉':[35.6051,140.1233],
            '東京':[35.6895,139.6917],'神奈川':[35.4478,139.6425],'新潟':[37.9026,139.0235],
            '富山':[36.6953,137.2113],'石川':[36.5947,136.6256],'福井':[36.0652,136.2216],
            '山梨':[35.6642,138.5683],'長野':[36.6513,138.1810],'岐阜':[35.3911,136.7223],
            '静岡':[34.9769,138.3831],'愛知':[35.1802,136.9066],'三重':[34.7303,136.5086],
            '滋賀':[35.0045,135.8686],'京都':[35.0211,135.7556],'大阪':[34.6863,135.5198],
            '兵庫':[34.6913,135.1830],'奈良':[34.6851,135.8329],'和歌山':[34.2261,135.1675],
            '鳥取':[35.5039,134.2381],'島根':[35.4723,133.0505],'岡山':[34.6618,133.9344],
            '広島':[34.3963,132.4596],'山口':[34.1859,131.4706],'徳島':[34.0658,134.5593],
            '香川':[34.3401,134.0434],'愛媛':[33.8416,132.7656],'高知':[33.5597,133.5311],
            '福岡':[33.6064,130.4181],'佐賀':[33.2494,130.2989],'長崎':[32.7448,129.8737],
            '熊本':[32.7898,130.7417],'大分':[33.2382,131.6126],'宮崎':[31.9111,131.4239],
            '鹿児島':[31.5602,130.5581],'沖縄':[26.2125,127.6809]
        };

        function jitter() { return (Math.random() - 0.5) * 0.06; }

        function loadEvents() {
            const inlineEl = document.getElementById('ssr-events-data');
            if (inlineEl && inlineEl.textContent.trim()) {
                try {
                    return Promise.resolve(JSON.parse(inlineEl.textContent));
                } catch (e) {
                    console.warn('inline events JSON parse failed, falling back to AJAX', e);
                }
            }
            return fetch('events.json?t=' + Date.now()).then(r => r.json());
        }

        loadEvents().then(data => {
            const today = new Date().toISOString().slice(0,10);
            const events = data
                .filter(e => e.slug && (e.dateEnd || e.date) >= today)
                .map(e => {
                    const c = PREF_COORDS[e.prefecture] || PREF_COORDS[e.region] || [35.6895,139.6917];
                    return {
                        slug: e.slug,
                        name: e.name || '',
                        date: e.dateDisplay || e.date,
                        lat: c[0] + jitter(),
                        lng: c[1] + jitter(),
                        tag: (e.tags && e.tags[0]) || ''
                    };
                });
            initMap(events);
        }).catch(err => {
            console.warn('events load failed', err);
            initMap([]);
        });

        function initMap(events) {
            const map = L.map('map').setView([36.5, 137.0], 6);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap contributors',
                maxZoom: 19
            }).addTo(map);

            const colorMap = {
                "即売会": "#e63946",
                "マルシェ": "#f4a261",
                "大型": "#264653",
                "展示会": "#2a9d8f"
            };

            events.forEach(event => {
                const color = colorMap[event.tag] || "#e63946";
                const marker = L.circleMarker([event.lat, event.lng], {
                    radius: 8,
                    fillColor: color,
                    color: color,
                    weight: 2,
                    opacity: 0.9,
                    fillOpacity: 0.75
                }).addTo(map);

                const popupContent = `
                    <div class="popup-event-name">${event.name}</div>
                    <div class="popup-event-date">${event.date}</div>
                    <a href="events/${event.slug}.html" class="popup-event-link">詳しく見る</a>
                `;

                marker.bindPopup(popupContent);
            });
        }
    </script>
    <script>
    // Ikitai badge count
    (function(){
        var b = document.getElementById('ikitaiBadge');
        if (!b) return;
        try {
            var favs = JSON.parse(localStorage.getItem('aen_favs') || '[]');
            if (favs.length > 0) {
                b.textContent = favs.length;
                b.classList.add('has-count');
            }
        } catch(e) {}
    })();
    </script>'''


CAL_JS_FIXED = '''<script>
        // Menu toggle
        const toggle = document.getElementById('menuToggle');
        const overlay = document.getElementById('navOverlay');
        toggle.addEventListener('click', () => {
            toggle.classList.toggle('active');
            overlay.classList.toggle('active');
            document.body.classList.toggle('no-scroll');
        });
        overlay.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                toggle.classList.remove('active');
                overlay.classList.remove('active');
                document.body.classList.remove('no-scroll');
            });
        });

        let events = [];

        let currentYear = (new Date()).getFullYear();
        let currentMonth = (new Date()).getMonth();

        function changeMonth(delta) {
            currentMonth += delta;
            if (currentMonth > 11) { currentMonth = 0; currentYear++; }
            if (currentMonth < 0) { currentMonth = 11; currentYear--; }
            renderCalendar();
        }

        function renderCalendar() {
            const monthNames = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月'];
            document.getElementById('calTitle').textContent = `${currentYear}年 ${monthNames[currentMonth]}`;

            const grid = document.getElementById('calGrid');
            grid.innerHTML = '';

            const dows = ['日','月','火','水','木','金','土'];
            dows.forEach(d => {
                const el = document.createElement('div');
                el.className = 'cal-dow';
                el.textContent = d;
                grid.appendChild(el);
            });

            const firstDay = new Date(currentYear, currentMonth, 1);
            const lastDay = new Date(currentYear, currentMonth + 1, 0);
            const startDow = firstDay.getDay();
            const daysInMonth = lastDay.getDate();

            const today = new Date();
            const todayStr = `${today.getFullYear()}-${String(today.getMonth()+1).padStart(2,'0')}-${String(today.getDate()).padStart(2,'0')}`;

            const prevLast = new Date(currentYear, currentMonth, 0);
            for (let i = startDow - 1; i >= 0; i--) {
                const cell = document.createElement('div');
                cell.className = 'cal-cell other-month';
                const dayNum = document.createElement('div');
                dayNum.className = 'cal-day-num';
                dayNum.textContent = prevLast.getDate() - i;
                cell.appendChild(dayNum);
                grid.appendChild(cell);
            }

            for (let d = 1; d <= daysInMonth; d++) {
                const cell = document.createElement('div');
                const dateStr = `${currentYear}-${String(currentMonth+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
                cell.className = 'cal-cell';
                if (dateStr === todayStr) cell.classList.add('today');

                const dayNum = document.createElement('div');
                dayNum.className = 'cal-day-num';
                dayNum.textContent = d;
                cell.appendChild(dayNum);

                events.forEach(ev => {
                    const start = new Date(ev.start + 'T00:00:00');
                    const end = new Date(ev.end + 'T23:59:59');
                    const cur = new Date(dateStr + 'T12:00:00');
                    if (cur >= start && cur <= end) {
                        const a = document.createElement('a');
                        a.className = `cal-event tag-${ev.tag}`;
                        a.href = `events/${ev.slug}.html`;
                        a.textContent = ev.name;
                        a.title = ev.name;
                        cell.appendChild(a);
                    }
                });

                grid.appendChild(cell);
            }

            const totalCells = startDow + daysInMonth;
            const remaining = totalCells % 7 === 0 ? 0 : 7 - (totalCells % 7);
            for (let i = 1; i <= remaining; i++) {
                const cell = document.createElement('div');
                cell.className = 'cal-cell other-month';
                const dayNum = document.createElement('div');
                dayNum.className = 'cal-day-num';
                dayNum.textContent = i;
                cell.appendChild(dayNum);
                grid.appendChild(cell);
            }
        }

        function loadEvents() {
            const inlineEl = document.getElementById('ssr-events-data');
            if (inlineEl && inlineEl.textContent.trim()) {
                try {
                    return Promise.resolve(JSON.parse(inlineEl.textContent));
                } catch (e) {
                    console.warn('inline events JSON parse failed, falling back to AJAX', e);
                }
            }
            return fetch('events.json?t=' + Date.now()).then(r => r.json());
        }

        loadEvents().then(data => {
            events = data
                .filter(e => e.slug && e.date && e.status !== 'past')
                .map(e => ({
                    slug: e.slug,
                    name: e.name || '',
                    start: e.date,
                    end: e.dateEnd || e.date,
                    tag: (e.tags && e.tags[0]) || ''
                }));
            renderCalendar();
        }).catch(() => renderCalendar());
        </script>
    <script>
    // Ikitai badge count
    (function(){
        var b = document.getElementById('ikitaiBadge');
        if (!b) return;
        try {
            var favs = JSON.parse(localStorage.getItem('aen_favs') || '[]');
            if (favs.length > 0) {
                b.textContent = favs.length;
                b.classList.add('has-count');
            }
        } catch(e) {}
    })();
    </script>'''



import re as _re_cleanup

def strip_previous_insertions(html_src):
    """過去のビルドが挿入したSSRブロック(JSON-LD/インラインJSON/フォールバック一覧)を全て除去する。
    これが無いとビルドのたびに1セットずつ蓄積する(2026-06-11に4.2MBまで肥大したバグの恒久対策)。"""
    # ItemList JSON-LD (このスクリプトが挿入したもの)
    html_src = _re_cleanup.sub(
        r'<script type="application/ld\+json">\s*\{"@context":"https://schema\.org","@type":"ItemList".*?</script>\n?',
        '', html_src, flags=_re_cleanup.S)
    # インラインイベントJSON
    html_src = _re_cleanup.sub(
        r'<script type="application/json" id="ssr-events-data">.*?</script>\n?',
        '', html_src, flags=_re_cleanup.S)
    # SSRフォールバック一覧
    html_src = _re_cleanup.sub(
        r'<section class="ssr-event-list".*?</section>\n?',
        '', html_src, flags=_re_cleanup.S)
    return html_src

def rewrite_map_html(html_src, events_list, inline_data_block):
    html_src = strip_previous_insertions(html_src)
    fallback = render_fallback_list(events_list, '開催予定イベント一覧（地図に表示中）')
    jsonld = render_itemlist_jsonld(events_list, 'アガベ・植物イベントマップ', 'https://agave-navi.com/map.html')

    # 1) JS全体を置き換え: <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script> 以降を全部置換
    leaflet_marker = '<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>'
    if leaflet_marker not in html_src:
        raise RuntimeError("Leaflet script marker not found in map.html")
    pre, _, _ = html_src.partition(leaflet_marker)
    new_html = pre + leaflet_marker + '\n    ' + MAP_JS_FIXED + '\n</body>\n</html>\n'

    # 2) </footer> の直前にSSRイベント一覧 + インラインJSON + JSON-LDを挿入
    insertion = jsonld + '\n' + inline_data_block + '\n' + fallback + '\n'
    new_html = new_html.replace('</footer>', '</footer>\n' + insertion, 1)

    return new_html


def rewrite_cal_html(html_src, events_list, inline_data_block):
    html_src = strip_previous_insertions(html_src)
    fallback = render_fallback_list(events_list, '開催予定イベント一覧（カレンダーに表示中）')
    jsonld = render_itemlist_jsonld(events_list, 'アガベ・植物イベントカレンダー', 'https://agave-navi.com/calendar.html')

    # JS全体を置き換え: 元のスクリプトを新しいCAL_JS_FIXEDに差し替え
    # マッチさせるパターン: <script>\n        // Menu toggle ... </script>
    # 単純に "<script>\n        // Menu toggle" から最後の "</body>" 直前までを置換
    menu_marker = '<script>\n        // Menu toggle'
    body_close = '</body>'
    idx_start = html_src.find(menu_marker)
    idx_end = html_src.rfind(body_close)
    if idx_start < 0 or idx_end < 0:
        raise RuntimeError("calendar.html script markers not found")
    pre = html_src[:idx_start]
    new_html = pre + CAL_JS_FIXED + '\n</body>\n</html>\n'

    # SSRイベント一覧 + インラインJSON + JSON-LD を </footer> 直前に挿入
    insertion = jsonld + '\n' + inline_data_block + '\n' + fallback + '\n'
    new_html = new_html.replace('</footer>', '</footer>\n' + insertion, 1)

    return new_html


def main():
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    upcoming = upcoming_events(events)
    print(f'upcoming events: {len(upcoming)}')
    inline_data_block = render_inline_events_json(upcoming)

    # map.html
    with open(MAP_HTML, encoding='utf-8') as f:
        map_src = f.read()
    new_map = rewrite_map_html(map_src, upcoming, inline_data_block)
    if new_map != map_src:
        with open(MAP_HTML, 'w', encoding='utf-8') as f:
            f.write(new_map)
        print('map.html updated')
    else:
        print('map.html unchanged')

    # calendar.html
    with open(CAL_HTML, encoding='utf-8') as f:
        cal_src = f.read()
    new_cal = rewrite_cal_html(cal_src, upcoming, inline_data_block)
    if new_cal != cal_src:
        with open(CAL_HTML, 'w', encoding='utf-8') as f:
            f.write(new_cal)
        print('calendar.html updated')
    else:
        print('calendar.html unchanged')


if __name__ == '__main__':
    main()
