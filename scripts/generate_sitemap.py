#!/usr/bin/env python3
"""sitemap.xml — HTML files + landing pages + image:image extension。"""
import os, glob, json, hashlib
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

LASTMOD_MANIFEST = os.path.join(REPO_ROOT, 'scripts', 'sitemap-lastmod.json')


def load_lastmod_manifest():
    """URL → {sha, date}。中身が変わった日を覚えておくための台帳。"""
    if not os.path.exists(LASTMOD_MANIFEST):
        return {}
    try:
        with open(LASTMOD_MANIFEST, encoding='utf-8') as f:
            return json.load(f).get('pages') or {}
    except (OSError, ValueError):
        return {}


def content_sha(fp):
    h = hashlib.sha1()
    with open(fp, 'rb') as f:
        h.update(f.read())
    return h.hexdigest()


def lastmod(fp, loc, manifest, today):
    """lastmod は「中身が最後に変わった日」。

    2026-08-30 まで os.path.getmtime を見ていた。CI は毎回まっさらに clone するので
    全ファイルの mtime がチェックアウト時刻になり、**313件すべてが毎日『今日更新』**を
    名乗っていた(実測: 08-28/08-29/08-30 のどの版も lastmod が全件同一日)。
    3月から変わっていない利用規約まで毎日更新と申告する状態で、
    Google は当てにならない lastmod を無視するので、信号として死んでいた。
    mtime ではなく内容のハッシュで判定し、変わった日だけを繰り上げる。
    台帳(scripts/sitemap-lastmod.json)は生成物と一緒にコミットする。
    """
    sha = content_sha(fp)
    prev = manifest.get(loc) or {}
    date = prev.get('date') if prev.get('sha') == sha else None
    if not date:
        date = today
    manifest[loc] = {'sha': sha, 'date': date}
    return date


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

# ランディング頁を置くディレクトリ。ここの index.html は末尾スラッシュ形の
# URL で載せる(頁側の canonical がその形だから)。
# 2026-08-30 まで、収集する側のリストには 'guides' が入っているのに
# 末尾スラッシュにする側のタプルからは抜けており、guides/index.html だけが
# `/guides/index.html` として sitemap に載っていた。頁の canonical は
# `/guides/` なので、sitemap が自分で「正規ではないURL」を申告していた。
# 同じ列挙を2か所に書いたことが原因なので、単一の定数にする。
LANDING_DIRS = ('tag', 'pref', 'region', 'archive', 'venue',
                'this-weekend', 'this-month', 'guides', 'new')

def generate():
    manifest = load_lastmod_manifest()
    today = sitelib.today_jst()
    image_map = load_event_images()
    noindex_slugs = load_noindex_slugs()
    noindex_landing = load_noindex_landing()
    files = []
    files += glob.glob(os.path.join(REPO_ROOT, "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "events", "*.html"))
    files += glob.glob(os.path.join(REPO_ROOT, "category", "*.html"))
    # Landing pages
    for d in LANDING_DIRS:
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
        if first in LANDING_DIRS and basename == 'index.html':
            loc = DOMAIN + '/' + os.path.dirname(rel).replace(os.sep,'/') + '/'
        lm = lastmod(fp, loc, manifest, today)

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

    # 台帳は sitemap に載せたURLだけを残す。消えた頁の記録を持ち続けると、
    # 同じURLが後で復活したときに「昔のまま変わっていない」と誤って言う。
    keep = {loc for loc, *_ in rows}
    manifest = {k: v for k, v in manifest.items() if k in keep}
    with open(LASTMOD_MANIFEST, 'w', encoding='utf-8') as f:
        json.dump({'_note': 'sitemap.xml の lastmod 台帳。generate_sitemap.py が'
                            '内容のsha1と、その内容になった日を持つ。mtime は'
                            'CIのcloneで毎回更新されるため使えない(2026-08-30)。',
                   'pages': dict(sorted(manifest.items()))},
                  f, ensure_ascii=False, indent=1)
        f.write('\n')
    _dates = sorted({r[1] for r in rows})
    print(f'sitemap.xml: {len(rows)} URLs, '
          f'{sum(1 for r in rows if r[4] in image_map)} with image, '
          f'lastmod {len(_dates)}種 ({_dates[0]}〜{_dates[-1]})')

if __name__ == '__main__':
    generate()
