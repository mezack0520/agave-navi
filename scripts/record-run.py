#!/usr/bin/env python3
"""record-run.py — スケジュールタスクの実行日を台帳に記録する。

    python3 scripts/record-run.py <taskId>

**起動直後に一度だけ呼ぶ。** 終わりに呼ぶ設計にしていたが、
成果物が無い回はそもそも push されず、記録だけが落ちた。
2026-09-02 に台帳を見たら、agave-event-update は3日連続で走っていたのに
history が空、event-monitor は3回中1回しか書けていなかった。
「動かなかった日」と「動いたが書けなかった日」が区別できず、
監査 task_run_gap が実際には走っていた日を抜けとして出していた。

記録するのは「起動した日」であって「完走した日」ではない。
監査が知りたいのは『そもそも動いたのか』なので、それで足りる。
完走の有無は成果物とレポートで分かる。

event-listing-review だけは new-inquiries.json の reviewedOn /
reviewedHistory が同じ役目を持つので、そちらへ書く。
二重に持つと必ず片方だけ更新されて食い違う。

冪等。同じ日に何度呼んでも履歴は増えない。
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
from sitelib import today_jst   # 「今日」の定義は sitelib が単一情報源

KEEP = 14

TASK_RUNS = os.path.join(REPO, 'task-runs.json')
INQUIRIES = os.path.join(REPO, 'new-inquiries.json')
INQUIRY_TASK = 'event-listing-review'


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def save(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')


def record_inquiry(day):
    d = load(INQUIRIES)
    hist = [x for x in d.get('reviewedHistory', []) if x]
    changed = False
    if day not in hist:
        hist.append(day)
        changed = True
    d['reviewedHistory'] = sorted(set(hist))[-KEEP:]
    if d.get('reviewedOn') != day:
        d['reviewedOn'] = day
        changed = True
    save(INQUIRIES, d)
    return changed


def record_task(task_id, day):
    d = load(TASK_RUNS)
    tasks = d.setdefault('tasks', {})
    if task_id not in tasks:
        print(f'record-run: 未登録の taskId「{task_id}」。'
              f'登録済み: {", ".join(sorted(tasks))}', file=sys.stderr)
        return False
    t = tasks[task_id]
    hist = [x for x in t.get('history', []) if x]
    changed = day not in hist
    if changed:
        hist.append(day)
    t['history'] = sorted(set(hist))[-KEEP:]
    save(TASK_RUNS, d)
    return changed


def main():
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    task_id = sys.argv[1]
    day = today_jst()
    if task_id == INQUIRY_TASK:
        changed = record_inquiry(day)
        where = 'new-inquiries.json (reviewedOn / reviewedHistory)'
    else:
        changed = record_task(task_id, day)
        if changed is False and task_id not in load(TASK_RUNS).get('tasks', {}):
            return 1
        where = 'task-runs.json'
    print(f'record-run: {task_id} {day} → {where} '
          f'({"追記" if changed else "既に記録済み"})')
    print('  この変更を含めて push すること。push しないと台帳は残らない。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
