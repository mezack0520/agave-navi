# site-health-check 2026-11-16

- 構造: 詳細2(urban-jungle-weeks / art-bikakushida)・トップ・ガイド(agave-seedling)・ランディング(pref/aichi・tag/agave)を ?cb 付きで確認。canonical 正常、JSON-LD は詳細 Event+BreadcrumbList、ガイド Article+BreadcrumbList、壊れた画像 0、375幅で横スクロールなし
- アフィリエイト: tag=aganavi-22 のみ、旧ID agavenavi-22 なし。.rk-card 3、agn_rk_v1 あり。.aff-mercari は詳細・タグ・ガイドで枠の先頭(pref は無しで仕様どおり)。.aff-bar は1280幅で DOM に無し、375幅で is-shown・Amazon。隠れたペインでトランジションが止まるだけで、transition を切ると画面内(top 749)。ガイドで楽天の .aff-shop-btn が1行出たのは .rk-card の無い行で仕様どおり(§3.11 を直した)。コンソールエラー 0
- Actions: 11-15 06:32 JST 以降の60件で failure 0。cancelled は pages build 5件(後続 push による取り消し)
- audit: urgent 0(11-05 以降 11-08 の1件を除き0)。info は task_run_gap 1・cross_script_duplicate 3・rejected_revisit_stale 9
- 修正:
  - cross_script_duplicate: _load / diff / render は役割が別の汎用名なので audit.py の _DUP_OK に理由付きで追加。再実行で 0
  - rejected_revisit_stale 9件: event-monitor が 11-14〜16 の3回「ブラウザ要」で未対応に書くだけで誰も拾っていなかった。プレイブックの表に、agave-event-update が1日3件まで rejected_revisit_due と同じ手順で見る行を足した。今回は9件の一次情報は見ていない
  - task_run_gap: agave-event-update 2026-11-09 はレポートも成果物のコミットも無く、実行されていない。単発で以後毎日動いている
- キュー: Search Console の Secret GSC_SA_KEY 未設定を積んだ(11-16 の実行ログで確認。search-demand.json が無い)

## 週次の自己点検
1. 直近7日のレポート28件: 2回以上の失敗は rejected_revisit_stale の放置(上記で手順に入れた)
2. audit-history: urgent は 11-08 の1件のみ。info 3〜8 で推移、悪化なし
3. search-demand.json: 無い。Secret 未設定(キューに積んだ)
4. pending-judgments: 今回の1件のみ
5. task_run_gap は上記。work\ の回収: 反映を確かめた patch 6件(event-monitor 11-03/11-04/11-07、eyecatch-20261022、ads/bar-20261020)、9月の bundle・候補 json、日付付きの eyecatch 一時フォルダを work\_to_delete\ に移した(計36件。削除は目崎が行う)。fixlog/linkcheck/matome/orgig/resched/roots の patch と eyecatch の bundle は反映を確かめられず残した
6. プレイブック: 61KB(上限72KB)。日付の付いた行は7か所で、経緯の追記の節は無し

clone 削除済み
