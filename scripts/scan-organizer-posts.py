#!/usr/bin/env python3
"""scan-organizer-posts.py — 主催の最近の投稿に出る「当サイトに無い先の日付」を、CI の信号より広く並べる。

    python3 scripts/scan-organizer-posts.py            # 投稿から14日以内・先150日以内
    python3 scripts/scan-organizer-posts.py --days 21

なぜあるか(2026-10-07):
  ig-organizer-watch.py の signals.unlisted は「主催が自分の催しを告知している投稿」だけを数える
  (_looks_like_own_announcement: 植物の語があり、開催/日時/日程/会場 のうち2語以上を含み、
  出店側の言い回しを含まない)。初回(2026-09-23)の40件の雑音を落とすための絞りで、
  10-07 の signals.unlisted は0件だった。ところが同じ organizer-posts.json を絞らずに読むと、
  掲載相当が10件出た。
    - 「告知になります」「場所」で書く主催(和〜なごみ〜 のナゴリバ舞鶴・The販売会 秋の部)
    - 日付を「2026.11.29」と書く主催(GREEN SANTA のサンタフェ vol.20)。month_days はこの形を読まない
    - 出店者一覧と【場所】だけの告知(ピクニックガーデン vol.26)
  CI の絞りを広げると、毎朝の候補にワークショップや店頭フェアが混ざる(10-07 に測った:
  _OWN_EVENT に「場所」を足すと新しく出る6件のうち4件がワークショップ・値引きフェア)。
  そこで CI は狭いまま、朝のタスク(agave-event-update)がこの一覧を目で読む。

出すもの:
  投稿から --days 日以内、出店側の言い回し(ig-organizer-watch._VENDOR_SIDE)を含まない投稿の、
  今日から --ahead 日以内の日付のうち、その主催の掲載済みの回の会期にも、
  同じ日の掲載・見送り(ig-organizer-watch.known_elsewhere)にも当たらないもの。
  CI の信号に既に出ているもの(_looks_like_own_announcement を通るもの)は「CI」と印を付ける。
読み方:
  1行ずつ本文の抜粋を見て、主催の告知なら一次情報として裏取りに進む。ワークショップ単独・値引きだけ・
  店の営業日案内は listing-policy の規則で見送る(多ければ rejected-events.json に記録して翌日から消す)。
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
import sitelib  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    'igwatch', os.path.join(REPO, 'scripts', 'ig-organizer-watch.py'))
w = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w)

# 年つきの点区切り「2026.11.29」。年が付かない「11.29」は鉢のサイズ(3.5号)や
# 小数と区別できないので読まない
_DOT_YMD = re.compile(r'(?<!\d)20\d\d\s*[.．]\s*(\d{1,2})\s*[.．]\s*(\d{1,2})(?!\d)')


def month_days_wide(text):
    out = set(w.month_days(text))
    for m in _DOT_YMD.finditer(text):
        if w._DEADLINE.search(text[m.end():m.end() + 12].split('\n')[0]):
            continue
        if w._DEADLINE_BEFORE.search(text[max(0, m.start() - 10):m.start()]):
            continue
        mo, d = int(m.group(1)), int(m.group(2))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            out.add((mo, d))
    return out


def known_days(org_events):
    days = set()
    for e in org_events:
        days |= w.event_md(e)
        try:
            a = datetime.strptime(e['date'], '%Y-%m-%d')
            b = datetime.strptime(e.get('dateEnd') or e['date'], '%Y-%m-%d')
        except (KeyError, ValueError):
            continue
        if (b - a).days <= 62:
            d = a
            while d <= b:
                days.add((d.month, d.day))
                d += timedelta(days=1)
    return days


def scan(days_back, ahead):
    with open(os.path.join(REPO, 'organizer-posts.json'), encoding='utf-8') as f:
        results = json.load(f).get('results') or {}
    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    with open(os.path.join(REPO, 'rejected-events.json'), encoding='utf-8') as f:
        rejected = json.load(f).get('items') or []
    today = datetime.strptime(sitelib.today_jst(), '%Y-%m-%d')
    allorg = w.all_by_org(events)
    day_index, rejected_by_day = w.day_indexes(events, rejected)
    rows = []
    for user, r in sorted(results.items()):
        if not r.get('ok'):
            continue
        known = known_days(allorg.get(user.lower(), []))
        for p in r.get('posts') or []:
            try:
                posted = datetime.strptime((p.get('timestamp') or '')[:10], '%Y-%m-%d')
            except ValueError:
                continue
            if (today - posted).days > days_back:
                continue
            cap = w.norm(p.get('caption'))
            if not cap or any(v in cap for v in w._VENDOR_SIDE):
                continue
            future = []
            for (mo, d) in sorted(month_days_wide(cap) - known):
                y = today.year if (mo, d) >= (today.month, today.day) else today.year + 1
                try:
                    cand = datetime(y, mo, d)
                except ValueError:
                    continue
                if 0 <= (cand - today).days <= ahead:
                    iso = cand.strftime('%Y-%m-%d')
                    if not w.known_elsewhere(cap, iso, day_index, rejected_by_day):
                        future.append(iso)
            if future:
                code = (re.search(r'/(?:p|reel)/([A-Za-z0-9_-]+)', p.get('permalink') or '') or [None, ''])[1]
                rows.append((future[0], future, user, code, posted.strftime('%Y-%m-%d'),
                             'CI' if w._looks_like_own_announcement(cap) else '  ',
                             re.sub(r'\s+', ' ', cap)[:140]))
    return sorted(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, default=14, help='投稿から何日以内を読むか')
    ap.add_argument('--ahead', type=int, default=150, help='今日から何日先までの日付を出すか')
    a = ap.parse_args()
    rows = scan(a.days, a.ahead)
    for first, dates, user, code, posted, ci, excerpt in rows:
        print(f'{first} {ci} @{user} {code} ({posted}) {",".join(d[5:] for d in dates)} | {excerpt}')
    print(f'scan-organizer-posts: {len(rows)} 投稿(うち CI の信号の対象 '
          f'{sum(1 for r in rows if r[5] == "CI")})', file=sys.stderr)


if __name__ == '__main__':
    main()
