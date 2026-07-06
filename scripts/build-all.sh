#!/usr/bin/env bash
# build-all.sh — 全静的ファイルの再生成チェーン(単一情報源)。
# 各workflowはこのスクリプトを呼ぶ。順序に意味がある:
#   detail/guides → static/index系 → landing(noindex manifest出力) → sitemap(manifest参照)
set -euo pipefail
cd "$(dirname "$0")/.."

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

echo "build-all: done"
