#!/usr/bin/env python3
"""sitemap.xml — HTML files + landing pages + image:image extension。"""
import os, glob, json
from datetime import datetime

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

def html_escape(s):
    return (s or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def load_event_images():
    if not os.path.exists(EVENTS_JSON): return {}
    with open(EVENTS_JSON, encoding='utf-8') as f:
        data = json.load(f)
    return {e['slug']: (e.get('imageUrl'), e.get('name','')) for e in data if e.get('slug') and e.get('imageUrl')}

def generate():
    image_map = load_event_images()
    files = []
    files += glob.glob(os.path.join(REPO_ROOT, "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "events", "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "category", "*.html"))
    # Landing pages
    for d in ['tag','pref','region','archive','venue','this-weekend','this-month','guides']:
        files += glob.glob(os.path.join(REPO_ROOT, d, "**", "*.html"), recursive=True)

    rows = []
    for fp in sorted(files):
        rel = os.path.relpath(fp, REPO_ROOT)
        basename = os.path.basename(fp)
        if basename.startswith('google') or basename == '404.html':
            continue
        loc = url_for(rel)
        # Landing page index URLs end in / (trailing slash form)
        first = rel.split(os.sep)[0]
        if first in ('tag','pref','region','archive','venue','this-weekend','this-month') and basename == 'index.html':
            loc = DOMAIN + '/' + os.path.dirname(rel).replace(os.sep,'/') + '/'
        lm = lastmod(fp)

        if basename in PRIORITY_MAP:
            pri, freq = PRIORITY_MAP[basename]
        elif rel.startswith('events' + os.sep):
            pri, freq = '0.8', 'weekly'
        elif rel.startswith('category' + os.sep):
            pri, freq = '0.6', 'weekly'
        elif first in ('tag','pref','region'):
            pri, freq = '0.7', 'weekly'
        elif first == 'this-weekend' or first == 'this-month':
            pri, freq = '0.8', 'daily'
        elif first == 'archive':
            pri, freq = '0.5', 'monthly'
        elif first == 'venue':
            pri, freq = '0.6', 'weekly'
        elif first == 'guides':
            pri, freq = '0.7', 'monthly'
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
