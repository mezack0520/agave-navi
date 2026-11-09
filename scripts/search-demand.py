#!/usr/bin/env python3
"""search-demand.py — Search Console の検索語句から、需要があるのに頁が弱い語句・無い語句を出す(2026-11-09)。

    python3 scripts/search-demand.py              # 取得して search-demand.json を書く(Secret GSC_SA_KEY が要る)
    python3 scripts/search-demand.py --self-test  # 判定だけを合成データで確かめる

なぜ要るか: 何を作るか・どこを直すかを、検索の需要を見ずに決めていた。
週次の点検(site-health-check、プレイブック §6)がこのファイルを読んで手を打つ。

出すもの(直近28日。Search Console は数日遅れるので3日前まで):
  opportunities  表示回数が多いのに平均順位が4〜20位の語句。頁を直せば上がる見込みがある
  hubLanded      掲載済みの回の名前で検索されたのに、着地が一覧の頁になっている語句
  seriesLanded   3〜10回に当たるシリーズの名前で検索され、一覧の頁に着地した語句。シリーズの頁が無い
  unknownEvents  催しらしい語句なのに、掲載にも見送りにも無い名前。取りこぼしの手がかり

公開リポジトリに置くので、表示回数が10未満の語句(個人の名前などが混ざりうる)と、
メールアドレスや電話番号の形を含む語句は書かない。

認証はサービスアカウント。JSON を Secret GSC_SA_KEY に置き、そのメールアドレスを
Search Console の agave-navi.com に「制限付き」のユーザーとして足す(手順は docs/search-console.md)。
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import name_key_text, today_jst  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'search-demand.json')
API = 'https://searchconsole.googleapis.com/webmasters/v3'
SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'

MIN_IMPRESSIONS = 10          # これ未満の語句は公開ファイルに書かない
OPP_MIN_IMPRESSIONS = 20
OPP_POSITION = (4.0, 20.0)
TOP_N = 30
EVENTISH = re.compile(r'(マルシェ|即売会|フェス|フェスタ|展示会|イベント|販売会|市|祭|フェア|ポップアップ|'
                      r'market|fes|fair|show|popup|pop up)', re.I)
PRIVATE = re.compile(r'@|\d{2,4}-\d{2,4}-\d{3,4}|\d{10,}')


def _norm(s):
    return unicodedata.normalize('NFKC', s or '').lower().strip()


def _path(url):
    m = re.match(r'https?://[^/]+(/[^?#]*)', url or '')
    return m.group(1) if m else (url or '')


def is_hub(url):
    """一覧の頁か。回の頁(/events/)とガイド(/guides/)以外"""
    p = _path(url)
    return not (p.startswith('/events/') or p.startswith('/guides/'))


def _tokens(q):
    return [t for t in re.split(r'[\s　・/|]+', _norm(q)) if len(name_key_text(t)) >= 3]


def name_index(events, rejected):
    """(掲載の名前の鍵の一覧 → slug, 見送りの名前の鍵の一覧)。aliases も含む"""
    listed = []
    for e in events:
        for n in [e.get('name') or ''] + list(e.get('aliases') or []):
            k = name_key_text(n)
            if len(k) >= 3:
                listed.append((k, e.get('slug')))
    rej = [name_key_text(r.get('name') or r.get('key') or '') for r in rejected]
    return listed, [k for k in rej if len(k) >= 3]


def _generic(listed):
    """多くの回の名前に入る語は固有名にならない。名前の鍵に5回以上出る2〜6字の部分を一般語とみなす"""
    from collections import Counter
    c = Counter()
    for k, _ in listed:
        seen = set()
        for w in range(2, 7):
            for i in range(0, max(len(k) - w + 1, 0)):
                seen.add(k[i:i + w])
        c.update(seen)
    return {s for s, n in c.items() if n >= 5}


def analyze_demand(rows, events, rejected):
    """rows: [{'query','page','clicks','impressions','position'}]。返り値は search-demand.json の本体"""
    listed, rej = name_index(events, rejected)
    generic = _generic(listed)

    by_q = {}
    for r in rows:
        q = r['query']
        if PRIVATE.search(q):
            continue
        d = by_q.setdefault(q, {'query': q, 'clicks': 0, 'impressions': 0, '_pos': 0.0, 'pages': {}})
        d['clicks'] += r.get('clicks', 0)
        d['impressions'] += r.get('impressions', 0)
        d['_pos'] += r.get('position', 0) * r.get('impressions', 0)
        d['pages'][r['page']] = d['pages'].get(r['page'], 0) + r.get('impressions', 0)
    qs = []
    for d in by_q.values():
        if d['impressions'] < MIN_IMPRESSIONS:
            continue
        d['position'] = round(d['_pos'] / d['impressions'], 1) if d['impressions'] else None
        d['page'] = max(d['pages'], key=d['pages'].get)
        qs.append({k: d[k] for k in ('query', 'clicks', 'impressions', 'position', 'page')})
    qs.sort(key=lambda x: -x['impressions'])

    def specific(q):
        return [t for t in _tokens(q) if name_key_text(t) not in generic]

    def match_listed(q):
        hits = set()
        for t in specific(q):
            tk = name_key_text(t)
            hits |= {s for k, s in listed if tk in k}
        return sorted(hits)

    def match_rejected(q):
        return any(name_key_text(t) in k for t in specific(q) for k in rej)

    opportunities = [q for q in qs if q['impressions'] >= OPP_MIN_IMPRESSIONS
                     and q['position'] and OPP_POSITION[0] <= q['position'] <= OPP_POSITION[1]][:TOP_N]
    hub_landed, series, unknown = [], [], []
    for q in qs:
        hits = match_listed(q['query'])
        if 1 <= len(hits) <= 2 and is_hub(q['page']):
            hub_landed.append(dict(q, events=hits))
        elif 3 <= len(hits) <= 10 and is_hub(q['page']):
            series.append(dict(q, events=hits))
        elif not hits and EVENTISH.search(q['query']) and specific(q['query']) \
                and not match_rejected(q['query']):
            unknown.append(q)
    total_c = sum(r.get('clicks', 0) for r in rows)
    total_i = sum(r.get('impressions', 0) for r in rows)
    return {'opportunities': opportunities, 'hubLanded': hub_landed[:TOP_N],
            'seriesLanded': series[:TOP_N], 'unknownEvents': unknown[:TOP_N],
            'totals': {'clicks': total_c, 'impressions': total_i, 'queries': len(by_q)}}


def fetch(key_json, start, end):
    from google.oauth2 import service_account
    from google.auth.transport.requests import AuthorizedSession
    creds = service_account.Credentials.from_service_account_info(json.loads(key_json), scopes=[SCOPE])
    s = AuthorizedSession(creds)
    site = os.environ.get('GSC_SITE')
    if not site:
        sites = s.get(f'{API}/sites', timeout=60).json().get('siteEntry') or []
        cand = [x['siteUrl'] for x in sites if 'agave-navi.com' in x.get('siteUrl', '')]
        if not cand:
            raise SystemExit('Search Console に agave-navi.com のプロパティが見えない。'
                             'サービスアカウントをプロパティのユーザーに足したか')
        site = sorted(cand, key=lambda u: not u.startswith('sc-domain:'))[0]
    from urllib.parse import quote
    rows, start_row = [], 0
    while True:
        body = {'startDate': start, 'endDate': end, 'dimensions': ['query', 'page'],
                'rowLimit': 25000, 'startRow': start_row}
        r = s.post(f'{API}/sites/{quote(site, safe="")}/searchAnalytics/query', json=body, timeout=120)
        r.raise_for_status()
        got = r.json().get('rows') or []
        rows += [{'query': x['keys'][0], 'page': x['keys'][1], 'clicks': x.get('clicks', 0),
                  'impressions': x.get('impressions', 0), 'position': x.get('position', 0)} for x in got]
        if len(got) < 25000:
            return site, rows
        start_row += 25000


def _self_test():
    ev = [{'slug': 'hanatomo-2026', 'name': '第9回 花友フェスタ'},
          {'slug': 'a', 'name': 'ボタニカルマルシェ 富山'}, {'slug': 'b', 'name': 'ボタニカルマルシェ 金沢'},
          {'slug': 'c', 'name': 'ボタニカルマルシェ 福井'}, {'slug': 'd', 'name': 'ボタニカルマルシェ 京都'},
          {'slug': 'e', 'name': 'ボタニカルマルシェ 大阪'}]
    rej = [{'name': '見送った多肉フェア(愛知)'}]
    rows = [
        {'query': '花友フェスタ 2026', 'page': 'https://agave-navi.com/', 'clicks': 1, 'impressions': 40, 'position': 9},
        {'query': 'ひみつの植物市', 'page': 'https://agave-navi.com/tag/marche/', 'clicks': 0, 'impressions': 15, 'position': 30},
        {'query': '見送った多肉フェア', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 12, 'position': 30},
        {'query': 'ボタニカルマルシェ', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 50, 'position': 3},
        {'query': '090-1234-5678', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 99, 'position': 5},
        {'query': 'まれな語', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 3, 'position': 5},
    ]
    out = analyze_demand(rows, ev, rej)
    bad = []
    if [q['query'] for q in out['opportunities']] != ['花友フェスタ 2026']:
        bad.append(('伸びしろは表示20回以上・4〜20位', out['opportunities']))
    if [q['query'] for q in out['hubLanded']] != ['花友フェスタ 2026']:
        bad.append(('掲載済みの回の名前で一覧に着地した語句', out['hubLanded']))
    if [q['query'] for q in out['seriesLanded']] != ['ボタニカルマルシェ']:
        bad.append(('3回以上に当たるシリーズの名前', out['seriesLanded']))
    if [q['query'] for q in out['unknownEvents']] != ['ひみつの植物市']:
        bad.append(('一般語・見送り済みは取りこぼし候補にしない', out['unknownEvents']))
    if any('090' in q['query'] for k in ('opportunities', 'hubLanded', 'seriesLanded', 'unknownEvents')
           for q in out[k]):
        bad.append(('電話番号の形は書かない',))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    args = ap.parse_args()
    bad = _self_test()
    if bad or args.self_test:
        for b in bad:
            print('self-test FAIL:', b, file=sys.stderr)
        print('self-test:', 'OK' if not bad else 'NG')
        return 1 if bad else 0
    key = os.environ.get('GSC_SA_KEY', '').strip()
    if not key:
        print('search-demand: Secret GSC_SA_KEY が無いので取得しない(手順は docs/search-console.md)')
        return 0
    from datetime import date
    end = date.fromisoformat(today_jst()) - timedelta(days=3)
    start = end - timedelta(days=27)
    site, rows = fetch(key, start.isoformat(), end.isoformat())
    with open(os.path.join(ROOT, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    with open(os.path.join(ROOT, 'rejected-events.json'), encoding='utf-8') as f:
        rejected = json.load(f).get('items') or []
    body = analyze_demand(rows, events, rejected)
    doc = {'_note': 'Search Console の直近28日から作る(scripts/search-demand.py)。表示10回未満の語句と、'
                    'メール・電話番号の形の語句は書かない。site-health-check が週次で読んで手を打つ',
           'generatedOn': today_jst(), 'site': site, 'range': [start.isoformat(), end.isoformat()], **body}
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
    t = body['totals']
    print(f"search-demand: {start}〜{end} クリック{t['clicks']} 表示{t['impressions']} 語句{t['queries']} → "
          f"伸びしろ{len(body['opportunities'])} 一覧に着地{len(body['hubLanded'])} シリーズ{len(body['seriesLanded'])} "
          f"未掲載の手がかり{len(body['unknownEvents'])}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
