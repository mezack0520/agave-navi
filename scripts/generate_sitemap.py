#!/usr/bin/env python3
"""
Auto-generate sitemap.xml from all HTML files + events.json image data.
Includes image:image extension so Google can index event hero images.
"""
import os
import glob
import json
from datetime import datetime

DOMAIN = "https://agave-navi.com"
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(REPO_ROOT, 'events.json')

PRIORITY_MAP = {
    "index.html":     ("1.0", "daily"),
    "ikitai.html":    ("0.8", "daily"),
    "calendar.html":  ("0.8", "daily"),
    "map.html":       ("0.7", "weekly"),
    "listing.html":   ("0.7", "monthly"),
    "about.html":     ("0.5", "monthly"),
    "contact.html":   ("0.5", "monthly"),
    "privacy.html":   ("0.3", "yearly"),
    "terms.html":     ("0.3", "yearly"),
    "disclaimer.html":("0.3", "yearly"),
    "operator.html":  ("0.3", "yearly"),
}


def url_for(rel):
    if rel == "index.html":
        return DOMAIN + "/"
    return DOMAIN + "/" + rel.replace(os.sep, "/")


def lastmod(fp):
    mtime = os.path.getmtime(fp)
    return datetime.fromtimestamp(mtime).strftime("%Y-%m-%d")


def html_escape(s):
    return (s or '').replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def load_event_images():
    """slug → imageUrl map"""
    if not os.path.exists(EVENTS_JSON):
        return {}
    with open(EVENTS_JSON, encoding='utf-8') as f:
        data = json.load(f)
    out = {}
    for e in data:
        slug = e.get('slug')
        img = e.get('imageUrl')
        if slug and img:
            out[slug] = (img, e.get('name', ''))
    return out


def generate():
    image_map = load_event_images()

    # Collect HTML files
    files = []
    files += glob.glob(os.path.join(REPO_ROOT, "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "events", "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "category", "*.html"))

    rows = []
    for fp in sorted(files):
        rel = os.path.relpath(fp, REPO_ROOT)
        basename = os.path.basename(fp)
        if basename.startswith('google') or basename == '404.html':
            continue
        loc = url_for(rel)
        lm = lastmod(fp)
        if basename in PRIORITY_MAP:
            pri, freq = PRIORITY_MAP[basename]
        elif rel.startswith('events/'):
            pri, freq = '0.8', 'weekly'
        elif rel.startswith('category/'):
            pri, freq = '0.6', 'weekly'
        else:
            pri, freq = '0.5', 'monthly'

        # detail page → image:image entry if event has imageUrl
        slug = None
        if rel.startswith('events/'):
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
            img_url, ev_name = image_map[slug]
            out.append('    <image:image>')
            out.append(f'      <image:loc>{html_escape(img_url)}</image:loc>')
            out.append(f'      <image:title>{html_escape(ev_name)}</image:title>')
            out.append('    </image:image>')
        out.append('  </url>')
    out.append('</urlset>')

    sitemap_path = os.path.join(REPO_ROOT, 'sitemap.xml')
    with open(sitemap_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out) + '\n')
    print(f'Generated sitemap.xml: {len(rows)} URLs, {sum(1 for r in rows if r[4] in image_map)} with image')


if __name__ == '__main__':
    generate()
