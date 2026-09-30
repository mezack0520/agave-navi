#!/usr/bin/env python3
"""build-health-mail.py — 日次メールの本文を組む。

**2026-09-30 に作り直した。**目崎の指摘は「これもあんまり意味ないな」。
その日のメールは900行あり、目崎が読んで何かする必要のある行は無かった。
並んでいたのは、朝のタスクが既に直した結果、スクリプトの関数名の重複や
タスク台帳の抜けといった仕組み側の話、主催の発表待ちの詳細未定10件、
開催予定168件の全件一覧。件名の【異常1件】は、ログを grep で数えた値だった。

**メールは運営者(目崎)が読むもの。**載せるのは次の3つだけにする。
  1. あなたの判断が必要なこと(pending-judgments.json)
  2. サイトに反映したこと。掲載は過去24時間に events.json に入った回
     (new-events-added.json。タスクの記録の書き忘れに左右されない)、
     修正は朝のタスクの修正記録(auto-fix-log.json の fixed。仕組み側の修正は除く)
  3. タスクが直せずに残っていること。監査の urgent と、健全性チェック
     (データ整合性・外部リンク切れ・SSL)の検出。本来は朝のタスクが直すので、
     残っているのはタスクが止まっているか直し方が決まっていない兆候
どれも無い日は送らない(GITHUB_OUTPUT の send=false)。
詳細未定・今後の一覧・見送り・直せなかった理由などは、直す担当(朝のタスク)が
監査・check-results.json・auto-fix-log.json から直接読む。人に送る理由が無い。

出力:
  email-body.txt                メール本文
  GITHUB_OUTPUT の subject / send
  標準出力にも本文を出す(ローカルで確認できるように)
"""
import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402


def _load(path, default):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _env_int(k, d=0):
    try:
        return int(os.environ.get(k) or d)
    except ValueError:
        return d


def _tail(path, n):
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            return [l.rstrip() for l in f if l.strip()][-n:]
    except OSError:
        return []


data = _load('check-results.json', {})
added = (_load('new-events-added.json', {}) or {}).get('events') or []
judgments = _load('pending-judgments.json', {}).get('items', []) or []
audit = _load('audit-results.json', {})
fixlog = _load('auto-fix-log.json', {'items': []})
now = sitelib.now_jst()
today = now.strftime('%Y/%m/%d')
today_iso = now.strftime('%Y-%m-%d')

# 読者に見えない修正(仕組み側)。メールの「サイトに反映したこと」には出さない
_ENGINEERING_KINDS = {
    'cross_script_duplicate', 'cancel_watch', 'cancel_watch_unreachable', 'task_run_gap',
    'task_run_never_recorded', 'orphan_outputs', 'unreferenced_scripts', 'ci_push_bypassed',
    'rejected_revisit_expired',
}
unsent = [i for i in fixlog.get('items') or [] if not i.get('mailedOn')]
site_fixes = [i for i in unsent
              if i.get('action') == 'fixed' and i.get('kind') not in _ENGINEERING_KINDS]

# タスクが直せずに残っていること
residual = []
for k, v in (audit.get('findings') or {}).items():
    if v.get('severity', 'urgent') == 'urgent' and v.get('count'):
        residual.append((f"{v.get('title', k)}: {v.get('count')}件", (v.get('items') or [])[:3]))
_ie, _lb, _ssl = _env_int('INTEGRITY_ERR'), _env_int('LINKS_BROKEN'), _env_int('SSL_DAYS', 999)
if _ie:
    residual.append((f'データ整合性エラー: {_ie}件', _tail('/tmp/integrity.log', 5)))
if _lb:
    residual.append((f'サイト内の外部リンク切れ: {_lb}件', _tail('/tmp/links.log', 5)))
if _ssl < 30:
    residual.append((f'SSL証明書の残り: {_ssl}日', []))

lines = [f'【アガベイベントナビ】{today}', '']

if judgments:
    lines.append(f'━━━ 🙋 あなたの判断が必要です（{len(judgments)}件）━━━')
    for j in judgments:
        lines.append(f"■ {j.get('title', '')}（{j.get('date', '')}）")
        if j.get('detail'):
            lines.append(f"  {j['detail']}")
        if j.get('proposal'):
            lines.append(f"  → 提案: {j['proposal']}")
    lines.append('Cowork で Claude に指示してください（例:「キューの◯◯を承認」）。')
    lines.append('')

if added or site_fixes:
    lines.append(f'━━━ 🛠 サイトに反映したこと（{len(added) + len(site_fixes)}件）━━━')
    for e in added:
        _end = f"〜{e['dateEnd']}" if e.get('dateEnd') and e['dateEnd'] != e.get('date') else ''
        lines.append(f"・[掲載] {e.get('date', '')}{_end} {e.get('name', '')}（{e.get('prefecture', '')}）")
        lines.append(f"    {sitelib.DOMAIN}/events/{e.get('slug')}.html")
    for i in site_fixes:
        lines.append(f"・[修正] {i.get('target')}")
        if i.get('detail'):
            lines.append(f"    {i['detail']}")
    lines.append('')

if residual:
    lines.append(f'━━━ ⚠️ タスクが直せずに残っていること（{len(residual)}件）━━━')
    lines.append('朝のタスクが止まっているか、直し方が決まっていない項目です。')
    for head, items in residual:
        lines.append(f'・{head}')
        for it in items:
            lines.append(f'    - {str(it)[:160]}')
    lines.append('')

send = bool(judgments or added or site_fixes or residual)

# 数字は1行。一覧は載せない(サイトを見れば分かる)
_up = data.get('upcoming_events') or []
_sat = now.date() + timedelta(days=(5 - now.weekday()) % 7)
_sun = _sat + timedelta(days=1)


def _on_weekend(e):
    try:
        a = datetime.strptime(e.get('date', ''), '%Y-%m-%d').date()
        b = datetime.strptime(e.get('dateEnd') or e.get('date', ''), '%Y-%m-%d').date()
    except ValueError:
        return False
    return a <= _sun and b >= _sat


if send:
    lines.append(f"開催予定 {len(_up)}件 / 今週末（{_sat.month}/{_sat.day}-{_sun.day}）"
                 f"{sum(1 for e in _up if _on_weekend(e))}件")
    lines.append(f'{sitelib.DOMAIN}/this-weekend/')

body = '\n'.join(lines).rstrip() + '\n'
with open('email-body.txt', 'w', encoding='utf-8') as f:
    f.write(body)

if judgments:
    subject = f'【要判断{len(judgments)}件】アガベイベントナビ {today}'
elif residual:
    subject = f'【要確認】アガベイベントナビ {today}'
else:
    subject = f'アガベイベントナビ 今日の反映{len(added) + len(site_fixes)}件 {today}'

# 送る回(schedule / dispatch)だけ mailedOn を付ける。push で走る回は送らないので付けない
if unsent and os.environ.get('GITHUB_OUTPUT') \
        and os.environ.get('GITHUB_EVENT_NAME') not in ('push', None, ''):
    for i in unsent:
        i['mailedOn'] = today_iso
    with open('auto-fix-log.json', 'w', encoding='utf-8') as f:
        json.dump(fixlog, f, ensure_ascii=False, indent=1)
        f.write('\n')

_out = os.environ.get('GITHUB_OUTPUT')
if _out:
    with open(_out, 'a') as f:
        f.write(f'subject={subject}\n')
        f.write(f"send={'true' if send else 'false'}\n")
else:
    print(f'(subject={subject} / send={send})')
print(body)
