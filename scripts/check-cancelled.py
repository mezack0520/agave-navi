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

3. **日付**: 頁が散文で日付を名乗っているのに、そこに**この回の開催日が
   一度も出てこない**なら、その出典はこの回を裏付けていない。同じシリーズの
   前回の記事を出典にしている型と、名前が同じだけの無関係な頁を掴んでいる型を
   拾う(2026-09-08 に2件検出。Wi-Wi BOTANICAL Vol.2 は6月開催回のニュース記事、
   ONE LOVE 佐野は同名のアイドルグループのライブ日程頁だった)。
   `url` は「在るか」しか見られていないので、中身が別の回でも薄頁判定を外れ、
   詳細頁は「裏取り済み」の顔で出る。判定は audit.source_page_wrong_edition。

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
from sitelib import (today_jst, is_cancelled, event_span,   # noqa: E402
                     find_month_days, event_month_days)

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


# 天候の条件を述べているだけの言い回し。**告知ではない。**
# 「※雨天時は中止となる場合があります」で毎日鳴っていた
# (GreenSnap Marche 横浜。中止したのはイベントではなく、
#  雨のときのマスコットのグリーティング。2026-09-09 確認)。
#
# 「場合」「際」「とき」が付く条件文と、雨天中止・荒天中止の熟語だけを
# 落とす。「悪天候のため中止しました」は残す。過去形で言い切っている
# ものは本物の告知なので、消してはいけない。
CONDITIONAL_CANCEL = (
    r'[雨荒悪][天候][時中]?[はの]?(?:場合|際|とき)?[はに]?(?:中止|順延|延期)',
    r'(?:中止|順延|延期)(?:と)?(?:なる|する|の)?(?:場合|際|とき)',
    r'雨天中止',
    r'荒天中止',
)


def drop_conditional(text):
    """条件文だけを落とす。判定に使う前に通す。"""
    out = text
    for pat in CONDITIONAL_CANCEL:
        out = re.sub(pat, ' ', out)
    return out


def find_words(texts):
    """強い語と弱い語をそれぞれ拾う。条件文は数えない"""
    blob = drop_conditional(' '.join(texts))
    strong = sorted({w for w in CANCEL_WORDS if w in blob})
    weak = sorted({w for w in WEAK_WORDS if w in blob})
    return strong, weak


def drop_today(text, today=None):
    """今日の日付を落とす。

    「本日の開園時間 2026.09.09 9:30〜17:00」のような表示を持つ頁があり、
    本文が毎日変わる。**未来のイベントが中止かどうかと、頁に今日の日付が
    出ていることは何の関係もない**(しまね花の郷で2件が毎日鳴っていた。
    2026-09-09 確認)。署名を作る前にこれだけ落とす。
    イベントの日付は落とさない。日程変更は拾いたい信号なので。
    """
    d = today or today_jst()
    if isinstance(d, str):
        # sitelib.today_jst() は文字列を返す。date に揃える
        d = date.fromisoformat(d[:10])
    pats = [
        f'{d.year}.{d.month:02d}.{d.day:02d}', f'{d.year}.{d.month}.{d.day}',
        f'{d.year}/{d.month:02d}/{d.day:02d}', f'{d.year}/{d.month}/{d.day}',
        f'{d.year}-{d.month:02d}-{d.day:02d}',
        f'{d.year}年{d.month}月{d.day}日',
    ]
    out = text
    for x in pats:
        out = out.replace(x, ' ')
    return out


def page_signature(html, today=None):
    """本文と画像の集合から署名を作る。

    画像の中の文字は読めないので、URLの集合が変わったことをもって
    「差し替わった」と見る。メインビジュアルが告知画像に変わる型を拾うため。
    """
    body = drop_today(strip_html(html), today)
    imgs = sorted(set(image_tokens(html)))
    return {
        'text': hashlib.sha256(body.encode('utf-8')).hexdigest()[:16],
        'images': hashlib.sha256('\n'.join(imgs).encode('utf-8')).hexdigest()[:16],
        'textLen': len(body),
        'imageCount': len(imgs),
    }


def page_dates(html):
    """頁が名乗っている日付。(散文で名乗った数, 全書式で拾った集合)

    **判定は非対称にする。** 「日付を名乗っている頁か」は「◯月◯日」だけで
    見る(スラッシュ形は画像パス /2026/09/ やページ送りにも出るので、
    名乗りの根拠にならない)。一方「この回の日付が出ているか」は全書式で見る。
    こうすると、鳴りにくく・消えやすい側に倒れる。
    実測(2026-09-08・巡回23件): 非対称にすると誤検知0で実害2件だけが残る。
    両方を狭い側で見ると 2026.10.10 表記の回が、両方を広い側で見ると
    公式トップ頁(日付は画像の中)が、それぞれ誤検知になった。
    """
    body = strip_html(html)
    blob = body + ' ' + ' '.join(meta_texts(html))
    return len(find_month_days(blob, kanji_only=True)), find_month_days(blob)


def analyze(html, event=None):
    texts = [strip_html(html)] + meta_texts(html) + image_tokens(html)
    strong, weak = find_words(texts)
    sig = page_signature(html)
    named, found = page_dates(html)
    out = {'strong': strong, 'weak': weak, 'signature': sig,
           'datesNamed': named}
    if event is not None:
        span = event_month_days(event)
        out['eventDateSeen'] = bool(span & found) if span else None
    return out


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

    # 判定が壊れたまま巡回すると、もっともらしい「兆候なし」が書き込まれ、
    # 読む側からは正常と区別が付かない。coverage-sweep が 2026-09-01 に
    # 同じ穴(どのCIからも呼ばれない自己テスト)を塞いだのに、こちらは
    # 外れたままだった(2026-09-08)。daily の push を巻き込みたくないので
    # ジョブは止めず、logicErrors に積んで audit の
    # cancel_watch_broken(urgent) に出す。
    logic_errors = []
    if self_test(verbose=False) != 0:
        logic_errors.append('自己テストが失敗した。判定ロジックが壊れている。'
                            'suspects と eventDateSeen は当てにならない'
                            '(python3 scripts/check-cancelled.py --self-test)')

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

        res = analyze(html, e)
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
            # 出典がこの回を裏付けているか。audit.source_page_wrong_edition が読む。
            # CI から頁を取れるのはこのスクリプトだけなので、判定材料を
            # ここに置かないと監査側からは見えない
            'datesNamed': res['datesNamed'],
            'eventDateSeen': res.get('eventDateSeen'),
            'firstSeenOn': before.get('firstSeenOn') or today,
        }

        # 「本文だけ毎回変わる」ページがある。Wix や WordPress の一部は
        # 日付・カウンタ・ランダムなIDを埋め込むので、中止と無関係に
        # 署名が動く。同じ回で本文だけの変化が続いたら数えない。
        # 毎日鳴る指摘は読まれなくなり、本物の変化を埋める(2026-09-08)。
        noisy = int(before.get('textOnlyChanges') or 0)
        text_only = (changed == ['本文'])
        if text_only:
            noisy += 1
        elif changed:
            noisy = 0
        pages[slug]['textOnlyChanges'] = noisy

        why = []
        if res['strong']:
            why.append('中止・延期の語: ' + ' / '.join(res['strong']))
        elif res['weak'] and changed:
            why.append('弱い語(' + ' / '.join(res['weak']) + ')＋ページが変わった')
        elif '画像' in changed:
            why.append('公式ページが変わった(' + '・'.join(changed) + ')')
        elif text_only and before and noisy <= 2:
            why.append('公式ページが変わった(本文)')
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
        'logicErrors': logic_errors,
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

# 出典が「同じ名前の前回の回」を指している型。頁は日付を名乗っているのに、
# それは6月開催回のもの(2026-09-08 の wi-wi-botanical-minokamo-2026-09)
FIX_WRONG_EDITION = '''<html><head><title>【美濃加茂市】「Wi-Wi BOTANICAL」開催</title></head><body>
<p>2026年6月7日（日）、リバーポートパーク美濃加茂にて開催されます。</p>
<p>関連記事 8月30日のマルシェ / 9月28日で休業</p></body></html>'''

# 出典は正しいが、日付は画像の中にしか無い公式トップ頁。
# ここで鳴らすと、告知を画像で出す主催が全部誤検知になる
FIX_DATE_IN_IMAGE = '''<html><head><title>【公式】On the Plants</title></head><body>
<p>九州最大級の複合販売イベント。出店者を募集しています。</p>
<img src="/wp-content/uploads/2026/09/keyvisual.jpg" alt=""></body></html>'''

# 日付を「2026.10.10」形式だけで書く頁。名乗りの数は0でも、
# この回の日付は拾えていなければならない
FIX_DOT_DATE = '''<html><head><title>◇◇サボテン展</title></head><body>
<p>会期 2026.10.10 - 2026.10.11 / 入場無料</p></body></html>'''


FIX_COND = """<html><body><h1>◯◯マルシェ</h1>
<p>2026年10月10日(土) 開催します。</p>
<p>※雨天時は中止となる場合があります。最新情報はSNSでご確認ください。</p>
</body></html>"""

FIX_REAL_WEATHER = """<html><body><h1>◯◯マルシェ</h1>
<p>悪天候のため中止しました。ご来場を予定されていた皆様にお詫び申し上げます。</p>
</body></html>"""

# 「本日の開園時間」を持つ頁。中身は同じで日付だけが違う
FIX_TODAY_A = """<html><body><p>本日の開園時間 2026.09.09 9:30〜17:00</p>
<h1>サボテン・多肉植物展</h1><p>開催期間 2026/10/10 〜 2026/10/12</p>
</body></html>"""

FIX_TODAY_B = """<html><body><p>本日の開園時間 2026.09.10 9:30〜17:00</p>
<h1>サボテン・多肉植物展</h1><p>開催期間 2026/10/10 〜 2026/10/12</p>
</body></html>"""

FIX_DATE_CHANGED = """<html><body><p>本日の開園時間 2026.09.09 9:30〜17:00</p>
<h1>サボテン・多肉植物展</h1><p>開催期間 2026/10/17 〜 2026/10/19</p>
</body></html>"""


def self_test(verbose=True):
    ok = True

    def chk(label, got, want):
        nonlocal ok
        mark = 'OK ' if got == want else '★NG'
        if got != want:
            ok = False
        if verbose or got != want:
            print(f'  {mark} {label}: {got!r} 期待={want!r}')

    def say(msg):
        if verbose:
            print(msg)

    say('--- 文言の検出 ---')
    a = analyze(FIX_TEXT_NOTICE)
    chk('本文に中止告知 → 強い語', bool(a['strong']), True)
    b = analyze(FIX_WEAK)
    chk('雨天中止 → 強い語ではない', bool(b['strong']), False)
    # 2026-09-09 に方針を変えた。天候の条件文は数えない。
    # 「※雨天時は中止となる場合があります」で毎日鳴っていた
    chk('雨天中止は条件文なので弱い語でも数えない', bool(b['weak']), False)
    d = analyze(FIX_COND)
    chk('雨天時は中止となる場合 → 数えない', bool(d['strong'] or d['weak']), False)
    e = analyze(FIX_REAL_WEATHER)
    chk('悪天候のため中止しました → 拾う', bool(e['strong'] or e['weak']), True)
    c = analyze(FIX_PLAIN)
    chk('平常のページ → どちらも出ない', bool(c['strong'] or c['weak']), False)

    say('')
    say('--- 今日の日付は署名に入れない ---')
    import datetime as _dt
    _t = _dt.date(2026, 9, 9)
    # 実際の巡回は「その日の頁をその日の today で署名する」。
    # 昨日は昨日の日付が、今日は今日の日付が落ちるので署名は揃う。
    # 同じ today で別の日の頁を比べても意味がない(最初そう書いて外した)
    s1 = page_signature(FIX_TODAY_A, today=_t)
    s2 = page_signature(FIX_TODAY_B, today=_dt.date(2026, 9, 10))
    chk('今日の日付を出す頁 → 日をまたいでも署名は同じ', s1['text'], s2['text'])
    s3 = page_signature(FIX_DATE_CHANGED, today=_t)
    chk('開催日が変わった頁 → 署名は変わる', s1['text'] != s3['text'], True)

    say('\n--- 画像だけの告知(文言では拾えないことの確認) ---')
    before = analyze(FIX_IMAGE_NOTICE_BEFORE)
    after = analyze(FIX_IMAGE_NOTICE_AFTER)
    chk('画像差し替えでは強い語は出ない', bool(after['strong']), False)
    chk('画像の署名は変わる',
        before['signature']['images'] != after['signature']['images'], True)
    chk('本文の署名は変わらない',
        before['signature']['text'] == after['signature']['text'], True)

    say('\n--- 出典がこの回を裏付けているか ---')
    ev_sep = {'slug': 'x', 'date': '2026-09-20', 'dateEnd': '2026-09-20'}
    w = analyze(FIX_WRONG_EDITION, ev_sep)
    chk('別の回の記事 → 開催日が出てこない', w['eventDateSeen'], False)
    chk('別の回の記事 → 散文で日付は名乗っている', w['datesNamed'] > 0, True)
    i = analyze(FIX_DATE_IN_IMAGE, ev_sep)
    chk('日付が画像の中だけ → 名乗り0(判定しない)', i['datesNamed'], 0)
    d = analyze(FIX_DOT_DATE, {'slug': 'y', 'date': '2026-10-10',
                               'dateEnd': '2026-10-11'})
    chk('2026.10.10 形式でも開催日は拾う', d['eventDateSeen'], True)
    chk('2026.10.10 形式は名乗りには数えない', d['datesNamed'], 0)
    g = analyze(FIX_WRONG_EDITION, {'slug': 'z', 'date': '2026-06-07',
                                    'dateEnd': '2026-06-07'})
    chk('同じ頁でも6月開催の回なら裏付けになる', g['eventDateSeen'], True)

    say('\n--- 巡回対象の絞り込み ---')
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

    say('\n結果: ' + ('すべて通過' if ok else '★失敗あり'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
