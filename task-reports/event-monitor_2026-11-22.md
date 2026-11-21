# event-monitor 2026-11-22

## 起動
- clone /tmp/tmp.tfKU8R1OAi、record-run 済み(2241c74c)。

## 監査
- data-integrity-check: errors 0 / warnings 0(821件)
- audit 悪化: venue_slug_romaji_candidates 0→2、coverage_gap_logged_but_open 0→1。どちらも今朝の新規掲載・巡回に由来。

## 直したこと
1. venue_slug_romaji_candidates: オザキフラワーパーク(HOP で3件)、プロトリーフ ゆめが丘ソラトス店(necomoss で3件)を `_VENUE_ROMAJI_RAW` に足し、ハッシュの旧頁を `_VENUE_REDIRECTS_RAW` に残した。venue_redirect_broken は daily の再生成まで2件出る。
2. coverage_gap_logged_but_open: coverage-sweep の主催一覧(Jolie Nursery)で、会期中に初日が過ぎた回の見出しを2日目の「開催日時」の行から取り、名前の無い候補(春日店・小戸店の行)を出していた。年の無い日付が直前の年月日の続きなら見出しを年月日の行から取るよう直し、自己テストを足した。push で daily が巡回し直す。
3. organizer_unlisted_dates(@greensnap.jp 12/31): HAMACHO MIDORI MARKET の本文にあるスタンプラリーの期限。見送りに告知 Df9SGPjGY97 を書いた。見張り(known_elsewhere)は見送りが挙げた投稿でも会期の日付しか既知にしていなかったので、投稿のどの日付も既知にした(scan-organizer-posts も同じ関数)。自己テスト2件追加。
4. 監査の拡張:
   - organizer_unlisted_rejected_post を見張りと同じく日付で絞らないようにした。直す前のデータで HAMACHO の1件を検出することを確認。
   - organizer_unlisted_dates は、巡回の後にその投稿を出典に載せた回が会期で日付を覆えば数えない(HOP の1件)。数えなかった件数を出力する。

5. daily の巡回し直しで、取りこぼし候補の春日店・小戸店の行と HAMACHO の 12/31 が消えたことを確認。新たに出た @grace.succulents 11/28・29(福島市街なか交流館)は主催の告知 Df_jaXqyulB で裏取りし、日次メールの後に new-events.json で掲載。

## 残り
- 11-21 は event-listing-review / agave-event-update / agave-navi-eyecatch が trigger 上は発火したが何も押していない(task_run_gap)。今日は3本とも動いた。
- monster-plants-kagawa-2027-03 の保留が41日動いていない(rejected_revisit_stale、info)。agave-event-update の持ち分。
- pending-judgments 0件、needs_browser の未処理 0件。

## 終わり
- mail-request.json を push。health 成功、lastMailedOn 2026-11-22。clone 削除済み。
