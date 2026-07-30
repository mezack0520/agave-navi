#!/usr/bin/env python3
"""sync-footers.py — ルート直下の静的HTML(404.html含む)を sitelib の正規値に同期する。
  1. フッターを sitelib.site_footer() に合わせる(フッター乖離=過去の404バグの再発防止)
  2. style.css の版数を sitelib.CSS_VERSION に合わせる

版数同期の理由(2026-07-30): 手書きの静的ページは版数がジェネレータに追随せず、
index.html だけ 20260504d のまま等の乖離が起きていた。版数が古いままだと
CSSを直しても閲覧者のキャッシュが更新されず、壊れたCSSが残り続ける。
冪等。該当箇所を置換するだけで他は触らない。
"""
import os, re, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 生成物(events/guides/landing)はジェネレータ側がsitelibを使うため対象外。
TARGETS = [f for f in glob.glob(os.path.join(REPO_ROOT, '*.html'))
           if not os.path.basename(f).startswith('google')]

FOOTER_RE = re.compile(r'[ \t]*<footer class="footer">.*?</footer>', re.S)
CSSVER_RE = re.compile(r'(style\.css)(\?v=[0-9a-zA-Z]*)?')
# ローカルJSも版数を付ける。付いていないと変更が閲覧者のキャッシュに届かない。
JSVER_RE = re.compile(r'((?:affiliate|ads|status-auto)\.js)(\?v=[0-9a-zA-Z]*)?')

def main():
    canonical = sitelib.site_footer().rstrip('\n')
    want_ver = f'?v={sitelib.CSS_VERSION}'
    changed = 0
    ver_changed = 0
    for fp in sorted(TARGETS):
        html = open(fp, encoding='utf-8').read()
        orig = html
        reasons = []

        m = FOOTER_RE.search(html)
        if m is None:
            print(f'  skip(no footer): {os.path.basename(fp)}')
        elif m.group(0) != canonical:
            html = html[:m.start()] + canonical + html[m.end():]
            reasons.append('footer')

        # CSS版数を正規化(版数なしの参照にも付ける)
        new_html, n = CSSVER_RE.subn(lambda mo: mo.group(1) + want_ver, html)
        if n and new_html != html:
            html = new_html
            reasons.append('cssver')

        # JS版数を正規化
        want_js = f'?v={sitelib.JS_VERSION}'
        new_html, n = JSVER_RE.subn(lambda mo: mo.group(1) + want_js, html)
        if n and new_html != html:
            html = new_html
            reasons.append('jsver')

        if html != orig:
            open(fp, 'w', encoding='utf-8').write(html)
            if 'footer' in reasons:
                changed += 1
            if 'cssver' in reasons or 'jsver' in reasons:
                ver_changed += 1
            print(f'  synced({"+".join(reasons)}): {os.path.basename(fp)}')
    print(f'sync-footers: footer {changed}件 / 版数 {ver_changed}件 更新 '
          f'(CSS={sitelib.CSS_VERSION} JS={sitelib.JS_VERSION})')

if __name__ == '__main__':
    main()
