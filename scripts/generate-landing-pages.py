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
import os, re, json, hashlib, unicodedata
from datetime import datetime, timedelta, timezone
from collections import defaultdict

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(REPO_ROOT, 'events.json')
DOMAIN = 'https://agave-navi.com'
JST = timezone(timedelta(hours=9))

PREF_ROMAJI = {
    '北海道':'hokkaido','青森':'aomori','岩手':'iwate','宮城':'miyagi','秋田':'akita',
    '山形':'yamagata','福島':'fukushima','茨城':'ibaraki','栃木':'tochigi','群馬':'gunma',
    '埼玉':'saitama','千葉':'chiba','東京':'tokyo','神奈川':'kanagawa',
    '新潟':'niigata','富山':'toyama','石川':'ishikawa','福井':'fukui',
    '山梨':'yamanashi','長野':'nagano','岐阜':'gifu','静岡':'shizuoka','愛知':'aichi','三重':'mie',
    '滋賀':'shiga','京都':'kyoto','大阪':'osaka','兵庫':'hyogo','奈良':'nara','和歌山':'wakayama',
    '鳥取':'tottori','島根':'shimane','岡山':'okayama','広島':'hiroshima','山口':'yamaguchi',
    '徳島':'tokushima','香川':'kagawa','愛媛':'ehime','高知':'kochi',
    '福岡':'fukuoka','佐賀':'saga','長崎':'nagasaki','熊本':'kumamoto',
    '大分':'oita','宮崎':'miyazaki','鹿児島':'kagoshima','沖縄':'okinawa',
}
REGION_ROMAJI = {'北海道':'hokkaido','東北':'tohoku','関東':'kanto','北陸':'hokuriku',
                 '東海':'tokai','関西':'kansai','中国':'chugoku','四国':'shikoku','九州':'kyushu'}
TAG_ROMAJI = {'即売会':'sokubaikai','マルシェ':'marche','大型':'big','展示会':'tenjikai',
              'ブロメリア':'bromelia','珍奇植物':'chinki','多肉':'tanniku',
              'コーデックス':'caudex','アガベ':'agave',
              '塊根植物':'kaikon','多肉植物':'succulent','サボテン':'cactus',
              'ビカクシダ':'platycerium','アロイド':'aroid','着生植物':'epiphyte'}
VENUE_ROMAJI = {'五反田TOCビル 13階':'gotanda-toc','サンシャインシティ':'sunshine-city',
                '久屋大通庭園フラリエ':'flarie','研究学園駅前公園（つくば市）':'kenkyu-gakuen-park',
                '千住本氷川神社':'senju-hikawa-jinja'}
# 「会場」として意味をなさない曖昧値はvenueページを作らない
VAGUE_VENUES = {'東京','東京都内','都内','大阪','名古屋','会場未定','未定'}

def safe_slug(s, kind='gen'):
    if not s: return ''
    nfkd = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', nfkd).strip('-')[:50]
    if slug: return slug
    h = hashlib.md5(s.encode('utf-8')).hexdigest()[:8]
    return f'{kind}-{h}'

def pref_slug(p): return PREF_ROMAJI.get(p) or safe_slug(p, 'pref')
def region_slug(r): return REGION_ROMAJI.get(r) or safe_slug(r, 'region')
def tag_slug(t): return TAG_ROMAJI.get(t) or safe_slug(t, 'tag')
def venue_slug(v): return VENUE_ROMAJI.get(v) or safe_slug(v, 'v')

HEAD = '''<!DOCTYPE html>
<html lang="ja">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-NKY8V1H8HY"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NKY8V1H8HY');</script>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-0790348660030345" crossorigin="anonymous"></script>
  <meta charset="UTF-8">
  <meta name="google-adsense-account" content="ca-pub-0790348660030345">
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
  <style>
    .landing-hero{{max-width:1200px;margin:1.2rem auto .6rem;padding:0 1rem}}
    .landing-hero h1{{font-size:1.8rem;margin:.2rem 0;color:#111}}
    .landing-hero p.lead{{color:#555;margin:.4rem 0 0}}
    .landing-stats{{font-size:.9rem;color:#666;margin:.4rem 0}}
    .landing-grid{{max-width:1200px;margin:1rem auto;padding:0 1rem;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}}
    .landing-card{{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden;transition:transform .2s,box-shadow .2s}}
    .landing-card:hover{{transform:translateY(-2px);box-shadow:0 6px 16px rgba(0,0,0,.12)}}
    .landing-card a{{display:block;color:inherit;text-decoration:none;padding:1rem}}
    .landing-card .lc-date{{font-weight:700;color:#111;font-size:.9rem}}
    .landing-card .lc-name{{font-size:1.05rem;margin:.4rem 0 .3rem;line-height:1.35}}
    .landing-card .lc-meta{{font-size:.85rem;color:#666}}
    .landing-empty{{max-width:1200px;margin:2rem auto;padding:2rem 1rem;text-align:center;color:#666;background:#fff;border-radius:12px}}
    .landing-intro{{max-width:1200px;margin:.4rem auto 0;padding:0 1rem;color:#444;font-size:.95rem;line-height:1.85}}
    .landing-intro p{{margin:.5rem 0}}
    .landing-intro a{{color:#111}}
  </style>
</head>'''

HEADER = '''  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo"><span class="logo-en">AGAVE EVENT NAVI</span><span class="logo-jp">アガベイベントナビ</span></a>
      <div class="header-actions">
        <a href="/ikitai.html" class="ikitai-blob-btn"><span class="blob-bg"></span>
          <svg class="ikitai-heart" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
          <span class="ikitai-label">行きたい</span></a>
      </div>
    </div>
  </header>'''

FOOTER = '''  <footer class="footer">
    <div class="footer-inner">
      <nav class="footer-nav"><a href="/">イベント一覧</a><a href="/calendar.html">カレンダー</a><a href="/map.html">マップ</a><a href="/ikitai.html">行きたいリスト</a><a href="/guides/">植物ガイド</a><a href="/about.html">サイトについて</a><a href="/contact.html">お問い合わせ</a></nav>
      <nav class="footer-nav footer-nav-tertiary"><a href="/listing.html">掲載申請</a><a href="/operator.html">運営者情報</a><a href="/privacy.html">プライバシー</a><a href="/terms.html">利用規約</a><a href="/disclaimer.html">免責事項</a></nav>
      <p class="copyright">© アガベイベントナビ</p>
    </div>
  </footer>'''


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

def card(e):
    slug=e.get('slug',''); name=e.get('name','')
    dd=e.get('dateDisplay') or e.get('date','')
    venue=e.get('location') or ''; pref=e.get('prefecture') or ''
    meta=' / '.join(x for x in [pref,venue] if x)
    return f'<article class="landing-card"><a href="/events/{slug}.html"><div class="lc-date">{dd}</div><h2 class="lc-name">{name}</h2><div class="lc-meta">{meta}</div></a></article>'

NOINDEX_PATHS = []  # sitemap除外用(リポジトリ相対パス)。main()終了時にmanifest出力。

def render(title, desc, kw, canon, bc, h1, lead, evs, root='../../',
           noindex=False, intro_html='', fallback_evs=None, rel_path=None):
    robots_meta = '<meta name="robots" content="noindex,follow">' if noindex else '<meta name="robots" content="index,follow">'
    if noindex and rel_path:
        NOINDEX_PATHS.append(rel_path)
    head = HEAD.format(title=title, description=desc, keywords=kw, canonical=canon,
                       root=root, breadcrumb_jsonld=bc_jsonld(bc), robots_meta=robots_meta)
    bch = bc_html(bc)
    if evs:
        cards = ''.join(card(e) for e in evs)
        grid = f'  <div class="landing-grid">\n{cards}\n  </div>'
        stats = f'<p class="landing-stats">該当イベント: {len(evs)}件</p>'
    else:
        fb = ''
        if fallback_evs:
            fb_cards = ''.join(card(e) for e in fallback_evs)
            fb = (f'\n  <section class="landing-hero" style="margin-top:1.5rem"><h2 style="font-size:1.15rem">'
                  f'代わりに、全国の直近開催予定のイベントをご紹介します</h2></section>'
                  f'\n  <div class="landing-grid">\n{fb_cards}\n  </div>')
        grid = ('  <div class="landing-empty">現在このページに該当するイベント情報はありません。'
                '<a href="/">ホーム</a>から最新の一覧を確認できます。</div>' + fb)
        stats = '<p class="landing-stats">該当イベント: 0件</p>'
    intro = f'\n  <section class="landing-intro">{intro_html}</section>' if intro_html else ''
    body = f'<body>\n{HEADER}\n{bch}\n  <main>\n  <section class="landing-hero"><h1>{h1}</h1><p class="lead">{lead}</p>{stats}</section>{intro}\n{grid}\n  </main>\n{FOOTER}\n</body>\n</html>\n'
    return head + '\n' + body

def write_page(path, html):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path,'w',encoding='utf-8') as f: f.write(html)

def upcoming_then_past(evs):
    today=datetime.now(JST).strftime('%Y-%m-%d')
    up=sorted([e for e in evs if e.get('date','')>=today], key=lambda e:e.get('date',''))
    past=sorted([e for e in evs if e.get('date','')<today], key=lambda e:e.get('date',''), reverse=True)
    return up + past

def index_page(out_path, title, desc, kw, canon, h1, lead, items, root='../'):
    """items: list of (name, url, count)"""
    cards = ''.join(f'<article class="landing-card"><a href="{u}"><h2 class="lc-name">{n}</h2><div class="lc-meta">{c}件</div></a></article>' for n,u,c in items)
    grid = f'  <div class="landing-grid">\n{cards}\n  </div>'
    bc = [('ホーム', DOMAIN+'/'), (title.replace('一覧','').replace('別',''), None)]
    head = HEAD.format(title=title, description=desc, keywords=kw, canonical=canon, root=root, breadcrumb_jsonld=bc_jsonld(bc), robots_meta='<meta name="robots" content="index,follow">')
    bch = bc_html(bc)
    body = f'<body>\n{HEADER}\n{bch}\n  <main>\n  <section class="landing-hero"><h1>{h1}</h1><p class="lead">{lead}</p></section>\n{grid}\n  </main>\n{FOOTER}\n</body>\n</html>\n'
    write_page(out_path, head + '\n' + body)

THIN_THRESHOLD = 3  # 掲載イベントがこの件数未満のタグ/都道府県ページはnoindex

def dyn_facts(evs, today_str):
    """イベント群から事実ベースの動的な紹介文を作る。"""
    up = sorted([e for e in evs if (e.get('date') or '') >= today_str], key=lambda e: e.get('date',''))
    parts = []
    if up:
        nxt = up[0]
        dd = nxt.get('dateDisplay') or nxt.get('date','')
        parts.append(f"直近の開催予定は「{nxt.get('name','')}」({dd})です。")
        parts.append(f"今後の開催予定は{len(up)}件掲載しています。")
    return ' '.join(parts)

def main():
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    today = datetime.now(JST)
    today_str = today.strftime('%Y-%m-%d')
    upcoming_all = sorted([e for e in events if (e.get('date') or '') >= today_str], key=lambda e: e.get('date',''))
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
                   fallback_evs=fallback5, rel_path=f'tag/{sl}/index.html'))
        counters['tag']+=1

    # Pref pages
    by_pref = defaultdict(list)
    for e in events:
        if e.get('prefecture'): by_pref[e['prefecture']].append(e)
    for p, evs in by_pref.items():
        sl = pref_slug(p)
        region = next((e.get('region') for e in evs if e.get('region')), None)
        facts = dyn_facts(evs, today_str)
        intro_html = f'<p>{p}で開催されるアガベ・塊根植物・多肉植物・ビザールプランツのイベントをまとめています。当サイト掲載分は{len(evs)}件です。</p>'
        if facts:
            intro_html += f'<p>{facts}</p>'
        if region and region in REGION_ROMAJI:
            intro_html += f'<p>近隣で開催されるイベントは<a href="/region/{REGION_ROMAJI[region]}/">{region}地方のイベント一覧</a>からも探せます。</p>'
        write_page(os.path.join(REPO_ROOT, 'pref', sl, 'index.html'),
            render(f'{p}のアガベ・植物イベント', f'{p}で開催されるアガベ・多肉植物・塊根植物のイベント情報。{len(evs)}件掲載。',
                   f'{p},アガベ,多肉植物,イベント,即売会', f'{DOMAIN}/pref/{sl}/',
                   [('ホーム',DOMAIN+'/'),('都道府県別','/pref/'),(p,None)],
                   f'{p}のイベント', f'{p}で開催される植物イベント一覧。', upcoming_then_past(evs), '../../',
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
        write_page(os.path.join(REPO_ROOT, 'region', sl, 'index.html'),
            render(f'{r}のアガベ・植物イベント', f'{r}地方で開催されるアガベ・多肉植物のイベント情報。{len(evs)}件掲載。',
                   f'{r},アガベ,イベント', f'{DOMAIN}/region/{sl}/',
                   [('ホーム',DOMAIN+'/'),('地域別','/region/'),(r,None)],
                   f'{r}地方のイベント', f'{r}地方で開催される植物イベント一覧。', upcoming_then_past(evs), '../../',
                   noindex=(len(evs) < THIN_THRESHOLD), intro_html=intro_html,
                   fallback_evs=fallback5, rel_path=f'region/{sl}/index.html'))
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
                   sorted(evs, key=lambda e:e.get('date','')), '../../',
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
                   sorted(evs, key=lambda e:e.get('date','')), '../../'))
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
               sorted(we, key=lambda e:e.get('date','')), '../',
               noindex=(len(we) == 0), fallback_evs=fallback5, rel_path='this-weekend/index.html'))
    counters['this_weekend']+=1

    # this-month
    cur_ym = today.strftime('%Y-%m')
    me = [e for e in events if e.get('date','').startswith(cur_ym)]
    write_page(os.path.join(REPO_ROOT, 'this-month', 'index.html'),
        render(f'{today.year}年{today.month}月のアガベ・植物イベント', f'今月開催の全{len(me)}件。',
               f'今月,{today.year}年{today.month}月,アガベ,イベント', f'{DOMAIN}/this-month/',
               [('ホーム',DOMAIN+'/'),(f'{today.year}年{today.month}月',None)],
               f'今月のイベント({today.year}年{today.month}月)', '今月開催されるイベント一覧。',
               sorted(me, key=lambda e:e.get('date','')), '../',
               noindex=(len(me) == 0), fallback_evs=fallback5, rel_path='this-month/index.html'))
    counters['this_month']+=1

    # Venue (2件以上のみ)
    by_venue = defaultdict(list)
    for e in events:
        v = (e.get('location') or '').strip()
        if v and v not in VAGUE_VENUES: by_venue[v].append(e)
    for v, evs in by_venue.items():
        if len(evs) < 2: continue
        sl = venue_slug(v)
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
    vi = sorted([(v,f'/venue/{venue_slug(v)}/',len(by_venue[v])) for v in by_venue if len(by_venue[v])>=2], key=lambda x:-x[2])
    index_page(os.path.join(REPO_ROOT,'venue','index.html'),
        '会場別イベント一覧','複数開催実績のある会場のみ。','会場別,アガベ,イベント',
        f'{DOMAIN}/venue/','会場別イベント一覧','複数回開催実績のある会場のみ掲載。',
        vi, '../')
    counters['index']+=1

    # sitemap 除外用 manifest
    with open(os.path.join(REPO_ROOT, 'scripts', 'landing-meta.json'), 'w', encoding='utf-8') as f:
        json.dump({'noindex': sorted(NOINDEX_PATHS)}, f, ensure_ascii=False, indent=1)

    print('=== ランディングページ生成完了 ===')
    print(f'  noindex: {len(NOINDEX_PATHS)} pages')
    for k,v in sorted(counters.items()):
        print(f'  {k}: {v} pages')

if __name__ == '__main__':
    main()
