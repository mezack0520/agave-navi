# event-monitor 2026-11-16

## 監査
- data-integrity-check: errors 0 / warnings 0(797件)
- audit: urgent 0、前回からの悪化・解消なし。今日の daily(07:49 JST)後の状態で実行
- 日次メールの予定: 反映1件(ゆるっと多肉マルシェ第2回の時刻)、残り項目0

## 直したこと
- organizer_unlisted_dates 3件(info)
  - @botalife_pachy 11/21・11/28、@lahainagarden 11/21・11/22: 出店予定・巡回先として HAZE、植祭、多肉だョ全員集合(津山・福山)を挙げた投稿で、どれも掲載済み
  - 原因: known_elsewhere が名前の先頭6字と会場名でしか当てず、「HAZE(茨城)」「植祭(静岡 つま恋)」「岡山県津山市」のような短い書き方に当たらなかった
  - ig-organizer-watch.py に、日付の前後(同じ予定の行)に名前の先頭の語か開催地の市が出ていれば既知とする規則を足した。一般語・英語の一般語・2字の非漢字・大都市の市名は当てない。自己テスト6件追加
  - 今の organizer-posts.json の全投稿(3,867件)に当て、新たに既知になる組は20件。全件が実際にその掲載回を指していた(誤検知0)
  - @vandaka_plants 11/21-23: 京都店の営業日の案内。Dfre8E2GqZU を挙げて見送りに記録
- log-fix に3件記録、mail-request.json を push

## 未対応
- rejected_revisit_stale 9件(info)。一次情報の確認にブラウザが要る

