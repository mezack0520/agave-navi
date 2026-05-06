# Instagram投稿から即イベント追加 - クイック設定ガイド

## 仕組み(全体像)

```
[Instagram投稿を見つけた]
     ↓
[1-tap でURLを送信] (iOS Shortcut / curl / Cowork SKILL)
     ↓
GitHub Actions: add-from-instagram.yml
     ↓
1. URL から post_id 抽出
2. og:meta から name/desc/image を試行取得(取れる範囲)
3. stub entry を new-events.json に作成
4. sanity-check (重複チェック)
5. events.json にマージ
6. Brave検索で公式URL/詳細補完(新規slugのみ enrich)
7. 詳細ページ + index + RSS + sitemap 再生成
8. 自動 push → GitHub Pages デプロイ
     ↓
[サイトに反映] (約2-3分)
```

## 方法A: iOS Shortcut(おすすめ)

### セットアップ(初回のみ)
1. iPhoneの「ショートカット」アプリで新規ショートカット作成
2. 名前: `agave-naviに追加`
3. アクション追加(順番):
   - **「URL」アクション**: `https://api.github.com/repos/mezack0520/agave-navi/dispatches`
   - **「ファイル」→「ショートカットの入力」**(Share Sheet 受け取り、URLのみ)
   - **「テキスト」アクション**(Body作成):
     ```
     {"event_type":"ig-event","client_payload":{"url":"<ショートカット入力>"}}
     ```
   - **「URLの内容を取得」アクション**:
     - メソッド: POST
     - ヘッダー: `Authorization: token <PATをここに>`,
       `Accept: application/vnd.github.v3+json`,
       `Content-Type: application/json`
     - 本文: 直前のテキスト
4. 共有シートに表示: ON / 受け付けるタイプ: URL のみ

### 使い方
1. Instagram投稿で「共有」→「agave-naviに追加」をタップ
2. 約2-3分後、サイトに反映

## 方法B: curl one-liner(PC側)

```bash
PAT=$(cat /path/to/github.pat | tr -d '\n\r ')
IG_URL="https://www.instagram.com/p/XXXXX/"

curl -X POST -H "Authorization: token $PAT" \
  -H "Accept: application/vnd.github.v3+json" \
  "https://api.github.com/repos/mezack0520/agave-navi/dispatches" \
  -d "{\"event_type\":\"ig-event\",\"client_payload\":{\"url\":\"$IG_URL\"}}"
```

## 方法C: GitHub Actions UI から手動

1. https://github.com/mezack0520/agave-navi/actions/workflows/add-from-instagram.yml
2. 「Run workflow」→ Instagram URL を貼り付け→ Run

## 方法D: Cowork SKILL(agave-event-update)

「<IG URL> を追加」とSKILLに依頼すれば curl コマンドを使ってtriggerできる
(SKILL.md の手順内で IG URL 直入力対応を追加可)

---

## stub entry の中身

iOS Shortcut/curl/dispatch から URL を投げた直後の events.json エントリ:

```json
{
  "slug": "ig-<post_id_short>",
  "name": "(未確定) IG投稿 <post_id>",  // og:title が取れれば使用
  "date": "",                              // 翌火曜の enrich で補完
  "venue": "調整中",
  "instagramUrl": "https://www.instagram.com/p/<post_id>/",
  "instagramPostId": "<post_id>",
  "status": "upcoming",
  "addedDate": "<today>"
  // imageUrl: og:image 取れれば付く
}
```

**直後のサイト表示**:
- 詳細ページに iframe で IG投稿が埋込
- 名前/日時は「(未確定)」「近日開催」のplaceholder
- 翌火曜の `enrich-events.yml` 実行で Brave検索 →
  公式情報源見つかれば自動補完(name, date, venue, etc.)

## 即時補完したい場合

1. 上記で追加した直後、当該slugで`enrich-events`を手動 dispatch
   ```bash
   curl -X POST -H "Authorization: token $PAT" \
     "https://api.github.com/repos/mezack0520/agave-navi/actions/workflows/enrich-events.yml/dispatches" \
     -d '{"ref":"main","inputs":{"slug":"<追加されたslug>","limit":"1"}}'
   ```
2. or 手動で events.json を編集して date/venue/name を埋める

