#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""サイトとSNSのアイコン一式を1つの定義から生成する。

手で走らせるスクリプト。build-all.sh には入れない。アイコンはビルドの
たびに変わるものではないし、cairosvg を CI の依存に足すとビルド全体が
壊れる面が増えるだけ。形を変えたいときだけ実行して成果物をコミットする。

    pip install cairosvg pillow fonttools --break-system-packages
    python3 scripts/build-icons.py

## なぜワードマークなのか

旧 favicon.svg は 512 の座標系で線幅 5〜8px のアガベを線画で描いていた。
16px に縮むと 0.25px 相当になって完全に消え、タブでは黒い角丸にしか
見えなかった。文字は "AEN" で、これも 16px では 1.5px 相当で読めず、
しかも旧ブランド名のまま残っていた。

作り直しにあたりアガベの図案を7通り試したが、中心から葉を放射させる
図形はどう調整しても記号として成立しなかった。葉を太くしても細くしても
星、横向きにすると蓮、鋸歯を足すと大麻の葉に見える。IGのアイコンとして
出せる水準に届かなかったので、造形は捨てて文字で組んだ。
植物らしさは投稿画像が担う。アイコンは「何のアカウントか」を言う役にする。

## サイズごとの出し分け

- 大きく出る面(IG 110px / ホーム画面 / apple-touch)は "AGA NAVI" の2段組み
- favicon の 16px では2段組みは潰れて読めない。実測して唯一読めた
  頭文字 "A" の1文字を置く。書体・色は同じなので家系は保たれる
- 文字はすべてパスに変換して埋め込む。閲覧側に Poppins が無くても崩れない
  (このスクリプトを走らせるときだけフォントが要る)

## 角丸の使い分け

- ブラウザ用(svg/ico/png)は角丸。タブの地色に対して輪郭が立つ
- apple-touch / android-chrome は角丸なし。OS 側がマスクするので、
  こちらで丸めると二重に丸まって縁が汚れる
- maskable は Android の安全域(中心80%の円)に収まるまで図案を縮めた別版
"""
import io
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT = '/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf'

INK = '#12302a'    # 地。深緑。旧地色 #16181a は Chrome のダークタブに沈んだ
CREAM = '#f5f2e9'  # 文字
CORNER = 112       # 角丸(512基準)


def text_paths(text, size, tracking, cx, baseline, fill):
    """文字列をSVGパスに落とす。閲覧側のフォントに依存させないため。"""
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.ttLib import TTFont
    f = TTFont(FONT)
    gs, cmap = f.getGlyphSet(), f.getBestCmap()
    upem, hmtx = f['head'].unitsPerEm, f['hmtx']
    sc = size / upem
    adv = []
    for ch in text:
        g = cmap.get(ord(ch))
        adv.append((g, hmtx[g][0] * sc if g else size * 0.32))
    total = sum(a for _, a in adv) + tracking * (len(text) - 1)
    x = cx - total / 2
    out = []
    for g, a in adv:
        if g and g != 'space':
            pen = SVGPathPen(gs)
            gs[g].draw(pen)
            cmds = pen.getCommands()
            if cmds:
                out.append(
                    f'<path d="{cmds}" fill="{fill}" '
                    f'transform="translate({x:.1f},{baseline:.1f}) '
                    f'scale({sc:.5f},{-sc:.5f})"/>')
        x += a + tracking
    return '\n  '.join(out)


def svg(inner, corner):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'
            f'  <rect width="512" height="512" rx="{corner}" fill="{INK}"/>\n'
            f'  {inner}\n</svg>\n')


def wordmark(corner, scale=1.0):
    """AGA / NAVI の2段組み。scale<1 は maskable の安全域用。"""
    s = scale
    return svg(text_paths('AGA', 132 * s, 6 * s, 256, 256 - 24 * s, CREAM) + '\n  ' +
               text_paths('NAVI', 132 * s, 6 * s, 256, 256 + 112 * s, CREAM), corner)


def monogram(corner):
    """16px で読める唯一の版。AN / AGA は実測で潰れた。"""
    return svg(text_paths('A', 390, 0, 256, 392, CREAM), corner)


def write_ico(path, svg_text, sizes=(16, 32, 48)):
    """各サイズを個別にラスタライズして詰める。

    Pillow の ICO 保存は1枚を渡すと内部で縮小するだけで、いちばんよく
    見られる 16px が眠くなる。ICO は PNG を並べただけの器なので自前で組む。
    """
    import cairosvg
    entries = []
    for s in sizes:
        buf = io.BytesIO()
        cairosvg.svg2png(bytestring=svg_text.encode('utf-8'), write_to=buf,
                         output_width=s, output_height=s)
        entries.append((s, buf.getvalue()))
    header = struct.pack('<HHH', 0, 1, len(entries))
    offset = len(header) + 16 * len(entries)
    dirs, blobs = b'', b''
    for s, data in entries:
        dirs += struct.pack('<BBBBHHII', s, s, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    with open(path, 'wb') as f:
        f.write(header + dirs + blobs)


def main():
    try:
        import cairosvg
    except ImportError:
        sys.exit('cairosvg / pillow / fonttools が要る: '
                 'pip install cairosvg pillow fonttools --break-system-packages')
    if not os.path.exists(FONT):
        sys.exit(f'フォントが無い: {FONT}')

    mono_round = monogram(CORNER)
    word_round = wordmark(CORNER)
    word_square = wordmark(0)
    word_mask = wordmark(0, scale=0.72)

    with open(os.path.join(ROOT, 'favicon.svg'), 'w', encoding='utf-8') as f:
        f.write(mono_round)
    print('favicon.svg (頭文字A)')

    def png(text, name, size):
        cairosvg.svg2png(bytestring=text.encode('utf-8'),
                         write_to=os.path.join(ROOT, name),
                         output_width=size, output_height=size)
        print(f'{name} ({size}px)')

    png(mono_round, 'favicon-32x32.png', 32)
    png(word_square, 'apple-touch-icon.png', 180)
    png(word_square, 'android-chrome-192x192.png', 192)
    png(word_square, 'android-chrome-512x512.png', 512)
    png(word_mask, 'android-chrome-maskable-512x512.png', 512)
    # SNSのアイコン用。サイトからは参照しない
    png(word_square, 'images/social-avatar-1024.png', 1024)
    # 角丸版も置いておく(OGP等で単体表示するとき用)
    png(word_round, 'images/logo-mark-512.png', 512)

    write_ico(os.path.join(ROOT, 'favicon.ico'), mono_round)
    print('favicon.ico (16/32/48 個別ラスタライズ)')

    if subprocess.call(['which', 'optipng'], stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL) == 0:
        for n in ('favicon-32x32.png', 'apple-touch-icon.png',
                  'android-chrome-192x192.png', 'android-chrome-512x512.png',
                  'android-chrome-maskable-512x512.png',
                  'images/social-avatar-1024.png', 'images/logo-mark-512.png'):
            subprocess.call(['optipng', '-quiet', '-o2', os.path.join(ROOT, n)])
        print('optipng: done')


if __name__ == '__main__':
    main()
