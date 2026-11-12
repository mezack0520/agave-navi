# event-monitor 2026-11-13

- 起動記録: push済み
- audit: 検出786件。悪化 venue_key_split 0→2(下記で解消)。urgent 0
- data-integrity-check: errors 0 / warnings 0
- 日次メールの予定: 「サイトに反映したこと」は朝の2件と今回の2件。「直せずに残っていること」は venue_key_split だけで、今回直した。mail-request.json を push

## 直したこと
- 悪化の原因は 11-12・11-13 に足した回(森の多肉園 鹿児島、田主丸ガーデン Vol.5)ではなく、同じ施設の古い回の location に区画が入っていたこと。新しい回が施設名で入って割れが表に出た
- lier-taniku-festival-aira-2026-11: location から「展示室」を外した(venue には残る)
- tanushimaru-garden-shokuyo-osei-vol4-2026: location を「田主丸ガーデン（福岡県久留米市田主丸町）」、venue を「田主丸ガーデン 駐車場」に
- どちらも log-fix 記録済み。手元の audit で venue_key_split 0。venue_history_drift 4 は生成物の古さで、CI の再生成で消える

## 検査の拡張
- sitelib.VENUE_SUBAREA_RE に「駐車場」を足した。今回の田主丸は先頭一致の規則で拾えていたが、「X 北駐車場」「X 南駐車場」のような末尾だけ違う割れは拾えなかった。修正前のデータで2組、修正後0組で変化なし
- 新しい類型の検査は足していない。今回の割れは既存の venue_key_split が当日に拾った

## 未対応
- organizer_unlisted_dates 8件(info)、再評価待ち30日超 8件: ブラウザ要。agave-event-update の担当
- task_run_gap: agave-event-update 2026-11-09(過去の日で直す先は無い)
