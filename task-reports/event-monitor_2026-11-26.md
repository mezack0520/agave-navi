# event-monitor 2026-11-26

## 監査
- audit.py: 前日比の悪化 venue_slug_romaji_candidates 0→1、time_vs_organizer_post 0→1。data-integrity-check: errors 0 / warnings 0。
- build-health-mail(着手前): 反映1件、残り2件(上の2つ)。
- pending-judgments: items 0。log-fix の skipped 未解決 2件(11/02・11/10 の coverage_gaps、agave-event-update 担当)。

## 直したこと
- 緑楽宴mini in 明石: time 10:00〜20:00 → 10:00〜16:00。主催 @honoka.kakogawa の告知 DgEd9OCAOM0。11/24 の掲載時に手で入れた値の誤り。
- 兵庫県立フラワーセンター: 加西Plants Market で3件になった。_VENUE_ROMAJI_RAW に hyogo-flower-center、旧 v-22c46406 を _VENUE_REDIRECTS_RAW に。venue_redirect_broken は daily の再生成で消える。
- 花友フェスタ(cancel_suspects、画像): hanatomofesta.com は画像URLの末尾に取得のたびに変わる数字(?1795648812)を付けており、本文が変わった翌回に毎回「画像」で鳴っていた(cancel-reviewed に開催予定のまま3回)。check-cancelled.py で末尾の ?数字 と ?ver= を落として比べる(IMG_RULE。初回は画像を比べない)。self-test に2件。頁は 12/19 のままで中止の語なし。
- @vivi_succulent 12/20(organizer_unlisted_dates): ROOTS MARKET の出店者募集の締切「募集期間は只今より、12月20日まで」。ig-organizer-watch.py の _PERIOD_BEFORE を「は只今より」まで読むようにした。self-test に1件。3/21 は掲載済み。
- mail-request.json を push(日次メールの合図)。

## 未対応
- なし
