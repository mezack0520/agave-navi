#!/usr/bin/env python3
"""
issue-to-candidates.py — GitHub Issues (label='auto-crawl' or 'auto-enrich') から
イベント候補を抽出して candidates.json に蓄積。
SKILL.md / 人間が手動レビューする際の入力データ。
"""
import os, json, re, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAND = os.path.join(ROOT, 'staging', 'candidates.json')

def fetch_issues(repo='mezack0520/agave-navi', label='auto-crawl', token=None):
    url = f'https://api.github.com/repos/{repo}/issues?state=open&labels={label}&per_page=20'
    req = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json',
        **({'Authorization': f'token {token}'} if token else {}),
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception as e:
        print(f'fetch error: {e}'); return []

def extract_candidates(body):
    """簡易: イベント名らしき行 + URL を抽出"""
    if not body: return []
    candidates = []
    # markdown header または bullet と URL の組
    for m in re.finditer(r'(?:^|\n)#+\s*(.+?)(?:\n|$).*?(https?://\S+)', body, re.DOTALL):
        name = m.group(1).strip()[:100]
        url = m.group(2).rstrip(',.)')
        if name and url and 'agave-navi.com' not in url:
            candidates.append({'name': name, 'url': url})
    return candidates[:30]

def main():
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    all_cand = []
    for label in ['auto-crawl', 'auto-enrich']:
        issues = fetch_issues(label=label, token=token)
        for iss in issues:
            cand = extract_candidates(iss.get('body', ''))
            for c in cand:
                c['source_issue'] = iss.get('html_url', '')
                c['issue_label'] = label
            all_cand.extend(cand)
    # dedupe by URL
    seen = set(); uniq = []
    for c in all_cand:
        if c['url'] not in seen:
            seen.add(c['url']); uniq.append(c)
    os.makedirs(os.path.dirname(CAND), exist_ok=True)
    with open(CAND, 'w', encoding='utf-8') as f:
        json.dump(uniq, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'staging/candidates.json: {len(uniq)} candidates from open issues')

if __name__ == '__main__':
    main()
