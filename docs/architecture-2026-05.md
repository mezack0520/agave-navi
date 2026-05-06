# agave-navi.com アーキテクチャ全体図 (2026-05時点)

## 1. データフロー(全体俯瞰)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         [DISCOVERY 層 - 新イベント発見]                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ① Cowork Scheduled Task                                                │
│     SKILL: agave-event-update                                           │
│     ── Web検索 + 裏取り → new-events.json 作成                            │
│     ── 拒否: ticketing/aggregator URL                                   │
│                                                                         │
│  ② crawl-events.yml(月水金 09:00 JST)                                    │
│     scripts/crawl_events.py                                             │
│     ── crawl-sources.json(32ソース)を巡回                                │
│        ・公式IG / 公式site / aggregator(discovery_only)                 │
│     ── 新候補をGitHub Issue起票(label: auto-crawl)                       │
│                                                                         │
│  ③ discover-sources.yml(週水)                                           │
│     scripts/discover_sources.py                                         │
│     ── 未知ソースをDDG検索 → Issue起票(label: auto-enrich)              │
│                                                                         │
│  ④ issue-to-candidates.yml(週日)                                        │
│     scripts/issue-to-candidates.py                                      │
│     ── 上記Issueから候補抽出 → staging/candidates.json                   │
│     ── ①の SKILL がレビュー時の入力に                                     │
│                                                                         │
│  ⑤ auto-event.yml(repository_dispatch [new-event])                      │
│     ── 外部API push経由で1件追加(現在未使用)                              │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓ new-events.json
┌─────────────────────────────────────────────────────────────────────────┐
│                        [GATE層 - 品質ゲート]                             │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  scripts/sanity-check-new-events.py                                     │
│  ── 拒否1: ticketing系URL(l-tike, kyodo-osaka, eplus, pia 等9)         │
│  ── 拒否2: aggregator URL(nextmeet, botanical-zone 等7)                │
│  ── 拒否3: slug 重複                                                     │
│  ── 拒否4: 名前+日付一致 → 重複                                           │
│  ── 拒否5: 会場+日付+部分名 → likely-duplicate                            │
│  ── 拒否6: missing slug/name                                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓ events.json (本体マージ)
┌─────────────────────────────────────────────────────────────────────────┐
│                        [ENRICHMENT層 - 詳細補完]                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ⑥ enrich-events.yml(火 10:00 JST)                                      │
│     scripts/enrich_events.py + Brave Search API                         │
│     ── プレースホルダー検出('調整中'/'未定'等) → 強制対象化                │
│     ── 検索順序: Brave → Google CSE(残置) → DDGフォールバック             │
│     ── ヒットがaggregator → SKIP-ALL(全フィールド書き戻し拒否)            │
│     ── 公式site → og:image / og:description / venues / prices /          │
│        times / access を抽出 → events.json に書き戻し                    │
│     ── HTMLテーブル形式('ラベル\\n値')にも対応                            │
│     ── IG投稿URL → instagramUrl/instagramPostId                         │
│     ── description は品質チェック(ボイラープレート/言語/関連性)           │
│     ── imageURL は HEAD 検証 + aggregator/汎用OGP拒否                    │
│                                                                         │
│  ⑦ backfill-images.yml(日 10:00 JST)                                    │
│     scripts/backfill-images.py                                          │
│     ── events.json 内 url/sourceUrl/instagramUrl から og:image 補完     │
│     ── 同じ品質ゲート適用                                                 │
│                                                                         │
│  ⑧ check-date-updates.yml(毎日 06:00 JST)                               │
│     scripts/check_date_updates.py                                       │
│     ── sourceUrlから日付変更検出(aggregator skip)                        │
│                                                                         │
│  ⑨ auto-status-update.yml(毎日 07:00 JST)                               │
│     ── 終了したイベントを status='past' に自動切替                         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────────┐
│                      [BUILD/RENDER層 - 静的生成]                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  build-detail-pages.py                                                  │
│  ── events.json + templates/detail.html → events/*.html (102件)         │
│  ── 動的: og:image / Twitter Card / JSON-LD Event(image, offers,        │
│     eventStatus) / BreadcrumbList(都道府県含) / 公式情報rows /            │
│     hero画像 / Instagram埋込 / マップ / シェアボタン                      │
│  ── 過去30日経過 → robots="noindex,follow"                               │
│                                                                         │
│  scripts/sync-index-cards.py                                            │
│  ── index.html の各カードのサムネを events.json と同期                    │
│                                                                         │
│  scripts/generate-rss.py                                                │
│  ── rss.xml(新着20件、addedDate降順)                                    │
│                                                                         │
│  scripts/generate-itemlist-jsonld.py                                    │
│  ── index.html の <head> に upcoming最新12件 ItemList JSON-LD埋込        │
│                                                                         │
│  scripts/generate_sitemap.py                                            │
│  ── sitemap.xml(image:image namespace付、117 URLs)                      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                              ↓ git commit + push (5回retry付)
                              ↓
                       GitHub Pages 自動デプロイ
                              ↓
                    https://agave-navi.com/
```

## 2. ヘルスチェック層(品質維持)

```
┌─────────────────────────────────────────────────────────────────┐
│  ⑩ image-health.yml(月初)                                       │
│     scripts/image-health-check.py                               │
│     ── 全 imageUrl に HEAD → 4xx/5xx/timeout は null化           │
│     ── 翌火曜の enrich-events で自動再取得                         │
├─────────────────────────────────────────────────────────────────┤
│  ⑪ data-integrity.yml(週月+pushトリガー)                        │
│     scripts/data-integrity-check.py                             │
│     ── duplicate slug / pref-region整合 / date-dateEnd 前後 /   │
│        date format を検証 → 不整合あれば Issue起票               │
├─────────────────────────────────────────────────────────────────┤
│  ⑫ link-check.yml(週月)                                         │
│     scripts/check-links.sh                                      │
│     ── 全リンク死活チェック → 切れがあれば Issue起票             │
├─────────────────────────────────────────────────────────────────┤
│  ⑬ event-check.yml(毎日 09:00 JST)                              │
│     scripts/check_events.py                                     │
│     ── 期限切れチェック + 公式URL生死 → Issue起票                │
├─────────────────────────────────────────────────────────────────┤
│  ⑭ domain-check.yml(月初)                                       │
│     ── SSL/ドメイン期限の inline チェック → Issue起票            │
└─────────────────────────────────────────────────────────────────┘
```

## 3. 全Workflow一覧(時刻順)

| 実行タイミング | Workflow | 役割 |
|---|---|---|
| 毎日 06:00 JST | check-date-updates | sourceUrlから日付変更検出 |
| 毎日 07:00 JST | auto-status-update | 終了→past自動切替 |
| 毎日 09:00 JST | event-check | 期限/URL生死チェック |
| 月水金 09:00 | crawl-events | 32ソース巡回 → Issue |
| 火 10:00 JST | enrich-events | events.json 全件 enrichment |
| 水 09:00 JST | discover-sources | 新ソース候補発見 |
| 月 10:00 JST | link-check | リンク切れ |
| 日 07:00 JST | issue-to-candidates | Issue → staging |
| 日 10:00 JST | backfill-images | og:image 補完 |
| 月 09:00 JST | data-integrity | events.json整合 |
| 月初 09:00 | domain-check | SSL/ドメイン |
| 月初 11:00 | image-health | imageUrl HEAD |
| push trigger | update-sitemap | sitemap.xml |
| 手動 / dispatch | sync-events / auto-event | new-events.json マージ |

## 4. データスキーマ(events.json 抜粋)

```json
{
  "slug": "fukuoka-green-party-6th-2026",
  "name": "第6回 福岡グリーンパーティー",
  "date": "2026-05-03",
  "dateEnd": "2026-05-04",
  "dateDisplay": "2026.05.03-04",
  "venue": "志摩中央公園",
  "mapQuery": "志摩中央公園",
  "prefecture": "福岡",
  "region": "九州",
  "description": "...",
  "tags": ["即売会"],
  "status": "upcoming",         // upcoming / past
  "eventStatus": "confirmed",    // confirmed / cancelled / postponed / rescheduled
  "imageUrl": "https://...",
  "url": "https://公式site.com/",
  "sourceUrl": "https://www.instagram.com/<handle>/",
  "instagramUrl": "https://www.instagram.com/p/<id>/",
  "instagramPostId": "<id>",
  "admission": "500円(高校生以下無料)",
  "time": "10:00〜16:00",
  "access": "JR〇〇駅徒歩5分 / 〇〇IC隣接",
  "addedDate": "2026-04-01"
}
```

## 5. SEO/収益のためのレイヤー

```
   コンテンツ生成層
   ↓
 ┌────────────────────────────────────────────┐
 │ ・各詳細ページ: title / meta-description /   │
 │   canonical / og:image動的 / Twitter Card / │
 │   robots(active=index, past+30d=noindex)    │
 │ ・JSON-LD: Event(image,offers,eventStatus)/ │
 │   BreadcrumbList(ホーム>地域>都道府県>名)     │
 │ ・index: WebSite+Organization+Breadcrumb+   │
 │   ItemList(動的upcoming12件)                │
 │ ・category: CollectionPage+Breadcrumb       │
 ├────────────────────────────────────────────┤
 │ ・sitemap.xml(image:image)                  │
 │ ・rss.xml(新着20件)                          │
 │ ・robots.txt(Crawl-delay+害悪botブロック)    │
 │ ・PWA manifest.webmanifest                  │
 │ ・速度: lazy-loading + preconnect/dns-prefetch │
 └────────────────────────────────────────────┘
   ↓
   収益(AdSense Auto Ads + 楽天/ValueCommerce/Amazon)
   詳細ページ下部に .ad-affiliate-area + AdSense自動配信
```

## 6. キーファイル一覧

```
agave-navi/
├ events.json                  ← データ本体(102件)
├ index.html                   ← トップ(112件カード静的+動的JSON-LD)
├ events/<slug>.html           ← 詳細ページ(template生成)
├ category/{sokubai,marche,large,exhibition}.html
├ ikitai.html / calendar.html / map.html
├ build-detail-pages.py        ← detail HTML生成
├ templates/detail.html        ← 詳細テンプレート
├ scripts/
│  ├ enrich_events.py            ← Brave検索+書き戻し
│  ├ backfill-images.py          ← og:image補完
│  ├ sanity-check-new-events.py  ← 入口ゲート
│  ├ image-health-check.py       ← imageUrl HEAD監視
│  ├ data-integrity-check.py     ← データ整合性
│  ├ generate-rss.py             ← RSS feed
│  ├ generate-itemlist-jsonld.py ← 動的ItemList
│  ├ generate_sitemap.py         ← サイトマップ
│  ├ sync-index-cards.py         ← index ↔ events.json同期
│  ├ issue-to-candidates.py      ← Issue → staging
│  ├ crawl_events.py / discover_sources.py / check_events.py
│  └ check_date_updates.py
├ .github/workflows/(14ワークフロー)
└ docs/
   ├ architecture-2026-05.md   ← この文書
   ├ event-data-prompt.md       ← イベント追加プロンプト
   ├ setup-guide.md             ← セットアップ
   ├ brave-search-setup.md      ← Brave API設定
   ├ workflow-audit-2026-05.md  ← workflow監査
   └ events-needing-image.md    ← 手動補完リスト
```
