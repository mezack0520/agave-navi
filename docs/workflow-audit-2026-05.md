# Workflow & Schedule 総点検レポート (2026-05-04)

## サマリー
- 全 13 → **12** workflows(`fix-header-links.yml` 削除)
- 不健全データ要因: `crawl-sources.json` から aggregator 3件削除
- aggregator 対策: `crawl_events.py` / `discover_sources.py` / `check_date_updates.py` に共通ブロックリスト追加

## 各workflow 役割と頻度

| Workflow | 頻度 | 役割 | 状態 |
|---|---|---|---|
| **sync-events.yml** | 手動 | new-events.json マージ + Brave enrich + ビルド | ✓ 修正済み |
| **auto-event.yml** | repository_dispatch | API経由1件追加 → 同上パスを通る | ✓ 修正済み |
| **enrich-events.yml** | 火 10:00 JST | 全upcoming 巡回 enrich | ✓ Brave統合済 |
| **backfill-images.yml** | 日 10:00 JST | events.json内urlからog:image補完 | ✓ aggregator対策済 |
| **auto-status-update.yml** | 毎日 07:00 JST | 終了→pastステータス自動切替 | ✓ |
| **check-date-updates.yml** | 毎日 06:00 JST | sourceUrl から日付変更検出 | ✓ aggregator skip追加 |
| **event-check.yml** | 毎日 09:00 JST | 期限切れチェック → Issue起票 | ✓ |
| **crawl-events.yml** | 月水金 09:00 JST | crawl-sources 巡回 → 新候補をIssue | ✓ aggregator対策済 |
| **discover-sources.yml** | 水 09:00 JST | 新巡回先をWeb発見 → Issue起票 | ✓ aggregator対策済 |
| **link-check.yml** | 月 10:00 JST | 全リンク死活チェック | ✓ |
| **domain-check.yml** | 月初 09:00 JST | SSL/ドメイン期限チェック | ✓ |
| **update-sitemap.yml** | push trigger | sitemap更新 | ✓(他workflow内でも更新するが二重で問題なし) |

## 削除したもの
- **`.github/workflows/fix-header-links.yml`**: 過去の一回限り修正用、役目終了
- **`scripts/fix-header-fav-link.py`**: 同上

## crawl-sources.json から削除した aggregator
- Leaf Laboratory: leaf-laboratory.com/pages/events-agave
- BOTANICAL ZONE: botanical-zone.tokyo/
- NextMeet: nextmeet.app/plants

## 共通ブロックリスト
3つのスクリプトに同一の `AGGREGATOR_BLOCKLIST` を追加:
- nextmeet.app / botanical-zone.tokyo / leaf-laboratory.com
- tochinavi.net / pukubook.jp / fukuoka-now.com / churatoku.net

`is_aggregator(url)` 関数で URL文字列全体を検査(CDN proxy対応)。

## Coworkスケジュールタスク (`Documents/Claude/Scheduled/agave-event-update`)
- 役割: Web検索 → 新規イベント発見 → curl で `new-events.json` を作成
- ⚠️ **PAT がプレーンテキストで埋め込み**: 改善余地(別タスクで)
- 現在のフロー: SKILL.md → new-events.json 作成 → ユーザーが手動 sync-events 実行
  - Brave enrich step が走るので imageUrl/url が自動補完される
