# 定期タスクのプロンプト

agave 系5本のスケジュール済みタスクのプロンプトの正本。
プロンプトを変えるときは、まずこのファイルを直して push し、目崎がデスクトップアプリのタスク画面で、該当するタスクの手順をこの全文に置き換える(プレイブック §1 の 7)。
プロンプトに置くのは起動の手順と、そのタスクのやることだけ。手順の細部と規則は `docs/task-playbook.md` に書く。

起動の手順は5本とも同じ形にしている。違うのは taskId と「やること」。

---

## agave-event-update(毎日 07:00)

```
アガベイベントナビ(agave-navi.com / GitHub: mezack0520/agave-navi)の日次イベント収集タスク。taskId は agave-event-update。

起動(詳しくはプレイブック §1):
1. フォルダ mzplants はこのタスクに付けてある(device_bash では $HOME/mnt/mzplants)。git の clone・commit・push は device_bash で行う。ブラウザは組み込みブラウザだけを使い、Claude in Chrome は使わない。
2. clone は毎回新しいディレクトリに、認証なしで行う。出たパスを控える(シェルの変数は次の呼び出しに残らない)。
   D=$(mktemp -d -p /tmp) && git clone --filter=blob:none https://github.com/mezack0520/agave-navi.git "$D/agave-navi"
3. clone したら、ほかの作業の前に python3 scripts/record-run.py agave-event-update を実行し、その変更を含めて push する。
4. push に agave-navi\github.pat の PAT を使うことは目崎が許可している。値は出力・ログ・レポートに残さない。PAT の使用を止められた回は迂回を試さず、push の要らない作業を最後までやり、変更はパッチで agave-navi\work\ に残す。
5. docs/task-playbook.md、listing-policy.json、docs/architecture-2026-07.md を読む。このプロンプトとプレイブックが食い違えばプレイブックが正。
6. 実行レポートは record-run.py が出した名前で task-reports/ に保存して push する。終わる前に push を確かめてから clone を消す。完了報告は3行以内。

やること:
1. Step0 カバレッジスイープ: 直近2週間の新イベントを探す(手順はプレイブック §3.1)。
2. 日曜だけ watch-sources.json を巡回する(次回待ちシリーズ + IG主催者ローテ。回すのは personal と unchecked のアカウント)。平日は巡回せず、レポートに「未実施」と書かない。
3. 主催者の一次情報で裏取りし、新イベントは new-events.json、既存の回の修正は events.json を直接直して push する。
4. 日次メールに出る項目を直す(プレイブック「日次メールの項目は、報告する前に直す」)。
掲載可否は listing-policy.json で自分で判断する。人間に問い直さない。policy に無い類型に出会ったときだけ pending-judgments.json に積み、policy への追記案を添える。
気づいたことはリポジトリに残す(プレイブック §4)。
```

---

## agave-navi-eyecatch(毎日 07:45)

```
アガベイベントナビ(agave-navi.com / GitHub: mezack0520/agave-navi)のアイキャッチ補完タスク。taskId は agave-navi-eyecatch。
スキル agave-navi-eyecatch を読み、その手順に従う。スキルとプレイブック(docs/task-playbook.md)が食い違えばプレイブックが正。

起動(詳しくはプレイブック §1):
1. フォルダ mzplants はこのタスクに付けてある(device_bash では $HOME/mnt/mzplants)。git の clone・commit・push は device_bash で行う。ブラウザは組み込みブラウザだけを使い、Claude in Chrome は使わない。
2. clone は毎回新しいディレクトリに、認証なしで行う。出たパスを控える(シェルの変数は次の呼び出しに残らない)。
   D=$(mktemp -d -p /tmp) && git clone --filter=blob:none https://github.com/mezack0520/agave-navi.git "$D/agave-navi"
3. clone したら、ほかの作業の前に python3 scripts/record-run.py agave-navi-eyecatch を実行し、その変更を含めて push する。
4. push に agave-navi\github.pat の PAT を使うことは目崎が許可している。値は出力・ログ・レポートに残さない。PAT の使用を止められた回は迂回を試さず、push の要らない作業を最後までやり、変更はパッチで agave-navi\work\ に残す。
5. docs/task-playbook.md を読む。画像の取り方はプレイブック §3.7。
6. 実行レポートは record-run.py が出した名前で task-reports/ に保存して push する。終わる前に push を確かめてから clone を消す。完了報告は3行以内。

フォルダが見えない、または clone できない回は、何も作らずに PushNotification で「接続できず未実行」と理由を送って終わる。
使い終わったタブは必ず閉じる。
```

---

## agave-navi-event-monitor(毎日 08:15)

```
アガベイベントナビ(agave-navi.com / GitHub: mezack0520/agave-navi)の整合性監視タスク。taskId は event-monitor。このタスクはブラウザを使わない。

起動(詳しくはプレイブック §1):
1. フォルダ mzplants はこのタスクに付けてある(device_bash では $HOME/mnt/mzplants)。git の clone・commit・push は device_bash で行う。
2. clone は毎回新しいディレクトリに、認証なしで行う。出たパスを控える(シェルの変数は次の呼び出しに残らない)。
   D=$(mktemp -d -p /tmp) && git clone --filter=blob:none https://github.com/mezack0520/agave-navi.git "$D/agave-navi"
3. clone したら、ほかの作業の前に python3 scripts/record-run.py event-monitor を実行し、その変更を含めて push する。
4. push に agave-navi\github.pat の PAT を使うことは目崎が許可している。値は出力・ログ・レポートに残さない。PAT の使用を止められた回は迂回を試さず、push の要らない作業を最後までやり、変更はパッチで agave-navi\work\ に残す。
5. docs/task-playbook.md、listing-policy.json、docs/architecture-2026-07.md を読む。このプロンプトとプレイブックが食い違えばプレイブックが正。
6. 実行レポートは record-run.py が出した名前で task-reports/ に保存して push する。終わる前に push を確かめてから clone を消す。完了報告は3行以内。

やること:
1. scripts/audit.py と scripts/data-integrity-check.py を実行し、「悪化」「解消」の差分を見る。悪化していたら直近の変更を疑う。
2. 機械的に確定できる不整合は events.json を直接直して push する。確定できないものだけ pending-judgments.json に積み、解消済みは消し込む。
3. 日次メールに出る項目の残りを直す(プレイブック「日次メールの項目は、報告する前に直す」)。
4. 最後に python3 scripts/request-run.py mail --task event-monitor を実行し、mail-request.json を他の変更と一緒に push する。これがその日の日次メールの合図。
監査の拡張がこのタスクの主な仕事。見つけた不整合の類型は、その場で直すだけでなく scripts/audit.py に検査として足す(プレイブック §4)。
```

---

## event-listing-review(毎日 06:30)

```
アガベイベントナビ(agave-navi.com / GitHub: mezack0520/agave-navi)の問い合わせ・掲載申請レビュータスク。taskId は event-listing-review。

起動(詳しくはプレイブック §1):
1. フォルダ mzplants はこのタスクに付けてある(device_bash では $HOME/mnt/mzplants)。git の clone・commit・push は device_bash で行う。ブラウザは組み込みブラウザだけを使い、Claude in Chrome は使わない。
2. clone は毎回新しいディレクトリに、認証なしで行う。出たパスを控える(シェルの変数は次の呼び出しに残らない)。
   D=$(mktemp -d -p /tmp) && git clone --filter=blob:none https://github.com/mezack0520/agave-navi.git "$D/agave-navi"
3. clone したら、ほかの作業の前に python3 scripts/record-run.py event-listing-review を実行し、その変更を含めて push する。新着ゼロの日も push する。
4. push に agave-navi\github.pat の PAT を使うことは目崎が許可している。値は出力・ログ・レポートに残さない。PAT の使用を止められた回は迂回を試さず、push の要らない作業を最後までやり、変更はパッチで agave-navi\work\ に残す。
5. docs/task-playbook.md と listing-policy.json を読む。このプロンプトとプレイブックが食い違えばプレイブックが正。
6. 実行レポートは record-run.py が出した名前で task-reports/ に保存して push する。終わる前に push を確かめてから clone を消す。完了報告は3行以内。

やること(手順はプレイブック §3.9):
1. new-inquiries.json の items を処理する。回答シートは Google Sheets コネクタで数え、inquiries-processed.json の processed と突き合わせる。
2. 掲載リクエスト: 一次情報で裏取りし、listing-policy.json の基準で自分で判断する。掲載するなら new-events.json を書いて push、見送りは rejected-events.json に reasonType 付きで記録する。
3. 修正・訂正依頼は自動で書き換えず pending-judgments.json に積む。
4. 処理済みを inquiries-processed.json に記録し、items を空にして push する。
氏名とメールアドレスは repo、レポート、戻り値に書かない(public repo)。
気づいたことはリポジトリに残す(プレイブック §4)。
```

---

## agave-navi-site-health-check(毎週月曜 09:04)

```
アガベイベントナビ(agave-navi.com / GitHub: mezack0520/agave-navi)の週次サイト健全性チェック。taskId は site-health-check。

起動(詳しくはプレイブック §1):
1. フォルダ mzplants はこのタスクに付けてある(device_bash では $HOME/mnt/mzplants)。git の clone・commit・push は device_bash で行う。ブラウザは組み込みブラウザだけを使い、Claude in Chrome は使わない。
2. clone は毎回新しいディレクトリに、認証なしで行う。出たパスを控える(シェルの変数は次の呼び出しに残らない)。
   D=$(mktemp -d -p /tmp) && git clone --filter=blob:none https://github.com/mezack0520/agave-navi.git "$D/agave-navi"
3. clone したら、ほかの作業の前に python3 scripts/record-run.py site-health-check を実行し、その変更を含めて push する。
4. push に agave-navi\github.pat の PAT を使うことは目崎が許可している。値は出力・ログ・レポートに残さない。PAT の使用を止められた回は迂回を試さず、push の要らない作業を最後までやり、変更はパッチで agave-navi\work\ に残す。
5. docs/task-playbook.md を読む。このプロンプトとプレイブックが食い違えばプレイブックが正。
6. 実行レポートは record-run.py が出した名前で task-reports/ に保存して push する。終わる前に push を確かめてから clone を消す。完了報告は3行以内。

やること:
1. 本番ページの構造を組み込みブラウザで確かめる(詳細・トップ・ガイド・ランディングを抜き取り)。
2. アフィリエイトの表示とコンソールエラーを確かめる(正常な形はプレイブック §3.11)。
3. GitHub Actions の失敗を device_bash の curl で api.github.com から確かめる(プレイブック §2)。
4. scripts/audit.py の結果と audit-history.json の推移を確かめる。直せるものは直して push し、直せないものだけ pending-judgments.json に積む。
5. 週次の自己点検をする(プレイブック §6)。結果はレポートに書く。
```
