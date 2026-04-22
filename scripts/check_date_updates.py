#!/usr/bin/env python3
"""
check_date_updates.py
sourceUrlを持つイベントの公式サイトをチェックし、
日程情報の変更を検出してevents.jsonと詳細ページを自動更新する。

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
EVENTS_JSON = ROOT / "events.json"
EVENTS_DIR = ROOT / "events"

# 日付パターン（日本語）
DATE_PATTERNS = [
    # 2026年5月25日
    re.compile(r'(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日'),
    # 5月25日（日）- 年なし
    re.compile(r'(\d{1,2})\s*月\s*(\d{1,2})\s*日'),
    # 5/25（日）
    re.compile(r'(\d{1,2})\s*/\s*(\d{1,2})\s*[（(]\s*[日月火水木金土]'),
]

HEADERS = {
    "User-Agent": "AgaveNavi-DateChecker/1.0 (+https://agave-navi.com)"
}


def extract_dates_from_text(text, event_name, current_year=None):
    """テキストからイベント名に近い日付を抽出"""
    if not current_year:
        current_year = datetime.now().year

    found = []

    # パターン1: YYYY年M月D日
    for m in DATE_PATTERNS[0].finditer(text):
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            dt = datetime(y, mo, d)
            found.append({"date": dt.strftime("%Y-%m-%d"), "pos": m.start(), "raw": m.group()})
        except ValueError:
            pass

    # パターン2: M月D日（年なし→current_year補完）
    for m in DATE_PATTERNS[1].finditer(text):
        mo, d = int(m.group(1)), int(m.group(2))
        try:
            dt = datetime(current_year, mo, d)
            found.append({"date": dt.strftime("%Y-%m-%d"), "pos": m.start(), "raw": m.group()})
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

    # data-date属性を更新
    content = content.replace(f'data-date="{old_date}"', f'data-date="{new_date}"')

    # Googleカレンダーリンクの日付を更新
    old_gcal = old_date.replace("-", "")
    new_gcal = new_date.replace("-", "")
    old_gcal_end = (datetime.strptime(old_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    new_gcal_end = (datetime.strptime(new_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
    content = content.replace(f"dates={old_gcal}%2F{old_gcal_end}", f"dates={new_gcal}%2F{new_gcal_end}")

    if content != original:
        html_path.write_text(content, encoding="utf-8")
        print(f"  HTML updated: {html_path.name}")
        return True
    else:
        print(f"  HTML: no changes needed")
        return False


def make_date_display(date_str):
    """日付文字列から表示用文字列を生成"""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    weekdays = ["月", "火", "水", "木", "金", "土", "日"]
    wd = weekdays[dt.weekday()]
    return f"{dt.year}年{dt.month}月{dt.day}日（{wd}）"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--slug", help="特定イベントのslugのみチェック")
    parser.add_argument("--dry-run", action="store_true", help="確認のみ（更新しない）")
    args = parser.parse_args()

    with open(EVENTS_JSON, "r", encoding="utf-8") as f:
        events = json.load(f)

    targets = []
    for ev in events:
        if args.slug and ev.get("slug") != args.slug:
            continue
        if not ev.get("sourceUrl"):
            continue
        # Instagram URLはスキップ（日付の構造化データがない）
        if "instagram.com" in ev.get("sourceUrl", ""):
            continue
        targets.append(ev)

    print(f"チェック対象: {len(targets)}件")
    updates = []

    for i, ev in enumerate(targets):
        name = ev.get("name", "")
        slug = ev.get("slug", "")
        source = ev.get("sourceUrl", "")
        current_date = ev.get("date", "")

        print(f"\n[{i+1}/{len(targets)}] {name} ({slug})")
        print(f"  現在: {current_date} / source: {source}")

        html = fetch_page(source)
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(separator=" ", strip=True)

        # 日付抽出
        year = int(current_date[:4]) if current_date else datetime.now().year
        found_dates = extract_dates_from_text(text, name, current_year=year)

        if not found_dates:
            print("  日付パターン見つからず")
            continue

        # 最も関連性の高い日付（イベント名に近い＆未来の日付を優先）
        today = datetime.now().strftime("%Y-%m-%d")
        future_dates = [d for d in found_dates if d["date"] >= today]
        best = future_dates[0] if future_dates else found_dates[0]

        print(f"  検出: {best['date']} ({best['raw']})")

        if best["date"] != current_date:
            print(f"  *** 日程変更検出: {current_date} → {best['date']}")
            new_display = make_date_display(best["date"])

            if not args.dry_run:
                ev["date"] = best["date"]
                ev["dateDisplay"] = new_display
                update_detail_html(slug, current_date, best["date"], new_display)

            updates.append({
                "slug": slug,
                "name": name,
                "old_date": current_date,
                "new_date": best["date"],
                "display": new_display,
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
                f.write(f"updated_count={len(updates)}\n")
                f.write(f"summary={summary.replace(chr(10), '%0A')}\n")


if __name__ == "__main__":
    main()
