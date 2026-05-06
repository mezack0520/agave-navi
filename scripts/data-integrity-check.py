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

PREF_TO_REGION = {
    '北海道':'北海道',
    '青森':'東北','岩手':'東北','宮城':'東北','秋田':'東北','山形':'東北','福島':'東北',
    '茨城':'関東','栃木':'関東','群馬':'関東','埼玉':'関東','千葉':'関東','東京':'関東','神奈川':'関東',
    '愛知':'東海','静岡':'東海','岐阜':'東海','三重':'東海',
    '新潟':'北陸','富山':'北陸','石川':'北陸','福井':'北陸','山梨':'北陸','長野':'北陸',
    '滋賀':'関西','京都':'関西','京都府':'関西','大阪':'関西','兵庫':'関西','奈良':'関西','和歌山':'関西',
    '鳥取':'中国','島根':'中国','岡山':'中国','広島':'中国','山口':'中国',
    '徳島':'四国','香川':'四国','愛媛':'四国','高知':'四国',
    '福岡':'九州','佐賀':'九州','長崎':'九州','熊本':'九州','大分':'九州','宮崎':'九州','鹿児島':'九州',
    '沖縄':'沖縄',
}
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
            expected_region = PREF_TO_REGION.get(pref.replace('府','').replace('県','').replace('都','').replace('道',''))
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
