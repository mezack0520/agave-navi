# site-health-check 2026-11-23

- 構造: 詳細2(hanatomofesta-2026 / rojiura-botanical-2026-12)・トップ・ガイド(caudex-intro)・ランディング(tag/cactus・pref/osaka)を ?cb 付きで確認。canonical 正常、JSON-LD は詳細 Event+BreadcrumbList+FAQPage、トップ WebSite+Organization+BreadcrumbList+ItemList、ガイド Article+BreadcrumbList、ランディング CollectionPage+BreadcrumbList。壊れた画像 0、375幅で横スクロールなし
- アフィリエイト: tag=aganavi-22 のみ、旧ID agavenavi-22 なし。.aff-shop-btn は Amazon と Yahoo!。.rk-card は詳細3・ガイド2(楽天 API 200、agn_rk_v1 あり)。.aff-mercari は詳細・タグ・ガイドで枠の先頭、pref は無しで仕様どおり。.aff-bar は 375幅で is-shown、1280幅で DOM に無し。コンソールエラー 0
- Actions: 11-16 以降の144件で failure 0。cancelled は pages build 16件(後続 push による取り消し)
- audit: urgent 0(直近12日ずっと0)。info は coverage_gap_stale 1・inquiry_review_gap 1・task_run_gap 2
  - 11-21 は event-listing-review / agave-event-update / agave-navi-eyecatch の3本が発火したが何も押せていない(event-monitor 11-21 のレポートで確認)。その日だけで以後は毎日動いている。単発なので手は入れない
- 修正(search-demand の site-health-check 分、priority 上位3件 + 同じ変更で片づく1件):
  - /guides/agave-winter-hardiness.html: 題名を「アガベの耐寒性一覧: 寒さに強い品種の耐寒温度と…」に、description を耐寒温度・品種別一覧の書き出しに、本文冒頭に既存の数値をまとめた品種別の耐寒温度一覧表を追加
  - /: 題名を「全国のアガベ・多肉植物・塊根植物の植物イベント情報」に(og:title も)、description に「植物イベント」「今日・今週末」を追加
  - /region/*/: 生成器の題名を「{地方}の多肉植物・アガベイベント一覧({年}年)」、description を多肉植物・アガベ・塊根植物の即売会・マルシェ・展示会に。kanto と kansai の指示を記録
- キュー: pending-judgments 0件。先週積んだ GSC Secret 未設定は解消済み(search-demand.json あり)

## 週次の自己点検
1. 直近7日のレポート25件: 2回以上出た失敗なし。IG topsearch の分類器停止は 11-19 の1回で、§3.6 に追記済み
2. audit-history: urgent 0 が継続。rejected_revisit_stale は 9→0 に消化(先週プレイブックに入れた手順が効いた)。何週も動かない項目なし
3. search-demand: 上記の3件(+関西)を直して --log で記録。evaluations の revert 対象なし
4. pending-judgments: 0件
5. task_run_gap は上記。work\: 先週 _to_delete\ に移したはずのファイル(patch・bundle・候補 json)が work\ に戻っており、_to_delete\ にはフォルダだけが残っている。フォルダには iCloud の衝突コピー「… 2」がある。今回 event-monitor_2026-11-07.patch を1件だけ移して残るかを試した(移動直後と45秒後は移動先にあった)。来週もそこにあれば、残りを同じように移す。戻っていれば work\ の整理は目崎が Windows 側でやる
6. プレイブック: 64KB(上限72KB)。日付の付いた行は8か所で、経緯の追記の節は無し

clone 削除済み
