# Search Console の取り込み

`scripts/search-demand.py` が週1回(月曜 04:07 JST)、Search Console の直近28日の検索語句を読み、
`search-demand.json` に「伸びしろ」「一覧の頁に着地した回の名前」「シリーズの名前」「未掲載の手がかり」を書く。
月曜の週次点検(site-health-check)がそれを読んで手を打つ(プレイブック §6)。

## 最初の設定(目崎が一度だけ行う)

1. Google Cloud コンソールでプロジェクトを1つ選び(新しく作ってもよい)、「API とサービス」→「ライブラリ」で **Google Search Console API** を有効にする。
2. 「IAM と管理」→「サービス アカウント」→「サービス アカウントを作成」。名前は agave-navi-gsc など。ロールは付けなくてよい。
3. 作ったアカウントの「鍵」→「鍵を追加」→「新しい鍵を作成」→ JSON。ファイルがダウンロードされる。
4. Search Console の agave-navi.com のプロパティで「設定」→「ユーザーと権限」→「ユーザーを追加」。
   メールアドレスに手順2のアカウントのアドレス(…@….iam.gserviceaccount.com)、権限は「制限付き」。
5. GitHub の mezack0520/agave-navi で「Settings」→「Secrets and variables」→「Actions」→「New repository secret」。
   名前は `GSC_SA_KEY`、値に手順3の JSON の中身を丸ごと貼る。ダウンロードしたファイルはその後消してよい。

設定したら、会話のセッションが `search-request.json` を push して初回を回す(PAT では workflow_dispatch が通らない)。

## 公開について

リポジトリは public なので、`search-demand.json` には表示10回未満の語句と、メール・電話番号の形の語句を書かない。
数字は語句ごとのクリックと表示の回数と平均順位だけ。
