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

## 3. 既知のハマりどころ

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
- 見送りは `rejected-events.json` に `reasonType` 付きで記録（`policy` / `unverified`）
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

## 6. 週次の自己点検（site-health-check が実施）

毎週、次を見て**プレイブック自体を更新する**。

1. `mzplants\agave-navi\task-reports\` の直近7日分を読む。
   同じ失敗が2回以上出ていたら §3 に追記する
2. `audit-history.json` の推移を見る。
   - urgent が前週より増えていれば原因を特定して直す
   - 何週間も同じ値のまま動かない項目は、対処されていないか検査が不適切。どちらかを直す
   - 常に0が続く項目は `severity='info'` に落とすことを検討（メールのノイズを減らす）
3. `pending-judgments.json` が3件以上溜まっていたら、人間の判断が本当に要るのか見直す。
   要らないものは `listing-policy.json` に基準を書いて自動化する
4. 上記でプレイブックを更新したら、何を変えたかレポートに1行で書く
