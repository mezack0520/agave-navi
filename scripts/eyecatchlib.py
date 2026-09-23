#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""アイキャッチの候補選びと保存。CI(ig-organizer-watch.py)と apply-eyecatch.py が使う。

## なぜ CI で候補を作るのか (2026-09-23)

アイキャッチ取得はブラウザ専用だった。GitHub Actions からも Cowork の
サンドボックスからも instagram.com に届かないためで、毎日14:50の
agave-navi-eyecatch タスクが組み込みブラウザで1件ずつ投稿を開いていた。

Business Discovery(Graph API)は主催がプロアカウントなら最新投稿の
media_url を返す。**これは切り出しの無い原寸**で、og:image の
`stp=c180.0.540.540a` 問題(ig-eyecatch.js 冒頭)が起きない。
主催者の見張り(ig-organizer-watch.py)が毎日同じ呼び出しで投稿を取っているので、
**API呼び出しを1回も増やさずに**候補が作れる。

## 採否は人が決める

照合の点数は候補を絞る道具で、採否の根拠にならない(2026-09-08 に機械判定の
12件が誤り。出店者募集・出店者紹介・御礼の集合写真・暑中見舞い)。
だから CI は **staging/eyecatch/ に置くだけで events.json は触らない。**
人(またはタスク)が画像を1枚ずつ見て apply-eyecatch.py で採否を書く。

## 置き方(採用後)

    images/events/<slug>.jpg     長辺800pxまで縮小・正方形に余白・JPEG品質82
    imageUrl = https://agave-navi.com/images/events/<slug>.jpg
    imageSource = 取得元の投稿URL
"""
import io as _io
import json
import os
import re
import unicodedata
import urllib.request
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://agave-navi.com'
IMG_DIR = os.path.join(REPO, 'images', 'events')
STAGE_DIR = os.path.join(REPO, 'staging', 'eyecatch')
STAGE_JSON = os.path.join(STAGE_DIR, 'candidates.json')
REJECTED_JSON = os.path.join(REPO, 'scripts', 'eyecatch-rejected.json')

MAX_EDGE = 800
JPEG_QUALITY = 82
MAX_BYTES = 400 * 1024
# 同時に置いておく候補の上限。見る人の手に余る数を積まない
MAX_PENDING = 12

# 照合の役に立たない共通語(ig-eyecatch.js の GENERIC と同じ考え)
_GENERIC = {'vol', '2026', '2027', 'the', 'and', 'plants', 'plant', 'popup', 'pop',
            'market', 'fes', 'show', 'shop', 'store', '開催', '販売', '即売', '即売会',
            'マルシェ', 'フェス', 'フェスタ', 'イベント', '会場', '出店', '植物',
            'botanical', 'green', 'garden', 'festa', 'ボタニカル', 'グリーン', 'ガーデン'}
# 来場者向けの告知ではない投稿。点数が高くても採らない
_NOT_FLYER = ('出店者募集', '出展者募集', '出店者様募集', '出店者紹介', '出店者様紹介',
              '出展者紹介', '出店者さま', '出店者様発表', '出店者発表', 'ご来場ありがとう', 'ありがとうございました', '御礼',
              '暑中見舞い', '残暑見舞い', '中止', '延期', '会場図', '配置図',
              'イベント終了', '無事終了', '終了しました', '募集終了', 'オンラインショップ')
# 告知が開催のどれだけ前から出るか。これより古い投稿は前の回の話
MAX_LEAD_DAYS = 150
# 本文の日付。「10/3」「10月3日」「2026.10.3」
_CAP_DATE = re.compile(r'(?<![\d.])(?:20\d\d[./年])?(\d{1,2})\s*(?:月\s*(\d{1,2})\s*日?|[/.](\d{1,2}))(?![\d])')


def _n(s):
    return unicodedata.normalize('NFKC', s or '').lower()


def tokens(name):
    n = re.sub(r'[（）()【】\[\]・,、.。!！?？~〜_/&\-]', ' ', _n(name))
    raw = re.findall(r'[぀-ヿ]{2,}|[一-鿿]{2,}|[a-z0-9]{3,}', n)
    return sorted({t for t in raw if t not in _GENERIC and not t.isdigit()})


def date_hits(cap_n, ev):
    out = []
    for k in ('date', 'dateEnd'):
        v = ev.get(k) or ''
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
            continue
        mo, d = int(v[5:7]), int(v[8:10])
        for s in (f'{mo}月{d}日', f'{mo}/{d}'):
            if s in cap_n and s not in out:
                out.append(s)
    return out


def post_code(url):
    m = re.search(r'instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url or '')
    return m.group(1) if m else ''


def pick_post(ev, posts, rejected_posts=()):
    """この回の告知投稿を選ぶ。(post, 根拠dict) か (None, None)。

    出典が投稿URLなら、その投稿が最近の投稿に入っていればそれを採る。
    それ以外はキャプションで照合し、名前の特徴語と開催日の両方、または
    4文字以上を含む特徴語2つ以上が出る投稿だけを採る。適当な最新投稿は貼らない。
    """
    rejected = {post_code(p) for p in rejected_posts}
    want_code = ''
    for k in ('instagramUrl', 'url', 'sourceUrl'):
        want_code = post_code(ev.get(k))
        if want_code:
            break
    want_code = want_code or (ev.get('instagramPostId') or '').strip()
    usable = [p for p in posts if p.get('image') and post_code(p.get('permalink')) not in rejected]
    # 出典の投稿でも、募集終了のお知らせや店の連絡であることがある(2026-09-23 の試走で
    # アメプラの「出展者募集終了」と toky の「オンラインショップ移転」を拾った)
    usable = [p for p in usable if not any(w in _n(p.get('caption')) for w in _NOT_FLYER)]
    if want_code:
        for p in usable:
            if post_code(p.get('permalink')) == want_code:
                return p, {'by': 'sourcePost'}
    want = tokens(ev.get('name'))
    start = ev.get('date') or ''
    end = ev.get('dateEnd') or start
    ev_md = set()
    try:
        a = datetime.strptime(start, '%Y-%m-%d')
        b = datetime.strptime(end, '%Y-%m-%d')
        while a <= b and len(ev_md) < 70:
            ev_md.add((a.month, a.day))
            a += timedelta(days=1)
        oldest = (datetime.strptime(start, '%Y-%m-%d')
                  - timedelta(days=MAX_LEAD_DAYS)).strftime('%Y-%m-%d')
    except ValueError:
        oldest = ''
    best = None
    for p in usable:
        cap = _n(p.get('caption'))
        if not cap:
            continue
        posted = (p.get('timestamp') or '')[:10]
        if end and posted > end:
            continue  # 会期の後の投稿は御礼か次回の話
        if oldest and posted < oldest:
            continue  # 前の回の告知
        # 本文に日付があって、この回の会期のどの日とも合わないなら別の回の話
        # (botanical botanical の沖縄の回に福岡の回の告知を当てかけた)
        cap_md = {(int(m.group(1)), int(m.group(2) or m.group(3)))
                  for m in _CAP_DATE.finditer(cap)}
        cap_md = {x for x in cap_md if 1 <= x[0] <= 12 and 1 <= x[1] <= 31}
        if cap_md and ev_md and not (cap_md & ev_md):
            continue
        nh = [w for w in want if w in cap]
        dh = date_hits(cap, ev)
        long_hit = any(len(w) >= 4 for w in nh)
        # 名前と日付の両方か、日付が無くても名前の特徴語が2つ以上。
        # 特徴語1つだけは別の回・スナップ投稿に当たる(botanical 1語で青山のスナップを拾った)
        if not ((nh and dh) or (long_hit and len(nh) >= 2)):
            continue
        score = len(nh) * 2 + len(dh) * 2 + (2 if long_hit else 0)
        if best is None or score > best[1]['score']:
            best = (p, {'by': 'caption', 'score': score, 'nameHit': nh, 'dateHit': dh})
    return best if best else (None, None)


def _edge_color(im):
    """余白に敷く色。長辺側のふちの平均。白で埋めると濃い地のフライヤーで枠が浮く"""
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
    """縮小し、正方形に余白を足して JPEG で保存する。(幅, 高さ, バイト数)。

    カードのサムネは 1:1。9:16 の告知を cover で切るとタイトルが消えるので、
    切らずに余白を足す。切ると情報が減る。余白は減らない。
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


def load_json(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write('\n')


def stage_candidates(events, fresh_posts, today):
    """今回取れた投稿から、アイキャッチが無い開催予定の回の候補を staging に置く。

    fresh_posts: {username: [post(image=原寸URL付き)]}。media_url は署名付きで
    期限があるので、取れた回のうちに落とす。戻り値は新しく置いた件数。
    """
    import sitelib
    stage = load_json(STAGE_JSON, {'_note': '', 'items': {}})
    stage['_note'] = ('CI が Business Discovery の原寸画像から作ったアイキャッチ候補。'
                      '人が画像を見て scripts/apply-eyecatch.py で採否を書く。'
                      'events.json はここでは変わらない')
    items = stage.setdefault('items', {})
    rejected = load_json(REJECTED_JSON, {}).get('items', {})
    by_slug = {e.get('slug'): e for e in events}
    # 画像が付いた回・中止・終了した回の候補は捨てる
    for sl in list(items):
        e = by_slug.get(sl)
        d, de = sitelib.event_span(e) if e else ('', '')
        if (not e or e.get('imageUrl') or sitelib.is_cancelled(e)
                or not d or (de or d) < today):
            items.pop(sl)
            try:
                os.remove(os.path.join(STAGE_DIR, f'{sl}.jpg'))
            except OSError:
                pass
    added = 0
    for e in sorted(events, key=lambda x: sitelib.list_sort_key(x, today)):
        if len(items) >= MAX_PENDING:
            break
        sl = e.get('slug')
        if not sl or sl in items or e.get('imageUrl') or sitelib.is_cancelled(e):
            continue
        d, de = sitelib.event_span(e)
        if not d or (de or d) < today:
            continue
        u = (e.get('organizerIg') or '').strip().lstrip('@')
        posts = fresh_posts.get(u)
        if not posts:
            continue
        p, why = pick_post(e, posts, [r.get('post') for r in rejected.get(sl, [])])
        if not p:
            continue
        dest = os.path.join(STAGE_DIR, f'{sl}.jpg')
        try:
            with urllib.request.urlopen(p['image'], timeout=30) as r:
                raw = r.read()
            w, h, size = save_image(raw, dest)
        except Exception as ex:  # noqa: BLE001
            print(f'  アイキャッチ候補 {sl}: 画像を落とせない {type(ex).__name__}')
            continue
        if size > MAX_BYTES:
            os.remove(dest)
            continue
        items[sl] = {'name': e.get('name'), 'date': e.get('date'),
                     'post': p.get('permalink'), 'postedOn': (p.get('timestamp') or '')[:10],
                     'caption': _n(p.get('caption'))[:160], 'why': why,
                     'size': f'{w}x{h}', 'stagedOn': today}
        added += 1
    write_json(STAGE_JSON, stage)
    return added
