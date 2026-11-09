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
| `new-inquiries.json` | 問い合わせ新着の受け渡し箱。連絡先は入れない。通知メールはGASが送る(2026-09-07に1通へ統合) | event-listing-review |
| `rejected-events.json` | 掲載見送り決定の記録。event-updateは掲載中のイベントを再提案しない | ユーザー決定をClaudeが記録 |
| `docs/task-playbook.md` | タスク共通の運用手順。**タスク自身が更新してよい**唯一の恒久化先 | 各Claudeタスク |
| `audit-history.json` | 監査結果の推移(直近90件)。改善/悪化の判断に使う | scripts/audit.py |
| `listing-policy.json` | 掲載基準の機械可読版。event-updateが判断に使い、書いていない類型だけキューに積む | 人間の決定をClaudeが記録 |
| `crawl-sources.json` | 既知の情報源の一覧。generate-watchlist.py が公式候補の重複除けに使う(週次クローラは 2026-09-30 に廃止) | 手動 |
| `check-results.json` | 日次チェック結果(メール本文の素) | health.yml |
| `audit-results.json` | 整合監査の結果。除外・欠落・孤児を毎ビルドで記録 | scripts/audit.py |
| `scripts/sitelib.py` | 単一情報源(スラッグ表/日付整形/共通ヘッダフッタ/CSS版数) | 手動 |

## 2. 毎日のタイムライン (JST)

2026-10-06 に詰めた。目崎の指示は「全体をコンパクトに、メールは9時に」。
**朝の流れは PC のタスクが合図ファイルを push して進める**(scripts/request-run.py)。
タスクは 2026-10-18 からクラウドのスケジュール済みタスク(`list_triggers` で見える)で、PC が起きていることが前提。
GitHub の schedule は時刻を当てにできない(daily の 06:00 指定は 08:50〜10:40、
health の 00:00 指定は 11時台、03:00 指定は 18〜19時台に走り、health は 10/5・10/6 に走らなかった)。
schedule はどちらも合図が来なかった日の保険で、合図で済んだ日は巡回もメールもしない。
```
06:30  [Claude] event-listing-review
       起動記録(record-run.py)がその日最初なら crawl-request.json を書く → 一緒に push
       回答シート(Google Form)を Sheets コネクタで読取 → 新着は種別問わず new-inquiries.json に書いてpush
       → 掲載リクエスト:裏取り→new-events.json+sync-events / 修正・訂正:キュー積み(自動書換なし)
06:3x  [GitHub] daily.yml (crawl-request.json の push で起動。約8分)
       check_date_updates.py / coverage-sweep.py(未掲載) / check-cancelled.py(中止) /
       ig-organizer-watch.py(主催IG・アイキャッチ候補) → build-all.sh → push
07:00  [Claude] agave-event-update (約10〜20分)
       直近14日カバレッジスイープ → watch-sources巡回 → 裏取り → new-events.json → sync-events
       → 日次メールに出る項目を報告前に直す(プレイブック「日次メールの項目は、報告する前に直す」)
07:45  [Claude] agave-navi-eyecatch (約5分)
       CIの候補(staging/eyecatch/)を目で見て採否 → 候補が無い回だけ組み込みブラウザで取る
08:15  [Claude] agave-navi-event-monitor (約5〜10分)
       events.json不整合検査 → 確定できるものは自動修正 → 確定不能はキューへ
       → 最後に request-run.py mail で mail-request.json を push(メールの合図)
08:3x  [GitHub] health.yml (mail-request.json の push で起動。約10分) → 日次メール(9時までに届く)
       build-all.sh で作り直して監査し直す(メールの「残っていること」はこの監査)
       check_events.py: 本日開催/URL死活(終わっていない回のみ)/TBD(開催前のみ)/内容妥当性
       → 判断が必要なこと・サイトに反映したこと・直せず残ったことだけを送る。無い日は送らない
保険    daily.yml schedule 21:00 UTC(実際 9〜11時)/ health.yml schedule 00:00 UTC(実際 11時台)
随時    [GitHub] sync-events.yml (dispatch: sync-events)
       new-events.json → sanity-check(チケット/aggregator/無関係イベントドメイン拒否)
       → events.jsonへマージ → enrich → indexカード追加 → build-all.sh → push
随時    [GitHub] notify-inquiry.yml (push: new-inquiries.json) → 受け渡し箱の見張りのみ
       JSONとして読めなくなったときだけ警報を送る。通知メールは送らない
       (2026-09-07: 同じ1件でGASと2通届いていたためGAS側に一本化)
push毎  [GitHub] pages build and deployment → 本番反映(CDNキャッシュ~10分)
```

## 3. 週次
```
月 09:04 [Claude] agave-navi-site-health-check
         ページ構造(event-hero/eh-spec/status-auto.js等の現行基準)・Actions失敗検出
         → 失敗があれば dispatch(daily) で自動再ビルド / 提案系はキューへ(最大2件/週)
日 10:00 [GitHub] weekly-enrichment.yml
         enrich_events.py(欠損フィールド補完) → backfill-images.py --upcoming-only
         (daybook記事本文フライヤー・開催日照合・汎用/無関係画像拒否) → build-all.sh
```

## 4. ビルドチェーン (scripts/build-all.sh — 全ワークフロー共通の単一情報源)
```
build-detail-pages.py   詳細205頁: ヒーロー/スペック表/地図(会場名フォールバック)/開催履歴/
                        近隣イベント/FAQ(JSON-LD)/折りたたみガイド/関連記事(スコア2+分散2)
build-guides.py         ガイド(原稿は guides_content/NN_*.py。統計記事はevents.jsonから自動集計)
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
運用上の規則と注意は `docs/task-playbook.md` に1か所でまとめている(2026-11-08 にここから移した)。ここには設計の前提だけを置く。
- デザインはモノクロ基調・スマホ軸・装飾控えめ(詳細はメモリ/過去コミット参照)

## 8. 履歴
変更の履歴は `docs/history.md` に移した(2026-11-09)。起動時には読まない。新しい項目もそちらの末尾に足す。
