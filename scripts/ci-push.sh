#!/usr/bin/env bash
# ci-push.sh — 生成物を含むコミットを push する。衝突したら rebase せずに作り直す。
#
# 使い方:
#   bash scripts/ci-push.sh "<commit message>" ["<再生成コマンド>"]
#
# なぜ rebase を使わないか (2026-09-07 に daily.yml #160 の失敗を追って導入):
#   このリポジトリは events.json から feeds/*.xml・*.ics・詳細頁・sitemap を毎回
#   まるごと再生成する。remote 側の別ジョブも同じファイルを書き換えているので、
#   push が拒否された時点で rebase は生成物で必ず衝突する。
#   従来の `git pull --rebase || true` は衝突を握り潰し、リポジトリを
#   rebase 途中の detached HEAD("You are not currently on a branch")に残していた。
#   そのため 2〜5 回目の再試行は一度も成功しえず、5回ぶん無駄に回して失敗していた。
#   プレイブック §3 に「生成物の rebase は必ず衝突する。origin/main に reset --hard →
#   データ変更を再適用 → 再ビルド → push」と書いてあるのに、CI 側だけ従っていなかった。
#
# 復旧の考え方:
#   生成物は data から一意に決まるので、持ち越すのは data の差分だけでよい。
#   生成物のパスは scripts/ci-generated-paths.txt が単一情報源。
#   HEAD^ を基準にするので shallow clone (fetch-depth: 1) でも動く。
#
# 巡回の観測結果(scripts/ci-snapshot-paths.txt)は「この回の版」で上書きする(2026-10-07):
#   cancel-watch.json / coverage-gaps.json は build-all.sh では作り直せないが、
#   毎回まるごと書き換わるので差分で貼ると同時に走った回と衝突する(2026-09-15)。
#   そこで生成物と同じく差分からは外し、この回が書き換えていれば作り直しの後に
#   この回の版をそのまま置く。外すだけにしていた間は、push が拒否された回の
#   巡回結果が黙って捨てられていた。朝の巡回は合図(crawl-request.json)の push で
#   走り、合図を出したタスクがその数分後に自分の変更を push するので、
#   2026-10-06 以降はほぼ毎朝ここに当たる(10-07 実測: 中止の疑い2件が落ちた)。
set -uo pipefail

MSG="${1:?commit message required}"
REGEN="${2:-}"

cd "$(git rev-parse --show-toplevel)"
GEN_LIST="scripts/ci-generated-paths.txt"
SNAP_LIST="scripts/ci-snapshot-paths.txt"

git config user.name  "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

commit_all() {
  git add -A
  git reset -q HEAD -- '**/__pycache__' 2>/dev/null || true
  if git diff --staged --quiet; then return 1; fi
  git commit -q -m "$MSG"
  return 0
}

# 生成物を除外する pathspec を組み立てる。
exclude_args() {
  [ -f "$GEN_LIST" ] || return 0
  while IFS= read -r p; do
    case "$p" in ''|\#*) continue;; esac
    printf '%s\n' ":(exclude)$p"
  done < "$GEN_LIST"
}

# 巡回の観測結果のうち、このジョブが書き換えたものを退避する。
# 退避先のディレクトリを標準出力に返す(何も無ければ空)。
save_snapshots() {
  local base="$1" dir="" p
  [ -f "$SNAP_LIST" ] || return 0
  while IFS= read -r p; do
    case "$p" in ''|\#*) continue;; esac
    git cat-file -e "HEAD:$p" 2>/dev/null || continue
    git diff --quiet "$base" HEAD -- "$p" 2>/dev/null && continue
    [ -n "$dir" ] || dir="$(mktemp -d)"
    mkdir -p "$dir/$(dirname "$p")"
    git show "HEAD:$p" > "$dir/$p"
  done < "$SNAP_LIST"
  printf '%s' "$dir"
}

restore_snapshots() {
  local dir="$1" f
  [ -n "$dir" ] && [ -d "$dir" ] || return 0
  while IFS= read -r f; do
    f="${f#./}"
    mkdir -p "$(dirname "$f")"
    cp "$dir/$f" "$f"
    echo "巡回結果をこの回の版で置いた: $f"
  done < <(cd "$dir" && find . -type f)
  rm -rf "$dir"
}

# 差分が無くても push まで進む。前のステップが既にコミットしている場合があり、
# ここで早期 return すると、そのコミットが push されないまま成功扱いになる
# (旧 ops.yml は commit を省いても push ループには必ず入っていた)。
# push するものが無ければ git push は "Everything up-to-date" で 0 を返す。
commit_all || echo "このステップでのコミットは無し(既存コミットがあれば push する)"

for attempt in 1 2 3 4 5; do
  if git push; then
    echo "pushed (attempt $attempt)"
    exit 0
  fi
  echo "::warning::push が拒否された ($attempt/5)。origin/main に作り直して再試行する"

  # 前回の失敗が rebase 途中を残していても必ず抜ける(従来の壊れ方の後始末)。
  git rebase --abort 2>/dev/null || true
  git merge  --abort 2>/dev/null || true

  # 起点は毎周 merge-base で取り直す。固定値にすると、
  # 割り込んだ相手のコミットを既に取り込んでいる周で「相手の変更を取り消す差分」を
  # 作ってしまい、貼り直した瞬間に相手の仕事を消す(2026-09-07 の T6 で実測)。
  # merge-base が取れない(shallow で共通祖先が無い)ときは HEAD を起点にする。
  # その場合の差分は空になるので、消すのではなく何もしない側に倒れる。
  BASE="$(git merge-base origin/main HEAD 2>/dev/null || git rev-parse HEAD)"

  # このジョブが触ったファイルのうち、生成物でないものだけを取り出す。
  mapfile -t EXC < <(exclude_args)
  PATCH="$(mktemp)"
  # events.json はテキストでなく回と項目の単位で合わせる(merge-events-3way.py の冒頭)。
  # 差分が隣り合うだけで git apply が衝突し、sync-events の取り込みが落ちていた(#111)
  EV_BASE=""; EV_OURS=""
  if ! git diff --quiet "$BASE" HEAD -- events.json 2>/dev/null; then
    EV_BASE="$(mktemp)"; EV_OURS="$(mktemp)"
    git show "$BASE:events.json" > "$EV_BASE"
    git show "HEAD:events.json" > "$EV_OURS"
    EXC+=(":(exclude)events.json")
  fi
  git diff --binary "$BASE" HEAD -- . "${EXC[@]}" > "$PATCH"
  # reset で消える前に、この回の巡回結果を退避する
  SNAP_DIR="$(save_snapshots "$BASE")"

  if ! git fetch -q origin main; then
    echo "::error::origin/main を fetch できない"
    rm -f "$PATCH"; exit 1
  fi
  git reset -q --hard FETCH_HEAD

  if [ -s "$PATCH" ]; then
    if ! git apply --3way --whitespace=nowarn "$PATCH"; then
      echo "::error::データファイルが remote と衝突した。生成物ではないので自動では直せない。手で解消すること"
      git status --short | head -20
      rm -f "$PATCH"; exit 1
    fi
  else
    echo "持ち越すデータ変更なし(生成物だけのコミットだった)"
  fi
  rm -f "$PATCH"

  if [ -n "$EV_OURS" ]; then
    if ! python3 scripts/merge-events-3way.py "$EV_BASE" "$EV_OURS" events.json events.json; then
      echo "::error::events.json の項目単位のマージに失敗した"
      rm -f "$EV_BASE" "$EV_OURS"; exit 1
    fi
    rm -f "$EV_BASE" "$EV_OURS"
  fi

  restore_snapshots "$SNAP_DIR"

  if [ -n "$REGEN" ]; then
    if ! bash -c "$REGEN"; then
      echo "::error::再生成に失敗した: $REGEN"
      exit 1
    fi
  fi

  if ! commit_all; then
    echo "作り直した結果 remote と同じ内容になった。push するものは無い"
    exit 0
  fi

  sleep $(( (RANDOM % 4) + 2 ))
done

echo "::error::push failed after 5 attempts"
exit 1
