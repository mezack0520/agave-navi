#!/usr/bin/env python3
"""test-time-parity.py — 時間軸の規則が Python と JS で一致するかを見る。

`status-auto.js` の AEN_TIME は `sitelib.py` の event_phase /
list_sort_key / is_long_run と**同じ規則の別実装**。ブラウザで動く以上
JS 側は消せないが、同じ規則が2つあることに変わりはない。

2026-08-29、JS 側の todayJST() だけが壊れて、JSTの閲覧者に
0:00〜9:00 のあいだ「本日開催」が「明日開催」と出た。
`test-date-boundary.js` は JS 側だけを4タイムゾーンで見るので、
**両者がずれたことは見ていなかった。**ここで突き合わせる。

JS は status-auto.js の TIME-RULES マーカーの範囲だけを切り出して
node で評価する。window / document には触らない範囲なのでそのまま動く。

build-all.sh から呼ぶ。ずれたら非0で終了してビルドを止める。
"""
import json
import os
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
import sitelib   # noqa: E402

TODAY = '2026-09-10'

# 境界をまたぐ形を並べる。1日ずれると答えが変わる組み合わせを厚めに。
CASES = [
    ('', '', '無日付'),
    ('2026-09-10', '', '今日1日'),
    ('2026-09-10', '2026-09-10', '今日1日(終了日あり)'),
    ('2026-09-09', '2026-09-10', '昨日から今日まで'),
    ('2026-09-09', '2026-09-09', '昨日で終了'),
    ('2026-09-11', '', '明日'),
    ('2026-09-08', '2026-09-12', '会期5日の途中'),
    ('2026-09-10', '2026-09-13', '今日から4日'),
    ('2026-09-10', '2026-09-12', '今日から3日'),
    ('2026-08-27', '2026-08-27', '14日前ちょうど'),
    ('2026-08-26', '2026-08-26', '15日前'),
    ('2026-12-31', '2027-01-02', '年をまたぐ'),
    ('2027-03-01', '', 'ずっと先'),
]

JS_HARNESS = r'''
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const a = src.indexOf('/* TIME-RULES:START');
const b = src.indexOf('/* TIME-RULES:END */');
if (a < 0 || b <= a) { console.error('TIME-RULES のマーカーが無い'); process.exit(2); }
const block = src.slice(a, b);
// block は `var AEN_TIME = (function(){...})();` を含む。
// 自分のスコープで実行して返させる(eval だと外側の宣言と衝突する)
const AEN_TIME = new Function(block + '\nreturn AEN_TIME;')();
const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const today = process.argv[4];
const out = cases.map(c => ({
  phase: AEN_TIME.phase(c.date, c.dateEnd, today),
  days: AEN_TIME.days(c.date, c.dateEnd),
  longRun: AEN_TIME.isLongRun(c.date, c.dateEnd),
  sortKey: AEN_TIME.listSortKey(c.date, c.dateEnd, today, c.name),
}));
console.log(JSON.stringify({
  LONG_RUN_DAYS: AEN_TIME.LONG_RUN_DAYS,
  PAST_KEEP_DAYS: AEN_TIME.PAST_KEEP_DAYS,
  results: out,
}));
'''


def main():
    events = [{'date': d, 'dateEnd': de, 'name': label}
              for d, de, label in CASES]
    want = []
    for e in events:
        want.append({
            'phase': sitelib.event_phase(e, TODAY),
            'days': sitelib.event_days(e),
            'longRun': sitelib.is_long_run(e),
            'sortKey': list(sitelib.list_sort_key(e, TODAY)),
        })

    with tempfile.TemporaryDirectory() as tmp:
        cj = os.path.join(tmp, 'cases.json')
        hj = os.path.join(tmp, 'harness.js')
        with open(cj, 'w', encoding='utf-8') as f:
            json.dump(events, f, ensure_ascii=False)
        with open(hj, 'w', encoding='utf-8') as f:
            f.write(JS_HARNESS)
        try:
            raw = subprocess.run(
                ['node', hj, os.path.join(REPO, 'status-auto.js'), cj, TODAY],
                capture_output=True, text=True, check=True).stdout
        except FileNotFoundError:
            print('::warning::node が無いため test-time-parity をスキップしました')
            return 0
        except subprocess.CalledProcessError as e:
            print('JS 側が落ちた:', e.stderr.strip(), file=sys.stderr)
            return 1
    got = json.loads(raw)

    bad = 0
    if got['LONG_RUN_DAYS'] != sitelib.LONG_RUN_DAYS:
        print(f"✗ LONG_RUN_DAYS: py={sitelib.LONG_RUN_DAYS} js={got['LONG_RUN_DAYS']}")
        bad += 1
    if got['PAST_KEEP_DAYS'] != sitelib.PAST_KEEP_DAYS:
        print(f"✗ PAST_KEEP_DAYS: py={sitelib.PAST_KEEP_DAYS} js={got['PAST_KEEP_DAYS']}")
        bad += 1
    for (d, de, label), w, g in zip(CASES, want, got['results']):
        for key in ('phase', 'days', 'longRun', 'sortKey'):
            if w[key] != g[key]:
                print(f'✗ {label} ({d}〜{de or d}) {key}: py={w[key]!r} js={g[key]!r}')
                bad += 1
    if bad:
        print(f'\n時間軸の規則が Python と JS でずれている: {bad}件')
        print('  sitelib.py と status-auto.js の TIME-RULES を突き合わせること')
        return 1
    print(f'time-parity: {len(CASES)}件すべて一致 (phase / days / longRun / sortKey)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
