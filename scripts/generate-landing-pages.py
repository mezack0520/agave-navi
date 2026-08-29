#!/usr/bin/env python3
"""
SEOランディングページ一括生成
- /tag/<slug>/        - タグ別アーカイブ
- /pref/<romaji>/     - 都道府県別アーカイブ
- /region/<slug>/     - 地域別アーカイブ
- /archive/YYYY-MM/   - 月別アーカイブ
- /archive/YYYY/      - 年別アーカイブ
- /this-weekend/      - 今週末のイベント
- /this-month/        - 今月のイベント
- /venue/<slug>/      - 会場別(2件以上)
"""
import os, re, json
from datetime import datetime, timedelta
from collections import defaultdict

import sitelib
from sitelib import (
    JST, DOMAIN, html_escape, pref_slug, region_slug, tag_slug, venue_slug,
    PREF_ROMAJI, REGION_ROMAJI, TAG_ROMAJI, VENUE_ROMAJI, VAGUE_VENUES, safe_slug,
    is_upcoming, is_ongoing, list_sort_key, split_ongoing,
    is_vague_venue, venue_key, venue_display, VENUE_SLUG_REDIRECTS,
    event_card_html, event_grid_html, section_heading_html, past_range_label,
    event_span, LONG_RUN_DAYS, CARDS_PER_PAGE, PAST_CARDS_INIT,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(REPO_ROOT, 'events.json')

HEAD = '''<!DOCTYPE html>
<html lang="ja">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-NKY8V1H8HY"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NKY8V1H8HY');</script>
  <meta charset="UTF-8">
  {robots_meta}
  <link rel="canonical" href="{canonical}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | アガベイベントナビ</title>
  <meta name="description" content="{description}">
  <meta name="keywords" content="{keywords}">
  <meta property="og:title" content="{title} | アガベイベントナビ">
  <meta property="og:description" content="{description}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="https://agave-navi.com/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/svg+xml" href="{root}favicon.svg">
  <link rel="icon" type="image/x-icon" href="{root}favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="{root}apple-touch-icon.png">
  <link rel="manifest" href="{root}manifest.webmanifest">
  <meta name="theme-color" content="#111">
  <link rel="alternate" type="application/rss+xml" title="アガベイベントナビ" href="{root}rss.xml">
  <link rel="stylesheet" href="{root}style.css?v=20260611a">
  <script type="application/ld+json">
  {{"@context":"https://schema.org","@type":"CollectionPage","name":"{title}","description":"{description}","url":"{canonical}","isPartOf":{{"@type":"WebSite","name":"アガベイベントナビ","url":"https://agave-navi.com/"}}}}
  </script>
{breadcrumb_jsonld}
  <script src="{root}list-ui.js?v=20260820a"></script>
</head>'''
HEAD = HEAD.replace('style.css?v=20260611a', 'style.css?v=' + sitelib.CSS_VERSION)
HEAD = HEAD.replace('list-ui.js?v=20260820a', 'list-ui.js?v=' + sitelib.JS_VERSION)  # 版数の正はsitelib

HEADER = sitelib.site_header()
FOOTER = sitelib.site_footer()

# --- ページ固有の解説文 (boilerplate化を避けるため種別ごとに手書き) ---
TAG_INTROS = {
    '即売会': '生産者・専門店が会場に集まり、その場で植物を購入できる形式です。一点物の選抜株に出会えるのが最大の魅力で、人気イベントでは開場前から整理券や行列が発生します。',
    'マルシェ': '飲食・雑貨と併催されるカジュアルな植物イベントです。専門イベントより敷居が低く、入門向けの小苗から愛好家向けの株まで価格帯が広いのが特徴です。',
    '大型': '出店者数・来場者数とも最大級のイベントです。広域から生産者が集まるため品揃えの幅が広く、複数日会期や数万人規模の来場となる回もあります。',
    '展示会': '愛好家・団体による銘品株の展示が中心のイベントです。即売が併設される場合もありますが、観賞と情報交換が主目的になります。',
    'アガベ': 'ロゼット状の葉と鋸歯(きょし)が魅力のリュウゼツラン属。チタノタ/オテロイ系を中心に近年人気が高く、専門イベントも開催されています。',
    '塊根植物': 'パキポディウムやアデニウムなど、肥大した幹・根を楽しむ植物群(コーデックス)。実生株から現地球まで流通形態が幅広いジャンルです。',
    '多肉植物': 'エケベリアやハオルチアをはじめ、水分を蓄える厚い葉・茎を持つ植物の総称です。初心者でも始めやすく、イベントでも最も裾野の広いジャンルです。',
    '珍奇植物': 'ビザールプランツとも呼ばれる、姿かたちの個性的な植物群の総称です。塊根植物・アガベ・蟻植物・食虫植物など幅広いジャンルを横断します。',
    'サボテン': 'トゲ座(刺座)を持つサボテン科の植物。多肉植物と並んで歴史の長い愛好分野で、専門業者による即売・展示の伝統があります。',
    'ブロメリア': 'パイナップル科の植物群。チランジア(エアプランツ)やネオレゲリアなどを含み、専門イベントが定期開催されています。',
    'ビカクシダ': 'コウモリラン(プラティセリウム)とも呼ばれる着生シダ。板付け・苔玉などの仕立てで人気があり、専門の即売イベントも生まれています。',
    'アロイド': 'サトイモ科(モンステラ・フィロデンドロン・アンスリウム等)の植物群。斑入り品種を中心に近年注目度が高いジャンルです。',
    '着生植物': '土に根を張らず樹木や岩に着生して育つ植物の総称。チランジア・ビカクシダ・着生ランなどが含まれます。',
}

REGION_DESCS = {
    '関東': '東京・神奈川・埼玉・千葉を中心に、全国で最も植物イベントの開催数が多いエリアです。都市型の大型即売会から神社・公園でのマルシェまで形式も多彩で、週末に複数イベントが重なることも珍しくありません。',
    '関西': '大阪市内の大型会場を中心に、京都・兵庫・奈良・和歌山の地域マルシェまで層の厚いエリアです。関東と並ぶ二大開催地域で、大型フェスの定期開催も定着しています。',
    '東海': '名古屋を中心に、愛知・岐阜・三重・静岡で定期イベントが定着しているエリアです。園芸生産の盛んな地域でもあり、生産者の直接出店が多いのが特徴です。',
    '九州': '福岡を中心に、熊本・大分・鹿児島など各県でイベントが開催されています。温暖な気候を背景に屋外マルシェ型の開催が多いエリアです。',
    '北海道': '札幌近郊を中心に、雪解け後の春〜秋に開催が集中するエリアです。本州よりイベント数は少なめですが、その分1回ごとの注目度が高い傾向があります。',
    '東北': '仙台を中心に、春から秋にかけての開催が中心のエリアです。',
    '北陸': '金沢・富山・福井などで、春と秋を中心にイベントが開催されるエリアです。',
    '中国': '広島・岡山を中心としたエリアです。関西圏からの出店者の参加も多く見られます。',
    '四国': '愛媛・香川・高知・徳島の地域密着型マルシェが中心のエリアです。',
}

def bc_jsonld(items):
    elems=[]
    for i,(n,u) in enumerate(items,1):
        e={"@type":"ListItem","position":i,"name":n}
        if u: e["item"]=u
        elems.append(e)
    return '  <script type="application/ld+json">\n  ' + json.dumps({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":elems}, ensure_ascii=False) + '\n  </script>'

def bc_html(items):
    parts=[]
    for i,(n,u) in enumerate(items):
        last = (i==len(items)-1)
        parts.append(f'<a href="{u}">{n}</a>' if (u and not last) else f'<span>{n}</span>')
    return '  <nav class="breadcrumb" aria-label="パンくずリスト">\n    ' + ' &gt; '.join(parts) + '\n  </nav>'

# イベントカードは sitelib.event_card_html が単一情報源。
# ここに独自実装(landing-card)を持っていたため、106ページで画像・ステータス
# バッジ・行きたいが出ず、status-auto.js も効かなかった(2026-08-20に統合)。
# .landing-card は /tag/ /pref/ /region/ の索引ページのリンクタイル専用に残す。

def redirect_page(dest, label, root='../../'):
    """旧URL用の中継頁。noindex + canonical で宛先に寄せる。

    JSを切っている閲覧者とクローラのために本文にもリンクを置く。
    """
    esc = html_escape(label)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="robots" content="noindex,follow">
  <meta http-equiv="refresh" content="0;url={dest}">
  <link rel="canonical" href="{DOMAIN}{dest}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>移転しました | アガベイベントナビ</title>
  <link rel="stylesheet" href="{root}style.css?v={sitelib.CSS_VERSION}">
</head>
<body>
{HEADER}
  <main>
  <section class="landing-hero">
    <h1>ページは移転しました</h1>
    <p class="lead">このURLは <a href="{dest}">{esc}</a> に移動しました。
    自動で転送されない場合はリンクから移動してください。</p>
  </section>
  </main>
{FOOTER}
</body>
</html>
"""


def load_more_wrap(wrap_id, fn, show):
    style = '' if show else ' style="display:none"'
    return (f'<div class="load-more-wrap" id="{wrap_id}"{style}>'
            f'<button class="load-more-btn" onclick="{fn}()"><span>もっと見る</span>'
            f'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
            f'stroke-linecap="round" stroke-linejoin="round">'
            f'<polyline points="6 9 12 15 18 9"></polyline></svg></button></div>')


def event_sections(evs, today_str):
    """開催中 / これから開催 / 終了 の3節。空の節は見出しごと出さない。

    idは index.html と同じ。list-ui.js の「もっと見る」と
    status-auto.js のステータス付与・振り分けがそのまま効く。
    終了は打ち切らない。ランディングは地域の開催実績も情報なので、
    トップの PAST_KEEP_DAYS(過去14日)は適用しない。
    その意思は past グリッドに data-past-keep-days を付けないことで示す。
    """
    up = [e for e in evs if is_upcoming(e, today_str)]
    past = [e for e in evs if not is_upcoming(e, today_str)]
    ongoing, coming = split_ongoing(up, today_str)
    past.sort(key=lambda e: (event_span(e)[1] or '', e.get('name') or ''), reverse=True)
    parts = [
        section_heading_html('開催中' if ongoing else '', f'会期{LONG_RUN_DAYS}日以上',
                             'h2', 'ongoingHeading'),
        event_grid_html(ongoing, 'ongoingEventsGrid', today=today_str),
        section_heading_html('これから開催' if coming else '', f'{len(coming)}件',
                             'h2', 'upcomingHeading'),
        event_grid_html(coming, 'eventsGrid', eager_first=True, today=today_str),
        load_more_wrap('loadMoreWrap', 'loadMoreEvents', len(coming) > CARDS_PER_PAGE),
        section_heading_html('終了したイベント' if past else '', past_range_label(past),
                             'h3', 'pastEventsHeading'),
        event_grid_html(past, 'pastEventsGrid', extra_class='past-events',
                        today=today_str, compact=True),
        load_more_wrap('pastLoadMoreWrap', 'loadMorePastEvents', len(past) > PAST_CARDS_INIT),
    ]
    return '\n  '.join(parts)

NOINDEX_PATHS = []  # sitemap除外用(リポジトリ相対パス)。main()終了時にmanifest出力。
CANONICALIZED_PATHS = []  # canonicalを他URLに向けた頁。noindexではないがsitemapには載せない。

def render(title, desc, kw, canon, bc, h1, lead, evs, root='../../',
           noindex=False, intro_html='', fallback_evs=None, rel_path=None,
           canonical_of=None, feed_href=None):
    # canonical_of: 別URLと内容が完全に重複する頁で、正規URLをそちらに寄せる。
    # noindexにはしない(利用者には見える・リンクも辿らせる)が、
    # 自分自身を指さないcanonicalとsitemap掲載は矛盾するのでsitemapからは外す。
    if canonical_of:
        canon = canonical_of
        if rel_path:
            CANONICALIZED_PATHS.append(rel_path)
    robots_meta = '<meta name="robots" content="noindex,follow">' if noindex else '<meta name="robots" content="index,follow">'
    if noindex and rel_path:
        NOINDEX_PATHS.append(rel_path)
    head = HEAD.format(title=title, description=desc, keywords=kw, canonical=canon,
                       root=root, breadcrumb_jsonld=bc_jsonld(bc), robots_meta=robots_meta)
    if feed_href:
        # generate-rss.py が吐くタグ別・地域別フィードへの導線。
        # 貼らないと、生成しているだけでどこからも辿れないファイルになる
        # (2026-08-20まで23本が未参照だった)。
        head = head.replace(
            '<link rel="stylesheet"',
            f'<link rel="alternate" type="application/rss+xml" '
            f'title="{html_escape(h1)}" href="{feed_href}">\n  <link rel="stylesheet"', 1)
    bch = bc_html(bc)
    today_str = datetime.now(JST).strftime('%Y-%m-%d')
    if evs:
        # 件数は各節の見出しに出るので「該当イベント: N件」の行は持たない。
        # h1・lead・intro・stats で同じことを4回言っていた(2026-08-20)。
        grid = '  ' + event_sections(evs, today_str)
    else:
        fb = ''
        if fallback_evs:
            fb = ('\n  <h2 class="section-heading section-heading--sub">'
                  '全国の直近開催予定</h2>\n  '
                  + event_grid_html(fallback_evs, 'eventsGrid',
                                    eager_first=True, today=today_str))
        grid = ('  <div class="landing-empty">現在このページに該当するイベント情報はありません。'
                '<a href="/">ホーム</a>から最新の一覧を確認できます。</div>' + fb)
    intro = f'\n  <section class="landing-intro">{intro_html}</section>' if intro_html else ''
    aff, aff_js = aff_block(root, noindex=noindex)
    body = (f'<body>\n{HEADER}\n{bch}\n  <main>\n  <section class="landing-hero"><h1>{h1}</h1>'
            f'<p class="lead">{lead}</p></section>{intro}\n{grid}{aff}\n  </main>\n{FOOTER}\n'
            f'{aff_js}  <script src="{root}status-auto.js?v={sitelib.JS_VERSION}"></script>\n'
            f'</body>\n</html>\n')
    return head + '\n' + body

def aff_block(root, noindex=False, tags=''):
    """アフィリエイト枠。noindexの薄いページには出さない(薄頁×広告を避ける)。"""
    if noindex:
        return '', ''
    attr = f' data-tags="{tags}"' if tags else ''
    return (f'\n  <section class="affiliate-section"{attr} style="max-width:960px;margin:1.5rem auto 0;"></section>',
            f'  <script src="{root}affiliate.js?v={sitelib.JS_VERSION}"></script>\n')

GENERATED_PAGES = set()

def write_page(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,'w',encoding='utf-8') as f: f.write(html)
    GENERATED_PAGES.add(os.path.abspath(path))

# このスクリプトが所有するディレクトリ。ここ配下の index.html は毎回生成される前提。
OWNED_DIRS = ['tag', 'pref', 'region', 'archive', 'venue', 'category',
              'this-weekend', 'this-month', 'new']


def cleanup_orphans():
    """今回生成されなかった配下ページを削除する。
    対象が減った(該当イベントが0件になった等)ときに空ページが残り、
    sitemapに載り続けるのを防ぐ。安全弁として、生成数が極端に少ない場合は何もしない。"""
    if len(GENERATED_PAGES) < 20:
        print('  cleanup: 生成数が少ないためスキップ(異常終了の可能性)')
        return []
    removed = []
    for d in OWNED_DIRS:
        root = os.path.join(REPO_ROOT, d)
        if not os.path.isdir(root):
            continue
        for cur, _dirs, files in os.walk(root):
            for fn in files:
                if not fn.endswith('.html'):
                    continue
                fp = os.path.abspath(os.path.join(cur, fn))
                if fp in GENERATED_PAGES:
                    continue
                os.remove(fp)
                removed.append(os.path.relpath(fp, REPO_ROOT))
        # 空になったディレクトリを畳む
        for cur, dirs, files in os.walk(root, topdown=False):
            if cur != root and not os.listdir(cur):
                os.rmdir(cur)
    return sorted(removed)


def listed(evs, today_str):
    """一覧に出す順に並べる。開催中の長期開催を先頭、以降は sitelib の並び順。"""
    ongoing, rest = split_ongoing(evs, today_str)
    return ongoing + rest


def upcoming_then_past(evs):
    """開催予定(開催中を含む) → 終了 の順。判定と並びは sitelib が単一情報源。

    date >= today で切っていたため、開催中の長期イベントが終了側に落ちていた
    (2026-08-20)。開催予定/終了の別は必ず dateEnd で判定する。
    """
    today=datetime.now(JST).strftime('%Y-%m-%d')
    ongoing, rest = split_ongoing([e for e in evs if is_upcoming(e, today)], today)
    past=sorted([e for e in evs if not is_upcoming(e, today)],
                key=lambda e:e.get('date',''), reverse=True)
    return ongoing + rest + past

def index_page(out_path, title, desc, kw, canon, h1, lead, items, root='../'):
    """items: list of (name, url, count)"""
    cards = ''.join(f'<article class="landing-card"><a href="{u}"><h2 class="lc-name">{n}</h2><div class="lc-meta">{c}件</div></a></article>' for n,u,c in items)  # 索引のリンクタイル(イベントカードではない)
    grid = f'  <div class="landing-grid">\n{cards}\n  </div>'
    bc = [('ホーム', DOMAIN+'/'), (title.replace('一覧','').replace('別',''), None)]
    head = HEAD.format(title=title, description=desc, keywords=kw, canonical=canon, root=root, breadcrumb_jsonld=bc_jsonld(bc), robots_meta='<meta name="robots" content="index,follow">')
    bch = bc_html(bc)
    aff, aff_js = aff_block(root)
    body = (f'<body>\n{HEADER}\n{bch}\n  <main>\n  <section class="landing-hero"><h1>{h1}</h1>'
            f'<p class="lead">{lead}</p></section>\n{grid}{aff}\n  </main>\n{FOOTER}\n'
            f'{aff_js}</body>\n</html>\n')
    write_page(out_path, head + '\n' + body)

THIN_THRESHOLD = 3  # 掲載イベントがこの件数未満のタグ/都道府県ページはnoindex

def dyn_facts(evs, today_str):
    """イベント群から事実ベースの動的な紹介文を作る。"""
    ongoing, rest = split_ongoing([e for e in evs if is_upcoming(e, today_str)], today_str)
    up = ongoing + rest
    parts = []
    if ongoing:
        o = ongoing[0]
        parts.append(f"現在開催中は「{o.get('name','')}」({o.get('dateDisplay') or o.get('date','')})です。")
    nxt = next((e for e in rest if not is_ongoing(e, today_str)), None)
    if nxt:
        dd = nxt.get('dateDisplay') or nxt.get('date','')
        parts.append(f"直近の開催予定は「{nxt.get('name','')}」({dd})です。")
    if up:
        parts.append(f"今後の開催予定は{len(up)}件掲載しています。")
    return ' '.join(parts)

def main():
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    today = datetime.now(JST)
    today_str = today.strftime('%Y-%m-%d')
    _up_ongoing, _up_rest = split_ongoing([e for e in events if is_upcoming(e, today_str)], today_str)
    upcoming_all = _up_ongoing + _up_rest
    fallback5 = upcoming_all[:5]
    counters = defaultdict(int)

    # Tag pages
    by_tag = defaultdict(list)
    for e in events:
        for t in e.get('tags', []): by_tag[t].append(e)
    for t, evs in by_tag.items():
        sl = tag_slug(t)
        intro = TAG_INTROS.get(t, '')
        facts = dyn_facts(evs, today_str)
        intro_html = f'<p>{intro}</p>' if intro else ''
        if facts:
            intro_html += f'<p>{facts}</p>'
        write_page(os.path.join(REPO_ROOT, 'tag', sl, 'index.html'),
            render(f'{t}のイベント一覧', f'{t}に該当するアガベ・多肉植物・塊根植物のイベント情報。{len(evs)}件掲載。',
                   f'{t},アガベ,多肉植物,イベント,即売会', f'{DOMAIN}/tag/{sl}/',
                   [('ホーム',DOMAIN+'/'),('タグ別','/tag/'),(t,None)],
                   f'タグ: {t}', f'「{t}」のイベント一覧。直近の開催から過去の実績まで。', upcoming_then_past(evs), '../../',
                   noindex=(len(evs) < THIN_THRESHOLD), intro_html=intro_html,
                   fallback_evs=fallback5, rel_path=f'tag/{sl}/index.html',
                   feed_href=f'/feeds/tag-{sl}.xml'))
        counters['tag']+=1

    # Pref pages
    by_pref = defaultdict(list)
    for e in events:
        if e.get('prefecture'): by_pref[e['prefecture']].append(e)
    for p, evs in by_pref.items():
        sl = pref_slug(p)
        region = next((e.get('region') for e in evs if e.get('region')), None)
        facts = dyn_facts(evs, today_str)
        # 前置きは lead と intro の2つに畳む。h1・lead・intro・stats で
        # 同じことを言い直して画面の1/4を使っていた(2026-08-20)。
        intro_html = f'<p>{facts}</p>' if facts else ''
        if region and region in REGION_ROMAJI:
            intro_html += f'<p>近隣で開催されるイベントは<a href="/region/{REGION_ROMAJI[region]}/">{region}地方のイベント一覧</a>からも探せます。</p>'
        write_page(os.path.join(REPO_ROOT, 'pref', sl, 'index.html'),
            render(f'{p}のアガベ・植物イベント', f'{p}で開催されるアガベ・多肉植物・塊根植物のイベント情報。{len(evs)}件掲載。',
                   f'{p},アガベ,多肉植物,イベント,即売会', f'{DOMAIN}/pref/{sl}/',
                   [('ホーム',DOMAIN+'/'),('都道府県別','/pref/'),(p,None)],
                   f'{p}のイベント',
                   f'{p}で開催されるアガベ・塊根植物・多肉植物・ビザールプランツのイベントをまとめています。掲載{len(evs)}件。',
                   upcoming_then_past(evs), '../../',
                   noindex=(len(evs) < THIN_THRESHOLD), intro_html=intro_html,
                   fallback_evs=fallback5, rel_path=f'pref/{sl}/index.html'))
        counters['pref']+=1

    # Region pages
    by_region = defaultdict(list)
    for e in events:
        if e.get('region'): by_region[e['region']].append(e)
    for r, evs in by_region.items():
        sl = region_slug(r)
        desc_txt = REGION_DESCS.get(r, '')
        facts = dyn_facts(evs, today_str)
        prefs_in = sorted({e.get('prefecture') for e in evs if e.get('prefecture')})
        intro_html = f'<p>{desc_txt}</p>' if desc_txt else ''
        if facts:
            intro_html += f'<p>{facts}</p>'
        if prefs_in:
            links = '、'.join(f'<a href="/pref/{pref_slug(pp)}/">{pp}</a>' for pp in prefs_in)
            intro_html += f'<p>都道府県別: {links}</p>'
        # 掲載イベントが1県に閉じている地域は /pref/<県>/ と掲載内容もtitleも完全に一致する。
        # 北海道は PREF_TO_REGION 上そもそも1県=1地方なので構造的に必ずこうなる。
        # 両方をindexさせると同一内容の2URLが競合するため、正規URLを県頁に寄せる。
        canonical_of = None
        if len(prefs_in) == 1:
            canonical_of = f'{DOMAIN}/pref/{pref_slug(prefs_in[0])}/'
        write_page(os.path.join(REPO_ROOT, 'region', sl, 'index.html'),
            render(f'{r}のアガベ・植物イベント', f'{r}地方で開催されるアガベ・多肉植物のイベント情報。{len(evs)}件掲載。',
                   f'{r},アガベ,イベント', f'{DOMAIN}/region/{sl}/',
                   [('ホーム',DOMAIN+'/'),('地域別','/region/'),(r,None)],
                   f'{r}地方のイベント', f'{r}地方で開催される植物イベント一覧。', upcoming_then_past(evs), '../../',
                   noindex=(len(evs) < THIN_THRESHOLD), intro_html=intro_html,
                   fallback_evs=fallback5, rel_path=f'region/{sl}/index.html',
                   canonical_of=canonical_of, feed_href=f'/feeds/region-{sl}.xml'))
        counters['region']+=1

    # Archive YM
    by_ym = defaultdict(list)
    for e in events:
        d = e.get('date','')
        if len(d)>=7: by_ym[d[:7]].append(e)
    cur_ym_str = today.strftime('%Y-%m')
    for ym, evs in by_ym.items():
        y, m = ym.split('-'); m_int=int(m)
        is_future = ym > cur_ym_str
        label = '開催予定のイベント' if is_future else '開催されたイベント'
        write_page(os.path.join(REPO_ROOT, 'archive', ym, 'index.html'),
            render(f'{y}年{m_int}月のアガベ・植物イベント', f'{y}年{m_int}月の植物イベント{len(evs)}件。',
                   f'{y}年{m_int}月,アガベ,イベント', f'{DOMAIN}/archive/{ym}/',
                   [('ホーム',DOMAIN+'/'),('アーカイブ','/archive/'),(f'{y}年{m_int}月',None)],
                   f'{y}年{m_int}月のイベント', f'{y}年{m_int}月に{label}の一覧です。',
                   sorted(evs, key=lambda e:e.get('date','')), '../../',  # start-date-ok: 月別アーカイブは開始日の時系列
                   noindex=(len(evs) < 2), rel_path=f'archive/{ym}/index.html'))
        counters['archive_ym']+=1

    # Archive Y
    by_y = defaultdict(list)
    for e in events:
        d = e.get('date','')
        if len(d)>=4: by_y[d[:4]].append(e)
    for y, evs in by_y.items():
        write_page(os.path.join(REPO_ROOT, 'archive', y, 'index.html'),
            render(f'{y}年のアガベ・植物イベントまとめ', f'{y}年開催の全{len(evs)}件のイベント情報。',
                   f'{y}年,アガベ,イベント,まとめ', f'{DOMAIN}/archive/{y}/',
                   [('ホーム',DOMAIN+'/'),('アーカイブ','/archive/'),(f'{y}年',None)],
                   f'{y}年のイベントまとめ', f'{y}年に開催された全イベント。',
                   sorted(evs, key=lambda e:e.get('date','')), '../../'))  # start-date-ok: 年別アーカイブは開始日の時系列
        counters['archive_y']+=1

    # this-weekend
    wd = today.weekday()
    if wd == 5: sat = today
    elif wd == 6: sat = today - timedelta(days=1)
    else: sat = today + timedelta(days=(5 - wd))
    sun = sat + timedelta(days=1)
    sat_d = sat.strftime('%Y-%m-%d'); sun_d = sun.strftime('%Y-%m-%d')
    we = []
    for e in events:
        d=e.get('date',''); de=e.get('dateEnd') or d
        if d and de and d <= sun_d and de >= sat_d: we.append(e)
    label = f'{sat.month}月{sat.day}日(土)・{sun.month}月{sun.day}日(日)'
    write_page(os.path.join(REPO_ROOT, 'this-weekend', 'index.html'),
        render('今週末のアガベ・植物イベント', f'今週末({label})開催のイベント情報。',
               '今週末,アガベ,イベント', f'{DOMAIN}/this-weekend/',
               [('ホーム',DOMAIN+'/'),('今週末',None)],
               '今週末のイベント', f'今週末({label})に開催されるイベント一覧。',
               listed(we, today_str), '../',
               noindex=(len(we) == 0), fallback_evs=fallback5, rel_path='this-weekend/index.html'))
    counters['this_weekend']+=1

    # this-month
    cur_ym = today.strftime('%Y-%m')
    # 開始日ではなく「会期が今月に掛かるか」で採る。
    # 先月に始まって今月まで続く展示(会期39〜49日の回が実在する)が
    # startswith(cur_ym) だと落ち、今行ける催しが今月の一覧から消える。
    # status(auto-status-jst.py) と this-weekend は既に dateEnd を見ており、
    # ここだけ開始日基準で「今」の定義が3通りに割れていた(2026-08-18に検出)。
    me = [e for e in events
          if e.get('date','')[:7] <= cur_ym <= (e.get('dateEnd') or e.get('date',''))[:7]
          and e.get('date','')]
    # titleは常設URL向けに「今月の」で固定する。
    # 「{年}年{月}月のアガベ・植物イベント」にすると /archive/{ym}/ と毎月必ず
    # 同titleになり、同一内容のindex対象URLが2つ並ぶ(2026-08-18に検出)。
    # アーカイブ側はその月の恒久URL、こちらは毎月中身が入れ替わる常設URLで役割が違う。
    write_page(os.path.join(REPO_ROOT, 'this-month', 'index.html'),
        render('今月のアガベ・植物イベント', f'今月({today.year}年{today.month}月)開催の全{len(me)}件。',
               f'今月,{today.year}年{today.month}月,アガベ,イベント', f'{DOMAIN}/this-month/',
               [('ホーム',DOMAIN+'/'),(f'{today.year}年{today.month}月',None)],
               f'今月のイベント({today.year}年{today.month}月)', '今月開催されるイベント一覧。',
               listed(me, today_str), '../',
               noindex=(len(me) == 0), fallback_evs=fallback5, rel_path='this-month/index.html'))
    counters['this_month']+=1

    # Venue (2件以上のみ)
    # 束ねるキーは venue_key()。生の location で束ねると、住所の括弧書きの
    # 有無や空白の入れ方だけで同じ会場が別ページに割れる。
    # 未定判定は is_vague_venue() を使う(VAGUE_VENUES への完全一致だけだと
    # 「金沢（会場未確定）」のような値を会場名として扱ってしまう)。
    by_venue = defaultdict(list)
    venue_label = {}
    for e in events:
        raw = (e.get('location') or '').strip()
        if not raw or is_vague_venue(raw):
            continue
        k = venue_key(raw)
        by_venue[k].append(e)
        disp = venue_display(raw)
        if k not in venue_label or len(disp) < len(venue_label[k]):
            venue_label[k] = disp
    for k, evs in by_venue.items():
        if len(evs) < 2: continue
        v = venue_label[k]
        sl = venue_slug(k)
        pref_v = next((e.get('prefecture') for e in evs if e.get('prefecture')), '')
        facts = dyn_facts(evs, today_str)
        intro_html = f'<p>{v}({pref_v})で開催される植物イベントの開催実績・予定をまとめています。同じ会場の過去回の様子は、規模感やアクセスの参考になります。</p>'
        if facts:
            intro_html += f'<p>{facts}</p>'
        write_page(os.path.join(REPO_ROOT, 'venue', sl, 'index.html'),
            render(f'{v}でのアガベ・植物イベント', f'{v}で開催されるイベント情報。{len(evs)}件。',
                   f'{v},アガベ,イベント', f'{DOMAIN}/venue/{sl}/',
                   [('ホーム',DOMAIN+'/'),('会場別','/venue/'),(v,None)],
                   v, f'{v}で過去/今後に開催されるイベント一覧。', upcoming_then_past(evs), '../../',
                   intro_html=intro_html, rel_path=f'venue/{sl}/index.html'))
        counters['venue']+=1

    # 旧URLからの中継頁。GitHub Pages はサーバ側リダイレクトを持てないので
    # meta refresh + canonical + noindex の頁を置く。宛先は sitelib の
    # VENUE_SLUG_REDIRECTS が単一情報源で、宛先スラッグが将来変わっても追随する。
    # 現役のスラッグと同名になる旧slugは飛ばす(自分自身への転送を防ぐ)。
    live_venue_slugs = {venue_slug(k) for k, evs in by_venue.items() if len(evs) >= 2}
    for old_slug, dest_key in VENUE_SLUG_REDIRECTS.items():
        if old_slug in live_venue_slugs:
            continue
        dest = f'/venue/{venue_slug(dest_key)}/' if dest_key else '/venue/'
        label = venue_label.get(dest_key) or (dest_key or '会場別イベント一覧')
        rel = f'venue/{old_slug}/index.html'
        write_page(os.path.join(REPO_ROOT, 'venue', old_slug, 'index.html'),
                   redirect_page(dest, label, root='../../'))
        NOINDEX_PATHS.append(rel)
        counters['venue_redirect'] += 1

    # カテゴリページ /category/*.html (旧・手作り静的ページを日次生成に置換。URL維持)
    CATEGORY_PAGES = [
        ('sokubai.html', '即売会', '即売会イベント一覧'),
        ('marche.html', 'マルシェ', 'マルシェイベント一覧'),
        ('exhibition.html', '展示会', '展示会イベント一覧'),
        ('large.html', '大型', '大型イベント一覧'),
    ]
    for fname, tag_name, page_title in CATEGORY_PAGES:
        evs = by_tag.get(tag_name, [])
        intro = TAG_INTROS.get(tag_name, '')
        facts = dyn_facts(evs, today_str)
        intro_html = (f'<p>{intro}</p>' if intro else '') + (f'<p>{facts}</p>' if facts else '')
        write_page(os.path.join(REPO_ROOT, 'category', fname),
            render(page_title, f'{tag_name}形式のアガベ・多肉植物・塊根植物イベント一覧。{len(evs)}件掲載。',
                   f'{tag_name},アガベ,多肉植物,イベント', f'{DOMAIN}/category/{fname}',
                   [('ホーム',DOMAIN+'/'),('カテゴリ',None),(tag_name,None)],
                   page_title, f'{tag_name}形式のイベント一覧。開催予定から過去実績まで。', upcoming_then_past(evs), '../',
                   noindex=(len(evs) < THIN_THRESHOLD), intro_html=intro_html,
                   fallback_evs=fallback5, rel_path=f'category/{fname}'))
        counters['category'] += 1

    # 新着イベントページ /new/
    added = [e for e in events if e.get('addedDate')]
    added.sort(key=lambda e: (e.get('addedDate',''), e.get('slug','')), reverse=True)
    recent = added[:30]
    # カードは sitelib.event_card_html。ここにも独自実装があり、
    # NEWバッジと(終了)注記を手で組んでいた。どちらも status-auto.js が
    # data-added-date / data-date-end から出すので二重だった(2026-08-20)。
    # 並びは掲載日順なので3節に分けず1グリッド。
    n_cards = [event_card_html(
        e, today=today_str,
        extra_meta=f'<span class="event-added">掲載: {(e.get("addedDate") or "").replace("-", ".")}</span>')
        for e in recent]
    n_grid = ('  <div class="events-grid" id="eventsGrid">' + ''.join(n_cards) + '</div>\n  '
              + load_more_wrap('loadMoreWrap', 'loadMoreEvents', len(recent) > CARDS_PER_PAGE))
    n_bc = [('ホーム', DOMAIN+'/'), ('新着', None)]
    n_head = HEAD.format(
        title='新着掲載イベント', description='アガベ・塊根植物・多肉植物イベントの新着掲載情報。当サイトに最近追加されたイベントを掲載日順に一覧できます。',
        keywords='新着,植物イベント,アガベ,即売会', canonical=f'{DOMAIN}/new/', root='../',
        breadcrumb_jsonld=bc_jsonld(n_bc), robots_meta='<meta name="robots" content="index,follow">')
    n_style = ''   # スタイルは style.css(.event-added)。インライン<style>は持たない
    n_intro = ('<p>当サイトのデータベースに最近追加されたイベント30件を、掲載日の新しい順に並べています。'
               '毎日の自動収集と手動確認で随時追加しているため、定期的にチェックすると新しいイベントをいち早く見つけられます。'
               '開催日順に探す場合は<a href="/">イベント一覧</a>、購読型で受け取りたい場合は<a href="/calendar.html">カレンダー(iCal対応)</a>や<a href="/rss.xml">RSS</a>もご利用ください。</p>')
    n_body = (f'<body>\n{HEADER}\n{bc_html(n_bc)}\n  <main>\n'
              f'  <section class="landing-hero"><h1>新着掲載イベント</h1>'
              f'<p class="lead">最近サイトに追加されたイベント{len(recent)}件を掲載日の新しい順に並べています。</p></section>'
              f'\n  <section class="landing-intro">{n_intro}</section>'
              f'\n{n_grid}{aff_block("../")[0]}\n  </main>\n{FOOTER}\n'
              f'{aff_block("../")[1]}'
              f'  <script src="../status-auto.js?v={sitelib.JS_VERSION}"></script>\n'
              f'</body>\n</html>\n')
    write_page(os.path.join(REPO_ROOT, 'new', 'index.html'), n_head + n_style + '\n' + n_body)
    counters['new'] += 1

    # Index pages
    index_page(os.path.join(REPO_ROOT,'tag','index.html'),
        'タグ別イベント一覧','カテゴリ別にイベントを絞り込めます。','タグ別,アガベ,イベント',
        f'{DOMAIN}/tag/','タグ別イベント一覧','タグで絞り込んでイベントを探せます。',
        [(t,f'/tag/{tag_slug(t)}/',len(by_tag[t])) for t in sorted(by_tag,key=lambda t:-len(by_tag[t]))], '../')
    counters['index']+=1

    index_page(os.path.join(REPO_ROOT,'pref','index.html'),
        '都道府県別イベント一覧','お住まいの地域から探せます。','都道府県別,アガベ,イベント',
        f'{DOMAIN}/pref/','都道府県別イベント一覧','お住まいの地域から探せます。',
        [(p,f'/pref/{pref_slug(p)}/',len(by_pref[p])) for p in sorted(by_pref,key=lambda p:-len(by_pref[p]))], '../')
    counters['index']+=1

    index_page(os.path.join(REPO_ROOT,'region','index.html'),
        '地域別イベント一覧','8地方からイベントを探せます。','地域別,関東,関西,アガベ',
        f'{DOMAIN}/region/','地域別イベント一覧','8地方からイベントを探せます。',
        [(r,f'/region/{region_slug(r)}/',len(by_region[r])) for r in sorted(by_region,key=lambda r:-len(by_region[r]))], '../')
    counters['index']+=1

    # Archive index (years + months)
    items = []
    for y in sorted(by_y, reverse=True):
        items.append((f'{y}年', f'/archive/{y}/', len(by_y[y])))
    for ym in sorted(by_ym, reverse=True):
        y,m=ym.split('-')
        items.append((f'{y}年{int(m)}月', f'/archive/{ym}/', len(by_ym[ym])))
    index_page(os.path.join(REPO_ROOT,'archive','index.html'),
        'イベントアーカイブ','年別・月別に過去イベントを参照できます。','アーカイブ,過去イベント',
        f'{DOMAIN}/archive/','イベントアーカイブ','年別・月別に過去イベントを参照できます。',
        items, '../')
    counters['index']+=1

    # Venue index
    vi = sorted([(venue_label[k],f'/venue/{venue_slug(k)}/',len(by_venue[k])) for k in by_venue if len(by_venue[k])>=2], key=lambda x:-x[2])
    index_page(os.path.join(REPO_ROOT,'venue','index.html'),
        '会場別イベント一覧','複数開催実績のある会場のみ。','会場別,アガベ,イベント',
        f'{DOMAIN}/venue/','会場別イベント一覧','複数回開催実績のある会場のみ掲載。',
        vi, '../')
    counters['index']+=1

    # sitemap 除外用 manifest
    with open(os.path.join(REPO_ROOT, 'scripts', 'landing-meta.json'), 'w', encoding='utf-8') as f:
        json.dump({'noindex': sorted(NOINDEX_PATHS),
                   'canonicalized': sorted(CANONICALIZED_PATHS)}, f, ensure_ascii=False, indent=1)

    removed = cleanup_orphans()

    print('=== ランディングページ生成完了 ===')
    print(f'  noindex: {len(NOINDEX_PATHS)} pages')
    for k,v in sorted(counters.items()):
        print(f'  {k}: {v} pages')
    if removed:
        print(f'  孤児ページ削除: {len(removed)}件 — ' + ', '.join(removed))

if __name__ == '__main__':
    main()
