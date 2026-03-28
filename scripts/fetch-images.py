#!/usr/bin/env python3
"""
fetch-images.py — 全イベントのOGP画像を公式サイトから取得し、サムネイル・ヒーロー画像として保存する。

使い方:
  python3 scripts/fetch-images.py

動作:
  1. events.json を読み込み
  2. 各イベントの sourceUrl / organizerUrl / imageUrl にアクセス
  3. OGP画像（og:image）を探す
  4. 画像をダウンロードし、thumb (400x300) と hero (1200x600) にリサイズして保存
  5. プレースホルダーのままのイベントをレポート出力

注意:
  - Instagram URLからは画像取得不可（ログイン必要）→ プレースホルダーのまま
  - 既にユニークな画像がある場合はスキップ（プレースホルダーかどうかで判定）
"""

import json
import os
import sys
import hashlib
import re
import urllib.request
import urllib.error
from pathlib import Path

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("WARNING: Pillow not installed. Images will be saved without resizing.")

# Paths
SCRIPT_DIR = Path(__file__).parent
REPO_DIR = SCRIPT_DIR.parent
EVENTS_JSON = REPO_DIR / "events.json"
IMAGES_DIR = REPO_DIR / "images" / "events"
DEFAULT_IMG = REPO_DIR / "images" / "ogp-default.jpg"

# Placeholder hash (ogp-default.jpg)
def get_file_hash(path):
    if not path.exists():
        return None
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

PLACEHOLDER_HASH = get_file_hash(DEFAULT_IMG)

def is_placeholder(path):
    """Check if an image is the placeholder (ogp-default.jpg)."""
    if not path.exists():
        return True
    return get_file_hash(path) == PLACEHOLDER_HASH

def fetch_url(url, timeout=15):
    """Fetch URL content with proper headers."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (compatible; AgaveNaviBot/1.0)',
        'Accept': 'text/html,application/xhtml+xml,*/*',
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get('Content-Type', '')
    except Exception as e:
        return None, str(e)

def extract_ogp_image(html_bytes, base_url):
    """Extract og:image URL from HTML."""
    try:
        html = html_bytes.decode('utf-8', errors='replace')
    except:
        return None

    # Try og:image
    match = re.search(r'<meta\s+(?:property|name)=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
    if not match:
        match = re.search(r'<meta\s+content=["\']([^"\']+)["\']\s+(?:property|name)=["\']og:image["\']', html, re.IGNORECASE)

    if match:
        img_url = match.group(1)
        # Handle relative URLs
        if img_url.startswith('//'):
            img_url = 'https:' + img_url
        elif img_url.startswith('/'):
            from urllib.parse import urlparse
            parsed = urlparse(base_url)
            img_url = f"{parsed.scheme}://{parsed.netloc}{img_url}"
        return img_url
    return None

def download_image(url, save_path):
    """Download image and optionally resize."""
    data, content_type = fetch_url(url, timeout=20)
    if not data:
        return False

    # Save raw first
    tmp_path = save_path.with_suffix('.tmp')
    with open(tmp_path, 'wb') as f:
        f.write(data)

    if HAS_PIL:
        try:
            img = Image.open(tmp_path)
            img = img.convert('RGB')
            img.save(save_path, 'JPEG', quality=85)
            tmp_path.unlink()
            return True
        except Exception as e:
            # If PIL can't open it, keep raw
            tmp_path.rename(save_path)
            return True
    else:
        tmp_path.rename(save_path)
        return True

def resize_for_thumb(src_path, dst_path, size=(400, 300)):
    """Create thumbnail version."""
    if not HAS_PIL:
        import shutil
        shutil.copy2(src_path, dst_path)
        return
    try:
        img = Image.open(src_path)
        img = img.convert('RGB')
        img.thumbnail(size, Image.LANCZOS)
        img.save(dst_path, 'JPEG', quality=85)
    except:
        import shutil
        shutil.copy2(src_path, dst_path)

def resize_for_hero(src_path, dst_path, size=(1200, 600)):
    """Create hero version."""
    if not HAS_PIL:
        import shutil
        shutil.copy2(src_path, dst_path)
        return
    try:
        img = Image.open(src_path)
        img = img.convert('RGB')
        # Crop to aspect ratio then resize
        target_ratio = size[0] / size[1]
        img_ratio = img.width / img.height
        if img_ratio > target_ratio:
            new_w = int(img.height * target_ratio)
            left = (img.width - new_w) // 2
            img = img.crop((left, 0, left + new_w, img.height))
        else:
            new_h = int(img.width / target_ratio)
            top = (img.height - new_h) // 2
            img = img.crop((0, top, img.width, top + new_h))
        img = img.resize(size, Image.LANCZOS)
        img.save(dst_path, 'JPEG', quality=85)
    except:
        import shutil
        shutil.copy2(src_path, dst_path)

def process_event(ev):
    """Process a single event: fetch OGP image if needed."""
    slug = ev['slug']
    thumb_path = IMAGES_DIR / f"{slug}-thumb.jpg"
    hero_path = IMAGES_DIR / f"{slug}-hero.jpg"

    # Skip if already has real images
    if not is_placeholder(thumb_path) and not is_placeholder(hero_path):
        return 'exists', slug

    # Try imageUrl first (direct image URL from events.json)
    image_url = ev.get('imageUrl', '')
    if image_url:
        tmp_path = IMAGES_DIR / f"{slug}-raw.tmp"
        if download_image(image_url, tmp_path):
            resize_for_thumb(tmp_path, thumb_path)
            resize_for_hero(tmp_path, hero_path)
            tmp_path.unlink(missing_ok=True)
            return 'fetched_direct', slug

    # Try sourceUrl (fetch page and extract OGP)
    source_url = ev.get('sourceUrl', '') or ev.get('organizerUrl', '')
    if not source_url or 'instagram.com' in source_url:
        return 'skip_instagram', slug

    html_data, _ = fetch_url(source_url)
    if not html_data:
        return 'fetch_failed', slug

    ogp_url = extract_ogp_image(html_data, source_url)
    if not ogp_url:
        return 'no_ogp', slug

    tmp_path = IMAGES_DIR / f"{slug}-raw.tmp"
    if download_image(ogp_url, tmp_path):
        resize_for_thumb(tmp_path, thumb_path)
        resize_for_hero(tmp_path, hero_path)
        tmp_path.unlink(missing_ok=True)
        return 'fetched_ogp', slug

    return 'download_failed', slug

def ensure_placeholder(ev):
    """Ensure placeholder images exist for events without real images."""
    slug = ev['slug']
    thumb_path = IMAGES_DIR / f"{slug}-thumb.jpg"
    hero_path = IMAGES_DIR / f"{slug}-hero.jpg"

    import shutil
    if not thumb_path.exists():
        shutil.copy2(DEFAULT_IMG, thumb_path)
    if not hero_path.exists():
        shutil.copy2(DEFAULT_IMG, hero_path)

def main():
    with open(EVENTS_JSON, 'r', encoding='utf-8') as f:
        events = json.load(f)

    upcoming = [e for e in events if e.get('status') == 'upcoming']

    results = {
        'exists': [],
        'fetched_direct': [],
        'fetched_ogp': [],
        'skip_instagram': [],
        'fetch_failed': [],
        'no_ogp': [],
        'download_failed': [],
    }

    print(f"Checking {len(upcoming)} upcoming events...")
    for ev in upcoming:
        status, slug = process_event(ev)
        results[status].append(slug)
        ensure_placeholder(ev)

        icon = {'exists': '✓', 'fetched_direct': '⬇', 'fetched_ogp': '⬇',
                'skip_instagram': '📷', 'fetch_failed': '✗', 'no_ogp': '○',
                'download_failed': '✗'}
        print(f"  {icon.get(status, '?')} {slug}: {status}")

    # Summary
    print(f"\n=== 画像取得レポート ===")
    print(f"既存画像あり: {len(results['exists'])}件")
    print(f"新規取得（直接URL）: {len(results['fetched_direct'])}件")
    print(f"新規取得（OGP）: {len(results['fetched_ogp'])}件")
    print(f"Instagram（取得不可）: {len(results['skip_instagram'])}件")

    failed = results['fetch_failed'] + results['no_ogp'] + results['download_failed']
    if failed:
        print(f"取得失敗: {len(failed)}件")
        for s in failed:
            print(f"  - {s}")

    # Return counts for scripting
    return results

if __name__ == '__main__':
    main()
