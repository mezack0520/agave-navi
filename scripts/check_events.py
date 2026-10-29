#!/usr/bin/env python3
"""
イベント定期チェックスクリプト
- events.json の全イベントの公式URL死活チェック
- eventStatus が 'tbd' のイベントをリスト化
- 結果をJSONで出力（GitHub Actionsで利用）
"""
import json
import sys
import os
from datetime import datetime, date

EVENTS_JSON = os.path.join(os.path.dirname(__file__), '..', 'events.json')
RESULTS_JSON = os.path.join(os.path.dirname(__file__), '..', 'check-results.json')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sitelib import (today_jst, DESC_MIN_CHARS, content_implausible_issues,  # noqa: E402
                     probe_status, should_retry_status, _self_test_request_url)

def check_url(url):
    """URLの死活チェック。ステータスコードを返す。取り方(HEAD→GET・429/5xx の引き直し)は
    sitelib.probe_status が単一情報源(2026-10-22。それまでここで自前に取っていた)。

    返り値の意味（ここを混同すると誤検知になる）:
      0        URL未設定
      200      SNS等で検査対象外（ボット遮断のため常にOK扱い）
      2xx/3xx  生存
      429/5xx  引き直しても「今は無理」。頁が無い証拠ではない(link_state が日数で見る)
      その他の4xx  サーバが「無い」と答えた = 本物のリンク切れ
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

    return probe_status(url)

def status_is_alive(code):
    """check_url の返り値が「生存」か。docstring の約束どおり 2xx/3xx はすべて生存。

    2026-10-15 まで 200 と 301/302/303/307/308 しか生存に数えておらず、2xx の残りが
    「サーバが無いと答えた」側に落ちていた。BORDER BREAK!! 11th の出典(blogspot)が
    CI の HEAD に 204 を返し、日次メールに「開催前の回の公式リンク切れ」として出た
    (手元からは HEAD・GET とも 200・本文 17.7KB)。204 は成功の応答で、消えた頁の返事ではない。
    """
    return code == 0 or 200 <= code < 400


# 429/5xx が何日続いたらリンク切れに数えるか。引き直しても駄目な日があっても、
# 翌日に戻る相手は多い(2026-10-22 bookkasama.com は 10-06〜10-21 の16回すべて 200、10-22 だけ 502)。
# 3日続けば、来場者が見に行っても見られない状態が続いている
PERSIST_DAYS = 3


def link_state(code, failing_since, today):
    """'alive' / 'dead' / 'unreachable'(判定不能)。failing_since はこの URL が生きていなかった最初の日"""
    if status_is_alive(code):
        return 'alive'
    if code == -1:
        return 'unreachable'
    if should_retry_status(code):
        try:
            days = (date.fromisoformat(today) - date.fromisoformat(failing_since)).days
        except (TypeError, ValueError):
            days = 0
        return 'dead' if days >= PERSIST_DAYS - 1 else 'unreachable'
    return 'dead'


def _previous_failing_since(path):
    """前回の check-results.json から、生きていなかった URL → その初日。
    failingSince の無い古い記録は、その回の check_date を初日とみなす"""
    try:
        with open(path, encoding='utf-8') as f:
            prev = json.load(f)
    except (OSError, ValueError):
        return {}
    out = {}
    for r in prev.get('url_results') or []:
        if r.get('alive') or not r.get('sourceUrl'):
            continue
        since = r.get('failingSince') or prev.get('check_date') or ''
        if since and (r['sourceUrl'] not in out or since < out[r['sourceUrl']]):
            out[r['sourceUrl']] = since
    return out


def _self_test_link_state():
    """link_state の自己テスト。失敗は check-results.json の selfTestErrors に残す"""
    t = '2026-10-22'
    cases = [(200, t, 'alive'), (404, t, 'dead'), (410, t, 'dead'), (403, t, 'dead'),
             (502, t, 'unreachable'), (502, '2026-10-21', 'unreachable'),
             (502, '2026-10-20', 'dead'), (429, t, 'unreachable'), (-1, '2026-09-01', 'unreachable')]
    return [f'link_state({c}, {s}): 期待 {w}' for c, s, w in cases if link_state(c, s, t) != w]


def _self_test_status_is_alive():
    """status_is_alive の自己テスト。main() が毎回呼ぶ。失敗しても巡回は止めない
    (health の後段のメールごと落ちるため)。警告を出し、check-results.json の selfTestErrors に残す"""
    cases = [(0, True), (200, True), (204, True), (206, True), (301, True), (308, True),
             (404, False), (410, False), (429, False), (500, False), (-1, False)]
    return [f'{c}: 期待 {w}' for c, w in cases if status_is_alive(c) != w]


def main():
    # request_url が崩れると、日本語を含む URL がまた「接続できない(-1)」に落ちる(2026-10-29)
    _bad = _self_test_status_is_alive() + _self_test_link_state() + _self_test_request_url()
    if _bad:
        print('::warning::check_events: 死活判定の自己テスト失敗: ' + ' / '.join(_bad), file=sys.stderr)
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
        'unresolved_ig': [],
        'selfTestErrors': _bad,
    }
    # 前回まで生きていなかった URL の初日。429/5xx が続いた日数を数える(link_state)
    _prev_fail = _previous_failing_since(RESULTS_JSON)

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
                'alive': status_is_alive(status_code)
            }
            if not url_result['alive']:
                url_result['failingSince'] = _prev_fail.get(_chk) or today
            results['url_results'].append(url_result)

            _state = link_state(status_code, url_result.get('failingSince', today), today)
            if _state == 'unreachable':
                # 判定不能。こちらの取得手段の限界か、相手の一時的な不調
                results['unreachable'].append(url_result)
            elif _state == 'dead':
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
        print(f"⚠️ リンク切れ検出(4xx を返した、または 429/5xx が{PERSIST_DAYS}日続いた):")
        _by_url = {}
        for dl in results['dead_links']:
            _by_url.setdefault((dl['sourceUrl'], dl['statusCode']), []).append(dl['slug'])
        for (u, code), slugs in sorted(_by_url.items()):
            print(f"  - HTTP {code} {u} ← {len(slugs)}件 ({', '.join(slugs[:3])}{'...' if len(slugs) > 3 else ''})")
        print()

    if results['unreachable']:
        print("判定不能(接続できない、または 429/5xx が続いていない。相手が生きている可能性が高い):")
        _by_url2 = {}
        for dl in results['unreachable']:
            _by_url2.setdefault((dl['sourceUrl'], dl['statusCode'], dl.get('failingSince')), []).append(dl['slug'])
        for (u, code, since), slugs in sorted(_by_url2.items(), key=lambda kv: kv[0][0]):
            print(f"  - {u} (HTTP {code}、{since}から) ← {len(slugs)}件 ({', '.join(slugs[:3])}{'...' if len(slugs) > 3 else ''})")
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
    with open(RESULTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 終了コード（リンク切れがあれば1）
    if results['dead_links']:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
