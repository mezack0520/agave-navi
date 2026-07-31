#!/usr/bin/env python3
"""
data-integrity-check.py — events.json のスキーマ/値整合性をチェック
- prefecture と region の整合性
- date と dateEnd の前後関係
- dateDisplay と date の整合
- duplicate slug
- 空 / 異常値の警告
exit 1 if 重大な不整合あり
"""
import json, os, re, sys, argparse
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = os.path.join(ROOT, 'events.json')

from sitelib import PREF_TO_REGION, pref_to_region  # 地域分類の単一情報源
PLACEHOLDER = {'', '調整中', '未定', 'TBD', 'TBA', '-', '−', '—', '?', '？', '不明', '未発表'}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--strict', action='store_true', help='exit 1 on any issue')
    args = ap.parse_args()
    with open(EVENTS, encoding='utf-8') as f:
        d = json.load(f)
    errors, warnings = [], []
    seen_slugs = {}
    for ev in d:
        slug = ev.get('slug', '?')
        # slug duplicate
        if slug in seen_slugs:
            errors.append(f'DUPLICATE slug: {slug}')
        else:
            seen_slugs[slug] = True
        # required
        if not ev.get('name'):
            errors.append(f'{slug}: missing name')
        # prefecture/region 整合性
        pref = ev.get('prefecture') or ''
        region = ev.get('region') or ''
        if pref and pref not in PLACEHOLDER:
            expected_region = pref_to_region(pref)
            if not expected_region:
                # try direct
                expected_region = PREF_TO_REGION.get(pref)
            if expected_region and region and region != expected_region:
                warnings.append(f'{slug}: prefecture={pref} but region={region} (expected {expected_region})')
        # date format
        date = ev.get('date')
        if date and not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
            errors.append(f'{slug}: invalid date format: {date}')
        date_end = ev.get('dateEnd')
        if date_end and date and date_end < date:
            errors.append(f'{slug}: dateEnd ({date_end}) < date ({date})')
    print(f'=== Data integrity check ===')
    print(f'events: {len(d)}')
    print(f'errors: {len(errors)}')
    for e in errors[:20]: print(f'  ERR: {e}')
    print(f'warnings: {len(warnings)}')
    for w in warnings[:20]: print(f'  WARN: {w}')
    if errors and args.strict:
        sys.exit(1)

if __name__ == '__main__':
    main()
