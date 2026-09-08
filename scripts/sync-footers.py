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
JSVER_RE = re.compile(r'((?:affiliate|status-auto|list-ui|nav|top-filter)\.js)(\?v=[0-9a-zA-Z]*)?')
# ヘッダーのロゴも正規化する。408ファイルに直書きされており手で直すと必ず乖離する。
LOGO_RE = re.compile(r'<a href="/" class="logo">.*?</a>', re.S)

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

        # AdSenseの撤去(2026-07-30 に利用を断念)。外部スクリプトを毎ページ読む無駄を消す。
        h2 = re.sub(r'[ \t]*<script async src="https://pagead2\.googlesyndication\.com[^\n]*\n', '', html)
        h2 = re.sub(r'[ \t]*<meta name="google-adsense-account"[^\n]*\n', '', h2)
        h2 = re.sub(r'[ \t]*<script src="[^"]*ads\.js[^"]*"></script>\n', '', h2)
        if h2 != html:
            html = h2
            reasons.append('adsense')

        # ヘッダーのロゴを正規化
        canon_logo = ('<a href="/" class="logo">'
                      '<span class="logo-en">AGA NAVI</span>'
                      '<span class="logo-jp">アガベイベントナビ</span></a>')
        new_html, n = LOGO_RE.subn(lambda _m: canon_logo, html)
        if n and new_html != html:
            html = new_html
            reasons.append('logo')

        # パンくず。sitelib.crumb_bar_html が唯一の組み立て。
        # 手書きのページは古い `<nav class="breadcrumb">` を直書きしていて、
        # 帯の見た目を .crumb-bar に移した瞬間に枠と余白が消えた
        # (2026-09-08。「取り残されてる」と言われた状態)。
        # 根っこの呼び名も「ホーム」のままで、トップの現在地「全国」と
        # 割れていた。ここで毎回作り直す。
        m_bc = re.search(r'([ \t]*)(?:<div class="crumb-bar">\s*)?'
                         r'<(nav|div) class="breadcrumb"[^>]*>(.*?)</\2>'
                         r'(?:\s*<form class="search-field".*?</form>)?'
                         r'(?:\s*</div>)?', html, re.S)
        if m_bc:
            inner = m_bc.group(3)
            items, saw_current = [], False
            for mm in re.finditer(
                    r'<a\s[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
                    r'|<span([^>]*)>(.*?)</span>', inner, re.S):
                if mm.group(1) is not None:
                    label = re.sub(r'<[^>]+>', '', mm.group(2)).strip()
                    href = mm.group(1)
                    if label in ('ホーム', '全国') or href in ('/', '/index.html'):
                        # ここが扱うのはサイトの案内頁だけ。
                        # イベント一覧の範囲(地域・県・タグ)ではないので、
                        # 根っこは「ホーム」。「全国」を置くと
                        # 全国一覧を絞った頁のように読める(2026-09-09 指摘)
                        items.append(sitelib.CRUMB_HOME)
                    elif label:
                        items.append((label, href))
                    continue
                # 区切りの span は項目ではない。ここを弾かないと、
                # 一度作り直したあとの再実行で「>」を項目として拾い、
                # 走らせるほど増える(2026-09-08 に about.html で発生)
                attrs = mm.group(3) or ''
                if 'pref-sep' in attrs or 'aria-hidden' in attrs:
                    continue
                label = re.sub(r'<[^>]+>', '', mm.group(4) or '').strip()
                if label:
                    items.append((label, None))
                    saw_current = True
            # 現在地を素のテキストで書いていたページがある
            # (ikitai / calendar / map)。最後のタグの後ろの文字を拾う。
            if items and not saw_current:
                tail = re.split(r'</(?:a|span)>', inner)[-1]
                tail = re.sub(r'<[^>]+>', '', tail)
                tail = tail.replace('&gt;', '').replace('>', '').strip()
                if tail:
                    items.append((tail, None))
            if items:
                want_bc = sitelib.crumb_bar_html(items)
                if m_bc.group(0).strip() != want_bc.strip():
                    html = html[:m_bc.start()] + want_bc + html[m_bc.end():]
                    reasons.append('breadcrumb')

        # ハンバーガーの開閉スクリプト。ヘッダーがあるページには必ず読ませる。
        # 手で足すと必ず抜ける。実際、注釈だけ入れてscriptタグを入れ忘れた
        # 状態で本番に出た(2026-09-08。注釈に nav.js の文字が入っていたので
        # 「もう入っている」と判定していた)。
        if 'class="header"' in html and 'src="/nav.js' not in html:
            tag = f'    <script src="/nav.js?v={sitelib.JS_VERSION}" defer></script>\n'
            if '</head>' in html:
                html = html.replace('</head>', tag + '</head>', 1)
                reasons.append('navjs')

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
            if [r for r in reasons if r != 'footer']:
                ver_changed += 1
            print(f'  synced({"+".join(reasons)}): {os.path.basename(fp)}')
    print(f'sync-footers: footer {changed}件 / 版数 {ver_changed}件 更新 '
          f'(CSS={sitelib.CSS_VERSION} JS={sitelib.JS_VERSION})')

if __name__ == '__main__':
    main()
