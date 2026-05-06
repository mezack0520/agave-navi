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
              'コーデックス':'caudex','アガベ':'agave'}

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
def venue_slug(v): return safe_slug(v, 'v')

HEAD = '''<!DOCTYPE html>
<html lang="ja">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-NKY8V1H8HY"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NKY8V1H8HY');</script>
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-0790348660030345" crossorigin="anonymous"></script>
  <meta charset="UTF-8">
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
  <meta name="theme-color" content="#2d5016">
  <link rel="alternate" type="application/rss+xml" title="アガベイベントナビ" href="{root}rss.xml">
  <link rel="stylesheet" href="{root}style.css?v=20260507a">
  <script type="application/ld+json">
  {{"@context":"https://schema.org","@type":"CollectionPage","name":"{title}","description":"{description}","url":"{canonical}","isPartOf":{{"@type":"WebSite","name":"アガベイベントナビ","url":"https://agave-navi.com/"}}}}
  </script>
{breadcrumb_jsonld}
  <style>
    .landing-hero{{max-width:1200px;margin:1.2rem auto .6rem;padding:0 1rem}}
    .landing-hero h1{{font-size:1.8rem;margin:.2rem 0;color:#2d5016}}
    .landing-hero p.lead{{color:#555;margin:.4rem 0 0}}
    .landing-stats{{font-size:.9rem;color:#6a7855;margin:.4rem 0}}
    .landing-grid{{max-width:1200px;margin:1rem auto;padding:0 1rem;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem}}
    .landing-card{{background:#fff;border-radius:12px;box-shadow:0 2px 8px rgba(0,0,0,.06);overflow:hidden;transition:transform .2s,box-shadow .2s}}
    .landing-card:hover{{transform:translateY(-2px);box-shadow:0 6px 16px rgba(0,0,0,.12)}}
    .landing-card a{{display:block;color:inherit;text-decoration:none;padding:1rem}}
    .landing-card .lc-date{{font-weight:700;color:#2d5016;font-size:.9rem}}
    .landing-card .lc-name{{font-size:1.05rem;margin:.4rem 0 .3rem;line-height:1.35}}
    .landing-card .lc-meta{{font-size:.85rem;color:#6a7855}}
    .landing-empty{{max-width:1200px;margin:2rem auto;padding:2rem 1rem;text-align:center;color:#6a7855;background:#fff;border-radius:12px}}
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
      <p class="footer-tagline">アガベ・塊根・ビザールプランツのイベント検索ナビ</p>
      <nav class="footer-nav"><a href="/">ホーム</a><a href="/calendar.html">カレンダー</a><a href="/map.html">マップ</a><a href="/ikitai.html">行きたいリスト</a></nav>
      <nav class="footer-nav"><a href="/pref/">都道府県別</a><a href="/region/">地域別</a><a href="/tag/">タグ別</a><a href="/archive/">アーカイブ</a></nav>
      <nav class="footer-nav"><a href="/about.html">サイトについて</a><a href="/operator.html">運営者情報</a><a href="/listing.html">掲載申請</a><a href="/contact.html">お問い合わせ</a></nav>
      <p class="copyright">© アガベイベントナビ</p>
    </div>
  </footer>'''

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

def render(title, desc, kw, canon, bc, h1, lead, evs, root='../../'):
    head = HEAD.format(title=title, description=desc, keywords=kw, canonical=canon, root=root, breadcrumb_jsonld=bc_jsonld(bc))
    bch = bc_html(bc)
    if evs:
        cards = ''.join(card(e) for e in evs)
        grid = f'  <div class="landing-grid">\n{cards}\n  </div>'
        stats = f'<p class="landing-stats">該当イベント: {len(evs)}件</p>'
    else:
        grid = '  <div class="landing-empty">該当するイベント情報はありません。<a href="/">ホーム</a>から最新の一覧を確認できます。</div>'
        stats = '<p class="landing-stats">該当イベント: 0件</p>'
    body = f'<body>\n{HEADER}\n{bch}\n  <main>\n  <section class="landing-hero"><h1>{h1}</h1><p class="lead">{lead}</p>{stats}</section>\n{grid}\n  </main>\n{FOOTER}\n</body>\n</html>\n'
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
    head = HEAD.format(title=title, description=desc, keywords=kw, canonical=canon, root=root, breadcrumb_jsonld=bc_jsonld(bc))
    bch = bc_html(bc)
    body = f'<body>\n{HEADER}\n{bch}\n  <main>\n  <section class="landing-hero"><h1>{h1}</h1><p class="lead">{lead}</p></section>\n{grid}\n  </main>\n{FOOTER}\n</body>\n</html>\n'
    write_page(out_path, head + '\n' + body)

def main():
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    today = datetime.now(JST)
    counters = defaultdict(int)

    # Tag pages
    by_tag = defaultdict(list)
    for e in events:
        for t in e.get('tags', []): by_tag[t].append(e)
    for t, evs in by_tag.items():
        sl = tag_slug(t)
        write_page(os.path.join(REPO_ROOT, 'tag', sl, 'index.html'),
            render(f'{t}のイベント一覧', f'{t}に該当するアガベ・多肉植物・塊根植物のイベント情報。{len(evs)}件掲載。',
                   f'{t},アガベ,多肉植物,イベント,即売会', f'{DOMAIN}/tag/{sl}/',
                   [('ホーム',DOMAIN+'/'),('タグ別','/tag/'),(t,None)],
                   f'タグ: {t}', f'「{t}」のイベント一覧。直近の開催から過去の実績まで。', upcoming_then_past(evs), '../../'))
        counters['tag']+=1

    # Pref pages
    by_pref = defaultdict(list)
    for e in events:
        if e.get('prefecture'): by_pref[e['prefecture']].append(e)
    for p, evs in by_pref.items():
        sl = pref_slug(p)
        write_page(os.path.join(REPO_ROOT, 'pref', sl, 'index.html'),
            render(f'{p}のアガベ・植物イベント', f'{p}で開催されるアガベ・多肉植物・塊根植物のイベント情報。{len(evs)}件掲載。',
                   f'{p},アガベ,多肉植物,イベント,即売会', f'{DOMAIN}/pref/{sl}/',
                   [('ホーム',DOMAIN+'/'),('都道府県別','/pref/'),(p,None)],
                   f'{p}のイベント', f'{p}で開催される植物イベント一覧。', upcoming_then_past(evs), '../../'))
        counters['pref']+=1

    # Region pages
    by_region = defaultdict(list)
    for e in events:
        if e.get('region'): by_region[e['region']].append(e)
    for r, evs in by_region.items():
        sl = region_slug(r)
        write_page(os.path.join(REPO_ROOT, 'region', sl, 'index.html'),
            render(f'{r}のアガベ・植物イベント', f'{r}地方で開催されるアガベ・多肉植物のイベント情報。{len(evs)}件掲載。',
                   f'{r},アガベ,イベント', f'{DOMAIN}/region/{sl}/',
                   [('ホーム',DOMAIN+'/'),('地域別','/region/'),(r,None)],
                   f'{r}地方のイベント', f'{r}地方で開催される植物イベント一覧。', upcoming_then_past(evs), '../../'))
        counters['region']+=1

    # Archive YM
    by_ym = defaultdict(list)
    for e in events:
        d = e.get('date','')
        if len(d)>=7: by_ym[d[:7]].append(e)
    for ym, evs in by_ym.items():
        y, m = ym.split('-'); m_int=int(m)
        write_page(os.path.join(REPO_ROOT, 'archive', ym, 'index.html'),
            render(f'{y}年{m_int}月のアガベ・植物イベント', f'{y}年{m_int}月開催のイベント{len(evs)}件。',
                   f'{y}年{m_int}月,アガベ,イベント', f'{DOMAIN}/archive/{ym}/',
                   [('ホーム',DOMAIN+'/'),('アーカイブ','/archive/'),(f'{y}年{m_int}月',None)],
                   f'{y}年{m_int}月のイベント', f'{y}年{m_int}月に開催された/開催予定のイベント。',
                   sorted(evs, key=lambda e:e.get('date','')), '../../'))
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
               sorted(we, key=lambda e:e.get('date','')), '../'))
    counters['this_weekend']+=1

    # this-month
    cur_ym = today.strftime('%Y-%m')
    me = [e for e in events if e.get('date','').startswith(cur_ym)]
    write_page(os.path.join(REPO_ROOT, 'this-month', 'index.html'),
        render(f'{today.year}年{today.month}月のアガベ・植物イベント', f'今月開催の全{len(me)}件。',
               f'今月,{today.year}年{today.month}月,アガベ,イベント', f'{DOMAIN}/this-month/',
               [('ホーム',DOMAIN+'/'),(f'{today.year}年{today.month}月',None)],
               f'今月のイベント({today.year}年{today.month}月)', '今月開催されるイベント一覧。',
               sorted(me, key=lambda e:e.get('date','')), '../'))
    counters['this_month']+=1

    # Venue (2件以上のみ)
    by_venue = defaultdict(list)
    for e in events:
        v = (e.get('location') or '').strip()
        if v: by_venue[v].append(e)
    for v, evs in by_venue.items():
        if len(evs) < 2: continue
        sl = venue_slug(v)
        write_page(os.path.join(REPO_ROOT, 'venue', sl, 'index.html'),
            render(f'{v}でのアガベ・植物イベント', f'{v}で開催されるイベント情報。{len(evs)}件。',
                   f'{v},アガベ,イベント', f'{DOMAIN}/venue/{sl}/',
                   [('ホーム',DOMAIN+'/'),('会場別','/venue/'),(v,None)],
                   v, f'{v}で過去/今後に開催されるイベント一覧。', upcoming_then_past(evs), '../../'))
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

    print('=== ランディングページ生成完了 ===')
    for k,v in sorted(counters.items()):
        print(f'  {k}: {v} pages')

if __name__ == '__main__':
    main()
