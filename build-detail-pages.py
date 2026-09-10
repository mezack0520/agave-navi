#!/usr/bin/env python3
"""
build-detail-pages.py
events.json + templates/detail.html.tmpl → events/*.html

Usage:
  python3 build-detail-pages.py                 # Generate all pages
  python3 build-detail-pages.py --slug foo-2026  # Generate one page
  python3 build-detail-pages.py --dry-run        # Preview without writing
"""

import json
import os
import re
import sys
import argparse
from datetime import datetime, timedelta
from urllib.parse import quote

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts'))
import sitelib
from sitelib import (
    html_escape, compact_date as make_compact_date, normalize_series_name,
    is_vague_venue as _is_vague, WEEKDAYS_JA, slug_hash as _slug_hash,
    date_to_japanese, is_upcoming, list_sort_key, split_ongoing,
    DESC_MIN_CHARS,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
EVENTS_JSON = os.path.join(SCRIPT_DIR, 'events.json')
# 拡張子は .tmpl。.html のままだと GitHub Pages がリポジトリごと配信するので、
# 未展開のテンプレートが公開URL(/templates/detail.html)として
# index 対象で生き続ける(2026-09-01に是正)。
TEMPLATE_FILE = os.path.join(SCRIPT_DIR, 'templates', 'detail.html.tmpl')
OUTPUT_DIR = os.path.join(SCRIPT_DIR, 'events')
CSS_VERSION = sitelib.CSS_VERSION
JS_VERSION = sitelib.JS_VERSION

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



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
        # 投稿IDをURLから取る。リール(/reel/)とIGTV(/tv/)も投稿として埋め込める。
        # 2026-08-27まで /p/ しか見ておらず、リールのURLだけを持つ回は
        # 埋め込みごと消えていた(plants-garage-market-2026-spring)。
        # return '' で静かに消えるため、頁を見るまで気づけない経路だった。
        import re
        m = re.search(r'/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)', ig_url)
        if m:
            post_id = m.group(1)
        else:
            return ''

    if not ig_url:
        ig_url = f'https://www.instagram.com/p/{post_id}/'

    return f'''        <div class="detail-section detail-instagram-embed">
          <h2 class="detail-section-title" data-kicker="SNS">Instagram投稿</h2>
          <div class="instagram-embed-wrap">
            <iframe src="https://www.instagram.com/p/{post_id}/embed/" loading="lazy" frameborder="0" scrolling="no" allowtransparency="true" allowfullscreen></iframe>
          </div>
          <p class="instagram-embed-link">{sitelib.ext_link(ig_url, 'Instagramで見る')}</p>
        </div>
'''

def split_venue(ev):
    """会場名と住所に分ける。

    events.json の location は「有楽町阪急メンズ東京 1階 メインベース
    （東京都千代田区有楽町2-5-1）」のように住所を括弧に入れて1つの
    文字列で持っている。括弧書きは読みにくいので、表示のときに分ける
    (2026-09-08 指摘)。データ側は触らない。

    括弧の中が都道府県名で始まるものだけ住所とみなす。
    「（雨天中止）」のような但し書きを住所の行に落とさないため。
    """
    venue = (ev.get('location') or ev.get('venue') or '').strip()
    if not venue:
        return ('', '')
    m = re.search(r'[（(]([^（()）]+)[)）]\s*$', venue)
    if not m:
        return (venue, '')
    inner = m.group(1).strip()
    if not any(inner.startswith(p) for p in sitelib.PREF_TO_REGION):
        return (venue, '')
    return (venue[:m.start()].strip(), inner)


def make_venue_value(ev):
    """スペック表の会場欄。会場名と住所を2行に分ける。"""
    name, addr = split_venue(ev)
    if not name or _is_vague(name):
        return _venue_placeholder(ev)
    out = html_escape(name)
    if addr:
        out += f'<span class="venue-addr">{html_escape(addr)}</span>'
    return out


def make_venue_map(ev):
    """会場の地図。**会場欄のすぐ下に置く。**

    以前はページの下のほうに ACCESS の節として置いていた。
    会場名を読んだ人がいちばん知りたいのは「どこ」なので、
    その場で見せる(2026-09-08 指摘)。

    mapQuery が無ければ 会場名+都道府県 で引く。収集で入った回は
    mapQuery を持たないことが多く、それで地図が消えていた。
    """
    map_query = (ev.get('mapQuery') or '').strip()
    venue_name = (ev.get('location') or ev.get('venue') or '').strip()
    pref = (ev.get('prefecture') or '').strip()
    if not map_query and venue_name and not _is_vague(venue_name):
        map_query = f'{venue_name} {pref}'.strip()
    if not map_query:
        return ''

    # 所在を地図の上に文字でも出していたが、会場欄に住所が入っている回では
    # 同じ住所が2行に並んだ(2026-09-08 指摘)。会場欄と地図で足りている。
    q = quote(map_query)
    where = ''
    # 「マップで開く」は埋め込み自身が左上に出すので足さない。
    # 二重に出しても行き先は同じ(2026-08 の判断を踏襲)。
    return f'''          <div class="venue-map">
            {where}<iframe src="https://www.google.com/maps?q={q}&output=embed" width="100%" height="300" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade" title="会場の地図"></iframe>
          </div>
'''


def make_date_hero(ev):
    """画像が無いイベント用: 大きな日付+カテゴリ/地域チップのビジュアルブロック。"""
    d = ev.get('date') or ''
    cat = detect_primary_category(ev)
    pref = ev.get('prefecture') or ev.get('region') or ''
    if d:
        try:
            sdt = datetime.strptime(d, '%Y-%m-%d')
            de = ev.get('dateEnd') or d
            edt = datetime.strptime(de, '%Y-%m-%d')
            big = f'{sdt.month}.{sdt.day}'
            wd = WEEKDAYS_JA[sdt.weekday()]
            sub = f'{sdt.year}年 {wd}曜日'
            if de != d:
                big += f'<span class="dh-tilde">–</span>{edt.month}.{edt.day}'
                sub = f'{sdt.year}年 {wd}〜{WEEKDAYS_JA[edt.weekday()]}曜日'
        except ValueError:
            big, sub = '', ''
    else:
        big, sub = '', '開催日未発表'
    chips = ''.join(f'<span class="dh-chip">{html_escape(x)}</span>' for x in [cat, pref] if x)
    big_html = f'<div class="dh-date">{big}</div>' if big else '<div class="dh-date dh-tbd">Coming</div>'
    return (f'    <div class="date-hero">\n'
            f'      <div class="dh-inner">{big_html}<div class="dh-sub">{html_escape(sub)}</div>'
            f'<div class="dh-chips">{chips}</div></div>\n'
            f'    </div>\n')

def make_hero_section(ev):
    """Hero: imageUrl があれば画像、無ければ日付タイポグラフィのヒーロー(モノクロ)。"""
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
            <span class="info-label">{icon('train')}アクセス</span>
            <span class="info-value">{html_escape(access)}</span>
          </div>'''


def make_og_image(ev):
    """og:image: imageUrl があればそれ、無ければサイト共通OGP"""
    img = ev.get('imageUrl') or ''
    if img:
        return img
    return 'https://agave-navi.com/images/ogp-default.jpg'


def make_share_section(ev):
    """リンクのコピー。

    X と LINE のボタンは外した(2026-09-08)。**押された回数は
    測っていないので「使われていない」とは言えない。**
    分かっているのは、5つ並べるとスマホで1行に収まらないこと。
    リンクをコピーできれば貼り先は本人が選べるので、
    行きたい・カレンダー・コピーの3つに絞った。
    必要になったらここに戻す。
    """
    slug = ev.get('slug', '') or ''
    page_url = f'https://agave-navi.com/events/{slug}.html'
    return f'''        <div class="detail-share">
          <button class="share-btn share-copy" type="button" onclick="(function(b){{const u='{page_url}';navigator.clipboard.writeText(u).then(()=>{{const o=b.querySelector('span').textContent;b.querySelector('span').textContent='コピー済';setTimeout(()=>b.querySelector('span').textContent=o,1500);}});}})(this);" aria-label="リンクをコピー">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
            <span>リンクをコピー</span>
          </button>
        </div>
'''


def make_tags_csv(ev):
    return ','.join(ev.get('tags', []) or [])


NOINDEX_EVENT_SLUGS = []  # フルビルド時に収集し sitemap 用 manifest に出力


def _is_thin_event(ev):
    """有用性の低い(薄い)イベント判定: 出典(url/sourceUrl)無し、または出典があっても
    実質情報(time / imageUrl / 説明が sitelib.DESC_MIN_CHARS 字以上)が無いものは
    noindex 対象(AdSense低品質対策)。閾値は audit.py の is_thin と同じ定数を見る。"""
    desc = ev.get('description') or ''
    has_src = bool((ev.get('url') or '').strip()) or bool((ev.get('sourceUrl') or '').strip())
    has_substance = (bool((ev.get('time') or '').strip())
                     or bool((ev.get('imageUrl') or '').strip())
                     or len(desc) >= DESC_MIN_CHARS)
    return not (has_src and has_substance)


def make_prefecture_row(ev):
    """会場名が出せない回に都道府県の行を足す。
    スペック表には都道府県の行が無いため、会場欄を「記録なし」にすると
    地理情報が完全に消えてしまう(2026-08-13)。"""
    venue = (ev.get('venue') or ev.get('location') or '').strip()
    if venue and not _is_vague(venue):
        return ''
    pref = (ev.get('prefecture') or '').strip() or (ev.get('region') or '').strip()
    if not pref:
        return ''
    return ('\n          <div class="info-row">'
            '\n            <span class="info-label">地域</span>'
            f'\n            <span class="info-value">{html_escape(pref)}</span>'
            '\n          </div>')


def _venue_placeholder(ev):
    """会場が無いときの表示。終了済みに「会場未定」は誤り(未定=これから決まる)。
    終わった回で会場が分からないものは記録が無いだけなので「記録なし」と出す。"""
    end = (ev.get('dateEnd') or ev.get('date') or '')
    today = sitelib.today_jst()
    if end and end < today:
        return '記録なし'
    return '会場未定'


def make_cancel_notice(ev):
    """中止・延期の告知。概要より前に置く。

    削除ではなく中止として残す方針(listing-policy.json の cancelledOrPostponed)。
    消すとURLが404になり、共有リンクやブックマークを踏んだ人には何も伝わらない。
    「◯◯ 中止」で検索して来た人に答えるのが一覧サイトの役目。
    """
    if not sitelib.is_cancelled(ev):
        return ''
    label = sitelib.cancel_label(ev)
    reason = (ev.get('cancelReason') or '').strip()
    on = (ev.get('cancelledOn') or '').strip()
    notice = (ev.get('cancelNoticeUrl') or ev.get('sourceUrl')
              or ev.get('url') or '').strip()
    lines = [f'<span class="notice-head">この回は{html_escape(label)}になりました</span>']
    body = []
    if reason:
        body.append(f'理由: {html_escape(reason)}')
    if on:
        body.append(f'主催者の告知: {html_escape(sitelib.date_to_japanese(on))}')
    if body:
        lines.append('<p>' + ' / '.join(body) + '</p>')
    if notice:
        lines.append('<p>'
                     + sitelib.ext_link(notice, '主催者の告知を見る')
                     + '</p>')
    lines.append('<p>最新の情報は主催者の発表をご確認ください。</p>')
    return ('        <div class="event-notice-cancelled">\n          '
            + '\n          '.join(lines) + '\n        </div>')


def make_affiliate_block(ev):
    """アフィリエイト枠。出典(url/sourceUrl)がある回には出す。

    中止の回には出さない。中止の告知のすぐ下に買い物の導線があるのは
    体裁が悪いし、来場を前提にした「当日の持ち物」の枠なので文脈も合わない。

    2026-07-30まではAdSense審査を意識して「薄い」判定の回を除外していたが、
    審査を断念したため条件を緩めた。出典があれば実在が確認できたイベントであり、
    説明文の長さで収益動線を落とす理由はない。
    出典がまったく無い回(アーカイブの49件)だけ除外する。"""
    if sitelib.is_cancelled(ev):
        return ''
    if not ((ev.get('url') or '').strip() or (ev.get('sourceUrl') or '').strip()):
        return ''
    tags = make_tags_csv(ev)
    return (f'        <section class="affiliate-section" data-tags="{tags}"></section>')


def make_robots_meta(ev):
    """終了30日超 または 有用性の低い(薄い)イベントには noindex を付与。"""
    from datetime import datetime, timedelta
    noindex = False
    end = ev.get('dateEnd') or ev.get('date') or ''
    if end:
        try:
            if datetime.strptime(end, '%Y-%m-%d') < datetime.strptime(
                    sitelib.today_jst(), '%Y-%m-%d') - timedelta(days=30):
                noindex = True
        except ValueError:
            pass
    if _is_thin_event(ev):
        noindex = True
    if noindex:
        slug = ev.get('slug')
        if slug and slug not in NOINDEX_EVENT_SLUGS:
            NOINDEX_EVENT_SLUGS.append(slug)
        return 'noindex,follow'
    return 'index,follow'


def breadcrumb_items(ev):
    """パンくずの項目。表示とJSON-LDの両方がここから作られる。

    以前は表示用・LD用・位置番号用の3関数に分かれていて、
    片方だけ直すと食い違った。根っこの呼び名も「ホーム」のままで、
    トップの絞り込みの現在地「全国」と割れていた(2026-09-08 指摘)。
    """
    items = [sitelib.CRUMB_ROOT]
    region = (ev.get('region') or '').strip()
    pref = (ev.get('prefecture') or '').strip()
    # 実在する頁を指す。以前は `/?region=関西` `/?region=関西&pref=大阪` という
    # トップの絞り込みクエリを指していた。同じ内容の `/region/kansai/`
    # `/pref/osaka/` が別にあるのに、パンくずも BreadcrumbList も
    # そちらを向いていない。**クエリURLは正規化されない**ので、
    # 検索側には階層が無いのと同じだった(2026-09-10)。
    # 47県・9地域とも generate-landing-pages.py が全イベントから作るので、
    # 詳細ページがある回の県・地域の頁は必ず存在する。
    if region:
        items.append((region, f'/region/{sitelib.region_slug(region)}/'))
    if pref:
        items.append((pref, f'/pref/{sitelib.pref_slug(pref)}/'))
    items.append((ev.get('name') or '', None))
    return items


def make_event_jsonld(ev):
    """schema.org Event JSON-LD. Skip entirely if no date (avoid invalid empty startDate)."""
    if not ev.get('date'):
        return ''
    from datetime import datetime, timedelta
    name = html_escape(ev.get('name', ''))
    date = ev.get('date', '')
    end = ev.get('dateEnd') or date
    _raw_venue = (ev.get('venue') or ev.get('location') or '').strip()
    # 都道府県名・「調整中」等は会場名ではない。Place.name に入れると
    # 構造化データが誤った施設を指すため、その場合は名前を持たせない。
    venue = html_escape(_raw_venue) if not _is_vague(_raw_venue) else ''
    # 空文字の name を出すと、構造化データ上「名前が空の会場」を主張することになる。
    # 会場が分からない回はキーごと省く。
    venue_name_field = f'\n      "name": "{venue}",' if venue else ''
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
        # 但し書きの「無料」に引っかからせない。判定は sitelib が単一情報源。
        # 素の `'無料' in admission` だと「一般入場無料(先行入場はチケット制)」が
        # price="0" の Offer になり、リッチリザルトが「無料」と申告する(2026-09-05)。
        is_free = sitelib.admission_is_free(admission)
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
      "@type": "Place",{venue_name_field}
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

def official_link_items(ev):
    """公式情報の行に出す (URL, 種別, 表示文字)。

    脚注の「出典」もこれを見て、行に出したURLは繰り返さない。
    同じリンクが同じページに2回出ていた(2026-09-08 指摘)。
    """
    items, seen_kinds, seen_urls = [], set(), set()
    has_ig_embed = bool(ev.get('instagramPostId') or ev.get('instagramUrl'))

    def add(url, field):
        u = (url or '').strip()
        if not u or u in seen_urls:
            return
        kind, text = sitelib.link_kind(u, field)
        if not kind or kind in seen_kinds:
            return
        # 本文にInstagramの埋め込みが出る回は、同じ投稿への行を重ねない
        if kind == 'Instagram' and has_ig_embed and text == 'この回の告知':
            return
        seen_urls.add(u)
        seen_kinds.add(kind)
        items.append((u, kind, text))

    add(ev.get('url'), 'url')
    add(ev.get('sourceUrl'), 'sourceUrl')
    add(ev.get('instagramUrl'), 'instagramUrl')

    if not items and not has_ig_embed:
        name = ev.get('name', '')
        if name:
            venue = ev.get('venue') or ev.get('location') or ''
            q = quote(f'{name} {venue} 2026'.strip())
            items.append((f'https://www.google.com/search?q={q}', '検索',
                          'Googleで探す'))
    return items


def make_official_links_rows(ev):
    """公式情報の行。ラベルに種別、値に行き先を出す。

    以前は全部の行のラベルが「リンク」で、値のほうに
    「Instagram投稿」「関連サイト」と書いていた。読む順が逆だった。
    「関連サイト」は関係が曖昧で何も伝わらないのでやめた
    (2026-09-08 指摘)。種別と文字は sitelib.link_kind が唯一の持ち主。
    """
    rows = []
    for u, kind, text in official_link_items(ev):
        rows.append(
            f'          <div class="info-row">\n'
            f'            <span class="info-label">{html_escape(kind)}</span>\n'
            f'            <span class="info-value">'
            f'{sitelib.ext_link(u, text)}</span>\n'
            f'          </div>'
        )
    return '\n'.join(rows)


def make_admission_row(ev):
    """Admission info row"""
    admission = ev.get('admission', '')
    if not admission:
        return ''
    return f'''          <div class="info-row">
            <span class="info-label">{icon('ticket')}入場料</span>
            <span class="info-value">{admission}</span>
          </div>'''

def make_time_row(ev):
    """Time info row。日時行(dateDisplayFull)に時間が含まれるケースでは重複するため出さない。"""
    time_str = ev.get('time', '')
    if not time_str:
        return ''
    if ev.get('date'):
        return ''  # dateがあればmake_date_display_fullがtimeを含む
    return f'''          <div class="info-row">
            <span class="info-label">{icon('clock')}時間</span>
            <span class="info-value">{time_str}</span>
          </div>'''



# ---------------------------------------------------------------------------
# Main build
# ---------------------------------------------------------------------------

def build_page(template, ev, ctx):
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
        '{{dateDisplayFull}}': make_date_display_full(ev),
        '{{region}}': region,
        '{{regionEncoded}}': quote(region),
        '{{venue}}': make_venue_value(ev),
        '{{prefectureRow}}': make_prefecture_row(ev),
        '{{description}}': html_escape(ev.get('description', '')),
        '{{metaDescription}}': html_escape(make_meta_description(ev)),
        # gcalUrl は {{gcalButton}} に取り込んだ(2026-09-08)。
        # 中止の回はカウントダウンを出さない。「あと14日」は開催を約束する表示。
        # カレンダー登録も出さない。中止の予定を人の予定表に入れさせない
        '{{cancelledAttr}}': (' data-cancelled="1"' if sitelib.is_cancelled(ev) else ''),
        '{{gcalButton}}': ('' if sitelib.is_cancelled(ev) else
                           f'        <a href="{make_gcal_url(ev)}" target="_blank"'
                           f' rel="noopener" class="gcal-btn">'
                           f'<svg viewBox="0 0 24 24" fill="none"'
                           f' stroke="currentColor" stroke-width="2">'
                           f'<rect x="3" y="4" width="18" height="18" rx="2"/>'
                           f'<line x1="3" y1="10" x2="21" y2="10"/>'
                           f'<line x1="8" y1="2" x2="8" y2="6"/>'
                           f'<line x1="16" y1="2" x2="16" y2="6"/></svg>'
                           f'カレンダー</a>'),
        '{{cssVersion}}': CSS_VERSION,
        '{{jsVersion}}': JS_VERSION,
        '{{heroSection}}': make_hero_section(ev),
        '{{eventJsonLd}}': make_event_jsonld(ev),
        '{{accessRow}}': make_access_row(ev),
        '{{robotsMeta}}': make_robots_meta(ev),
        '{{officialLinksRows}}': make_official_links_rows(ev),
        '{{ogImage}}': make_og_image(ev),
        '{{shareSection}}': make_share_section(ev),
        '{{instagramSection}}': make_instagram_section(ev),
        '{{venueMap}}': make_venue_map(ev),
        '{{admissionRow}}': make_admission_row(ev),
        '{{timeRow}}': make_time_row(ev),
        '{{enrichedContent}}': make_enriched_content(ev, ctx),
        '{{siteHeader}}': sitelib.site_header(),
        '{{correctionNote}}': sitelib.correction_note('/'),
        '{{breadcrumb}}': sitelib.breadcrumb_html(breadcrumb_items(ev)),
        '{{breadcrumbJsonLd}}': sitelib.crumb_jsonld(breadcrumb_items(ev)),
        '{{affiliateBlock}}': make_affiliate_block(ev),
        '{{cancelNotice}}': make_cancel_notice(ev),
        '{{heroMetaNote}}': make_hero_meta_note(ev),
        '{{dataSummary}}': make_data_summary(ev, ctx),
        '{{primaryCategory}}': html_escape(detect_primary_category(ev)),
        '{{weatherRow}}': make_weather_row(ev, ctx),
        '{{siteFooter}}': sitelib.site_footer(),
    }

    html = template
    for key, value in replacements.items():
        html = html.replace(key, value)

    return html




def make_hero_meta_note(ev):
    """最終更新と出典を脚注1行にまとめる。about.html で参照元と最終更新日の明記を
    掲載方針としているため、表から外しても情報自体は必ず残す。
    片方が欠けても区切り文字が浮かないよう、ここで組み立てる。"""
    parts = []

    last = ev.get('updatedAt') or ev.get('enrichedAt') or ev.get('addedDate')
    if last:
        try:
            from datetime import datetime as _dt
            dt = _dt.strptime(last[:10], '%Y-%m-%d')
            disp = f'{dt.year}年{dt.month}月{dt.day}日'
        except (ValueError, TypeError):
            disp = str(last)
        parts.append(f'最終更新 {html_escape(disp)}')

    # 出典の優先順は url → dataSource → 主催者のSNS → スタッフ収集情報。
    # 2026-09-07 に dataSource を読むようにしたが、見ていたのはそこまでで、
    # **sourceUrl / instagramUrl しか持たない回は素通しだった**(2026-09-08)。
    # 主催者本人の投稿を同じ頁に埋め込んでおきながら、脚注は
    # 「出典 スタッフ収集情報」と名乗っていた回が24件あった。
    # 09-07 に直したのと同じ嘘で、経路が違うだけ。
    # 検査は audit.source_label_understated。
    url = (ev.get('url') or '').strip()
    src_text = (ev.get('dataSource') or '').strip()
    if not url and not src_text:
        # 投稿URL(その回の告知)をアカウントURLより先に採る
        url = ((ev.get('instagramUrl') or '').strip()
               or (ev.get('sourceUrl') or '').strip())
    if url:
        # 表の行に同じURLが出ているなら繰り返さない。
        # 「Instagram この回の告知」の下に「出典 Instagram」が続いていた
        # (2026-09-08 指摘)。脚注に残す値打ちがあるのは最終更新と、
        # 画像を自分のドメインから配っているときの画像の出どころ。
        _shown = {u for u, _k, _t in official_link_items(ev)}
        if url not in _shown:
            # 表記は sitelib.link_kind が唯一の持ち主。ここで
            # 「公式Instagram」と別名を作ると、表の行と脚注で呼び名が割れる
            kind, _t = sitelib.link_kind(url, 'url' if ev.get('url') else None)
            parts.append('出典 ' + sitelib.ext_link(url, kind))
    else:
        # dataSource は出所を人間語で持つ(例: 主催者からの掲載申請)。
        # url が無い回をすべて「スタッフ収集情報」と名乗ると、
        # 主催者本人から受け取った回まで自社収集だと偽ることになる。
        # 2026-09-07 まで実際にそうなっていた(agave-popup-market-nagoya-2026-07)。
        parts.append('出典 ' + html_escape(src_text) if src_text
                     else '出典 スタッフ収集情報')

    # 自サイトに置いたアイキャッチは、取得元を明示する。
    # 他人の告知画像を複製して自分のドメインから配っているので、
    # どこから来たかを黙っておくのは筋が通らない(2026-09-08)。
    isrc = (ev.get('imageSource') or '').strip()
    if isrc and (ev.get('imageUrl') or '').startswith('https://agave-navi.com/images/events/'):
        parts.append('画像 ' + sitelib.ext_link(isrc, '主催者の告知より'))

    if not parts:
        return ''
    return ('<p class="eh-meta-note">' + '<span class="ehm-sep">/</span>'.join(parts)
            + '</p>')


# ---------------------------------------------------------------------------
# Enriched content (AdSense / SEO 向け本文増強セクション)
# ---------------------------------------------------------------------------
# 設計方針 (2026-06 改修):
#   ページ間で共通する定型文(boilerplate)の比率を下げ、イベント固有の
#   実データから生成されるコンテンツを主役にする。
#   - 固定文は カテゴリ×複数バリアント とし slug ハッシュで分散
#   - 開催履歴 / 近隣イベント / 同会場 / FAQ / 統計サマリは
#     events.json の実データのみから生成(憶測・創作はしない)


GUIDE_LINKS = [
    ('agave-winter-hardiness.html', 'アガベの耐寒性ガイド: 屋外越冬できる品種と室内必須種の見分け方', 'アガベ'),
    ('agave-titanota-care.html',    'アガベ チタノタ系の管理: 美観を保ちながら長く育てるコツ',       'アガベ'),
    ('titanota-oteroi-labels.html', 'チタノタとオテロイ: イベントで迷わない品種ラベルの読み方',      'アガベ'),
    ('agave-bareroot-rooting.html', 'ベアルート株の発根管理: イベントで買った抜き苗を枯らさない手順', 'アガベ'),
    ('pachypodium-gracilius.html',  'パキポディウム グラキリスを枯らさない: 実生株と現地球の管理差', 'コーデックス'),
    ('caudex-intro.html',           '塊根植物(コーデックス)入門: 夏型・冬型の見分け方と選び方',     'コーデックス'),
    ('adenium-wintering.html',      'アデニウム(砂漠の薔薇)の冬越し完全ガイド: 種類別の温度管理',   'コーデックス'),
    ('wintering-tokyo.html',        '東京近郊での冬越し: 練馬から学ぶ屋外・軒下・不織布・室内の使い分け', '管理'),
    ('rainy-season-care.html',      '梅雨〜真夏のアガベ・塊根植物管理: 遮光・水やり・風通しの実務',  '管理'),
    ('failure-analysis.html',       '失敗から学ぶ塊根管理: 過去に枯らした植物と原因分析',           '管理'),
    ('sokubaikai-tips.html',        '植物即売会で失敗しないチェックリスト: 当日の流れと買付けのコツ', '購入'),
    ('plant-health-check.html',     'イベントで失敗しない株の選び方: 葉・根・害虫のチェックポイント', '購入'),
    ('event-types-guide.html',      '植物イベントの種類と選び方: 即売会・マルシェ・展示会の違い',    'イベント'),
    ('event-data-2026.html',        'データで見る2026年の植物イベント: 開催数・地域・入場料の傾向',  'イベント'),
    ('soil-pot-repot.html',         'アガベ・塊根植物の用土と鉢: 配合例と植え替えの基本手順',        '管理'),
    ('agave-seedling.html',         'アガベ実生入門: 種まきから1年目までの管理カレンダー',           'アガベ'),
    ('pest-treatment.html',         'アガベ・多肉の病害虫対策: カイガラムシ・ハダニ・根腐れの治療',  '管理'),
    ('offsets-guide.html',          '子株(カキコ)の外し方と育成: 失敗しない株分けの手順',            'アガベ'),
    ('grow-light-basics.html',      '植物育成LEDライト入門: アガベ室内管理の徒長を防ぐ',             '管理'),
]

# カテゴリ解説: 1カテゴリ複数バリアント。slugハッシュで安定的に1つ選ぶ。
CATEGORY_INTROS = {
    '即売会': [
        (
            '即売会は、複数の生産者・販売店が一堂に集まり、その場で植物を購入できる形式のイベントです。'
            '通信販売では出会えない一点物の選抜株を実物を見て選べること、'
            '生産者から株の育成歴や管理のコツを直接聞けることが最大の魅力で、'
            '人気生産者のブースには開場直後から行列ができる傾向があります。'
        ),
        (
            '店頭やネット通販と違い、即売会では生産者が当日持ち込む株を「流通に乗る前」の状態で選べます。'
            '同じ品種でも株ごとに姿が大きく異なるアガベや塊根植物では、'
            '複数ブースを見比べながら状態と価格のバランスで選べる対面形式の利点が特に大きく、'
            '発根状態や用土の様子をその場で確認・質問できるのも即売会ならではです。'
        ),
        (
            '即売会形式のイベントは、はじめての方でも気軽に参加できますが、'
            '人気株は開場直後の数十分で動くことが多いのが実情です。'
            '出店者リストの事前確認と予算の上限決めが当日の満足度を大きく左右します。'
            'なお、株を手に取って確認したい場合は出店者へ一声かけるのが会場での一般的なマナーです。'
        ),
    ],
    'マルシェ': [
        (
            '植物マルシェは、即売会よりカジュアルな雰囲気で、飲食やワークショップと併催されることが多い形式です。'
            '出店者は園芸店・生産者・個人作家・鉢メーカーなど多彩で、'
            '植物本体だけでなく鉢・用土・小物まで一度に揃えられます。'
            '家族連れでも立ち寄りやすく、多肉植物・塊根植物の入り口としても向いています。'
        ),
        (
            'マルシェ型のイベントは地域密着の開催が多く、植物専門の即売会に比べて敷居が低いのが特徴です。'
            '価格帯も入門向けの小苗から愛好家向けの選抜株まで幅広く、'
            '掘り出し物との出会いは早い時間帯ほど多い傾向があります。'
            '雑貨・飲食ブースと合わせて、半日かけてゆっくり回るのに向いたイベントです。'
        ),
        (
            '屋外開催が中心のマルシェは、天候の影響を受けやすい一方で開放的な雰囲気が魅力です。'
            '寄せ植え体験や植え替えワークショップなど参加型の企画が組まれることも多く、'
            '買う・見るだけでなく「体験する」楽しみ方ができます。'
            '当日の開催可否・時間変更は主催者のSNSで直前に告知されることが多いので出発前の確認がおすすめです。'
        ),
    ],
    '大型イベント': [
        (
            '大型イベントは、出店者数・来場者数とも最大級の植物イベントです。'
            '広域から生産者・専門店が集まるため、通常の即売会では入手しづらい選抜株や輸入株に出会える可能性が高まります。'
            '1日で回り切れない規模のことも多く、事前に出店者一覧と会場マップを確認して'
            '目的のブースに優先順位を付けておくのが効率的です。'
        ),
        (
            '複数日にわたって開催される大型イベントでは、初日と最終日で楽しみ方が変わります。'
            '品揃えを重視するなら初日の開場直後、価格との折り合いを重視するなら'
            '在庫整理が進む最終日の午後、という回り方がよく知られています。'
            '再入場の可否やリストバンドの扱いは主催者ごとに異なるため、公式案内の確認をおすすめします。'
        ),
    ],
    '展示会': [
        (
            '展示会は販売よりも「観賞」と「情報交換」が中心のイベントです。'
            '長年の愛好家が育てた銘品株やコンテスト出品株の実物を見られる貴重な機会で、'
            '写真では伝わらないサイズ感・葉の質感・株姿の作り込みを学ぶ場として活用できます。'
        ),
        (
            '展示中心のイベントでは、即売コーナーが併設される場合でも販売株は限られることが多いため、'
            '「銘品を観察して育成のヒントを得る」視点で時間を確保するのがおすすめです。'
            '気になる株はラベルの品種名・出品者名を控えておくと、後日の調査や入手検討に役立ちます。'
        ),
    ],
    '展示販売会': [
        (
            '展示販売会は、観賞向けの展示と即売を組み合わせた構成のイベントです。'
            '銘品株の解説を聞きながら、近い系統の入手可能な株をその場で探せるのが大きな利点で、'
            '初心者から中・上級者まで幅広く楽しめます。'
        ),
    ],
    '講演': [
        (
            '講演・トークイベントは、生産者や愛好家が長年の栽培・採集経験を直接共有する場です。'
            '書籍やネット記事には載らない現場の知見 — 失敗事例、地域別の管理差、流通の裏側 — を'
            '聞ける機会として、栽培経験者ほど得るものが大きい形式です。'
        ),
    ],
}

def detect_primary_category(ev):
    """tags から主カテゴリを判定して、CATEGORY_INTROS のキーを返す。"""
    tags = ev.get('tags') or []
    priority = [
        ('大型イベント', '大型イベント'), ('大型', '大型イベント'),
        ('展示販売会', '展示販売会'), ('展示会', '展示会'),
        ('講演', '講演'), ('マルシェ', 'マルシェ'), ('即売会', '即売会'),
    ]
    for tag, key in priority:
        if tag in tags:
            return key
    return '即売会'

def make_category_intro(ev):
    """(折りたたみ内で使用) カテゴリ解説文のみ返す。"""
    cat = detect_primary_category(ev)
    variants = CATEGORY_INTROS.get(cat, CATEGORY_INTROS['即売会'])
    return variants[_slug_hash(ev.get('slug')) % len(variants)]

# --- 来場前チェックリスト(カテゴリ別バリアント + 実データ差し込み) ---

_TIPS_VARIANTS = {
    '即売会': [
        [
            '開場前に整理券配布や入場列が発生することが多い形式です。目当ての生産者がある場合は、開場の60〜90分前到着を見込んでおくと安心です。',
            '株を運ぶ大きめのトートバッグ・苗運搬用の緩衝材・現金(小銭/小額紙幣)の準備がおすすめです。人気株は即決が求められる場面が多いため、価格上限を事前に決めておくと迷いません。',
        ],
        [
            '出店者リストが公開されている場合は事前に確認し、目当てのブースの位置と回る順番を決めておくと当日の動きに無駄がなくなります。',
            '支払いは出店者によって現金のみの場合があります。キャッシュレス対応を過信せず、現金を多めに用意しておくのが無難です。購入株の持ち帰り用に底の安定したバッグもあると安心です。',
        ],
    ],
    'マルシェ': [
        [
            'カジュアルな雰囲気のマルシェは滞在時間が長くなりがちです。飲食ブースが併設されることも多いので、半日ほど余裕を持ったスケジュールがおすすめです。',
            '鉢・用土・小物などの周辺アイテムも揃うため、手持ちの鉢のサイズメモや既存株の写真があると組み合わせ買いがスムーズです。',
        ],
        [
            '屋外会場の場合は天候対策(帽子・飲み物・雨具)を忘れずに。天候による開催可否は主催者SNSで当日朝に告知されることが多いので、出発前の確認をおすすめします。',
            '混雑のピークは開場直後と昼前後になる傾向があります。ゆっくり見たい場合は午後の時間帯も選択肢です。ただし人気の植物は午前中に動くことが多い点は織り込んでおいてください。',
        ],
    ],
    '大型イベント': [
        [
            '複数日開催・出店者多数の大型イベントは、事前に公式の出店者一覧・会場マップを確認して回るルートを決めてから来場するのが効率的です。',
            '1日では回り切れない規模が多いため、初日午前で全体を俯瞰してから目的の株を購入する2段構えも有効です。再入場条件(半券・リストバンド)の確認をお忘れなく。',
        ],
    ],
    '展示会': [
        [
            '展示中心のイベントは販売株が限られる場合があります。購入目的というより「銘品を観察して育成のヒントを得る」視点で時間を確保するのがおすすめです。',
            'カメラ・メモの準備をして、気になる株のラベル(品種名・出品者)を控えておくと後日の調査・購入検討に役立ちます。',
        ],
    ],
}

def make_visit_tips(ev):
    """カテゴリ別バリアント + admission/time/会場の実データでチェックリストを生成。"""
    cat = detect_primary_category(ev)
    region = ev.get('region') or ''
    pref = ev.get('prefecture') or ''
    # venue は location へフォールバックさせる(他の会場表示は 339/513/1008行で
    # 既にフォールバック済みで、ここだけ venue 単独だった)。どちらも無い回は
    # 「会場は東京(会場)です」という空括弧が出ていたため括弧ごと省く(2026-08-10: 123頁)。
    venue = ev.get('venue') or ev.get('location') or ''
    admission = (ev.get('admission') or '').strip()
    time_str = (ev.get('time') or '').strip()
    # 本文の「入場無料のイベントです」も admission_is_free で判定する。
    # 2026-09-05 の修正はFAQと要約の2か所だけで、ここが残っていた(有料9件)。
    is_free = sitelib.admission_is_free(admission)

    variants = _TIPS_VARIANTS.get(cat) or [[
        '開場時間・整理券の有無は主催者の公式情報を直前に再確認することをおすすめします。天候による会期変更にも備えて、当日朝の最新告知をチェックしてください。',
    ]]
    tips = list(variants[_slug_hash(ev.get('slug')) % len(variants)])

    if region:
        tips.append(
            f'会場は{html_escape(pref or region)}'
            + (f'({html_escape(venue)})' if venue and not _is_vague(venue) else '')
            + 'です。'
            '公共交通機関でのアクセスを基本に、休日の駐車場混雑・周辺道路の状況も'
            '合わせて確認しておくと当日のスケジュールが組みやすくなります。'
        )
    if is_free:
        tips.append('入場無料のイベントです。会場によっては協賛・カンパ箱が設置されることもあるため、小銭があると気持ちよく参加できます。')
    elif admission:
        tips.append(f'入場料は「{html_escape(admission)}」です。前売り・当日券の差や再入場のルールは公式情報でご確認ください。')
    if time_str:
        tips.append(f'開催時間は{html_escape(time_str)}です。人気株は開場直後に動くことが多いため、購入目的の場合は開場時刻を基準に予定を組むのがおすすめです。')

    return '\n'.join(f'            <li>{t}</li>' for t in tips)


def make_visitor_guide(ev):
    """カテゴリ解説+来場チェックリストを1つの折りたたみに。
    定型文が本文を占拠しない(ユーザーからの指摘対応)一方、開けば読める＆クローラにも見える。"""
    cat = detect_primary_category(ev)
    intro = make_category_intro(ev)
    tips = make_visit_tips(ev)
    return (
        f'        <details class="visitor-guide detail-enriched">\n'
        f'          <summary><span class="vg-icon">?</span>はじめての{html_escape(cat)}ガイド — 楽しみ方と来場前チェック</summary>\n'
        f'          <div class="vg-body">\n'
        f'            <p>{html_escape(intro)}</p>\n'
        f'            <ul class="visit-tips-list">\n{tips}\n            </ul>\n'
        f'          </div>\n'
        f'        </details>\n'
    )

# --- シリーズ開催履歴 (同名イベントの過去回・別回) ---




def make_chip_date(e, today):
    """カードの日付列(HTML)。範囲は2行に整形して中途半端な折返しを防ぐ。
    当年: "7.12" / "7.25(–26)" 、他年: 年を1行目に。"""
    d = e.get('date') or ''
    if not d:
        return '未定'
    de = e.get('dateEnd') or d
    cur_year = today[:4]
    lines = []
    if d[:4] != cur_year:
        lines.append(d[:4])
    main = f"{int(d[5:7])}.{int(d[8:10])}"
    if de and de != d:
        to = f"–{int(de[8:10])}" if de[5:7] == d[5:7] else f"–{int(de[5:7])}.{int(de[8:10])}"
        lines.append(main)
        lines.append(f'<span class="mc-to">{to}</span>')
    else:
        lines.append(main)
    return '<span class="mc-l">' + '</span><span class="mc-l">'.join(lines) + '</span>' 

def make_mini_card(e, today, show_state=True):
    """イベントへのカード型リンク(モノクロ)。"""
    dd = make_chip_date(e, today)
    place = e.get('prefecture') or e.get('region') or ''
    venue = e.get('location') or e.get('venue') or ''
    if _is_vague(venue) or venue == place:
        venue = ''
    meta = ' / '.join(x for x in [place, venue] if x)
    d_end = e.get('dateEnd') or e.get('date') or ''
    ended = show_state and bool(d_end) and d_end < today
    state = '<span class="mc-state">終了</span>' if ended else ''
    meta_html = f'<span class="mc-meta">{html_escape(meta)}</span>' if meta else ''
    return (f'<a class="mini-card{" is-ended" if ended else ""}" href="/events/{e["slug"]}.html">'
            f'<span class="mc-date">{dd}</span>'
            f'<span class="mc-body"><span class="mc-name">{html_escape(e.get("name",""))}</span>{meta_html}</span>'
            f'{state}</a>')

def make_series_history(ev, ctx):
    key = normalize_series_name(ev.get('name'))
    if len(key) < 4:
        return ''
    siblings = [e for e in ctx['series'].get(key, []) if e['slug'] != ev.get('slug')]
    if not siblings:
        return ''
    siblings = sorted(siblings, key=lambda e: e.get('date') or '0000', reverse=True)[:6]
    today = ctx['today']
    cards = ''.join(make_mini_card(e, today) for e in siblings)
    my_end = ev.get('dateEnd') or ev.get('date') or ''
    all_ended = bool(my_end) and my_end < today and all(
        (e.get('dateEnd') or e.get('date') or '9999') < today for e in siblings)
    watch_note = ''
    if all_ended:
        watch_note = ('          <p class="series-watch-note">次回開催は未発表です。'
                      '主催者の公式発信を継続的に確認しており、告知を確認し次第掲載します。'
                      '新しい掲載は<a href="/new/">新着ページ</a>から確認できます。</p>\n')
    return (
        f'        <div class="detail-section detail-enriched">\n'
        f'          <h2 class="detail-section-title" data-kicker="SERIES">このイベントの開催履歴・関連回</h2>\n'
        f'          <div class="mini-grid">{cards}</div>\n'
        f'{watch_note}'
        f'        </div>\n'
    )


# --- 近隣・今後のイベント (静的リンク。クローラからも見える) ---

def make_nearby_events(ev, ctx):
    today = ctx['today']
    # 開始日で切ると、いま開催中の回が「今後のイベント」から落ちる。
    # 開催予定/終了の別は sitelib(dateEnd基準)が単一情報源。
    pool = [e for e in ctx['events']
            if e.get('slug') != ev.get('slug') and is_upcoming(e, today)]
    skey = normalize_series_name(ev.get('name'))
    if len(skey) >= 4:
        pool = [e for e in pool if normalize_series_name(e.get('name')) != skey]
    pref = ev.get('prefecture')
    region = ev.get('region')
    same_pref = sorted([e for e in pool if pref and e.get('prefecture') == pref],
                       key=lambda e: list_sort_key(e, today))
    same_region = sorted([e for e in pool if e.get('region') == region and e not in same_pref],
                         key=lambda e: list_sort_key(e, today))
    picks = (same_pref + same_region)[:5]
    if not picks:
        picks = sorted(pool, key=lambda e: list_sort_key(e, today))[:5]
        if not picks:
            return ''
        scope = '全国'
    elif all(e.get('prefecture') == pref for e in picks):
        # 全件が同一都道府県のときだけ県名を名乗る(見出しと中身の不一致防止)
        scope = html_escape(pref)
    else:
        scope = html_escape(region or '近隣') + 'エリア'

    d_end = ev.get('dateEnd') or ev.get('date') or ''
    is_past = bool(d_end) and d_end < today
    if is_past:
        lead = f'このイベントは終了していますが、{scope}では今後も植物イベントの開催が予定されています。'
    else:
        lead = f'{scope}で今後開催が予定されている植物イベントです。あわせて予定を立てる際の参考にどうぞ。'

    cards = ''.join(make_mini_card(e, today, show_state=False) for e in picks)
    title = f'{scope}の今後の植物イベント'
    return (
        f'        <div class="detail-section detail-enriched">\n'
        f'          <h2 class="detail-section-title" data-kicker="UPCOMING">{title}</h2>\n'
        f'          <p class="section-note">{lead}</p>\n'
        f'          <div class="mini-grid">{cards}</div>\n'
        f'        </div>\n'
    )


# --- 同会場の他イベント ---


def make_venue_history(ev, ctx):
    v = (ev.get('location') or '').strip()
    if _is_vague(v):
        return ''
    others = [e for e in ctx['venues'].get(v, []) if e.get('slug') != ev.get('slug')]
    if not others:
        return ''
    others = sorted(others, key=lambda e: e.get('date') or '', reverse=True)[:5]
    today = ctx['today']
    cards = ''.join(make_mini_card(e, today) for e in others)
    return (
        f'        <div class="detail-section detail-enriched">\n'
        f'          <h2 class="detail-section-title" data-kicker="VENUE">{html_escape(v)}で開催される他のイベント</h2>\n'
        f'          <p class="section-note">同じ会場での開催情報です。会場の雰囲気やアクセスの参考になります。</p>\n'
        f'          <div class="mini-grid">{cards}</div>\n'
        f'        </div>\n'
    )


# --- よくある質問 (実データのみ + FAQPage JSON-LD) ---

def _faq_pairs(ev, ctx):
    today = ctx['today']
    name = ev.get('name', '')
    d = ev.get('date') or ''
    d_end = ev.get('dateEnd') or d
    is_past = bool(d_end) and d_end < today
    pairs = []

    if d:
        dd = make_date_display_full(ev)
        if is_past:
            a = f'{name}は{dd}に開催されました。'
        else:
            a = f'{dd}に開催予定です。直前の変更もあり得るため、最新情報は主催者の公式発信もあわせてご確認ください。'
        pairs.append((f'{name}の開催日はいつですか？', a))
    else:
        pairs.append((f'{name}の開催日はいつですか？', '開催日は現時点で未発表です。公式発表があり次第、本ページを更新します。'))

    admission = (ev.get('admission') or '').strip()
    if admission:
        if sitelib.admission_is_free(admission):
            a = '入場は無料です。'
        else:
            a = f'入場料は「{admission}」です。前売り・当日の価格差がある場合は主催者の公式案内をご確認ください。'
        pairs.append(('入場料はかかりますか？', a))

    time_str = (ev.get('time') or '').strip()
    if time_str:
        verb = 'でした' if is_past else 'です'
        pairs.append(('開催時間は何時から何時までですか？', f'開催時間は{time_str}{verb}。整理券配布や入場列は開場前に始まることがあります。'))

    venue = (ev.get('location') or ev.get('venue') or '').strip()
    if venue and not _is_vague(venue):
        pref = ev.get('prefecture') or ev.get('region') or ''
        # location に住所が入っている回は県名が本文に既にある。
        # そのまま (県) を足すと「◯◯（静岡県富士市…）(静岡)です」と括弧が二重になる。
        a = f'会場は{venue}({pref})です。' if pref and pref not in venue else f'会場は{venue}です。'
        access = (ev.get('access') or '').strip()
        if access:
            a += f'アクセス: {access}'
        pairs.append(('会場はどこですか？', a))

    return pairs

def make_event_faq(ev, ctx):
    pairs = _faq_pairs(ev, ctx)
    # 日付・会場を言い直すだけのFAQは出さない
    if len(pairs) < 3:
        return ''
    rows = []
    for q, a in pairs:
        rows.append(
            f'          <details class="faq-item">\n'
            f'            <summary class="faq-q">{html_escape(q)}</summary>\n'
            f'            <p class="faq-a">{html_escape(a)}</p>\n'
            f'          </details>'
        )
    rows_html = '\n'.join(rows)
    import json as _json
    ld = {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": q,
             "acceptedAnswer": {"@type": "Answer", "text": a}}
            for q, a in pairs
        ],
    }
    ld_str = _json.dumps(ld, ensure_ascii=False)
    return (
        f'        <div class="detail-section detail-enriched detail-faq">\n'
        f'          <h2 class="detail-section-title" data-kicker="FAQ">よくある質問</h2>\n{rows_html}\n'
        f'        </div>\n'
        f'        <script type="application/ld+json">{ld_str}</script>\n'
    )

# --- 概要セクションに足す実データ・サマリ段落 ---

def make_data_summary(ev, ctx):
    sentences = []
    d = ev.get('date') or ''
    d_end = ev.get('dateEnd') or d

    if d:
        try:
            sdt = datetime.strptime(d, '%Y-%m-%d')
            edt = datetime.strptime(d_end, '%Y-%m-%d')
            days = (edt - sdt).days + 1
            wd_s = WEEKDAYS_JA[sdt.weekday()]
            if days == 1:
                sentences.append(f'開催は{sdt.year}年{sdt.month}月{sdt.day}日({wd_s})の1日です。')
            else:
                wd_e = WEEKDAYS_JA[edt.weekday()]
                sentences.append(
                    f'会期は{sdt.year}年{sdt.month}月{sdt.day}日({wd_s})から'
                    f'{edt.month}月{edt.day}日({wd_e})までの{days}日間です。'
                )
        except ValueError:
            pass

    admission = (ev.get('admission') or '')
    # 素の '無料' in で判定すると「大人250円・未就学児無料」のような
    # 但し書きに引っかかり、有料の回が本文で無料を名乗る(2026-09-05)。
    # 判定は sitelib.admission_is_free() が単一情報源。
    if sitelib.admission_is_free(admission):
        sentences.append('入場は無料です。')

    if not sentences:
        return ''
    return '          <p class="data-summary">' + html_escape(' '.join(sentences)) + '</p>\n'

def make_site_mission_section():
    return (
        '        <div class="detail-section detail-enriched detail-mission">\n'
        '          <p class="mission-note">本ページの情報は、運営者(東京・練馬の愛好家/栽培歴8年)が主催者の公式発信を確認して編集しています。'
        '誤りのご指摘は<a href="/contact.html">お問い合わせ</a>から。'
        '<a href="/about.html">編集方針</a> / <a href="/operator.html">運営者情報</a></p>\n'
        '        </div>\n'
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
        if 'アガベ' in name and gcat == 'アガベ':
            score += 5
        if ('パキポ' in name or 'グラキリス' in name) and 'パキポ' in title:
            score += 8
        if 'アデニウム' in name and 'アデニウム' in title:
            score += 8
        if ('コーデックス' in name or '塊根' in name) and gcat == 'コーデックス':
            score += 5
        if '即売' in name and gcat == '購入':
            score += 6
        scored.append((score, path, title))
    scored.sort(reverse=True)
    # 関連度の高い2本 + slugハッシュで分散させる2本(全19記事がサイト全体に行き渡る)
    top = [x for x in scored[:2] if x[0] > 0]
    slug = ev.get('slug', '')
    offset = _slug_hash(slug) % len(GUIDE_LINKS)
    rotated = GUIDE_LINKS[offset:] + GUIDE_LINKS[:offset]
    chosen_paths = {p for _, p, _ in top}
    for p, t, _ in rotated:
        if len(top) >= 4:
            break
        if p not in chosen_paths:
            top.append((0, p, t))
            chosen_paths.add(p)

    items = []
    for _, path, title in top:
        items.append(f'            <li><a href="/guides/{path}">{html_escape(title)}</a></li>')
    items_html = '\n'.join(items)

    return (
        f'        <div class="detail-section detail-enriched">\n'
        f'          <h2 class="detail-section-title" data-kicker="GUIDE">あわせて読みたい栽培ガイド</h2>\n'
        f'          <p class="section-note">このイベントで出会える植物の管理・購入判断に役立つ、本サイト独自のガイド記事です。</p>\n'
        f'          <ul class="related-guides-list">\n{items_html}\n          </ul>\n'
        f'          <p class="related-guides-more"><a href="/guides/">栽培ガイド一覧を見る →</a></p>\n'
        f'        </div>\n'
    )

def make_enriched_content(ev, ctx):
    return (
        make_series_history(ev, ctx)
        + make_nearby_events(ev, ctx)
        + make_venue_history(ev, ctx)
        + make_event_faq(ev, ctx)
        + make_visitor_guide(ev)
        + make_related_guides(ev)
        + make_site_mission_section()
    )

def build_context(events):
    """全イベント横断の事前計算: シリーズ・会場・統計。"""
    from datetime import timezone as _tz, timedelta as _td
    today = datetime.now(_tz(_td(hours=9))).strftime('%Y-%m-%d')

    series = {}
    venues = {}
    pref_counts = {}
    cat_counts = {}
    free_n = 0
    admission_known = 0
    for e in events:
        k = normalize_series_name(e.get('name'))
        if len(k) >= 4:
            series.setdefault(k, []).append(e)
        v = (e.get('location') or '').strip()
        if v and not _is_vague(v):
            venues.setdefault(v, []).append(e)
        p = e.get('prefecture')
        if p:
            pref_counts[p] = pref_counts.get(p, 0) + 1
        c = detect_primary_category(e)
        cat_counts[c] = cat_counts.get(c, 0) + 1
        adm = (e.get('admission') or '')
        if adm:
            admission_known += 1
            if sitelib.admission_is_free(adm):
                free_n += 1

    total = len(events) or 1
    cat_pct = {c: round(100.0 * n / total) for c, n in cat_counts.items() if n >= 3}
    ranked = sorted(pref_counts.items(), key=lambda x: -x[1])
    pref_rank = {p: i + 1 for i, (p, _) in enumerate(ranked)}
    free_pct = round(100.0 * free_n / admission_known) if admission_known >= 20 else None

    return {
        'events': events,
        'today': today,
        'series': series,
        'venues': venues,
        'stats': {
            'pref_counts': pref_counts,
            'pref_rank': pref_rank,
            'cat_pct': cat_pct,
            'free_pct': free_pct,
        },
    }





# --- インラインSVGアイコン (モノクロ・16px・currentColor) ---
_ICONS = {
    'calendar': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    'pin': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>',
    'ticket': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M2 9a3 3 0 0 1 0 6v3a1 1 0 0 0 1 1h18a1 1 0 0 0 1-1v-3a3 3 0 0 1 0-6V6a1 1 0 0 0-1-1H3a1 1 0 0 0-1 1z"/><line x1="13" y1="5" x2="13" y2="19" stroke-dasharray="2 3"/></svg>',
    'clock': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    'train': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><rect x="4" y="3" width="16" height="14" rx="2"/><line x1="4" y1="11" x2="20" y2="11"/><circle cx="8.5" cy="14.5" r="0.5"/><circle cx="15.5" cy="14.5" r="0.5"/><path d="M8 19l-2 3M16 19l2 3"/></svg>',
    'link': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>',
    'weather': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><path d="M17.5 19a4.5 4.5 0 1 0 0-9h-1.8A7 7 0 1 0 4 14.9"/></svg>',
    'update': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>',
    'source': '<svg class="i" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><circle cx="12" cy="8" r="0.5"/></svg>',
}

def icon(name):
    return _ICONS.get(name, '')

def make_weather_row(ev, ctx):
    """天気行は撤去した(2026-07-30)。
    Google検索に送り出すだけで、収益も回遊も生まないうえ検索結果で競合サイトに
    出会わせる離脱動線になっていた。天気は読者が自分で見る。"""
    return ''


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

    # 全イベント横断コンテキスト(シリーズ/会場/統計)は必ず全件で構築する
    ctx = build_context(events)

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

        html = build_page(template, ev, ctx)
        output_path = os.path.join(OUTPUT_DIR, f'{slug}.html')

        if args.dry_run:
            print(f'  DRY-RUN: {slug}.html ({len(html)} bytes)')
        else:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html)
            print(f'  Generated: {slug}.html')

        generated += 1

    print(f'\nDone: {generated} generated, {skipped} skipped')

    if not args.slug and not args.dry_run:
        import json as _meta_json
        meta_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'scripts', 'events-meta.json')
        with open(meta_path, 'w', encoding='utf-8') as f:
            _meta_json.dump({'noindex': sorted(set(NOINDEX_EVENT_SLUGS))}, f, ensure_ascii=False, indent=2)
        print(f'noindex events: {len(set(NOINDEX_EVENT_SLUGS))} -> scripts/events-meta.json')

        # events.json から消えたイベントの詳細ページを掃除する。
        # 残しておくと本番に生き続け sitemap にも載り続ける(2026-07-30に発覚)。
        # 生成数が極端に少ない場合は異常終了とみなし何もしない。
        if generated >= 20:
            import glob as _glob
            live = {e.get('slug') for e in events}
            removed = []
            for fp in _glob.glob(os.path.join(OUTPUT_DIR, "*.html")):
                slug_f = os.path.basename(fp)[:-5]
                if slug_f not in live:
                    os.remove(fp)
                    removed.append(slug_f)
            if removed:
                print(f'孤児ページ削除: {len(removed)}件 — ' + ', '.join(sorted(removed)))
        else:
            print('孤児ページ掃除: 生成数が少ないためスキップ(異常終了の可能性)')


if __name__ == '__main__':
    main()
