#!/bin/bash
# =============================================================
# agave-navi.com リンク切れチェッカー
# - index.html 内の外部サムネイル画像URL
# - events.json 内の sourceUrl（公式サイトリンク）
# - イベント詳細ページのリンク整合性
# =============================================================

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPORT_FILE="/tmp/link-check-report.md"
BROKEN_COUNT=0
WARN_COUNT=0

echo "# リンクチェックレポート" > "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
echo "実行日時: $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M JST')" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# --------------------------------------------------
# 1. 外部サムネイル画像の死活チェック
# --------------------------------------------------
echo "## サムネイル画像URL" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

IMG_URLS=$(grep -oP 'event-thumb"><img src="\K[^"]+' "$REPO_ROOT/index.html" 2>/dev/null || true)

if [ -z "$IMG_URLS" ]; then
  echo "画像URLなし（すべてNO IMAGE）" >> "$REPORT_FILE"
else
  IMG_OK=0
  IMG_NG=0
  for url in $IMG_URLS; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 15 \
      -H "Referer: " -A "Mozilla/5.0 (compatible; AgaveNaviBot/1.0)" "$url" 2>/dev/null || echo "000")
    SLUG=$(grep -B5 "$url" "$REPO_ROOT/index.html" | grep -oP 'data-slug="\K[^"]+' | tail -1)
    if [ "$HTTP_CODE" -ge 200 ] 2>/dev/null && [ "$HTTP_CODE" -lt 400 ] 2>/dev/null; then
      IMG_OK=$((IMG_OK + 1))
    elif [ "$HTTP_CODE" = "000" ]; then
      # 接続エラー（タイムアウト等）= 警告扱い
      IMG_NG=$((IMG_NG + 1))
      WARN_COUNT=$((WARN_COUNT + 1))
      echo "- ⚠️ **接続不可** \`${SLUG}\` → ${url}" >> "$REPORT_FILE"
    else
      IMG_NG=$((IMG_NG + 1))
      BROKEN_COUNT=$((BROKEN_COUNT + 1))
      echo "- ❌ **${HTTP_CODE}** \`${SLUG}\` → ${url}" >> "$REPORT_FILE"
    fi
  done
  if [ "$IMG_NG" -eq 0 ]; then
    echo "✅ 全${IMG_OK}件 正常" >> "$REPORT_FILE"
  else
    echo "" >> "$REPORT_FILE"
    echo "合計: ✅ ${IMG_OK}件 正常 / ❌ ${IMG_NG}件 エラー" >> "$REPORT_FILE"
  fi
fi
echo "" >> "$REPORT_FILE"

# --------------------------------------------------
# 2. events.json の sourceUrl チェック
# --------------------------------------------------
echo "## イベント公式サイト (sourceUrl)" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

# JSONからslug+sourceUrlペアを抽出
SRC_PAIRS=$(python3 -c "
import json, sys
with open('$REPO_ROOT/events.json') as f:
    events = json.load(f)
for e in events:
    url = e.get('sourceUrl','')
    if url:
        print(e['slug'] + '\t' + url)
" 2>/dev/null || true)

SRC_OK=0
SRC_NG=0
SRC_WARN=0

if [ -n "$SRC_PAIRS" ]; then
  while IFS=$'\t' read -r slug url; do
    # Instagram/Xはログイン壁があるので軽いチェックのみ
    if echo "$url" | grep -qE '(instagram\.com|twitter\.com|x\.com)'; then
      HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 \
        -A "Mozilla/5.0" "$url" 2>/dev/null || echo "000")
      if [ "$HTTP_CODE" -eq 000 ]; then
        SRC_WARN=$((SRC_WARN + 1))
        WARN_COUNT=$((WARN_COUNT + 1))
        echo "- ⚠️ **タイムアウト** \`${slug}\` → ${url}" >> "$REPORT_FILE"
      else
        SRC_OK=$((SRC_OK + 1))
      fi
    else
      HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -L --max-time 10 \
        -A "Mozilla/5.0" "$url" 2>/dev/null || echo "000")
      if [ "$HTTP_CODE" = "000" ]; then
        # 接続エラー（タイムアウト等）= 警告扱い
        SRC_WARN=$((SRC_WARN + 1))
        WARN_COUNT=$((WARN_COUNT + 1))
        echo "- ⚠️ **接続不可** \`${slug}\` → ${url}" >> "$REPORT_FILE"
      elif [ "$HTTP_CODE" -ge 200 ] 2>/dev/null && [ "$HTTP_CODE" -lt 400 ] 2>/dev/null; then
        SRC_OK=$((SRC_OK + 1))
      elif [ "$HTTP_CODE" -ge 400 ] 2>/dev/null && [ "$HTTP_CODE" -lt 500 ] 2>/dev/null; then
        # 4xx = 明確なリンク切れ
        SRC_NG=$((SRC_NG + 1))
        BROKEN_COUNT=$((BROKEN_COUNT + 1))
        echo "- ❌ **${HTTP_CODE}** \`${slug}\` → ${url}" >> "$REPORT_FILE"
      else
        # 5xx / その他 = 一時的な問題の可能性 → 警告
        SRC_WARN=$((SRC_WARN + 1))
        WARN_COUNT=$((WARN_COUNT + 1))
        echo "- ⚠️ **${HTTP_CODE}** \`${slug}\` → ${url}" >> "$REPORT_FILE"
      fi
    fi
  done <<< "$SRC_PAIRS"

  echo "" >> "$REPORT_FILE"
  echo "合計: ✅ ${SRC_OK}件 / ❌ ${SRC_NG}件 エラー / ⚠️ ${SRC_WARN}件 警告" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# --------------------------------------------------
# 3. イベント詳細ページの存在チェック
# --------------------------------------------------
echo "## イベント詳細ページ整合性" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"

DETAIL_MISSING=0
SLUGS_IN_JSON=$(python3 -c "
import json
with open('$REPO_ROOT/events.json') as f:
    events = json.load(f)
for e in events:
    print(e['slug'])
" 2>/dev/null || true)

for slug in $SLUGS_IN_JSON; do
  if [ ! -f "$REPO_ROOT/events/${slug}.html" ]; then
    DETAIL_MISSING=$((DETAIL_MISSING + 1))
    BROKEN_COUNT=$((BROKEN_COUNT + 1))
    echo "- ❌ \`events/${slug}.html\` が存在しません" >> "$REPORT_FILE"
  fi
done

if [ "$DETAIL_MISSING" -eq 0 ]; then
  TOTAL_SLUGS=$(echo "$SLUGS_IN_JSON" | wc -l)
  echo "✅ 全${TOTAL_SLUGS}件の詳細ページが存在" >> "$REPORT_FILE"
fi
echo "" >> "$REPORT_FILE"

# --------------------------------------------------
# 4. サマリー
# --------------------------------------------------
echo "---" >> "$REPORT_FILE"
echo "" >> "$REPORT_FILE"
if [ "$BROKEN_COUNT" -gt 0 ]; then
  echo "## ⚠️ 要対応: ${BROKEN_COUNT}件のリンク切れが見つかりました" >> "$REPORT_FILE"
elif [ "$WARN_COUNT" -gt 0 ]; then
  echo "## 📋 ${WARN_COUNT}件の警告があります（即時対応不要）" >> "$REPORT_FILE"
else
  echo "## ✅ すべてのリンクが正常です" >> "$REPORT_FILE"
fi

cat "$REPORT_FILE"

# 終了コードで通知判断（GitHub Actions用）
echo "$BROKEN_COUNT" > /tmp/broken-count
echo "$WARN_COUNT" > /tmp/warn-count
