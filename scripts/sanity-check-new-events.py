#!/usr/bin/env python3
"""
sanity-check-new-events.py — new-events.json の品質チェック。
明らかに植物イベントでないエントリ(チケット販売系URL等)を除外する。

Usage:
  python3 scripts/sanity-check-new-events.py [--in <path>] [--strict]

--strict: 1件でも reject があれば exit code 1 で失敗
"""
import argparse, json, os, re, sys

# チケット販売・コンサート系ドメイン → 植物イベントの url であるはずがない
TICKETING_DOMAINS = (
    'l-tike.com', 'lawsonticket.com', 'eplus.jp',
    'kyodo-osaka.co.jp', 'kyodo-tokyo.co.jp',
    'pia.jp', 'ticket.rakuten.co.jp', 'cnplayguide',
    'tixee.tv', 'zaiko.io', 'streetdance.jp',
    'fan-club', 'fanclub',
)
# 植物と無関係の有名イベント公式ドメイン(名前類似の誤リンク事故防止。
# 例: HAPPY SMILE→goodsmilefest.com 誤登録 2026-07-06検出)
UNRELATED_EVENT_DOMAINS = (
    'goodsmilefest.com', 'comiket.co.jp', 'wonfes.jp',
    'designfesta.com', 'tokyogameshow.jp',
)
# Aggregator (データ汚染源) → 同じく url にしてはいけない
AGGREGATOR_DOMAINS = (
    'nextmeet.app', 'botanical-zone.tokyo', 'leaf-laboratory.com',
    'tochinavi.net', 'pukubook.jp', 'fukuoka-now.com', 'churatoku.net', 'agavemaniacs.com',
)

def url_domain(u):
    m = re.match(r'https?://([^/]+)', (u or '').lower())
    return m.group(1) if m else ''

def _normalize(s):
    """イベント名比較用に正規化: 全半角統一/記号除去/小文字化/Vol番号維持"""
    if not s: return ''
    import re, unicodedata
    s = unicodedata.normalize('NFKC', s)
    s = s.lower()
    s = re.sub(r'[\s　]+', '', s)
    s = re.sub(r'[!！?？「」『』()（）"\'-]+', '', s)
    return s


def _existing_events():
    """events.json をロードして既存event一覧を返す(重複検出用キャッシュ)"""
    import json, os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = os.path.join(root, 'events.json')
    if not os.path.exists(p): return []
    with open(p, encoding='utf-8') as f:
        return json.load(f)


_EXISTING = None

def reasons(ev):
    rs = []
    url = ev.get('url') or ''
    src = ev.get('sourceUrl') or ''
    full = (url + ' ' + src).lower()
    for d in TICKETING_DOMAINS:
        if d in full:
            rs.append(f'ticketing-domain: {d}')
            break
    for d in UNRELATED_EVENT_DOMAINS:
        if d in full:
            rs.append(f'unrelated-event-domain: {d}')
    for d in AGGREGATOR_DOMAINS:
        if d in full:
            rs.append(f'aggregator-domain: {d}')
            break
    if not ev.get('slug'):
        rs.append('missing slug')
    if not ev.get('name'):
        rs.append('missing name')

    # 重複検出: name+venue+date が類似する既存イベントを探す
    global _EXISTING
    if _EXISTING is None:
        _EXISTING = _existing_events()
    new_name_norm = _normalize(ev.get('name', ''))
    new_venue_norm = _normalize(ev.get('venue', '') or ev.get('location', ''))
    new_date = ev.get('date', '')
    new_slug = ev.get('slug', '')
    for ee in _EXISTING:
        if ee.get('slug') == new_slug:
            rs.append(f'slug already exists: {new_slug}')
            break
        ex_name_norm = _normalize(ee.get('name', ''))
        ex_venue_norm = _normalize(ee.get('venue', '') or ee.get('location', ''))
        ex_date = ee.get('date', '')
        # 同名+同日 → 重複
        if ex_name_norm and ex_name_norm == new_name_norm and ex_date == new_date and new_date:
            rs.append(f'duplicate (name+date matches existing slug={ee.get("slug")})')
            break
        # 同会場+同日 + 名前部分一致 → 高確度の重複
        if (ex_venue_norm and ex_venue_norm == new_venue_norm and ex_date == new_date and new_date
            and ex_name_norm and new_name_norm
            and (ex_name_norm in new_name_norm or new_name_norm in ex_name_norm)):
            rs.append(f'likely-duplicate (venue+date+partialname matches slug={ee.get("slug")})')
            break
    return rs

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='inp', default='new-events.json')
    ap.add_argument('--strict', action='store_true')
    args = ap.parse_args()

    if not os.path.exists(args.inp):
        print(f'No file: {args.inp}'); return 0

    with open(args.inp, encoding='utf-8') as f:
        events = json.load(f)
    if isinstance(events, dict):
        events = [events]

    kept, rejected = [], []
    for ev in events:
        rs = reasons(ev)
        if rs:
            rejected.append((ev.get('slug','?'), ev.get('name','?'), rs))
        else:
            kept.append(ev)

    print(f'Total: {len(events)}, OK: {len(kept)}, Rejected: {len(rejected)}')

    # ウォッチ対象に載るかの確認。裸の投稿URL(instagram.com/p/XXXX/)だけだと
    # 主催者ハンドルが取れず自己拡張ループから漏れる。拒否はせず警告する。
    import re as _re
    _IG = _re.compile(r'instagram\.com/([A-Za-z0-9_.]+)/?')
    _NON = {'p', 'reel', 'reels', 'tv', 'explore', 'stories', 'accounts'}
    for ev in kept:
        if (ev.get('organizerIg') or '').strip():
            continue
        urls = [(ev.get(k) or '') for k in ('instagramUrl', 'sourceUrl', 'url')]
        if not any('instagram.com' in u for u in urls):
            continue
        if any((_IG.search(u) and _IG.search(u).group(1).lower() not in _NON) for u in urls):
            continue
        print(f"  WARNING {ev.get('slug')}: IGのURLから主催者ハンドルが取れません。"
              f"organizerIg に主催者アカウント名を入れないとウォッチ対象になりません")
    # 名称の先頭が曜日語 → Googleの画像OCRが日付の曜日を名前に食い込ませた疑い。
    # 例: "2026.10.18. SUN GREEN BASE MARKET" の SUN は 10/18(日) の曜日。
    # date の曜日と一致したときだけ警告する(SUNSET等の正当な名前で鳴らないよう完全一致に限る)。
    import datetime as _dt
    _WD = ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT', 'SUN')
    for ev in kept:
        head = (ev.get('name') or '').strip().split(' ')[0].upper().strip('.,:')
        if head not in _WD:
            continue
        try:
            wd = _WD[_dt.date.fromisoformat(ev.get('date', '')).weekday()]
        except ValueError:
            continue
        if head == wd:
            print(f"  WARNING {ev.get('slug')}: 名称が曜日語 '{head}' で始まり date の曜日と一致します。"
                  f"Googleの画像OCRが日付の曜日を名前に食い込ませた可能性があります。"
                  f"主催者の告知で正式名称を確認してください")

    for slug, name, rs in rejected:
        print(f'  REJECT: {slug} ({name}) — {rs}')

    # Overwrite with kept-only
    if rejected:
        with open(args.inp, 'w', encoding='utf-8') as f:
            json.dump(kept, f, ensure_ascii=False, indent=2); f.write('\n')
        print(f'Wrote filtered file: {args.inp}')

    if args.strict and rejected:
        sys.exit(1)

if __name__ == '__main__':
    main()
