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
- **GitHubへの書き込み経路は PAT の `git push` だけ。** ブラウザからは一切書けない。
  Chromeは仕事用の `YujiMezaki` でログインしており `mezack0520` のリポジトリはWeb UIから編集できない。
  以前は Edge が `mezack0520` でログイン済みで `switch_browser` の逃げ道があったが、
  **Edge は2026-08-18に廃止した。代替のブラウザは無い。**
  したがって Run workflow ボタンを押す・Web UIでファイルを直す・Actions を手動再実行する、は**できない**。
  `workflow_dispatch` はPATでも403なので、ワークフローを動かしたいときは
  対象ファイルを push して `on.push` を発火させるしかない。
  読み取り（無認証の `api.github.com` GET・Actionsの実行結果閲覧）はブラウザから通る

## 3. 既知のハマりどころ

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
- **Chromeのプロファイルは前回の実行のlocalStorageを引きずる。本番の見え方を「壊れている」と
  判定する前に localStorage を読む。** 2026-08-18、トップの件数バッジが 30件(実データは開催予定77件)で
  47件が非表示になっており、掲載漏れの重大バグに見えた。原因は前回のチェックが残した
  `aen_region="関東"` で、サイトは正しく動いていた。`index.html` の `initRegion()` が
  地域選択を localStorage から復元する仕様。表示件数・表示要素を疑ったら、まず
  `Object.keys(localStorage)` を出してから結論する
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
4. 上記でプレイブックを更新したら、何を変えたかレポートに1行で書く
