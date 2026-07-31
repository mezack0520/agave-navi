#!/usr/bin/env python3
"""
issue-to-shops.py — Issue Form (.github/ISSUE_TEMPLATE/add-shop.yml) で submit された
店舗追加リクエストを取り込んで crawl-sources.json の type=shop エントリに追加する。

トリガー対象 Issue:
- label: 'add-source' または 'shop' を持つ open issue

完了したら Issue にコメントしてラベルを 'processed' に変更（クローズはしない、レビュー用）。
"""
import os, json, re, sys, urllib.request, urllib.parse

REPO = 'mezack0520/agave-navi'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CRAWL_SOURCES = os.path.join(ROOT, 'crawl-sources.json')


def github_api(method, path, token, data=None):
    url = f'https://api.github.com{path}'
    headers = {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'token {token}',
    }
    body = json.dumps(data).encode() if data is not None else None
    if body:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, headers=headers, method=method, data=body)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode('utf-8')) if r.status != 204 else None


def fetch_open_shop_issues(token):
    """Get open issues with 'add-source' or 'shop' label, not yet 'processed'."""
    results = []
    for label in ['add-source', 'shop']:
        path = f'/repos/{REPO}/issues?state=open&labels={urllib.parse.quote(label)}&per_page=30'
        try:
            issues = github_api('GET', path, token)
            for iss in issues:
                if 'pull_request' in iss:
                    continue
                labels = [l['name'] for l in iss.get('labels', [])]
                if 'processed' in labels:
                    continue
                results.append(iss)
        except Exception as e:
            print(f'fetch error for label {label}: {e}', file=sys.stderr)
    # dedupe by issue number
    seen = set()
    uniq = []
    for iss in results:
        if iss['number'] not in seen:
            seen.add(iss['number'])
            uniq.append(iss)
    return uniq


def parse_issue_form(body):
    """
    Parse GitHub Issue Form output. Each field shows as:
        ### Field Label
        \n\n
        Value
        \n\n
    """
    if not body:
        return {}
    sections = re.split(r'(?m)^### ', body)
    fields = {}
    for sec in sections[1:]:
        lines = sec.split('\n', 1)
        if len(lines) < 2:
            continue
        label = lines[0].strip().lower()
        value = lines[1].strip()
        # Strip _No response_ etc.
        if value.startswith('_') and value.endswith('_'):
            value = ''
        fields[label] = value
    return fields


def field_match(fields, keywords):
    """Find first field whose label contains any of the keywords."""
    for label, value in fields.items():
        if any(k in label for k in keywords):
            return value
    return ''


REGION_MAP = {
    '北海道': '北海道', '東北': '東北', '関東': '関東',
    '中部・東海': '中部・東海', '中部': '中部・東海', '東海': '中部・東海',
    '北陸': '北陸', '関西': '関西', '中国': '中国',
    '四国': '四国', '九州・沖縄': '九州', '九州': '九州', '沖縄': '九州',
}


def build_shop_entry(issue):
    fields = parse_issue_form(issue.get('body', ''))
    name = field_match(fields, ['店舗名', 'name'])
    url = field_match(fields, ['url', '巡回url', '巡回 url'])
    coverage = field_match(fields, ['地域', 'coverage'])
    prefecture = field_match(fields, ['都道府県', 'prefecture'])
    focus = field_match(fields, ['取り扱い', 'focus'])
    frequency = field_match(fields, ['頻度', 'frequency'])
    instagram = field_match(fields, ['instagram'])
    notes = field_match(fields, ['補足', 'notes'])

    if not name or not url:
        return None, 'missing name or url'

    # Normalize
    if frequency not in ('weekly', 'monthly'):
        frequency = 'monthly'
    coverage_norm = REGION_MAP.get(coverage.strip(), coverage)

    notes_parts = []
    if prefecture:
        notes_parts.append(f'所在: {prefecture}')
    if instagram:
        notes_parts.append(f'Instagram: {instagram}')
    if notes:
        notes_parts.append(notes)
    notes_parts.append(f'(via Issue #{issue["number"]})')

    entry = {
        'name': name,
        'url': url.strip(),
        'type': 'shop',
        'coverage': coverage_norm,
        'focus': focus or '多肉植物・アガベ・塊根植物',
        'frequency': frequency,
        'notes': ' / '.join(notes_parts),
    }
    return entry, None


def comment_and_label(issue_num, token, comment, add_label='processed'):
    try:
        github_api('POST', f'/repos/{REPO}/issues/{issue_num}/comments', token,
                   {'body': comment})
        github_api('POST', f'/repos/{REPO}/issues/{issue_num}/labels', token,
                   {'labels': [add_label]})
    except Exception as e:
        print(f'  comment/label error: {e}', file=sys.stderr)


def main():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    if not token:
        print('No GH_TOKEN, skipping.', file=sys.stderr)
        sys.exit(0)

    issues = fetch_open_shop_issues(token)
    print(f'Open shop addition issues: {len(issues)}')

    if not issues:
        return

    with open(CRAWL_SOURCES, encoding='utf-8') as f:
        cs = json.load(f)
    existing_urls = {s.get('url') for s in cs.get('sources', [])}

    added = 0
    for iss in issues:
        entry, err = build_shop_entry(iss)
        if err:
            print(f'  #{iss["number"]}: skipped — {err}')
            continue
        if entry['url'] in existing_urls:
            print(f'  #{iss["number"]}: skipped — already in crawl-sources.json')
            comment_and_label(iss['number'], token,
                              f'既に `crawl-sources.json` に同じURLが登録されています。スキップしました。')
            continue
        cs['sources'].append(entry)
        existing_urls.add(entry['url'])
        added += 1
        print(f'  #{iss["number"]}: added — {entry["name"]} ({entry["coverage"]})')
        comment_and_label(iss['number'], token,
                          f'✅ `crawl-sources.json` に追加しました。\n\n```json\n{json.dumps(entry, ensure_ascii=False, indent=2)}\n```\n\n次回の weekly-discovery 実行時から巡回対象になります。')

    if added > 0:
        from datetime import date
        cs['lastUpdated'] = date.today().isoformat()
        with open(CRAWL_SOURCES, 'w', encoding='utf-8') as f:
            json.dump(cs, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f'\n✅ {added} shop(s) added to crawl-sources.json')
    else:
        print('No additions.')


if __name__ == '__main__':
    main()
