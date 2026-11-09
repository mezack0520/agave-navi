# タスク運用プレイブック

定期タスクと会話のセッションが共通で使う運用手順。
タスクは自分のプロンプトを編集できないので、運用の知識はプロンプトではなくこのファイルに書く。
**タスク自身がこのファイルを更新してよい。**書き方は §4 に従う。

2026-11-08 に話題別に書き直した。
それまでの全文と経緯は `git show 79e146e491f1:docs/task-playbook.md` で読める。
手順として読むのはこのファイルだけにする。

---

## 1. 起動時の手順

1. **実行環境。**定期タスクはクラウドのスケジュール済みタスクで、PC の device_bash と組み込みブラウザを使う。
   フォルダ mzplants はタスクに付けてある(device_bash では `$HOME/mnt/mzplants`)。
   見えない回は `device_request_folder_access` を1回だけ試し、通らなければその旨をレポートに書いて終える。
   ブラウザは組み込みブラウザ(`mcp__remote-devices__Claude_Browser__*`)だけを使い、Claude in Chrome は使わない。
   Chrome は2台つながっていて、無人の実行では選べない。
   git の clone、commit、push は device_bash で行う。クラウドのコンテナからの push は 403 になる。

2. **clone 先は毎回一意なディレクトリにする。**
   ```
   D=$(mktemp -d -p /tmp) && git clone https://github.com/mezack0520/agave-navi.git "$D/agave-navi"
   ```
   - 公開リポジトリなので clone に PAT は要らない。PAT を使うのは push だけ。
   - 名義は `mezack0520 <88774621+mezack0520@users.noreply.github.com>`。
     手順5の `record-run.py` が repo に設定するので、それより前にコミットしない。
   - `/tmp` 直下の固定名(`/tmp/agave-navi`、`/tmp/audit_out.txt` など)は前のセッションの残骸で書けないことがある。
     作業ファイルも `$D` の中に置く。
   - PAT(`agave-navi\github.pat`)を読む操作は、自動モードの分類器に止められることがある。
     止められたら別の読み方を試さない。push の要らない作業(監査、レポート)は最後までやり、
     変更は `git diff` で `work\<taskId>_<日付>.patch` に残し、レポートの先頭に「push できず。PAT の使用を止められた」と書く。
     会話のセッションがそのパッチを当てて push する。
   - 終わったら clone を消す。push が通ったこと(`git fetch` 後の `git status -sb` が ahead 0)を確かめてから、
     clone したときに出たパスをそのまま書いて `cd / && rm -rf /tmp/tmp.XXXXXXXX` を実行し、`ls` で消えたのを確かめる。
     シェルの変数は次の呼び出しに残らないので、`rm -rf "$D"` は何も消さずに終わる。
     レポートに「clone 削除済み」と書く。push できなかった回は消さず、パスと理由をレポートに書く。

3. このファイル、`listing-policy.json`、`docs/architecture-2026-07.md` の §1〜§7 を読む。architecture の §8 は経緯なので、要るときだけ読む。

4. プロンプトとこのファイルが食い違えば、このファイルが正。

5. **起動直後に `python3 scripts/record-run.py <taskId>` を実行し、その変更を含めて push する。**
   - 台帳に起動日(JST)が入る。台帳は `task-runs.json`、event-listing-review だけは `new-inquiries.json` の `reviewedOn` と `reviewedHistory`。冪等なので何度呼んでもよい。
   - `<taskId>` は `agave-event-update`、`event-monitor`、`site-health-check`、`event-listing-review`、`agave-navi-eyecatch`。
   - 終わりではなく最初に書く。成果物が無い回は push されないので、終わりに書く設計だと記録だけが落ちる。
     完走したかどうかは成果物とレポートで分かる。
   - 実行レポートは、record-run.py が出す行(`実行レポート: task-reports/<taskId>_<日付>.md`)の名前のまま保存して push する。
     日付は JST。実行環境の `date` は UTC なので、朝9時前は前日になる。
   - プロンプトにはこの2つ(record-run.py の行とレポートの保存)が要る。無いタスクは監査 `task_run_never_recorded` に出る。

6. **shell が起動しない回は、起動記録を `work\task-runs-unpushed.json` に残す。**
   形は `{"runs": [{"taskId": ..., "date": ...}]}`。次に push できた回が最初に流し込む。
   ```
   python3 scripts/record-run.py --flush-worklog "<mzplants>/agave-navi/work/task-runs-unpushed.json"
   ```
   台帳に入った項目だけが `runs` から消える。転記の漏れを探すときは `task-reports/` のファイル名を起点にする。

7. **スケジュール済みタスクとプロンプト。**
   - 定期タスクは claude-code-remote の trigger で、`list_triggers` で一覧と最後の実行が見える。時刻は architecture §2。
   - どれも「このPCが必要」で動いている。フォルダはタスクの編集画面でしか付けられない。
     プロンプトの変更は、その PC につながった Cowork の会話で目崎が `update_trigger` を承認したときだけ効く。
     それ以外は `needs_device_approval` が返り、何も変わらない。
     作り直し(`create_trigger`)はしない。PC の承認が無いとクラウド専用になり、PC にもフォルダにも届かない。
   - プロンプトに置くのは起動の手順(clone の場所、record-run.py、このファイルを読む)だけにする。手順と規則はこのファイルに書く。
   - 変えたいプロンプトは `pending-judgments.json` に提案として積む(対象のタスクと、置換前 → 置換後)。
     目崎が承認すると `approvedOn` が付き、日次メールに出る。当てるのは会話のセッション。
     現行の本文に差分だけを当てて `update_trigger` し、承認されたら `list_triggers` で指定の箇所だけ変わったのを確かめ、
     `resolved` に移して push する。**定期実行はプロンプトを書き換えない。**
   - 台帳に taskId を足したら、同じ回にそのタスクのプロンプトへ record-run.py の行を入れる提案を積む。
   - 動いたかどうかは成果物で見る。`last_run` の SUCCEEDED は会話が終わったことしか示さない。
     台帳に抜けがあれば、`task-reports/<taskId>_<日付>.md`、`git log` の成果物のコミット、`list_triggers` の順に見る。
     レポートがあれば記録の問題、コミットがあれば動いている、どちらも無ければタスクが止まっている。
   - 全タスクが同じ日に揃って抜けたのは PC 側の停止で、repo にもタスクにも原因は無い(監査 `pc_tasks_all_stopped`)。
     1タスクだけの抜けを追う。

8. **日次メールに出る項目は、報告する前に直す。**手順は「日次メールの項目は、報告する前に直す」の節。

置き場(mzplants は `C:\Users\yujim\iCloudDrive\Claude\Projects\mzplants`):
- PAT: `mzplants\agave-navi\github.pat`
- 受け渡し(repo の外): `mzplants\agave-navi\work\`
- 実行レポート: repo の `task-reports/<taskId>_YYYY-MM-DD.md`

---

## 1.5 どこから何に届くか

| | device_bash(PC) | クラウドのコンテナ |
|---|---|---|
| github.com | clone、push とも通る。push は PAT | clone は通る。push は 403(プロキシ) |
| api.github.com | 通る。ジョブのログは PAT 付きで取る | 不通 |
| agave-navi.com | 通る | 通る |
| Instagram の画像(CDN の署名付き URL) | 未確認 | curl で取れる |
| 画像や PDF を目で見る(Read) | できない | `device_stage_files` で取り込めばできる |

Instagram の本文とプロフィールは組み込みブラウザで読む(§3.6)。
到達性は変わる。「不通」と書いてあっても、まず1回叩いて確かめる。

**会話のセッションから push する手順。**
1. クラウドの clone でコミットし、`git format-patch -1 --stdout` を `/mnt/user-data/outputs/<毎回違う名前>.patch` に書く。
   `device_commit_files` は同じ `stagedPath` を2回送ると最初の中身を書くので、名前は毎回変える。
2. `device_commit_files` で `mzplants\agave-navi\work\_transfer.patch` に置き、両側の sha256 を突き合わせる。
   パッチの中身を device_bash のコマンド文字列に写さない。写すと内容が変わる。
3. device_bash で `/tmp` に新しく clone し、名義を設定して `git am --3way` で当て、PAT で push する。
   拒否されたら `git pull --rebase` して押し直す。
4. 押したら §2 のとおり CI の結果を見る。

タスクが残したパッチ(`work\<taskId>_<日付>.patch`)は、作られた時点の土台の写しになっている。
`git apply --include=<手で直したソースとデータ>` で必要なファイルだけを当て、生成物と運ぶデータ(`task-runs.json`、`auto-fix-log.json`、`mail-request.json`、`audit-*.json`)は取り込まずに作り直す。
push できなかった日の起動日は、パッチを当てた回が `task-runs.json` の history に足す。

---

## 2. 書き込み手順

- 名義は `mezack0520 <88774621+mezack0520@users.noreply.github.com>`。
- push は PAT(`mzplants\agave-navi\github.pat`)で行う。PAT の値は出力、ログ、レポートに残さない。
  401 なら再発行が要る旨を `pending-judgments.json` に積んで終える。PAT は `.github/workflows/` も push できる。
- ワークフローは push で起こす。`workflow_dispatch` と `repository_dispatch` は PAT でも 403。
  朝の巡回(`crawl-request.json`)と日次メール(`mail-request.json`)の合図は `scripts/request-run.py` が書き、
  週次エンリッチは `enrich-request.json` の push で起きる。
  CI が `GITHUB_TOKEN` で押したコミットはワークフローを起こさないので、ループしない。
- 新しい回は `new-events.json` に書き、sync-events が取り込む。既存の回は `events.json` を直接直す。
  `new-events.json` に既存の slug を入れると sanity-check が黙って落とし、ワークフローは成功で終わる。
- `events.json` と `new-events.json` を同じ push に入れない。daily と sync-events が同時に走り、片方が cancelled になるか衝突する。
  押す前に、データを書くワークフロー(daily、sync-events、health)が走っていないことを確かめる。
  daily、health、週次は同じ concurrency group で、待ちは1本しか置けない。
- 生成物(`scripts/ci-generated-paths.txt` に並ぶもの)の中身は手で直さず、`bash scripts/build-all.sh` で作り直す。
  rebase で衝突したら、衝突したのが生成物だけかを `git diff --name-only --diff-filter=U` で確かめてから、生成物は捨てて作り直す。
  ソースが衝突していたら中身を見て解く。
- repo は public で、監査結果も公開される。氏名、メールアドレス、トークンを書かない。
- JSON はファイルごとにインデント(1か2)と末尾改行が違う。元の書式で書き戻し、`git diff --stat` で差分が自分の変更だけかを見る。
- 手元で `audit.py` を回したら、`audit-results.json` と `audit-history.json` を `git checkout` で戻してからコミットする。結果は CI が書く。
  その日の daily(status の更新と再生成)が入る前に回すと、暦で決まる検査(`status_date_mismatch`、`index_card_drift` など)が
  前日に終わった回の数だけ出る。結果は daily を pull してから読む。
- 押したら結果を確かめる。CI は device_bash から api.github.com で見る。一覧とジョブ一覧は無認証、ログは PAT 付き。
  ```
  curl -s "https://api.github.com/repos/mezack0520/agave-navi/actions/runs?per_page=20"
  curl -s "https://api.github.com/repos/mezack0520/agave-navi/actions/runs/<id>/jobs"
  curl -s -L -H "Authorization: Bearer $PAT" "https://api.github.com/repos/mezack0520/agave-navi/actions/jobs/<id>/logs"
  ```
  本番は `agave-navi.com` に一意なクエリ(`?cb=<日付>`)を付けて読む。
  `raw.githubusercontent.com` と web_fetch は URL ごとに古い版を返すことがある。

---

## 日次メールの項目は、報告する前に直す

目崎の指示(2026-09-29)は「積み残し、異常あり、他所に出ていて当サイトに無いイベントは、報告だけでなくそのまま直して、その結果を報告する」。
メールは「判断が必要なこと」「サイトに反映したこと」「タスクが直せずに残っていること」だけを載せ、どれも無い日は送らない(`build-health-mail.py` の冒頭)。
掲載は events.json の差分から出るが、修正は `log-fix.py` の記録からしか出ない。

### 誰がいつ

- 時刻は architecture §2。メールは9時までに届く。
- **`agave-event-update`(07:00)が主担当。**本業(巡回と掲載)の後に、下の表を上から処理する。
  その日の巡回結果は、最初のタスク(06:30 `event-listing-review`)の起動記録が出す合図(`crawl-request.json`)で 06:3x に出ている。
- `event-monitor`(08:15)は残りを拾う。朝の回が届かなかった分と、朝以降に出た分。
- **メールは `event-monitor` の最後に送る。**直し終えたら `python3 scripts/request-run.py mail --task event-monitor` で
  `mail-request.json` を書き、他の変更と一緒に push する。health.yml が作り直して監査し直し、メールを送る(約10分)。
  忘れるとその日のメールは昼の保険(schedule)まで出ない。
- 始める前に `python3 scripts/audit.py` と `python3 scripts/build-health-mail.py` で今日のメールに出る予定の一覧を作り、それを処理の入力にする。
  手元の audit に出る生成物の古さ(直した回の `index_card_body_drift` など)はメールに出ない。
- event-monitor が直せずブラウザが要る項目は `log-fix.py --kind needs_browser --action skipped` で渡す。
  `--detail` は「ブラウザ要: 何をどこで確かめるか」。agave-event-update は本業の前に
  `python3 scripts/log-fix.py --open --kind needs_browser` を見て拾い、片づけたら同じ kind と target で fixed か reviewed を書く。
  event-monitor のレポートの「未対応」は翌朝のタスクに届かない。

### 何をどう直すか

| メールの項目(監査のキー) | 直し方 | log-fix の action |
|---|---|---|
| 他所に出ていて当サイトに無い(`coverage_gaps`) | 主催の一次情報で裏取り。載せる回は `new-events.json`、載せない回は `rejected-events.json`(listing-policy の規則どおり) | listed / rejected |
| 主催の投稿に当サイトに無い日付(`organizer_unlisted_dates`) | 同上。ワークショップ単独などは workshopOnly で見送り。主催の日程変更なら既存の回を直す(§3.8) | listed / rejected / fixed |
| 中止・延期の兆候(`organizer_cancel_signal` / `cancel_suspects`) | 投稿と公式頁を開く(§3.8)。中止なら cancelled にする。違えば `scripts/cancel-reviewed.json` | fixed / reviewed |
| 再評価待ちの見送りが開催日を過ぎた(`rejected_revisit_expired`) | `revisit=false` にして理由に一文足す | fixed |
| 再評価待ちの見送りが開催10日前を切ったのに見ていない(`rejected_revisit_due`) | 保留の理由に書いた一次情報(出店者の一覧、施設の告知)が出ていないかを見て、掲載するか見送りを確定する。出店者の一覧が出ていれば数える(breakdownPublished)。決められなければ `revisitedOn` に実行日、理由の末尾に見たことを一文 | listed / rejected / reviewed |
| アイキャッチ候補(`eyecatch_candidates_pending`) | 画像を Read で見て `apply-eyecatch.py` で採否(§3.7) | fixed |
| 内容の異常(`content_implausible` / `time_vs_organizer_post` / `time_vs_description` / `time_implausible`) | 主催の告知で確かめて直す。出典に無い値は消す。入場料に出店料や貸しスペース料が入る例が繰り返し出ている | fixed |
| 主催の最新の告知と会期が1〜3日ずれる(`organizer_post_span_differs`、info) | 主催が会期を動かしたのか、上位の催しや別の回の会期なのかを投稿で見る。動かしたなら date / dateEnd / dateDisplay、説明文の会期、出典を直す | fixed / reviewed |
| 会期と説明文の食い違い(`desc_span_mismatch` / `desc_date_mismatch`) | 出典で会期を確かめ、日付欄か説明文を直す。daily の日付照合が書いた日付なら `git log -G` で書き換えたコミットを引き、元の値と比べる | fixed |
| 説明文が「未発表・告知待ち」と書く項目に値がある(`desc_claims_unannounced`) | 値の出所を確かめる。出典の告知にあれば説明文の一文を消し、無ければ値を消す。enrich が一覧の頁から別の回の値を拾っていないかをログの `Found:` で見る | fixed |
| 終わった回に「未定」などの仮置きの値(`past_placeholder_value`) | 出典に実際の値があれば入れ、無ければキーごと消す。会場は表示側が「記録なし」に落とすので対象外 | fixed |
| 説明文が会場を別の県の施設として書く(`desc_venue_other_prefecture`) | 主催の告知で所在地を確かめ、説明文を location の住所どおりに直す。location / prefecture が違っていればそちらを直す | fixed |
| 埋め込みやアイキャッチが前の回の投稿(`instagram_post_predates_edition`) | instagramPostId / instagramUrl なら外す。imageSource なら imageUrl と画像も外して `image-rejected.json` に記録し、この回の告知を主催の投稿で探し直す | fixed |
| 同じシリーズの回で名称の表記が割れている(`series_name_variant`) | 主催の告知の表記に揃え、使わなくなった表記は aliases に残す。本当に別のイベントなら名前で区別が付くようにする | fixed |
| リンク切れ(開催前の回) | まず手元から HEAD と GET で引き直す。CI にだけ 204 や 429 を返す相手があり、生きていれば reviewed。切れていれば主催の新しい告知 URL に差し替える。サイトのトップも休止やメンテナンスの頁なら、主催の Instagram を url と organizerIg に入れ、画像がその告知頁のものなら告知頁を imageSource に残す。見つからなければ skipped に理由 | fixed / reviewed / skipped |
| 詳細未定(TBD) | 主催の最新告知を見て、出ていれば埋めて `eventStatus` を外す | fixed / skipped |
| 手でやる巡回が止まっている(`manual_sweep_stale`) | その巡回をやり、`manual-sweeps.json` を更新(§3.1) | fixed |
| 参考値が急に動いた(`metric_moved`) | 項目に出た内訳を見る(§3.12)。upcoming_no_image は新規掲載と外した画像を引いた残りで鳴るので、addedDate が前回より前で画像の無い開催予定を `git diff` で探す。画像の消失なら event_image_lost も鳴り、鳴らなければ日付の更新で戻った回 | fixed / reviewed |
| その他の urgent | 監査の note のとおり直す | fixed / skipped |

```
python3 scripts/log-fix.py --task agave-event-update --kind coverage_gaps \
    --target "ボタの市 meets ビカク横丁 (2026-10-25)" --action listed \
    --detail "主催 @botanoichi の告知 Dds5U7DN2Vf で裏取り"
```

- 直せなかった項目は `skipped` に理由を書く。メールには出ないが、翌日のタスクが同じ調べ直しをしないための記録になる。
- `pending-judgments.json` に積むのは、listing-policy に規則が無い類型に出会ったときだけ。`doNotEscalate` の項目は積まない。
- `auto-fix-log.json` は CI が運ぶデータ(`audit._CI_CARRY_DATA`)。`log-fix.py` の変更も push に含める。push しない記録はメールに届かない。
- 合図を押した後は、health のログの `New events added` と本文を見る。`send=False` で終わっても workflow は緑になる。
  `mail-state.json` の `lastMailedOn` が今日でなければ送っていないので、その日に限り `mail-request.json` を押し直す。

---

## 3. 作業ごとの規則

規則のうちコードや監査が見張っているものは、ここではその場所を指すだけにする。

### 3.1 取りこぼしを探す(Step0)

- 機械の巡回は `scripts/coverage-sweep.py`(daily)。LEAFLA の日付別(先45日)、NextMeet の月別、まとめブログ、主催公式の一覧、PUKUBOOK を読み、
  events.json と rejected-events.json のどちらにも無い回を `coverage-gaps.json` に出す(日次メールの `coverage_gaps`)。
  `coverage_sweep_broken` が出ている日は、候補が0件でも取りこぼしなしの証拠にならない。巡回を先に直す。
  候補が出た理由や当たった相手は `python3 scripts/coverage-sweep.py --explain --days 1` で見られる。
- アグリゲータ3社(LEAFLA、NextMeet、PUKUBOOK)は互いに取りこぼす。
  会場公式のカレンダーにしか出ない大型の回もある(なばなの里、富山県中央植物園、京都パルスプラザの日本シャボテン大会)。
- `coverage-gaps.json` は巡回した時点の写しで、その後に載せた回は `coverage_gap_stale` に分かれる。
  掲載済みの回が候補に残り続けるなら、アグリゲータ側の呼び名を該当の回の `aliases` に足す。
  auto-fix-log に書くだけでは消えない(`coverage_gap_logged_but_open`)。
- `truncatedUnresolved`(途中で切れた見出し)は毎日1件ずつ既存に当てる。切れた見出しは範囲の判定にも同一の判定にも使えない。
- `manual-sweeps.json` は、自動巡回が読めなかった日に手で回した記録。回った日に `lastSweptOn`、`lastScope`、`history` を更新し、
  回れなかった日は進めない(`manual_sweep_stale`)。
- 主催の投稿は `ig-organizer-watch.py`(daily)が読み、`organizer-posts.json` に置く。
  CI の信号(`organizer_unlisted_dates`)は主催が自分の催しを告知した投稿しか数えないので、
  **朝のタスクは `python3 scripts/scan-organizer-posts.py` の一覧(約130行)を目で読む。**
  主催の告知と読めた行だけ開いて裏取りし、ワークショップ単独、値引きだけ、営業日の案内は見送りに記録する。記録した投稿は翌日から一覧に出ない。
- LEAFLA の新着は記事番号の連番で引ける(`/blogs/media/topics<番号>`)。leaf-laboratory.com のタブから前回の右端 +150 まで1件ずつ fetch する。
  並列にすると 429 で塞がる。最後の番号が 200 なら +50 ずつ伸ばし、404 が10件続いたら止める。
  h1、開催情報の表、参考サイト欄の IG 投稿を抜けば開かずに選別できる。見た右端をレポートに書く。
- Google 検索は、google.com を開いたタブの javascript から `/search?hl=ja&tbs=qdr:w2&num=20&q=...` を fetch し、DOMParser で `a h3` を拾う。
  1回の起動で30本前後が上限(間隔1.5〜2秒)。リダイレクトの頁になったら google.com へ1回 navigate し直すと戻る。
  空の頁や CAPTCHA が出たら打ち切る。CAPTCHA は解かない。
  Instagram のタブからは google.com を fetch できない(CORS)。WebSearch では Instagram の告知はほぼ拾えない。
- 検索のスニペットは、別の投稿のキャプションや別の出店者の予定表を混ぜて出す。知識パネルの入場料と営業情報は出典にしない。
- 主催が personal の回はブラウザで回る(§3.6)。順番は前回のレポートから決めず、`revisit=true` の見送りの reason と name に出る handle のうち、
  personal のものと watch-sources に居ないものを先に回す。告知が出た主催に何日も届かなくなるため。
- 主催公式サイトの「イベント一覧」と、生産者が投稿の末尾に貼る「出店・販売会予定」は、1回で巡業ぶんが取れる。
  取りこぼしを裏取りするときは、会場のイベント一覧まで開く。
- 月別の巡回は当月から3か月先まで見る。主催はそのくらい前から告知する。
- 掲載済みの回の延期は、新しい回を探す検索語では拾えない。毎回1回 `多肉植物 OR アガベ イベント "中止" OR "延期" <対象月>` を検索する。
  主催の投稿に出たものは `organizer_post_span_differs` と `organizer_unlisted_dates` に出る。
- アグリゲータとまとめブログは出典に使えない(`blockedUrlDomains`)。拾ったら主催の告知で裏取りする。
  アグリゲータは中止や休会を反映せず、一行要約は参加条件(「即売会はありません」など)を落とす。
  LEAFLA の参考サイト欄の IG 投稿は、別のイベントを指していることがある。
- 一度も掲載したことのない主催は watch-sources に入らない。主催だと分かった handle は `watch-seeds.json` に足す(出店者の handle は足さない)。
  開いて存在しなかった handle は同じファイルの `deadHandles` に `checkedOn` 付きで足す。

### 3.2 載せる前の照合

- 既存とは slug、名称、aliases に加えて、日付と会場、主催IGの±45日、日付の重なりと県で当てる。
  アグリゲータは会場名やブランド名で名前を付けるので、名前だけでは当たらない。3字以下の短い名前も名前では当たらない。
- 見送り(`rejected-events.json`)にも当てる。理由が「回が無い」「休会」の記録に当たったら、会場公式か主催の一覧で、その日付に回があるかを確かめ直す。
- 略称や別名で当たったら、既存の回の `aliases` に足す。
- 同じ会場、同じ日に別の主催が並べて開く回は二重掲載ではない。主催と告知の投稿が別なら、併催として `coexistsWith` を書く。
- 2会場の回と巡業は、会場ごとに別の回にする。同じ name の開催予定が並ぶときは name に日か会場を足す(`same_name_upcoming`)。
- 載せたら、同じ回の見送り記録を消す(`rejected_but_listed`)。
- 1投稿から複数の回を立てたときと、会場の掲載が3件目になるときは、押す前にコピーした clone で merge と audit を回し、
  `duplicate_event_entry`、`venue_slug_romaji_candidates`、`time_vs_organizer_post` を見る。

### 3.3 載せるかの判断

- 掲載基準は `listing-policy.json` が正。ここには読み方の注意だけを書く。
- 出店者の告知は「主催は誰か」を書いている。`vendorAnnouncementsOnly` は、主催が別にいて出店者だけが告知している回の規則。
  **出店者の予定表でも、書いた本人がその回の主催なら一次情報。**行ごとに主催を引き直す。
  出店者が自分たちで開く合同の販売会は、出店者の告知が主催の告知になる。会場の投稿に別の主催(「主催者さん @…」)が出ていないかで決める。
- `vendorAnnouncementsOnly` で見送る前に、主催の handle を Instagram の topsearch で1回引く(§3.6)。自己紹介欄の告知も主催の告知として扱う。
- 主催の IG の投稿とプロフィールは、検索のスニペットで読めたものも一次情報。公式サイトが古いことを理由に unverified にしない。
- 作品展は、売るかどうかではなく、作品の主題が対象の植物そのものかで切る。
- 同じ主催が対象と対象外のジャンルの回を並行して開くことがある。「A × B」の併記は主題を言っていない。
  総合マルシェを回ごとに植物テーマで売る主催は、シリーズ単位で覚える。
- 出店者一覧が公開されていれば数える(`breakdownPublished`)。ジャンルは各出店者のプロフィールの自己紹介で数える。
  instagram.com のタブから `fetch('/<handle>/')` の `meta[name="description"]` で、1回の呼び出しで何件も読める。
- 範囲の判定に使うのは、回の主題を言っている文だけ。会場主催の頁の出店者紹介は、その店が普段扱う品目を書いていて、回の品目ではない。
- 主催の固定投稿は、投稿日が古くても本文が更新されていることがある。
- 主催が「◯/◯予定」と書いた自分の次回は、日付が出たものとして tbd で載せる。出店者の予定表に出た日付は `vendorAnnouncementsOnly` のまま。
- 搬入、設営、チケット発売、締切、ボランティアの作業日は開催日に数えない。日付の前後の見出しで、その日に何が起きるかを読む。
- 告知の日付と曜日が食い違ったら、別の投稿で突き合わせる。どちらかを推測で採らず、募集ポータルの日付でも埋めない。
- 出店者の「今後の出店予定」は前年の固定投稿のことがある。曜日で年を確かめる。
- 店の月例の案内の中に即売会の告知が紛れていることがある。個人主催のマルシェは、会場の施設の公式サイトに主催と出店者一覧が出ていることが多い。
- 見送りの記録:
  - `reasonType` は `_reasonTypes` の値(`policy`、`unverified`、`undisclosed`、`cancelled`)だけを使う。
  - name には県名まで書く。一般語1つだと掲載済みの回と衝突する。
  - `eventDate` は開始日。決定日を入れない。会期があれば `eventDateEnd` も書く。
  - 日付が未確定で見送った回は、日付が確定した日に記録ごと消して載せる。
  - 保留(`revisit=true`)は開催10日前に一度見て、掲載か見送りを確定する(`rejected_revisit_due`)。
    決められなければ `revisitedOn` と、理由の末尾に見たことを一文書く。開催日を過ぎたら `revisit=false`(`rejected_revisit_expired`)。
  - 会期の長い常設の掲載(PUKUBOOK の「注目イベント」など)は、1回の見送りでは毎回候補に出る。`listing-policy.json` の `precedents` に置く。
- 規則が無い類型に出会ったら `pending-judgments.json` に積み、`listing-policy.json` への追記案を添える。同じ問いを翌日も投げないため。

### 3.4 一次情報の読み方

- 頁の更新日や記事の投稿日を開始日として取り込まない。開始日を含む記事(`<article>` や本文の入れ物)だけを読む。
- 時刻:
  - 同じ日に複数の会場の時刻を並べた投稿は、その回の会場の見出しの行だけを比べる。巡業の日程の投稿は冒頭に別の催しの時刻を持つ。
  - 協賛やゲストの「来店予定」、施設の営業時間は、開催時間ではない。
  - 告知の日付の行は月を省くことがある。
  - time を直すときは、sourceUrl も時刻を書いた告知の投稿に替える。古い速報に紐づいたままだと照合が鳴り直す。
    `organizer-posts.json` は最新12件しか持たないので、時刻の食い違いは鳴った日に直す。
- 店や施設の投稿の末尾にある休館日や定休日の日付は、催しの日付ではない。
- 入場料: 出店料や貸しスペース料は入場料ではない。「最終日は入場無料」は入場無料ではない。
- 翌年の回に、今年の回の時間、入場料、フロアを写さない。先の回は、主催がその回について出した項目だけを書く。
- 出典を差し替えたら、time と admission を新しい出典で読み直す。
- 主催が告知を書き直していたら、最新の投稿に合わせる。
- PDF は文字にしてから読み、テキスト層が無ければ画像にして読む。日程がチラシの画像にしか無い告知は、画像を読む。
- SPA の公式サイトは curl では枠しか返らないので、web_fetch か組み込みブラウザで読む。
  Shift_JIS の頁は `iconv -f cp932 -t utf-8` で読む。証明書の中間が欠けた頁は CI からも web_fetch からも読めない(直す先は無い)。
- Threads の投稿は、組み込みブラウザで開くとタブの題名に全文が入る。

### 3.5 項目の書き方

- 項目の定義は `docs/event-data-prompt.md`。`events.json` にキーを足したら `audit.py` の `KNOWN_EVENT_FIELDS` にも足す(`unknown_event_fields`)。
- 値が無いならキーごと消す。null や空文字を入れない。開催前の回に「未定」を値として入れない。
- `location` は施設名と住所で書き、区画(「6号館D」「◯◯公園内」)まで書かない。区画まで書くと会場の頁が割れる(`venue_key_split`)。
  会場名が無く住所しか出さない主催には `venue` を作らない。`venue` の先頭に「会場：」のようなラベルを残さない。
- 会場の掲載が3件目になったら、同じ回で `_VENUE_ROMAJI_RAW` と `_VENUE_REDIRECTS_RAW` を足す。2件まではハッシュの URL のまま(`sitelib.VENUE_ROMAJI_MIN_EVENTS`)。
  足した直後は `venue_redirect_broken` が daily の再生成まで1件出る。
- `access` の出口名は、裏取りできなければ落として駅名だけ残す。
- `url` と `sourceUrl` はその回の告知頁にする。施設のトップ頁や一覧の頁にすると、daily の日付照合と enrich が別の回の日付や時刻を書く。
  1頁に複数の回が並ぶ頁なら `autoDateUpdate: false` を入れる(`shared_source_page_multi_date`)。
- `organizerIg` は handle だけを書く。@、URL、空白は入れない(`organizer_ig_format`)。
  **載せるときに主催の IG まで調べて入れる。**分からないと中止の告知を拾えない。無いと確かめた回は `organizerIgNone: true`(`organizer_ig_unknown`)。
  共催で施設が主催欄に並ぶ回は施設の IG を入れる。
- 告知か説明文に時刻があれば、載せるときに time を入れる。空のまま入れると `time_vs_description` が鳴る。
- 説明文は50字以上(`sitelib.DESC_MIN_CHARS`)。字数を埋めるために日時、会場、入場料を書き足さない。スペック表に出ている。
  足すのは出店数、扱う植物のジャンル、企画。「次回開催」の年は書かない。所在地の語は location の住所から写し、会期は日付欄と揃える。
- `merge-new-events.py` が新規の status、eventStatus、addedDate、updatedAt を埋める。既存の回を直したら `updatedAt` を今日にする。
  updatedAt が14日以内の回は enrich が説明文を上書きしない。
- 日程が変わった回は slug を変えない。`eventStatus` を `rescheduled`、`previousStartDate` に当初の開始日を書く。
  書き忘れると `slug_date_mismatch` と `desc_date_mismatch` が鳴る。
- アイキャッチを出典と別の投稿から採ったら、`instagramUrl` と `instagramPostId` も同じ投稿に揃えるか消す。
  前の回の投稿を入れない。投稿IDは投稿日時を持つ(`instagram_post_predates_edition`)。
- 画像を外したら `scripts/image-rejected.json` の `items` に記録する。消すだけだと翌週 enrich が書き戻す。
  確かめて正しかった別ホストの画像は同じファイルの `accepted` に入れる(`image_host_unrelated`)。

### 3.6 Instagram の読み方

- **Instagram は API で読める。**プロアカウントの主催は `ig-organizer-watch.py`(daily。接続は `scripts/iglib.py`、Secret `IG_PAGE_TOKEN`)が
  Graph API の Business Discovery で最新投稿の本文、日時、URL、原寸画像を読み、`organizer-posts.json` に置く。
  `watch-sources.json` の `apiStatus` が `api` のアカウントはブラウザで開き直さない。
  ブラウザが要るのは `personal` と `unchecked`、それと取得範囲より古い投稿だけ。personal には存在しないアカウントも混ざる。
- 本文は、ログイン済みの組み込みブラウザで instagram.com を開いたタブから fetch して読む。短い抜粋で選別し、当たりだけ長く取る。
  ```js
  const cap = async (code, n=600) => {
    const r = await fetch('/p/'+code+'/embed/captioned/', {credentials:'include'});
    const c = new DOMParser().parseFromString(await r.text(), 'text/html').querySelector('.Caption');
    return c ? c.innerText.replace(/\s+/g,' ').slice(0, n) : '(none)';
  };
  ```
  `(none)` が返るアカウントは埋め込みを許可していない。`/p/<code>/` を fetch して `meta[name="description"]` を読む。
- プロフィールは navigate して DOM の `a[href*="/p/"]` から拾う。プロフィールの HTML を fetch しても投稿リンクは入っていない。
  グリッドの `img.alt` にはチラシの文字が OCR 済みで入っていて、同じ主催の別の回も一緒に見える。
- ペインが隠れていると投稿もグリッドも描画されない。navigate のあと `computer` の screenshot を1回撮ると `visible` になる。
  `browser_batch` は navigate → screenshot(scale 0.3)→ javascript の組を5つまで並べ、プロフィールは3秒待ってから拾う。
- `javascript_tool` は45秒で打ち切られ、戻り値は約1,000字で切れ、URL を含むと止められる。
  長い処理は `window` に積んで次の呼び出しで読み、URL は `replace(/https?:\/\//g,'H//')` で潰して返す。navigate すると `window` の値は消える。
- 画像のバイト列を文脈に通さない。CDN(`scontent-*.cdninstagram.com`)の署名付き URL はクラウドのコンテナから curl で取れる。
  instagram.com の `localStorage` を読む javascript は分類器に止められる。
- カルーセルの2枚目以降は `/p/<code>/?img_index=N` で開く。全部の画像の URL は、`embed/captioned` の HTML の `edge_sidecar_to_children` にある `display_url` から取れる。
  ```js
  const html = await (await fetch('/p/<code>/embed/captioned/', {credentials:'include'})).text();
  let seg = html.slice(html.indexOf('edge_sidecar_to_children'), html.indexOf('edge_sidecar_to_children') + 40000);
  for (let k = 0; k < 6; k++) seg = seg.replace(/\\\\/g, '\\').replace(/\\"/g, '"').replace(/\\\//g, '/');
  seg = seg.replace(/\\u0026/g, '&').replace(/u00253D/g, '%3D').replace(/u0026/g, '&');
  [...seg.matchAll(/"display_url"\s*:\s*"([^"]+)"/g)].map(m => m[1]);
  ```
- 主催の handle は名前から topsearch で引ける。未ログインの日は 404 になる。
  ```js
  fetch('/api/v1/web/search/topsearch/?context=blended&query='+encodeURIComponent('<名前>'),
        {credentials:'include', headers:{'x-ig-app-id':'936619743392459'}}).then(r=>r.json())
    .then(j=>j.users.map(u=>u.user.username+' / '+u.user.full_name))
  ```
  Google の `"<名前>" site:instagram.com` で出店者の投稿から引けることも多い。未ログインでも `fetch('/<handle>/')` の `<title>` で持ち主を確かめられる。
- 回専用のアカウントや共同投稿者がいる。共同投稿は共同投稿者のグリッドにも出るので、会場が共同投稿者なら会場の告知として扱う。

### 3.7 アイキャッチの取り方

- 手順はスキル agave-navi-eyecatch。まず CI の候補(`staging/eyecatch/`)を片づけ、ブラウザで取るのは候補が出ない回だけにする(1回6件まで)。
- **採否は画像を1枚ずつ目で見て決める。**照合の点数は候補を絞る道具で、採否の根拠にならない。迷ったら捨てる。
  人物(子どもを含む)が写った画像は、告知として使われていれば採る(listing-policy)。
- 採否は `apply-eyecatch.py` で書く。`--list` で並べ、`--approve <slug>` で採用、`--reject "<slug>=理由"` で不採用。
  - ブラウザで取って捨てた投稿は `--reject-post "<slug>=<投稿URL>=<理由>"`。
  - どの回の告知でもない画像(苗や商品の写真、店の案内、出店者紹介、募集、ロゴだけ)は `--not-flyer` を付け、全部の回の候補から外す。別の回の告知には付けない。
  - 動画は記録しない。記録すると、CI が動画の表紙を候補に出す道を塞ぐ。
  - カルーセルの1枚目を捨てても `--reject-post` は書かない。投稿単位の記録なので、2枚目を採る道を塞ぐ。
- ブラウザで開く回は `python3 scripts/list-missing-eyecatch.py --browser --limit 6` で出す。`hintRejected` の付いた回は同じ投稿を開き直さない。
  `ciSkipsSource` と `ciSourceOutOfRange` の回は、主催が api でも CI が候補に出さない。
  候補が出ていないことは告知が無い証拠にならない。staging は12件(`eyecatchlib.MAX_PENDING`)で頭打ちになる。
- 投稿ページで `igGrabHere`(`scripts/browser/ig-eyecatch.js`)を呼び、表示中のスライドと候補の数を確かめる。
  画像は `embed/captioned` の `EmbeddedMediaImage` の src をコンテナで curl し、`eyecatchlib.save_image` で保存する。
  og:image とグリッドのサムネイルは切り出し版なので使わない。`/reel/<code>` は `/p/<code>/` に読み替える。
  screenshot を挟んで20秒待っても img が無く video だけなら動画。
- 候補の画像を Read で見るには、`mzplants\agave-navi\work\_eyecatch_tmp` に置いて `device_stage_files` で取り込む。`/tmp` は stage できない。
  フォルダは固定名で毎回上書きする。日付付きで作ると、無人の実行は削除できず残骸が増える(2026-11-09 時点で10個)。
- 採った画像に時刻、入場料、会場が書いてあって回の値に無ければ、その場で埋める。
  会場が分かった tbd の回は venue と location を埋めて eventStatus を confirmed にする(`tbd_with_named_venue`)。
- 取得元は `imageSource` に必ず残す。詳細ページの脚注に出る。

### 3.8 中止と日程変更の見張り

- 中止は条件を満たせば自動で反映される(`auto_cancel_ok`)。主催がその回の日付つきで中止を言い切り、延期などの語が無く、掲載日以降で開催日以前の投稿のとき。
  日次メールの「主催の告知で中止にした回（自動）」に出る。誤りなら eventStatus を戻し、`scripts/cancel-reviewed.json` に記録する。
- `cancel_suspects` は公式ページが変わったことで鳴る。変化は中止の証拠ではない。
  url と sourceUrl を開いて、会期の表記、本文の中止や延期の告知、メインビジュアルの画像を見る。
  判断は `cancel-reviewed.json`(slug、checkedOn、verdict、note)に書く。書かないと毎日同じものが並び、本物の変化が埋もれる。
- 中止の語は、どの回のものかを前後の文で確かめる。過去の回の「中止のお知らせ」、同じ頁の別企画の雨天延期、出展者1組の取り止め、
  施設の「利用中止」、天候の条件文(「場合」「際」「とき」が付く)は、その回の中止ではない。
- 同じ型の誤検知が2回出たら、記録で黙らせず `check-cancelled.py` の規則を直す。同じ回を3回「開催予定のまま」と記録しそうなら、記録ではなく規則を直す。
  会期の最終日に3回目を記録しない。
- 主催の日程変更は新しい回ではない。`organizer_unlisted_dates` や `organizer_post_span_differs` に出たら、既存の回の date、dateDisplay、説明文、出典を直して `rescheduled` にする(§3.5)。
- 主催が会期を後から動かすことがある。最新の投稿と食い違えば `organizer_post_span_differs` に出る。

### 3.9 問い合わせフォーム

担当は `event-listing-review`。

- フォームが送信されると、GAS(`scripts/google-apps-script.js`。Apps Script「agave-navi フォーム→GitHub連携」)が通知メールを送り、`new-inquiries.json` の `items` に追記する。
- タスクは `items` を処理して `inquiries-processed.json` に移し、`items` を空にする。
  `processed` に加えて `outcomes` に `{timestamp, type, eventName, action, detail, verifiedOn}` を書く。action は `listed`、`rejected`、`queued`、`no-action`(`inquiry_outcome_event_mismatch`)。
- 起動記録(§1 の 5)が `reviewedOn` と `reviewedHistory` を書く。これがタスクの生存確認になるので、新着ゼロの日も push する(`inquiry_check_stale`、`inquiry_review_gap`)。
  `lastChecked` は GAS が書くので触らない。
- 回答シートを毎回数える。Google Sheets コネクタの `get_values` で spreadsheetId `1iTWAAbd5FV4NkNyt186H8wR6KqTPOLcFWSvHghZMDvI`、range `フォームの回答 1!A1:A500` を読み、
  A列が `^\d{4}/\d{1,2}/\d{1,2} \d{1,2}:\d{2}:\d{2}$` に一致する行を `values` から数える。戻り値の `range` の終端では数えない。
  - 行数 = `processed` なら新着ゼロ。行数 > `processed` は GAS の取りこぼしで、会話のセッションが Apps Script の `backfillFromSheet` を実行する。
    行数 < `processed` は読み取りの失敗で、新着ゼロと結論しない。
  - 数えたら `sheetRows` と `sheetCheckedOn` を書く。読めなかった回は日付を進めず、レポートに「コネクタ不可」と書く。
  - 新着の中身は B〜F 列(メールアドレス、お名前、お問い合わせ種別、イベント概要、イベント名)。設問が変わったかは1行目の見出しで見る。
- **氏名とメールアドレスは repo、レポート、戻り値に書かない。**repo は public で、監査結果も公開される。
- フォームやシートが読めなかった回も黙って終えない。レポートに書き、`pending-judgments.json` に積む。
- 新着ゼロが何週も続くときは、フォームの `viewform` に「回答を受け付けていません」が出ないことと、`contact.html` がそのフォームを指していることを確かめる。テスト送信はしない。
- Apps Script のトリガー画面は定期実行では開かない。開くのは行数 > `processed` が出たときだけで、会話のセッションから目崎のブラウザで開く。
  `/u/N` の番号は入れ替わるので、開いた画面のアカウントボタンで個人アカウントかを確かめてから読む。
- repo の GAS を直しても、Apps Script に貼るまで実機は変わらない。`gas_script_undeployed` は貼った後も次のフォーム送信まで鳴る。

### 3.10 CI と自動処理の癖

- daily の日付照合(`check_date_updates.py`)は出典を毎日読んで date を書き換える。
  enrich(sync-events と週次)は出典の頁から time、admission、説明文、画像を採る。
  出典が一覧や施設の頁だと、どちらも別の回の値を書く。一般名だけの回は、enrich が別のイベントの値を入れやすい。
  載せた後は sync-events のログ(`WRITE-BACK`、`Found:`)と自分の回の値を確かめる。
- 手で直した値をその夜の CI が戻すことがある。戻されたら、値を書く側のコードを直す。
- 週次エンリッチのスケジュール実行は20件しか処理しない。
- `enrich_events.py` は既定では回を消さない。消すのは `--remove` を付けたときだけ。
- CI の push が衝突したら `ci-push.sh` が生成物を作り直し、events.json は `scripts/merge-events-3way.py` で回と項目の単位で合わせる。
  巡回の結果(`scripts/ci-snapshot-paths.txt`)は作り直しで捨てない。
  daily のログに出た件数が repo のファイルに無ければ、手元で `coverage-sweep.py --days 45` と `check-cancelled.py` を回して押す。
- GitHub の schedule は時刻を当てにできない。朝の流れは合図の push で進め、schedule は保険(architecture §2)。

### 3.11 サイトの作りを変えるとき

- JS と CSS の中身を変えたら `scripts/sitelib.py` の `JS_VERSION` と `CSS_VERSION` を上げ、`bash scripts/build-all.sh` を通す。
  上げ忘れると CDN と閲覧者のブラウザが旧版を配り続け、検査では見つからない(`css_version_drift`、`js_version_drift` が見るのは頁の参照だけ)。
  確かめるときは本番のファイルを `?cb=` 付きで取得して中身を見る。
- 「今日」は `sitelib.today_jst()` と `status-auto.js` の `AEN_TIME` だけで決める。
  JS は `new Date(Date.now() + 9*3600000)` に `getUTC*()` を使い、`getTimezoneOffset()` は使わない(`js_local_timezone_math`)。
- 開催中の回は本体の一覧に混ぜ、件数で節を出し分けない。絞り込みのたびに変わる数を、読み込み時に1回だけ決める分岐の条件にしない。
- スラッグは `sitelib` の `*_slug()`、会場の束ねは `sitelib.venue_key()`、都道府県と地域は `PREF_TO_REGION`、会場が未定かは `is_vague_venue()`、
  画像が汎用かは `is_generic_image_url()`、休日かは `is_rest_day`(祝日を含む)で決める。写しを持たない。
- 挿入系のスクリプトは冪等(除去してから挿入)にする。
- 本番を組み込みブラウザで見るとき、ペインが隠れていると `innerWidth` が0、`document.hidden` が true で、
  scroll イベント、IntersectionObserver、CSS トランジションが動かない。
  `resize_window` で 375x812 にし、`scrollTo({top: …, behavior: 'instant'})` のあと `window.dispatchEvent(new Event('scroll'))` を足して見る。
  トップは `localStorage.removeItem('aen_region')` をしてから見る。終わったら desktop に戻してタブを閉じる。
- アフィリエイトの正常な形。`.aff-shop-btn` は Amazon(`tag=aganavi-22`)と Yahoo!ショッピング。旧ID `agavenavi-22` が出たら旧版を疑う(`affiliate_dead_tag`)。
  `.aff-mercari` は詳細、タグ、ガイドの枠の先頭(`affiliate-links.json` のリンクはダッシュボードで作ったものをそのまま使う)。
  `.aff-bar` はスマホ幅だけに出て、デスクトップ幅では DOM に無いのが正常。

### 3.12 監査と指標の読み方

- severity は3段階。urgent は壊れている(0が正常)、info は直せる負債、metric は構造上0にならない観測値。
- metric は急に動いたときだけ `metric_moved` で鳴る。直近の中央値から相対30%以上かつ絶対10件以上。
  `upcoming_no_image` と `eyecatch_backlog` は、前回からの新規掲載と外した画像を差し引いた残りで鳴る。新しく載せた回は必ず画像なしで入るため。
- リンク切れは URL 単位で数える。statusCode -1(DNS、タイムアウト、TLS)はリンク切れではない。
- `task_run_gap` の前に `task_run_never_recorded` を引く。全タスクが同じ日に抜けたのは PC 側の停止(§1 の 7)。
- 推移が何週も動かない項目は、担当スクリプトのスキップ条件を先に読む。手が足りないのではなく、手が届く前に return していることがある。

---

## 4. 自己改善のやり方

気づいたことは repo に残す。置き場は上から順に選ぶ。

| 気づいたこと | 置き場 |
|---|---|
| 機械で止められる誤り | コード。監査の検査、取り込みの入口、生成器 |
| 掲載の判断の基準 | `listing-policy.json` |
| 作業の手順と注意 | このファイルの該当する節。1〜3行 |
| 何が起きたか、いつ何を変えたか | コミットメッセージと `docs/architecture-2026-07.md` の §8 |

このファイルの書き方:
- 規則は今の形だけを書く。日付の付いた経緯、「追記」の節、点検の記録を足さない。経緯はコミットメッセージに書く。
- 古くなった行は書き換えるか消す。「※訂正」を重ねない。
- 1つの規則は1か所にだけ書く。同じ話題の行があれば、足さずにその行を直す。
- コードや listing-policy に入った規則は、ここではその場所を指すだけにする。
- このファイルは 72KB までにする(監査 `playbook_oversize`)。超えたら、コードや listing-policy に移した規則と古くなった行を消して縮める。

### audit.py に検査を足すとき

```python
add('key_name', '日本語のタイトル', items, note='対処のヒント', severity='urgent')
```

- urgent は日次メールに出る。0件が正常なものだけにする。常に0にならないものは info か metric にし、metric にするときは0にできない理由を note に書く。
- health.yml は触らなくてよい。メールは severity を見て出す。
- 監査を回せない回は検査を足さない。観測していない不整合への検査は、誤検知でその後の判断を汚す。
- 足したら1回実行して誤検知が無いことを確かめる。直す前のデータにも当て、狙った件数が出ることを確かめる。0件を返す検査は、壊れていても0件を返す。
- 誤検知が止まらない検査は消す。

### コードを直すときの原則

- 規則やデータの語彙を書いたら、それを読む側を同じコミットで足す。テストを足したら、それを呼ぶ側も同じコミットで足す。
- 検出だけを足すと、値を書く側が翌日に戻す。書く側を先に直す。
  書く側に関門を足したら、関門が無かった期間に書かれた値を、開催済みの回も含めて洗う。
- 1つの穴を塞いだら、同じ穴が他の経路に無いかをその日のうちに数える。
- 黙って抜ける分岐(`return ''`、`continue`、当たらない `str.replace`、条件付きの表示)を書いたら、抜けた件数を出力する。
- 同じ列挙や定数を2か所に書かない。`sitelib` に寄せる。
- 検査の母集団から何かを外すときは、外した先を見る検査を同じコミットで足す。
  メールや一覧から節を外すときは、その節だけが読んでいた値を grep して、読む側を移してから外す。
- 同じ項目を2日続けて reviewed や「開催予定のまま」で流したら、記録ではなく規則を疑う。

---

## 5. 自分を疑うこと

- 存在ではなく機能を確かめる。枠があるかではなく見える位置にあるか、生成されたかではなく全件載っているかを見る。
  見た目の変更は、スクリーンショットを見るまで完了と言わない。
- スクリプトは成功件数だけでなく、除外と欠落も出す。
- 検算は、増えたかではなく減っていないかを見る。
- push と本番の確認に `raw.githubusercontent.com` や素の URL の web_fetch を使わない。古い版が返ると、直したのに直っていないと読むことも、消したのに残っていると読むこともある。
- 前回より悪化していたら、まず自分の変更を疑う(`audit-history.json`)。
- レポートに書く件数は前回のレポートから写さず、数え直す。
- 指標の差だけで働きを測らない。残数は母数が増えれば増える。

---

## 6. 週次の自己点検

`site-health-check` が週に1回行う。結果はレポートに書き、このファイルには書かない。

1. 直近7日の `task-reports/` を読む。2回以上出た失敗は、§4 の順で恒久化する。
2. `audit-history.json` の推移を見る。urgent が増えていれば原因を直す。何週も動かない項目は、対処されていないか検査が不適切かのどちらかを直す。
3. `pending-judgments.json` が3件以上なら、人の判断が本当に要るかを見直す。要らないものは `listing-policy.json` に基準を書く。
4. `task_run_gap` を見る(§3.12)。台帳に無いタスクがあれば足す。
   `work\` に残った `*-unpushed-*.json` と `*.patch` は、反映済みか期限切れかを見て回収する。
5. このファイルを点検する。日付の付いた追記や同じ規則の重複が増えていれば、§4 の書き方に戻す。
