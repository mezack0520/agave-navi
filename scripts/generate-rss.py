#!/usr/bin/env python3
"""
generate-rss.py — events.json から RSS 2.0 feed を生成。
addedDate(掲載日) または date 順で新着20件を出力。
"""
import json, os
from datetime import datetime, timezone, timedelta
from xml.sax.saxutils import escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')
RSS = os.path.join(ROOT, 'rss.xml')
DOMAIN = 'https://agave-navi.com'

def main():
    with open(EVENTS, encoding='utf-8') as f:
        d = json.load(f)
    # Sort by addedDate desc, fallback to date asc
    d.sort(key=lambda e: (e.get('addedDate', ''), e.get('date', '')), reverse=True)
    items = []
    JST = timezone(timedelta(hours=9))
    for e in d[:20]:
        slug = e.get('slug', '')
        if not slug: continue
        url = f'{DOMAIN}/events/{slug}.html'
        title = e.get('name', slug)
        date_disp = e.get('dateDisplay') or e.get('date', '')
        venue = e.get('venue') or e.get('location', '') or ''
        desc = e.get('description', '')
        # pubDate from addedDate
        added = e.get('addedDate', '')
        try:
            pub = datetime.strptime(added, '%Y-%m-%d').replace(tzinfo=JST)
        except Exception:
            pub = datetime.now(JST)
        pub_rfc822 = pub.strftime('%a, %d %b %Y %H:%M:%S +0900')
        body = f'{date_disp} / {venue}<br>{desc}'
        items.append(f'''  <item>
    <title>{escape(title)}</title>
    <link>{url}</link>
    <guid>{url}</guid>
    <pubDate>{pub_rfc822}</pubDate>
    <description><![CDATA[{body}]]></description>
  </item>''')
    now = datetime.now(JST).strftime('%a, %d %b %Y %H:%M:%S +0900')
    rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
<channel>
  <title>アガベイベントナビ - 新着イベント</title>
  <link>{DOMAIN}/</link>
  <atom:link href="{DOMAIN}/rss.xml" rel="self" type="application/rss+xml"/>
  <description>全国のアガベ・塊根植物・多肉植物・珍奇植物のイベント情報、新着順</description>
  <language>ja</language>
  <lastBuildDate>{now}</lastBuildDate>
{chr(10).join(items)}
</channel>
</rss>
'''
    with open(RSS, 'w', encoding='utf-8') as f:
        f.write(rss)
    print(f'rss.xml: {len(items)} items')

if __name__ == '__main__':
    main()
