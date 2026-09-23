#!/usr/bin/env python3
"""ig-weekly.py — 今週末のイベントを Instagram のカルーセルにして @agave_navi に投稿する。

使い方:
  python3 scripts/ig-weekly.py build   [--out DIR] [--date YYYY-MM-DD]
      画像(1080x1350 JPEG)とキャプションを作るだけ。外に何も出さない。
  python3 scripts/ig-weekly.py publish --base-url URL [--out DIR] [--date YYYY-MM-DD]
      build 済みの画像を base-url 配下の公開URLとして Graph API に渡して投稿する。
      環境変数 IG_PAGE_TOKEN(期限なしのページトークン)が要る。

設計の要点(2026-09-23):
- 1枚目が表紙、2枚目以降が地域別の一覧。カルーセルは最大10枚なので、
  1回ぶんが30件あっても全件を載せられる形にした。イベントごとに1枚だと
  9件しか載らず、どれを落とすかという判断が毎週要る。
- 画像は主催の告知画像を使わず、ブランドの黒地に文字で組む。
  告知画像は主催の制作物で、サイトでは出典付きで載せているが、
  こちらのアカウントの投稿として再配布するのは扱いが違う。
- 主催の Instagram は、その回が載っている地域の頁に user_tags で付ける。
  主催に通知が届き、リポストの経路になる。存在しないユーザー名が1つでも
  混ざるとその頁の作成が丸ごと失敗するので、失敗したら tags 無しで作り直す。
- 同じ週末を2回投稿しない。ig-posts.json に週末の土曜日を鍵にして記録する。
- 中止の回は載せない(sitelib.is_cancelled)。
"""
import argparse
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402
import iglib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(REPO, 'ig-posts.json')

W, H = 1080, 1350
BLACK = (11, 11, 11)
IVORY = (243, 238, 228)
DIM = (150, 146, 138)
LINE = (46, 46, 46)
MAX_SLIDES = 10
BODY_TOP, BODY_H = 214, H - 214 - 150   # 見出しの下から足元の上まで
PILL_H, NAME_LH, META_H, ROW_GAP = 52, 54, 40, 34
NAME_PX = 44

REGION_ORDER = ['北海道', '東北', '関東', '北陸', '東海', '関西', '中国', '四国', '九州']
WEEKDAY = '月火水木金土日'

HASHTAGS = '#アガベ #塊根植物 #多肉植物 #植物イベント #アガベイベント'


# ---------------------------------------------------------------- 対象の回

def weekend_of(today):
    """その週の土日。土日に走ったらその週末、平日なら次の土日。"""
    wd = today.weekday()
    if wd == 5:
        sat = today
    elif wd == 6:
        sat = today - timedelta(days=1)
    else:
        sat = today + timedelta(days=5 - wd)
    return sat, sat + timedelta(days=1)


def weekend_events(events, sat, sun):
    s, u = sat.strftime('%Y-%m-%d'), sun.strftime('%Y-%m-%d')
    out = []
    for e in events:
        d = e.get('date') or ''
        de = e.get('dateEnd') or d
        if not d or sitelib.is_cancelled(e):
            continue
        if d <= u and de >= s:
            out.append(e)
    return out


def md(ds):
    dt = datetime.strptime(ds, '%Y-%m-%d')
    return f'{dt.month}/{dt.day}({WEEKDAY[dt.weekday()]})'


def date_label(e, sat, sun):
    """週末の中でその回がいつか。長期の回は『〜9/27』。"""
    d = e['date']
    de = e.get('dateEnd') or d
    s = sat.strftime('%Y-%m-%d')
    if d < s:
        return '開催中〜' + md(de).split('(')[0]
    if d == de:
        return md(d)
    a = datetime.strptime(d, '%Y-%m-%d')
    b = datetime.strptime(de, '%Y-%m-%d')
    if a.month == b.month:
        return f'{a.month}/{a.day}-{b.day}'
    return f'{a.month}/{a.day}-{b.month}/{b.day}'


def region_of(e):
    return sitelib.pref_to_region(e.get('prefecture') or '') or 'その他'


def plan_slides(evs, one_line=False):
    """[(地域名, [event,...]), ...]。表紙込みで10枚に収める。

    件数ではなく**描いたときの高さ**で頁を割る。件数で割ると、名前が2行に
    折り返す回が続いた頁だけ下の行と重なる(2026-09-23 の試作で NOVA CULTURA
    の2行目が次の日付と重なった)。10枚を超えるときは名前を1行に詰めて割り直す。
    """
    by = {}
    for e in evs:
        by.setdefault(region_of(e), []).append(e)
    order = [r for r in REGION_ORDER if r in by] + [r for r in by if r not in REGION_ORDER]
    pages = []
    for r in order:
        rows = sorted(by[r], key=lambda e: (e['date'], e.get('name') or ''))
        cur, used = [], 0
        for e in rows:
            h = row_height(e, one_line)
            if cur and used + h > BODY_H:
                pages.append((r, cur))
                cur, used = [], 0
            cur.append(e)
            used += h
        if cur:
            pages.append((r, cur))
    if len(pages) + 1 > MAX_SLIDES and not one_line:
        return plan_slides(evs, one_line=True)
    # それでも多ければ、同じ地域の続き頁や隣の少ない地域を詰める
    while len(pages) + 1 > MAX_SLIDES:
        best = None
        for i in range(len(pages) - 1):
            h = sum(row_height(e, one_line) for e in pages[i][1] + pages[i + 1][1])
            if h <= BODY_H and (best is None or h < best[0]):
                best = (h, i)
        if best is None:
            pages = pages[:MAX_SLIDES - 1]
            break
        i = best[1]
        a, b = pages[i], pages[i + 1]
        name = a[0] if a[0] == b[0] else f'{a[0]}・{b[0]}'
        pages[i:i + 2] = [(name, a[1] + b[1])]
    return pages, one_line


# ---------------------------------------------------------------- 画像

def _font(size, weight='Bold'):
    """Noto Sans CJK JP。無い太さは近い太さに落とす。

    Actions の ubuntu に apt で入る fonts-noto-cjk は Regular と Bold しか無い
    (Black / Medium は fonts-noto-cjk-extra)。太さを決め打ちすると CI だけで
    落ちる(2026-09-23 の初回実行で Black が無く build が空振りした)。
    """
    from PIL import ImageFont
    fallback = {'Black': ['Black', 'Bold'], 'Medium': ['Medium', 'Regular'],
                'Bold': ['Bold'], 'Regular': ['Regular']}
    for w in fallback.get(weight, [weight]) + ['Bold', 'Regular']:
        for p in (f'/usr/share/fonts/opentype/noto/NotoSansCJK-{w}.ttc',
                  f'/usr/share/fonts/noto-cjk/NotoSansCJK-{w}.ttc'):
            if os.path.exists(p):
                return ImageFont.truetype(p, size, index=0)  # index 0 = JP
    raise SystemExit('Noto Sans CJK が無い。fonts-noto-cjk を入れる')


def _fit(draw, text, font, width):
    """幅に収まるまで末尾を削って…を付ける。"""
    if draw.textlength(text, font=font) <= width:
        return text
    while text and draw.textlength(text + '…', font=font) > width:
        text = text[:-1]
    return text + '…'


def _wrap2(draw, text, font, width):
    """2行まで折り返す。はみ出す分は2行目の末尾で切る。"""
    line1 = ''
    for ch in text:
        if draw.textlength(line1 + ch, font=font) > width:
            break
        line1 += ch
    rest = text[len(line1):]
    if not rest:
        return [line1]
    return [line1, _fit(draw, rest, font, width)]


def _footer(img, draw):
    from PIL import Image
    logo_p = os.path.join(REPO, 'images', 'brand', 'logo-header.png')
    if os.path.exists(logo_p):
        logo = Image.open(logo_p).convert('RGBA')
        h = 44
        logo = logo.resize((round(logo.width * h / logo.height), h))
        img.paste(logo, (72, H - 72 - h), logo)
    f = _font(28, 'Medium')
    t = 'agave-navi.com'
    draw.text((W - 72 - draw.textlength(t, font=f), H - 72 - 36), t, font=f, fill=DIM)


def render_cover(sat, sun, n, path):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (W, H), BLACK)
    d = ImageDraw.Draw(img)
    mark_p = os.path.join(REPO, 'images', 'brand', 'agave-mark-master.png')
    if os.path.exists(mark_p):
        m = Image.open(mark_p).convert('RGBA')
        mw = 360
        m = m.resize((mw, round(m.height * mw / m.width)))
        img.paste(m, ((W - mw) // 2, 190), m)
    # 「植物イベント」だけだと観葉・花の催しにも読める。対象ジャンルを表紙で名乗る
    y = 600
    for text, size, col in (('今週末の', 56, DIM),
                            ('アガベ・塊根・多肉・サボテン', 58, IVORY),
                            ('植物イベント', 112, IVORY)):
        f = _font(size, 'Black' if size > 100 else 'Bold')
        d.text(((W - d.textlength(text, font=f)) / 2, y), text, font=f, fill=col)
        y += size + 30
    f = _font(52, 'Bold')
    t = f'{sat.month}.{sat.day} SAT — {sun.month}.{sun.day} SUN'
    d.text(((W - d.textlength(t, font=f)) / 2, y + 30), t, font=f, fill=IVORY)
    f = _font(40, 'Medium')
    t = f'全国 {n} 件　スワイプで地域別に'
    d.text(((W - d.textlength(t, font=f)) / 2, y + 130), t, font=f, fill=DIM)
    _footer(img, d)
    img.save(path, 'JPEG', quality=92)


def _meta(e):
    return '・'.join(x for x in ((e.get('prefecture') or '').strip(),
                                 (e.get('venue') or '').strip()) if x)


def _name_lines(e, one_line):
    from PIL import Image, ImageDraw
    d = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    f = _font(NAME_PX, 'Bold')
    name = e.get('name') or ''
    if one_line:
        return [_fit(d, name, f, W - 144)]
    return _wrap2(d, name, f, W - 144)


def row_height(e, one_line=False):
    return PILL_H + 14 + NAME_LH * len(_name_lines(e, one_line)) + META_H + ROW_GAP


def render_region(region, rows, sat, sun, page, pages, path, one_line=False):
    """地域の頁。user_tags に使う各行の中心座標(0..1)を返す。"""
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (W, H), BLACK)
    d = ImageDraw.Draw(img)
    f = _font(64, 'Black')
    d.text((72, 80), region, font=f, fill=IVORY)
    f2 = _font(30, 'Medium')
    t = f'{page}/{pages}'
    d.text((W - 72 - d.textlength(t, font=f2), 108), t, font=f2, fill=DIM)
    d.line((72, 184, W - 72, 184), fill=LINE, width=2)

    f_date = _font(32, 'Bold')
    f_name = _font(NAME_PX, 'Bold')
    f_meta = _font(30, 'Regular')
    y = BODY_TOP
    centers = []
    for i, e in enumerate(rows):
        y0 = y
        lab = date_label(e, sat, sun)
        pw = d.textlength(lab, font=f_date) + 40
        d.rounded_rectangle((72, y, 72 + pw, y + PILL_H), radius=PILL_H // 2, fill=IVORY)
        d.text((72 + 20, y + 5), lab, font=f_date, fill=BLACK)
        y += PILL_H + 14
        for ln in _name_lines(e, one_line):
            d.text((72, y), ln, font=f_name, fill=IVORY)
            y += NAME_LH
        meta = _meta(e)
        if meta:
            d.text((72, y + 2), _fit(d, meta, f_meta, W - 144), font=f_meta, fill=DIM)
        y += META_H
        if i < len(rows) - 1:
            d.line((72, y + ROW_GAP // 2 - 1, W - 72, y + ROW_GAP // 2 - 1), fill=LINE, width=1)
        y += ROW_GAP
        centers.append((0.5, round(min(0.95, ((y0 + y) / 2) / H), 3)))
    _footer(img, d)
    img.save(path, 'JPEG', quality=92)
    return centers


# ---------------------------------------------------------------- キャプション

def caption(sat, sun, pages, n):
    head = (f'今週末 {sat.month}/{sat.day}(土)・{sun.month}/{sun.day}(日) の'
            f'アガベ・塊根・多肉・サボテンのイベント {n}件\n\n')
    body = []
    prev = None
    for region, rows in pages:
        # 画像は高さで頁を割るので同じ地域が続くことがある。本文では見出しを1回にする
        if region != prev:
            if prev is not None:
                body.append('')
            body.append(f'【{region}】')
        prev = region
        for e in rows:
            body.append(f'{date_label(e, sat, sun)} {e.get("name")}（{e.get("prefecture")}）')
    body.append('')
    tail = ('各イベントの詳細・会場・出典はプロフィールのリンク agave-navi.com から。\n'
            '主催者の公式発信を確認して掲載しています。お出かけ前に主催者の最新情報もご確認ください。\n\n'
            + HASHTAGS)
    text = head + '\n'.join(body) + '\n' + tail
    if len(text) > 2150:  # 上限2200字。余裕を残して一覧側を詰める
        keep = 2150 - len(head) - len(tail) - 40
        text = head + '\n'.join(body)[:keep].rsplit('\n', 1)[0] + '\n…ほかはサイトで\n\n' + tail
    return text


# ---------------------------------------------------------------- build / publish

def load_events():
    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        return json.load(f)


def build(out, today):
    sat, sun = weekend_of(today)
    evs = weekend_events(load_events(), sat, sun)
    if not evs:
        print('今週末の回が0件。作らない')
        return None
    pages, one_line = plan_slides(evs)
    os.makedirs(out, exist_ok=True)
    manifest = {'weekend': sat.strftime('%Y-%m-%d'), 'count': len(evs), 'slides': []}
    render_cover(sat, sun, len(evs), os.path.join(out, '01.jpg'))
    manifest['slides'].append({'file': '01.jpg', 'tags': []})
    for i, (region, rows) in enumerate(pages, start=1):
        fn = f'{i + 1:02d}.jpg'
        centers = render_region(region, rows, sat, sun, i, len(pages), os.path.join(out, fn), one_line)
        tags = []
        for e, (x, y) in zip(rows, centers):
            u = (e.get('organizerIg') or '').strip().lstrip('@')
            if u and all(t['username'] != u for t in tags):
                tags.append({'username': u, 'x': x, 'y': y})
        manifest['slides'].append({'file': fn, 'tags': tags[:20]})
    manifest['caption'] = caption(sat, sun, pages, len(evs))
    with open(os.path.join(out, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out, 'caption.txt'), 'w', encoding='utf-8') as f:
        f.write(manifest['caption'])
    print(f'{manifest["weekend"]}: {len(evs)}件 → {len(manifest["slides"])}枚 → {out}')
    return manifest


_api = iglib.req


def _wait_public(url, limit=900):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(20)
    return False


def publish(out, base_url):
    token = os.environ.get('IG_PAGE_TOKEN', '').strip()
    if not token:
        raise SystemExit('IG_PAGE_TOKEN が無い')
    with open(os.path.join(out, 'manifest.json'), encoding='utf-8') as f:
        m = json.load(f)
    state = {}
    if os.path.exists(STATE):
        with open(STATE, encoding='utf-8') as f:
            state = json.load(f)
    if m['weekend'] in state:
        print(f'{m["weekend"]} は投稿済み({state[m["weekend"]].get("media_id")})。何もしない')
        return
    me = _api('GET', 'me', token, fields='id,name,instagram_business_account')
    ig = (me.get('instagram_business_account') or {}).get('id')
    if not ig:
        raise SystemExit(f'ページ {me.get("name")} に Instagram が紐付いていない')

    base = base_url.rstrip('/')
    first = f'{base}/{m["slides"][0]["file"]}'
    if not _wait_public(first):
        raise SystemExit(f'画像が公開されない: {first}')

    children = []
    for s in m['slides']:
        url = f'{base}/{s["file"]}'
        _wait_public(url, limit=300)
        params = {'image_url': url, 'is_carousel_item': 'true'}
        if s['tags']:
            params['user_tags'] = json.dumps(s['tags'])
        try:
            r = _api('POST', f'{ig}/media', token, **params)
        except RuntimeError as ex:
            if not s['tags']:
                raise
            print(f'  {s["file"]}: タグ付きで失敗 → タグ無しで作り直す ({ex})')
            params.pop('user_tags')
            r = _api('POST', f'{ig}/media', token, **params)
        children.append(r['id'])

    car = _api('POST', f'{ig}/media', token, media_type='CAROUSEL',
               children=','.join(children), caption=m['caption'])
    cid = car['id']
    for _ in range(30):
        st = _api('GET', cid, token, fields='status_code').get('status_code')
        if st == 'FINISHED':
            break
        if st in ('ERROR', 'EXPIRED'):
            raise SystemExit(f'カルーセルの作成に失敗: {st}')
        time.sleep(10)
    pub = _api('POST', f'{ig}/media_publish', token, creation_id=cid)
    link = _api('GET', pub['id'], token, fields='permalink').get('permalink')
    state[m['weekend']] = {'media_id': pub['id'], 'permalink': link,
                           'count': m['count'], 'slides': len(children),
                           'postedAt': datetime.now(sitelib.JST).isoformat(timespec='seconds')}
    with open(STATE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    print(f'投稿した: {link}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('mode', choices=['build', 'publish', 'outdir', 'check'])
    ap.add_argument('--out', default=None)
    ap.add_argument('--date', default=None, help='今日として扱う日(JST)')
    ap.add_argument('--base-url', default=None)
    a = ap.parse_args()
    today = (datetime.strptime(a.date, '%Y-%m-%d') if a.date
             else datetime.strptime(sitelib.today_jst(), '%Y-%m-%d'))
    sat, _ = weekend_of(today)
    out = a.out or os.path.join(REPO, 'images', 'ig', sat.strftime('%Y-%m-%d'))
    if a.mode == 'check':
        # 投稿しない回でもトークンと連携の生死だけは毎回確かめる。
        # 木曜の本番で初めて失効に気づくのを避ける。トークン自体は出さない。
        token = os.environ.get('IG_PAGE_TOKEN', '').strip()
        if not token:
            raise SystemExit('IG_PAGE_TOKEN が無い')
        ig_id, igu, page = iglib.own_account(token)
        lines = [f'ページ: {page} / Instagram: @{igu}' if igu
                 else f'ページ: {page} / Instagram が紐付いていない']
        # 主催者の見張り(ig-organizer-watch.py)が使う Business Discovery も確かめる。
        # 投稿とは要る権限が違う(instagram_manage_insights)ので、片方だけ通ることがある
        if igu:
            bd, err = iglib.business_discovery(ig_id, 'instagram', token, 'username,media_count')
            lines.append(f'Business Discovery: NG {err.get("message", "")[:200]}' if err
                         else f'Business Discovery: OK (@{bd.get("username")} {bd.get("media_count")}件)')
        print('\n'.join(lines))
        summ = os.environ.get('GITHUB_STEP_SUMMARY')
        if summ:
            with open(summ, 'a', encoding='utf-8') as f:
                f.write('### トークンの確認\n\n' + '\n'.join(f'- {x}' for x in lines) + '\n\n')
        if not igu:
            raise SystemExit(1)
        return
    if a.mode == 'outdir':
        # ワークフローが「今回作った頁」を取り違えないための問い合わせ。
        # images/ig/ の最新ディレクトリを拾う作りだと、今週が0件のとき
        # 先週の画像を投稿してしまう。今週ぶんが無ければ何も出さない。
        if os.path.exists(os.path.join(out, 'manifest.json')):
            print(os.path.relpath(out, REPO))
        return
    if a.mode == 'build':
        build(out, today)
    else:
        if not a.base_url:
            raise SystemExit('--base-url が要る')
        publish(out, a.base_url)


if __name__ == '__main__':
    main()
