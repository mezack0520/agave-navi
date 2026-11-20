# event-monitor 2026-11-21

## 起動
- clone /tmp/tmp.tSxBaRMbIw、record-run 済み(5d30221d)。この回の record-run が crawl-request.json を書いた = その日最初の起動記録。
- 朝の3タスク(event-listing-review 06:31 / agave-event-update 07:09 / agave-navi-eyecatch 07:45)は trigger 上は発火(last_run SUCCEEDED)したが、台帳・コミット・work\ のパッチのどれも無い。走ったが何も押せていない。原因は repo 側からは見えない。
- daily は 08:16 の合図で起動し 08:24 に成功(24eec62a)。

## 監査
- data-integrity-check: errors 0 / warnings 0(815件)
- audit 悪化: coverage_gap_logged_but_open 0→1、time_vs_organizer_post 0→1。どちらも監査側の誤報で、直した後は 0。

## 直したこと
1. coverage_gap_logged_but_open: 候補「YOSHIMURA CACTUS POP UP STORE in CALEE TOKYO(11/21)」が 11-11 の記録「COOLCACTUS POPUP」に部分文字列 CACTUS で当たっていた。audit の照合を語どうしの一致(6字以上・汎用語を除く)に変えた。候補は本物の未掲載で、needs_browser で agave-event-update に渡した。
2. time_vs_organizer_post(midorigakuen-himeji-2026-11): 主催投稿 Df9HaBuGAYX の「11時〜 18時〜」は特売を出す時刻。sitelib に time_range_matches を置き、後ろの時刻にも区切りが続く一致(開始時刻の列)を範囲と読まないようにした。time_ranges / announced_dated_hours / 説明文の照合の3か所が共通で使う。自己テスト _self_test_start_time_list を audit から呼ぶ。organizer-posts と events の全 5,521 文で差分を見て、外れたのは開始時刻の列だけ(予約枠、企画の開始時刻)。time は変えていない。

## 残り
- coverage_gaps 8件、organizer_unlisted_dates(@greensnap.jp HAMACHO MIDORI MARKET 12/4-5)、アイキャッチ候補7件は朝のタスクが動かなかったぶん。ブラウザ要なので翌朝の agave-event-update / eyecatch が拾う。
- green-days-matsuyama-vol3-2026 の会場(11-20 の needs_browser)は未処理のまま。

## 終わり
- mail-request.json を push。clone 削除済み。
