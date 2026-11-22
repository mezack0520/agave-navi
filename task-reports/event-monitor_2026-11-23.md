# event-monitor 2026-11-23

## 起動
- clone /tmp/tmp.SjAVMzAGkh、record-run 済み(2a62c0f7)。

## 監査
- data-integrity-check: errors 0 / warnings 0(831件)
- audit: urgent 0。前日比の悪化なし。info は coverage_gap_stale 1(巡回後に掲載済み、次の巡回で消える)、task_run_gap 2・inquiry_review_gap 1(11-21 の3本の抜け。11-22 以降は動いている)。
- 日次メールの予定は「サイトに反映したこと」2件のみで、直す項目なし。

## 直したこと
1. 監査の拡張: organizer_name_variant(urgent)を足した。同じ organizerIg の回で主催名が記号・空白・括弧の併記だけ違う組を出す。規則は sitelib.organizer_name_variants、自己テスト8件。店舗名の付け足しと共催の併記は数えない。8月以降の events.json 26版に当てて、出たのは下の2組だけ(誤検知0)。
2. 主催名を揃えた(log-fix 記録済み)。
   - agave-summit-osaka-2026-11: Heartplants → Heartplants.(最新の回と説明文の表記)
   - temonone-hanbaikai-hitotubu-vintage-2026-10: てものね → temo（てものね）(多肉もぶれ2回と同じ)
3. プレイブックの日次メールの表に organizer_name_variant の行を足した。

## 残り
- pending-judgments 0件、needs_browser の未処理 0件。

## 終わり
- mail-request.json を push。
