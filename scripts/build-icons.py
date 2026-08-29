#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""サイトアイコン一式を1つの定義から生成する。

手で走らせるスクリプト。build-all.sh には入れない。
アイコンはビルドのたびに変わるものではないし、cairosvg を CI の
依存に足すとビルド全体が壊れる面が増えるだけなので、
形を変えたいときだけローカルで実行して成果物をコミットする。

    pip install cairosvg pillow --break-system-packages
    python3 scripts/build-icons.py

設計の要点(2026-08-29に旧アイコンを捨てた理由):
- 旧 favicon.svg は 512 の座標系で線幅 5〜8px だった。16px に縮むと
  0.25px 相当になって完全に消え、タブでは真っ黒の角丸にしか見えなかった。
  → 線ではなく塗りのシルエットで作る。
- 旧アイコンの "AEN" は 16px で 1.5px 相当。読めないうえ旧ブランド名。
  → 文字を入れない。
- 旧アイコンの地色 #16181a は Chrome のダークタブ(#35363a 付近)に沈む。
  → 地色は深緑 #14312a。明タブ・暗タブのどちらでも輪郭が出る。
- 葉は 7 枚。8 枚だと左右対称が強すぎて「きらめき」や方位磁針の記号に
  見える。奇数にすると上に 1 枚立って植物側に寄る。
- 中心の赤は --accent-pop と同じ #e63946。16px でも 1.3px 相当が残る
  よう r=42 まで大きくしてある。ここを小さくすると消える。

角丸(rx)の使い分け:
- ブラウザ用(svg/ico/png)は角丸。タブの地色に対して輪郭が立つ。
- apple-touch / android-chrome は角丸なし。OS 側が自前でマスクするので、
  こちらで丸めると二重に丸まって縁が汚れる。
- maskable は Android の安全域(中心 80% の円)に収まるまで縮めた別版。
"""
import io
import math
import os
import struct
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

INK = '#14312a'    # 地。深緑
CREAM = '#f4f1e8'  # 葉
RED = '#e63946'    # 中心。style.css の --accent-pop と同じ

LEAVES = 7
LENGTH = 236       # 中心から葉先まで(512 の座標系)
HALF_W = 76        # 付け根の半幅
WAIST = 0.92       # 中ほどの膨らみ。1.0 に近いほど太い
DOT_R = 42         # 中心の赤の半径
CORNER = 112       # 角丸


def leaf(cx, cy, deg, length, half_w, waist, tip=0.10):
    """中心から放射する葉 1 枚を塗りパスで返す。"""
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)

    def P(fwd, side):
        return (cx + fwd * ca - side * sa, cy + fwd * sa + side * ca)

    bl, br = P(0, -half_w), P(0, half_w)
    ml, mr = P(length * 0.5, -half_w * waist), P(length * 0.5, half_w * waist)
    tl, tr = P(length * 0.9, -half_w * tip), P(length * 0.9, half_w * tip)
    ap = P(length, 0)
    return (f'M{bl[0]:.1f},{bl[1]:.1f} '
            f'C{ml[0]:.1f},{ml[1]:.1f} {tl[0]:.1f},{tl[1]:.1f} {ap[0]:.1f},{ap[1]:.1f} '
            f'C{tr[0]:.1f},{tr[1]:.1f} {mr[0]:.1f},{mr[1]:.1f} {br[0]:.1f},{br[1]:.1f} Z')


def build_svg(corner=CORNER, scale=1.0):
    """scale<1 で図案だけ縮める。maskable の安全域用。"""
    length = LENGTH * scale
    half_w = HALF_W * scale
    dot_r = DOT_R * scale
    paths = '\n    '.join(
        f'<path d="{leaf(256, 256, -90 + 360.0 * i / LEAVES, length, half_w, WAIST)}" fill="{CREAM}"/>'
        for i in range(LEAVES))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">\n'
            f'  <rect width="512" height="512" rx="{corner}" fill="{INK}"/>\n'
            f'  <g>\n    {paths}\n  </g>\n'
            f'  <circle cx="256" cy="256" r="{dot_r:.0f}" fill="{RED}"/>\n'
            f'</svg>\n')


def main():
    try:
        import cairosvg
    except ImportError:
        sys.exit('cairosvg と pillow が要る: '
                 'pip install cairosvg pillow --break-system-packages')

    rounded = build_svg(corner=CORNER)
    square = build_svg(corner=0)
    # Android の maskable は中心 80% の円しか保証されない。
    # 角丸なしの正方形に、図案だけ 0.72 倍で置く。
    maskable = build_svg(corner=0, scale=0.72)

    svg_path = os.path.join(ROOT, 'favicon.svg')
    with open(svg_path, 'w', encoding='utf-8') as f:
        f.write(rounded)
    print('favicon.svg')

    def png(svg_text, name, size):
        out = os.path.join(ROOT, name)
        cairosvg.svg2png(bytestring=svg_text.encode('utf-8'), write_to=out,
                         output_width=size, output_height=size)
        print(f'{name} ({size}px)')

    png(rounded, 'favicon-32x32.png', 32)
    png(square, 'apple-touch-icon.png', 180)
    png(square, 'android-chrome-192x192.png', 192)
    png(square, 'android-chrome-512x512.png', 512)
    png(maskable, 'android-chrome-maskable-512x512.png', 512)

    # .ico は 16/32/48 の 3 枚入り。Pillow の ICO 保存は 1 枚を渡すと
    # 内部で縮小するだけなので、16px が眠くなる。実際に見られるのは
    # ほぼ 16px なので、各サイズを個別にラスタライズして自前で詰める。
    # ICO は「PNG を並べただけ」の器なので難しいことはしていない。
    entries = []
    for s in (16, 32, 48):
        buf = io.BytesIO()
        cairosvg.svg2png(bytestring=rounded.encode('utf-8'), write_to=buf,
                         output_width=s, output_height=s)
        entries.append((s, buf.getvalue()))
    header = struct.pack('<HHH', 0, 1, len(entries))
    offset = len(header) + 16 * len(entries)
    dirs, blobs = b'', b''
    for s, data in entries:
        dirs += struct.pack('<BBBBHHII', s, s, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    with open(os.path.join(ROOT, 'favicon.ico'), 'wb') as f:
        f.write(header + dirs + blobs)
    print('favicon.ico (16/32/48 個別)')

    if subprocess.call(['which', 'optipng'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        for n in ('favicon-32x32.png', 'apple-touch-icon.png',
                  'android-chrome-192x192.png', 'android-chrome-512x512.png',
                  'android-chrome-maskable-512x512.png'):
            subprocess.call(['optipng', '-quiet', '-o2', os.path.join(ROOT, n)])
        print('optipng: done')


if __name__ == '__main__':
    main()
