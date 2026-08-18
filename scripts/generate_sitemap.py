#!/usr/bin/env python3
"""sitemap.xml — HTML files + landing pages + image:image extension。"""
import os, glob, json
from datetime import datetime

import sitelib
from sitelib import html_escape

DOMAIN = "https://agave-navi.com"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(REPO_ROOT, 'events.json')

PRIORITY_MAP = {
    "index.html":     ("1.0", "daily"),
    "ikitai.html":    ("0.8", "daily"),
    "calendar.html":  ("0.8", "daily"),
    "map.html":       ("0.7", "weekly"),
    "dashboard.html": ("0.7", "weekly"),
    "listing.html":   ("0.7", "monthly"),
    "about.html":     ("0.5", "monthly"),
    "contact.html":   ("0.5", "monthly"),
    "operator.html":  ("0.5", "monthly"),
    "privacy.html":   ("0.3", "yearly"),
    "terms.html":     ("0.3", "yearly"),
    "disclaimer.html":("0.3", "yearly"),
}

def url_for(rel):
    if rel == "index.html": return DOMAIN + "/"
    return DOMAIN + "/" + rel.replace(os.sep, "/")

def lastmod(fp):
    return datetime.fromtimestamp(os.path.getmtime(fp)).strftime("%Y-%m-%d")


def load_event_images():
    if not os.path.exists(EVENTS_JSON): return {}
    with open(EVENTS_JSON, encoding='utf-8') as f:
        data = json.load(f)
    return {e['slug']: (e.get('imageUrl'), e.get('name','')) for e in data if e.get('slug') and e.get('imageUrl')}

def load_noindex_slugs():
    """終了から30日超のイベント(detailページ側で noindex 付与)のslug集合。"""
    if not os.path.exists(EVENTS_JSON): return set()
    from datetime import timedelta
    with open(EVENTS_JSON, encoding='utf-8') as f:
        data = json.load(f)
    cutoff = (sitelib.now_jst() - timedelta(days=30)).strftime('%Y-%m-%d')
    out = set()
    for e in data:
        end = e.get('dateEnd') or e.get('date') or ''
        if end and end < cutoff:
            out.add(e.get('slug'))
    mpath = os.path.join(REPO_ROOT, 'scripts', 'events-meta.json')
    if os.path.exists(mpath):
        with open(mpath, encoding='utf-8') as f:
            out |= set(json.load(f).get('noindex', []))
    return out

def load_noindex_landing():
    """generate-landing-pages.py が出力した sitemap除外 manifest。
    noindex に加え、canonical を他URLに向けた頁も外す。
    自分自身を指さないcanonicalとsitemap掲載は矛盾した信号になるため。"""
    mpath = os.path.join(REPO_ROOT, 'scripts', 'landing-meta.json')
    if not os.path.exists(mpath): return set()
    with open(mpath, encoding='utf-8') as f:
        m = json.load(f)
    return set(m.get('noindex', [])) | set(m.get('canonicalized', []))

# 内部ツール・noindexページはsitemapに載せない
EXCLUDE_BASENAMES = {'dashboard.html'}

def generate():
    image_map = load_event_images()
    noindex_slugs = load_noindex_slugs()
    noindex_landing = load_noindex_landing()
    files = []
    files += glob.glob(os.path.join(REPO_ROOT, "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "events", "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "category", "*.html"))
    # Landing pages
    for d in ['tag','pref','region','archive','venue','this-weekend','this-month','guides','new']:
        files += glob.glob(os.path.join(REPO_ROOT, d, "**", "*.html"), recursive=True)

    rows = []
    for fp in sorted(files):
        rel = os.path.relpath(fp, REPO_ROOT)
        basename = os.path.basename(fp)
        if basename.startswith('google') or basename == '404.html':
            continue
        if basename in EXCLUDE_BASENAMES:
            continue
        relu = rel.replace(os.sep, '/')
        if relu in noindex_landing:
            continue
        if relu.startswith('events/') and os.path.splitext(basename)[0] in noindex_slugs:
            continue
        loc = url_for(rel)
        # Landing page index URLs end in / (trailing slash form)
        first = rel.split(os.sep)[0]
        if first in ('tag','pref','region','archive','venue','this-weekend','this-month','new') and basename == 'index.html':
            loc = DOMAIN + '/' + os.path.dirname(rel).replace(os.sep,'/') + '/'
        lm = lastmod(fp)

        # directory-based rules first (so landing-page index.html does NOT inherit
        # the root index.html priority of 1.0/daily)
        if rel.startswith('events' + os.sep):
            pri, freq = '0.8', 'weekly'
        elif rel.startswith('category' + os.sep):
            pri, freq = '0.6', 'weekly'
        elif first in ('tag','pref','region'):
            pri, freq = '0.7', 'weekly'
        elif first in ('this-weekend', 'this-month', 'new'):
            pri, freq = '0.8', 'daily'
        elif first == 'archive':
            pri, freq = '0.5', 'monthly'
        elif first == 'venue':
            pri, freq = '0.6', 'weekly'
        elif first == 'guides':
            pri, freq = '0.7', 'monthly'
        elif basename in PRIORITY_MAP:
            # only root-level html files fall here
            pri, freq = PRIORITY_MAP[basename]
        else:
            pri, freq = '0.5', 'monthly'

        slug = None
        if rel.startswith('events' + os.sep):
            slug = os.path.splitext(basename)[0]
        rows.append((loc, lm, freq, pri, slug))

    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
           '        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    for loc, lm, freq, pri, slug in rows:
        out.append('  <url>')
        out.append(f'    <loc>{loc}</loc>')
        out.append(f'    <lastmod>{lm}</lastmod>')
        out.append(f'    <changefreq>{freq}</changefreq>')
        out.append(f'    <priority>{pri}</priority>')
        if slug and slug in image_map:
            img, nm = image_map[slug]
            out.append('    <image:image>')
            out.append(f'      <image:loc>{html_escape(img)}</image:loc>')
            out.append(f'      <image:title>{html_escape(nm)}</image:title>')
            out.append('    </image:image>')
        out.append('  </url>')
    out.append('</urlset>')

    with open(os.path.join(REPO_ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    print(f'sitemap.xml: {len(rows)} URLs, {sum(1 for r in rows if r[4] in image_map)} with image')

if __name__ == '__main__':
    generate()
