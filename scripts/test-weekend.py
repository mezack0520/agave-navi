#!/usr/bin/env python3
"""test-weekend.py — 今週末・来週末の範囲(sitelib.weekend_blocks)の検算。

週末は土日と、それに続く祝日のひとまとまり。トップの日程チップ、/this-weekend/、
日次メール、Instagram の週末投稿が同じ関数を読むので、ここが崩れると全部が同時にずれる。
日曜・連休の最終日・祝日の金曜・大型連休を、暦で確かめた答えと突き合わせる。

    python3 scripts/test-weekend.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402

# 今日 → (今週末, 来週末)
WEEKEND_CASES = {
    '2026-11-16': (('2026-11-21', '2026-11-23'), ('2026-11-28', '2026-11-29')),  # 月曜。次の週末は勤労感謝の日まで
    '2026-11-22': (('2026-11-21', '2026-11-23'), ('2026-11-28', '2026-11-29')),  # 日曜はその週末
    '2026-11-23': (('2026-11-21', '2026-11-23'), ('2026-11-28', '2026-11-29')),  # 連休の最終日もその週末
    '2026-11-24': (('2026-11-28', '2026-11-29'), ('2026-12-05', '2026-12-06')),
    '2026-12-31': (('2027-01-01', '2027-01-03'), ('2027-01-09', '2027-01-11')),  # 元日(金)から。成人の日まで
    '2027-04-26': (('2027-05-01', '2027-05-05'), ('2027-05-08', '2027-05-09')),  # 4/29(木)だけの祝日は週末にしない
    '2026-09-18': (('2026-09-19', '2026-09-23'), ('2026-09-26', '2026-09-27')),  # 国民の休日を挟む5連休
}

WEEKEND_LABELS = {
    ('2026-11-21', '2026-11-23', False): '11/21-23',
    ('2026-11-21', '2026-11-23', True): '11/21(土)〜23(月・祝)',
    ('2026-11-28', '2026-11-29', True): '11/28(土)・29(日)',
    ('2027-01-01', '2027-01-03', True): '1/1(金・祝)〜3(日)',
    ('2026-12-26', '2027-01-03', False): '12/26-1/3',
}


def main():
    bad = []
    for today, want in WEEKEND_CASES.items():
        got = tuple((s.isoformat(), e.isoformat()) for s, e in sitelib.weekend_blocks(today, 2))
        if got != want:
            bad.append(f'{today}: {got} (期待 {want})')
        if sitelib.weekend_span(today, 1) != sitelib.weekend_blocks(today, 2)[1]:
            bad.append(f'{today}: weekend_span と weekend_blocks が食い違う')
    for (s, e, dow), want in WEEKEND_LABELS.items():
        got = sitelib.span_md(s, e, dow=dow)
        if got != want:
            bad.append(f'span_md({s}, {e}, dow={dow}) = {got} (期待 {want})')
    if bad:
        print('test-weekend: NG')
        for b in bad:
            print('  ' + b)
        sys.exit(1)
    print(f'test-weekend: OK ({len(WEEKEND_CASES)}日・表記{len(WEEKEND_LABELS)}件)')


if __name__ == '__main__':
    main()
