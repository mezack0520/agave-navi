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
5. **起動直後に `python3 scripts/record-run.py <taskId>` を実行し、その変更を含めて push する。**
   台帳(`task-runs.json` / `event-listing-review` は `new-inquiries.json`)に
   起動日(JST)が入る。冪等なので同じ日に何度呼んでもよい。
   `<taskId>` は `agave-event-update` / `event-monitor` / `site-health-check` /
   `event-listing-review`。

   **これは最後ではなく最初にやる。**(2026-09-02 に是正)
   以前は「終わったら書く」設計だったが、成果物が無い回はそもそも push されず、
   記録だけが落ちていた。2026-09-02 に台帳を見たら
   `agave-event-update` は3日連続で走っていたのに `history` が空、
   `event-monitor` は3回中1回しか書けていなかった。
   結果、監査 `task_run_gap` が**実際には走っていた日を「抜け」として出していた**。
   スケジューラ側の `lastRunAt` は全タスク当日実行済みを示しており、
   環境も enabled も正常だった。抜けていたのは実行ではなく記録。

   記録するのは**起動した日**であって完走した日ではない。
   監査が知りたいのは「そもそも動いたのか」なので、それで足りる。
   完走したかは成果物とレポートで分かる。
   起点(`since`)より前は判定しない。台帳の書き込みが働いていなかった期間を
   遡って「抜け」と呼ばないため、機構を直した日に `since` を張り直してある。

置き場（すべて `C:\Users\yujim\iCloudDrive\Claude\Projects\mzplants` 配下）:
- PAT: `agave-navi\github.pat`
- 実行レポート: `mzplants\agave-navi\task-reports\<taskId>_YYYY-MM-DD.md`
- 受け渡しJSON: `mzplants\agave-navi\work\`

## 2. 書き込み手順

- コミットは `git push`（`https://github.com`、名義 `mezack0520 <88774621+mezack0520@users.noreply.github.com>`）
- **PATは `.github/workflows/` も含めてpushできる**（2026-08-10に実証。以前「権限不足」と
  記録していたのは誤り）。`workflow_dispatch` はPATでも403で使えない
- **サンドボックスから `api.github.com` は通る（2026-09-07 訂正・実測）。**
  以前ここに「不通。`github.com`(git) のみ」と書いていたが、今日の実測では
  無認証 GET が200で返る。`Actions API は403で使えない` も読みに関しては誤りで、
  PAT を付ければ**ジョブの実行ログまで取れる**（`actions/jobs/<id>/logs` が200）。
  無認証だとログだけ403なので、一覧・ジョブ一覧は素で、ログは PAT で取る。
  つまり **Actions の失敗検出にブラウザは要らない。**
  ```
  curl -s "https://api.github.com/repos/mezack0520/agave-navi/actions/runs?per_page=60"
  curl -s "https://api.github.com/repos/.../actions/runs/<id>/jobs"
  curl -s -L -H "Authorization: Bearer $PAT" ".../actions/jobs/<id>/logs"
  ```
  `agave-navi.com` への curl も通るので、本番HTMLの構造照合・
  repo との sha1 比較もシェルでできる。ブラウザが要るのは
  **JSが動いた後の姿**（`.rk-card` / `.aff-bar` / コンソール）だけ。
  書き込み（`workflow_dispatch` の POST）は従来どおり403。
  **到達性は変わる。「不通」と書いてあっても、まず1回叩いて確かめること。**
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
- **途中で切れた見出しを判定に使わない（2026-09-01）。**
  LEAFLA の各ページ下部にある「最近追加されたイベント」枠は、記事の見出しを
  途中で切って `…` を付けたリンクを並べる。**この枠はページの日付と無関係に
  全ページへ同じ内容で出る。** 切り詰めが判定を2重に狂わせていた。
  1. 完全版「Lima2026が鹿児島で開催、塊根植物や琉球盆栽などを展開」は
     `盆栽`(OUT_OF_SCOPE)を含むので範囲外。**切ると盆栽が落ちて範囲内に化ける**
  2. 完全版のリンク文字列には会場名(`📍LIMACOFFEE…`)が付くので掲載済みの
     `location` と照合できるが、切ると会場が落ちて照合できない
  結果、掲載済みの `aobouzu-kagoshima-popup-2026-09`(9/6-7・同じ会場・
  出典も同じIG投稿)を45日ぶん「取りこぼし」として出し続けていた。
  対処: `is_truncated()` で切り詰めを判定し、同じ巡回で完全版が見えていれば
  **枠の複製は判定しない**(完全版は自分の開催日のページで判定済み)。
  戻せなかったものは `truncatedUnresolved` に出す。黙って捨てない。
  **切り詰めた文字列は判定材料にならない。**部分文字列は、含む語も含まない語も
  変えてしまうので、範囲判定と同一判定の両方が同時に狂う
- **アグリゲータはイベント名を会場名・ブランド名で付けることがある。**
  同じ回を LEAFLA は「Lima2026」(会場 LIMACOFFEE 由来)、こちらは
  「青坊主 鹿児島ポップアップ」(出店者名)と呼んでいた。
  **名前だけの照合では絶対に一致しない。**照合が会場でも走る設計に助けられた
  (`matches(t, e['venue'] or e['location'])`)。
  取りこぼし候補を裏取りするときは、名前ではなく**日付+会場**で既存を引く
- **`--self-test` は main() から毎回呼ぶ（2026-09-01）。**
  coverage-sweep の自己テストはどのCIからも呼ばれておらず、
  `date_boundary_test_unwired` と同じ「外れたテスト」になっていた。
  daily で落とすと push を巻き込むので、`main()` が静かに自己テストを走らせ、
  失敗したら `errors` に積む。`coverage_sweep_broken`(urgent) が同じ日に鳴る。
  **テストを足したら、それを呼ぶ側を同じコミットで足す。**

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

- **回答シートは組み込みブラウザからは読めない（2026-09-01 確定）。**
  組み込みブラウザはGoogleにログインしておらず、gviz CSV を叩くと
  `accounts.google.com` に飛ばされる。Cookieのインポート機能はあるが
  **Windowsでは Firefox からしか取り込めない**（macOSは Chrome/Edge/Firefox）ので、
  Windows＋Chrome のこの環境では使えない。
  目崎の判断で**ブラウザは組み込みのまま**にした（2026-09-01）。
  つまり**このタスクからシートを読む手段は無い**。
  Claude in Chrome なら実Chromeなので読めるが、既定を変えない方針。

- **だから `sheetRows` は GAS 側が書く（2026-09-01 変更）。**
  `onFormSubmit` が `countSheetRows()` の結果を `sheetRows` / `sheetCheckedOn` に書く。
  ブラウザで数えて手で入れる手順は廃止。読めないのに数えようとすると、
  測れないまま処理を進めて `sheetCheckedOn < reviewedOn` の urgent が立つだけになる。
  **この方式の穴**: GASが止まると `sheetRows` も止まる。GASの死活は
  `lastChecked` の古さと `inquiry_check_stale` で見る（シート行数では見られない）。

- **書く側を変えたら、その値を読む検査を同じコミットで直す（2026-09-01）。**
  08-31 に `sheetRows` / `sheetCheckedOn` を「タスクが gviz で数える」から
  「GASの `onFormSubmit` が書く」へ移したが、`audit.py` 側の
  `sheetCheckedOn < reviewedOn` → urgent はそのまま残っていた。
  新しい設計では `sheetCheckedOn` は**フォーム送信があった日にしか進まない**ので、
  この条件は送信の無い日は必ず成立する。つまり
  **タスクが正常に動くほど毎日 urgent が鳴る検査**になっていた。
  08-31 は送信があって日付が並んだので鳴らず、今日 `reviewedOn` を進めた瞬間に
  鳴るところだった(旧コードに今日のデータを当てて1件出ることを確認済み)。
  新しい不変量は **`sheetCheckedOn >= lastChecked`**。
  どちらもGASが同じ瞬間に書く値なので、行数だけ古いなら
  `countSheetRows` を持たない版のGASが動いている。
  **`doNotEscalate` や `blockedUrlDomains` と同じ型の穴だが、向きが逆。**
  あちらは「書いたのに読む側が無い」、こちらは「読む側が古い設計のまま残った」。
  設計変更のコミットでは、その値を**読んでいる行を grep してから**終わる
- **`inquiries-processed.json` の件数は `processed` を見る。`items` ではない（2026-09-01）。**
  このファイルは `processed`（重複判定用のタイムスタンプ配列）と
  `outcomes`（各回答をどう処理したかの記録）で出来ている。
  2026-09-01 に `items` というキーを勝手に足し、そちらだけを見て
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
- **その規則を、CI側6本は2026-09-07まで守っていなかった（2026-09-07）。**
  上の1行は 2026-08 から書いてある。にもかかわらず
  `daily` / `health` / `ops` / `sync-events` / `weekly-discovery` / `weekly-enrichment` の
  push は全部 `git pull --rebase || true` のままだった。
  2026-09-04 23:25 UTC、`sync-events` と同時刻の push で `Daily Maintenance #160` が落ちた。
  ログの形はこうなる。
  1回目: `! [rejected] main -> main (fetch first)`
  → `git pull --rebase` が `feeds/*.xml` 22本と `events.ics` と `audit-results.json` で衝突
  → `|| true` が衝突を握り潰す
  → 2〜5回目: `fatal: You are not currently on a branch.` /
    `fatal: Exiting because of an unresolved conflict.`
  **1回目が拒否された時点で、残り4回は成功しえない。**
  リトライ回数を増やしても直らない類の失敗で、しかも
  「5回試して駄目でした」に見えるので競合が原因だと読み取りにくい。
  対処: 復旧を `scripts/ci-push.sh` に集約した。使い方は
  `bash scripts/ci-push.sh "<commit message>" ["<再生成コマンド>"]`。
  拒否されたら rebase せず、**生成物でないファイルの差分だけを持ち越して
  `origin/main` に作り直し、再生成してから commit し直す**。
  生成物の一覧は `scripts/ci-generated-paths.txt` が単一情報源。
  検査は `ci_push_bypassed`(urgent、自前 push と rebase の両方を拾う)と
  `ci_generated_paths_missing`(urgent、除外リストの綴り間違いを拾う)。
  **散文の規則は、それを破れる側のコードが残っているかぎり守られない。**
  §3 に「必ずこうする」と書いた手順は、同じコミットで
  (a) それを実装した1本に寄せる (b) 迂回を検出する検査を足す、まで行って終わり。
  検証は sandbox に bare repo を立てて実測した(2026-09-07): 通常 / 差分なし /
  前段ステップの既存コミット / 単発の割り込み / 2連続の割り込み /
  旧ロジックが残した rebase 途中 の6通りで、両者の変更が残ることを確認済み。
  **起点は毎周 `git merge-base` で取り直すこと。** 固定すると、相手のコミットを
  取り込み済みの周で「相手の変更を取り消す差分」を作り、貼り直した瞬間に相手の仕事を消す
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
- **楽天APIの送信間隔は「応答からの待ち時間」で数えない（2026-09-07）。**
  `affiliate.js` は `setTimeout(next, 350)` を**応答が返ってから**掛けていた。
  実測の間隔は 905ms / 1002ms で、楽天の 1秒1件の境界に張り付いている。
  回線が速い回では 1秒に2〜3件飛んで 429 が返る（今日トップで1件観測）。
  429 は `r.ok` で弾かれて `null` になるだけなので**例外もログも出ず、
  キャッシュにも入らない**。表に出るのは「その枠だけ商品カードにならず
  テキストリンクのまま残る」という形だけで、見に行かないと分からない。
  送信時刻を覚えて `MIN_INTERVAL=1100` を保証する数え方に変えた。
  **待ち時間は「前の送信から」で測る。「前の応答から」だと応答時間のぶん詰まる。**
  キャッシュ `agn_rk_v1` は TTL 24時間で、期限切れの回だけ取りに行く。
  確認は `performance.getEntriesByType('resource')` で
  `openapi.rakuten.co.jp` の件数を見るか、`window.fetch` を差し替えて
  status を記録する（コンソールには `429` としか出ず、どのURLか分からない）
- **組み込みブラウザは `innerWidth` が 0 を返す（2026-09-07）。**
  そのため `matchMedia('(max-width: 720px)')` が真になり、
  **`.aff-bar` は何もしなくてもDOMに出る**。下の「デスクトップ幅では出ないのが正常」は
  実Chrome(Claude in Chrome)の話で、組み込みブラウザには当てはまらない。
  matchMedia を差し替えて `affiliate.js` を再注入する手順は要らず、
  50%までスクロールして `.aff-bar.is-shown` と実商品リンクを見れば足りる
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

- **リポジトリにある .html は、置き場所に関係なく全部が公開URLになる（2026-09-01）。**
  GitHub Pages はリポジトリの中身をそのまま配信する（`.nojekyll` があるので
  アンダースコア始まりも隠れない。robots.txt も全許可）。
  `templates/detail.html` が `https://agave-navi.com/templates/detail.html` として
  生きており、title が `{{name}} | アガベイベントナビ`、canonical が存在しない
  `/events/{{slug}}.html`、robots が置換前の `{{robotsMeta}}` で index 対象だった。
  どこからもリンクされていないので `orphan_indexable_page` が拾うはずだったが、
  **同検査は templates / staging / guides_content を頁の母集団から外している。**
  title 重複・description 欠落・内部リンクの各検査も同じ除外を持つので、
  **除外した先だけは誰も見ていない**状態が続いていた。
  対処はテンプレートを `.html` 以外の拡張子にすること（`detail.html.tmpl` に改名）。
  置き場を変えても配信からは隠れないので、拡張子で外すのが唯一効く。
  検査は `unrendered_template_published`（未展開の `{{placeholder}}` を含む .html と、
  除外階層に残った .html の両方を見る）。前者は生成物側の置換漏れも同時に拾う。
  **検査の母集団から外すときは、外した先を見る検査を同じコミットで足す。**

- **リポジトリは public。repo に書いたものは全部公開だと思って書く（2026-09-01）。**
  `private=false` で、しかも GitHub Pages が同じ内容を配信するので、
  公開経路は2つある（github.com の履歴と agave-navi.com のURL）。
  `new-inquiries.json` は設計上、フォーム送信者の**氏名とメールアドレス**を通す。
  GASが書いて push → `notify-inquiry.yml` がそれを読んでメール本文を組む、という
  受け渡しなので、申請1件ごとに必ず両方の公開経路を通る。
  2026-08-31 の `9bf760e8` で実際に1件が 12:41〜17:04 のあいだ公開URLに出ており、
  コミットは今も公開履歴に残っている。
  検査 `published_pii`(urgent) を足したので、以後は通った日に鳴る。
  **ただし鳴っても「通ったこと」は取り消せない。**恒久対処（連絡先をGASから
  直接メールし、repo には timestamp/type/eventName/body だけ通す）は
  Apps Script の再デプロイが要るのでタスクからは打てず、
  `pending-judgments.json` の `event-monitor:inquiry-pii-in-public-repo` に積んである。
  **監査結果そのものも公開ファイル。**`audit-results.json` に値を書くと
  検査が二次的な露出経路になるので、`published_pii` は所在だけを出して値は出さない。

- **「開催予定のうち◯◯な件数」は、暦だけで毎日減る（2026-09-01）。**
  `upcoming_with_image` は「ある件数は追加では減らないので、減ったら必ず消失を意味する」
  という理屈で 2026-08-24 に足し、`metric_moved` の警報方向を -1 にしていた。
  **前半は正しいが後半が成り立たない。**母集団である「開催予定」そのものが毎日縮むので、
  画像を持つ回が past に落ちるだけで減る。
  実測: 08-30 の 33 → 08-31 の 30 は `imageUrl` の削除ゼロ（全件の保有数は 63 で不動）で、
  8/31 に終わった3件が upcoming から外れただけ。今日の events.json をそのまま
  先送りすると 9/28 に 13、10/26 に 4 まで落ちる。画像は1枚も失われていない。
  しかも小さくなるほど `metric_moved` の「絶対10件以上」に届かなくなるので、
  **10月には全部消えても鳴らない。**
  対処: 消失は暦で動かない母集団で数える。`events_with_image`（全件）は
  追加でも暦でも減らず、減るのは imageUrl の削除かイベントの削除だけ。
  後者は `event_set_shrunk` の担当なので、その差し引きを引いた残りを
  `event_image_lost`(urgent) が**実数で**出す（1件でも鳴る。統計では当てない）。
  `upcoming_with_image` は参考値として残すが `metric_moved` の対象から外した。
  **「増えないから減ったら異常」と言う前に、母集団が動かないかを確かめる。**

- **参考値の母数は、その指標が数えている集合の母数にする（2026-09-01）。**
  `_METRIC_SCALES_WITH_EVENTS` は開催予定だけを数える指標まで**全件**で割り引いていた。
  全件は past を貯め込むので単調に増えるが、開催予定は暦で減る。別の量である。
  そのため 2026-08-27 に潰したはずの「まとめて掲載すると鳴る」誤検知が残っていた。
  実測: 画像なしの開催予定を50件足すと、全件は +13% なのに開催予定は +38% で、
  換算が追いつかず `upcoming_no_image` が鳴る（新方式では鳴らない）。
  母数は履歴に `upcoming` として残す。直近7回が全部それを持つときだけ使い、
  混ざる移行期は全件で換算する（欠けた回だけ別の母数で埋めると中央値の中で2つが混ざる）。

- **見送り記録は、後から掲載しても消えない。誰も突き合わせていなかった（2026-09-05）。**
  `rejected-events.json` に `rejected_but_listed` という検査は前からあったが、
  中身は「見送りの `key` が掲載 `slug` の部分文字列か」だけだった。
  **`key` は見送りを決めた日に手で付け、`slug` は掲載する日に別途手で付ける。**
  同じ回でも綴りが揃うことはまず無いので、この検査は壊れていても常に0を返していた
  (`taniku-torai-ki-ryuo-2026-09` / `taniku-toraiki-ryuoh-2026-09`、
  `gardens-umekita-2nd-anniversary-2026` / `gardens-umekita-2nd-anniv-2026-09`
  のどちらも部分文字列にならない)。実際に3組が両方のファイルに同時に載っていた。
  実害は2つ。(1) 掲載済みの回が `revisit=true` の再評価待ちとして残り、
  `rejected_revisit_expired` が開催日の翌日に**偽の urgent** を出す
  (多肉渡来記は9日前に掲載済みで、明日まさに鳴るところだった)。
  (2) 同じ回の判断が2つのファイルで食い違ったまま残る。
  照合は `eventDate` + 最長共通部分文字列でやる。包含では駄目で、
  **掲載側の正式名称のほうが長いことも、会場名に「道の駅」のような接頭辞が付くこともある。**
  閾値4の一致「だけ」を根拠にすると、この分野の一般語(植物・多肉植物・プランツ・
  マルシェ・popup・plants・ーパーク)が全部引っかかって誤検知が7件出た。
  名称と会場が同時に当たるか、名称だけで8字以上のときに限る。
  同じ会期・会場で併催される別イベントは正常に出るので、
  見送り側に `coexistsWith=<掲載slug>` を書いて明示的に除外する。逃げ道があるので0にできる。
  **`0` を返し続けている検査は、守られている証拠ではない。**
  照合するキーが「別々の日に人が手で付けた2つの文字列」なら、その検査は最初から死んでいる。

- **見送りの理由に、複合イベントの閾値を安易に当てない（2026-09-05）。**
  `gardens umekita 2周年` を2026-07-30に「著名ナーセリー2社で3社未満」として見送っていたが、
  これは `compositeEvents`(植物**以外**が主体の総合イベントに出店比率を当てる規則)の誤用だった。
  gardens umekita は「水と緑をもっと身近に」を掲げる**植物・アクアリウムの専門業態店**で、
  公式告知の名称そのものが「2周年記念イベント **店頭即売会**」、
  内容も三浦園芸(レアアロイド)とカクト・ロコ(ビザールプランツ)の即売会だけ。
  植物しか売っていない催しを「ナーセリーが3社に満たない」で落としていた。
  運営会社がホームセンター(コーナン商事)であることに引きずられている。
  **見るのは運営会社ではなく、その店舗の業態と、告知の名称・中身。**
  規則は `listing-policy.json` の `plantCentric.compositeEvents.storeAnniversary` に書いた。

- **`coverage-gaps.json` が0件でも「取りこぼしなし」ではない。あれは LEAFLA しか見ていない（2026-09-06）。**
  `coverage-sweep.py` は LEAFLA の日付別ページだけを巡回する。CI から
  NextMeet と Instagram は読めないので、他社を足す実装ができない。
  今日、`coverage-gaps` は 0件・`errors` 0・`coverage_sweep_broken` も 0 という
  いちばん健全に見える状態だったが、**NextMeet の月別一覧を手で開いたら
  未掲載が15件出た**（10月5件・11月10件）。うち5件は 11/14 以降の回で、
  LEAFLA の先45日の窓の外にあった。残りは窓の中なのに LEAFLA 側に無い。
  「アグリゲータ3社は互いに取りこぼす」は §3 に前から書いてあるのに、
  **機械化されたのは1社だけで、残りを回ったかどうかは repo のどこにも
  残っていなかった。** `reviewedOn` / `sheetRows` と同じ型で、
  **記録が無い手順は、やらなくても誰も気づかない。**
  対処: `manual-sweeps.json` に手動巡回の台帳を作り、
  `audit.py` の `manual_sweep_stale`(urgent) が経過日数で鳴らす。
  毎回 `lastSweptOn` / `lastScope` / `history` を更新する。
  **回れなかった回は日付を進めない。**進めると回った回と区別が付かなくなる。
  巡回するのは最低この2つ。
  - `https://nextmeet.app/plants/monthly/YYYY-MM` を**先2か月ぶん**（staleDays 7）
  - まとめブログの期間まとめ記事（もすレコ。の半期まとめ等・staleDays 14）
  NextMeet の月別は1ページに全国の会期が並ぶので、
  `events.json` と機械照合すれば数分で差分が出る。名称の表記ゆれで外れるので
  （`ぶらりぷらんつ` と掲載済み `ぷらりぷらんつ`）、**日付+会場でも引く**

- **アグリゲータの一行要約は、参加条件を落とす。掲載可否が逆になる（2026-09-06）。**
  埼玉サボテンクラブの大銘品展を NextMeet は
  「2年に一度の催しで、誰でも参加できる優良苗の交換会も予定されている」と書く。
  掲載相当に読める。ところが主催 IG の原文には
  **「即売会はありませんのでご留意ください。」**と明記され、
  参加費1500円(弁当飲物付)・第1部が品評会・第2部が交換会(1人10点まで)だった。
  一般来場者が買える回ではないので `closedGatherings` に当たる。
  **要約は「何があるか」しか書かず、「何が無いか」は落ちる。**
  クラブの品評会・展示会は、名前が展示会でも即売の有無を原文で確かめる。
  規則は `listing-policy.json` の `plantCentric.clubShowNoSale` に書いた

- **会場公式の一覧は、掲載と見送りを同時に決められる（2026-09-06）。**
  川口緑化センター 樹里安の `/event/` を1回開くと、
  掲載する「秋の多肉植物・サボテン展示会」(10/24-25)と、
  見送る「秋の古典園芸植物展」(9/26-27)・「晩秋の古典園芸植物展」(11/28-29)が
  同じ画面に並ぶ。**見送りをその場で記録しておけば、
  次に同じ会場の一覧を見たときに悩み直さずに済む。**
  同じ会場で年に何度も出るシリーズはこの形が効く
  （樹里安の古典園芸植物展は年4回、広島市植物公園の洋ラン展も毎年）。
  ジャンルの線引きは `listing-policy.json` の `outOfScopeGenres` に書いた

- **説明文に「次回開催」の年を書かない（2026-09-06）。**
  ときめきマルシェの2会場を入れたとき、主催が同じ投稿で告知していた
  次回(2027年3月)を説明文に書いたら `desc_stale_year` が2件鳴った。
  この検査は「本文の年が開催年と違う＝前年告知の使い回し」を見るもので、
  **未来の回を書いても同じように当たる。**検査のほうが正しい。
  次回日程は `watch-sources.json` の `awaitingNextEdition` が
  events.json から自動で導出するので、本文に書く必要はそもそも無い

- **会場名が無く住所しか出さない主催がいる。`venue` を作らない（2026-09-06）。**
  BOTANICAL LINK（ボタりん）は主催の告知が「愛知県春日井市坂下町4-224-7」だけで、
  施設名が存在しない。`venue="BOTANICAL LINK POP UP 会場"` のような
  説明的な文字列を置くと `venue_location_disagree` が鳴る（正しい）。
  §3 の「会場名が location にあるなら venue と mapQuery を消す」と同じで、
  **無い名前を作らず、location に住所だけを入れてフォールバックに任せる**

- **参考値を「直近7回の中央値」と比べると、週の周期を持つ指標は週末のたびに鳴る（2026-09-06）。**
  直近7回は平日5・土日2で**必ず平日に寄る**。`ongoing_events` は
  一日だけのイベントが土日に集中するので、平日の中央値 1.5 に対し土日は 9.5 で6倍ある
  （08-24〜09-06 の実測）。今日(日)の 15 が `metric_moved` で urgent を出したが、
  これは暦がそうさせているだけで異常ではない。
  母数の割り引き(`_METRIC_SCALES_WITH_UPCOMING`)では吸収できない。
  開催予定は 132→148 とほぼ動かないのに開催中だけが 1→15 になる量だからで、
  **母数が動いていないのに値が動く**のがこの周期の性質。
  対処: `_METRIC_WEEKLY_CYCLE` に入れた指標は**同じ曜日区分(平日/土日)の履歴だけ**で
  基準を作る。窓は28回に広げる（直近7回では土日が2回しか入らず標本が足りない）。
  標本が3回に満たないうちは判定しない。混ぜた基準に戻すと元の誤検知に戻る。
  検証: 修正前のデータで1件・修正後0件、週末の基準9に対し 22 以上なら今も鳴る
  （15は鳴らない、18も鳴らない、22で鳴る）。
  **同じ問題が二度と黙って通らないように、周期が生まれたこと自体を検査にした。**
  `metric_weekly_cycle_unmodeled`(urgent) が全 metric の平日・土日の中央値を比べ、
  絶対5件以上かつ相対30%以上の差があるのに `_METRIC_WEEKLY_CYCLE` にも
  `_METRIC_NO_ALARM` にも入っていない指標を出す。両側3回以上の標本があるときだけ判定する。
  検証は別の指標(`upcoming_no_image`)に人工の周期を仕込んで、
  ongoing_events 決め打ちでないことを確かめた(土日160で鳴り、140=27%では鳴らない)。
  **「毎週末に鳴る検査」は、毎日鳴る検査と同じで、そのうち中身を見ずに閉じられる。**

- **`audit.py` は読んだ履歴の行をそのまま書き戻す。試験で履歴を触ると本物が汚れる（2026-09-06）。**
  上の検証で `_hist_wide` の行に値を注入したら、その行は `audit-history.json` の
  実体と同じオブジェクトなので、**08-29 / 08-30 / 09-05 の `upcoming_no_image` が
  200 に書き換わったまま保存された**。監査は毎回全履歴を読んで書き戻すので、
  読み込んだ構造を試験で書き換えると過去の実測値が消える。
  `git diff audit-history.json` を見て気づいた。
  **注入して試すときは、終わったら必ず `git checkout -- audit-history.json` してから
  本物をもう一度回す。**差分が「今日の行だけ」であることを目で確かめる。

- **回名に「ボタニカル」が付いていても、出店者一覧が公開されているなら数える（2026-09-07）。**
  `undisclosedBreakdown` は**内訳が非公開で比率を数えられない**ときの逃げ道であって、
  「名称に植物語が入っていれば数えなくてよい」という規則ではない。
  トハメルカド境赤レンガ倉庫の第15回はテーマ名が「ボタニカル × オータムフェス」で、
  主催も株式会社多肉永遠(多肉の会社)。名称だけを見れば掲載相当に読める。
  ところが主催公式の**出店者紹介ページに63店舗の内訳が出ており、植物を売るのは
  主催を含めて5店ほど(約8%)**だった。残りはハンドメイド雑貨・飲食・整体・占い・
  ヒーリングで、主催自身が募集要項に「体験・ワークショップを**主役**として募集します」と
  書いている。総合マルシェが回ごとに植物テーマを付けるだけで通ってしまうので、
  **裏取りで主催公式を開いたら、出店者ページまで1階層見て内訳の有無を確かめる。**
  規則は `listing-policy.json` の `undisclosedBreakdown.breakdownPublished`。
  （§3 の「裏取りは会場のイベント一覧まで開く」と同じ動きで、こちらは出店者一覧側）

- **`manual-sweeps.json` に PUKUBOOK を足した（2026-09-07）。**
  プレイブック §3 には 2026-08-12 から「`pukubook.jp/events/` の一覧を必ず1回読む」と
  書いてあるのに、**回ったかを残す場所が無かった。**
  09-06 に NextMeet とまとめブログを台帳に載せたとき、3社目だけ漏れていた。
  今日の巡回で THE BOTANICAL SHOW 6th・トハメルカド境赤レンガ倉庫・
  アジア有用植物祭は pukubook にだけ出ていた(前2つは LEAFLA の45日窓の外)。
  `manual_sweep_stale` は `sweeps` の各項目を総なめするので、
  **エントリを足すだけで検査は効く。コードは触らなくてよい。**

- **「日付未確定で見送り」は、確定した日に見送り記録ごと消す（2026-09-07）。**
  `roots-and-sun-esaka-2026` は 08-12 に「主催が『2026年10月開催』とだけ言っていて
  日付未確定」として `unverified` / `revisit=true` で落としてあった。
  今日 主催の出店者募集投稿で 10月10日と確定したので掲載したが、
  **見送り記録を残したままだと `rejected_revisit_expired` が開催日の翌日に偽 urgent を出す。**
  09-05 に「見送り記録は、後から掲載しても消えない」で `rejected_but_listed` を直したのと同じ穴を、
  今度は**入れる側で塞ぐ**。掲載したらその場で `rejected-events.json` から抜く。
  照合の賢さに頼るより、二重に持たないほうが確実。

- **告知の日付と曜日が食い違ったら、曜日ではなく日付を疑う前に別の投稿で突き合わせる（2026-09-07）。**
  KUSABI の出店者募集投稿は「📅開催日：10月10日（日）」だが、2026-10-10 は土曜。
  同じアカウントの別投稿に「10月10日(土)に開催予定です」とあり、
  出店者側の告知も揃って「10月10日」だったので、括弧の曜日が誤記と確定した。
  **どちらかを推測で採らない。**主催の別投稿か出店者の告知で日付のほうを裏付ける。
  逆に曜日が正しくて日付が誤記の回もありうるので、当たるのは常に2つ目の情報源。

- 挿入系スクリプトは冪等に（除去→再挿入）。過去に calendar/map が4.2MBまで肥大した事故あり

- **取りこぼしの裏取りは、その会場のイベント一覧まで開く（2026-09-05）。**
  `coverage-gaps` の「島根サボテン・多肉の会 2026秋の展示会」を確かめるために
  しまね花の郷の `/event/` を開いたら、同じ一覧に**未掲載の「俺の！プランツ・コレクション！！」
  (9/19-21・多肉植物/サボテン/食虫植物/コーデックス・販売あり)が並んでいた**。
  この回はアグリゲータ3社にも coverage-sweep にも出ていない。
  会場公式にしか出ない大型イベントがある話は §3 に既に書いてあるが、
  **巡回先として会場公式を回るのは高くつく。** 一方、裏取りは必ず会場公式か主催公式を開くので、
  そのとき一覧まで1階層上がるのは追加コストがほぼゼロで、同じ会場の他の回を全部見られる。
  1件の裏取りが、その会場の全期間のスイープになる。**詳細頁で満足して戻らないこと。**

- **二重登録は、表記体系が違うと名前照合と会場照合が同時に外れる（2026-09-05）。**
  `narabikakufes-vol2-2026`(NARABIKAKUFES vol.2 / 奈良市役所 芝生広場) と
  `nara-bikaku-fes-vol2-2026-10`(ナラビカクフェス Vol.2 / 奈良市役所**前** 芝生広場) が
  同日・同県・同じIG出典で並んでいた。ローマ字とカタカナは NFKC で正規化しても一致せず、
  会場は「前」の1字違いで包含判定も外れる。`duplicate_event_entry` は
  名前の正規化一致・包含と会場一致しか見ていないので、**両方の経路が同時に死ぬ**。
  実害は表示の重複だけではない。入場料が **3,300円 と 入場無料 で食い違って**おり、
  古い側は自分の説明文に「入場無料」と書きながら `admission` に 3,300円 を持っていた
  （自己矛盾していたので、そちらが誤り）。両方とも Google にindexされていた。
  検査は `duplicate_event_same_source`(info)。**出典URLは表記体系に依存しない**ので、
  同日 + 同じ出典URL で拾う。同じ主催が同じ会場で併催する別イベントは正常に出る
  （天下一植物界 と BORDER BREAK!! が `no1plantae.com` を共有する組が実例）ので
  ゼロにはならない。だから urgent にはしない。
  **正規化で吸収できない差は、正規化しない値で照合する。**

- **同じ規則の写しは、直した側だけが賢くなる。今度は本文が取り残されていた（2026-09-05）。**
  `build-detail-pages.py` は入場料が無料かの判定を2か所に持っている。
  FAQ側(1050行)は `admission == '入場無料'` の完全一致に直してあったが、
  本文の要約(1131行)は素の `'無料' in admission` のままだった。
  そのため**有料の回が本文で「入場は無料です。」と名乗り、
  同じ頁のスペック表には正しい金額が出ている**状態が9件あった。
  「入園料 大人250円・小中高130円・未就学児無料」「500円（高校生以下は無料）」
  「前売600円／当日800円（中学生以下無料）」のように、**但し書きの「無料」に引っかかる。**
  コウレプ・オキボタ MAX のような有料の大型回も含まれていた。
  判定は `sitelib.admission_is_free()` に集約した。「無料」を含み、かつ
  金額・チケット制・有料・前売を示す語を一切含まないときだけ無料と見なす。
  検査は `admission_free_mismatch`(urgent)で、値ではなく**生成された頁を読む**。
  `sitelib_rule_duplicated` / `desc_min_chars_drift` と同じ型で、これで3例目。
  **同じ判断を2か所に書いたら、その場で片方を関数にする。**
  直すときは、直す側と同じ判断をしている行を先に grep する。

- **Googleの知識パネルの入場料・営業情報を出典にしない（2026-09-05）。**
  しまね花の郷は知識パネルが「入場料 無料」と出すが、公式の `/guidance/` は
  **入園料 大人250円・小人130円・未就学児無料**。知識パネルを信じていれば
  「入場無料」と書いた頁を出すところだった。会場の料金は必ず公式の利用案内を開く。
  住所と営業時間は一致していたので、**同じパネルの中でも項目によって当たり外れがある。**

- **文言を1つだけ見張る検査は、その文言を直した瞬間に盲目になる（2026-09-05 後続）。**
  同日午前の `agave-event-update` が「有料の回が本文で入場無料を名乗る」9件を直し、
  検査 `admission_free_mismatch` を足した。だが検査が見ていたのは
  **直した文言そのもの1つ(`入場は無料です。`)だけ**で、`build-detail-pages.py` には
  同じ判断があと4か所あった。結果、tips の
  **「入場無料のイベントです。」は同じ9件で出続けており、修正後の頁でも生きていた。**
  JSON-LD の `offers` も素の判定のままで、`一般入場無料（先行入場はチケット制）` の回が
  **`price="0"` を申告し、リッチリザルトが有料イベントを無料と出していた**
  (`botanicbomb-vol11-fukuchiyama-2026-10`)。検査は0を返し続けていた。
  対処は3つ。(1) 無料を主張しうる文言を集合で持つ (2) 同じ検査で価格の申告も見る
  (3) **書き方そのものを止める** — `inline_rule_reimplementation`(urgent) が
  AST で `'無料' in ...` を拾う。`sitelib_rule_duplicated` は同名の def / 定数しか
  見ないので、**式のまま埋まった再実装は名前を持たず素通りする**。それが4か所に
  散った理由で、規則を足す表 `_INLINE_RULES` に1行足せば次の規則も同じ形で拾える。
  **「同じ判断をしている行を先に grep する」は前日に書いたばかりで、守られなかった。**
  grep は書き方が揃っていることが前提で、`'無料' in admission` と
  `'無料' in adm` は同じ grep に出ない。人の grep ではなく検査にする。

- **生成物の集合を照合する検査は、頁の種類を1つずつ足していると必ず取り残す（2026-09-05）。**
  同じ穴を塞ぐのが3度目になった。index.html に `index_card_drift`(08-24)、
  同じ作り方の calendar/map に `embedded_event_set_drift`(08-27)、そして
  **`/tag` `/pref` `/region` `/archive` の88頁はどちらの母集団にも入っていなかった。**
  この88頁は sitemap 掲載・index 対象で、県別・タグ別の主要な入口である。
  1頁でも集合がずれると、その県から見た人にはそのイベントが存在しない。
  検査は `landing_event_set_drift`(urgent)。選定規則は写しではなく、
  tag=そのタグの全件 / pref=その県の全件 / region=その地方の全件 /
  archive/YYYY-MM=開始月 / archive/YYYY=開始年で events.json から一意に決まる。
  **「この頁にも同じ検査が要るのでは」を、足した日にその場で全部数えること。**
  生成物の一覧は `build-all.sh` が持っている。そこに出てくる出力先を順に当てれば漏れない。

- **repo のスクリプトを直しても、貼らなければ実機は変わらない。「resolved」にした日と、外部側が変わった日は別（2026-09-06）。**
  Apps Script のプロジェクト一覧で「agave-navi フォーム→GitHub連携」の**最終更新が 2026/08/24 のまま**だった。
  repo の `scripts/google-apps-script.js` は 08-31(`dcb424c9` sheetRows を書く)と
  09-01(`05a06026` 氏名・メールを公開経路に通さない)に直っているのに、**どちらも貼られていない。**
  裏付けは2つあり、日付だけの推測ではない。
  (1) 08-31 の GAS 書き込み `9bf760e8` は氏名とメールを含み、`sheetRows` を書いていない
  (2) プロジェクトの最終更新日が repo の修正日より前
  実害は2つ。
  (a) **次の送信でまた氏名とメールアドレスが公開URLと公開コミット履歴を通る。**
  `published_pii` は通った**後**にしか鳴らない。
  (b) `sheetRows` / `sheetCheckedOn` を GAS が書かないので、`inquiry_sheet_row_mismatch` は
  誰も更新しない固定値を照合し続ける。**5日間、誰も気づかなかった。**
  それでも `pending-judgments.json` では 09-01 に `resolved` に移されており、
  「Apps Script の貼り直しが済むまで旧仕様のまま」という但し書きが `note` に残っているだけだった。
  **但し書きが残っている項目は resolved ではない。** 但し書きに書ける程度に条件が残っているなら、
  それは未解決を散文で表現しているだけで、読むコードが無い以上、誰の目にも入らない。
  対処: `scripts/google-apps-script.js` の `CONFIG.SCRIPT_VERSION` と、
  `putFile` が毎回書く `new-inquiries.json` の `gasVersion` を突き合わせる
  `gas_script_undeployed`(urgent) を足した。貼るまで鳴り続ける。
  規則は `listing-policy.json` の `inquiryPii.deployment`。
  **外部システムに依存する対処は、repo を直した日ではなく外部側を確認した日で閉じる。**

- **「読む側を GAS に寄せる」は、GAS が旧版なら誰も書かないことになる（2026-09-06）。**
  09-01 に `sheetRows` / `sheetCheckedOn` を「タスクが数える」から「GASが書く」へ移したが、
  その `countSheetRows` を持つ版が**実機に入っていなかった**ので、以後どちらも一度も更新されていない。
  `inquiry_sheet_row_mismatch` は数字の整合しか見ないため、固定値のままでも通る。
  しかも移行時に手で `sheetCheckedOn=2026-09-01` を入れたせいで、
  唯一の手掛かりだった `sheetCheckedOn < lastChecked`(08-31) が**成立しなくなっていた**。
  **設計変更のときに手で入れた値が、その設計が働いていない証拠を消していた。**
  対処: `sheet_measurement_stale`(urgent) を足した。実測日が14日以上動かなければ鳴る。
  値の整合だけでなく、**値が古びること自体**を見る検査が要る。

- **回答シートは Claude in Chrome からなら読める。組み込みブラウザで読めないだけ（2026-09-06 訂正）。**
  09-01 に「このタスクからシートを読む手段は無い」と書いたが、これは**組み込みブラウザに限った話**。
  Chrome拡張(Claude in Chrome)は実Chromeなので個人アカウントでログイン済みで、
  スプレッドシートを開いて同一オリジンで
  `fetch('/spreadsheets/d/1iTWAAbd5FV4NkNyt186H8wR6KqTPOLcFWSvHghZMDvI/gviz/tq?tqx=out:csv',{credentials:'include'})`
  を叩けば全行取れる（2026-09-06 実測: status 200・データ行3）。
  **CSVは素朴に改行で切らないこと。** `body` 欄が複数行なので、引用符の中の改行を数えると
  住所の行(`〒460-0008`)がデータ行に化ける。データ行の判定は1列目が
  `^\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{2}:\d{2}$` に一致する行だけを数える。
  **戻り値に氏名・メールを含めない。** 列は タイムスタンプ / メールアドレス / お名前 /
  お問い合わせ種別 / イベント概要 / イベント名 の順で、2・3列目が連絡先。
  数えたら `sheetRows` / `sheetCheckedOn` に書いて push する。読めなかった回は日付を進めない。

- **Googleアカウントの `/u/N` は入れ替わる。番号ではなくページ上のメールアドレスで確かめる（2026-09-06）。**
  08-30 は個人アカウントが `/u/1/` だったが、**今日は `/u/0/` が個人 `yuji.mezaki@gmail.com`、
  `/u/1/` が仕事用(Gantt chart が並ぶ)、`/u/2/` が royalhoneystore** だった。
  プレイブックに「`/u/1/` を見る」と書いてあると、そのまま読んで
  「トリガーが消えた」と誤判定する(`/u/1/` は仕事用なので agave-navi の行が出ない)。
  当てずっぽうで番号を回す必要は無い。**ページ上の Google アカウントボタンから直接読める。**
  `[...document.querySelectorAll('[aria-label]')].map(e=>e.getAttribute('aria-label')).filter(s=>s&&s.includes('@'))`
  が `Google アカウント: Yuji Mezaki (yuji.mezaki@gmail.com)` を返す。
  **番号を固定で信用せず、開いた画面のアカウントを毎回読んでから判定する。**

- **フォーム→GAS→push→メールは、端から端まで通った実績がある（2026-09-06 確認）。**
  08-25 に「疎通は `testConnection` の手動実行だけで、実フォーム送信では一度も通っていない」と
  書いたが、その後 08-31 に実際に通っている。トリガー画面の「前回の実行」が
  **2026/08/31 12:41:02**、コミット `9bf760e8` が **12:41:03**、エラー率 0%。
  **この不確かさはもう抱えなくてよい。**残っている不確かさは版数のほう(上記)。

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

**2026-09-07 の週次点検の記録。**
`task_run_gap` は 09-03 / 09-04 の2日を出しているが、**3タスク全部が同じ2日を落としている**
（`agave-event-update` / `event-monitor` / `event-listing-review`）。
1タスクだけが抜けたなら、そのタスクの不具合か許可待ちを疑う。
**全タスクが同じ日に揃って抜けたときは、repo 側にも各タスク側にも原因は無い。**
09-02 と 09-05 は3タスクとも記録があり、CI(daily / health)は 09-03 も 09-04 も
`schedule` で成功しているので、落ちているのは手元の実行環境だけ。
（`audit-history.json` の 09-03 / 09-04 の行も CI が正常に書いている）
**この形の抜けを毎週「原因不明」と書き直さないこと。**
台帳を見て「全タスク同日」ならその1行で閉じてよい。1タスクだけなら追う。
`task_run_gap` を「全滅した日」と「1タスクだけ抜けた日」に割るのは、
標本がもう1回出たら検討する（今は09-03/09-04の1例だけで、
分けた検査が誤検知しない閾値を決められない）。

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
