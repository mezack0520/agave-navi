#!/usr/bin/env python3
"""search-demand.py — Search Console の検索語句から、需要があるのに頁が弱い語句・無い語句を出す(2026-11-09)。

    python3 scripts/search-demand.py              # 取得して search-demand.json を書く(Secret GSC_SA_KEY が要る)
    python3 scripts/search-demand.py --self-test  # 判定だけを合成データで確かめる
    python3 scripts/search-demand.py --log <actions の id> --change '何をどう変えたか(元の文言も)' [--no-change] [--page /organizer/x/]
    python3 scripts/search-demand.py --revert <evaluations の id> --change '何を戻したか'
                                                  # 手直しを search-actions.json に1行足す。タスクはこれで書く

なぜ要るか: 何を作るか・どこを直すかを、検索の需要を見ずに決めていた。
actions は、週次の点検(site-health-check、プレイブック §6 の 3)と毎朝の agave-event-update(§3.1)が直す。

出すもの(直近28日。Search Console は数日遅れるので3日前まで):
  opportunities  表示回数が多いのに平均順位が4〜20位の語句。頁を直せば上がる見込みがある
  hubLanded      掲載済みの回の名前で検索されたのに、着地が一覧の頁になっている語句
  seriesLanded   3〜10回に当たるシリーズの名前で検索され、一覧の頁に着地した語句。シリーズの頁が無い
  unknownEvents  催しらしい語句なのに、掲載にも見送りにも無い名前。取りこぼしの手がかり
  actions        上の4つを頁・回ごとにまとめた手直しの指示。見込みのクリック増で並べ、型ごとの成績で重みを付ける
  queues         指示を直すタスクごとの、指示が出続けている日(監査が手の止まりを数える)
  evaluations    search-actions.json の手直しの、その語句の前後28日のクリック率の比較(improved / flat / worse / waiting)

手直しの輪: このファイル(指示と測定) → タスクが直して search-actions.json に書く → 約3週後から測り、約5週後に確定
→ 効かない型は priority が下がり、頁の文言の worse は元に戻す(プレイブック §6 の 3)。
search-actions.json を push するとこのスクリプトが回り直し、直した指示は消える。

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
from sitelib import (name_key_text, today_jst, TAG_ROMAJI, REGION_ROMAJI,  # noqa: E402
                     PREF_TO_REGION)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'search-demand.json')
ACTIONS = os.path.join(ROOT, 'search-actions.json')
API = 'https://searchconsole.googleapis.com/webmasters/v3'
SCOPE = 'https://www.googleapis.com/auth/webmasters.readonly'

MIN_IMPRESSIONS = 10          # これ未満の語句は公開ファイルに書かない
OPP_MIN_IMPRESSIONS = 20
OPP_POSITION = (4.0, 20.0)
TOP_N = 30
COOLDOWN_DAYS = 56            # 手直しした頁・回には8週は次の指示を出さない。効いたかを測り終える間
# 測り方: 手直しの語句(queries)の、サイト全体でのクリック率を前後で比べる。検索の量は季節や
# 開催日の近さで動くが、率はほぼ動かない。頁ごとのクリック数で比べると、開催が過ぎた回の頁は
# 何をしても下がって見える
EVAL_DAYS = 28                # 前後それぞれの日数。曜日の偏りが出ないよう7の倍数
EVAL_SETTLE_DAYS = 7          # 手直しから再クロールまでの猶予。これを過ぎた日から「後」に数える
EVAL_MIN_DAYS = 14            # 「後」がこれに満たないうちは判定しない
EVAL_Z = 1.64                 # 率の差の確からしさ(片側95%)。これに届かなければ flat
REVERT_TYPES = {'page'}       # worse なら戻す型。頁の文言だけ。別名・主催・掲載は事実の訂正なので戻さない
MAX_ACTIONS = 10              # 直すタスクごと
# 指示の型ごとに直すタスクと、手が付かなければ輪が止まっているとみなす日数(週1回と毎日)
QUEUES = {'site-health-check': {'types': ['page', 'event_page', 'series_page'], 'idleDays': 14},
          'agave-event-update': {'types': ['coverage'], 'idleDays': 7}}
ACTION_BY = {t: task for task, q in QUEUES.items() for t in q['types']}
# 順位ごとのクリック率の目安。手直しの見込みを比べるためだけに使う
_CTR = {1: .28, 2: .15, 3: .10, 4: .07, 5: .05, 6: .04, 7: .03, 8: .025, 9: .02, 10: .018}
EVENTISH = re.compile(r'(マルシェ|即売会|フェス|フェスタ|展示会|イベント|販売会|市|祭|フェア|ポップアップ|'
                      r'market|fes|fair|show|popup|pop up)', re.I)
PRIVATE = re.compile(r'@|\d{2,4}-\d{2,4}-\d{3,4}|\d{10,}')

# 検索語のうち、催しの名前ではない語。これを除いて何も残らない語句(「植物イベント 関東 2026」
# 「アガベイベント 今日」)は、特定の回やシリーズを探した語句ではない。
# 種類・植物・地域・県は sitelib の一覧から取る。名前の一部にも入るので、語を消すのは
# 「名前を含む語句か」を決めるときだけで、名前との照合は語のまま行う
_QUERY_WORDS = sorted(
    {name_key_text(w) for w in (
        list(TAG_ROMAJI) + list(REGION_ROMAJI) + list(PREF_TO_REGION)
        + [p + s for p in PREF_TO_REGION for s in ('県', '府', '都')]
        + ['イベント', '販売会', 'フェスタ', 'フェス', 'フェア', 'ポップアップ', '市', '祭', 'まつり',
           'market', 'fes', 'fair', 'show', 'popup', 'pop up', 'event',
           '植物', '多肉', '塊根', '観葉', '園芸', '盆栽', 'ビザールプランツ', 'プランツ',
           '今日', '明日', '今週末', '週末', '今週', '来週', '今月', '来月', '開催', '予定', '日程',
           '一覧', '情報', '最新', '近く', '全国', '会場', '場所', 'おすすめ'])
     if name_key_text(w)}, key=len, reverse=True)
_YEARISH = re.compile(r'20\d\d年?|\d{1,2}月|\d{1,2}日')
_KANJI = re.compile(r'[\u4e00-\u9fff]')


def name_part(token):
    """語から催しの名前ではない語を除いた残り。残りが無い語は名前を含まない"""
    r = _YEARISH.sub('', name_key_text(token))
    for w in _QUERY_WORDS:
        r = r.replace(w, '')
    return r if len(r) >= (2 if _KANJI.search(r) else 3) else ''


def _norm(s):
    return unicodedata.normalize('NFKC', s or '').lower().strip()


def _path(url):
    m = re.match(r'https?://[^/]+(/[^?#]*)', url or '')
    return m.group(1) if m else (url or '')


def _event_slug(url):
    """回の頁(/events/<slug>.html)なら slug"""
    p = _path(url)
    return p[len('/events/'):].rsplit('.', 1)[0] if p.startswith('/events/') else ''


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


def ctr(pos):
    if not pos:
        return 0.0
    p = max(1, int(round(pos)))
    return _CTR.get(p, 0.01)


def windows(taken_on, data_end):
    """手直しの前後の期間 (前, 後)。前は前日までの28日。後は再クロールを待った7日後から、
    取れている日まで7日単位で最大28日。後がまだ無ければ None"""
    from datetime import date
    t = date.fromisoformat(taken_on)
    a0 = t + timedelta(days=EVAL_SETTLE_DAYS)
    n = min(EVAL_DAYS, ((data_end - a0).days + 1) // 7 * 7)
    return ((t - timedelta(days=EVAL_DAYS), t - timedelta(days=1)),
            (a0, a0 + timedelta(days=n - 1)) if n > 0 else None)


def window_stats(daily, queries, span):
    """語句の、期間内のサイト全体のクリック・表示・平均順位"""
    c = i = 0
    pw = 0.0
    if span:
        d0, d1 = span[0].isoformat(), span[1].isoformat()
        for q in {_norm(x) for x in queries}:
            for d, v in (daily.get(q) or {}).items():
                if d0 <= d <= d1:
                    c, i, pw = c + v[0], i + v[1], pw + v[2] * v[1]
    return {'days': (span[1] - span[0]).days + 1 if span else 0, 'clicks': c, 'impressions': i,
            'ctr': round(c / i, 4) if i else None, 'position': round(pw / i, 1) if i else None}


def verdict(b, a):
    """クリック率の差を二項の検定で見る。量が少なく差が確かでなければ flat。
    率が上がってもクリックが減った(またはその逆)ときも flat"""
    import math
    if a['days'] < EVAL_MIN_DAYS:
        return 'waiting'
    if not b['impressions'] or not a['impressions']:
        return 'flat'
    p = (b['clicks'] + a['clicks']) / (b['impressions'] + a['impressions'])
    if p <= 0 or p >= 1:
        return 'flat'
    z = (a['clicks'] / a['impressions'] - b['clicks'] / b['impressions']) \
        / math.sqrt(p * (1 - p) * (1 / b['impressions'] + 1 / a['impressions']))
    per_day = a['clicks'] / a['days'] - b['clicks'] / b['days']
    if z >= EVAL_Z and per_day >= 0:
        return 'improved'
    if z <= -EVAL_Z and per_day <= 0:
        return 'worse'
    return 'flat'


def _measurable(it):
    """測る手直しか。変えなかった記録(告知が無かった、催しでなかった)と戻した記録は測らない"""
    return bool(it.get('queries')) and bool(it.get('takenOn')) and not it.get('revertOf') \
        and not it.get('noChange')


def eval_span(log, data_end, prev_evals):
    """測り終えていない手直しのために取る日ごとの期間。無ければ None"""
    done = {e.get('id') for e in prev_evals or [] if e.get('final')}
    starts = [windows(it['takenOn'], data_end)[0][0] for it in log
              if _measurable(it) and it.get('id') not in done]
    return (min(starts), data_end) if starts else None


def evaluate(log, daily, data_end, prev_evals=None):
    """search-actions.json の手直しを、その語句の前後28日のクリック率で測る。
    測り終えた分(final)は前回の結果を使い、戻したかだけを読み直す"""
    reverted = {it.get('revertOf') for it in log if it.get('revertOf')}
    done = {e.get('id'): e for e in prev_evals or [] if e.get('final')}
    out = []
    for it in log:
        if not _measurable(it):
            continue
        e = done.get(it.get('id'))
        if e:
            e = dict(e)
        else:
            bspan, aspan = windows(it['takenOn'], data_end)
            b, a = window_stats(daily, it['queries'], bspan), window_stats(daily, it['queries'], aspan)
            e = {'id': it.get('id'), 'action': it.get('action'), 'type': it.get('type'), 'page': it.get('page') or '',
                 'takenOn': it['takenOn'], 'change': it.get('change') or '', 'verdict': verdict(b, a),
                 'final': a['days'] >= EVAL_DAYS, 'before': b, 'after': a}
        e['reverted'] = it.get('id') in reverted
        e['revert'] = e['verdict'] == 'worse' and e.get('type') in REVERT_TYPES and not e['reverted']
        out.append(e)
    return out


def type_factors(evals):
    """型ごとの成績から priority の重み(0〜2)。測った件数が無ければ 1。効かない型は自然に下がる"""
    from collections import Counter
    c = {}
    for e in evals:
        if e['verdict'] in ('improved', 'flat', 'worse'):
            c.setdefault(e['type'], Counter())[e['verdict']] += 1
    return {t: round((n['improved'] + 1) / (sum(n.values()) + 2) * 2, 2) for t, n in c.items()}


def pick_event(slugs, events_by_slug, today):
    """一覧に着地した語句が当たった回のうち、これから開く最も近い回。無ければ最後に開いた回"""
    def span(s):
        e = events_by_slug.get(s) or {}
        return e.get('date') or '', e.get('dateEnd') or e.get('date') or ''
    up = sorted((span(s)[0], s) for s in slugs if span(s)[1] >= today)
    if up:
        return up[0][1]
    return max(slugs, key=lambda s: span(s)[0])


def build_actions(body, log, events, today, factors):
    """4つの一覧を、頁・回ごとの手直しの指示にまとめる。見込みのクリック増 × 型の重みで並べる"""
    from datetime import date
    by_slug = {e.get('slug'): e for e in events}
    last = {}
    for it in log:
        k, d = it.get('action') or '', it.get('takenOn') or ''
        if k and d > last.get(k, ''):
            last[k] = d
    t0 = date.fromisoformat(today)
    cands = {}

    def add(type_, target, page, q, gain, **extra):
        key = f'{type_}:{target}'
        if key in last and (t0 - date.fromisoformat(last[key])).days < COOLDOWN_DAYS:
            return
        c = cands.get(key)
        if c:
            c['impressions'] += q['impressions']
            c['clicks'] += q['clicks']
            c['gain'] += gain
            if q['query'] not in c['queries']:
                c['queries'].append(q['query'])
            for k, v in extra.items():
                c.setdefault(k, v)
            return
        cands[key] = dict({'id': key, 'type': type_, 'page': page, 'queries': [q['query']],
                           'impressions': q['impressions'], 'clicks': q['clicks'],
                           'position': q['position'], 'gain': gain}, **extra)

    def next_one(q, s):
        """終わった回か、語句の年(「天下一植物界 2027」)がその回より先。探しているのは次の回"""
        e = by_slug.get(s) or {}
        ys = [int(y) for y in re.findall(r'20\d\d', _norm(q['query']))]
        return (e.get('dateEnd') or e.get('date') or '') < today \
            or (bool(ys) and max(ys) > int((e.get('date') or '0')[:4] or 0))

    # 次の回を探している語句は、その回の頁ではなく次の回の掲載で応える。告知を探す
    for q in body['opportunities']:
        p, s = _path(q['page']), _event_slug(q['page'])
        gain = q['impressions'] * max(0.0, ctr(3) - ctr(q['position']))
        if not s:
            add('page', p, p, q, gain)
        elif next_one(q, s):
            add('coverage', f'next:{s}', p, q, q['impressions'] * ctr(5), events=[s])
        else:
            add('event_page', s, p, q, gain)
    for q in body['hubLanded']:
        s = pick_event(q['events'], by_slug, today)
        if next_one(q, s):
            add('coverage', f'next:{s}', f'/events/{s}.html', q, q['impressions'] * ctr(5), events=[s])
        else:
            add('event_page', s, f'/events/{s}.html', q, q['impressions'] * ctr(3), landed=_path(q['page']))
    for q in body['seriesLanded']:
        add('series_page', name_key_text(q['query'])[:24], _path(q['page']), q, q['impressions'] * ctr(3),
            events=q['events'])
    for q in body['unknownEvents']:
        add('coverage', name_key_text(q['query'])[:24], _path(q['page']), q, q['impressions'] * ctr(5))
    from collections import Counter
    out, n = [], Counter()
    for c in sorted(cands.values(), key=lambda c: (-c['gain'] * factors.get(c['type'], 1.0), c['id'])):
        c['by'] = ACTION_BY[c['type']]
        if n[c['by']] >= MAX_ACTIONS:
            continue
        n[c['by']] += 1
        c['priority'] = round(c['gain'] * factors.get(c['type'], 1.0), 2)
        c['gain'] = round(c['gain'], 2)
        out.append(c)
    return out


def carry_over(prev, actions, evals, today):
    """監査が日数を数えるため、タスクごとに指示が出続けている日と、悪化と測った日を前回から持ち越す"""
    prev_q = prev.get('queues') or {}
    prev_by = {ACTION_BY.get(a.get('type')) for a in prev.get('actions') or []}
    queues = {}
    for task, q in QUEUES.items():
        has = any(a['type'] in q['types'] for a in actions)
        since = ((prev_q.get(task) or {}).get('since') or today) if has and task in prev_by else (today if has else None)
        queues[task] = dict(q, since=since)
    prev_worse = {e.get('id'): e.get('worseSince') for e in prev.get('evaluations') or [] if e.get('worseSince')}
    for e in evals:
        if e['revert']:
            e['worseSince'] = prev_worse.get(e['id']) or today
        else:
            e.pop('worseSince', None)
    return queues


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
        # 名前を含まない語(「植物イベント」「2026」)は照合に使わない。「植物イベント」が
        # 別名「丸十家具 植物イベント」の回に当たり、一般の語句がその回の語句に数えられていた(2026-11-17)
        return [t for t in _tokens(q) if name_key_text(t) not in generic and name_part(t)]

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
        # 回の頁に着地した語句は、その回が載っている。名前の書き方が違っても(「富士山フェスタ」と
        # 「フジサンフェスタ 2026秋」)取りこぼしの候補にしない
        if _event_slug(q['page']):
            continue
        if 1 <= len(hits) <= 2 and is_hub(q['page']):
            hub_landed.append(dict(q, events=hits))
        elif 3 <= len(hits) <= 10 and is_hub(q['page']):
            series.append(dict(q, events=hits))
        elif not hits and EVENTISH.search(q['query']) \
                and any(name_part(t) not in generic for t in specific(q['query'])) \
                and not match_rejected(q['query']):
            unknown.append(q)
    total_c = sum(r.get('clicks', 0) for r in rows)
    total_i = sum(r.get('impressions', 0) for r in rows)
    return {'opportunities': opportunities, 'hubLanded': hub_landed[:TOP_N],
            'seriesLanded': series[:TOP_N], 'unknownEvents': unknown[:TOP_N],
            'totals': {'clicks': total_c, 'impressions': total_i, 'queries': len(by_q)}}


def session(key_json):
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
    return s, site


def _query(s, site, start, end, dims):
    from urllib.parse import quote
    out, start_row = [], 0
    while True:
        body = {'startDate': start, 'endDate': end, 'dimensions': dims,
                'rowLimit': 25000, 'startRow': start_row}
        r = s.post(f'{API}/sites/{quote(site, safe="")}/searchAnalytics/query', json=body, timeout=120)
        r.raise_for_status()
        got = r.json().get('rows') or []
        out += got
        if len(got) < 25000:
            return out
        start_row += 25000


def fetch(s, site, start, end):
    return [{'query': x['keys'][0], 'page': x['keys'][1], 'clicks': x.get('clicks', 0),
             'impressions': x.get('impressions', 0), 'position': x.get('position', 0)}
            for x in _query(s, site, start, end, ['query', 'page'])]


def fetch_daily(s, site, start, end):
    """語句ごと・日ごとの [クリック, 表示, 平均順位]。手直しの前後比較だけに使い、ファイルには書かない"""
    out = {}
    for x in _query(s, site, start.isoformat(), end.isoformat(), ['date', 'query']):
        d, q = x['keys']
        v = out.setdefault(_norm(q), {}).setdefault(d, [0, 0, 0.0])
        c, i = x.get('clicks', 0), x.get('impressions', 0)
        if v[1] + i:
            v[2] = (v[2] * v[1] + x.get('position', 0) * i) / (v[1] + i)
        v[0], v[1] = v[0] + c, v[1] + i
    return out


ACTIONS_NOTE = ('検索の需要の手直しの記録。タスクは scripts/search-demand.py --log / --revert で足す'
                '(プレイブック §6 の 3、§3.1)。search-demand.py がその語句の前後28日のクリック率で測り、'
                'search-demand.json の evaluations に出す')


def log_action(action_id, change, today, by=None, page=None, no_change=False, revert_of=None):
    """search-actions.json に1行足す。指示の型・語句・頁は search-demand.json から写す。足した行を返す"""
    if not (change or '').strip():
        raise SystemExit('--change に何をどう変えたか(変えなかったなら理由)を書く')
    doc = _load(ACTIONS, {})
    items = doc.get('items') or []
    if revert_of:
        orig = next((it for it in items if it.get('id') == revert_of), None)
        if not orig:
            raise SystemExit(f'search-actions.json に {revert_of} が無い')
        item = {'id': f'revert:{revert_of}', 'action': orig.get('action'), 'type': orig.get('type'),
                'page': orig.get('page') or '', 'takenOn': today, 'by': by or orig.get('by') or '',
                'change': change.strip(), 'revertOf': revert_of}
    else:
        a = next((x for x in _load(OUT, {}).get('actions') or [] if x.get('id') == action_id), None)
        if not a:
            raise SystemExit(f'search-demand.json の actions に {action_id} が無い')
        item = {'id': f'{action_id}@{today}', 'action': action_id, 'type': a['type'],
                'page': page or a.get('page') or '', 'queries': list(a.get('queries') or []), 'takenOn': today,
                'by': by or a.get('by') or '', 'change': change.strip()}
        if no_change:
            item['noChange'] = True
    if any(it.get('id') == item['id'] for it in items):
        raise SystemExit(f"{item['id']} はもう書いてある")
    items.append(item)
    with open(ACTIONS, 'w', encoding='utf-8') as f:
        f.write(json.dumps({'_note': ACTIONS_NOTE, 'items': items}, ensure_ascii=False, indent=1) + '\n')
    return item


def _self_test():
    global ACTIONS, OUT
    ev = [{'slug': 'hanatomo-2026', 'name': '第9回 花友フェスタ'},
          {'slug': 'a', 'name': 'ボタニカルマルシェ 富山'}, {'slug': 'b', 'name': 'ボタニカルマルシェ 金沢'},
          {'slug': 'c', 'name': 'ボタニカルマルシェ 福井'}, {'slug': 'd', 'name': 'ボタニカルマルシェ 京都'},
          {'slug': 'e', 'name': 'ボタニカルマルシェ 大阪'}]
    ev += [{'slug': 'marujyu', 'name': 'kijimuna × BOTANY 植物販売会', 'aliases': ['丸十家具 植物イベント']},
           {'slug': 'tanikkuri', 'name': 'タニックリ', 'aliases': ['タニックリ クリスマス多肉植物イベント']},
           {'slug': 'shokubutsu-a', 'name': '春の植物イベント 岐阜'},
           {'slug': 'fujisan-festa-2026-autumn', 'name': 'フジサンフェスタ 2026秋'}]
    rej = [{'name': '見送った多肉フェア(愛知)'}]
    rows = [
        {'query': '花友フェスタ 2026', 'page': 'https://agave-navi.com/', 'clicks': 1, 'impressions': 40, 'position': 9},
        {'query': 'ひみつの植物市', 'page': 'https://agave-navi.com/tag/marche/', 'clicks': 0, 'impressions': 15, 'position': 30},
        {'query': '見送った多肉フェア', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 12, 'position': 30},
        {'query': 'ボタニカルマルシェ', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 50, 'position': 3},
        {'query': '090-1234-5678', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 99, 'position': 5},
        {'query': 'まれな語', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 3, 'position': 5},
        {'query': '植物イベント', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 30, 'position': 30},
        {'query': '多肉植物イベント 関東 2026', 'page': 'https://agave-navi.com/region/kanto/',
         'clicks': 0, 'impressions': 30, 'position': 30},
        {'query': 'アガベイベント 今日', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 30, 'position': 30},
        {'query': '富士山フェスタ', 'page': 'https://agave-navi.com/events/fujisan-festa-2026-autumn.html',
         'clicks': 0, 'impressions': 30, 'position': 30},
        {'query': 'ボタニカルイベント 2026', 'page': 'https://agave-navi.com/', 'clicks': 0, 'impressions': 76,
         'position': 30},
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
        bad.append(('一般語・見送り済み・回の頁に着地した語句は取りこぼし候補にしない', out['unknownEvents']))
    _generic_q = {'植物イベント', '多肉植物イベント 関東 2026', 'アガベイベント 今日'}
    if any(q['query'] in _generic_q for k in ('hubLanded', 'seriesLanded') for q in out[k]):
        bad.append(('名前を含まない語句を特定の回・シリーズに数えない',
                    [q['query'] for k in ('hubLanded', 'seriesLanded') for q in out[k]]))
    if any('090' in q['query'] for k in ('opportunities', 'hubLanded', 'seriesLanded', 'unknownEvents')
           for q in out[k]):
        bad.append(('電話番号の形は書かない',))

    # 手直しの指示: 同じ頁の語句はまとめる。直して8週の頁は出さない。型の重みが効く
    body = {'opportunities': [
                {'query': 'a 屋外', 'page': 'https://agave-navi.com/guides/x.html', 'clicks': 5, 'impressions': 500, 'position': 6},
                {'query': 'a 耐寒', 'page': 'https://agave-navi.com/guides/x.html', 'clicks': 1, 'impressions': 300, 'position': 8},
                {'query': 'b', 'page': 'https://agave-navi.com/guides/y.html', 'clicks': 1, 'impressions': 900, 'position': 5},
                {'query': '花友フェスタ 駐車場', 'page': 'https://agave-navi.com/events/hanatomo-2026.html', 'clicks': 0,
                 'impressions': 200, 'position': 7},
                {'query': '花友フェスタ 2025', 'page': 'https://agave-navi.com/events/old.html', 'clicks': 0,
                 'impressions': 300, 'position': 7}],
            'hubLanded': [{'query': '花友フェスタ', 'page': 'https://agave-navi.com/pref/osaka/', 'clicks': 0,
                           'impressions': 100, 'position': 9, 'events': ['old', 'hanatomo-2026']},
                          {'query': '花友フェスタ 2026春', 'page': 'https://agave-navi.com/', 'clicks': 0,
                           'impressions': 50, 'position': 9, 'events': ['old']},
                          {'query': '花友フェスタ 2027', 'page': 'https://agave-navi.com/', 'clicks': 0,
                           'impressions': 40, 'position': 9, 'events': ['hanatomo-2026']}],
            'seriesLanded': [], 'unknownEvents': []}
    evs = [{'slug': 'old', 'date': '2025-12-01'}, {'slug': 'hanatomo-2026', 'date': '2026-12-19'}]
    log = [{'id': 'page:/guides/y.html@2026-11-01', 'action': 'page:/guides/y.html', 'type': 'page',
            'page': '/guides/y.html', 'takenOn': '2026-11-01'}]
    acts = build_actions(body, log, evs, '2026-11-17', {'page': 0.5})
    ids = [a['id'] for a in acts]
    if 'page:/guides/y.html' in ids:
        bad.append(('直して8週の頁は指示に出さない', ids))
    gx = [a for a in acts if a['id'] == 'page:/guides/x.html']
    if not gx or gx[0]['queries'] != ['a 屋外', 'a 耐寒'] or gx[0]['impressions'] != 800:
        bad.append(('同じ頁の語句は1つの指示にまとめる', acts))
    ev_a = [a for a in acts if a['type'] == 'event_page']
    if not ev_a or ev_a[0]['page'] != '/events/hanatomo-2026.html' or ev_a[0]['landed'] != '/pref/osaka/':
        bad.append(('一覧に着地した語句は、これから開く回の頁を直す', ev_a))
    if len(ev_a) != 1 or ev_a[0]['queries'] != ['花友フェスタ 駐車場', '花友フェスタ'] \
            or any(a['type'] == 'page' and a['page'].startswith('/events/') for a in acts):
        bad.append(('回の頁の伸びしろは、その回の event_page にまとめる', acts))
    nx = [a for a in acts if a['id'] == 'coverage:next:old']
    if not nx or nx[0]['queries'] != ['花友フェスタ 2025', '花友フェスタ 2026春'] or nx[0]['by'] != 'agave-event-update':
        bad.append(('終わった回の名前の検索は、次の回の掲載を探す指示にする', acts))
    nx2 = [a for a in acts if a['id'] == 'coverage:next:hanatomo-2026']
    if not nx2 or nx2[0]['queries'] != ['花友フェスタ 2027']:
        bad.append(('回より先の年の検索は、次の回の掲載を探す指示にする', acts))
    if gx and ev_a and not gx[0]['priority'] < gx[0]['gain']:
        bad.append(('型の重みが priority に掛かる', gx))
    if any(a['by'] != ('agave-event-update' if a['type'] == 'coverage' else 'site-health-check') for a in acts):
        bad.append(('指示に直すタスクを付ける', [(a['id'], a['by']) for a in acts]))

    # 測定: 語句の前後28日のクリック率。後は手直しの7日後から、7日単位
    from datetime import date
    d_end = date(2026, 12, 31)
    b0, a0 = windows('2026-11-10', d_end)
    if (b0[0].isoformat(), b0[1].isoformat(), a0[0].isoformat(), a0[1].isoformat()) != \
            ('2026-10-13', '2026-11-09', '2026-11-17', '2026-12-14'):
        bad.append(('前は前日までの28日、後は7日後からの28日', b0, a0))
    _, a1 = windows('2026-11-10', date(2026, 12, 2))
    if (a1[1] - a1[0]).days + 1 != 14:
        bad.append(('後は7日単位で切る', a1))
    if windows('2026-11-10', date(2026, 11, 20))[1] is not None:
        bad.append(('猶予の間は後が無い',))

    def days(q, start, n, c, i, pos=6.0):
        s0 = date.fromisoformat(start)
        return {(s0 + timedelta(days=k)).isoformat(): [c, i, pos] for k in range(n)}
    daily = {'a 屋外': {**days('a 屋外', '2026-09-28', 28, 1, 50), **days('a 屋外', '2026-11-02', 28, 3, 50, 4.0)},
             'b': {**days('b', '2026-09-28', 28, 3, 50), **days('b', '2026-11-02', 28, 1, 50)},
             'c': {**days('c', '2026-09-28', 28, 1, 50), **days('c', '2026-11-02', 28, 1, 50)},
             '花友フェスタ': {**days('花友フェスタ', '2026-09-28', 28, 2, 20), **days('花友フェスタ', '2026-11-02', 28, 6, 60)}}
    log2 = [{'id': 'p@1', 'action': 'page:/guides/x.html', 'type': 'page', 'page': '/guides/x.html',
             'queries': ['A 屋外'], 'takenOn': '2026-10-26'},
            {'id': 'p@2', 'action': 'page:/guides/y.html', 'type': 'page', 'page': '/guides/y.html',
             'queries': ['b'], 'takenOn': '2026-10-26'},
            {'id': 'p@3', 'action': 'page:/guides/z.html', 'type': 'page', 'page': '/guides/z.html',
             'queries': ['c'], 'takenOn': '2026-10-26'},
            {'id': 'e@1', 'action': 'event_page:hanatomo', 'type': 'event_page', 'page': '/events/hanatomo.html',
             'queries': ['花友フェスタ'], 'takenOn': '2026-10-26'},
            {'id': 'e@2', 'action': 'event_page:x', 'type': 'event_page', 'page': '/events/x.html',
             'queries': ['b'], 'takenOn': '2026-12-20'},
            {'id': 'r@1', 'action': 'page:/guides/y.html', 'type': 'page', 'revertOf': 'p@2', 'takenOn': '2026-12-01'}]
    ev2 = {e['id']: e for e in evaluate(log2, daily, d_end)}
    got = {k: (e['verdict'], e['final'], e['reverted'], e['revert']) for k, e in ev2.items()}
    want = {'p@1': ('improved', True, False, False), 'p@2': ('worse', True, True, False),
            'p@3': ('flat', True, False, False), 'e@1': ('flat', True, False, False),
            'e@2': ('waiting', False, False, False)}
    if got != want:
        bad.append(('率で測る。量が増えただけは flat。戻したものは戻さない', got))
    if eval_span(log2, d_end, list(ev2.values())) != (date(2026, 11, 22), d_end):
        bad.append(('測り終えた分は取り直さない', eval_span(log2, d_end, list(ev2.values()))))
    log3 = [dict(it) for it in log2 if it['id'] != 'r@1']
    ev3 = {e['id']: e for e in evaluate(log3, {}, d_end, list(ev2.values()))}
    if ev3['p@1']['before']['clicks'] != 28 or not ev3['p@2']['revert'] or ev3['p@2']['reverted']:
        bad.append(('測り終えた分は前回の結果を使い、戻したかだけ読み直す', ev3['p@2']))
    f = type_factors([{'type': 'page', 'verdict': 'worse'}, {'type': 'page', 'verdict': 'flat'},
                      {'type': 'event_page', 'verdict': 'improved'}])
    if not (f['page'] < 1 < f['event_page']):
        bad.append(('効かない型は重みが下がる', f))

    # 持ち越し: 指示が出続けている日はタスクごと。悪化と測った日は戻すまで
    prev = {'actions': [{'type': 'page'}], 'queues': {'site-health-check': {'since': '2026-11-02'}},
            'evaluations': [{'id': 'p@2', 'worseSince': '2026-12-01'}]}
    evs = list(ev3.values())
    qs = carry_over(prev, [{'type': 'page'}, {'type': 'coverage'}], evs, '2026-12-08')
    if (qs['site-health-check']['since'], qs['agave-event-update']['since']) != ('2026-11-02', '2026-12-08'):
        bad.append(('指示が出続けている日をタスクごとに持ち越す', qs))
    if [e.get('worseSince') for e in evs if e['id'] == 'p@2'] != ['2026-12-01'] \
            or any('worseSince' in e for e in evs if e['id'] != 'p@2'):
        bad.append(('悪化と測った日を戻すまで持ち越す', evs))
    if carry_over({}, [], [], '2026-12-08')['site-health-check']['since'] is not None:
        bad.append(('指示が無ければ日を持たない',))

    # 記録: 型・語句・頁は指示から写す。変えなかった記録と戻した記録は測らない
    import tempfile
    saved = ACTIONS, OUT
    with tempfile.TemporaryDirectory() as td:
        ACTIONS, OUT = os.path.join(td, 'a.json'), os.path.join(td, 'd.json')
        try:
            with open(OUT, 'w', encoding='utf-8') as f:
                json.dump({'actions': acts}, f, ensure_ascii=False)
            i1 = log_action('page:/guides/x.html', '題名を「A」から「B」に', '2026-11-23')
            i2 = log_action('coverage:next:old', '次の回は未告知', '2026-11-23', no_change=True)
            i3 = log_action(None, '題名を「A」に戻した', '2026-12-28', revert_of=i1['id'])
            if (i1['type'], i1['queries'], i1['page'], i1['by']) != \
                    ('page', ['a 屋外', 'a 耐寒'], '/guides/x.html', 'site-health-check') \
                    or not i2.get('noChange') or i2['by'] != 'agave-event-update' \
                    or (i3['revertOf'], i3['action']) != (i1['id'], 'page:/guides/x.html'):
                bad.append(('記録は指示から写す', i1, i2, i3))
            for args in (('page:/guides/x.html', 'もう一度', '2026-11-23'), ('page:/nope/', 'x', '2026-11-23'),
                         ('page:/guides/x.html', ' ', '2026-11-24')):
                try:
                    log_action(*args)
                    bad.append(('同じ日の二重・無い指示・空の change は書かない', args))
                except SystemExit:
                    pass
            ev4 = evaluate(_load(ACTIONS, {})['items'], {}, d_end)
            if [(e['id'], e['reverted']) for e in ev4] != [(i1['id'], True)]:
                bad.append(('変えなかった記録と戻した記録は測らない', ev4))
        finally:
            ACTIONS, OUT = saved
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--log', metavar='ACTION_ID', help='search-demand.json の actions の id の手直しを記録する')
    ap.add_argument('--revert', metavar='EVAL_ID', help='evaluations の id の手直しを戻したことを記録する')
    ap.add_argument('--change', help='何をどう変えたか。文言なら元の文言も。変えなかったなら理由')
    ap.add_argument('--no-change', action='store_true', help='調べたが変えなかった(測らない。8週は再び出ない)')
    ap.add_argument('--page', help='直した頁が指示の頁と違うとき(主催の頁を立てたなど)')
    ap.add_argument('--by', help='直したタスク。省けば指示の by')
    args = ap.parse_args()
    if args.log or args.revert:
        it = log_action(args.log, args.change, today_jst(), by=args.by, page=args.page,
                        no_change=args.no_change, revert_of=args.revert)
        print('search-actions.json:', json.dumps(it, ensure_ascii=False))
        return 0
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
    today = today_jst()
    end = date.fromisoformat(today) - timedelta(days=3)
    start = end - timedelta(days=27)
    s, site = session(key)
    rows = fetch(s, site, start.isoformat(), end.isoformat())

    events = _load(os.path.join(ROOT, 'events.json'), [])
    rejected = _load(os.path.join(ROOT, 'rejected-events.json'), {}).get('items') or []
    log = _load(ACTIONS, {}).get('items') or []
    prev = _load(OUT, {})
    span = eval_span(log, end, prev.get('evaluations'))
    daily = fetch_daily(s, site, *span) if span else {}
    body = analyze_demand(rows, events, rejected)
    evals = evaluate(log, daily, end, prev.get('evaluations'))
    factors = type_factors(evals)
    actions = build_actions(body, log, events, today, factors)
    queues = carry_over(prev, actions, evals, today)
    doc = {'_note': 'Search Console の直近28日から作る(scripts/search-demand.py)。表示10回未満の語句と、'
                    'メール・電話番号の形の語句は書かない。actions は by のタスクが直して search-actions.json に書く'
                    '(プレイブック §6 の 3、§3.1)',
           'generatedOn': today, 'site': site, 'range': [start.isoformat(), end.isoformat()], **body,
           'actions': actions, 'queues': queues, 'evaluations': evals, 'typeFactors': factors}
    with open(OUT, 'w', encoding='utf-8') as f:
        f.write(json.dumps(doc, ensure_ascii=False, indent=1) + '\n')
    t = body['totals']
    from collections import Counter
    print(f"search-demand: {start}〜{end} クリック{t['clicks']} 表示{t['impressions']} 語句{t['queries']} → "
          f"伸びしろ{len(body['opportunities'])} 一覧に着地{len(body['hubLanded'])} シリーズ{len(body['seriesLanded'])} "
          f"未掲載の手がかり{len(body['unknownEvents'])} / 指示 {dict(Counter(a['by'] for a in actions))} / "
          f"測定 {dict(Counter(e['verdict'] for e in evals))}"
          + (f"(日ごとの語句 {span[0]}〜{span[1]} {len(daily)}語)" if span else ''))
    return 0


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


if __name__ == '__main__':
    sys.exit(main())
