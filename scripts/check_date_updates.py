#!/usr/bin/env python3
"""
check_date_updates.py
sourceUrlを持つイベントの公式サイトをチェックし、
日程情報の変更を検出してevents.json・詳細ページ・一覧ページ(index.html)を自動更新する。

Usage:
  python scripts/check_date_updates.py              # 全イベントをチェック
  python scripts/check_date_updates.py --slug XXX   # 特定イベントのみ
  python scripts/check_date_updates.py --dry-run    # 確認のみ（更新しない）
"""

import json
import re
import sys
import os
import argparse
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4"])
    import requests
    from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent

AGGREGATOR_BLOCKLIST = (
    'nextmeet.app', 'botanical-zone.tokyo', 'leaf-laboratory.com',
    'tochinavi.net', 'pukubook.jp', 'fukuoka-now.com', 'churatoku.net', 'agavemaniacs.com',
)


def is_aggregator(url):
    if not url: return False
    return any(ag in url.lower() for ag in AGGREGATOR_BLOCKLIST)


EVENTS_JSON = ROOT / "events.json"
EVENTS_DIR = ROOT / "events"
INDEX_HTML = ROOT / "index.html"

# 日付パターン（日本語）
DATE_PATTERNS = [
    # 2026年5月25日
    re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'),
    # 5月25日（日）- 年なし
    re.compile(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日'),
    # 5/25（日）
    re.compile(r'(\d{1,2})/(\d{1,2})\s*[（(]\s*[日月火水木金土]'),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; AgaveNaviBot/1.0)"
}

WEEKDAY_MAP = ["月", "火", "水", "木", "金", "土", "日"]


def extract_dates(text, event_name, current_year=None):
    """テキストから日付候補を抽出"""
    if current_year is None:
        current_year = datetime.now().year

    found = []

    # パターン1: YYYY年M月D日
    for m in DATE_PATTERNS[0].finditer(text):
        try:
            d = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            found.append({"date": d.strftime("%Y-%m-%d"), "pos": m.start()})
        except ValueError:
            pass

    # パターン2: M月D日
    for m in DATE_PATTERNS[1].finditer(text):
        try:
            month, day = int(m.group(1)), int(m.group(2))
            d = datetime(current_year, month, day)
            found.append({"date": d.strftime("%Y-%m-%d"), "pos": m.start()})
        except ValueError:
            pass

    # パターン3: M/D（曜日）
    for m in DATE_PATTERNS[2].finditer(text):
        try:
            month, day = int(m.group(1)), int(m.group(2))
            d = datetime(current_year, month, day)
            found.append({"date": d.strftime("%Y-%m-%d"), "pos": m.start()})
        except ValueError:
            pass

    # イベント名に最も近い日付を優先
    if not found:
        return []

    # イベント名の位置を探す
    name_pos = text.find(event_name)
    if name_pos == -1:
        # 部分一致を試す
        short_name = event_name[:min(len(event_name), 10)]
        name_pos = text.find(short_name)

    if name_pos >= 0:
        found.sort(key=lambda x: abs(x["pos"] - name_pos))

    return found


def fetch_page(url, timeout=15):
    """URLからページ内容を取得"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as e:
        print(f"  fetch error: {e}")
        return None


def update_detail_html(slug, old_date, new_date, new_display):
    """詳細ページHTMLの日付を更新"""
    html_path = EVENTS_DIR / f"{slug}.html"
    if not html_path.exists():
        print(f"  HTML not found: {html_path}")
        return False

    content = html_path.read_text(encoding="utf-8")
    original = content

    # data-date属性の更新
    content = content.replace(f'data-date="{old_date}"', f'data-date="{new_date}"')

    # 表示日付の更新（複数パターン対応）
    old_dt = datetime.strptime(old_date, "%Y-%m-%d")
    new_dt = datetime.strptime(new_date, "%Y-%m-%d")

    # Google Calendar リンクの日付更新
    old_cal = old_dt.strftime("%Y%m%d")
    new_cal = new_dt.strftime("%Y%m%d")
    content = content.replace(old_cal, new_cal)

    # 日本語表示の更新パターン
    old_patterns = [
        f"{old_dt.year}年{old_dt.month}月{old_dt.day}日",
        f"{old_dt.year}年{old_dt.month}月（日程未確定）",
        f"{old_dt.year}.{old_dt.month:02d} (日曜)",
        f"{old_dt.year}.{old_dt.month:02d}",
    ]
    for p in old_patterns:
        if p in content:
            content = content.replace(p, new_display)

    if content != original:
        html_path.write_text(content, encoding="utf-8")
        print(f"  ✅ 詳細ページ更新: {html_path.name}")
        return True
    else:
        print(f"  ⚠ 詳細ページ変更なし: {html_path.name}")
        return False


def update_index_html(slug, old_date, new_date, new_display):
    """一覧ペーズ(index.html)のイベントカード日付を更新"""
    if not INDEX_HTML.exists():
        print(f"  index.html not found")
        return False

    content = INDEX_HTML.read_text(encoding="utf-8")
    original = content

    old_dt = datetime.strptime(old_date, "%Y-%m-%d")
    new_dt = datetime.strptime(new_date, "%Y-%m-%d")

    # 1) data-date属性の更新（slugの近くにあるものだけ対象）
    # data-date="2026-05-01" data-slug="gotanda-big-bazaar-2026-05"
    pattern_data_date = re.compile(
        r'(data-date=")' + re.escape(old_date) + r'("[\s\S]{0,50}data-slug="' + re.escape(slug) + r'")'
    )
    content = pattern_data_date.sub(r'\g<1>' + new_date + r'\g<2>', content)

    # 2) JSON-LD内の startDate更新（slugのURL近くにあるもの）
    # "startDate":"2026-05-01",...,"url":"...gotanda-big-bazaar-2026-05.html"
    old_jsonld = f'"startDate":"{old_date}"'
    new_jsonld = f'"startDate":"{new_date}"'
    # slug付近のstartDateのみ置換
    slug_url = f'{slug}.html'
    # Find all occurrences of the slug in JSON-LD context and replace nearby startDate
    pos = 0
    while True:
        slug_pos = content.find(slug_url, pos)
        if slug_pos == -1:
            break
        # Look backwards for startDate within 300 chars
        search_start = max(0, slug_pos - 300)
        chunk = content[search_start:slug_pos]
        sd_pos = chunk.rfind(old_jsonld)
        if sd_pos != -1:
            abs_pos = search_start + sd_pos
            content = content[:abs_pos] + new_jsonld + content[abs_pos + len(old_jsonld):]
        pos = slug_pos + len(slug_url)

    # 3) event-dateテキストの更新（slugカード内）
    # Find the card for this slug and update the event-date span
    card_pattern = re.compile(
        r'(data-slug="' + re.escape(slug) + r'"[\s\S]*?<span class="event-date">)'
        r'([^<]+)'
        r'(</span>)',
        re.DOTALL
    )
    match = card_pattern.search(content)
    if match:
        # dateDisplay形式に変換: "2026.05.25" or "2026年5月25日（日）"
        weekday = WEEKDAY_MAP[new_dt.weekday()]
        card_date_display = f"{new_dt.year}.{new_dt.month:02d}.{new_dt.day:02d}"
        content = content[:match.start(2)] + card_date_display + content[match.end(2):]

    if content != original:
        INDEX_HTML.write_text(content, encoding="utf-8")
        print(f"  ✅ 一覧ページ(index.html)更新")
        return True
    else:
        print(f"  ⚠ 一覧ページ変更なし")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="特定イベントのslugのみチェック")
    parser.add_argument("--dry-run", action="store_true", help="確認のみ（更新しない）")
    args = parser.parse_args()

    with open(EVENTS_JSON, "r", encoding="utf-8") as f:
        events = json.load(f)

    targets = []
    recurring_targets = []
    for ev in events:
        if args.slug and ev.get("slug") != args.slug:
            continue
        if not ev.get("sourceUrl"):
            continue
        # Instagram URLはスキップ（日付の構造化データがない）
        if "instagram.com" in ev.get("sourceUrl", ""):
            continue
        # 定期開催イベントは優先チェック（過去イベントも含む）
        if ev.get("recurring"):
            recurring_targets.append(ev)
        else:
            targets.append(ev)

    # 定期開催イベントを先頭に配置（優先チェック）
    targets = recurring_targets + targets
    print(f"チェック対象: {len(targets)}件（うち定期開催: {len(recurring_targets)}件）")
    updates = []

    for i, ev in enumerate(targets):
        name = ev.get("name", "")
        slug = ev.get("slug", "")
        source = ev.get("sourceUrl", "")
        if is_aggregator(source):
            continue
        current_date = ev.get("date", "")

        print(f"\n[{i+1}/{len(targets)}] {name} ({slug})")
        print(f"  現在: {current_date} / source: {source}")

        html = fetch_page(source)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator="\n")

        dates = extract_dates(text, name)
        if not dates:
            print("  日付抽出できず")
            continue

        best = dates[0]
        print(f"  検出: {best['date']}")

        if best["date"] != current_date:
            print(f"  ⚡ 日程変更検出: {current_date} → {best['date']}")

            if not args.dry_run:
                # events.json更新
                new_dt = datetime.strptime(best["date"], "%Y-%m-%d")
                weekday = WEEKDAY_MAP[new_dt.weekday()]
                new_display = f"{new_dt.year}年{new_dt.month}月{new_dt.day}日（{weekday}）"

                ev["date"] = best["date"]
                ev["dateDisplay"] = new_display

                # 詳細ページ更新
                update_detail_html(slug, current_date, best["date"], new_display)

                # 一覧ページ(index.html)更新
                update_index_html(slug, current_date, best["date"], new_display)

            updates.append({
                "slug": slug,
                "name": name,
                "old_date": current_date,
                "new_date": best["date"],
                "display": new_display if not args.dry_run else best["date"],
            })
        else:
            print("  日程変更なし")

    # events.json保存
    if updates and not args.dry_run:
        with open(EVENTS_JSON, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"\n✅ {len(updates)}件の日程を更新しました")
    else:
        print(f"\n更新: {len(updates)}件 (dry-run: {args.dry_run})")

    # 結果をJSON出力（GitHub Actionsのsummary用）
    if updates:
        summary = "\n".join([f"- {u['name']}: {u['old_date']} → {u['new_date']}" for u in updates])
        print(f"\n--- 変更サマリー ---\n{summary}")

        # GitHub Actions output
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"updated=true\n")
                f.write(f"count={len(updates)}\n")


if __name__ == "__main__":
    main()
