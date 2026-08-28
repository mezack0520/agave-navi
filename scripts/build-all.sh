#!/usr/bin/env bash
# build-all.sh — 全静的ファイルの再生成チェーン(単一情報源)。
# 各workflowはこのスクリプトを呼ぶ。順序に意味がある:
#   detail/guides → static/index系 → landing(noindex manifest出力) → sitemap(manifest参照)
set -euo pipefail
cd "$(dirname "$0")/.."

# status を JST 基準で確定させてから生成する。UTCのまま生成すると
# 終了翌日の丸一日、ランディング頁とフィードに終了済みが開催予定として載る。
python3 scripts/auto-status-jst.py

# 開催バッジの日付境界テスト。0時直後・早朝・深夜を4タイムゾーンで検証する。
# 2026-08-29 に todayJST() の時差計算が誤っていて、JSTの閲覧者に
# 0:00〜9:00 のあいだ「本日開催」が「明日開催」と出ていた。
# 生成物を見ても分からない類の不具合なので、生成前に落とす。
if command -v node >/dev/null 2>&1; then
  node scripts/test-date-boundary.js
else
  echo "::warning::node が無いため test-date-boundary.js をスキップしました"
fi

python3 build-detail-pages.py
python3 scripts/build-guides.py
python3 scripts/build-static-html.py
python3 scripts/sync-index-cards.py
python3 scripts/generate-rss.py
python3 scripts/generate-itemlist-jsonld.py
python3 scripts/generate-landing-pages.py
python3 scripts/generate-ical.py
python3 scripts/generate-csv.py
python3 scripts/generate-watchlist.py
python3 scripts/sync-footers.py
python3 scripts/generate_sitemap.py

# 整合監査(読み取り専用)。除外・欠落・孤児を毎回出力し、黙って落ちるのを防ぐ。
python3 scripts/audit.py || echo "::warning::audit.py が失敗しました"

echo "build-all: done"
