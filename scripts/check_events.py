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
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import today_jst, DESC_MIN_CHARS, content_implausible_issues

def check_url(url, timeout=15):
    """URLの死活チェック。ステータスコードを返す。

    返り値の意味（ここを混同すると誤検知になる）:
      0        URL未設定
      200      SNS等で検査対象外（ボット遮断のため常にOK扱い）
      2xx/3xx  生存
      4xx/5xx  サーバが明確に「無い」と答えた = 本物のリンク切れ
      -1       DNS・タイムアウト・TLS・接続拒否で**判定できなかった**。
               「無い」ことの証明にはならないのでリンク切れに数えない。
               実例: http://isij.net/ は現役（2026-08-24時点で更新中）だが
               urllib からは HEAD/GET とも例外になり -1 が返る。
               これを7イベント分カウントして「リンク切れ7件」と報告していた。
    """
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

    today = today_jst()  # JSTで判定(UTCだと前日扱いになる)
    results = {
        'check_date': today,
        'total_events': len(events),
        'dead_links': [],
        'unreachable': [],
        'tbd_events': [],
        'past_events': [],
        'upcoming_events': [],
        'today_events': [],
        'url_results': [],
        'implausible': [],
        'short_descriptions': [],
        'unresolved_ig': []
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

        # bot遮断ドメインは死活チェック対象外(人間には正常表示・機械検証不能。
        # 実例: vandaka-plants.com が statusCode -1 で誤検知 2026-07-14)
        # 人間には正常表示だが機械検証できないドメイン。追加するときは
        # 必ずブラウザで生存を確認し、確認日を書くこと。
        #   vandaka-plants.com  2026-07-14 確認（statusCode -1 で誤検知）
        #   isij.net            2026-08-24 確認（現役・同日更新あり。素のHTTPで
        #                       urllib からは HEAD/GET とも例外になる。
        #                       7イベントが共有しているため -1 が7件に増幅されていた）
        #   threads.com/net     2026-09-29（未ログインのCIには 429 を返す。
        #                       緑楽宴・ときめきマルシェ2件が「リンク切れ」に出た）
        BOT_WALLED = ('x.com', 'twitter.com', 'instagram.com', 'facebook.com',
                      'threads.com', 'threads.net',
                      'vandaka-plants.com', 'isij.net')
        # 見るのは sourceUrl だけでなく url(詳細頁の「公式サイト」)も(2026-10-06)。
        # url が sourceUrl と別の頁を指す回は、どこからも死活を見られていなかった。
        # BOTANICAL TAMBA 2026 は url が観光協会の 404 の頁のまま 09-10 から載っており、
        # 開催60日前に中止の見張りの対象に入った 10-06 に初めて取得失敗として出た。
        # 結果の 'sourceUrl' キーは「確かめたURL」の意味で使い、どちらの項目かは 'field' に書く。
        _end = ev.get('dateEnd') or ev_date
        _recent = not _end or _end >= today
        _targets = [('sourceUrl', source_url)]
        _u = (ev.get('url') or '').strip()
        if _u and _u != '#' and _u != source_url:
            _targets.append(('url', _u))
        for _field, _chk in _targets:
            if not (_chk and _recent):
                continue
            if any(d in _chk.lower() for d in BOT_WALLED):
                continue
            status_code = check_url(_chk)
            url_result = {
                'slug': slug,
                'name': name,
                'sourceUrl': _chk,
                'field': _field,
                'statusCode': status_code,
                'alive': status_code in (0, 200, 301, 302, 303, 307, 308)
            }
            results['url_results'].append(url_result)

            if status_code == -1:
                # 判定不能。こちらの取得手段の限界であることが多い
                results['unreachable'].append(url_result)
            elif not url_result['alive'] and status_code != 0:
                results['dead_links'].append(url_result)

        # 出力妥当性チェック(開催前のみ)。実例: 入場料33,000円(アパレル価格の混入)、
        # 別イベントの説明文混入、日付なしupcoming — いずれも「機構は正常・中身が異常」で
        # 人間の指摘まで表面化しなかったクラスの問題を毎日検知する。
        _end_pl = ev.get('dateEnd') or ev_date
        _is_future = (not _end_pl) or _end_pl >= today
        if _is_future and ev.get('status') == 'upcoming':
            # 規則は sitelib.content_implausible_issues が単一情報源(2026-10-07)。
            # audit.content_implausible が同じ関数を当てて urgent で出す。
            # ここに書いていた頃は、メールの節が落ちた 09-30 から誰も読んでいなかった
            _issues = content_implausible_issues(ev)
            _desc = ev.get('description') or ''
            if _issues:
                results['implausible'].append({'slug': slug, 'name': name, 'issues': _issues})
            # meta description(=description流用)が下限字数未満だとSERPスニペット枠を使い切れない
            _dlen = len((_desc or '').strip())
            # 閾値は sitelib.DESC_MIN_CHARS が単一情報源(2026-08-24に統一)。
            # thin_fixable が50字なのに、こちらが70字で別基準を持っていた
            if _dlen < DESC_MIN_CHARS:
                results['short_descriptions'].append({'slug': slug, 'name': name, 'length': _dlen})

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

    # ウォッチ対象に載らない回(IGのURLはあるが主催者ハンドルが取れない)。
    # 自己拡張ループから漏れ、次回開催を自動検知できなくなる。
    try:
        with open(os.path.join(os.path.dirname(__file__), '..', 'watch-sources.json'),
                  encoding='utf-8') as _wf:
            results['unresolved_ig'] = (json.load(_wf).get('unresolvedIgHandles') or [])
    except (OSError, ValueError):
        pass

    # サマリー出力
    print(f"=== イベントチェック結果 ({today}) ===")
    print(f"総イベント数: {results['total_events']}")
    print(f"本日開催中: {len(results['today_events'])}")
    print(f"今後のイベント: {len(results['upcoming_events'])}")
    print(f"過去のイベント: {len(results['past_events'])}")
    print(f"詳細未定(TBD): {len(results['tbd_events'])}")
    print(f"内容妥当性フラグ: {len(results['implausible'])}")
    print(f"説明文{DESC_MIN_CHARS}字未満(開催予定): {len(results['short_descriptions'])}")
    print(f"IGハンドル未解決(ウォッチ対象外): {len(results['unresolved_ig'])}")
    # 件数はURL単位で数える。同じ出典を共有する回が並ぶため
    # イベント単位で数えると実体1件が7件に見える(2026-08-24 isij.net)
    _dead_urls = sorted({d['sourceUrl'] for d in results['dead_links']})
    _unreach_urls = sorted({d['sourceUrl'] for d in results['unreachable']})
    print(f"リンク切れ: {len(_dead_urls)} URL ({len(results['dead_links'])}イベント)")
    print(f"判定不能: {len(_unreach_urls)} URL ({len(results['unreachable'])}イベント) ※取得手段の限界の可能性")
    print()

    if results['today_events']:
        print("🎉 本日開催中:")
        for te in results['today_events']:
            end_info = f"〜{te['dateEnd']}" if te['dateEnd'] != te['date'] else ''
            print(f"  - {te['name']} ({te['date']}{end_info}) @ {te['location']}")
        print()

    if results['dead_links']:
        print("⚠️ リンク切れ検出(サーバが4xx/5xxを返した):")
        _by_url = {}
        for dl in results['dead_links']:
            _by_url.setdefault((dl['sourceUrl'], dl['statusCode']), []).append(dl['slug'])
        for (u, code), slugs in sorted(_by_url.items()):
            print(f"  - HTTP {code} {u} ← {len(slugs)}件 ({', '.join(slugs[:3])}{'...' if len(slugs) > 3 else ''})")
        print()

    if results['unreachable']:
        print("判定不能(接続できず。相手が生きている可能性が高い):")
        _by_url2 = {}
        for dl in results['unreachable']:
            _by_url2.setdefault(dl['sourceUrl'], []).append(dl['slug'])
        for u, slugs in sorted(_by_url2.items()):
            print(f"  - {u} ← {len(slugs)}件 ({', '.join(slugs[:3])}{'...' if len(slugs) > 3 else ''})")
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

    # 終了コード（リンク切れがあれば1）
    if results['dead_links']:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
