# タスク運用プレイブック

スケジュールタスク共通の手順書。**タスク自身がこのファイルを更新してよい。**

## なぜこのファイルがあるか

タスクのプロンプト(SKILL.md)は保護された場所にあり、**タスクは自分のプロンプトを編集できない**。
そのため運用知識をプロンプトに書くと、気づいたことがあっても恒久化できず、
毎回同じ失敗を繰り返す。知識はここに書く。プロンプトは「このファイルを読め」とだけ言う。

**改善したら必ずここに追記すること。** それが唯一の恒久化手段。

---

## 1. 起動時の手順

1. `request_cowork_directory` で `C:\Users\yujim\iCloudDrive\Claude\Projects\mzplants` を接続
   （2026-08-18に OneDrive から iCloud Drive へ移行。古いパスは存在しない）
   （既に接続済みなら何もしない）
2. リポジトリを clone
3. このファイル、`docs/architecture-2026-07.md`、`listing-policy.json` を読む
4. プロンプトとここに差異があれば**こちらが正**
5. **終わったら `task-runs.json` の自分の taskId の `history` に実行日(JST)を追記して push する。**
   直近14件で切る。これが repo 側に残る唯一の生存記録で、
   監査の `task_run_gap` が cadence から期待日を作って抜けた回を出す。
   成果物が何も出せずに終わった回でも、**ここだけは書いてから終わる**。
   書けずに終わると、その回は「動かなかった」と区別が付かない。
   `event-listing-review` はここに書かない(`new-inquiries.json` の
   `reviewedHistory` が同じ役目を持っており、二重に持つと必ず食い違う)

置き場（すべて `C:\Users\yujim\iCloudDrive\Claude\Projects\mzplants` 配下）:
- PAT: `agave-navi\github.pat`
- 実行レポート: `mzplants\agave-navi\task-reports\<taskId>_YYYY-MM-DD.md`
- 受け渡しJSON: `mzplants\agave-navi\work\`

## 2. 書き込み手順

- コミットは `git push`（`https://github.com`、名義 `mezack0520 <88774621+mezack0520@users.noreply.github.com>`）
- **PATは `.github/workflows/` も含めてpushできる**（2026-08-10に実証。以前「権限不足」と
  記録していたのは誤り）。Actions API と workflow_dispatch は403で使えない
- サンドボックスから `api.github.com` は不通。`github.com`(git) のみ
- **`repository_dispatch` は使わない**。`events.json` / `new-events.json` /
  `new-inquiries.json` の push でワークフローが発火する
- `GITHUB_TOKEN` によるCI側のpushはワークフローを再起動しない仕様。だからループしない。
  PATでpushしたときだけ `on.push` が発火する
- PATの値は出力・ログ・レポートに残さない。401ならPAT再発行が必要な旨をキューに積んで終了
- **GitHubへの書き込み経路は PAT の `git push` だけ。** ブラウザからは一切書けない。
  Chromeは仕事用の `YujiMezaki` でログインしており `mezack0520` のリポジトリはWeb UIから編集できない。
  以前は Edge が `mezack0520` でログイン済みで `switch_browser` の逃げ道があったが、
  **Edge は2026-08-18に廃止した。代替のブラウザは無い。**
  したがって Run workflow ボタンを押す・Web UIでファイルを直す・Actions を手動再実行する、は**できない**。
  `workflow_dispatch` はPATでも403なので、ワークフローを動かしたいときは
  対象ファイルを push して `on.push` を発火させるしかない。
  読み取り（無認証の `api.github.com` GET・Actionsの実行結果閲覧）はブラウザから通る

## 3. 既知のハマりどころ

- **取りこぼしは `coverage-gaps.json` に毎日出る。ここを見て動く。**
  `scripts/coverage-sweep.py` が LEAFLA の日付別ページを先45日ぶん取得し、
  対象キーワードを含むイベント名を `events.json` と `rejected-events.json` に
  突き合わせて、どちらにも無いものを候補として書き出す（daily.yml で毎日実行）。
  候補は健全性メールに中身が出る。**一次情報で裏取りして、掲載するか
  `rejected-events.json` に落とす。**見送りを記録すれば翌日から候補に出なくなる。
  `coverage_sweep_broken`（urgent）が鳴っているときは、候補が0件でも
  「取りこぼしなし」の証拠にならない。まず巡回を直す
  **同じイベントは会期ぶん畳んで1行にしている。**畳まないと店舗セールや常設展示が
  45日ぶん並ぶ（実測: 素の82件が畳んで13件になった）。
  初回実測（2026-08-27・先45日）: 45日取得・エラー0・候補1052件 → 対象192件 →
  掲載済み63 / 見送り済み47 / 取りこぼし13件。
  この13件には、人手の調査で「確度不足」として落としたもの
  （札幌カクタスクラブ秋の展示会・麋角植物作業室）も含まれていた。
  **人が見落としたものを仕組みが拾えている。**
- **巡回で分かった、情報源ごとの癖（2026-08-27の全国実測）。**
  - アグリゲータ3社（LEAFLA / NextMeet / PUKUBOOK）は**互いに取りこぼす**。
    どれか1つでは足りない。中国地方は PUKUBOOK が最も強く、
    沖縄は LEAFLA だけが拾えていた回がある
  - **会場公式カレンダーにしか出ない大型イベントがある。**
    なばなの里（80店超）、富山県中央植物園のサボテン展、
    京都パルスプラザの日本シャボテン大会は3社とも未掲載だった
  - LEAFLA の日付別ページは **`/blogs/media/event-list-YYYY-MM-DD`** が正しい形。
    先の日付は404になる（2026-08-27時点で10/28以降）。月次 `event-list-2026-10` で補う
  - LEAFLA の**地方別ページ**（`event-kanto-list` など）は3か月を1ページで通覧できて速いが、
    地域タグが `ALL` のまま漏れる回がある（狂仙会が関西面に出ていなかった）
  - LEAFLA の記事の「参考サイト」欄のIG投稿URLは**別イベントを指している例がある**
  - **Instagram投稿は未ログインでも `og:description` から全キャプションが取れる**。
    ログイン壁で本文が読めないときはメタタグを見る

- **裏取りして書いた説明文が、スクレイパに上書きされる。**
  2026-08-27、掲載直後の PLANTS SHOW 桐生で、手で書いた145字が
  note.com のページ全文296字に置き換わった。長さで勝てば通る設計だと、
  一次情報を読んで書いた文が機械的な貼り付けに負ける。
  対策を2つ入れた。
  1. `updatedAt` が14日以内の回は `enrich_events.py` が説明文を上書きしない
  2. ページ全文の目印を追加。`\n` の検査だけでは、改行を空白に潰してから
     渡してくる経路で抜ける。**2連続スペース**と**文末が終止符でない**を弾く
  **新しくイベントを入れたら `updatedAt` を必ず入れる。**これが無いと保護されない

- **Step0のスイープに「日付別インデックス」を必ず入れる。**
  キーワード検索と主催者アカウントのローテーションだけでは、
  **「その日に何があるか」を機械的に列挙できない。**
  2026-08-27に発覚: 「今週末の関東は？」に答えられず外部を洗ったところ、
  掲載2件に対して実際は関東で10件以上開催されていた。9月も同様に10件の未掲載。
  見ていなかったのは日付別の一覧ページ。
  - `https://leaf-laboratory.com/blogs/media/event-list-YYYY-MM-DD`（1日1ページ・全国）
  - `https://nextmeet.app/` の都県別ページと「週末開催」一覧
  **両方見ること。**片方だけでは足りない（2026-08-27の実測で、LEAFLAに
  ISIJビッグバザール・PLANTS SHOWが無く、NextMeetにRAFLUM・PLANT & POTが無かった）。
  どちらも `blockedUrlDomains` なので**出典には使えない**。候補を拾ったら
  必ず主催者の公式Instagram投稿・公式サイト・会場公式サイトで日付と会場を確認する。
  LEAFLAの「参考サイト」欄のIG投稿URLは**別イベントを指している例がある**
  （HAPPY SMILEの出典が無関係な岡山の花店の投稿だった）ので個別に検証する
- **Instagram投稿は未ログインでも `og:description` から全キャプションが取れる。**
  ログイン壁で本文が読めないときは、投稿URLのメタタグを見る。裏取りが速い
- **掲載前に既存と必ず突き合わせる。**
  2026-08-27、外部調査で「ISIJビッグバザール9/27が最大の取りこぼし」と報告されたが、
  `isij-big-bazaar-2026-09-27` として**既に載っていた**。
  調査結果をそのまま信じると二重登録になる。slug と名称の両方で照合する

- **`events.json` を直したら `sync-index-cards.py` を必ず回す。**
  トップのカードは `data-date` / `data-status` / `data-prefecture` などを持っており、
  `status-auto.js` がこれで「開催中 / これから開催 / 終了」を振り分ける。
  **属性が古いと、データが正しくても一覧から消える。**
  詳細ページもJSON-LDもsitemapも再生成されるので、他の検査は全部通る。
  2026-08-27に発覚: 木更津園芸市は 8/11→8/29 に直っていたのに
  カードが `data-date="2026-08-11" data-status="past"` のままで、
  **9日間「終了したイベント」の節に隠れていた**（同種の食い違いが22件）。
  **属性だけでなく本文（日付・タイトル・説明文）も古いまま残る。**
  同日時点で本文の食い違いが26件あり、「第8回 花友フェスタ 2026」のように
  前回開催の名前が出ている回もあった。サムネイルの枠には events.json の日付を
  出しているので、同じカードの中で日付が食い違っていた。
  監査の `index_card_attr_drift` と `index_card_body_drift`（どちらもurgent）が
  検出する。両方0件を確認してから終わる
- **「データが正しい」と「サイトに出ている」は別。**
  この件は audit urgent 0 / info 0 の状態で起きていた。
  イベントを直したら、**トップで実際に見えるかをブラウザで確かめる**。
  `/?` を開いて `document.querySelector('[data-slug="<slug>"]')` の
  `className` と表示サイズを見れば、隠れているかが分かる

- **版数を上げたら `sync-footers.py` だけでは行き渡らない。全生成を回す。**
  版数は各ジェネレータが生成時に埋め込むので、`sync-footers.py` は
  取りこぼし分しか直さない。2026-08-24、CSS版数を上げて sync-footers だけ回し、
  **467ページが旧版のままの状態で push した**（監査の `css_version_drift` で気づいた）。
  版数を上げたら `build-detail-pages` / `build-guides` / `build-static-html` /
  `generate-landing-pages` / `sync-index-cards` / `sync-footers` を通す。
  **push前に `css_version_drift` と `js_version_drift` が0であることを確認する**

- **参考値(metric)はメール本文に出さない。急に動いたときだけ鳴らす（2026-08-24）。**
  「対応不要」と書いたものを毎日並べても、ラベルを付け替えただけで結局読み飛ばされる。
  値は `audit-results.json` / `audit-history.json` に残っており、
  `metric_moved` が直近7回の中央値と比べて**相対30%以上かつ絶対10件以上**動いたときだけ
  urgent で鳴らす。片方だけの条件にすると、小さい値の±1や大きい値の自然増で毎日鳴る。
  **検査を新しく足すときの注意**: 履歴にそのキーが無い回を0とみなすと初日に必ず誤検知する。
  基準はそのキーを持つ履歴が3回以上あるときだけ作る
- **「無い件数」だけを数える指標は、消失と追加を区別できない。**
  `upcoming_no_image` は、画像が13件消えても +13、イベントが13件増えても +13 で同じに見える。
  そこで `upcoming_with_image`（ある件数）を足した。追加では減らないので、
  減ったら必ず消失を意味する。**異常を検知したい向きに動く指標を選ぶこと**

- **`sync-index-cards.py` の `THUMB_RE` は thumb の中身に依存させない。**
  `<img></div>` と空の `</div>` だけを想定した正規表現だったため、
  画像なし枠に `<span>` を入れた瞬間に一致しなくなり、置換されずカードが増殖した
  （2026-08-24: 101→908カード。トップで同じカードが縦に何度も出た）。
  **数え方を間違えないこと。** `grep -c 'class="event-card'` は閉じ引用符が無いため
  `class="event-card-body"` も拾い、常に実数の2倍（202）を返す。
  以前ここに「正常値は202」と書いていたのはこの二重計上で、
  事故時の値として書いていた1816も同じく2倍だった。
  数えるのは `class="event-card"`（閉じ引用符まで）か `data-slug` のユニーク数。
  ただし**手で数える運用はもう要らない。`audit.py` の `index_card_drift` が
  events.json から想定集合を算出して毎ビルド照合する。**
  生成物の見た目は必ず本番かローカルHTMLで目視する

- **`severity` は3段階。`metric` を `info` に混ぜないこと。**
  `urgent`=壊れている / `info`=直せる負債 / `metric`=構造上ゼロにならない観測値。
  混ぜていたため健全性メールの「積み残し」が常に8項目埋まり、一覧ごと読み飛ばされていた。
  `metric` に移したもの: `upcoming_no_image`（新規は必ず画像なしで入る）、
  `thin_archived` と `thin_past_with_source`（終了30日超はnoindexで誰も読まない）、
  `ongoing_events`（開催期間中は必ず出る）、`workflow_secrets`（使用中secretの棚卸し）。
  **移すときは「ゼロにできないのはなぜか」を note に書く。**書けないなら info のまま
- **リンク切れの statusCode `-1` は「リンク切れ」ではない。**
  DNS・タイムアウト・TLSで判定できなかった状態で、相手が生きている可能性が高い。
  件数は**URL単位で数える**。7イベントが同じ出典を共有していたため、実体1件が
  「リンク切れ7件」に増幅されていた（2026-08-24 isij.net。現役サイトだった）

- **`short_descriptions` の閾値は50字。70字から下げた（2026-08-24）。**
  `thin_fixable` が50字なのに `short_descriptions` が70字で、同じ性質に基準が2つあった。
  `audit.py` / `check_events.py` / `listing-policy.json` の3か所すべて50字。片方だけ直さない。
  **数字を減らすために日時・会場・入場料を説明文へ書き足さないこと。**
  それらはスペック表に既に出ており、繰り返しは水増し。300頁分の定型文は薄いページと見なされる。
  50字未満の回だけ、主催者の一次情報から**出店数・扱う植物のジャンル・企画**という
  スペック表に無い事実を足す。材料が無ければ短いままにしておくのが正しい

- **掲載申請フォームはもうポーリングしない。GAS連携が2026-08-24に稼働した。**
  フォーム送信の瞬間に GAS が `new-inquiries.json` へ追記し、`notify-inquiry.yml` が
  発火してメールが飛ぶ。**回答シートを毎日開く必要はない。**
  タスクがやることは `new-inquiries.json` の `items` を処理して、
  済んだものを `inquiries-processed.json` に移し、`items` を空にして push するだけ。
  Chromeを開く手順は残っているが**平常時は使わない**。
  スクリプト実体は `scripts/google-apps-script.js`、Apps Scriptプロジェクトは
  「agave-navi フォーム→GitHub連携」（回答スプレッドシートに紐づく）
- **`reviewedOn` を毎回書く。これがタスクの生存確認になっている。**
  `new-inquiries.json` の `reviewedOn` を実行日に更新して push する。
  監査の `inquiry_check_stale` はこれを見ており、4日以上古いと urgent で鳴る。
  `lastChecked` はGASが書くフィールドなので触らない（送信が無ければ古いまま。それは正常）。
  処理し終えた `items` は必ず空にする。残り続けると「未処理の問い合わせ」として鳴る
- **フォームが読めなかったときは黙って終わらない。**
  2026-08-21〜24、タスクは毎日起動していたのに Chrome の操作許可待ちで落ち、
  レポートもコミットも残らず、`lastChecked` が4日据え置かれるまで誰も気づかなかった。
  読めなかった回は必ず (1) レポートに「読めなかった」と書く
  (2) `pending-judgments.json` に積む — この2つだけは何があってもやる。
  **無音で終わるのが最悪。** 止まっていること自体が伝わらない
- **GAS連携は稼働中（2026-08-24 設置・疎通確認済み）。**
  トリガー: スプレッドシートから / フォーム送信時 → `onFormSubmit`。
  `testConnection` の実行ログで `OK items=0 lastChecked=2026-08-24` を確認した。
  **止まっていないかの確認方法**: `new-inquiries.json` の `lastChecked` は
  GASが書くので、フォーム送信が無ければ更新されない。
  つまり `lastChecked` の古さは異常の証拠にならなくなった。
  疑うときは Apps Script の「実行数」を見る。エラーが出ていれば
  `ALERT_TO`（yuji.mezaki@gmail.com）にGASからメールが飛ぶ設計。
  トリガーが消えていたら `script.google.com` の当該プロジェクト →
  トリガー画面で `onFormSubmit` の有無を見る。
  **2026-08-25 に `script.google.com/home/triggers` で現物を確認した。**
  「agave-navi フォーム→GitHub連携 / スプレッドシートから - フォーム送信時 / onFormSubmit」1件、
  エラー率は空。08-24 の当タスクが「トリガー0件」と報告したのは 10:22 時点の事実で、
  設置は同日 11:16 のコミット `0337285` で完了している。
  `pending-judgments.json` の `event-listing-review:gas-not-installed` は解消済み。
  **次回以降、設置の要否を再検討しないこと。**
- **GASのトリガーは「登録されている」だけで、実フォーム送信で発火した実績がまだ無い。**
  08-25 時点で「前回の実行」は `-`。最後の回答が 2026-07-02 なので当然だが、
  疎通確認は `testConnection`（手動実行）で取ったものであり、
  **フォーム送信 → GAS → push → メールの端から端までは一度も通っていない。**
  テスト送信して確かめたくなるが、やらない。回答シートに偽の行が残り、
  `processed` との検算がその分ずれ続ける。
  代わりに**下のシート突き合わせを毎回やる**。送信があったのにGASが動かなければ、
  シートの行数が `processed` を上回るので翌日には必ず表に出る。
  端から端までを事前に証明する代わりに、壊れたら1日で気づく側に倒す
- **`script.google.com/home/triggers` は仕事用アカウントを開く。個人用は `/u/1/`（2026-08-30）。**
  Chromeには2つのGoogleアカウントがログインしており、既定(`/u/0`)は仕事用の
  `mezaki@sterfield.co.jp` になっている。`/home/triggers` を素で開くと
  Gantt chart の無関係なトリガーが「多数のうち25個」だけ並び、
  **agave-navi のトリガーは1件も出ない**。ページ送りしても届かないので、
  そのまま読むと「トリガーが消えた」と誤判定して、
  既にあるトリガーを再設置しに行くことになる。
  見るのは `https://script.google.com/u/1/home/triggers`。
  プロジェクト一覧も同じで `/u/1/home/all`。
  `docs.google.com` 側の gviz CSV は既定アカウントのままでも200で返るので、
  **シートが読めたことはアカウントが合っている証拠にならない。**
  2026-08-25 と 08-27 のレポートが `/home/triggers` で確認できたと書いているが、
  今日は同じURLで出ない。アカウントの並び順は増減で変わるので、
  URLを固定で信用せず、**ページに `agave-navi フォーム→GitHub連携` の行が
  出ていることまで確かめる**。出なければ `/u/1/` `/u/2/` と当たる。
  （2026-08-30 実測: `/u/1/` に当該プロジェクト。トリガー1件、
  イベント=スプレッドシートから-フォーム送信時、関数=`onFormSubmit`、エラー率は空）
- **取りこぼしの回収は `backfillFromSheet`。**
  トリガーが止まっていた期間があっても、Apps Scriptエディタでこの関数を1回実行すれば
  シート全行から未処理のタイムスタンプだけを拾って `new-inquiries.json` に送る。
  重複は `timestamp` で弾く
- **gviz CSV でのシート突き合わせは毎回やる。非常用ではなく定常の検算（2026-08-25 変更）。**
  以前ここに「GASが壊れたときだけ使う」と書いていたが、それでは**壊れたことに気づく経路が無い**。
  `lastChecked` は送信が無ければ更新されないので古さが異常の証拠にならず、
  `audit.py` は CI から Google にアクセスできないので機械検出もできない。
  つまりGASの死活を見られるのはブラウザを持つこのタスクだけで、
  見る手段はシートの実データと `inquiries-processed.json` の `processed` の照合しかない。
  **毎回の手順は2つ。** (1) `/home/triggers` に `onFormSubmit` があるか（送信ゼロでも取れる生存証明）
  (2) 下のCSVでデータ行数を数え、`processed` 件数と比べる。
  行数 > processed なら**GASが取りこぼしている**ので `backfillFromSheet` を回す判断に入る。
  行数 < processed なら読み取り失敗。等しければ新着ゼロ。
  スプレッドシートを開いて同一オリジンで
  `fetch('/spreadsheets/d/1iTWAAbd5FV4NkNyt186H8wR6KqTPOLcFWSvHghZMDvI/gviz/tq?tqx=out:csv',{credentials:'include'})`
  を叩けば1回で全行取れる。グリッドのUIを読む手順には戻さないこと（許可待ちで止まる）。
  Chromeのログインは個人アカウント `yuji.mezaki@gmail.com`（Driveコネクタは仕事用なので見えない）。
  この日の実測: データ行2 / `inquiries-processed.json` の processed 2 → 検算通過・新着ゼロ。
  フォームの機能確認も実施済み（`viewform` は回答受付中、フォームIDの参照は `contact.html` 1件のみ）。
  直近回答が 2026-07-02 で約8週間空いているが、これはフォーム側の故障ではない

- **回答シートは組み込みブラウザからは読めない（2026-08-31 確定）。**
  組み込みブラウザはGoogleにログインしておらず、gviz CSV を叩くと
  `accounts.google.com` に飛ばされる。Cookieのインポート機能はあるが
  **Windowsでは Firefox からしか取り込めない**（macOSは Chrome/Edge/Firefox）ので、
  Windows＋Chrome のこの環境では使えない。
  目崎の判断で**ブラウザは組み込みのまま**にした（2026-08-31）。
  つまり**このタスクからシートを読む手段は無い**。
  Claude in Chrome なら実Chromeなので読めるが、既定を変えない方針。

- **だから `sheetRows` は GAS 側が書く（2026-08-31 変更）。**
  `onFormSubmit` が `countSheetRows()` の結果を `sheetRows` / `sheetCheckedOn` に書く。
  ブラウザで数えて手で入れる手順は廃止。読めないのに数えようとすると、
  測れないまま処理を進めて `sheetCheckedOn < reviewedOn` の urgent が立つだけになる。
  **この方式の穴**: GASが止まると `sheetRows` も止まる。GASの死活は
  `lastChecked` の古さと `inquiry_check_stale` で見る（シート行数では見られない）。

- **`inquiries-processed.json` の件数は `processed` を見る。`items` ではない（2026-08-31）。**
  このファイルは `processed`（重複判定用のタイムスタンプ配列）と
  `outcomes`（各回答をどう処理したかの記録）で出来ている。
  2026-08-31 に `items` というキーを勝手に足し、そちらだけを見て
  「2件が未処理のまま埋もれていた」と誤って判断した。実際は2件とも
  2026-08-30 までに `processed` / `outcomes` へ入っており、
  対象イベントも events.json に掲載済みだった。取りこぼしは無かった。
  監査 `inquiry_sheet_row_mismatch` が読むのも `processed` なので、
  **書く側と読む側で同じキーを使う。** 新しいキーを足す前に、
  そのファイルを読んでいるコードを先に探す。

- **数えた行数は `new-inquiries.json` に書く。散文のレポートは誰も読み返さない（2026-08-30）。**
  gviz CSV の検算は 2026-08-25 から毎回やっているが、結果は task-reports の
  散文にしか残っていなかった。**読むコードが1本も無いので、読み違えても
  「検算通過」と書けてしまう。** プレイブックの「必ず数える」は検査にする合図だ、
  と §5 で自分に言っているのに、この手順だけ例外になっていた。
  そこで実測値を `sheetRows`、読めた日を `sheetCheckedOn` として毎回書く。
  監査の `inquiry_sheet_row_mismatch`(urgent) が
  `sheetRows == processed + items` を照合する。
  多ければGASの取りこぼし、少なければ読み取り失敗、
  `sheetCheckedOn < reviewedOn` なら「動いたがシートを見ていない」回。
  CIからGoogleは見られないので、**シートの実態をCI側に持ち込める材料はこの2つだけ。**
  読めなかった回は `sheetCheckedOn` を進めない。進めると読めた回と区別が付かなくなる

- **品質の下限を緩めるときは、blocklistを同時に広げる。**
  説明文の下限を120字→50字に下げたら、会場名+イベント名+定型文だけの
  アグリゲータ見出しが通り、43字の実のある説明文を69字の定型文で上書きした
  （2026-08-20 greensnap横浜）。**字数が増えたことは改善の証明にならない。**
  エンリッチ実行後は件数ではなく、書き換わった本文そのものを読む
- **画像がイベント固有かの判定は `sitelib.is_generic_image_url()` だけを使う。**
  backfill-images.py 側にも `_GENERIC_IMG_RE` があるが、こちらはファイル名しか見ない。
  規則を足すときは sitelib に足す。両方に書くと必ず食い違う。
  接頭辞付きの `xxx-ogp.png` と、themes/ 配下にない素の `facebook.png` が
  素通りしていたので sitelib 側に追加した（2026-08-20）。
  `main` `thumb` を語頭一致で弾こうとすると `event-main-visual.jpg` を巻き込むので、
  この2語は完全一致に留める

- **Weekly Enrichment は `enrich-request.json` を push すると発火する**（2026-08-18に追加）。
  `repository_dispatch` も `workflow_dispatch` も送れないので、これが週次cron以外の唯一の起動手段。
  件数や対象slugもこのファイルで指定する（cron実行もこのファイルを読む）。
  積み残し（`short_descriptions` / `thin_fixable` / `upcoming_no_image`）を崩したいときはここを叩く。
  **「dispatchを送った」で終わったつもりにならないこと。送れていない。**
  発火したかは `api.github.com/.../actions/workflows/weekly-enrichment.yml/runs` を
  ブラウザで開いて `event` を見る。`schedule` しか並んでいなければ手動起動は一度も通っていない

- **会場が「未定」かどうかの判定は `sitelib.is_vague_venue()` を使う。**
  `VAGUE_VENUES` への完全一致だけだと「金沢（会場未確定）」のように
  括弧書きで未定を補った値を取りこぼす。取りこぼすと地図・FAQ・JSON-LDのPlaceに
  会場名として出てしまう（2026-08-18に検出・統一）
- **JSON-LDに空文字の値を出さない。** 会場不明の回で `"name": ""` を出していた（31頁）。
  空文字は「値が無い」ではなく「空という値がある」と読まれる。キーごと省く。
  `audit.py` の `jsonld_blank_value` が検出する
- **FAQの会場文は `location` に住所が入っていると括弧が二重になる。**
  「◯◯（静岡県富士市…）(静岡)です」。`location` に県名が既にあるときは `(県)` を足さない（38頁で発生）

- **既存イベントの修正は `events.json` を直接編集する。**
  `sanity-check-new-events.py` は既存slugを "slug already exists" で落とすため
  `new-events.json` 経由では通らない
- **nohup のバックグラウンド実行は呼び出し終了時に殺される。前景で叩く。**
  `build-all.sh` は前景で完走する。2026-08-11 の実測で全289件の詳細ページ+ガイド+
  ランディング+フィード+sitemap が **1.2秒**。分割して叩く必要はない
  (以前「45秒制限に収まらない」と書いていたのは誤り。遅いのは
  `check_date_updates.py` と `check-links.sh` のようなネットワークを叩く側だけ)
- **push が non-fast-forward で拒否されたら、生成物のrebaseは必ず衝突する。**
  `origin/main` に `reset --hard` → データ変更を再適用 → 再ビルド → push の順でやり直す
- **CSS/JSを変えたら `scripts/sitelib.py` の `CSS_VERSION` / `JS_VERSION` を上げる。**
  上げないと閲覧者のキャッシュが更新されず変更が届かない
- **Googleフォームの回答は htmlview の iframe 内にある。**
  `docs.google.com/spreadsheets/d/<id>/htmlview` を開き
  `document.querySelector('iframe').contentDocument` から table を読む。
  `get_page_text` ではシートタブ名しか取れない。
  `javascript_tool` の戻り値に URL を含めると応答がブロックされるので、返すのは値だけにする
- **読み取り行数が処理済み件数を下回ったら「新着なし」と結論しない。**
  htmlview の読み取りは失敗しても例外にならず0行や見出しだけで返る。
  `inquiries-processed.json` の件数を下回る行しか取れていないなら読み取り失敗として扱い、
  再試行する。黙って「新着なし」と報告すると申請を取りこぼす
- **この検算で数えるのは `tr` の数ではなく「タイムスタンプが入った行」の数。**
  回答シートの table は 1行目=列記号(A B C…)、2行目=見出し、3行目=空行 で、
  データ2件でも `tr` は5個ある。`tr` の数で検算すると、データを1行も読めていなくても
  5 ≥ 2 で通ってしまい、検算が意味を失う。A列の連番か1列目の日時でデータ行を判定する
  (2026-08-12 の実測: `tr`=5 / データ行=2)
- **`/tmp` に clone すると Read/Write/Edit ツールが届かない。**
  ファイルツールと bash は別のファイルシステムを見ているため、
  マウント外に clone した場合はリポジトリの編集も `bash` + `python3` のヒアドキュメントでやる。
  置換は `assert s.count(old)==1` を挟んでから書き戻すと、当てが外れたまま進むのを防げる
- **clone 先を outputs マウント配下に置くと失敗する。**
  `.git/config.lock` を unlink できず `fatal: could not set 'remote.origin.fetch'` で止まる。
  `/tmp/<name>` か `$HOME/<name>` に取る。マウント外に clone した場合
  `git config --global --add safe.directory <path>` が要ることがある。
  JSONの照合だけなら `--depth 1 --filter=blob:none --no-checkout` + `git show HEAD:<file>` で足りる
- **Googleの検索結果に出るIG画像のOCRは、曜日表記をイベント名に食い込ませる。**
  「2026.10.18. SUN GREEN BASE MARKET 出店者さま募集中」は `10月18日(日)` の `SUN` が
  名称の先頭に入ったもので、実際の名称は `GREEN BASE MARKET`。
  掲載済みの `green-base-market-vol1-nishikata-2026-10` と別イベントに見えて二重登録しかける
  (2026-08-18)。名称の先頭が SUN/MON/TUE/…/SAT で始まる候補は、
  **その語が date の曜日と一致しないかを先に疑う**。一致するなら OCR 由来
- **主催者のIGプロフィール文と投稿本文は、Googleの検索結果スニペットに出る。**
  Instagram を直接開けなくても、`"<イベント名>" "<会場名>"` や `<主催ハンドル> "<キーワード>"` の
  クォート検索で主催アカウントのスニペットが取れれば、それは一次情報として使える。
  2026-08-18 に北陸サボテンクラブの富山回・新潟回の日時と会場をこれで確定した
  (公式サイト hokusabo.jimdofree.com には2025年回までしか載っておらず、
  2026年回はIG側にしかなかった)。**公式サイトが古いことを理由に unverified にしない**
- **Step0 の通常クエリでは「掲載済みイベントの延期」を拾えない。**
  新規イベント向けの語(開催決定・出店者募集)は、既に載っている回の日付変更に当たらない。
  毎回1回だけ `多肉植物 OR アガベ イベント "中止" OR "延期" <対象月>` を回す。
  2026-08-18 にこれで木更津園芸市の 8/11→8/29 延期(台風接近)を検出した。
  延期に気づかないと `status=past` のまま残り、開催予定として二度と表に出ない。
  **repo内の検査では検出できない経路なので、探索側で塞ぐしかない**
- **既存イベントを直したら `updatedAt` を今日の日付にする。**
  詳細ページの「最終更新」は `updatedAt > enrichedAt > addedDate` の順で見る。
  `addedDate` は追加日なので、日付や会場を直しても動かない。
  2026-08-18に木更津園芸市の延期を反映したとき、ページの最終更新が7/29のままだった。
  about.html は「各イベントページに参照元と最終更新日を明記」と掲げているので、
  直した日が出ないのは掲載方針との食い違いになる
- **Instagram告知は WebSearch(US版)ではほぼ拾えない。**
  Chromeで `google.com/search?hl=ja&tbs=qdr:w2` を叩くのが主経路
- **Step0の検索だけでは開催予定を取りこぼす。`pukubook.jp/events/` の一覧を必ず1回読む。**
  2026-08-12 に検索経由で6件を拾った後、この一覧から未掲載の開催予定が8件出た(うち6件が掲載相当)。
  `blockedUrlDomains` は url/sourceUrl への使用禁止であって参照の禁止ではない。
  ただし**アグリゲータは中止・休会を反映しない**。ISIJ東京例会 8/23 は pukubook が
  「近日開催」のままだったが isij.net には「休会」と明記されていた。拾った候補は
  必ず主催者の一次情報で日付・会場・時間・入場料を裏取りする
- **Googleの検索結果は、無関係な投稿のキャプションを同じ結果ブロックに混ぜて表示する。**
  1つのスニペットに2つのイベントの日付が並ぶことがあり、そのまま読むと日付を取り違える。
  イベント名でクォート検索し直して、同じ日付が主催者側の複数の告知に出ることを確かめる
- 都道府県→地域は `scripts/sitelib.py` の `PREF_TO_REGION` が単一情報源。
  沖縄は九州、山梨・長野は北陸
- **`venue` は `location` より優先して表示・JSON-LD・地図に入る。**
  `build-detail-pages.py` の 350/473/524/811 行は `venue or location` なので、
  `venue` に会場名以外(都道府県名・日付・館内スポットだけ)が入っていると
  スペック表・JSON-LD の `Place.name`・埋め込み地図の3つが同時に壊れる。
  会場名が `location` にあるなら **`venue` と `mapQuery` を消して
  `location + prefecture` のフォールバックに任せる**のが正しい直し方
  (2026-08-12に17件を処理。`venue=mapQuery="愛知県"` のように県名だけの回が9件、
  日付をそのまま貼った回が1件あった)
- **「会場名として意味をなさない値」は `sitelib.VAGUE_VENUES` が単一情報源。**
  2026-08-12に全都道府県名(短縮形・接尾辞付きの両方)を追加した。
  以前は東京・大阪・名古屋だけの列挙で、`venue="岩手"` のような回が
  会場名として扱われ地図が県全体を指していた。
  ただし `VAGUE_VENUES` を見ているのは地図・FAQ・会場ランディングだけで、
  JSON-LD の `Place.name` とスペック表は素通しのまま(キューに記録済み)
- **「新着なし」が続くときは、フォーム側が生きていることを機能確認する。**
  回答シートが増えないのは「申請が来ていない」だけでなく、「フォームが回答受付を止めた」
  「`contact.html` からリンクが消えた」「フォームの出力先シートが差し替わった」でも起きる。
  どれも例外は出ず、シートは正常に0行増で返るので黙って取りこぼす。
  読み取り件数の検算はシートの中身しか見ていないため、この経路は塞げない。確認は2つで足りる:
  (1) `viewform` を開いて「回答を受け付けていません」が出ないこと
  (2) `grep -rlo "<フォームID>" --include=*.html .` が `contact.html` を返すこと
  (2026-08-13 実施。直近回答が 2026-07-02 で6週間空いていたため確認した。両方とも正常。
  サイト内でこのフォームIDを参照しているのは `contact.html` の1ファイルだけ)
- **本番を見る前に `localStorage.removeItem('aen_region')` を実行してリロードする。**
  Chromeのプロファイルは前回の実行の localStorage を引きずるので、
  地域を絞った状態の画面を「本番の見え方」として読んでしまう。
  2026-08-31 も残っており、トップの件数バッジが 42件(実際の開催予定は123件)だった。
  「疑ったら読む」と書いていたが、2回とも**まず壊れて見える**ので、
  疑うより先に消すほうが早い。
  2026-08-18 は 30件(実データは開催予定77件)で47件が非表示になっており、
  掲載漏れの重大バグに見えた。`index.html` の `initRegion()` が
  地域選択を localStorage から復元する仕様で、サイトは正しく動いていた。
  照合するのは**件数バッジと `sitelib.is_upcoming` の件数**。
  `.event-card` の総数・表示数とは一致しないのが正常で、
  `load-more-hidden` が付いた回は「もっと見る」まで隠れている
  (2026-08-31 実測: カード147枚・表示17枚・バッジ123件・is_upcoming 123件)
- **`.aff-bar`(スマホ固定バー)はデスクトップ幅ではDOMに存在しないのが正常。**
  `affiliate.js` が `matchMedia('(max-width: 720px)')` で生成自体を止めている。
  かつ `resize_window` は効かない(420px を指定しても `innerWidth` は 1478 のまま)。
  機能確認は **matchMedia を差し替えてから `affiliate.js` を再注入**し、
  45%までスクロールして `.aff-bar.is-shown` と実商品リンク(`hb.afl.rakuten.co.jp`)が
  出ることを見る。`display:none` は min-width:721px のCSSによるもので異常ではない
- **weekly-enrichment のスケジュール実行は毎回20件しか処理しない。**
  `LIMIT="${{ github.event.inputs.limit || '20' }}"` は cron 実行だと inputs が空なので常に20。
  `enrich_events.py` の `_priority` が短文の開催予定を先頭に並べるため、
  この20枠はほぼ `short_descriptions` の18件に使われる
- **`url` は「在るか」しか見られていない。中身が別イベントでも noindex を外す。**
  `_is_thin_event` の `has_src` は `url` / `sourceUrl` の文字列長しか見ない。
  そのため出典が**その回を裏付けていなくても**薄頁判定を外れ、index対象になる。
  2026-08-18に `fujiyama-days-little-green-park-2026` の `url` が
  2024年開催の別回(LIFE STYLE FESTA / 6月1-2日)についての協賛企業の告知だった。
  出典を疑うときは URL を開いて、**日付・イベント名・会場がその回と一致するか**を見る。
  一致しないなら出典ごと外す(残すと裏取り済みに見える)
- **「値が無い」は `null` と空文字が混在していた。2026-08-18にキーごと削除で統一。**
  `image-health-check.py` は死んだ `imageUrl` を `None` にし、別経路は空文字を書いていた。
  読む側は全部 `(x or '')` で吸収しているので実害は無かったが、
  `is None` や `k in e` で書いた検査を1つ足すと片方だけ拾って静かに漏れる。
  **値が無いならキーごと消す。** `blank_optional_fields` が0以外になったら
  どこかが空を書き戻している
- **`imageUrl` は https でないと画像が3箇所同時に落ちる。**
  サイトはHTTPSなので `http://` の画像は混在コンテンツで止まり、
  `<img>` の `onerror` でヒーロー画像ごと消える。同じ値が og:image / twitter:image /
  JSON-LD の image にも入るのでSNSカードとリッチリザルトの画像も落ちる
  (2026-08-18に `code-tokyo-popup-2026-08` で4箇所への露出を確認)。
  `url` / `sourceUrl` は外部リンクなので http のままでよい(isij.net は18件ある)
- **`eventStatus` の未知の値は黙って `EventScheduled` になる。**
  `build-detail-pages.py` の `status_map` に無い値は
  `status_map.get(x, 'EventScheduled')` で素通りする。
  `canceled`(lが1つ)のような綴り違いを書くと、中止の回を「開催予定」として
  リッチリザルトに出す。`tbd` はサイト独自の既知値
- **`/pref/hokkaido/` と `/region/hokkaido/` は構造的に必ず同一内容になる。**
  `PREF_TO_REGION` 上、北海道は1県=1地方。掲載イベントもtitleも完全に一致し、
  2026-08-18まで両方index対象で競合していた。
  `render()` に `canonical_of` を足し、掲載が1県に閉じている地域は
  正規URLを県頁に寄せるようにした。noindexにはしない(利用者には見えるしADも出す)。
  自分を指さないcanonicalとsitemap掲載は矛盾するので、
  `landing-meta.json` に `canonicalized` を出して `generate_sitemap.py` 側で除外する
- **`/this-month/` の title は「今月の」で固定する。**
  `{年}年{月}月のアガベ・植物イベント` にすると `/archive/{ym}/` と毎月必ず同titleになる。
  常設URLと月の恒久URLは役割が違うので、titleを役割で書き分ける
- **「今」の定義がリポジトリ内で4通りに割れていた。会期物は開始日基準の枠から落ちる。**
  `status`(`auto-status-jst.py`) と `this-weekend` は `dateEnd` を見るが、
  `/this-month/` と `this-month.ics` は `date.startswith(今月)`、`upcoming.ics` は
  `date >= today` で、どちらも開始日基準だった。先月に始まって今月まで続く展示
  (会期39〜49日の回が実在する)は、**今まさに開催中でも今月の一覧と配布フィードから消える**。
  2026-08-18に `/this-month/` 48→51件、`upcoming.ics` 83→85件で解消。
  期間を持つデータを月や週で切るときは、必ず
  `date[:7] <= 対象月 <= (dateEnd or date)[:7]` の重なりで採る。
  `upcoming.ics` は `(dateEnd or date) >= today`。
  `/archive/{ym}/` だけは開始月で固定してよい(その月の恒久URLで役割が違う)
- **`imageUrl` は enrich が og:image を素通しで採るので、告知ページに固有画像が無いサイトでは
  サイトロゴ・OGP既定画像が入る。** 2026-08-18に13件を検出(55件中)。
  露出は5箇所: カード / og:image / twitter:image / JSON-LD の image /
  **`sitemap.xml` の `image:image`**。sitemap にはイベント名が `image:title` として付くので、
  Facebookアイコンが「富士多肉 多肉植物・サボテンの販売」の画像としてGoogleに登録されていた。
  WordPress のアップロード先は `wp-content/uploads` なので **`themes/` 配下・
  `common/images/` 配下・`logo_ogp` や `ogImg` や `opengraph-image` を含むURLは
  イベント固有画像になり得ない**。差し替えではなく `imageUrl` をキーごと削除するのが正しい。
  検査は `generic_image_asset`
- **`is_thin` は `imageUrl` があるだけで substance 有りとみなす。**
  つまりサイトロゴが入っているだけで薄頁判定を外れる。
  上の13件を消したとき `thin_fixable` が37→38に増えた(`haze-various-genres-marche-2026`)。
  **これは悪化ではなく、ロゴが隠していた薄さが表に出ただけ**。
  同様に `upcoming_no_image` は68→71になる。
  画像を消す変更をしたら、この2項目の増加は想定内としてレポートに書く
- **検出側だけに規則を書くと、書き込み側が翌日それを戻す。**
  2026-08-18に「WordPress のアップロード先は wp-content/uploads だから `themes/` 配下・
  `common/images/` 配下はイベント固有画像になり得ない」と気づいて13件消したが、
  規則を書いた先は `audit.py` の `generic_image_asset` だけだった。
  `enrich_events.py` / `backfill-images.py` の `is_quality_image_url()` は
  **ファイル名しか見ない** `_GENERIC_IMG_RE`（`/logo.png` 等）のままだったので、
  2026-08-20の weekly-enrichment が同じ2件を書き戻した。
  判定を `sitelib.is_generic_image_url()` に集約し、検出側と書き込み側の3本が
  同じ関数を見るようにして解消。**「消して回る」で終わった修正は、
  同じ値を書く側のコードを読むまで終わっていない。**
- **同じ回の二重登録は、`sanity-check-new-events.py` を通らない経路では誰も見ていなかった。**
  あの重複検出は `new-events.json` の流入だけを見るので、
  検査ができる前に入った重複と、`events.json` を直接編集して入れた重複が素通りする。
  2026-08-20に2組を発見（`plants-fes-vol3` / `plants-fes-vol3-ehime-2026`、
  `botariba-2026-06` / `botariba-toyohashi-2026-06`）。どちらも同日・同県・同会場で、
  詳細ページ・sitemap・県頁・icsに同じ回が2回出ていた。
  `audit.py` の `duplicate_event_entry` で常時検査する。
  **名前の包含判定の最小長は4字にする。**「ボタり場」が4字で、5字にすると取りこぼす
- **消す側のフィールドを引き継ぐ前に、その値が正しいかを見る。**
  `botariba-2026-06` の `imageUrl` は熱海のジャカランダ写真（`ataminews.gr.jp`）で、
  豊橋の植物イベントとは無関係だった。重複の統合は「情報量の多いほうに寄せる」だが、
  多い側が間違っている場合がある

- **`reviewedOn` だけでは「抜けた日」を事後に検出できない。`reviewedHistory` を見る（2026-08-26 の抜けで判明）。**
  `inquiry_check_stale` は「今どれだけ古いか」しか見ないので、1日抜けても
  **翌日の回が `reviewedOn` を上書きした瞬間に痕跡が消える**。
  2026-08-26 はこのタスクの成果物が何も無い(コミットもレポートも無い)のに、
  同日 weekly-discovery と health は正常に走っており環境側は生きていた。
  08-27 の回で `reviewedOn` を書けば、この抜けは検出不能になっていた。
  そこで `new-inquiries.json` に `reviewedHistory`(実行日、直近14件)を持たせ、
  `audit.py` の `inquiry_review_gap` が直近7日の抜けた日を列挙する。
  **毎回 `reviewedOn` と `reviewedHistory` の両方を書く。** 履歴は14件で切る。
  `inquiry_check_stale` の閾値を1日に下げる案は採らない。実行時刻とCIの時差だけで
  誤検知するのが4日にしてある理由で、そこは変わっていない。日付の集合で見れば時差は効かない。
  2026-08-27 の初回実行で 08-21 / 08-22 / 08-23 / 08-26 の4日を検出した
  (前3日はプレイブックに既記の Chrome 許可待ちの回と一致する)

- **新着ゼロの日でも `new-inquiries.json` の `lastChecked` は必ず当日にして push する。**
  これが「event-listing-review が動いた」ことのリポジトリ側の唯一の痕跡。
  タスクが起動しなかった日も、起動したがフォームを読む前に落ちた日も、
  repo には何も残らないので次に動いた日まで誰も気づけない。
  実際 `task-reports/` の event-listing-review は 08-14〜08-17 と 08-19 が欠落しており、
  スケジュールは enabled・`lastRunAt` は当日で正常に見えるのに、成果物が無い日があった
  (`lastRunAt` は最新1回しか持たないので、過去の抜けは事後に判定できない)。
  2026-08-20 に `audit.py` の `inquiry_check_stale` を足して、
  `lastChecked` が4日以上前になったら日次メールに出るようにした。
  **「新着なし」で終わるときほど、書き戻しまでやってから終わること。**

- **`return ''` で消える生成物は、消えたことが誰にも伝わらない（2026-08-27）。**
  `build-detail-pages.make_instagram_section` は投稿IDが取れないと節ごと空を返す。
  IDの抽出は `/p/<id>/` しか見ていなかったため、**リールのURL(`/reel/<id>/`)だけを
  持つ回は Instagram 埋め込みが頁から丸ごと消えていた**
  (`plants-garage-market-2026-spring`)。IGは主催者の一次情報の主戦場で、
  埋め込みが消えるとその回の告知への導線が詳細頁から無くなる。
  例外も警告も出ないので、頁を開くまで気づけない。
  抽出は `/(?:p|reel|reels|tv)/` に広げた。検査は `instagram_embed_missing` で、
  **「値が在るか」ではなく「頁に埋め込みが出ているか」を見る**(機能確認)。
  埋め込みの投稿IDが events.json の値と違う場合も拾う(値だけ直して再生成しない事故)。
  **`return ''` / `continue` で静かに抜ける分岐を書いたら、その結果を数える検査を同時に足す。**

- **挿入で作る頁は index.html だけではない。calendar / map も数える（2026-08-27）。**
  `build-static-html.py` は既存HTMLへの挿入で作るため、置換が効かないと
  消さずに足すだけになる。過去に calendar/map が4.2MBまで肥大した事故があり、
  プレイブックには「冪等に書くこと」という注意書きだけがあって数える側が無かった。
  `index_card_drift` を index.html に付けたときに、同じ作り方のこの2頁を漏らしていた。
  検査は `embedded_event_set_drift`。1頁に3つの表現(インラインJSON /
  SSRの一覧 / ItemListのJSON-LD)があるので、**そのすべてが同じ集合を指しているか**を見る。
  1つだけ古いと、見る経路によって件数が違う頁になる。
  期待集合は `sitelib.is_upcoming` で算出する(生成側と同じ規則。写しを持たない)。
  冪等性は2回続けて実行してバイト一致を見れば確かめられる(2026-08-27 実測: 一致)。

- **`rejected-events.json` の `reasonType` を読むコードが1本も無かった（2026-08-27）。**
  このファイルは自分の中に `_reasonTypes`(policy / unverified / undisclosed / cancelled)
  という語彙表を持っているのに、repo 全体で `reasonType` を参照する行が無い。
  `blockedUrlDomains` と同じ型の穴で、綴り違いや未定義の値を書いても誰も止めず、
  「policy と unverified の件数」のような集計が黙ってずれる。
  検査は `rejected_reason_vocab`(語彙外・欠落・`reason` が空・`decided` の書式と未来日)。
  **語彙表をデータに書いたら、その語彙を突き合わせる検査を同じコミットで足す。**

- **「一次情報が出たら再評価する」保留には期限を持たせる（2026-08-27）。**
  `revisit=true` は植物軸を認めた上で出典が足りないだけの回で、掲載相当になる可能性が高い。
  ところが再評価を促す側が repo に無く、9件が最古 2026-07-30 のまま動いていなかった。
  うち `gujo-de-cactus-night-market-2026-08` は**開催日(8/16)を11日過ぎており、
  再評価の機会そのものが消えていた**。開催が終わればもう掲載できないので、
  この保留は永久に開いたままになる。
  そこで各項目に `eventDate`(名称に開催日が書かれている回だけ)を明示し、
  `rejected_revisit_expired` が開催日を過ぎた保留を urgent で拾う。
  日付未確定が保留理由そのものの回は期限を持てないので、
  `rejected_revisit_stale`(最終評価から30日以上、info)が受け皿になる。
  再評価したら `revisitedOn` に実行日を書く。**見たことの記録が無いと、
  見ていないのと区別が付かない。** 「後で見る」と書いた時点で、
  それを期限付きで表に出す側を作らないと二度と見ない。

- **URLスラッグは `sitelib` の `*_slug()` だけを使う。写しを持つと必ず食い違う。**
  `generate-rss.py` が `TAG_ROMAJI` と `safe_slug` を自前で持っており、
  sitelib に後から足した6タグ(アロイド・サボテン・着生植物・塊根植物・ビカクシダ・
  多肉植物)を知らないまま `feeds/tag-tag-<md5>.xml` を吐いていた。
  タグ頁は `/tag/aroid/` を名乗っているので、フィードのURLと一致していなかった
  (2026-08-20に検出)。検査は `sitelib_rule_duplicated`
- **`safe_slug` は日本語をほぼ全部落とす。残るのは名前に紛れていた半角英数字だけ。**
  「町田パリオ 4階」→ `/venue/4/`、「…（群馬県館林市野辺町1028-2）」→ `/venue/1028-2/` が
  実際に本番に出てsitemapにも載っていた。残渣は
  (1) URLとして何も伝えず、(2) **別の会場と衝突して片方のページを黙って上書きする**。
  上書きされたページは「生成済み」なので `cleanup_orphans` にも引っかからず、消えたことに気づけない。
  2026-08-20 に `1` `1f` `2` `2f` `i` `taut` の6組が衝突していた(どれも片側1件でページ化前だった)。
  対処: 英字3文字未満の残渣はハッシュに落とし、非ASCIIを含む名前には残渣+ハッシュ4桁を付ける。
  検査は `landing_slug_collision`。**読めるURLにしたい会場は `VENUE_ROMAJI` に足す**
- **会場ページを束ねるキーは `sitelib.venue_key()`。生の `location` で束ねない。**
  新しく足した回ほど `location` が「会場名（都道府県…住所）」の形になっており、
  住所の有無・空白の入れ方だけで同じ会場が別ページに割れていた(2026-08-20に10組)。
  割れると「複数回開催実績のある会場のみ」という会場ページの前提が崩れ、
  2回開催した会場がどちらも1件扱いでページにならない。
  **グルーピングのキーとスラッグの元は必ず同じ値にすること。**
  別々にすると、キーは2つ・URLは1つになって後勝ちで上書きされる
- **生成物には必ず掃除を付ける。掃除が無いのは `feeds/` だけだった。**
  ランディングは `cleanup_orphans`、詳細ページは 2026-07-30 に付けたが、
  `generate-rss.py` には無く、対象が消えたフィードがその日の中身のまま公開され続けていた
  (2026-06-11の「多肉」タグ、2026-07-31の沖縄地方)。検査は `feed_slug_drift`
- **生成しているだけで、どこからも辿れないファイルがあった。**
  タグ別・地域別フィード23本はサイト内のどこからも参照されておらずsitemapにも無かった。
  タグ頁・地域頁の `<link rel="alternate">` に自分のフィードを貼って解消(2026-08-20)。
  「生成された」ではなく「辿れるか」を見る(§5)
- **`is_vague_venue()` は 2026-08-20 まで `audit.py` のほうが賢かった。**
  「岐阜県内」「別府市内」「茨城県内会場」のような広域指定を弾く `_AREA_ONLY` を
  audit.py だけが持っており、sitelib は知らなかった。つまり**検出はできるのに、
  地図・JSON-LDのPlace・会場ページ側は素通し**という状態だった
  (`Place.name: "岐阜県内"` が5件出ていた)。sitelib に寄せて解消。
  規則を足す先は常に sitelib。検出側に書いて終わりにしない

- **listing-policy.json に書いた規則は、読むコードを書くまで規則ではない。**
  `blockedUrlDomains`(url/sourceUrl に使ってはならないアグリゲータ7ドメイン)は
  2026-08-24 まで参照している行が repo に1本も無かった。守っていたのは人の記憶だけで、
  crawl / enrich がアグリゲータのURLを出典に入れても誰も気づかない状態だった。
  アグリゲータは中止・休会・延期を反映しないので、出典にすると
  「裏取り済み」の見た目で誤情報が残る。検査は `blocked_source_domain`。
  **policy に項目を足したら、同じコミットでそれを読む側を足す。**
- **「人が数える運用」にした不変量は、検査に落とすまで守られない。**
  index.html のカード枚数の正常値(101枚)はこのプレイブックに書いてあったが、
  2026-08-24 の増殖事故はそれでは止まらなかった。想定集合は events.json から
  算出できる(未終了の全件 + `is_recent_past` の直近分、上限 `PAST_KEEP_MAX`)ので、
  件数のハードコードではなく生成側と同じ sitelib の規則で数える。
  検査は `index_card_drift`(重複・欠落・余分を別々に出す)。
  **プレイブックに「必ず数える」と書きたくなったら、それは検査にする合図。**
- **説明文の下限字数は `sitelib.DESC_MIN_CHARS`(50)。数字を直接書かない。**
  2026-08-24 に閾値を50へ揃えた時点でも、同じ数字は audit.py / check_events.py /
  enrich_events.py / build-detail-pages.py / listing-policy.json の5か所に
  リテラルで散っていた。以前この不一致(thin=50 / check=70 / enrich=120)が
  「短い回を優先度1位に並べておきながら too short で捨てる」取りこぼしを9週間続けた。
  検査は `desc_min_chars_drift`。**sitelib 以外でこの数字と比較したら鳴る。**
  無関係な用途でこの数字を使いたくなったら、その定数に名前を付けて sitelib に置く
- **`build-detail-pages.py` は scripts/ の外にあるので、grep の対象から落ちやすい。**
  上の5か所目はこれだった。`scripts/*.py` だけを回す検査は、
  必ず `build-detail-pages.py` を足してから件数を見る
- **index対象なのに内部リンクが1本も無い頁は、事実上存在しない。**
  フィード23本で起きたことは頁でも起きる。検査は `orphan_indexable_page`。
  例外は 404.html と Search Console の所有確認ファイルだけ。
  ここに出た頁は、一覧・ナビ・関連リンクのどこかから貼るか、
  noindex にして sitemap から外すかの二択

- **「今日」をランナーのタイムゾーンで決めない。`sitelib.today_jst()` が単一情報源（2026-08-28）。**
  GitHub Actions は UTC で走るので、06:00 JST 起動の daily はランナー日付が前日になる。
  `auto-status-jst.py` はまさにこの理由で作られたのに、**同じ書き方が他に9か所残っていた。**
  実害が2つ出ていた。
  1. `audit.py` が `audit-history.json` のキーを UTC 日付で書いており、
     **毎朝の daily が前日の実行記録を上書きして消していた。**
     08-27 の記録(315件)は翌朝の daily の値(367件)に置き換わっていて、
     レポートと履歴が食い違う。**08-28 より前の履歴は、その翌朝のCI実行の値である。**
  2. `coverage-sweep.py` の `sweptOn` が常に1日古く、巡回の鮮度検査が1日ぶん鈍っていた
  検査は `naive_local_date`。文字列や docstring の説明を拾わないよう、
  本文の正規表現ではなく **AST で実際の呼び出しだけ**を見る
  (最初に正規表現で書いたら、この検査自身の note を拾って誤検知した)。
  経過時間の計測は対象外。日付として比較・保存する値だけが問題

- **`.ics` の `DTSTAMP` は UTC 必須（RFC 5545）。JST の時刻に `Z` を付けない（2026-08-28）。**
  `generate-ical.py` が `datetime.now(JST).strftime('...Z')` を書いており、
  3本すべてが**9時間先の時刻を名乗っていた**。購読側は DTSTAMP で版の新旧を見るので、
  先の時刻を名乗ると後から出した訂正が古い版として無視されうる。
  検査は `build_timestamp_tz_drift`。**「今と比べて未来か」で見てはいけない。**
  ビルドから9時間経てば通ってしまい、検査が効かない時間帯ができる。
  同じビルドが書いた2つの時刻(`.ics` の DTSTAMP と `rss.xml` の lastBuildDate)を
  突き合わせれば、時計に依存せず判定できる

- **説明文の上書き保護を `updatedAt` だけに預けない（2026-08-28）。**
  2026-08-27 に入れた「updatedAt から14日は上書きしない」は、
  **新規登録で updatedAt を入れ忘れると一切効かない。**
  実際、直近14日に足した30件すべてが無防備で、週次エンリッチの2日前だった。
  「入れ忘れない」は運用で守れないので、`sitelib.desc_is_protected()` に集約し
  **addedDate でも守る**ようにした(ただし本文が `DESC_MIN_CHARS` 以上の回に限る。
  短いスタブまで保護すると、いちばん埋めてほしい回を14日間エンリッチから外してしまう)。
  `enrich_events.py`(書き込み側)と `audit.py`(検出側)は同じ関数を見る。
  `updated_at_missing_on_new`(info)が入れ忘れを拾う

- **イベントが「全部揃って」消えると、どの整合検査にも引っかからない（2026-08-28）。**
  `events.json` が正なので、消えれば詳細ページも sitemap もカードも一緒に消え、
  整合は完璧なまま件数だけが減る。唯一の手がかりは履歴の件数。
  検査は `event_set_shrunk`(前回比3件以上の減少で urgent)。
  削除は方針に沿った意図的なもので履歴19回で最大1件だったので、3件で誤検知しない

- **`metric_moved` は母数の変化を割り引く。指標には「異常を示す向き」がある（2026-08-28）。**
  08-27 に取りこぼし52件をまとめて掲載したら、`upcoming_no_image` が 72→103 で urgent が鳴った。
  増えて当然の増え方で、しかも中央値が追いつくまで4日鳴り続ける。
  **意図した掲載のたびに4日鳴る検査は、そのうち中身を見ずに閉じられる。**
  対処は2つ。(1) 掲載件数に比例する指標は母数の中央値で換算してから比べる
  (2) `upcoming_with_image` は「ある件数」で追加では減らない。
  **減ったときだけ画像の消失を意味する**ので、増加は鳴らさない。
  それが元々この指標を足した理由で、増加を鳴らすのは目的と逆。
  検証: 意図した52件掲載=0件、画像一斉消失(with 110→32)=2件、
  母数そのままで no_image が 20→103 = 1件

- **sitemap の `lastmod` を mtime で出さない（2026-08-30）。**
  CI は毎回まっさらに clone するので全ファイルの mtime がチェックアウト時刻になり、
  **313件すべてが毎日「今日更新」を名乗っていた**（08-28 / 08-29 / 08-30 の
  どの版も lastmod が全件同一日）。3月から変わっていない利用規約まで毎日更新と
  申告する状態で、当てにならない lastmod は無視されるので信号として死んでいた。
  内容の sha1 を台帳 `scripts/sitemap-lastmod.json` に持ち、
  **中身が変わった日だけ繰り上げる**。台帳は生成物と一緒にコミットする。
  検査は `sitemap_lastmod_untracked`（台帳の欠落・sha のずれ・sitemap との日付不一致・
  消えたURLの残骸の4つを見る）。
  **「毎回作り直すから最新」と「いつ変わったか」は別。**
  生成のたびに変わる値を、変更日として出さないこと

- **同じ列挙を2か所に書くと、片方だけ育つ（2026-08-30）。**
  `generate_sitemap.py` はランディング頁のディレクトリを2回列挙していた。
  収集する側には `guides` が入っているのに、末尾スラッシュ形のURLに直す側の
  タプルからは抜けていて、`guides/index.html` だけが `.../index.html` の形で
  sitemap に載っていた。頁側の canonical は `/guides/` なので、
  **sitemap が自分で「正規ではないURL」を申告していた**。
  `LANDING_DIRS` の1本にまとめて解消。検査は `sitemap_canonical_mismatch`
  （sitemap の loc とその頁の canonical を突き合わせる）。
  `sitemap_dead_entries` は「ファイルが在るか」、`sitemap_noindex_listed` は
  「noindex を載せていないか」しか見ておらず、**URLの形は誰も見ていなかった**

- **`.ics` の行長は継続行の先頭スペースも数える（2026-08-30）。**
  RFC 5545 §3.1 は1行75オクテット以下。`fold()` は中身を75オクテットぶん詰めてから
  `\r\n ` を足していたので、継続行が全部76オクテットになっていた（events.ics で816行）。
  ヘッダの `PRODID` / `X-WR-CALNAME` / `X-WR-CALDESC` はそもそも fold を通っていなかった。
  **折りたたみは購読側が必ず解くので、「中身が壊れていないこと」は検査にならない。**
  行の長さそのものを見る。検査は `ics_line_too_long`（CRLF が LF に落ちた場合も拾う）

- **`meta name="description"` の欠落は誰も見ていなかった（2026-08-30）。**
  `duplicate_indexable_title` は title の重複を見るが、description の有無は対象外だった。
  terms / contact / privacy / disclaimer / operator の5頁に無く、
  どれも sitemap 掲載・index 対象だった。生成物はテンプレートが必ず入れるので、
  ここに出るのは手書きの静的頁だけ。検査は `meta_description_missing`

- **データに書いた機械可読な値は、読む側を同じコミットで足す（2026-08-30）。**
  `blockedUrlDomains`(〜08-24) と `_reasonTypes`(〜08-27) で2回やった失敗を、
  類型として検査にした。`policy_machine_value_unread` が
  `listing-policy.json` の**真偽値・数値・ASCIIの短い語の配列**だけを拾い、
  その名前がクォート付きでコードに出てこなければ鳴らす（散文は対象外）。
  これで `doNotEscalate`（7節に真偽値・未参照）が出た。
  読む側として `pending_judgment_policy` を足し、
  キューの `id` 書式・重複・`proposal` の有無・`doNotEscalate` の節への投げ込みを見る。
  **キーの探索を素の部分文字列でやると、検査自身の note を拾って
  「読んでいる」ことになる**（`naive_local_date` と同じ罠）。
  辞書アクセスは必ずクォート付きの完全一致なので、そこだけを見る

- 挿入系スクリプトは冪等に（除去→再挿入）。過去に calendar/map が4.2MBまで肥大した事故あり

## 4. 自己改善のやり方

**気づいたことは必ずリポジトリに残す。** 手段は次の4つ。

| 気づいたこと | 書く場所 |
|---|---|
| 手順・ハマりどころ | このファイルの §3 |
| データの不整合を機械検出したい | `scripts/audit.py` に検査を追加 |
| 掲載可否の判断基準 | `listing-policy.json` |
| 構成の変更履歴 | `docs/architecture-2026-07.md` の §8 |

### audit.py に検査を足すとき

```python
add('key_name', '日本語のタイトル', items, note='対処のヒント', severity='urgent')
```

- `severity='urgent'` … 日次メールに出る。**0件が正常なものだけ**にする
- `severity='info'` … 参考行にまとめる。常時0にならないものはこちら
- **health.yml の編集は不要。** メールは `severity` を見て動的に出す
- 検査を足したら1回実行し、誤検知が出ないことを確認してから push する。
  **修正前のデータにも当てて、狙った件数が出ることを確かめる**。
  0を返す検査は、壊れていても0を返す
- 誤検知が止まらない検査は消す。**測れない検査は無いほうがよい**
- **`events.json` にキーを増やしたら `audit.py` の `KNOWN_EVENT_FIELDS` にも足す。**
  足さないと `unknown_event_fields` が毎日鳴る。逆に、読む側のコードが無いキーは
  この検査で止まる(2026-08-11に `organizerUrl` / `urlCheckOk` / `_htmlName` を検出)

### 判断の記録

- **問い合わせを処理済みにするときは `inquiries-processed.json` の `outcomes` に
  何をしたかも書く。** `processed` のタイムスタンプだけでは、処理済みにしたが実際には
  何も反映していない取りこぼしを後から検出できない。
  形: `{timestamp, type, eventName, action, detail, verifiedOn}`。
  `action` は `listed` / `rejected` / `queued` / `no-action`。
  このファイルを読むコードは無いのでキーを増やしてよい(2026-08-12に確認)
- 見送りは `rejected-events.json` に `reasonType` 付きで記録する。
  使える値は同ファイルの `_reasonTypes`（`policy` / `unverified` / `undisclosed` / `cancelled`）だけ。
  名称に開催日が書かれている回は `eventDate` も入れる（保留の期限判定に使う）。
  `revisit=true` を再評価したら、掲載/確定のどちらでもない回は `revisitedOn` に実行日を書く
- 人間の判断が要るものだけ `pending-judgments.json` に積む。
  そのとき **`listing-policy.json` への追記案を必ず添える**。同じ問いを翌日も投げないため
- 説明文が短いだけの回はキューに積まない（週次エンリッチに任せる方針で確定済み）

## 5. 自分を疑うこと

- **存在確認ではなく機能確認をする。** 「枠が存在する」ではなく「見える位置にあるか」、
  「生成された」ではなく「全件載っているか」を見る
- **スクリプトは成功件数だけでなく除外・欠落も出力する。** 黙って落ちると誰も気づかない
- **検算は「増えたか」ではなく「減っていないか」を見る。**
  CSSの範囲置換で1,100行を誤削除したとき、中括弧バランスは0のままで検出できなかった
- 視覚的な変更はスクリーンショットを見るまで完了と言わない
- `audit-history.json` に推移が残る。**前回より悪化していたら、自分の変更を疑う**
- **レポートに書く件数は、前回レポートから引き写さずファイルを数え直す。**
  本タスクの 2026-08-12 と 08-13 のレポートは `pending-judgments.json` を「7件のまま」と
  書いたが、7件は 08-11 の 6c4b084 で処理済みで、当時の中身は2件だった。
  管掌外のファイルほど前回の記述をそのまま運びやすい。触らないファイルでも、
  件数を書くなら `python3 -c` で数えてから書く

## 6. 週次の自己点検（site-health-check が実施）

毎週、次を見て**プレイブック自体を更新する**。

1. `mzplants\agave-navi\task-reports\` の直近7日分を読む。
   同じ失敗が2回以上出ていたら §3 に追記する
2. `audit-history.json` の推移を見る。
   - urgent が前週より増えていれば原因を特定して直す
   - 何週間も同じ値のまま動かない項目は、対処されていないか検査が不適切。どちらかを直す
   - **「対処されていない」と決める前に、対処する側のコードが入口で落ちていないかを読む。**
     2026-08-18、`short_descriptions` が9週間18のまま動かなかった原因は、
     enrichment が短文イベントを優先度1位に並べておきながら、`needs_update` の条件に
     説明文の長さが入っておらず `Already enriched, skipping` で即座に落としていたこと。
     「手が足りていない」ではなく「手が届く前に return していた」。
     推移が動かない項目は、まず担当スクリプトのスキップ条件を読む
   - 常に0が続く項目は `severity='info'` に落とすことを検討（メールのノイズを減らす）
3. `pending-judgments.json` が3件以上溜まっていたら、人間の判断が本当に要るのか見直す。
   要らないものは `listing-policy.json` に基準を書いて自動化する
4. `task-runs.json` の `task_run_gap` を見る。抜けた回があれば、そのタスクの
   task-reports と突き合わせて原因を書く。**台帳に書かれていないタスクを足す。**
   スケジュールを増やしたのに台帳に無いと、そのタスクだけ生存確認が無い状態に戻る
5. 上記でプレイブックを更新したら、何を変えたかレポートに1行で書く

**このタスク自身の抜けについて(2026-08-31 追記)。**
site-health-check は週次だが、`task-reports/` に 08-03 / 08-10 / 08-18 の次が無く、
**08-25 の回は成果物ゼロで終わっていた。** スケジュールは enabled のままで
`lastRunAt` も当日だったので、気づいたのは今日ファイル名を人が並べたときだった。
event-listing-review では同じ穴を `reviewedHistory` で塞いだのに、
**他の3タスクには適用していなかった。** `task-runs.json` と `task_run_gap` で塞いだ。
週次は曜日で照合しない。08-17 起動の回のレポートが 08-18 付で残っており、
曜日一致にすると1日の遅れで鳴り続けるため、7日の窓に1回あるかで見る。

## JS/CSS を直したら版数を上げる (2026-08-20)

`status-auto.js` / `list-ui.js` / `affiliate.js` / `style.css` の中身を変えたら、
**必ず `scripts/sitelib.py` の `JS_VERSION` / `CSS_VERSION` を上げる。**

版数を据え置いて中身だけ差し替えると、URL が変わらないので CDN と閲覧者の
ブラウザが旧ファイルを配り続ける。直したつもりで本番は直っていない状態になる。
2026-08-20 に status-auto.js を3回直したが、版数が `20260820a` のままで
本番には初回の版が配信され続けていた。修正の確認は
`https://agave-navi.com/status-auto.js` を直接取得して中身を見ること。

`sync-footers.py` が静的ページの `?v=` を sitelib の値に揃え、
`audit.py` の `css_version_drift` / `js_version_drift` が乖離を検出する。
検出できるのは「ページの参照が正規値と違う」ことだけで、
「正規値を上げ忘れた」ことは検出できない。ここは人が守る。

## 会場ページのURL (2026-08-21 決定)

`safe_slug` は日本語を落とすので、`VENUE_ROMAJI` に無い会場は
ハッシュURL `/venue/v-xxxxxxxx/` になる。

**運用ルール:**
- 掲載イベントが **3件以上** (`sitelib.VENUE_ROMAJI_MIN_EVENTS`) の会場だけ
  `_VENUE_ROMAJI_RAW` にローマ字を足して読めるURLにする。
- **2件の会場はハッシュURLのまま据え置く。** 2件は増減しやすく、
  そのたびにURLが変わるのを避ける。ハッシュURLは許容する。
- ローマ字を足すと既存URLが変わる。**必ず `_VENUE_REDIRECTS_RAW` に
  旧slugを残す。** 値は宛先の会場名で、スラッグが将来また変わっても
  `venue_slug()` で追随する。GitHub Pages はサーバ側リダイレクトを
  持てないので、`generate-landing-pages.py` が meta refresh + canonical +
  noindex の中継頁を出す。
- 候補は `audit.py` の `venue_slug_romaji_candidates` が毎ビルド出す。
  `venue_romaji_unused` は表記変更で当たらなくなった項目、
  `venue_redirect_broken` は宛先が消えた中継頁を拾う。

## 「今日」の出し方 (2026-08-29)

JSで JST の暦日を出すときは **必ず** `new Date(Date.now() + 9*3600000)` に
`getUTCFullYear()/getUTCMonth()/getUTCDate()` を使う。
`getTimezoneOffset()` も `setHours(0,...)` も要らないし、使ってはいけない。

`Date.now()` は既にUTCエポックなので、そこへ `getTimezoneOffset()` を足すと
JSTの閲覧者では -9h と +9h が打ち消し合ってUTCの暦日が返る。
0:00〜9:00 JST の9時間ずっと前日と判定され、「本日開催」が「明日開催」、
翌日の回が「あと2日」にずれる。**JST以外の閲覧者では偶然正しく出るので、
東京で朝に見たときだけ壊れる。** 2026-08-29 に利用者の指摘で発覚。

- 判定の単一情報源は `status-auto.js` の `AEN_TIME`(JS)と
  `scripts/sitelib.py` の `today_jst`(Python)。
- `scripts/test-date-boundary.js` が 0時直後・早朝・深夜を4タイムゾーンで
  検証する。`build-all.sh` の先頭で走り、失敗すればビルドが止まる。
- `audit.py` の `js_local_timezone_math` が手書きの時差計算を、
  `date_boundary_test_unwired` がテストの外し忘れを拾う。
