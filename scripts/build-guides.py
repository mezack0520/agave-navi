#!/usr/bin/env python3
"""
/guides/ 配下のエバーグリーン記事を生成。
各記事は guides_content/*.py からタイトル・メタ・本文(Markdown風)を読み込み
HTML化する。スタイルはサイト共通の style.css に揃える。
"""
import os, re, json, glob, importlib.util
from datetime import datetime

import sitelib
from sitelib import JST, DOMAIN

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTENT_DIR = os.path.join(REPO_ROOT, 'guides_content')
OUT_DIR = os.path.join(REPO_ROOT, 'guides')


HEAD = '''<!DOCTYPE html>
<html lang="ja">
<head>
  <script async src="https://www.googletagmanager.com/gtag/js?id=G-NKY8V1H8HY"></script>
  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-NKY8V1H8HY');</script>
  <meta charset="UTF-8">
  <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-0790348660030345" crossorigin="anonymous"></script>
  <meta name="google-adsense-account" content="ca-pub-0790348660030345">
  <link rel="canonical" href="{canonical}">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} | アガベイベントナビ</title>
  <meta name="description" content="{description}">
  <meta name="keywords" content="{keywords}">
  <meta property="og:title" content="{title} | アガベイベントナビ">
  <meta property="og:description" content="{description}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canonical}">
  <meta property="og:image" content="https://agave-navi.com/og-image.png">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" type="image/svg+xml" href="../favicon.svg">
  <link rel="icon" type="image/x-icon" href="../favicon.ico">
  <link rel="apple-touch-icon" sizes="180x180" href="../apple-touch-icon.png">
  <link rel="manifest" href="../manifest.webmanifest">
  <meta name="theme-color" content="#111">
  <link rel="alternate" type="application/rss+xml" title="アガベイベントナビ" href="../rss.xml">
  <link rel="stylesheet" href="../style.css?v=20260611a">
  <script type="application/ld+json">
  {{"@context":"https://schema.org","@type":"Article","headline":"{title}","description":"{description}","datePublished":"{date_iso}","dateModified":"{date_iso}","author":{{"@type":"Organization","name":"アガベイベントナビ","url":"https://agave-navi.com/"}},"publisher":{{"@type":"Organization","name":"アガベイベントナビ","url":"https://agave-navi.com/","logo":{{"@type":"ImageObject","url":"https://agave-navi.com/android-chrome-512x512.png"}}}},"mainEntityOfPage":{{"@type":"WebPage","@id":"{canonical}"}},"image":"https://agave-navi.com/og-image.png"}}
  </script>
  <script type="application/ld+json">
  {{"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":[{{"@type":"ListItem","position":1,"name":"ホーム","item":"https://agave-navi.com/"}},{{"@type":"ListItem","position":2,"name":"植物ガイド","item":"https://agave-navi.com/guides/"}},{{"@type":"ListItem","position":3,"name":"{title}"}}]}}
  </script>
  <style>
    .guide-wrap{{max-width:760px;margin:0 auto;padding:0 1rem}}
    .guide-hero{{padding:1.5rem 0 .8rem;border-bottom:1px solid #e8e8e8}}
    .guide-hero h1{{font-size:1.7rem;line-height:1.35;color:#1a1a1a;margin:.4rem 0 .6rem;font-weight:900;letter-spacing:-.01em}}
    .guide-meta{{font-size:.85rem;color:#888}}
    .guide-meta .meta-cat{{background:#f3f3ee;color:#444;padding:2px 8px;border-radius:3px;font-weight:600;margin-right:.5rem;font-size:.78rem}}
    .guide-toc{{background:#fafaf7;border-left:3px solid #d0d0c8;padding:.8rem 1rem;margin:1.2rem 0;border-radius:0 4px 4px 0}}
    .guide-toc h2{{font-size:.85rem;color:#666;margin:0 0 .4rem;letter-spacing:.05em;border:none;padding:0;font-weight:700}}
    .guide-toc ol{{margin:0;padding-left:1.3rem;line-height:1.7;font-size:.9rem}}
    .guide-toc a{{color:#333;text-decoration:none}}
    .guide-toc a:hover{{text-decoration:underline;color:#000}}
    .guide-body{{font-size:1rem;line-height:1.95;color:#222}}
    .guide-body h2{{font-size:1.3rem;color:#1a1a1a;border-bottom:1px solid #e0e0e0;padding-bottom:.45rem;margin:2.2rem 0 .9rem;font-weight:800;letter-spacing:-.005em}}
    .guide-body h3{{font-size:1.05rem;color:#222;margin:1.6rem 0 .5rem;font-weight:700}}
    .guide-body p{{margin:.7rem 0}}
    .guide-body ul,.guide-body ol{{margin:.7rem 0;padding-left:1.5rem;line-height:1.85}}
    .guide-body li{{margin:.35rem 0}}
    .guide-body strong{{color:#000;font-weight:700}}
    .guide-body .callout{{background:#fafaf5;border-left:3px solid #d0c890;padding:.7rem .9rem;margin:1rem 0;border-radius:0 4px 4px 0}}
    .guide-body .callout.warning{{background:#fdf3f0;border-left-color:#d6766a}}
    .guide-body .callout.tip{{background:#f0f6f4;border-left-color:#7ab39a}}
    .guide-body .callout p{{margin:.25rem 0;font-size:.92rem;color:#444}}
    .guide-related{{margin:2.5rem 0 1.5rem;padding:1.2rem;background:#fafaf7;border-radius:6px}}
    .guide-related h2{{font-size:.95rem;color:#666;margin:0 0 .8rem;border:none;padding:0}}
    .guide-related ul{{list-style:none;padding:0;display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:.5rem}}
    .guide-related li a{{display:block;padding:.6rem .8rem;background:#fff;border-radius:4px;color:#333;text-decoration:none;font-size:.9rem;border:1px solid #e8e8e8}}
    .guide-related li a:hover{{background:#f5f5f0;border-color:#999}}
    .guide-author{{margin:2rem 0 1rem;padding:1rem;background:#fafaf7;border-radius:6px;font-size:.85rem;color:#555;line-height:1.7}}
    .guide-author strong{{color:#222}}
    .guide-index-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:1rem;margin:1.5rem 0}}
    .guide-card{{background:#fff;border-radius:6px;border:1px solid #e8e8e8;overflow:hidden;transition:border-color .2s,box-shadow .2s}}
    .guide-card:hover{{border-color:#aaa;box-shadow:0 2px 8px rgba(0,0,0,.06)}}
    .guide-card a{{display:block;padding:1.1rem;color:inherit;text-decoration:none}}
    .guide-card .gc-cat{{display:inline-block;background:#f3f3ee;color:#555;font-size:.72rem;font-weight:600;padding:2px 7px;border-radius:3px;letter-spacing:.03em}}
    .guide-card .gc-title{{font-size:1.02rem;color:#1a1a1a;margin:.5rem 0 .35rem;line-height:1.45;border:none;padding:0;font-weight:700}}
    .guide-card .gc-lead{{font-size:.85rem;color:#555;line-height:1.6;margin:.25rem 0 .55rem}}
    .guide-card .gc-meta{{font-size:.75rem;color:#888}}
  </style>
</head>'''
HEAD = HEAD.replace('style.css?v=20260611a', 'style.css?v=' + sitelib.CSS_VERSION)


HEADER = sitelib.site_header()


FOOTER = sitelib.site_footer()


def render_markdown(md):
    """簡易Markdown→HTMLレンダラ。h2, h3, p, ul, ol, strong, callout 対応。"""
    lines = md.strip().split('\n')
    out = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        if not line:
            i += 1; continue
        if line.startswith('## '):
            slug = re.sub(r'[^\w぀-ヿ一-鿿]+', '-', line[3:]).strip('-')
            out.append(f'<h2 id="{slug}">{line[3:]}</h2>')
        elif line.startswith('### '):
            out.append(f'<h3>{line[4:]}</h3>')
        elif line.startswith('!!! '):
            # !!! tip / warning / note  + 連続段落
            kind = line[4:].strip()
            cls = {'tip':'tip','warning':'warning','note':''}.get(kind,'')
            block = []
            i += 1
            while i < len(lines) and lines[i].startswith('    '):
                block.append(lines[i][4:])
                i += 1
            out.append(f'<div class="callout {cls}">' + render_markdown('\n'.join(block)) + '</div>')
            continue
        elif line.startswith('- '):
            ul = []
            while i < len(lines) and lines[i].startswith('- '):
                ul.append('<li>' + inline_md(lines[i][2:]) + '</li>')
                i += 1
            out.append('<ul>\n' + '\n'.join(ul) + '\n</ul>')
            continue
        elif re.match(r'^\d+\. ', line):
            ol = []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i]):
                ol.append('<li>' + inline_md(re.sub(r'^\d+\. ', '', lines[i])) + '</li>')
                i += 1
            out.append('<ol>\n' + '\n'.join(ol) + '\n</ol>')
            continue
        else:
            out.append('<p>' + inline_md(line) + '</p>')
        i += 1
    return '\n'.join(out)


def inline_md(s):
    s = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', s)
    return s


def extract_toc(md):
    """## 見出しから目次を抽出。"""
    toc = []
    for line in md.split('\n'):
        if line.startswith('## '):
            t = line[3:].strip()
            slug = re.sub(r'[^\w぀-ヿ一-鿿]+', '-', t).strip('-')
            toc.append((t, slug))
    return toc


def render_guide(meta, md, related):
    toc = extract_toc(md)
    toc_html = ''
    if len(toc) >= 3:
        toc_html = ('  <div class="guide-toc"><h2>目次</h2><ol>' +
                    ''.join(f'<li><a href="#{s}">{t}</a></li>' for t, s in toc) +
                    '</ol></div>')
    body = render_markdown(md)
    rel_html = ''
    if related:
        items = ''.join(f'<li><a href="{u}">{n}</a></li>' for n, u in related)
        rel_html = f'  <section class="guide-related"><h2>関連ガイド・イベント</h2><ul>{items}</ul></section>'
    date_iso = datetime.now(JST).strftime('%Y-%m-%d')
    head = HEAD.format(
        title=meta['title'], description=meta['description'],
        keywords=meta['keywords'], canonical=f"{DOMAIN}/guides/{meta['slug']}.html",
        date_iso=date_iso,
    )
    bc = ('  <nav class="breadcrumb" aria-label="パンくずリスト">'
          '<a href="/">ホーム</a> &gt; <a href="/guides/">植物ガイド</a> &gt; '
          f'<span>{meta["title"]}</span></nav>')
    body_html = (f'<body>\n{HEADER}\n{bc}\n  <main>\n  <div class="guide-wrap">\n'
                 f'    <section class="guide-hero">\n'
                 f'      <div class="guide-meta"><span class="meta-cat">{meta["category"]}</span>'
                 f'最終更新: {date_iso} / 読了目安: {meta["read_min"]}分</div>\n'
                 f'      <h1>{meta["title"]}</h1>\n'
                 f'      <p style="color:#555;line-height:1.7">{meta["lead"]}</p>\n'
                 f'    </section>\n{toc_html}\n'
                 f'    <article class="guide-body">\n{body}\n    </article>\n'
                 f'    <section class="affiliate-section" data-guide="{meta["slug"]}"></section>\n'
                 f'    <section class="guide-author">'
                 f'<strong>このガイドについて</strong> — 当サイト運営者が実際に管理している植物の栽培記録(関東・東京)と、複数の文献・公的データ(USDA耐寒帯など)を参照して作成しました。'
                 f'掲載情報に誤りや改善提案がございましたら <a href="/contact.html">お問い合わせ</a> よりご連絡ください。'
                 f'</section>\n{rel_html}\n  </div>\n  </main>\n{FOOTER}\n'
                 f'  <script src="../affiliate.js"></script>\n</body>\n</html>')
    return head + '\n' + body_html


def main():
    files = sorted(glob.glob(os.path.join(CONTENT_DIR, '*.py')))
    if not files:
        print('No guide content files found.'); return
    os.makedirs(OUT_DIR, exist_ok=True)
    guides_meta = []
    for fp in files:
        spec = importlib.util.spec_from_file_location('g', fp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        meta = mod.META
        md = mod.CONTENT
        related = getattr(mod, 'RELATED', [])
        html = render_guide(meta, md, related)
        out_path = os.path.join(OUT_DIR, f"{meta['slug']}.html")
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        guides_meta.append(meta)
        print(f"  → guides/{meta['slug']}.html ({len(md)} chars)")

    # /guides/index.html
    cards = ''
    for m in guides_meta:
        cards += (f'<article class="guide-card"><a href="/guides/{m["slug"]}.html">'
                  f'<span class="gc-cat">{m["category"]}</span>'
                  f'<h2 class="gc-title">{m["title"]}</h2>'
                  f'<p class="gc-lead">{m["lead"]}</p>'
                  f'<span class="gc-meta">{m["read_min"]}分で読める</span>'
                  f'</a></article>')
    head = HEAD.format(title='植物ガイド一覧', description='アガベ・塊根植物・ビザールプランツの育て方や購入時のチェックポイントを解説したガイド記事一覧。',
                       keywords='植物ガイド,アガベ,塊根植物,育て方,即売会', canonical=f'{DOMAIN}/guides/', date_iso=datetime.now(JST).strftime('%Y-%m-%d'))
    body_html = f'''<body>
{HEADER}
  <nav class="breadcrumb" aria-label="パンくずリスト"><a href="/">ホーム</a> &gt; <span>植物ガイド</span></nav>
  <main>
    <div class="guide-wrap" style="max-width:1200px">
      <section class="guide-hero"><h1>植物ガイド</h1>
      <p style="color:#555;line-height:1.7">アガベ・塊根植物・ビザールプランツの育て方、即売会で失敗しないコツ、品種の見分け方など、現場で得た知見をまとめています。これから始める方も、もっと深く知りたい方もどうぞ。</p>
      </section>

      <div class="guide-index-grid">{cards}</div>
    </div>
  </main>
{FOOTER}
</body>
</html>
'''
    with open(os.path.join(OUT_DIR, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(head + '\n' + body_html)
    print(f"  → guides/index.html ({len(guides_meta)} guides)")


if __name__ == '__main__':
    main()
