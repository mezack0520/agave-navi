# Search Console の取り込み

`scripts/search-demand.py` が週1回(月曜 04:07 JST)、Search Console の直近28日の検索語句を読み、
`search-demand.json` に「伸びしろ」「一覧の頁に着地した回の名前」「シリーズの名前」「未掲載の手がかり」を書く。

## 手直しの輪

1. **指示**: 4つの一覧を頁・回ごとにまとめて `actions` にする。並びは見込みのクリック増 × 型ごとの成績。直して8週以内のものは出さない。
   `by` が直すタスク。頁の文言・回の頁・主催の頁は週次点検(site-health-check、プレイブック §6 の 3)が週3件まで、
   載っていない催しと、終わった回の次の回の掲載は毎朝の agave-event-update(§3.1)が1日3件まで。
2. **記録**: 直したタスクが `scripts/search-demand.py --log` で `search-actions.json` に1行足して push する。push でこの取り込みが回り直し、直した指示が消える。
3. **測る**: 手直しの語句の、サイト全体でのクリック率を前後28日で比べ、`evaluations` に出す。後は再クロールを待って7日後から数えるので、判定は約3週後から、確定は約5週後。
   検索の量は季節や開催日の近さで動くので、量ではなく率で比べる。差が確かでなければ `flat`。
4. **学ぶ**: `improved` が多い型は priority が上がり、`flat` と `worse` が多い型は下がる(`typeFactors`)。
   頁の文言の手直しが `worse` なら `revert` が付き、週次点検が元に戻す。別名・主催・掲載は事実の訂正なので戻さない。
5. **見張り**: 指示が出続けているのにタスクが手を付けない(週次点検は14日、毎朝のタスクは7日)と `search_actions_idle`、
   `revert` を7日戻さないと `search_action_worse` が日次メールに出る。

## 最初の設定(目崎が一度だけ行う)

1. Google Cloud コンソールでプロジェクトを1つ選び(新しく作ってもよい)、「API とサービス」→「ライブラリ」で **Google Search Console API** を有効にする。
2. 「IAM と管理」→「サービス アカウント」→「サービス アカウントを作成」。名前は agave-navi-gsc など。ロールは付けなくてよい。
3. 作ったアカウントの「鍵」→「鍵を追加」→「新しい鍵を作成」→ JSON。ファイルがダウンロードされる。
4. Search Console の agave-navi.com のプロパティで「設定」→「ユーザーと権限」→「ユーザーを追加」。
   メールアドレスに手順2のアカウントのアドレス(…@….iam.gserviceaccount.com)、権限は「制限付き」。
5. GitHub の mezack0520/agave-navi で「Settings」→「Secrets and variables」→「Actions」→「New repository secret」。
   名前は `GSC_SA_KEY`、値に手順3の JSON の中身を丸ごと貼る。ダウンロードしたファイルはその後消してよい。

設定したら、会話のセッションが `search-request.json` を push して初回を回す(PAT では workflow_dispatch が通らない)。

## 今の設定(2026-11-17)

- プロジェクト: 目崎の個人アカウントの agave-navi。サービスアカウントは agave-navi-gsc(ロール無し)
- Search Console: https://agave-navi.com/ の URL プレフィックスのプロパティに「制限付き」。ドメインのプロパティは無い
- 鍵は1本だけ有効にしておく。作り直したら古い鍵を消し、`GSC_SA_KEY` を貼り替える

## 公開について

リポジトリは public なので、`search-demand.json` には表示10回未満の語句と、メール・電話番号の形の語句を書かない。
数字は語句ごとのクリックと表示の回数と平均順位だけ。
