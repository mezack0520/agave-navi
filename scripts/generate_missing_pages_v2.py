#!/usr/bin/env python3
"""Generate missing event pages v2 - proper placeholder template."""
import json, os, re, urllib.parse
from datetime import datetime, timedelta

WEEKDAY_JP = ['月', '火', '水', '木', '金', '土', '日']
REGION_MAP = {
    '北海道':'北海道','青森':'東北','岩手':'東北','宮城':'東北','秋田':'東北','山形':'東北','福島':'東北',
    '茨城':'関東','栃木':'関東','群馬':'関東','埼玉':'関東','千葉':'関東','東京':'関東','神奈川':'関東',
    '新潟':'中部','富山':'中部','石川':'中部','福井':'中部','山梨':'中部','長野':'中部','岐阜':'中部','静岡':'中部','愛知':'中部',
    '三重':'近畿','滋賀':'近畿','京都':'近畿','大阪':'近畿','兵庫':'近畿','奈良':'近畿','和歌山':'近畿',
    '鳥取':'中国','島根':'中国','岡山':'中国','広島':'中国','山口':'中国',
    '徳島':'四国','香川':'四国','愛媛':'四国','高知':'四国',
    '福岡':'九州','佐賀':'九州','長崎':'九州','熊本':'九州','大分':'九州','宮崎':'九州','鹿児島':'九州','沖縄':'九州',
}

def fmt_date(d):
    if not d: return ''
    try:
        dt=datetime.strptime(d,'%Y-%m-%d'); w=WEEKDAY_JP[dt.weekday()]
        return f'{dt.year}年{dt.month}月{dt.day}日（{w}）'
    except: return d

def fmt_range(d, de):
    s=fmt_date(d)
    if not de or de==d: return s
    try:
        dt=datetime.strptime(de,'%Y-%m-%d'); w=WEEKDAY_JP[dt.weekday()]
        return f'{s} 〜 {dt.month}月{dt.day}日（{w}）'
    except: return s

def gcal(name,d,de,loc):
    try:
        ds=datetime.strptime(d,'%Y-%m-%d').strftime('%Y%m%d')
        if de and de!=d: es=(datetime.strptime(de,'%Y-%m-%d')+timedelta(days=1)).strftime('%Y%m%d')
        else: es=(datetime.strptime(d,'%Y-%m-%d')+timedelta(days=1)).strftime('%Y%m%d')
        p=urllib.parse.urlencode({'action':'TEMPLATE','text':name,'dates':f'{ds}/{es}','location':loc or ''})
        return f'https://calendar.google.com/calendar/render?{p}'
    except: return ''

def esc(s):
    if not s: return ''
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def maps_embed(loc,pref):
    q=loc or pref or ''
    return f'https://www.google.com/maps?q={urllib.parse.quote(q)}&output=embed' if q else ''

def maps_link(loc,pref):
    q=loc or pref or ''
    return f'https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(q)}' if q else ''

TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
<script async src="https://www.googletagmanager.com/gtag/js?id=G-MKY0V1H0HY"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments)}}gtag('js',new Date());gtag('config','G-MKY0V1H0HY');</script>
<meta charset="UTF-8">
<link rel="canonical" href="https://agave-navi.com/events/{slug}.html">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{name} | アガベイベントナビ</title>
<meta name="description" content="{meta_desc}">
<meta name="keywords" content="{name},{tags_text},アガベ,多肉植物,塊根植物,ビザールプランツ,即売会,イベント">
<meta property="og:title" content="{name} | アガベイベントナビ">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="https://agave-navi.com/events/{slug}.html">
<meta property="og:image" content="https://agave-navi.com/images/ogp-default.jpg">
<link rel="icon" type="image/svg+xml" href="../favicon.svg">
<link rel="icon" type="image/x-icon" href="../favicon.ico">
<link rel="apple-touch-icon" sizes="180x180" href="../apple-touch-icon.png">
<link rel="stylesheet" href="../style.css?v=20260329c">
<script type="application/ld+json">
{{"@context":"https://schema.org","@type":"Event","name":"{name}","startDate":"{date}","endDate":"{date_end}","eventAttendanceMode":"https://schema.org/OfflineEventAttendanceMode","eventStatus":"https://schema.org/EventScheduled","location":{{"@type":"Place","name":"{location}","address":{{"@type":"PostalAddress","addressRegion":"{prefecture}","addressCountry":"JP"}}}},"description":"{desc_esc}","organizer":{{"@type":"Organization","name":"{organizer}"}}{offers}}}
</script>
</head>
<body>
<header class="header"><div class="header-inner"><a href="/" class="logo"><span class="logo-en">AGAVE EVENT NAVI</span><span class="logo-jp">アガベイベントナビ</span></a><a href="/listing.html" class="fav-link" id="favLink"><span class="fav-icon">&#10084;</span> 行きたい<span class="fav-count" id="favCount">0</span></a></div></header>
<nav class="breadcrumb" aria-label="パンくずリスト"><a href="/">ホーム</a> &gt; <a href="/listing.html">{cat_label}</a> &gt; <span>{name}</span></nav>
<main class="detail-page">
<div class="detail-header">
<h1>{name}</h1>
<div class="detail-meta">
<span class="detail-status-badge" data-date="{date}" data-date-end="{date_end}"></span>
<span class="detail-meta-dot">&middot;</span>
<span class="detail-meta-item">{date_jp}</span>
<span class="detail-meta-dot">&middot;</span>
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
<h2 class="detail-section-title">概要</h2>
<p>{description}</p>
</div>
{map_section}
<div class="detail-back"><a href="/listing.html" class="detail-back-link">&larr; {cat_label}に戻る</a></div>
</div>
<div class="detail-sidebar">
<div class="detail-info-card">
<h3>EVENT INFO</h3>
<div class="info-row"><span class="info-label">日時</span><span class="info-value">{date_range}{time_html}</span></div>
{loc_row}{adm_row}
<div class="info-row"><span class="info-label">カテゴリ</span><span class="info-value">{tags_text}</span></div>
<div class="info-row"><span class="info-label">開催地域</span><span class="info-value">{region}</span></div>
{src_row}{gcal_html}
</div>
</div>
<div class="affiliate-section" id="affiliateSection"></div>
</div>
</main>
<div class="ad-slot ad-slot-article-bottom"><div class="ad-affiliate-area" id="adAffiliateArea"><div class="aff-slot" id="affSlot1"></div><div class="aff-slot" id="affSlot2"></div></div></div>
<div class="correction-notice"><p>掲載情報に誤りがある場合は<a href="/contact.html">お問い合わせ</a>よりご連絡ください。</p></div>
<footer class="footer"><div class="footer-inner"><div class="footer-logo"><span class="logo-en">AGAVE EVENT NAVI</span></div><nav class="footer-nav"><a href="/">イベント一覧</a><a href="/about.html">このサイトについて</a><a href="/contact.html">お問い合わせ</a><a href="/disclaimer.html">免責事項</a><a href="/privacy.html">プライバシーポリシー</a><a href="/operator.html">運営者情報</a></nav><p class="footer-copy">&copy; 2025-2026 アガベイベントナビ</p></div></footer>
<script src="../affiliate.js"></script>
<script src="../status-auto.js?v=20260330b"></script>
<script src="../ads.js"></script>
<script>
const SLUG='{slug}';
function toggleFav(){{let f=JSON.parse(localStorage.getItem('favEvents')||'[]');const i=f.indexOf(SLUG);if(i>=0)f.splice(i,1);else f.push(SLUG);localStorage.setItem('favEvents',JSON.stringify(f));updateFavUI()}}
function updateFavUI(){{const f=JSON.parse(localStorage.getItem('favEvents')||'[]');const b=document.getElementById('favBtn');const l=document.getElementById('favLabel');if(f.includes(SLUG)){{b.classList.add('is-fav');l.textContent='行きたい！'}}else{{b.classList.remove('is-fav');l.textContent='行きたい'}}const c=document.getElementById('favCount');if(c)c.textContent=f.length}}
updateFavUI();
</script>
</body>
</html>"""

def gen(ev):
    slug=ev.get('slug','')
    name=ev.get('name',slug)
    date=ev.get('date','')
    date_end=ev.get('dateEnd','') or date
    loc=ev.get('location','')
    pref=ev.get('prefecture','')
    region=ev.get('region','') or REGION_MAP.get(pref,'')
    tags=ev.get('tags',[])
    if isinstance(tags,str): tags=[t.strip() for t in tags.split(',')]
    tags_text=','.join(tags)
    desc=ev.get('description',f'{name}のイベント情報です。')
    src=ev.get('sourceUrl','')
    adm=ev.get('admission','')
    tm=ev.get('time','')
    org=ev.get('organizer','')
    date_jp=fmt_date(date)
    date_range=fmt_range(date, date_end if date_end!=date else '')
    meta_desc=desc[:120] if desc else f'{name}のイベント情報'
    cat_label='即売会一覧'
    time_html=f'<br>{tm}' if tm else ''
    loc_row=f'<div class="info-row"><span class="info-label">会場</span><span class="info-value">{esc(loc)}</span></div>' if loc else ''
    adm_row=f'<div class="info-row"><span class="info-label">入場料</span><span class="info-value">{esc(adm)}</span></div>' if adm else ''
    if src:
        if 'instagram.com' in src:
            src_row=f'<div class="info-row"><span class="info-label">Instagram</span><span class="info-value"><a href="{esc(src)}" target="_blank" rel="noopener">Instagram →</a></span></div>'
        else:
            src_row=f'<div class="info-row"><span class="info-label">公式サイト</span><span class="info-value"><a href="{esc(src)}" target="_blank" rel="noopener">公式サイト →</a></span></div>'
    else: src_row=''
    gu=gcal(name,date,date_end,loc or pref)
    gcal_html=f'<a href="{gu}" target="_blank" rel="noopener" class="gcal-btn">&#128197; Googleカレンダーに追加</a>' if gu else ''
    if loc:
        me=maps_embed(loc,pref); ml=maps_link(loc,pref)
        map_section=f'<div class="detail-map"><h2 class="detail-section-title">会場</h2><div class="map-container"><a href="{ml}" target="_blank" rel="noopener" class="map-open-link">マップで開く &#8599;</a><iframe src="{me}" width="100%" height="300" style="border:0;" allowfullscreen="" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe></div></div>'
    else: map_section=''
    offers=''
    if adm: offers=f',"offers":{{"@type":"Offer","price":"0","priceCurrency":"JPY","description":"{esc(adm)}"}}'
    return TEMPLATE.format(slug=slug,name=esc(name),date=date,date_end=date_end or date,location=esc(loc or pref),prefecture=esc(pref),region=esc(region),tags_text=esc(tags_text),description=esc(desc),desc_esc=esc(desc).replace('\n',' '),meta_desc=esc(meta_desc),date_jp=date_jp,date_range=date_range,time_html=time_html,cat_label=cat_label,organizer=esc(org or name),offers=offers,map_section=map_section,loc_row=loc_row,adm_row=adm_row,src_row=src_row,gcal_html=gcal_html)

def card_data(idx,slug):
    p=idx.find(f'data-slug="{slug}"')
    if p<0: return None
    cs=idx.rfind('<div class="event-card"',0,p)
    ac=idx[cs:p+len(slug)+2]; ch=idx[p:p+2500]
    tx=[]
    i=0
    while i<len(ch):
        g=ch.find('>',i)
        if g<0: break
        l=ch.find('<',g)
        if l<0: break
        t=ch[g+1:l].strip()
        if t: tx.append(t)
        i=l
    dm=re.search(r'data-date="([^"]+)"',ac)
    dem=re.search(r'data-date-end="([^"]+)"',ac)
    pm=re.search(r'data-pref="([^"]+)"',ac)
    tm=re.search(r'data-tags="([^"]+)"',ac)
    return {'slug':slug,'name':tx[1] if len(tx)>1 else slug,'date':dm.group(1) if dm else '','dateEnd':dem.group(1) if dem else '','dateDisplay':tx[0] if tx else '','description':tx[2] if len(tx)>2 else '','prefecture':pm.group(1) if pm else '','region':REGION_MAP.get(pm.group(1),'') if pm else '','tags':tm.group(1).split(',') if tm else []}

def main():
    with open('events.json','r',encoding='utf-8') as f: events=json.load(f)
    with open('index.html','r',encoding='utf-8') as f: idx=f.read()
    slugs=re.findall(r'data-slug="([^"]+)"',idx)
    exist=set(fn.replace('.html','') for fn in os.listdir('events') if fn.endswith('.html')) if os.path.isdir('events') else set()
    missing=[s for s in slugs if s not in exist]
    print(f'Missing: {len(missing)}')
    if not missing: print('Nothing to do.'); return
    os.makedirs('events',exist_ok=True)
    for s in missing:
        ev=next((e for e in events if e['slug']==s),None) or card_data(idx,s)
        if not ev: print(f'  Skip {s}'); continue
        with open(f'events/{s}.html','w',encoding='utf-8') as f: f.write(gen(ev))
        print(f'  Created: events/{s}.html')
    print('Done!')

if __name__=='__main__': main()
