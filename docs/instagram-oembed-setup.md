# Instagram oEmbed セットアップ手順

`scripts/instagram-oembed.py` で Instagram投稿の画像URLを取得するには、Meta(Facebook)の oEmbed Read 権限を持つアクセストークンが必要です。

このドキュメントでは、ユーザー側で実施する作業をまとめます。**Claudeは代行できないため、ご自身で以下の手順を実施してください。**

---

## 必要なもの

- Facebookアカウント(個人で可)
- 5〜30分程度の作業時間(App Review待ちを除く)

---

## ステップ1: Meta App を作成

1. https://developers.facebook.com/ にFacebookアカウントでログイン
2. 右上「マイアプリ」→「アプリを作成」
3. アプリのユースケース: 「**その他**」を選択 → 「次へ」
4. アプリタイプ: 「**ビジネス**」を選択 → 「次へ」
5. アプリ名: 例 `agave-navi-oembed` (任意)
6. 連絡先メール: ご自身のメールアドレス
7. ビジネスポートフォリオ: 個人なら「いいえ、後で行います」 → 「アプリを作成」

---

## ステップ2: oEmbed Read 製品を追加

1. アプリのダッシュボードで左メニュー「**製品を追加**」
2. **oEmbed Read** カードの「設定」をクリック → 「セットアップ」
3. これで oembed_read が有効化されます

---

## ステップ3: アクセストークンを取得

oEmbed Read 用のアクセストークンには2種類あります:

### A. App Access Token (推奨・サーバー側用)

App ID と App Secret を組み合わせるだけ。最も簡単。

1. アプリ ダッシュボード → 「設定」→「ベーシック」
2. **App ID** と **App Secret** をメモ(Secretは「表示」ボタンで確認)
3. トークンの形式: `<App ID>|<App Secret>`
   例: `123456789|abcdef0123456789abcdef0123456789`

### B. App Access Token (API経由)

```
GET https://graph.facebook.com/oauth/access_token?
    client_id=<APP_ID>
    &client_secret=<APP_SECRET>
    &grant_type=client_credentials
```
レスポンスの `access_token` を使用。

---

## ステップ4: App Review (本番利用時のみ必要)

oEmbed Read は **Standard Access** で利用できますが、サードパーティ投稿(自分以外)を取得するには **Advanced Access** を申請する必要があります。

- 開発モード: 自分の投稿および テスター追加した投稿のみ取得可
- ライブモード(Advanced Access): 公開投稿すべて

申請手順:
1. アプリ ダッシュボード → 左メニュー「**App Review**」→「権限と機能」
2. `oembed_read` の「**Advanced Access** をリクエスト」
3. 用途を記述 (例: "Aggregate event information from public Instagram posts on agave-navi.com")
4. スクリーンキャストを添付して送信
5. Meta側のレビューに 数日〜2週間程度

開発中は自分のIG投稿でテスト → ライブで全公開投稿対応、という流れ。

---

## ステップ5: GitHub Actions に組み込む

1. リポジトリ Settings → Secrets and variables → Actions → 「New repository secret」
2. Name: `IG_OEMBED_TOKEN`, Value: ステップ3で取得したトークン
3. `.github/workflows/instagram-oembed.yml` (このセットアップ後に追加するワークフロー) が自動実行される

ローカル実行:
```bash
export IG_OEMBED_TOKEN='123456789|abcdef0123456789abcdef0123456789'
python3 scripts/instagram-oembed.py --dry-run
```

---

## トラブルシューティング

| エラー | 原因と対処 |
|---|---|
| HTTP 400 | URLが正しくない / 権限不足 |
| HTTP 403 | App Review未完了で他人の投稿に対し oembed_read 不可 |
| HTTP 404 | 投稿が削除済み / 非公開アカウント |
| `Application does not have permission for this action` | oembed_read を製品に追加していない |

---

## セキュリティ注意

- App Access Token は **絶対に公開リポジトリにコミットしない**
- ローカルの `.env` か OS の環境変数で管理
- リーク時は Meta ダッシュボードで App Secret を再生成
