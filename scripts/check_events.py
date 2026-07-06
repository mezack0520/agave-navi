#!/usr/bin/env python3
"""
イベント定期チェックスクリプト
- events.json の全イベントの公式URL死活チェック
- eventStatus が 'tbd' のイベントをリスト化
- 結果をJSONで出力（GitHub Actionsで利用）
"""
import json
import urllib.request
import urllib.error
import sys
import os
from datetime import datetime, date

EVENTS_JSON = os.path.join(os.path.dirname(__file__), '..', 'events.json')

def check_url(url, timeout=15):
    """URLの死活チェック。ステータスコードを返す。エラー時は-1"""
    if not url or url == '#':
        return 0  # URL未設定

    # Instagram / SNS はボットを弾くので常にOK扱い
    SKIP_DOMAINS = ['instagram.com', 'twitter.com', 'x.com', 'facebook.com', 'tiktok.com']
    for domain in SKIP_DOMAINS:
        if domain in url:
            return 200  # SNSは死活チェックスキップ

    # ブラウザに近いUser-Agentを使用
    ua = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    try:
        req = urllib.request.Request(url, method='HEAD', headers={
            'User-Agent': ua
        })
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.getcode()
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        # HEADが拒否される場合はGETで再試行
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': ua
            })
            resp = urllib.request.urlopen(req, timeout=timeout)
            return resp.getcode()
        except urllib.error.HTTPError as e:
            return e.code
        except Exception:
            return -1

def main():
    with open(EVENTS_JSON, 'r', encoding='utf-8') as f:
        events = json.load(f)

    today = date.today().isoformat()
    results = {
        'check_date': today,
        'total_events': len(events),
        'dead_links': [],
        'tbd_events': [],
        'past_events': [],
        'upcoming_events': [],
        'today_events': [],
        'url_results': []
    }

    for ev in events:
        slug = ev.get('slug', '')
        name = ev.get('name', '')
        ev_date = ev.get('date', '')
        source_url = ev.get('sourceUrl', '')
        event_status = ev.get('eventStatus', 'confirmed')

        # 過去イベントチェック
        if ev_date and ev_date < today:
            end_date = ev.get('dateEnd', ev_date)
            if end_date < today:
                results['past_events'].append({
                    'slug': slug,
                    'name': name,
                    'date': ev_date,
                    'dateEnd': ev.get('dateEnd', ''),
                })

        # TBDイベントリスト(開催前のイベントのみ。終了済みのtbd旗は実害がないため報告しない)
        ev_end_for_tbd = ev.get('dateEnd') or ev_date
        is_past_ev = bool(ev_end_for_tbd) and ev_end_for_tbd < today
        if event_status == 'tbd' and not is_past_ev:
            results['tbd_events'].append({
                'slug': slug,
                'name': name,
                'date': ev_date,
                'sourceUrl': source_url,
                'note': '日時・詳細未確定'
            })

        # URL死活チェック(終了30日超のイベントは対象外。
        # 主催者が告知ページを消すのは自然で、古い切れリンクを毎日報告しても積み上がるだけのため)
        from datetime import datetime as _dt, timedelta as _td
        _end = ev.get('dateEnd') or ev_date
        _recent = True
        if _end:
            try:
                _recent = _dt.strptime(_end, '%Y-%m-%d') >= _dt.strptime(today, '%Y-%m-%d') - _td(days=30)
            except ValueError:
                pass
        if source_url and _recent:
            status_code = check_url(source_url)
            url_result = {
                'slug': slug,
                'name': name,
                'sourceUrl': source_url,
                'statusCode': status_code,
                'alive': status_code in (0, 200, 301, 302, 303, 307, 308)
            }
            results['url_results'].append(url_result)

            if not url_result['alive'] and status_code != 0:
                results['dead_links'].append(url_result)

        # 今後のイベント
        if ev_date and ev_date >= today:
            results['upcoming_events'].append({
                'slug': slug,
                'name': name,
                'date': ev_date,
                'dateEnd': ev.get('dateEnd', ''),
                'location': ev.get('location', ''),
                'eventStatus': event_status,
                'sourceUrl': source_url,
            })

        # 本日開催中チェック（date <= today <= dateEnd）
        if ev_date:
            end_date = ev.get('dateEnd', ev_date)
            if ev_date <= today <= end_date:
                results['today_events'].append({
                    'slug': slug,
                    'name': name,
                    'date': ev_date,
                    'dateEnd': end_date,
                    'location': ev.get('location', ''),
                    'eventStatus': event_status,
                    'sourceUrl': source_url,
                })

    # サマリー出力
    print(f"=== イベントチェック結果 ({today}) ===")
    print(f"総イベント数: {results['total_events']}")
    print(f"本日開催中: {len(results['today_events'])}")
    print(f"今後のイベント: {len(results['upcoming_events'])}")
    print(f"過去のイベント: {len(results['past_events'])}")
    print(f"詳細未定(TBD): {len(results['tbd_events'])}")
    print(f"リンク切れ: {len(results['dead_links'])}")
    print()

    if results['today_events']:
        print("🎉 本日開催中:")
        for te in results['today_events']:
            end_info = f"〜{te['dateEnd']}" if te['dateEnd'] != te['date'] else ''
            print(f"  - {te['name']} ({te['date']}{end_info}) @ {te['location']}")
        print()

    if results['dead_links']:
        print("⚠️ リンク切れ検出:")
        for dl in results['dead_links']:
            print(f"  - {dl['name']}: {dl['sourceUrl']} (HTTP {dl['statusCode']})")
        print()

    if results['tbd_events']:
        print("📋 詳細未定イベント:")
        for tbd in results['tbd_events']:
            print(f"  - {tbd['name']} ({tbd['date']}) → {tbd['sourceUrl']}")
        print()

    if results['past_events']:
        print("🕐 終了済みイベント:")
        for pe in results['past_events']:
            print(f"  - {pe['name']} ({pe['date']})")
        print()

    # JSON結果をファイル出力（GitHub Actions用）
    output_path = os.path.join(os.path.dirname(__file__), '..', 'check-results.json')
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # GitHub Actions の GITHUB_OUTPUT に書き出し
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"dead_links={len(results['dead_links'])}\n")
            f.write(f"tbd_count={len(results['tbd_events'])}\n")
            f.write(f"past_count={len(results['past_events'])}\n")
            f.write(f"today_count={len(results['today_events'])}\n")
            has_issues = len(results['dead_links']) > 0 or len(results['tbd_events']) > 0
            f.write(f"has_issues={'true' if has_issues else 'false'}\n")

    # 終了コード（リンク切れがあれば1）
    if results['dead_links']:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
