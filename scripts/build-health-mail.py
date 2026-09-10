#!/usr/bin/env python3
"""build-health-mail.py — 日次の健全性メール本文を組む。

**2026-09-10 に health.yml から出した。**197行の Python が workflow の
`run: |` に直書きされていて、ローカルで実行も検証もできなかった。
2026-08-31 にカード挿入の処理が sync-events.yml にしか無く、手で足した回は
カードが作られない、という事故を出している。**CIでしか走らないコードは
壊れても分からない。**

出力:
  email-body.txt          メール本文
  GITHUB_OUTPUT の subj_prefix   件名の頭(要判断がある回だけ)
  標準出力にも本文を出す(ローカルで確認できるように)

読むファイル: check-results.json / new-events-added.json /
pending-judgments.json / audit-results.json
"""
import json
from datetime import date
with open('check-results.json') as f:
    data = json.load(f)
new_added = {"count": 0, "events": []}
try:
    with open('new-events-added.json') as f:
        new_added = json.load(f)
except Exception:
    pass
today = date.today().strftime('%Y/%m/%d')
# 要人間判断キュー(各スケジュールタスクが積む)を読み込み
judgments = []
try:
    with open('pending-judgments.json') as f:
        judgments = json.load(f).get('items', [])
except Exception:
    pass
# 整合監査(audit.py)の結果。検出があれば要修正。
audit = {}
try:
    with open('audit-results.json') as f:
        audit = json.load(f)
except Exception:
    pass
lines = []
lines.append("【アガベイベントナビ】イベント定期チェック結果")
lines.append(f"チェック日: {today}")
if judgments:
    lines.append("")
    lines.append(f"━━━ 🙋 あなたの判断が必要です（{len(judgments)}件）━━━")
    for j in judgments:
        lines.append(f"■ [{j.get('source','?')}] {j.get('title','')} ({j.get('date','')})")
        if j.get('detail'):
            lines.append(f"  {j['detail']}")
        if j.get('proposal'):
            lines.append(f"  → 提案: {j['proposal']}")
        lines.append("")
    lines.append("対応はCoworkでClaudeに指示してください（例:「キューの◯◯を承認」）。対応済みの項目は各タスクが自動で消し込みます。")
    lines.append("")
lines.append("")
lines.append("━━━ サマリー ━━━")
lines.append(f"総イベント数: {data['total_events']}")
today_events = data.get('today_events', [])
lines.append(f"🎪 本日開催中: {len(today_events)}")
lines.append(f"🆕 本日追加: {new_added['count']}件")
lines.append(f"今後のイベント: {len(data['upcoming_events'])}")
lines.append(f"終了済み: {len(data['past_events'])}")
lines.append(f"詳細未定(TBD): {len(data['tbd_events'])}")
lines.append(f"✍️ 説明文70字未満(開催予定): {len(data.get('short_descriptions') or [])}件")
lines.append(f"👀 IGハンドル未解決(ウォッチ対象外): {len(data.get('unresolved_ig') or [])}件")
# 出す項目は audit.py 側の severity で決まる。ここに項目名を書かない。
_af = (audit.get('findings') or {})
_hit = [(k, v) for k, v in _af.items()
        if v.get('severity', 'urgent') == 'urgent' and v.get('count')]
if _hit:
    lines.append("")
    lines.append("━━━ 🔧 整合監査：要修正 ━━━")
    for _k, _v in _hit:
        lines.append(f"・{_v.get('title', _k)}: {_v.get('count')}件")
        for _it in (_v.get('items') or [])[:5]:
            lines.append(f"    - {_it}")
        if _v.get('note'):
            lines.append(f"    → {_v['note']}")
else:
    lines.append("🔧 整合監査：異常なし")
_info = [(k, v) for k, v in _af.items()
         if v.get('severity') == 'info' and v.get('count')]
if _info:
    lines.append("")
    lines.append("━━━ 📊 積み残し（急がないが減らしたい） ━━━")
    for _k, _v in _info:
        lines.append(f"・{_v.get('title', _k)}: {_v.get('count')}件")
# 件数はURL単位。同じ出典を共有する回が並ぶため、イベント単位だと実体1件が7件に見える
_dead_u = sorted({d['sourceUrl'] for d in data['dead_links']})
_unreach_u = sorted({d['sourceUrl'] for d in (data.get('unreachable') or [])})
if _dead_u:
    lines.append(f"・リンク切れ(サーバが4xx/5xxを返した): {len(_dead_u)}URL")
if _unreach_u:
    lines.append(f"・出典に接続できない(相手が生きている可能性が高い。要確認): {len(_unreach_u)}URL")

# 取りこぼし候補は本文に中身を出す。件数だけだと動かない。
# 一次情報で裏取りして掲載するか、rejected に落とせば翌日から消える
try:
    with open('coverage-gaps.json', encoding='utf-8') as _cf:
        _cov = json.load(_cf)
except (OSError, ValueError):
    _cov = {}
_cgaps = _cov.get('gaps') or []
_cerr = _cov.get('errors') or []
if _cgaps:
    lines.append("")
    lines.append("━━━ 🔍 他所に出ていて当サイトに無いイベント ━━━")
    lines.append("一次情報で裏取りして、掲載するか見送りに記録してください。")
    lines.append("見送りを rejected-events.json に入れれば翌日から出なくなります。")
    for _g in _cgaps[:25]:
        _sp = _g.get('date')
        if _g.get('days'):
            _sp = f"{_g.get('date')}〜{_g.get('lastSeen')}({_g.get('days')}日)"
        lines.append(f"・{_sp} {str(_g.get('title'))[:110]}")
    if len(_cgaps) > 25:
        lines.append(f"  ほか {len(_cgaps) - 25}件")
if _cerr:
    lines.append("")
    lines.append("━━━ ⚠️ 取りこぼし巡回が失敗している ━━━")
    lines.append("この状態では上の候補が0件でも「取りこぼしなし」の証拠になりません。")
    for _e in _cerr[:8]:
        lines.append(f"・{_e}")
# 参考値(metric)は本文に出さない。「対応不要」と書いたものを毎日並べても
# 読み飛ばされるだけで、ラベルを付け替えただけになる(2026-08-24に本文から外した)。
# 値は audit-results.json / audit-history.json に残っており、
# 急変したときだけ監査の metric_moved が urgent で鳴らす。
lines.append("")
lines.append("━━━ ✅ 毎日の自動チェック ━━━")
lines.append(f"要判断キュー: {len(judgments)}件 / 内容異常の検知: {len(data.get('implausible') or [])}件 / リンク切れ: {len(_dead_u)}URL / 詳細未定: {len(data['tbd_events'])}件")
lines.append("※いずれも0件なら対応不要です。1件以上ある項目だけ、下に内訳が出ます。")
lines.append("")
if new_added['count'] > 0:
    lines.append(f"━━━ 🆕 本日追加イベント（{new_added['count']}件） ━━━")
    for ne in new_added['events']:
        end_info = f"〜{ne['dateEnd']}" if ne.get('dateEnd') else ''
        lines.append(f"・{ne['name']}")
        lines.append(f"  日時: {ne['date']}{end_info}")
        lines.append(f"  場所: {ne.get('prefecture', '')} {ne.get('location', '')}")
        lines.append(f"  URL: https://agave-navi.com/events/{ne['slug']}.html")
        lines.append("")
if today_events:
    lines.append("━━━ 🎪 本日開催中！ ━━━")
    for te in today_events:
        end_info = f"〜{te['dateEnd']}" if te.get('dateEnd') and te['dateEnd'] != te['date'] else ''
        lines.append(f"・{te['name']}")
        lines.append(f"  日時: {te['date']}{end_info}")
        lines.append(f"  場所: {te['location']}")
        lines.append(f"  URL: https://agave-navi.com/events/{te['slug']}.html")
        lines.append("")
if data['dead_links']:
    lines.append("━━━ ⚠️ リンク切れ検出 ━━━")
    _g = {}
    for dl in data['dead_links']:
        _g.setdefault((dl['sourceUrl'], dl['statusCode']), []).append(dl)
    for (_u, _c), _evs in sorted(_g.items()):
        lines.append(f"・HTTP {_c} {_u}")
        lines.append(f"  該当 {len(_evs)}件: " + '、'.join(e['name'] for e in _evs[:4])
                     + ('…' if len(_evs) > 4 else ''))
        lines.append(f"  例: https://agave-navi.com/events/{_evs[0]['slug']}.html")
        lines.append("")
if data.get('unreachable'):
    lines.append("━━━ 出典に接続できなかった（判定不能） ━━━")
    lines.append("HTTPの応答自体が取れていないので、リンク切れとは限りません。")
    lines.append("ブラウザで開いて生きていれば、こちらの取得手段の問題です。")
    _g2 = {}
    for dl in data['unreachable']:
        _g2.setdefault(dl['sourceUrl'], []).append(dl)
    for _u, _evs in sorted(_g2.items()):
        lines.append(f"・{_u} ← {len(_evs)}件")
    lines.append("")
if data.get('implausible'):
    lines.append("━━━ 🧪 内容の異常を自動検知（要確認） ━━━")
    for ip in data['implausible']:
        lines.append(f"・{ip['name']}")
        for iss in ip['issues']:
            lines.append(f"  - {iss}")
        lines.append(f"  詳細: https://agave-navi.com/events/{ip['slug']}.html")
        lines.append("")
if data['tbd_events']:
    lines.append("━━━ 📋 詳細未定イベント（要確認） ━━━")
    for tbd in data['tbd_events']:
        lines.append(f"・{tbd['name']} ({tbd['date']})")
        lines.append(f"  ソース: {tbd['sourceUrl']}")
        lines.append("")
if data['upcoming_events']:
    lines.append("━━━ 📅 今後のイベント一覧 ━━━")
    for ue in sorted(data['upcoming_events'], key=lambda x: x['date']):
        status_label = '✅' if ue['eventStatus'] == 'confirmed' else '⏳'
        end = f"〜{ue['dateEnd']}" if ue.get('dateEnd') else ''
        lines.append(f"{status_label} {ue['name']}")
        lines.append(f"   日時: {ue['date']}{end}")
        lines.append(f"   場所: {ue['location']}")
        lines.append(f"   URL: https://agave-navi.com/events/{ue['slug']}.html")
        lines.append("")
lines.append("━━━━━━━━━━━━━━━━━━━━")
lines.append("アガベイベントナビ https://agave-navi.com")
with open('email-body.txt', 'w') as f:
    f.write('\n'.join(lines))
subj_prefix = f"【要判断{len(judgments)}件】" if judgments else ""
import os
# CI の外でも動くこと。GITHUB_OUTPUT が無いだけで落ちると、
# ローカルで確かめられない = 直書きだった頃と同じになる
_out = os.environ.get('GITHUB_OUTPUT')
if _out:
    with open(_out, 'a') as f:
        f.write(f"subj_prefix={subj_prefix}\n")
else:
    print(f"(subj_prefix={subj_prefix})")
print('\n'.join(lines))
