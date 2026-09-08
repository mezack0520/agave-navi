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
from sitelib import (PREF_TO_REGION as REGION_FROM_PREFECTURE, today_jst,
                     is_upcoming, split_ongoing)


def esc(s):
    return (str(s or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def upcoming_events(events):
    today_iso = today_jst()  # JSTで判定(UTCだと06:00 JSTの日次実行で前日扱いになる)
    rows = [e for e in events
            if e.get('status') != 'past' and is_upcoming(e, today_iso)]
    # 並び順は sitelib が単一情報源。開始日で並べると会期の長い回が先頭に居座る。
    ongoing, rest = split_ongoing(rows, today_iso)
    return ongoing + rest


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

MAP_JS_FIXED = '''<!-- PAGE-JS:START この下は build-static-html.py の生成物。手で書かない -->
    <script>
        // ハンバーガーの開閉は nav.js が単一実装。読み込みは </head> 側
        // (sync-footers.py が入れる)。ここに写しを持っていたため、
        // 手書き側を直してもビルドで元に戻っていた(2026-09-08)。

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
    <!-- 行きたいの件数バッジは nav.js が単一実装。
         ここに写しを持っていたため、手書き側から消してもビルドで
         戻っていた(2026-09-09) -->'''


CAL_JS_FIXED = '''<!-- PAGE-JS:START この下は build-static-html.py の生成物。手で書かない -->
    <script>
        // 開閉と行きたいバッジは nav.js が単一実装。読み込みは </head> 側
        // (sync-footers.py が入れる)。
        //
        // ## 描き方を2つ持つ理由(2026-09-09 に作り直し)
        // 7列のグリッドは 375px の画面に入らない。1列216px×7=1518pxで、
        // 日曜と月曜しか見えていなかった。
        // 狭い画面は「日付ごとの一覧」、広い画面は「月のグリッド」。
        // 両方を描いてCSSでどちらかを隠す。JS側で画面幅を見ると、
        // 回転やウィンドウ操作のたびに描き直す番人が必要になる。
        //
        // ## 会期の長い回は初日だけに出す
        // 以前は会期の全日にバーを出していた。9月は112本のうち
        // 「Sakuya Green Jam 5」が16本、山城愛仙園が10本、
        // NOVA CULTURA が9本。**カレンダーで見たいのは
        // 「どの日が混んでいるか」なのに、それが潰れていた**。
        // 初日に1本だけ出して「〜9/20」と会期を添える。
        // 月をまたいで続いている回は、その月の最初の日に「開催中」で出す。

        let events = [];
        let currentYear = (new Date()).getFullYear();
        let currentMonth = (new Date()).getMonth();

        const DOW = ['日', '月', '火', '水', '木', '金', '土'];

        function changeMonth(delta) {
            currentMonth += delta;
            if (currentMonth > 11) { currentMonth = 0; currentYear++; }
            if (currentMonth < 0) { currentMonth = 11; currentYear--; }
            render();
        }

        function ymd(y, m, d) {
            return y + '-' + String(m + 1).padStart(2, '0')
                     + '-' + String(d).padStart(2, '0');
        }

        function mdLabel(iso) {
            const p = (iso || '').split('-');
            return p.length === 3 ? (+p[1]) + '/' + (+p[2]) : iso;
        }

        // その月に出す回を、出す日ごとにまとめる。
        // 初日がその月にある回はその日。前月から続いている回は1日。
        function monthBuckets(year, month) {
            const first = ymd(year, month, 1);
            const last = ymd(year, month, new Date(year, month + 1, 0).getDate());
            const out = {};
            events.forEach(ev => {
                if (ev.end < first || ev.start > last) return;
                const key = ev.start >= first ? ev.start : first;
                (out[key] = out[key] || []).push(ev);
            });
            return out;
        }

        function eventLink(ev, dayKey) {
            const a = document.createElement('a');
            a.className = 'cal-event' + (ev.tag ? ' tag-' + ev.tag : '');
            a.href = 'events/' + ev.slug + '.html';
            const span = document.createElement('span');
            span.className = 'cal-event-name';
            span.textContent = ev.name;
            a.appendChild(span);
            let note = '';
            if (ev.start < dayKey) {
                note = '開催中 〜' + mdLabel(ev.end);
            } else if (ev.end > ev.start) {
                note = '〜' + mdLabel(ev.end);
            }
            if (note) {
                const s = document.createElement('span');
                s.className = 'cal-event-span';
                s.textContent = note;
                a.appendChild(s);
            }
            a.title = ev.name + (note ? ' (' + note + ')' : '');
            return a;
        }

        function renderDays(year, month, buckets) {
            const wrap = document.getElementById('calDays');
            if (!wrap) return;
            wrap.innerHTML = '';
            const keys = Object.keys(buckets).sort();
            if (!keys.length) {
                const p = document.createElement('p');
                p.className = 'cal-empty';
                p.textContent = 'この月に掲載しているイベントはありません。';
                wrap.appendChild(p);
                return;
            }
            keys.forEach(k => {
                const d = new Date(k + 'T12:00:00');
                const row = document.createElement('section');
                row.className = 'cal-day';
                const h = document.createElement('h3');
                h.className = 'cal-day-head';
                const dow = DOW[d.getDay()];
                h.innerHTML = '<span class="cal-day-date">' + mdLabel(k)
                    + '</span><span class="cal-day-dow dow-' + d.getDay() + '">('
                    + dow + ')</span><span class="cal-day-count">'
                    + buckets[k].length + '件</span>';
                row.appendChild(h);
                const ul = document.createElement('div');
                ul.className = 'cal-day-list';
                buckets[k].forEach(ev => ul.appendChild(eventLink(ev, k)));
                row.appendChild(ul);
                wrap.appendChild(row);
            });
        }

        function renderGrid(year, month, buckets) {
            const grid = document.getElementById('calGrid');
            if (!grid) return;
            grid.innerHTML = '';
            DOW.forEach((d, i) => {
                const el = document.createElement('div');
                el.className = 'cal-dow dow-' + i;
                el.textContent = d;
                grid.appendChild(el);
            });
            const startDow = new Date(year, month, 1).getDay();
            const daysInMonth = new Date(year, month + 1, 0).getDate();
            const t = new Date();
            const todayStr = ymd(t.getFullYear(), t.getMonth(), t.getDate());
            const prevLast = new Date(year, month, 0).getDate();
            for (let i = startDow - 1; i >= 0; i--) {
                const cell = document.createElement('div');
                cell.className = 'cal-cell other-month';
                cell.innerHTML = '<div class="cal-day-num">' + (prevLast - i) + '</div>';
                grid.appendChild(cell);
            }
            for (let d = 1; d <= daysInMonth; d++) {
                const key = ymd(year, month, d);
                const cell = document.createElement('div');
                cell.className = 'cal-cell' + (key === todayStr ? ' today' : '');
                const num = document.createElement('div');
                num.className = 'cal-day-num';
                num.textContent = d;
                cell.appendChild(num);
                (buckets[key] || []).forEach(ev => cell.appendChild(eventLink(ev, key)));
                grid.appendChild(cell);
            }
            const total = startDow + daysInMonth;
            const rest = total % 7 === 0 ? 0 : 7 - (total % 7);
            for (let i = 1; i <= rest; i++) {
                const cell = document.createElement('div');
                cell.className = 'cal-cell other-month';
                cell.innerHTML = '<div class="cal-day-num">' + i + '</div>';
                grid.appendChild(cell);
            }
        }

        function render() {
            const names = ['1月','2月','3月','4月','5月','6月',
                           '7月','8月','9月','10月','11月','12月'];
            const el = document.getElementById('calTitle');
            if (el) el.textContent = currentYear + '年 ' + names[currentMonth];
            const buckets = monthBuckets(currentYear, currentMonth);
            renderDays(currentYear, currentMonth, buckets);
            renderGrid(currentYear, currentMonth, buckets);
        }

        // 後方互換。HTMLの onclick から呼ばれていた名前
        function renderCalendar() { render(); }

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
                }))
                .sort((a, b) => (a.start < b.start ? -1 : a.start > b.start ? 1 : 0));
            render();
        }).catch(() => render());
        </script>'''


import re as _re_cleanup

def strip_previous_insertions(html_src):
    """過去のビルドが挿入したSSRブロック(JSON-LD/インラインJSON/フォールバック一覧)を全て除去する。
    これが無いとビルドのたびに1セットずつ蓄積する(2026-06-11に4.2MBまで肥大したバグの恒久対策)。

    末尾の改行は \n* で全て食う。\n? だと挿入側が付ける改行を1本ずつ取り残し、
    ビルドのたびに空行が1行増え続ける(2026-08-10時点で map/calendar に251行ずつたまっていた)。"""
    # ItemList JSON-LD (このスクリプトが挿入したもの)
    html_src = _re_cleanup.sub(
        r'<script type="application/ld\+json">\s*\{"@context":"https://schema\.org","@type":"ItemList".*?</script>\n*',
        '', html_src, flags=_re_cleanup.S)
    # インラインイベントJSON
    html_src = _re_cleanup.sub(
        r'<script type="application/json" id="ssr-events-data">.*?</script>\n*',
        '', html_src, flags=_re_cleanup.S)
    # SSRフォールバック一覧
    html_src = _re_cleanup.sub(
        r'<section class="ssr-event-list".*?</section>\n*',
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
    # 印は生成物にも必ず出るものにする。以前は '// Menu toggle' の行を
    # 印にしていたため、その行を書き換えた次のビルドが
    # 「印が無い」で落ちた(2026-09-08)。移行のため旧印も見る。
    body_close = '</body>'
    idx_start = -1
    for menu_marker in ('<!-- PAGE-JS:START',
                        '<script src="/nav.js" defer></script>\n    <script>',
                        '<script>\n        // Menu toggle'):
        idx_start = html_src.find(menu_marker)
        if idx_start >= 0:
            break
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
