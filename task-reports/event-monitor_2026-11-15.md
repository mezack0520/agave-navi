# event-monitor 2026-11-15

## 監査
- data-integrity-check: errors 0 / warnings 0
- 前回(11-14)からの悪化: cancel_suspects 0→3、cancel_watch_unreachable 0→1、duplicate_image_url 0→1、organizer_unlisted_dates 7→8(いずれも info。日次メールの残り項目は0)

## 直したこと
- duplicate_image_url: okibota-december-2026-sunshine の出典を今朝 IG 投稿に替えたため、出典ホストだけで見ていた同一主催の判定から外れていた(同シリーズのキービジュアル共用)。audit.py の判定を organizerIg と url/sourceUrl のホスト(instagram.com を除く)の共通で見るように直した → 0
- cancel_suspects 3件: 公式頁を curl で確認。joyfulhonda(+2字)、isij.net(11/22 配置図の公開)で中止・延期の語なし。cancel-reviewed.json に記録 → 0
- cancel_watch_unreachable: borderbreak の blogspot は手元から 200、12/5,6 の記載のまま(CI 側の一時的な 429)
- organizer_unlisted_dates の誤検知の類型を ig-organizer-watch.py で塞いだ(自己テスト追加)
  - 受付・予約・申込期間の見出しの日付、チケット投稿の販売期間・販売日・「前売り券:日付」、落とした日付から〜で続く会期の終わり
  - 見送り記録が同じ投稿のショートコードを挙げていれば既知(和歌山サボテンクラブ 新年会 1/17 が見送り済みなのに残っていた)
  - scan-organizer-posts の一覧は 174→162 行、CI 信号の対象 22→10(goodthings.jp の出店者紹介9件、notreatelier.29、wakayama_cactus_club ほか)
- 監査に organizer_unlisted_rejected_post(info)を追加。見送りが挙げた投稿の日付が信号に残っていれば出す。今日の写しで1件(wakayama)、翌日の daily で0になる想定
- @plants2306.fe のコケ玉ワークショップ 12/12 を workshopOnly で見送りに記録
- プレイブック §3.1: 見送りの reason に投稿のショートコードを書けば一覧から消える旨に直した

## 未対応
- organizer_unlisted_dates の残り(botalife_pachy 店頭フェア、lahainagarden 寄せ植えフォトコンテスト、okibota_2021 東海フラワーショウ2027、vandaka_plants 台湾の催し、campparkworld 4/24-25 ほか)は判断が要るので朝のタスクに残す
- rejected_revisit_stale 9件(info)

clone 削除済み
