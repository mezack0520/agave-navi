#!/usr/bin/env python3
"""
events.json から RSS 2.0 feed を生成。
- /rss.xml — 全体(20件)
- /feeds/region-<slug>.xml — 地域別
- /feeds/tag-<slug>.xml — タグ別
"""
import json, os, re, hashlib, unicodedata
from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')
DOMAIN = 'https://agave-navi.com'
JST = timezone(timedelta(hours=9))

from sitelib import REGION_ROMAJI  # 地域スラッグの単一情報源
TAG_ROMAJI = {'即売会':'sokubaikai','マルシェ':'marche','大型':'big','展示会':'tenjikai',
              'ブロメリア':'bromelia','珍奇植物':'chinki','多肉':'tanniku',
              'コーデックス':'caudex','アガベ':'agave'}


def safe_slug(s, kind='gen'):
    if not s: return ''
    nfkd = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', nfkd).strip('-')[:50]
    return slug or f'{kind}-{hashlib.md5(s.encode()).hexdigest()[:8]}'


def render_rss(title, link, description, events, max_items=20):
    events = sorted(events, key=lambda e: (e.get('addedDate',''), e.get('date','')), reverse=True)
    items = []
    for e in events[:max_items]:
        slug = e.get('slug','')
        if not slug: continue
        url = f'{DOMAIN}/events/{slug}.html'
        nm = e.get('name', slug)
        dd = e.get('dateDisplay') or e.get('date','')
        venue = e.get('location') or ''
        pref = e.get('prefecture') or ''
        desc = e.get('description','')
        added = e.get('addedDate','')
        try:
            pub = datetime.strptime(added, '%Y-%m-%d').replace(tzinfo=JST)
        except Exception:
            pub = datetime.now(JST)
        pub_str = pub.strftime('%a, %d %b %Y %H:%M:%S +0900')
        meta = ' / '.join(x for x in [dd, pref, venue] if x)
        body = f'{meta}<br>{desc}'
        items.append(f'''  <item>
    <title>{escape(nm)}</title>
    <link>{url}</link>
    <guid>{url}</guid>
    <pubDate>{pub_str}</pubDate>
    <description><![CDATA[{body}]]></description>
  </item>''')
    now = datetime.now(JST).strftime('%a, %d %b %Y %H:%M:%S +0900')
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>{escape(title)}</title>
  <link>{link}</link>
  <atom:link href="{link.rstrip("/")}.xml" rel="self" type="application/rss+xml"/>
  <description>{escape(description)}</description>
  <language>ja</language>
  <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
'''


def main():
    with open(EVENTS, encoding='utf-8') as f:
        events = json.load(f)

    # 1. 全体
    with open(os.path.join(ROOT, 'rss.xml'), 'w', encoding='utf-8') as f:
        f.write(render_rss('アガベイベントナビ - 新着イベント', f'{DOMAIN}/',
                          '全国のアガベ・塊根植物・多肉植物・珍奇植物のイベント情報、新着順', events))

    feeds_dir = os.path.join(ROOT, 'feeds')
    os.makedirs(feeds_dir, exist_ok=True)

    # 2. 地域別
    by_region = defaultdict(list)
    for e in events:
        if e.get('region'): by_region[e['region']].append(e)
    region_count = 0
    for r, evs in by_region.items():
        sl = REGION_ROMAJI.get(r) or safe_slug(r, 'region')
        with open(os.path.join(feeds_dir, f'region-{sl}.xml'), 'w', encoding='utf-8') as f:
            f.write(render_rss(f'アガベイベントナビ - {r}地方', f'{DOMAIN}/region/{sl}/',
                              f'{r}地方のアガベ・植物イベント新着情報', evs))
        region_count += 1

    # 3. タグ別
    by_tag = defaultdict(list)
    for e in events:
        for t in e.get('tags', []): by_tag[t].append(e)
    tag_count = 0
    for t, evs in by_tag.items():
        sl = TAG_ROMAJI.get(t) or safe_slug(t, 'tag')
        with open(os.path.join(feeds_dir, f'tag-{sl}.xml'), 'w', encoding='utf-8') as f:
            f.write(render_rss(f'アガベイベントナビ - {t}', f'{DOMAIN}/tag/{sl}/',
                              f'{t}カテゴリのイベント新着情報', evs))
        tag_count += 1

    print(f'rss.xml: 1 (main) + {region_count} regions + {tag_count} tags = {1+region_count+tag_count} feeds')


if __name__ == '__main__':
    main()
