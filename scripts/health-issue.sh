#!/usr/bin/env bash
# health-issue.sh — 健全性チェックの結果をまとめて Issue を1本立てる。
#
# 2026-09-10 に health.yml から出した。56行が workflow の `run: |` に
# 直書きされていて、ローカルで組み立てを確かめられなかった。
#
# 入力は環境変数(workflow の step outputs から渡す)。
#   INTEGRITY_ERR / LINKS_BROKEN / IMAGES_DEAD / SSL_DAYS
# ログは /tmp/{integrity,links,img,events}.log を読む(無ければ空欄)。
#
# gh が無い環境では本文を標準出力に出して終わる。
# **CIの外で落ちるなら、出した意味が無い。**
set -uo pipefail

INTEGRITY_ERR="${INTEGRITY_ERR:-0}"
LINKS_BROKEN="${LINKS_BROKEN:-0}"
IMAGES_DEAD="${IMAGES_DEAD:-0}"
SSL_DAYS="${SSL_DAYS:-999}"

PROBLEMS=$((INTEGRITY_ERR + LINKS_BROKEN + IMAGES_DEAD))
SSL_ALERT=""
if [ "$SSL_DAYS" -lt 30 ]; then
  SSL_ALERT="⚠️ SSL残${SSL_DAYS}日"
  PROBLEMS=$((PROBLEMS + 1))
fi

if [ "$PROBLEMS" -eq 0 ]; then
  echo "All health checks passed. No issue needed."
  exit 0
fi

REPORT=/tmp/health-report.md
{
  echo "## 健全性レポート $(date +%Y-%m-%d)"
  echo
  echo "| 項目 | 状態 |"
  echo "|---|---|"
  echo "| データ整合性エラー | ${INTEGRITY_ERR}件 |"
  echo "| リンク切れ | ${LINKS_BROKEN}件 |"
  echo "| 画像URL死亡 | ${IMAGES_DEAD}件 |"
  echo "| SSL残日数 | ${SSL_DAYS}日 ${SSL_ALERT} |"
  echo
  echo "### 詳細ログ"
  for pair in "data integrity:/tmp/integrity.log:30" "links:/tmp/links.log:20" \
              "images:/tmp/img.log:20" "events:/tmp/events.log:20"; do
    name="${pair%%:*}"; rest="${pair#*:}"; path="${rest%%:*}"; n="${rest##*:}"
    echo "<details><summary>${name}</summary>"
    echo
    echo '```'
    tail -n "$n" "$path" 2>/dev/null
    echo '```'
    echo "</details>"
  done
} > "$REPORT"

if ! command -v gh >/dev/null 2>&1; then
  echo "gh が無いので Issue は立てない。本文だけ出す:"
  echo "---"
  cat "$REPORT"
  exit 0
fi

gh label create "auto-health" --description "自動健全性レポート" --color "F4A261" 2>/dev/null || true
gh issue create \
  --title "🩺 健全性レポート $(date +%Y-%m-%d) (${PROBLEMS}件)" \
  --body-file "$REPORT" \
  --label "auto-health" || true
