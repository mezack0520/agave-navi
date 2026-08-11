# agave-navi.com 運用アーキテクチャ (2026-07-13時点)

「誰が・いつ・何をするか」の全体図。実行主体は3つ:
**Claudeスケジュールタスク**(ユーザーPCのCowork上で実行、判断を伴う仕事)、
**GitHub Actions**(機械的な定期処理)、**ビルドチェーン**(全ページ生成)。

## 1. データの正とファイル
| ファイル | 役割 | 書き手 |
|---|---|---|
| `events.json` | イベントデータの正(205件) | daily.yml / sync-events / event-monitor |
| `new-events.json` | 新規イベントの受け渡し箱 | Claudeタスク → sync-events.ymlが取り込み |
| `watch-sources.json` | ウォッチ対象(IG主催者/次回待ちシリーズ/公式サイト候補)。events.jsonから毎日自動導出 | generate-watchlist.py |
| `pending-judgments.json` | 要人間判断キュー。健全性メールに集約表示 | 各Claudeタスク(id重複禁止・解消時自削除) |
| `inquiries-processed.json` | フォーム回答の処理済み管理 | event-listing-review |
| `new-inquiries.json` | 問い合わせ新着の受け渡し箱。pushで notify-inquiry.yml が発火しメール送信 | event-listing-review |
| `rejected-events.json` | 掲載見送り決定の記録。event-updateは掲載中のイベントを再提案しない | ユーザー決定をClaudeが記録 |
| `docs/task-playbook.md` | タスク共通の運用手順。**タスク自身が更新してよい**唯一の恒久化先 | 各Claudeタスク |
| `audit-history.json` | 監査結果の推移(直近90件)。改善/悪化の判断に使う | scripts/audit.py |
| `listing-policy.json` | 掲載基準の機械可読版。event-updateが判断に使い、書いていない類型だけキューに積む | 人間の決定をClaudeが記録 |
| `crawl-sources.json` | 週次クローラの巡回先(52+自動候補) | 手動+discover_sources |
| `check-results.json` | 日次チェック結果(メール本文の素) | health.yml |
| `audit-results.json` | 整合監査の結果。除外・欠落・孤児を毎ビルドで記録 | scripts/audit.py |
| `scripts/sitelib.py` | 単一情報源(スラッグ表/日付整形/共通ヘッダフッタ/CSS版数) | 手動 |

## 2. 毎日のタイムライン (JST)
```
06:00  [GitHub] daily.yml
       check_date_updates.py(公式ソースから日付スクレイプ照合)
       → build-all.sh → push
       (status自動更新と eventCountバッジ は build-all.sh 内に移管。2026-08-10)
08:06  [Claude] agave-event-update
       Step0 直近14日カバレッジスイープ(日付明示のWeb検索+pukubook地域頁+leaf個別記事)
       → watch-sources巡回(次回待ちシリーズ10+IG主催者ローテ約10/日・8日で一巡)
       → まとめブログ/aggregator広域探索 → 裏取り(公式ソース必須・拒否ドメイン照合)
       → new-events.json作成(contents API) → dispatch(sync-events)
09:00  [GitHub] health.yml
       check_events.py: 本日開催/URL死活(終了30日以内のみ)/TBD(開催前のみ)/内容妥当性
       (入場料異常・説明文混入・日付なしupcoming・無関係ドメイン)
       → pending-judgments.jsonを集約した日次メールをGmail送信
       (件名に【要判断n件】/ 新着・本日開催・今後一覧・異常検知)
10:09  [Claude] event-listing-review
       回答シート(Google Form)をChromeで読取 → 新着は種別問わず new-inquiries.json に書いてpush
       (=notify-inquiry.ymlが発火し即メール)
       → 掲載リクエスト:裏取り→new-events.json+sync-events / 修正・訂正:キュー積み(自動書換なし)
       → inquiries-processed.json更新
11:00  [Claude] agave-navi-event-monitor
       events.json不整合検査 → 確定できるもの(status/time由来の日付)は自動修正PUT
       → dispatch(daily)で再生成 → 確定不能はキューへ追加・解消分は消し込み
随時    [GitHub] sync-events.yml (dispatch: sync-events)
       new-events.json → sanity-check(チケット/aggregator/無関係イベントドメイン拒否)
       → events.jsonへマージ → enrich → indexカード追加 → build-all.sh → push
随時    [GitHub] notify-inquiry.yml (push: new-inquiries.json) → Gmail即時送信
       items空のpushでは送らない。送信後の消し込みは次回タスクが行う
push毎  [GitHub] pages build and deployment → 本番反映(CDNキャッシュ~10分)
```

## 3. 週次
```
月 09:04 [Claude] agave-navi-site-health-check
         ページ構造(event-hero/eh-spec/status-auto.js等の現行基準)・Actions失敗検出
         → 失敗があれば dispatch(daily) で自動再ビルド / 提案系はキューへ(最大2件/週)
水 09:00 [GitHub] weekly-discovery.yml
         crawl_events.py(crawl-sources 52+watch-sources公式候補を巡回)
         → discover_sources.py(新ソース発掘) → 候補issue化
日 10:00 [GitHub] weekly-enrichment.yml
         enrich_events.py(欠損フィールド補完) → backfill-images.py --upcoming-only
         (daybook記事本文フライヤー・開催日照合・汎用/無関係画像拒否) → build-all.sh
```

## 4. ビルドチェーン (scripts/build-all.sh — 全ワークフロー共通の単一情報源)
```
build-detail-pages.py   詳細205頁: ヒーロー/スペック表/地図(会場名フォールバック)/開催履歴/
                        近隣イベント/FAQ(JSON-LD)/折りたたみガイド/関連記事(スコア2+分散2)
build-guides.py         ガイド21本(統計記事はevents.jsonから自動集計)
build-static-html.py    map/calendar SSR埋め込み(冪等・除去→再挿入)
sync-index-cards.py     indexサムネ同期+削除イベントのカード自動除去+開催予定バッジ更新
generate-rss.py / generate-itemlist-jsonld.py
generate-landing-pages.py  tag/pref/region/venue/archive/category/new/this-weekend等
                        (イベント<3件はnoindex,follow+sitemap除外、固有解説文、空頁fallback)
generate-ical.py / generate-csv.py
generate-watchlist.py   watch-sources.json自動導出(自己拡張ループの心臓)
sync-footers.py         全静的頁(404含む)のフッターをsitelib正規版に同期
generate_sitemap.py     noindex頁/内部ツール/終了30日超イベントを除外
```

## 5. 通知と判断の一元化ルール
- **自動修正できるもの** → 各タスク/ワークフローが黙って実行(コミットメッセージに主体を明記)
- **人間の判断が必要なもの** → `pending-judgments.json` に積む → 翌日の健全性メール件名に【要判断n件】
- **問い合わせ** → 受信の都度 new-inquiries.json のpushで即時メール(7/2見逃し事故の恒久対応)。
  dispatchではなくpushで発火する(§7)
- Cowork上のタスク報告は3行以内(見なくてよい設計)
- ユーザーの操作: メールを見る → 必要ならCoworkで「キューの◯◯を反映/却下」と指示するだけ

## 6. 自己拡張ループ
```
新イベント登録(url/sourceUrlに公式IG) → 翌日build: watch-sources.jsonに主催者が自動追加
→ 日次タスクがローテ巡回 → 次回開催を検知 → 登録 → (最初へ)
```
新規主催者の発見はStep0カバレッジスイープが担う(ウォッチは既知主催者の再来専用)。

## 7. 制約・注意(ハマりどころ)
- PAT(`mzplants\agave-navi\github.pat`)は**ワークフローファイルのpushができる**(2026-08-10に実測)。
  `.github/workflows/` 配下も git push で更新できる。workflow_dispatch/Actions APIは403のままで、
  サンドボックスから api.github.com も不通。定期失効するので401が出たら長期限で再発行。
  2026-08-10まで『contents権限のみでワークフローは触れない』と誤って記録されており、
  この思い込みで notify-inquiry.yml の修正が10日間放置された
- Claudeタスクは**Coworkアプリ起動中のみ**実行される。プロンプト変更後は「Run now」でツール事前承認
- Instagram/nextmeetはサーバーから読めない → **Chromeで google.com/search?hl=ja&tbs=qdr:w2** が主経路
  (WebSearchのUS版ではIG告知がほぼ拾えない)
- **repository_dispatchは使わない。** events.json / new-events.json / new-inquiries.json のpushでワークフローが
  起動する(daily.yml / sync-events.yml の on.push)。Chrome経由のdispatchは、認証ヘッダ付きfetchが
  Chromeツール側で遮断されPromiseが解決しなくなったため2026-07-31に廃止した
  (以前はService Worker干渉と見ていたが、SWは未登録で原因が別だった)。
  サンドボックスからの api.github.com 直叩きも不通。**ローカルで build-all.sh を回して
  生成物ごとpushする**のが標準手順
- **GITHUB_TOKENによるpushはワークフローを再起動しない**(GitHubの仕様)。だからCI側の自動コミットで
  ループしない。PATでpushしたときだけ on.push が発火する
- sanity-check-new-events.py は既存slugを落とす。**既存イベントの修正は events.json を直接編集**する
- サンドボックスの nohup バックグラウンド実行は呼び出し終了時に殺される。build-all.sh は45秒制限に
  収まらないので scripts を4〜6本ずつ前景で順に叩く
- pushが non-fast-forward で拒否されたら、生成物のrebaseは衝突する。**origin/main に reset --hard
  → データ変更を再適用 → 再ビルド → push** の順でやり直す
- CSS/JSを変えたら scripts/sitelib.py の CSS_VERSION / JS_VERSION を上げる。上げないと閲覧者の
  キャッシュが更新されず変更が届かない
- 都道府県→地域の定義は **scripts/sitelib.py の PREF_TO_REGION が単一情報源**。沖縄は九州、
  山梨・長野は北陸。各スクリプトが独自定義を持っていて割れた事故がある
- 挿入系スクリプトは必ず冪等設計(除去→再挿入)。過去にcalendar/mapが4.2MBまで肥大した事故あり
- デザインはモノクロ基調・スマホ軸・装飾控えめ(詳細はメモリ/過去コミット参照)

## 8. 履歴
- 2026-08-10: 要判断キュー7件を一括処理し、同じ類型が再び上がらないよう listing-policy に
  4項目を追加(venueRecord / descriptionFreshness / descriptionProvenance /
  compositeEvents.undisclosedBreakdown)。データ側は二重掲載1件の統合、前年告知の使い回し1件の
  書き直し、協賛企業の告知文1件の削除、裏取り不能な開催時間1件の削除、location欠落6件の補完。
  終了済みで会場不明な回の表示を「会場未定」から「記録なし」に変更(未定はこれから決まるの意味で
  終わった回には当てはまらない)。audit.py の duplicate_venue_date が同一建物内の別ホールを
  誤検知していたため下位区画(ホール/館/階/催事場等)を除外。真陽性は合成データで検出を確認済み。
  季節連動は育成LEDを9月開始から10月開始に変更(9月は関東ではまだ屋外最盛期)、遮光ネットを追加、
  オルトランを4〜10月に設定。全12か月で3枠が埋まることを検算済み

- 2026-08-10: 運用の総点検。(1)health.yml が監査項目名をハードコードしていたため、audit.py に
  検査を追加するたびワークフロー編集が必要だった。重要度(severity)を audit.py 側に持たせ
  health.yml は動的に全項目を読むよう変更。以後は audit.py だけ直せば日次メールに反映される。
  常時0にならない項目(薄い判定・説明文70字未満・secrets)は info に落として参考行にまとめた。
  毎日叫ぶ項目が混ざると監査全体が無視されるため。
  (2)統合済みで放置されていたワークフロー13本を削除(21→8本)。すべて統合先ヘッダに「統合元」と
  明記済み。とくに auto-status-update.yml は build-all.sh を使わず9ステップを個別列挙しており、
  sync-footers(CSS/JS版数とロゴの正規化)・build-guides・generate-watchlist・audit が抜けた
  古い生成手順のままで、誤実行すると不整合な生成物が出る状態だった

- 2026-08-10: PATでワークフローファイルをpushできることを実測で確認した。docs §7 とキュー項目は『contents権限のみ、ワークフローは触れない』と記録していたが誤りで、notify-inquiry.yml の差し替えはそのままpushできた。この誤記のせいで7/31以降の通知経路の断絶とhealth.ymlの未反映検査がユーザー作業待ちのまま滞留していた。Actions API(workflow_dispatch)が403なのは事実なので、ワークフローの起動はpushトリガのみという運用は変えない
- 2026-08-10: 問い合わせの即時メール経路を push に移した。7/31に dispatch を廃止したとき notify-inquiry.yml だけ切り替え漏れがあり、発火条件が repository_dispatch のみのまま10日間 通知手段が存在しない状態になっていた(新着ゼロで実害はなし)。new-inquiries.json を新設し、event-listing-review が新着要約を書いてpushするとメールが飛ぶ。items空のpushでは送らないので消し込みで空メールは出ない。client_payload経路も互換で残してある。当初『ワークフローはPATでpushできない』と書いていたが誤りで、同日タスク側からpushして反映済み
- 2026-08-10: daily.yml から2ステップを削除した。UTC判定の Auto status update は 8/3 に scripts/auto-status-jst.py へ移管済みで冗長だった。eventCountバッジ更新は build-all.sh より前に走るため status 更新前の値を数えており、さらに sync-events / weekly-enrichment 経由のビルドでは誰も更新していなかった。sync-index-cards.py に移して build-all.sh を通る全経路で揃うようにした。あわせて health.yml の image health が events.json を書き換えたときに generate_sitemap.py を回すようにした(終了30日超で noindex になった回が翌朝まで sitemap に残っていた)
- 2026-07-27: ClaudeをTeamプランへ移行(個人→Team組織)。Coworkスケジュールタスクは移行対象外で消失したため、
  4本(agave-event-update / event-listing-review / agave-navi-event-monitor / agave-navi-site-health-check)を
  本書§2・§3の仕様どおり同日再作成。スケジュール・フローの変更なし
- 2026-07-27: 要判断4件を処理。enrich_events.pyを「開催予定×説明文70字未満」優先処理に変更、
  健全性メールに同件数の計測を追加、フェルム・ド・フェスVol.29とLOCALGREEN FESTIVAL'26は
  掲載見送り(rejected-events.json新設)、タスクの書き込みは.agave-naviフォルダ接続方式で復旧
- 2026-07-31: repository_dispatch への依存を廃止。Chrome経由でAuthorizationヘッダ付きfetchを送ると
  Chromeツール側で遮断されPromiseが解決しなくなったため(SW干渉ではなくツール側の挙動)。
  代わりに daily.yml と sync-events.yml に on.push(paths: events.json / new-events.json)を追加し、
  pushだけで再生成と取り込みが走るようにした。pushトリガ時は外部サイトのスクレイプをスキップする。
  GITHUB_TOKENのpushはワークフローを再起動しない仕様なので自己ループしない
- 2026-07-31: 都道府県→地域の定義を scripts/sitelib.py の PREF_TO_REGION に統合。沖縄が
  九州(5件)と沖縄(2件)に割れ、山梨・長野も北陸と中部で食い違い、REGION_ROMAJIに無い地域名が
  /region/region-b2e5cfe1/ というハッシュURLの頁を生んでいた。沖縄は九州に寄せ、
  data-integrity-check.py / build-static-html.py / issue-to-shops.py / generate-rss.py の
  独自定義を撤去して sitelib 参照に統一。audit.py に region_mismatch 検査を追加し日次メールにも出す
- 2026-07-31: 作業ファイルの置き場を mzplants 配下に集約。従来の C:\Users\yujim\.agave-navi は空にした。
  新配置は mzplants\agave-navi\ 配下で github.pat / task-reports\ / work\。スケジュールタスク4本の
  プロンプトも接続先とレポート出力先を更新済み。PATはOneDrive同期される点をユーザーが承知のうえ移動
- 2026-07-30: AdSenseの利用を断念し関連を全撤去。GSC実測でガイド21本の流入が90日クリック40件
  (全体の1.0%、うち34件が agave-winter-hardiness の1本)しかなく、審査対策として作った資産が
  機能していないことが確定したため。撤去内容: adsbygoogle.jsの読み込み(408頁)、
  google-adsense-accountメタ(408頁)、ads.txt、ads.js(AdSense初期化のみのため削除。
  サイドバー制御は affiliate.js へ移設)。sync-footers.py に撤去処理を入れ再混入を防ぐ。
  あわせて薄い判定の回にもアフィリエイト枠を出すよう条件を緩めた(出典があれば出す)。
  枠のある詳細ページが171→221件。天下一植物界(90日194クリック)など流入がありながら
  枠ゼロだったページを回収した。ガイドは削除せず追加投資もしない方針を維持
- 2026-07-30: JS参照に版数を導入。affiliate.js と ads.js に ?v= が付いておらず(status-auto.js だけ
  付いていた)、JSの変更が閲覧者のキャッシュを越えず届いていなかった。楽天カードが本番で
  出なかった直接の原因。sync-footers.py でCSSと同様に正規化し、audit.py に乖離検査を追加、
  日次メールの通知対象にも入れた
- 2026-07-30: 楽天商品カードをブラウザ側取得に切り替えて稼働開始。サーバー側(GitHub Actions)からは
  403 REQUEST_CONTEXT_BODY_HTTP_REFERRER_MISSING で拒否される(アプリ種別 Web Application の
  リファラ制限。Refererヘッダを付けても通らない)。accessKeyは pk_ 始まりの publishable key で
  クライアント公開が前提の設計。affiliate.js から都度取得し localStorage に24時間キャッシュ、
  レート制限に配慮して直列取得する。先にテキストで描画し取得後に差し替えるため表示は遅れない。
  rakuten-products.yml の定期実行は停止(手動/dispatchのみ残置)、product-cache.json は削除
- 2026-07-30: 楽天アフィリエイトIDをコンソール表示値(0e86e911…)に差し替え。設定値は
  5251fbf3… だった。楽天アフィリエイトIDはアカウント単位で1つ発行され(サイト登録一覧に
  サイト別IDの表示はない)、正値は楽天ウェブサービスのアプリ管理画面が示すもの。
  旧値が誤っていた場合それまでのクリックと購入は成果計上されていない
- 2026-07-30: 説明文不足の扱いを方針化。開催予定で説明文が短い回はキューに積まず
  週次エンリッチに任せる。主催者が詳細未発表なのが原因で、推測で埋めれば7/26に削除した
  自動生成文と同じものになる。listing-policy.json の shortDescriptions に doNotEscalate で記載
- 2026-07-30: 楽天ウェブサービスにアプリ登録(アガベイベントナビ/Web Application/agave-navi.com)。
  API仕様が2026-07-01版に変わっており、エンドポイントが openapi.rakuten.co.jp/ichibams/... へ移行、
  accessKey が applicationId と併用で必須になっていた。旧エンドポイントは新規発行のUUID形式
  applicationId を受け付けない。accessKeyは秘密情報のためクライアント側からは呼べず、
  ビルド時にサーバーから取得する設計が前提となる。secretsに RAKUTEN_APP_ID と
  RAKUTEN_ACCESS_KEY の2つが必要
- 2026-07-30: 監査の初回棚卸しを実施。IGハンドル未解決14→1件(投稿URLから告知アカウントを特定)、
  ウォッチ対象122→134アカウント、開催予定の薄い10→4件(公式プロフィールの事実で加筆)、
  未参照スクリプト1→0件(add-from-instagram.py削除)。薄い判定は「直せる」「アーカイブ許容」
  「開催予定で出典なし」に分類し、終了済み・出典なしの49件は対処不要と定義した
- 2026-07-30: scripts/audit.py を新設し build-all.sh の最後に組み込んだ。各スクリプトが
  成功件数だけを出力し除外・欠落・孤児を黙っていたため、問題が指摘されるまで表面化しなかった。
  slug重複/同名同日の二重掲載/孤児・欠落ページ/sitemapの死活/見送りと掲載の矛盾/
  status矛盾/フィード件数/ガイドリンク死活/CSS版数乖離/未参照スクリプト/楽天キャッシュ網羅率を
  毎回検査し、重要項目は日次メールに出す。初回検査で二重掲載1件(春のサボテン多肉植物フェア)を検出
- 2026-07-30: 掲載基準を listing-policy.json に機械可読化。同じ類型の掲載可否を毎回人間に
  問い直していたため、一次情報の要件・複合イベントの閾値(植物出店3割以上または著名店3者以上)・
  会場未発表時のTBD掲載・矛盾データの削除を明文化した。rejected-events に reasonType を導入し
  「方針として載せない(policy)」と「一次情報待ち(unverified/revisit)」を区別
- 2026-07-30: 孤児ページの掃除を詳細ページにも追加。events.jsonから削除した回のHTMLが
  本番に残りsitemapに載り続けていた(二子玉川の削除で発覚)。ランディング側と同じ穴
- 2026-07-30: 自己拡張ループの穴を塞いだ。裸の投稿URL(instagram.com/p/XXXX/)しか持たない回は
  IGハンドルが取れずウォッチ対象から静かに漏れていた(16件)。organizerIg フィールドの明示指定に
  対応し、未解決件数を watch-sources.json の stats・ビルドログ・日次メールに出すようにした。
  sanity-check も新規追加時に警告する
- 2026-07-29: アフィリエイト導線を再設計。affiliate.js + amazon-links.json に一本化し
  (ads.jsの画像URL/価格べた書き実装151行は廃止)、ランディング系・ガイド21本・イベント詳細171件に
  .affiliate-section を設置。ガイドは記事別キーワード(育成ライト/温室/薬剤等の高単価帯)を文脈連動。
  薄い判定のページには枠を出さない。AFFILIATE_ENABLED=true。AdSenseは未申請
- 2026-07-28: sync-eventsに多重dispatch安全化(checkout後にorigin/mainへreset)。同日の4重dispatchで
  余剰Runが古いSHAを再処理しpush競合失敗した件の恒久対応。dispatchは204空応答が正常・再送禁止
