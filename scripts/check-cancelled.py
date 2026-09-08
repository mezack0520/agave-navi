#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""開催予定の回について、主催者の出典に中止・延期の兆候が出ていないか毎日見る。

coverage-sweep.py の逆。あちらは「他所にあってこちらに無い回」を探し、
こちらは「こちらにあって、もう開催されない回」を探す。

## なぜ要るか

2026-09-08まで、掲載は追加の一方通行だった。Collect Plants Vol.3 は
2026-07-28 の令和8年熊本地震を受けて 08-12 に中止が告知されていたが、
当サイトは 09-08 まで27日間「開催予定」として載せ続けた。気づいたのは
主催者からフォームで削除依頼が来たからで、こちらからは何も見ていなかった。

## 2つの信号を使う

1. **文言**: ページの本文・title・og・画像のalt・画像のファイル名から
   「中止」「延期」等を探す。安いが、取りこぼす。
2. **変化**: 本文と画像URLの集合のハッシュを前回と比べる。開催が近い回の
   公式ページが動いたら、それだけで人が見る理由になる。

**2 が要るのは、日本の主催者が告知を画像で出すから。** collect-plants.com は
トップのメインビジュアルに「開催中止のお知らせ」と大書していたが、
HTMLの文字列には一言も無く、1 では絶対に見つからない。
画像の中の文字はOCRなしには読めないので、ここは「変わった」ことだけを見て
人に回す。ノイズは出る。出ないようにすると今回の型を落とす。

## 使い方

    python3 scripts/check-cancelled.py            # 巡回して cancel-watch.json を更新
    python3 scripts/check-cancelled.py --self-test  # 判定だけ検証(通信なし)
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
from sitelib import today_jst, is_cancelled, event_span   # noqa: E402

WATCH_JSON = os.path.join(REPO, 'cancel-watch.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# 開催まで何日先まで見るか。過ぎた回と遠い回は毎日取りに行っても意味が薄い
HORIZON_DAYS = 60

# 中止・延期を示す語。「順延」は雨天順延の告知でも出るので単独では弱いが、
# 人が見る材料としては拾ってよい
CANCEL_WORDS = (
    '開催中止', '中止のお知らせ', '中止となりました', '中止いたします',
    '中止させていただ', '開催を中止', '中止が決定',
    '延期のお知らせ', '延期となりました', '延期させていただ', '開催を延期',
    '開催見合わせ', '見合わせとなりました', '開催を見送',
)
# 「中止」単独は「雨天中止」「中止の場合は」など条件付きの文でも出る。
# 単独語は弱い信号として別に数える
WEAK_WORDS = ('中止', '延期', '見合わせ', 'キャンセル')

# 出典がSNSのものは本文が取れないので巡回しない(ログインが要る)
SKIP_DOMAINS = ('instagram.com', 'twitter.com', 'x.com', 'facebook.com',
                'tiktok.com', 'peatix.com')


def norm(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s or '')).strip()


def strip_html(html):
    """本文のテキスト。script/style/noscript は落とす"""
    h = re.sub(r'(?is)<(script|style|noscript)\b.*?</\1>', ' ', html or '')
    h = re.sub(r'(?s)<!--.*?-->', ' ', h)
    h = re.sub(r'<[^>]+>', ' ', h)
    return norm(h)


def image_tokens(html):
    """画像のURLとalt。告知が画像のとき、ファイル名やaltに手がかりが残る"""
    out = []
    for m in re.finditer(r'(?is)<img\b[^>]*>', html or ''):
        tag = m.group(0)
        src = (re.search(r'(?i)\bsrc\s*=\s*["\']([^"\']+)', tag) or [None, ''])[1]
        alt = (re.search(r'(?i)\balt\s*=\s*["\']([^"\']*)', tag) or [None, ''])[1]
        if src:
            out.append(norm(src))
        if alt:
            out.append(norm(alt))
    for m in re.finditer(r'(?i)<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html or ''):
        out.append(norm(m.group(1)))
    return out


def meta_texts(html):
    out = []
    t = re.search(r'(?is)<title[^>]*>(.*?)</title>', html or '')
    if t:
        out.append(norm(re.sub(r'<[^>]+>', ' ', t.group(1))))
    for prop in ('og:title', 'og:description', 'description'):
        for m in re.finditer(
                r'(?i)<meta[^>]+(?:property|name)=["\']' + re.escape(prop)
                + r'["\'][^>]+content=["\']([^"\']*)', html or ''):
            out.append(norm(m.group(1)))
    return out


def find_words(texts):
    """強い語と弱い語をそれぞれ拾う"""
    blob = ' '.join(texts)
    strong = sorted({w for w in CANCEL_WORDS if w in blob})
    weak = sorted({w for w in WEAK_WORDS if w in blob})
    return strong, weak


def page_signature(html):
    """本文と画像の集合から署名を作る。

    画像の中の文字は読めないので、URLの集合が変わったことをもって
    「差し替わった」と見る。メインビジュアルが告知画像に変わる型を拾うため。
    """
    body = strip_html(html)
    imgs = sorted(set(image_tokens(html)))
    return {
        'text': hashlib.sha256(body.encode('utf-8')).hexdigest()[:16],
        'images': hashlib.sha256('\n'.join(imgs).encode('utf-8')).hexdigest()[:16],
        'textLen': len(body),
        'imageCount': len(imgs),
    }


def analyze(html):
    texts = [strip_html(html)] + meta_texts(html) + image_tokens(html)
    strong, weak = find_words(texts)
    sig = page_signature(html)
    return {'strong': strong, 'weak': weak, 'signature': sig}


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA,
                                               'Accept-Language': 'ja'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return raw.decode('utf-8', 'replace')


def watch_targets(events, today, horizon=HORIZON_DAYS):
    """巡回対象。開催予定で、出典が取れるURLを持つ回だけ"""
    t = date.fromisoformat(today)
    out = []
    for e in events:
        if is_cancelled(e):
            continue
        d, de = event_span(e)
        if not d:
            continue
        try:
            end = date.fromisoformat(de or d)
            start = date.fromisoformat(d)
        except ValueError:
            continue
        if end < t or (start - t).days > horizon:
            continue
        url = (e.get('url') or e.get('sourceUrl') or '').strip()
        if not url or url == '#':
            continue
        if any(dom in url for dom in SKIP_DOMAINS):
            continue
        out.append((e, url))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--sleep', type=float, default=0.8)
    ap.add_argument('--horizon', type=int, default=HORIZON_DAYS)
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    try:
        with open(WATCH_JSON, encoding='utf-8') as f:
            prev = json.load(f)
    except (OSError, ValueError):
        prev = {}
    prev_pages = (prev.get('pages') or {})

    today = today_jst()
    targets = watch_targets(events, today, args.horizon)
    pages, suspects, errors = {}, [], []
    stats = {'targets': len(targets), 'fetched': 0}

    for e, url in targets:
        slug = e.get('slug') or ''
        try:
            html = fetch(url)
            stats['fetched'] += 1
        except urllib.error.HTTPError as err:
            errors.append(f'{slug}: HTTP {err.code} {url}')
            continue
        except Exception as err:                      # noqa: BLE001
            errors.append(f'{slug}: {type(err).__name__} {url}')
            continue

        res = analyze(html)
        before = prev_pages.get(slug) or {}
        bsig = before.get('signature') or {}
        sig = res['signature']
        changed = []
        if bsig:
            if bsig.get('text') != sig['text']:
                changed.append('本文')
            if bsig.get('images') != sig['images']:
                changed.append('画像')

        pages[slug] = {
            'url': url, 'checkedOn': today, 'signature': sig,
            'strong': res['strong'], 'weak': res['weak'],
            'firstSeenOn': before.get('firstSeenOn') or today,
        }

        why = []
        if res['strong']:
            why.append('中止・延期の語: ' + ' / '.join(res['strong']))
        elif res['weak'] and changed:
            why.append('弱い語(' + ' / '.join(res['weak']) + ')＋ページが変わった')
        elif changed and before:
            why.append('公式ページが変わった(' + '・'.join(changed) + ')')
        if why:
            suspects.append({
                'slug': slug, 'name': e.get('name') or '',
                'date': e.get('date') or '', 'url': url,
                'why': ' / '.join(why),
                'changed': changed,
            })
        time.sleep(args.sleep)

    out = {
        '_note': ('開催予定の回について、主催者の出典に中止・延期の兆候が出ていないかを'
                  '毎日見た結果。scripts/check-cancelled.py が書く。'
                  'suspects は「人が見る理由がある」だけで、中止の証拠ではない。'
                  '一次情報を確認して、中止なら events.json の eventStatus を '
                  'cancelled にする(削除しない)。'
                  '**画像の中の文字は読めない。**主催者が告知を画像で出す型は '
                  'signature の変化でしか拾えないので、ノイズは織り込んでいる。'
                  'errors が空でないときは巡回そのものが失敗しているので、'
                  'suspects が0件でも「兆候なし」とは言えない。'),
        'sweptOn': today, 'stats': stats, 'errors': errors,
        'suspects': sorted(suspects, key=lambda x: x['date']),
        'pages': pages,
    }
    with open(WATCH_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f"巡回対象 {stats['targets']} 件 / 取得できた {stats['fetched']} 件")
    print(f"★ 中止の疑い: {len(suspects)}件")
    for s in suspects:
        print(f"    {s['date']} {s['name'][:34]} — {s['why']}")
    if errors:
        print(f"⚠ 取得できなかった: {len(errors)}件")
        for e in errors[:10]:
            print('    ' + e)
    return 0


# ---------------------------------------------------------------- self-test
FIX_TEXT_NOTICE = '''<html><head><title>◯◯フェス</title></head><body>
<h1>◯◯フェス</h1><p>このたびの台風の影響により、開催中止のお知らせを申し上げます。</p>
<img src="/img/key.jpg" alt="キービジュアル"></body></html>'''

FIX_IMAGE_NOTICE_BEFORE = '''<html><head><title>コレクトプランツ</title></head><body>
<img src="/uploads/2025/06/collectplants_mv2_pc.png" alt="">
<p>熊本最大級の植物イベント</p></body></html>'''

FIX_IMAGE_NOTICE_AFTER = '''<html><head><title>コレクトプランツ</title></head><body>
<img src="/uploads/2026/08/cancel_mv.png" alt="">
<p>熊本最大級の植物イベント</p></body></html>'''

FIX_WEAK = '''<html><head><title>△△マルシェ</title></head><body>
<p>雨天中止の場合はInstagramでお知らせします。</p>
<img src="/img/a.jpg" alt=""></body></html>'''

FIX_PLAIN = '''<html><head><title>□□植物祭</title></head><body>
<p>今年も開催します。出店者を募集中です。</p>
<img src="/img/b.jpg" alt=""></body></html>'''


def self_test():
    ok = True

    def chk(label, got, want):
        nonlocal ok
        mark = 'OK ' if got == want else '★NG'
        if got != want:
            ok = False
        print(f'  {mark} {label}: {got!r} 期待={want!r}')

    print('--- 文言の検出 ---')
    a = analyze(FIX_TEXT_NOTICE)
    chk('本文に中止告知 → 強い語', bool(a['strong']), True)
    b = analyze(FIX_WEAK)
    chk('雨天中止 → 強い語ではない', bool(b['strong']), False)
    chk('雨天中止 → 弱い語では拾う', bool(b['weak']), True)
    c = analyze(FIX_PLAIN)
    chk('平常のページ → どちらも出ない', bool(c['strong'] or c['weak']), False)

    print('\n--- 画像だけの告知(文言では拾えないことの確認) ---')
    before = analyze(FIX_IMAGE_NOTICE_BEFORE)
    after = analyze(FIX_IMAGE_NOTICE_AFTER)
    chk('画像差し替えでは強い語は出ない', bool(after['strong']), False)
    chk('画像の署名は変わる',
        before['signature']['images'] != after['signature']['images'], True)
    chk('本文の署名は変わらない',
        before['signature']['text'] == after['signature']['text'], True)

    print('\n--- 巡回対象の絞り込み ---')
    today = '2026-09-08'
    evs = [
        {'slug': 'near', 'date': '2026-09-22', 'url': 'https://example.com/'},
        {'slug': 'past', 'date': '2026-09-01', 'url': 'https://example.com/'},
        {'slug': 'far', 'date': '2027-03-01', 'url': 'https://example.com/'},
        {'slug': 'ig', 'date': '2026-09-22',
         'url': 'https://www.instagram.com/p/xxx/'},
        {'slug': 'nourl', 'date': '2026-09-22', 'url': ''},
        {'slug': 'done', 'date': '2026-09-22', 'url': 'https://example.com/',
         'eventStatus': 'cancelled'},
    ]
    got = sorted(e.get('slug') for e, _ in watch_targets(evs, today))
    chk('対象は開催前・出典あり・SNS以外・未中止だけ', got, ['near'])

    print('\n結果: ' + ('すべて通過' if ok else '★失敗あり'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
