#!/usr/bin/env python3
"""build-css.py — style.src.css から配信用の style.css を作る(2026-11-09)。

直すのは style.src.css。style.css は生成物で、コメントを落としただけのもの。
CSS のコメントには「なぜこう書いたか」が書いてあり、直す人には要るが、閲覧者には
要らない。コメントが gzip で 24KB のうち 11KB を占め、全ページで描画を止める
CSS の転送の半分になっていた。規則・並び・空白はそのまま残すので、見た目は変わらない。

    python3 scripts/build-css.py           # style.css を書く
    python3 scripts/build-css.py --check   # 生成結果と食い違えば 1 で終わる(audit.css_source_drift も同じ判定)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'style.src.css')
OUT = os.path.join(ROOT, 'style.css')
HEADER = '/* 生成物。直すのは style.src.css(scripts/build-css.py が作る) */\n'


def strip_comments(css):
    """コメントを落とす。文字列の中の /* は落とさない"""
    out, i, n = [], 0, len(css)
    while i < n:
        ch = css[i]
        if ch in '"\'':
            j = i + 1
            while j < n and css[j] != ch:
                j += 2 if css[j] == '\\' else 1
            out.append(css[i:j + 1])
            i = j + 1
        elif css.startswith('/*', i):
            e = css.find('*/', i + 2)
            i = n if e < 0 else e + 2
        else:
            out.append(ch)
            i += 1
    text = ''.join(out)
    text = re.sub(r'[ \t]+\n', '\n', text)          # コメントを落とした行末の空白
    text = re.sub(r'\n{3,}', '\n\n', text)           # 続いた空行は1つにする
    return text.lstrip('\n')


def build_css():
    with open(SRC, encoding='utf-8') as f:
        return HEADER + strip_comments(f.read())


def main():
    want = build_css()
    try:
        have = open(OUT, encoding='utf-8').read()
    except OSError:
        have = None
    if '--check' in sys.argv[1:]:
        if have != want:
            print('style.css が style.src.css から作ったものと違う。style.css を直接直していないか', file=sys.stderr)
            return 1
        return 0
    if have != want:
        with open(OUT, 'w', encoding='utf-8') as f:
            f.write(want)
        print(f'build-css: style.css を書いた({len(want.encode()):,} バイト)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
