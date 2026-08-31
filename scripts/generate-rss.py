#!/usr/bin/env python3
"""
events.json から RSS 2.0 feed を生成。
- /rss.xml — 全体(20件)
- /feeds/region-<slug>.xml — 地域別
- /feeds/tag-<slug>.xml — タグ別
"""
import json, os, re
from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')
DOMAIN = 'https://agave-navi.com'
JST = timezone(timedelta(hours=9))

# スラッグは sitelib が単一情報源。ここに写しを置くと必ず食い違う。
# 2026-08-20まで TAG_ROMAJI と safe_slug をこのファイルで独自に持っており、
# sitelib 側に後から足した6タグ(アロイド・サボテン・着生植物・塊根植物・
# ビカクシダ・多肉植物)を知らないまま feeds/tag-tag-<md5>.xml を吐いていた。
# タグページ側は /tag/aroid/ を名乗っており、フィードのURLと一致しなかった。
from sitelib import REGION_ROMAJI, region_slug, tag_slug


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
        # pubDate はビルド時刻にフォールバックしない(2026-08-31)。
        # addedDate の無い回が129件あり、そこへ datetime.now() を入れていたため、
        # 毎日の再生成でその回の pubDate が「今」に更新されていた
        # (実測: フィード全324itemのうち68itemがlastBuildDateと同時刻)。
        # 購読側は pubDate で並べ替えと新着判定をするので、
        # 中身が何も変わっていない回が毎日いちばん上に新着として出る。
        # sitemap の lastmod を mtime で出していたのと同じ型の誤り
        # (2026-08-30)。生成のたびに変わる値を、発行日として出さない。
        # 安定した日付が1つも無い回は pubDate を出さない。
        # RSS 2.0 で pubDate は任意。分からない日付を主張するより出さないほうがよい。
        pub_str = ''
        for _k in ('addedDate', 'updatedAt', 'enrichedAt'):
            try:
                pub_str = (datetime.strptime(str(e.get(_k) or '')[:10], '%Y-%m-%d')
                           .replace(tzinfo=JST)
                           .strftime('%a, %d %b %Y %H:%M:%S +0900'))
                break
            except Exception:
                continue
        pub_line = f'\n    <pubDate>{pub_str}</pubDate>' if pub_str else ''
        meta = ' / '.join(x for x in [dd, pref, venue] if x)
        body = f'{meta}<br>{desc}'
        items.append(f'''  <item>
    <title>{escape(nm)}</title>
    <link>{url}</link>
    <guid>{url}</guid>{pub_line}
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

    written = set()

    # 2. 地域別
    by_region = defaultdict(list)
    for e in events:
        if e.get('region'): by_region[e['region']].append(e)
    region_count = 0
    for r, evs in by_region.items():
        sl = region_slug(r)
        written.add(f'region-{sl}.xml')
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
        sl = tag_slug(t)
        written.add(f'tag-{sl}.xml')
        with open(os.path.join(feeds_dir, f'tag-{sl}.xml'), 'w', encoding='utf-8') as f:
            f.write(render_rss(f'アガベイベントナビ - {t}', f'{DOMAIN}/tag/{sl}/',
                              f'{t}カテゴリのイベント新着情報', evs))
        tag_count += 1

    # 生成しなかった region-*.xml / tag-*.xml を消す。
    # 掃除が無いと、対象が消えたフィード(2026-07-31の沖縄地方、
    # 2026-06-11の「多肉」タグ)がその日の中身のまま公開され続ける。
    removed = []
    for fn in sorted(os.listdir(feeds_dir)):
        if not (fn.startswith(('region-', 'tag-')) and fn.endswith('.xml')):
            continue
        if fn in written:
            continue
        os.remove(os.path.join(feeds_dir, fn))
        removed.append(fn)

    print(f'rss.xml: 1 (main) + {region_count} regions + {tag_count} tags = {1+region_count+tag_count} feeds')
    if removed:
        print(f'  孤児フィードを削除: {len(removed)}件 / ' + ', '.join(removed))


if __name__ == '__main__':
    main()
