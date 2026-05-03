# Brave Search API セットアップ手順

`scripts/enrich_events.py` の検索バックエンドとして Brave Search API を使うための設定。

> **背景**
> Google Custom Search の「ウェブ全体を検索」機能が2026年に非推奨化され、CSE経由の汎用Web検索は事実上使えなくなりました。代替として Brave Search API を採用します。

---

## ステップ1: アカウント登録(無料)

1. https://api.search.brave.com/app/dashboard を開く
2. 「Sign up」(または「Login with Google/GitHub」でも可)
3. メール認証完了

## ステップ2: 無料プラン(Free)を選択

1. ダッシュボード左「Subscription」または「API Keys」
2. プラン: **「Free」** を選択(月2,000クエリ、1qps)
3. クレジットカード登録は不要

## ステップ3: APIキー発行

1. 「API Keys」→「+ Add API Key」
2. Name: 例 `agave-navi-enrich`(任意)
3. 発行されたキー(`BSA...` で始まる文字列)をコピー

## ステップ4: GitHub Secrets に登録

1. https://github.com/mezack0520/agave-navi/settings/secrets/actions
2. 「New repository secret」
3. Name: **`BRAVE_API_KEY`** Value: ステップ3のキー
4. 「Add secret」

## ステップ5: 動作確認

GitHub Actions の **Event Info Enrichment** workflow を手動実行:
1. https://github.com/mezack0520/agave-navi/actions/workflows/enrich-events.yml
2. 「Run workflow」→ limit を 5 程度にして「Run workflow」
3. ログに `Brave: N results for ...` が表示されればOK

---

## 検索バックエンドの優先順位

scripts/enrich_events.py は以下の順で試します:
1. **Brave Search API**(BRAVE_API_KEY) — primary
2. Google Custom Search API(GOOGLE_API_KEY + GOOGLE_CSE_ID) — 残置(将来Googleが復活させた場合の互換用)
3. DuckDuckGo HTML スクレイピング — 最終フォールバック

## 利用上限と監視

- Free プラン: 月 **2,000クエリ** / 1秒1リクエスト
- 当サイトのイベント数 100〜200件 × 月1〜4回 = 月数百クエリ程度なので余裕
- ダッシュボード「Usage」で使用状況確認可
- 上限超過時はそのリクエストだけ失敗 → DDGフォールバックへ自動降格

## トラブルシューティング

| エラー | 原因 |
|---|---|
| HTTP 401 Unauthorized | キーが正しくセットされていない / 期限切れ |
| HTTP 422 | クエリパラメータ不正 |
| HTTP 429 Too Many Requests | レート上限(1qps)超過 — workflow の sleep を調整 |
