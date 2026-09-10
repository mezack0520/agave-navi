#!/usr/bin/env python3
"""record-run.py — スケジュールタスクの実行日を台帳に記録する。

    python3 scripts/record-run.py <taskId>
    python3 scripts/record-run.py --flush-worklog <path>

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

台帳への書き込みは push に乗っている。つまり **shell が落ちた日は
「起動した日を記録する」が原理的に守れない**(2026-09-09 と 09-10 に
agave-event-update / event-monitor / event-listing-review が2日連続で
これに当たった)。その日は repo の外(Coworkのプロジェクトフォルダ)に
起動記録を残しておき、次に push できた回が --flush-worklog で流し込む。
**単一障害点に乗った記録は、障害の日にちょうど落ちる。**

worklog の形:

    {"runs": [{"taskId": "...", "date": "YYYY-MM-DD"}, ...]}

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
    # reviewedOn は前へしか進めない。--flush-worklog で過去の回を
    # 流し込むときに後ろへ戻すと、監査 inquiry_check_stale が
    # 「止まっている」と誤って鳴る。履歴のほうが抜けを持っている
    if day > (d.get('reviewedOn') or ''):
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


def record(task_id, day):
    """taskId と日付を、その taskId の記録先へ書く。書き先は1つだけ。"""
    if task_id == INQUIRY_TASK:
        return record_inquiry(day), 'new-inquiries.json (reviewedOn / reviewedHistory)'
    return record_task(task_id, day), 'task-runs.json'


def flush_worklog(path):
    """push できなかった回の起動記録を台帳へ流し込む。

    台帳に入った項目だけ worklog から消す。**弾かれた項目は残す。**
    消し込みで起動記録が落ちるほうが、二重に流し込むより痛い(冪等なので
    二重に流し込んでも履歴は増えない)。
    """
    if not os.path.exists(path):
        print(f'record-run: worklog が無い: {path}', file=sys.stderr)
        return 1
    d = load(path)
    runs = d.get('runs') or []
    if not runs:
        print(f'record-run: worklog は空: {path}')
        return 0
    added, known, left = 0, 0, []
    for r in runs:
        task_id = (r.get('taskId') or '').strip()
        day = (r.get('date') or '').strip()
        if not task_id or not day:
            print(f'record-run: taskId か date が無い項目を残した: {r}',
                  file=sys.stderr)
            left.append(r)
            continue
        if (task_id != INQUIRY_TASK
                and task_id not in load(TASK_RUNS).get('tasks', {})):
            print(f'record-run: 未登録の taskId「{task_id}」を残した。'
                  f'task-runs.json に登録してから流し込むこと', file=sys.stderr)
            left.append(r)
            continue
        changed, where = record(task_id, day)
        if changed:
            added += 1
        else:
            known += 1
        print(f'  {task_id} {day} → {where} '
              f'({"追記" if changed else "既に記録済み"})')
    # **台帳に入ったものだけ消す。**全部消すと、弾かれた項目の起動記録が
    # 消し込みと一緒に落ちる。実際 agave-navi-eyecatch は未登録のままで、
    # 登録が1日遅れていれば 09-09 の起動が黙って消えていた
    # (2026-09-10 の event-monitor が同じ型を指摘している)。
    d['runs'] = left
    d['_flushedOn'] = today_jst()
    try:
        save(path, d)
    except OSError as e:
        print(f'record-run: worklog を空にできなかった({e})。手で消すこと。',
              file=sys.stderr)
    print(f'record-run: worklog を流し込んだ 追記{added} / 既知{known}')
    print('  この変更を含めて push すること。push しないと台帳は残らない。')
    return 0


def main():
    if len(sys.argv) == 3 and sys.argv[1] == '--flush-worklog':
        return flush_worklog(sys.argv[2])
    if len(sys.argv) != 2:
        print(__doc__.strip().splitlines()[2].strip(), file=sys.stderr)
        return 2
    task_id = sys.argv[1]
    day = today_jst()
    changed, where = record(task_id, day)
    if (task_id != INQUIRY_TASK and changed is False
            and task_id not in load(TASK_RUNS).get('tasks', {})):
        return 1
    print(f'record-run: {task_id} {day} → {where} '
          f'({"追記" if changed else "既に記録済み"})')
    print('  この変更を含めて push すること。push しないと台帳は残らない。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
