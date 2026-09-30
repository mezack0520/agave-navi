#!/usr/bin/env python3
"""data-change-report.py — events.json が <ref> から今までに何が変わったかを文章にする。

    python3 scripts/data-change-report.py <git-ref>          # 標準出力へ
    python3 scripts/data-change-report.py <git-ref> --out f  # ファイルへ(変更が無ければ作らない)

なぜあるか(2026-09-30):
  週次補完(weekly-enrichment)のメールは「検索で見つけた値」を並べて
  「正確性を確認の上で更新してください」と書いていた。実際には
  enrich_events.py --write-back が空欄に書き込み済みで、メールを読んでも
  **何が変わったのかが分からず、手で更新する物も無い。**目崎の指摘は
  「意味があるようにしておく」。

  メールに載せるのは「このジョブが実際に書き換えた内容」だけにする。
  抽出候補ではなく、events.json の前後の差分を回・項目ごとに出す。
  値が間違っていたら、その行を見ればどの回のどの項目を戻せばよいか分かる。
"""
import argparse
import json
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 毎回動くだけで内容の変化ではない項目
_IGNORE = {'updatedAt', 'status'}
_LABEL = {'imageUrl': 'アイキャッチ', 'imageSource': '画像の出典', 'url': '公式URL',
          'sourceUrl': '出典', 'venue': '会場', 'location': '場所', 'mapQuery': '地図',
          'time': '時間', 'admission': '入場料', 'description': '説明文',
          'date': '開始日', 'dateEnd': '終了日', 'dateDisplay': '日付表記',
          'eventStatus': '状態', 'organizer': '主催', 'organizerIg': '主催IG',
          'instagramPostId': 'IG投稿', 'tags': 'タグ', 'name': '名称', 'access': 'アクセス'}


def _short(v, n=60):
    if v is None:
        return '(なし)'
    s = v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= n else s[:n] + '…'


def diff(before, after):
    b = {e.get('slug'): e for e in before}
    a = {e.get('slug'): e for e in after}
    added = [a[s] for s in a if s not in b]
    removed = [b[s] for s in b if s not in a]
    changed = []
    for s, ae in a.items():
        be = b.get(s)
        if be is None:
            continue
        rows = []
        for k in list(be.keys()) + [k for k in ae.keys() if k not in be]:
            if k in _IGNORE:
                continue
            if be.get(k) != ae.get(k):
                rows.append((k, be.get(k), ae.get(k)))
        if rows:
            changed.append((ae, rows))
    return added, removed, changed


def render(added, removed, changed):
    out = []
    if changed:
        out.append(f'■ 書き換えた回（{len(changed)}件）')
        for e, rows in sorted(changed, key=lambda x: x[0].get('date') or ''):
            out.append(f"・{e.get('date', '')} {e.get('name', '')}")
            out.append(f"  https://agave-navi.com/events/{e.get('slug')}.html")
            for k, ov, nv in rows:
                lab = _LABEL.get(k, k)
                if ov in (None, '', []):
                    out.append(f'    {lab}: 追加 → {_short(nv)}')
                elif nv in (None, '', []):
                    out.append(f'    {lab}: 削除（{_short(ov)}）')
                else:
                    out.append(f'    {lab}: {_short(ov)} → {_short(nv)}')
        out.append('')
    if added:
        out.append(f'■ 追加した回（{len(added)}件）')
        for e in added:
            out.append(f"・{e.get('date', '')} {e.get('name', '')}")
        out.append('')
    if removed:
        out.append(f'■ 消した回（{len(removed)}件）')
        for e in removed:
            out.append(f"・{e.get('date', '')} {e.get('name', '')}（{e.get('slug')}）")
        out.append('')
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ref')
    ap.add_argument('--out')
    a = ap.parse_args()
    try:
        raw = subprocess.run(['git', 'show', f'{a.ref}:events.json'], cwd=REPO,
                             capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as e:
        print(f'{a.ref} の events.json を読めない: {e.stderr.strip()}', file=sys.stderr)
        return 1
    before = json.loads(raw)
    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        after = json.load(f)
    text = render(*diff(before, after))
    if a.out:
        if text.strip():
            with open(a.out, 'w', encoding='utf-8') as f:
                f.write(text + '\n')
    else:
        print(text or '変更なし')
    return 0


if __name__ == '__main__':
    sys.exit(main())
