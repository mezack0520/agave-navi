# agave-navi.com セットアップガイド

## 0. アーキテクチャ概要(2026-05時点)

### データの単一ソース
`events.json` がすべてのイベント情報の唯一のソース。詳細ページ・トップページ表示・サイトマップ等はすべてここから生成される。

スキーマ詳細: [event-data-prompt.md](event-data-prompt.md)

主要フィールド:
- `slug`, `name`, `date`, `dateEnd`, `dateDisplay`
- `region`, `prefecture`, `venue`, `mapQuery`
- `description`, `admission`, `time`
- `imageUrl` — ヒーロー画像URL(詳細ページ上部に表示。空の場合は非表示)
- `instagramUrl` / `instagramPostId` — Instagram埋め込み用
- `tags`, `eventStatus`, `addedDate`

### ビルドパイプライン
```
events.json + templates/detail.html
            │
            ▼  python3 build-detail-pages.py
            │
            ▼
        events/*.html (100件強)
```

`build-detail-pages.py` の主要オプション:
- `--slug <slug>` 個別生成
- `--dry-run` 書き込み無しで確認

### アクティブなWorkflows(.github/workflows/)
| Workflow | 用途 | スクリプト |
|---|---|---|
| sync-events.yml | events.json更新時の詳細ページ再生成 | build-detail-pages.py |
| auto-status-update.yml | ステータス自動更新+詳細ページ再生成 | build-detail-pages.py |
| auto-event.yml | repository_dispatch で新イベントページ生成 | scripts/generate_event_page.py |
| crawl-events.yml | 月水金 自動巡回 | scripts/crawl_events.py |
| discover-sources.yml | 週次 巡回先候補発見 | scripts/discover_sources.py |
| enrich-events.yml | 週次 イベント情報の補強 | scripts/enrich_events.py |
| event-check.yml | 毎日 イベント期限チェック | scripts/check_events.py |
| check-date-updates.yml | 日付変更検出 | scripts/check_date_updates.py |
| update-sitemap.yml | サイトマップ更新 | scripts/generate_sitemap.py |
| link-check.yml | 週次 リンク切れチェック | scripts/check-links.sh |
| domain-check.yml | 月次 SSL/ドメイン期限チェック | (inline) |
| fix-header-links.yml | ヘッダーリンク自動補正 | scripts/fix-header-fav-link.py |

### イベント追加の標準フロー
1. `new-events.json` にイベントエントリを追加(必須項目だけでOK: slug/name/date/region など)
   詳細は [docs/event-data-prompt.md](event-data-prompt.md) を参照
2. リポジトリへコミット → 「Sync New Events」 workflow を手動実行
3. workflow 内で:
   - events.json にマージ
   - **新規slugだけ Brave Search で自動 enrichment**(imageUrl / url / time / admission 等を補完)
   - 詳細ページ + index.html カードを再生成
   - 自動コミット&プッシュ
4. それでも空欄の項目は、毎週火曜の `Event Info Enrichment` workflow が再試行

### 補完の仕組み (Brave Search API)
- 検索バックエンド: Brave Search API(月2,000クエリ無料枠)
- aggregator サイトは自動拒否(集約ページから複数イベントの情報を混入させない)
- 取得した imageUrl は HTTP HEAD で生存確認、汎用OGP(.../ogp.png 等)は拒否
- 詳細: [docs/brave-search-setup.md](brave-search-setup.md)

---


## 1. Google Search Console 連携

### 手順

1. **Google Search Console にアクセス**
   - https://search.google.com/search-console/ にGoogleアカウントでログイン

2. **プロパティを追加**
   - 「プロパティを追加」→「URLプレフィックス」を選択
   - `https://agave-navi.com/` を入力

3. **所有権の確認**
   - HTMLタグ方式（既に設定済み）: `<meta name="google-site-verification" content="23j_bxcczlGhWRVrlfh94HO0hYGk9qxQzfbew60oWB0" />`
   - すべてのページの `<head>` に既に埋め込み済みなので、「確認」をクリックするだけ

4. **サイトマップを送信**
   - 左メニュー「サイトマップ」をクリック
   - 「新しいサイトマップの追加」に `sitemap.xml` と入力
   - 「送信」をクリック
   - ステータスが「成功しました」になれば完了

5. **確認事項**
   - robots.txt: `https://agave-navi.com/robots.txt` → 既にサイトマップURL記載済み
   - sitemap.xml: `https://agave-navi.com/sitemap.xml` → 全30イベント + 固定ページのURL記載済み

### 送信後のチェック
- 24〜48時間後に「カバレッジ」でインデックス状況を確認
- 「URL検査」で個別ページのインデックス状態を確認可能
- 「パフォーマンス」で検索クエリ・クリック数を確認（数日後にデータが表示される）

---

## 2. GitHub Actions 自動巡回スクリプト

### 概要
- 毎週月曜 9:00 (JST) に17サイトを自動巡回
- 新イベントが見つかったらGitHub Issueとして自動報告
- 手動実行も可能

### ファイル構成
```
.github/workflows/crawl-events.yml  # ワークフロー定義
scripts/crawl_events.py             # クローラー本体
crawl-sources.json                  # 巡回先リスト（17サイト）
```

### セットアップ手順

1. **リポジトリにファイルをプッシュ**
   - `.github/workflows/crawl-events.yml`
   - `scripts/crawl_events.py`
   - これらのファイルは既にリポジトリに含まれています

2. **GitHub Actionsを有効化**
   - リポジトリの Settings → Actions → General
   - 「Allow all actions and reusable workflows」を選択
   - 「Workflow permissions」を「Read and write permissions」に設定

3. **ラベルを作成**
   - Issues → Labels → 「auto-crawl」ラベルを新規作成（色: #0075ca）

4. **手動実行でテスト**
   - Actions タブ → 「Weekly Event Crawl」→ 「Run workflow」→ 「Run workflow」ボタン

5. **結果確認**
   - Issuesタブに「[自動巡回] イベント情報更新レポート YYYY-MM-DD」が作成される
   - レポートには: 巡回結果サマリー + 新規イベント候補リスト

### 巡回先の追加・変更
`crawl-sources.json` を編集するだけで巡回先を変更できます。

---

## 3. Cloudflare 無料プラン設定手順

### メリット
- 無料CDN（世界200+拠点でキャッシュ）
- 無料SSL証明書
- DDoS攻撃防御
- アクセス分析（Web Analytics）
- ページ速度の向上

### セットアップ手順

1. **Cloudflareアカウント作成**
   - https://dash.cloudflare.com/sign-up にアクセス
   - メールアドレスとパスワードで登録

2. **サイトを追加**
   - 「サイトを追加」をクリック
   - `agave-navi.com` を入力
   - 「Freeプラン」を選択

3. **DNSレコードの設定**
   - Cloudflareが既存のDNSレコードを自動検出
   - GitHub Pages用のレコードが正しいか確認:
     ```
     タイプ: CNAME
     名前: agave-navi.com (または @)
     ターゲット: mezack0520.github.io
     プロキシ: オン（オレンジ雲）
     ```
   - `www` のCNAMEも同様に設定

4. **ネームサーバーの変更**
   - Cloudflareが表示するネームサーバー2つをコピー
   - ドメインレジストラ（お名前.com、ムームードメイン等）の管理画面で変更
   - 例: `ns1.cloudflare.com`, `ns2.cloudflare.com`
   - 反映まで最大24時間

5. **SSL/TLS設定**
   - SSL/TLS → 概要 → 「フル（厳密）」を選択
   - Edge Certificates → 「常にHTTPSを使用」をオン
   - 「自動HTTPS書き換え」をオン

6. **キャッシュ設定**
   - キャッシュ → 構成
   - 「ブラウザキャッシュTTL」を「1日」に設定
   - 画像・CSS・JSは自動的にCDNキャッシュされる

7. **速度最適化**
   - Speed → 最適化
   - 「Auto Minify」: JavaScript, CSS, HTML すべてオン
   - 「Brotli」圧縮: オン

8. **Web Analytics（分析）**
   - Analytics → Web Analytics
   - 無料のプライバシーファーストな分析ツール
   - Google Analyticsとの併用可能

### GitHub Pages + Cloudflare の注意点
- GitHub Pages側のカスタムドメイン設定はそのまま維持
- CNAMEファイルはリポジトリに残す
- SSL証明書はCloudflareが自動管理するため、GitHub Pages側の「Enforce HTTPS」は不要

---

## 4. お問い合わせフォーム → メール通知

### 現在の構成
- Google Forms を iframe で contact.html に埋め込み済み
- フォームURL: `https://docs.google.com/forms/d/e/1FAIpQLSdwmTPPXWBAH-tP1IYQIn9x7F9tVpE1SBAL8IVcRPvb0qXhLA/viewform`

### メール通知の設定（Google Apps Script）

#### 方法: Google Forms の回答をスプレッドシート経由で通知

1. **Google Formsを開く**
   - フォームの編集画面にアクセス

2. **スプレッドシートをリンク**
   - 「回答」タブ → スプレッドシートアイコン → 「新しいスプレッドシートを作成」

3. **Apps Scriptを開く**
   - スプレッドシートの「拡張機能」→「Apps Script」

4. **以下のコードを貼り付け**

```javascript
function onFormSubmit(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var lastRow = sheet.getLastRow();
  var data = sheet.getRange(lastRow, 1, 1, sheet.getLastColumn()).getValues()[0];

  // メール設定
  var to = "yuji.mezaki@gmail.com";
  var subject = "[アガベイベントナビ] 新しいお問い合わせ";

  // ヘッダー行を取得
  var headers = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];

  // メール本文を作成
  var body = "アガベイベントナビに新しいお問い合わせがありました。\n\n";
  body += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n";

  for (var i = 0; i < headers.length; i++) {
    body += "【" + headers[i] + "】\n";
    body += (data[i] || "（未入力）") + "\n\n";
  }

  body += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n";
  body += "このメールはGoogle Formsの自動通知です。\n";
  body += "回答の詳細: " + SpreadsheetApp.getActiveSpreadsheet().getUrl();

  // メール送信
  MailApp.sendEmail({
    to: to,
    subject: subject,
    body: body
  });
}
```

5. **トリガーを設定**
   - Apps Script エディタの左メニュー「トリガー」（時計アイコン）
   - 「トリガーを追加」をクリック
   - 設定:
     - 実行する関数: `onFormSubmit`
     - イベントのソース: 「スプレッドシートから」
     - イベントの種類: 「フォーム送信時」
   - 「保存」→ Googleアカウントの認証を承認

6. **テスト**
   - contact.html からテスト送信
   - yuji.mezaki@gmail.com にメールが届くことを確認

### events.json による管理フロー（テンプレートシステム導入済み）
1. イベント情報を `events.json` に追加・編集（[情報収集プロンプト](event-data-prompt.md) を参照）
2. `python3 build-detail-pages.py` を実行 → 全詳細ページが自動生成
3. コミット＆プッシュ → GitHub Pagesが自動デプロイ
- 個別の詳細ページHTMLを直接編集する必要はありません
- テンプレート: `templates/detail.html`

---

## 5. 運用チェックリスト

### 週次タスク
- [ ] GitHub Issues で自動巡回レポートを確認
- [ ] 新規イベント候補があれば events.json に追加
- [ ] お問い合わせメールを確認・対応

### 月次タスク
- [ ] Google Search Console でインデックス状況を確認
- [ ] Google Analytics でアクセス数を確認
- [ ] 過去イベントの status を "past" に更新
- [ ] 新しい巡回先があれば crawl-sources.json に追加
