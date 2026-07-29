#!/usr/bin/env python3
"""generate-watchlist.py — events.json から「ウォッチ対象」を自動導出する。

自己拡張の仕組み:
  収集パイプラインが新イベントを events.json に追加する
  → 毎日のビルドで本スクリプトが実行され、そのイベントの公式Instagram/公式サイトが
    watch-sources.json に自動で入る
  → 日次の収集タスク(agave-event-update)が watch-sources.json を読んで巡回する
  → 次回開催の告知を検知して新イベントを登録する → 最初に戻る(ループ)
手動でウォッチリストを管理する必要はない。

出力: リポジトリ直下 watch-sources.json (https://agave-navi.com/watch-sources.json で公開)
"""
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import normalize_series_name, today_jst, now_jst

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(REPO_ROOT, 'events.json')
CRAWL_SOURCES = os.path.join(REPO_ROOT, 'crawl-sources.json')
OUT = os.path.join(REPO_ROOT, 'watch-sources.json')

IG_RE = re.compile(r'instagram\.com/([A-Za-z0-9_.]+)/?')
NON_HANDLES = {'p', 'reel', 'reels', 'tv', 'explore', 'stories', 'accounts'}

# 公式サイト候補から除外するドメイン(aggregator/チケット/SNS/自サイト)
EXCLUDED_DOMAINS = (
    'instagram.com', 'facebook.com', 'twitter.com', 'x.com', 'youtube.com', 'tiktok.com',
    'nextmeet.app', 'botanical-zone.tokyo', 'leaf-laboratory.com', 'pukubook.jp',
    'tochinavi.net', 'fukuoka-now.com', 'churatoku.net', 'agavemaniacs.com',
    'daybook-botanical.com', 'takez.jp', 'kuro-shiba.net', 'minna-ta29.com', 'hanaprime.jp',
    'l-tike.com', 'eplus.jp', 'pia.jp', 'lawsonticket.com', 'ticket.rakuten.co.jp',
    'agave-navi.com', 'google.com', 'ameblo.jp',
)


def ig_handle(ev):
    # 明示指定を最優先。裸の投稿URL(instagram.com/p/XXXX/)しか手元にない回でも
    # ここに主催者ハンドルを入れておけばウォッチ対象に載る。
    explicit = (ev.get('organizerIg') or '').strip().lstrip('@').lower()
    if explicit and explicit not in NON_HANDLES:
        return explicit
    for k in ('instagramUrl', 'sourceUrl', 'url'):
        u = ev.get(k) or ''
        m = IG_RE.search(u)
        if m:
            h = m.group(1).lower()
            if h not in NON_HANDLES:
                return h
    return None


def site_domain(url):
    m = re.match(r'https?://(?:www\.)?([^/]+)', url or '')
    if not m:
        return None
    d = m.group(1).lower()
    if any(x in d for x in EXCLUDED_DOMAINS):
        return None
    return d


def main():
    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    today = today_jst()

    # --- 1. Instagramアカウント(=主催者)の集計 ---
    by_handle = defaultdict(list)
    for e in events:
        h = ig_handle(e)
        if h:
            by_handle[h].append(e)

    ig_accounts = []
    for h, evs in by_handle.items():
        evs_dated = sorted([e for e in evs if e.get('date')], key=lambda e: e['date'])
        last = evs_dated[-1] if evs_dated else evs[0]
        last_end = last.get('dateEnd') or last.get('date') or ''
        has_future = any((e.get('dateEnd') or e.get('date') or '') >= today for e in evs_dated)
        ig_accounts.append({
            'handle': h,
            'url': f'https://www.instagram.com/{h}/',
            'eventCount': len(evs),
            'lastEventName': last.get('name'),
            'lastEventDate': last.get('date'),
            'hasUpcoming': has_future,
            # 優先度: 複数回実績 > 直近まで活動 > その他。未来イベント掲載済みなら急がない
            'priority': (0 if has_future else 1) + (0 if len(evs) >= 2 else 1),
        })
    # priority昇順(0が最重要)→イベント数降順→最終開催日降順
    ig_accounts.sort(key=lambda a: (a['priority'], -a['eventCount'], a['lastEventDate'] or ''), reverse=False)

    # --- 2. 次回開催待ちシリーズ (全開催回が終了済のシリーズ) ---
    series = defaultdict(list)
    for e in events:
        k = normalize_series_name(e.get('name'))
        if len(k) >= 4:
            series[k].append(e)
    awaiting = []
    for k, evs in series.items():
        dated = [e for e in evs if e.get('date')]
        if not dated:
            continue
        if any((e.get('dateEnd') or e.get('date')) >= today for e in dated):
            continue  # 未来回が既に掲載済み
        last = max(dated, key=lambda e: e.get('date'))
        last_end = last.get('dateEnd') or last.get('date')
        months = (int(today[:4]) * 12 + int(today[5:7])) - (int(last_end[:4]) * 12 + int(last_end[5:7]))
        if months > 18:
            continue  # 1年半以上音沙汰なしは休止とみなし対象外
        awaiting.append({
            'series': last.get('name'),
            'lastSlug': last.get('slug'),
            'lastDate': last.get('date'),
            'lastEnd': last_end,
            'monthsSinceLast': months,
            'igHandle': ig_handle(last),
            'officialUrl': last.get('url'),
            'recurring': len(evs) >= 2,
        })
    # 複数回実績があるもの優先、次に最終開催が新しい順
    awaiting.sort(key=lambda a: (not a['recurring'], a['lastEnd']), reverse=False)
    awaiting.sort(key=lambda a: (0 if a['recurring'] else 1, -(int(a['lastEnd'][:4])*100+int(a['lastEnd'][5:7]))))

    # --- 3. crawl-sources.json 未登録の公式サイト(requestsで巡回可能な自動候補) ---
    try:
        with open(CRAWL_SOURCES, encoding='utf-8') as f:
            existing = {site_domain(s.get('url')) for s in json.load(f)['sources']}
    except Exception:
        existing = set()
    site_candidates = {}
    for e in events:
        d = site_domain(e.get('url') or '')
        if not d or d in existing or d in site_candidates:
            continue
        end = e.get('dateEnd') or e.get('date') or ''
        # 直近12か月に活動実績のある主催者サイトのみ
        if end and (int(today[:4]) - int(end[:4])) * 12 + int(today[5:7]) - int(end[5:7]) <= 12:
            site_candidates[d] = {
                'domain': d, 'url': e.get('url'),
                'eventName': e.get('name'), 'eventDate': e.get('date'),
            }

    # IGのURLは持っているのにハンドルが解決できない回。organizerIg を入れれば解消する。
    unresolved = []
    for e in events:
        if ig_handle(e):
            continue
        if any('instagram.com' in (e.get(k) or '') for k in ('instagramUrl', 'sourceUrl', 'url')):
            unresolved.append({'slug': e.get('slug'), 'name': e.get('name'),
                               'igUrl': next((e.get(k) for k in ('instagramUrl', 'sourceUrl', 'url')
                                              if 'instagram.com' in (e.get(k) or '')), '')})

    out = {
        'generated': now_jst().strftime('%Y-%m-%d %H:%M JST'),
        'description': 'events.jsonから自動導出されるウォッチ対象。手動編集不要(毎日のビルドで再生成)。',
        'stats': {
            'igAccounts': len(ig_accounts),
            'awaitingNextEdition': len(awaiting),
            'officialSiteCandidates': len(site_candidates),
            'unresolvedIgHandles': len(unresolved),
        },
        'igAccounts': ig_accounts,
        'awaitingNextEdition': awaiting[:40],
        'officialSiteCandidates': list(site_candidates.values())[:30],
        'unresolvedIgHandles': unresolved,
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"watch-sources.json: IG {len(ig_accounts)}件 / 次回待ちシリーズ {len(awaiting)}件 / サイト候補 {len(site_candidates)}件")
    if unresolved:
        print(f"  ⚠ IGハンドル未解決 {len(unresolved)}件 — organizerIg を入れるまでウォッチ対象外: "
              + ', '.join(u['slug'] for u in unresolved[:5])
              + (' ...' if len(unresolved) > 5 else ''))


if __name__ == '__main__':
    main()
