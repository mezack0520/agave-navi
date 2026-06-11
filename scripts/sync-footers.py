#!/usr/bin/env python3
"""sync-footers.py — ルート直下の静的HTML(404.html含む)のフッターを
sitelib.site_footer() の正規版に同期する。フッター乖離(過去の404バグ)の再発防止。
冪等。<footer class="footer">...</footer> ブロックを置換するだけで他は触らない。
"""
import os, re, glob, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 生成物(events/guides/landing)はジェネレータ側がsitelibを使うため対象外。
TARGETS = [f for f in glob.glob(os.path.join(REPO_ROOT, '*.html'))
           if not os.path.basename(f).startswith('google')]

FOOTER_RE = re.compile(r'[ \t]*<footer class="footer">.*?</footer>', re.S)

def main():
    canonical = sitelib.site_footer().rstrip('\n')
    changed = 0
    for fp in sorted(TARGETS):
        html = open(fp, encoding='utf-8').read()
        m = FOOTER_RE.search(html)
        if not m:
            print(f'  skip(no footer): {os.path.basename(fp)}')
            continue
        if m.group(0) == canonical:
            continue
        html = html[:m.start()] + canonical + html[m.end():]
        open(fp, 'w', encoding='utf-8').write(html)
        changed += 1
        print(f'  synced: {os.path.basename(fp)}')
    print(f'sync-footers: {changed} files updated')

if __name__ == '__main__':
    main()
