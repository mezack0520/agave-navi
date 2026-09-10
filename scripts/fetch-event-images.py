#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Instagram が唯一の出典の回について、告知画像を取得して自サイトに置く。

## なぜ要るか

2026-09-08 時点で、開催予定145件のうち116件にアイキャッチが無く、
**そのうち88件は Instagram が唯一の出典**だった。
backfill-images.py は `static.cdninstagram.com` を除外しており、
Instagram 出典の回は構造的にアイキャッチが付かない状態だった。

除外そのものは正しい。Instagram の画像URLは署名付きで期限があり、
リファラも見られる。**ホットリンクしても遠からず壊れる。**

そこで、URLを指すのではなく**画像を取得して自サイトに置く**。
期限切れもホットリンク遮断も起きなくなる。

## 置き方

    images/events/<slug>.jpg     長辺800pxまで縮小・JPEG品質82
    imageUrl = https://agave-navi.com/images/events/<slug>.jpg
    imageSource = 取得元の投稿URL（出所の記録）

長辺800pxはカードの表示が640x360で、2倍解像度の端末を考えた上限。
原寸を置くとリポジトリが膨らむだけで画質は見えない。

## どこで走らせるか

**GitHub Actions からは走らない。**2026-09-08 の実測で、Actions のIPからは
instagram.com が応答せず30件すべてタイムアウトし、取得は0件だった
(同じ回で backfill-images は非IGの4件を取れている)。Coworkのサンドボックスも
403 で届かない。**届くのは組み込みブラウザだけ。**
ブラウザを持つセッションから実行するか、ブラウザで取得した画像を
images/events/ に置いてから events.json を更新する。

## 使い方

    python3 scripts/fetch-event-images.py --limit 20
    python3 scripts/fetch-event-images.py --slug foo-2026
    python3 scripts/fetch-event-images.py --dry-run
    python3 scripts/fetch-event-images.py --self-test   # 通信なし
"""
import argparse
import io as _io
import json
import os
import re
import sys
import time

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import sitelib
from sitelib import today_jst, is_cancelled, event_span   # noqa: E402

EVENTS_JSON = os.path.join(REPO, 'events.json')
IMG_DIR = os.path.join(REPO, 'images', 'events')
SITE = 'https://agave-navi.com'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
MAX_EDGE = 800
JPEG_QUALITY = 82
# 1枚あたりの上限。これを超えるものは縮小しても大きすぎるので採らない
MAX_BYTES = 400 * 1024



def ig_post_url(ev):
    """この回の Instagram 投稿URL。プロフィールURLは対象外。

    プロフィールの og:image はアイコンなので、アイキャッチにならない。
    """
    for key in ('instagramUrl', 'url', 'sourceUrl'):
        v = (ev.get(key) or '').strip()
        m = sitelib.IG_POST_RE.match(v)
        if m:
            return m.group(0)
    pid = (ev.get('instagramPostId') or '').strip()
    if pid:
        return f'https://www.instagram.com/p/{pid}/'
    return ''


# **このスクリプトの og:image 経路は使わない(2026-09-08)。**
# og:image のURLには stp=c180.0.540.540a_... のような切り出し指定が入っており、
# 元が 1080x1350 の縦長フライヤーでも 540x540 に切られてタイトルが落ちる。
# 実際に74件をこれで保存して半分近くを見切れさせた。
# 切り出しの無い画像は投稿ページのDOMにしか出ないので、
# scripts/browser/ig-eyecatch.js（組み込みブラウザから実行）を使う。
# ここは og:image しか見られないため、実質的に使えない。
def og_image_or_blank(html):
    """sitelib の抽出に「無ければ空文字」の約束だけ被せる薄い包み。

    判定そのものは持たない。sitelib と同じ名前にすると、
    写しなのか包みなのかが名前から分からなくなる。
    """
    return sitelib.extract_og_image(html) or ''


def targets(events, today, slug=None):
    out = []
    for e in events:
        if slug and e.get('slug') != slug:
            continue
        if e.get('imageUrl'):
            continue
        if is_cancelled(e):
            continue
        d, de = event_span(e)
        if not d or (de or d) < today:
            continue
        post = ig_post_url(e)
        if post:
            out.append((e, post))
    return out


def _edge_color(im):
    """余白に敷く色。長辺側のふちの平均を採る。

    白で埋めると濃い地のフライヤーで枠が浮く。ふちの色を拾えば、
    単色の余白があるフライヤーではそのまま繋がって見える。
    """
    from PIL import ImageStat
    w, h = im.size
    if h > w:
        band = max(1, w // 12)
        a, b = im.crop((0, 0, band, h)), im.crop((w - band, 0, w, h))
    else:
        band = max(1, h // 12)
        a, b = im.crop((0, 0, w, band)), im.crop((0, h - band, w, h))
    m = [ImageStat.Stat(x).mean for x in (a, b)]
    return tuple(int(round((m[0][i] + m[1][i]) / 2)) for i in range(3))


def save_image(raw, dest):
    """縮小し、**正方形にパディングして**JPEGで保存する。

    カードのサムネは 1:1(style.css の .event-thumb)。
    Instagram の告知フライヤーはほぼ正方形なので大半はそのまま収まるが、
    ストーリー比(9:16)の告知も混ざる。1:1 で cover すると左右が44%落ちて
    タイトルが消えるので、切るのではなく余白を足して正方形にする。
    切ると情報が減る。余白は減らない。

    戻り値は (幅, 高さ, バイト数)
    """
    from PIL import Image
    im = Image.open(_io.BytesIO(raw)).convert('RGB')
    w, h = im.size
    if max(w, h) > MAX_EDGE:
        if w >= h:
            im = im.resize((MAX_EDGE, round(h * MAX_EDGE / w)), Image.LANCZOS)
        else:
            im = im.resize((round(w * MAX_EDGE / h), MAX_EDGE), Image.LANCZOS)
    w, h = im.size
    if w != h:
        n = max(w, h)
        canvas = Image.new('RGB', (n, n), _edge_color(im))
        canvas.paste(im, ((n - w) // 2, (n - h) // 2))
        im = canvas
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    im.save(dest, 'JPEG', quality=JPEG_QUALITY, optimize=True)
    return im.size[0], im.size[1], os.path.getsize(dest)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug')
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--sleep', type=float, default=1.2)
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    import requests

    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    today = today_jst()
    tg = targets(events, today, args.slug)
    if args.limit:
        tg = tg[:args.limit]
    print(f'対象 {len(tg)} 件')

    ok = fail = 0
    for ev, post in tg:
        slug = ev['slug']
        try:
            r = requests.get(post, headers={'User-Agent': UA,
                                            'Accept-Language': 'ja'}, timeout=20)
            if r.status_code != 200:
                print(f'  ✗ {slug}: 投稿ページ HTTP {r.status_code}')
                fail += 1
                continue
            src = og_image_or_blank(r.text)
            if not src:
                print(f'  ✗ {slug}: og:image が取れない')
                fail += 1
                continue
            ir = requests.get(src, headers={'User-Agent': UA}, timeout=25)
            if ir.status_code != 200 or not ir.content:
                print(f'  ✗ {slug}: 画像 HTTP {ir.status_code}')
                fail += 1
                continue
            if args.dry_run:
                print(f'  (dry) {slug}: {len(ir.content)}バイト ← {src[:60]}')
                ok += 1
                continue
            dest = os.path.join(IMG_DIR, f'{slug}.jpg')
            w, h, size = save_image(ir.content, dest)
            if size > MAX_BYTES:
                os.remove(dest)
                print(f'  ✗ {slug}: 縮小後も {size}バイトで大きすぎる')
                fail += 1
                continue
            ev['imageUrl'] = f'{SITE}/images/events/{slug}.jpg'
            ev['imageSource'] = post
            ev['updatedAt'] = today
            print(f'  ✓ {slug}: {w}x{h} {size//1024}KB')
            ok += 1
        except Exception as err:                      # noqa: BLE001
            print(f'  ✗ {slug}: {type(err).__name__} {err}')
            fail += 1
        time.sleep(args.sleep)

    if not args.dry_run and ok:
        with open(EVENTS_JSON, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
            f.write('\n')
    print(f'取得 {ok} 件 / 失敗 {fail} 件')
    return 0


# ---------------------------------------------------------------- self-test
def self_test():
    ok = True

    def chk(label, got, want):
        nonlocal ok
        mark = 'OK ' if got == want else '★NG'
        if got != want:
            ok = False
        print(f'  {mark} {label}: {got!r} 期待={want!r}')

    print('--- 投稿URLの判定 ---')
    chk('投稿URLを拾う',
        ig_post_url({'url': 'https://www.instagram.com/p/DcYbxwJhQnG/'}),
        'https://www.instagram.com/p/DcYbxwJhQnG')
    chk('reelも拾う',
        ig_post_url({'sourceUrl': 'https://www.instagram.com/reel/DcalRTLSAQE/'}),
        'https://www.instagram.com/reel/DcalRTLSAQE')
    chk('プロフィールURLは対象外（og:imageがアイコンになる）',
        ig_post_url({'url': 'https://www.instagram.com/kyoshoku_sai/'}), '')
    chk('instagramPostId からも作れる',
        ig_post_url({'instagramPostId': 'ABC123'}),
        'https://www.instagram.com/p/ABC123/')
    chk('IG以外は対象外',
        ig_post_url({'url': 'https://collect-plants.com/'}), '')

    print('\n--- og:image の抽出 ---')
    chk('property が先',
        og_image_or_blank('<meta property="og:image" content="https://x/a.jpg">'),
        'https://x/a.jpg')
    chk('content が先でも取れる',
        og_image_or_blank('<meta content="https://x/b.jpg" property="og:image">'),
        'https://x/b.jpg')
    chk('&amp; を戻す',
        og_image_or_blank('<meta property="og:image" content="https://x/c.jpg?a=1&amp;b=2">'),
        'https://x/c.jpg?a=1&b=2')
    chk('相対パスは採らない',
        og_image_or_blank('<meta property="og:image" content="/a.jpg">'), '')
    chk('無ければ空', og_image_or_blank('<html></html>'), '')

    print('\n--- 対象の絞り込み ---')
    today = '2026-09-08'
    evs = [
        {'slug': 'ig-none', 'date': '2026-09-22',
         'url': 'https://www.instagram.com/p/AAA/'},
        {'slug': 'ig-has-img', 'date': '2026-09-22', 'imageUrl': 'https://x/a.jpg',
         'url': 'https://www.instagram.com/p/BBB/'},
        {'slug': 'ig-past', 'date': '2026-09-01',
         'url': 'https://www.instagram.com/p/CCC/'},
        {'slug': 'ig-cancelled', 'date': '2026-09-22', 'eventStatus': 'cancelled',
         'url': 'https://www.instagram.com/p/DDD/'},
        {'slug': 'web', 'date': '2026-09-22', 'url': 'https://example.com/'},
    ]
    chk('画像なし・未終了・未中止・IG投稿の回だけ',
        sorted(e['slug'] for e, _ in targets(evs, today)), ['ig-none'])

    print('\n結果: ' + ('すべて通過' if ok else '★失敗あり'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
