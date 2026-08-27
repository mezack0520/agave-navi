#!/usr/bin/env python3
"""coverage-sweep.py — 他所に載っていて当サイトに無いイベントを毎日検出する。

## なぜあるか

2026-08-27、「今週末の関東のイベントは？」に答えられなかった。
掲載2件に対して実際は関東で10件以上開催されており、9月も関東で10件、
全国では42件の未掲載が見つかった。中には60店舗超の大型イベントもあった。

このとき audit は urgent 0 / info 0 だった。**手元のデータの整合性は完璧で、
外の世界に対して欠けていることを誰も見ていなかった。**
イベント掲載サイトにとって、これがいちばん重い欠陥。

巡回はキーワード検索と主催者アカウントのローテーションだけで、
「その日に何があるか」を機械的に列挙する経路が無かったのが原因。

## 何をするか

LEAFLA の日付別ページ（1日1ページ・全国）を先の日付ぶん取得し、
そこに出ているイベント名を events.json と rejected-events.json に突き合わせて、
**どちらにも無いものを「取りこぼし候補」として書き出す。**

出力: coverage-gaps.json
  audit.py が読んで件数を報告し、健全性メールに出る。
  日次タスクはこの候補を一次情報で裏取りして、掲載するか rejected に落とす。

## 誤検知を抑える設計

LEAFLA は植物全般を扱うので、当サイトの対象外（ダリア園・盆栽・薬用植物の
観察会・ポトスの育成企画など）が大量に混ざる。全部を候補に出すと一覧が埋まり、
**今日いちばん学んだ「対応不要なものを並べると一覧ごと無視される」を繰り返す。**
そこで対象キーワードを含むものだけを候補にする。

取得に失敗した日は「候補ゼロ」ではなく `errors` に積む。
黙って0件になるのが最悪なので、区別できるようにしておく。

Usage:
  python3 scripts/coverage-sweep.py                # 先45日
  python3 scripts/coverage-sweep.py --days 60
  python3 scripts/coverage-sweep.py --self-test    # 判定ロジックだけ検証(通信なし)
"""

import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'coverage-gaps.json')

# 日付別ページ。1日1ページで全国のその日のイベントが並ぶ。
# 先の日付は404になる(2026-08-27時点で約2か月先まで)。404は異常として扱わない。
BASE = 'https://leaf-laboratory.com/blogs/media/event-list-'
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# 当サイトの対象。これを含まない候補は範囲外として捨てる。
# LEAFLA は植物全般を載せるので、この絞りが無いと候補の大半がノイズになる
# (実測: 2026-09-06 の44件のうち対象は6件だった)。
IN_SCOPE = (
    'アガベ', 'agave', '多肉', 'サボテン', 'カクタス', 'cactus',
    '塊根', 'コーデックス', 'caudex', 'パキポ', 'グラキリス',
    'ビカクシダ', '麋角', 'platycerium', 'ビザール', 'bizarre',
    '珍奇', 'エケベリア', 'ハオルチア', 'ユーフォルビア',
    'チランジア', 'ティランジア', 'ブロメリア', 'ディッキア',
    'アデニウム', 'ステファニア', 'ユッカ', 'アロエ', 'メセン',
)

# 対象キーワードを含んでいても、これらが主題なら範囲外
OUT_OF_SCOPE = (
    'ダリア', '盆栽', 'ボンサイ', '観察会', '講座', 'ポトス',
    '苔テラリウム', 'テラリウムのみ', '援農', '商談会', '卸し',
)


# 照合の役に立たない共通語。この分野の名前に頻出するので、
# 1語当たっただけでは別イベントを同一と誤認する。
# 実例: 「GREEN HOLIC in KARIYA」の green だけで
# 「Sakuya Green Jam」に一致してしまった(2026-08-27の自己テストで検出)。
# 迷ったら generic に入れる。取りこぼしを見逃すより、
# 候補に多めに出して裏取りで落とすほうが安全。
GENERIC = {
    'vol', 'the', 'and', 'plants', 'plant', 'event', 'events', 'in', 'of',
    'green', 'greens', 'garden', 'gardens', 'botanical', 'botanic',
    'flower', 'flowers', 'market', 'marche', 'market', 'festa', 'fest',
    'festival', 'show', 'jam', 'fes', 'shop', 'store', 'popup', 'pop',
    'sale', 'expo', 'club', 'works', 'factory', 'nursery', 'farm',
    'tokyo', 'japan', 'autumn', 'spring', 'summer', 'winter',
    'day', 'days', 'park', 'base', 'house', 'life', 'style', 'world',
    'イベント', '開催', '販売', '販売会', '即売', '即売会', '出店',
    'マルシェ', '展示', '展示会', 'フェス', 'フェスタ', '第', '記念',
    'プランツ',
    '2026', '2027', '2025',
}


def norm(s):
    """比較用に正規化する。全角半角・記号・空白の揺れを潰す。"""
    s = unicodedata.normalize('NFKC', s or '').lower()
    return re.sub(r'[^0-9a-z぀-ヿ㐀-鿿]', '', s)


def tokens(name):
    """イベント名から照合用の特徴語を取る。

    3文字以上の連続した仮名・漢字・英数のかたまり。
    「第1回」「2026」「vol」のような共通語は照合の役に立たないので落とす。
    """
    raw = re.findall(r'[぀-ヿ㐀-鿿A-Za-z0-9]{3,}',
                     unicodedata.normalize('NFKC', name or ''))
    out = []
    for t in raw:
        low = t.lower()
        if re.fullmatch(r'\d+', t):
            continue
        if low in GENERIC:
            continue
        out.append(low)
    return out


def in_scope(title):
    n = norm(title)
    if not any(norm(k) in n for k in IN_SCOPE):
        return False
    if any(norm(k) in n for k in OUT_OF_SCOPE):
        return False
    return True


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA,
                                              'Accept-Language': 'ja'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode('utf-8', 'replace')


def extract_titles(html):
    """記事リンクのテキストを重複なしで取る。

    LEAFLA の日付別ページは、その日のイベントを /blogs/media/topics… への
    リンクで並べている。リンク文字列に「イベント名＋会場」が入る。
    """
    titles = []
    seen = set()
    for m in re.finditer(
            r'<a\b[^>]*href="[^"]*/blogs/media/topics[^"]*"[^>]*>(.*?)</a>',
            html, re.S | re.I):
        txt = re.sub(r'<[^>]+>', ' ', m.group(1))
        txt = re.sub(r'\s+', ' ', txt).strip()
        if txt and txt not in seen:
            seen.add(txt)
            titles.append(txt)
    return titles


def load_json(path, default):
    try:
        with open(os.path.join(REPO, path), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def build_index():
    """掲載済み・見送り済みの照合表を作る。

    掲載済みは「その日に会期がかかっているもの」だけを見る。
    同名のシリーズが別の日にあるとき、別回を掲載済みと誤認しないため。
    """
    d = load_json('events.json', [])
    evs = d['events'] if isinstance(d, dict) else d
    by_day = {}
    for e in evs:
        s = (e.get('date') or '')[:10]
        t = (e.get('dateEnd') or e.get('date') or '')[:10]
        if not s:
            continue
        try:
            ds = datetime.strptime(s, '%Y-%m-%d').date()
            de = datetime.strptime(t or s, '%Y-%m-%d').date()
        except ValueError:
            continue
        cur = ds
        while cur <= de and (cur - ds).days <= 400:
            by_day.setdefault(cur.isoformat(), []).append(e)
            cur += timedelta(days=1)

    rej = load_json('rejected-events.json', {})
    rejected = [(i.get('name') or '') for i in (rej.get('items') or [])]
    return by_day, rejected


def matches(title, name):
    """候補のリンク文字列が、こちらのイベント名を指しているか。

    LEAFLA の文字列は「<会場>で<イベント名>を開催、…」のような文なので、
    こちらの名前の特徴語がその中に出てくるかで見る。
    2語以上一致、または5文字以上の語が1つ一致したら同じとみなす。
    """
    n = norm(title)
    ts = tokens(name)
    if not ts:
        return False
    hit = [t for t in ts if norm(t) and norm(t) in n]
    if len(hit) >= 2:
        return True
    return any(len(t) >= 5 for t in hit)


def sweep(days, sleep=0.7):
    by_day, rejected = build_index()
    gaps, errors, stats = [], [], {'fetched': 0, 'candidates': 0,
                                   'in_scope': 0, 'covered': 0,
                                   'known_rejected': 0}
    today = date.today()
    for i in range(days):
        d = today + timedelta(days=i)
        key = d.isoformat()
        url = BASE + key
        try:
            html = fetch(url)
            stats['fetched'] += 1
        except urllib.error.HTTPError as e:
            # 先の日付はページが無い。404は異常ではない
            if e.code != 404:
                errors.append(f'{key}: HTTP {e.code}')
            continue
        except Exception as e:                      # noqa: BLE001
            errors.append(f'{key}: {type(e).__name__} {e}')
            continue

        titles = extract_titles(html)
        if not titles:
            errors.append(f'{key}: リンクを1件も抽出できなかった'
                          f'(ページ構造が変わった可能性 / {len(html)}バイト)')
            continue
        stats['candidates'] += len(titles)

        for t in titles:
            if not in_scope(t):
                continue
            stats['in_scope'] += 1
            if any(matches(t, e.get('name', '')) or
                   matches(t, e.get('venue') or e.get('location') or '')
                   for e in by_day.get(key, [])):
                stats['covered'] += 1
                continue
            if any(matches(t, r) for r in rejected):
                stats['known_rejected'] += 1
                continue
            gaps.append({'date': key, 'title': t[:180]})
        time.sleep(sleep)
    return gaps, errors, stats


# ---- 自己テスト（通信しない。判定ロジックだけ確かめる） -------------------
SELFTEST_TITLES = [
    'GREENHOLICinKARIYA2026が刈谷市で開催、アガベや塊根植物と園芸用品を販売',
    'Sakuya Green Jam 5が植物販売会を開催、観葉植物や多肉植物などが咲くやこの花館に集結',
    'コーナンgardensumekitaが2周年イベント2026を開催、三浦園芸とカクト・ロコが珍奇植物を即売',
    '多肉渡来記近江・竜王の章2026が開催、苗や作品の出店者がアグリパーク竜王に集結',
    'ワイルドプランツ路地裏のギボウシが第1回ボタニカルX2026を開催、珍しい植物と手作り作品を坂東市で販売',
    '長野大岡ひなたダリア園2026が開園、800株のダリアが咲く天空の花園を公開',
    'My Bonsai, My Care2026がgarage TOYOHASHIで開催、ミニ盆栽作りと持ち込みのお手入れ講座を実施',
    'THEポトスチャレンジ2026がSputterで開催、ゴールデンポトスの葉っぱの大きさを競う育成企画',
    '第52回薬用植物観察会2026秋の観察会を富山大学薬学部附属薬用植物園が開催、園内観察ツアーと特設展示を実施予定',
    '毎週末のプチ援農2026があんばい農園で開催、自然栽培落花生畑の草取り参加者を募集',
    'ちびさぼ卸し商談会2026年8月と9月に開催、たまちゃんず農園で仕入れを直接相談',
    'Jolie Nurseryが長野初上陸、ホームセンタームサシ須坂店でインドアプランツ即売会を開催',
    '花と獣いろとかたち2026が札幌芸術の森で開催、動植物を主題にした絵画彫刻写真を展示',
]
SELFTEST_EXPECT_SCOPE = [
    True, True, True, True, False,
    False, False, False, False, False, False, False, False,
]


def self_test():
    ok = True
    print('--- 対象判定（範囲内/範囲外） ---')
    for t, want in zip(SELFTEST_TITLES, SELFTEST_EXPECT_SCOPE):
        got = in_scope(t)
        mark = 'OK ' if got == want else '★NG'
        if got != want:
            ok = False
        print(f'  {mark} 範囲内={got!s:5} 期待={want!s:5} {t[:52]}')

    print('\n--- 掲載済みとの照合 ---')
    cases = [
        ('GREENHOLICinKARIYA2026が刈谷市で開催、アガベや塊根植物と園芸用品を販売',
         'GREEN HOLIC in KARIYA 2026', True),
        ('ワイルドプランツ路地裏のギボウシが第1回ボタニカルX2026を開催',
         '第1回 ボタニカルX', True),
        ('多肉渡来記近江・竜王の章2026が開催、アグリパーク竜王に集結',
         '多肉渡来記 近江・竜王の章', True),
        ('Sakuya Green Jam 5が植物販売会を開催、咲くやこの花館に集結',
         'GREEN HOLIC in KARIYA 2026', False),
        ('コーナンgardensumekitaが2周年イベント2026を開催',
         '第1回 ボタニカルX', False),
    ]
    for title, name, want in cases:
        got = matches(title, name)
        mark = 'OK ' if got == want else '★NG'
        if got != want:
            ok = False
        print(f'  {mark} 一致={got!s:5} 期待={want!s:5} {name[:28]}')

    print('\n--- リンク抽出 ---')
    html = ('<a href="/blogs/media/topics1">アガベ即売会2026を開催</a>'
            '<a href="/blogs/media/topics2"><span>多肉</span>マルシェ</a>'
            '<a href="/other">対象外リンク</a>'
            '<a href="/blogs/media/topics1">アガベ即売会2026を開催</a>')
    got = extract_titles(html)
    want = ['アガベ即売会2026を開催', '多肉 マルシェ']
    mark = 'OK ' if got == want else '★NG'
    if got != want:
        ok = False
    print(f'  {mark} {got}')

    print('\n結果:', 'すべて通過' if ok else '★失敗あり')
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=45)
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--sleep', type=float, default=0.7)
    args = ap.parse_args()

    if args.self_test:
        return self_test()

    gaps, errors, stats = sweep(args.days, args.sleep)
    payload = {
        '_note': ('他所(LEAFLAの日付別ページ)に出ていて当サイトに無いイベントの候補。'
                  'scripts/coverage-sweep.py が毎日書き出す。'
                  '一次情報で裏取りして、掲載するか rejected-events.json に落とす。'
                  'errors が空でないときは巡回そのものが失敗しているので、'
                  'gaps が0件でも「取りこぼしなし」とは言えない。'),
        'sweptOn': date.today().isoformat(),
        'daysAhead': args.days,
        'stats': stats,
        'errors': errors,
        'gaps': gaps,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f"取得できた日: {stats['fetched']} / 候補 {stats['candidates']}件")
    print(f"  うち対象: {stats['in_scope']}件 "
          f"(掲載済み {stats['covered']} / 見送り済み {stats['known_rejected']})")
    print(f"★ 取りこぼし候補: {len(gaps)}件")
    for g in gaps[:20]:
        print(f"    {g['date']} {g['title'][:70]}")
    if errors:
        print(f"⚠ 巡回できなかった日: {len(errors)}")
        for e in errors[:10]:
            print(f"    {e}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
