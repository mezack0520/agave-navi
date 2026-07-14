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
| `crawl-sources.json` | 週次クローラの巡回先(52+自動候補) | 手動+discover_sources |
| `check-results.json` | 日次チェック結果(メール本文の素) | health.yml |
| `scripts/sitelib.py` | 単一情報源(スラッグ表/日付整形/共通ヘッダフッタ/CSS版数) | 手動 |

## 2. 毎日のタイムライン (JST)
```
06:00  [GitHub] daily.yml
       check_date_updates.py(公式ソースから日付スクレイプ照合)
       → status自動更新(upcoming→past) → eventCountバッジ → build-all.sh → push
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
       回答シート(Google Form)をChromeで読取 → 新着は種別問わず dispatch(notify-inquiry)=即メール
       → 掲載リクエスト:裏取り→new-events.json+sync-events / 修正・訂正:キュー積み(自動書換なし)
       → inquiries-processed.json更新
11:00  [Claude] agave-navi-event-monitor
       events.json不整合検査 → 確定できるもの(status/time由来の日付)は自動修正PUT
       → dispatch(daily)で再生成 → 確定不能はキューへ追加・解消分は消し込み
随時    [GitHub] sync-events.yml (dispatch: sync-events)
       new-events.json → sanity-check(チケット/aggregator/無関係イベントドメイン拒否)
       → events.jsonへマージ → enrich → indexカード追加 → build-all.sh → push
随時    [GitHub] notify-inquiry.yml (dispatch: notify-inquiry) → Gmail即時送信
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
sync-index-cards.py     indexサムネ同期+削除イベントのカード自動除去
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
- **問い合わせ** → 受信の都度 notify-inquiry で即時メール(7/2見逃し事故の恒久対応)
- Cowork上のタスク報告は3行以内(見なくてよい設計)
- ユーザーの操作: メールを見る → 必要ならCoworkで「キューの◯◯を反映/却下」と指示するだけ

## 6. 自己拡張ループ
```
新イベント登録(url/sourceUrlに公式IG) → 翌日build: watch-sources.jsonに主催者が自動追加
→ 日次タスクがローテ巡回 → 次回開催を検知 → 登録 → (最初へ)
```
新規主催者の発見はStep0カバレッジスイープが担う(ウォッチは既知主催者の再来専用)。

## 7. 制約・注意(ハマりどころ)
- PAT(`C:\Users\yujim\.agave-navi\github.pat`)は**contents権限のみ**。repository_dispatchは可、
  workflow_dispatch/Actions APIは403。定期失効するので401が出たら長期限で再発行
- Claudeタスクは**Coworkアプリ起動中のみ**実行される。プロンプト変更後は「Run now」でツール事前承認
- Instagram/nextmeetはサーバーから読めない → Google検索スニペット経由 or ユーザーChromeで読む
- 挿入系スクリプトは必ず冪等設計(除去→再挿入)。過去にcalendar/mapが4.2MBまで肥大した事故あり
- デザインはモノクロ基調・スマホ軸・装飾控えめ(詳細はメモリ/過去コミット参照)
