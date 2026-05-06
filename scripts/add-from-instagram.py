#!/usr/bin/env python3
"""
add-from-instagram.py — IG投稿URL → new-events.json に stub entry 追加。
詳細(name/date/venue/etc)は翌火曜の enrich-events で Brave検索 + 公式site 経由で補完される。

Usage:
  python3 scripts/add-from-instagram.py <ig_url> [hint_name]
"""
import json, os, re, sys, requests
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = os.path.join(ROOT, 'new-events.json')

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'

def parse(url):
    m = re.match(r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)', url)
    if not m: return None
    return m.group(1)

def fetch_og(url):
    """IG投稿のog metaを取れる範囲で取得"""
    try:
        r = requests.get(url, headers={'User-Agent': UA}, timeout=10, allow_redirects=True)
        if r.status_code != 200:
            return {}
        title = re.search(r'<meta property="og:title" content="([^"]+)"', r.text)
        desc = re.search(r'<meta property="og:description" content="([^"]+)"', r.text)
        image = re.search(r'<meta property="og:image" content="([^"]+)"', r.text)
        return {
            'title': (title.group(1) if title else '').strip(),
            'desc': (desc.group(1) if desc else '').strip(),
            'image': (image.group(1) if image else '').strip(),
        }
    except Exception as e:
        print(f'fetch error: {e}')
        return {}

def main():
    if len(sys.argv) < 2:
        print('Usage: add-from-instagram.py <ig_url> [hint_name]'); sys.exit(1)
    url = sys.argv[1].strip()
    hint = sys.argv[2].strip() if len(sys.argv) >= 3 else ''
    post_id = parse(url)
    if not post_id:
        print(f'::error::Invalid IG URL: {url}'); sys.exit(1)

    canonical_url = f'https://www.instagram.com/p/{post_id}/'
    og = fetch_og(canonical_url)

    # name: hint > og:title > placeholder
    name = hint or og.get('title') or f'(未確定) IG投稿 {post_id}'
    name = name[:80]

    # slug: name から生成、ASCII化、最大40文字
    import unicodedata
    base = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii').lower()
    base = re.sub(r'[^a-z0-9]+', '-', base).strip('-')
    if not base or len(base) < 4:
        base = f'ig-{post_id.lower()}'
    slug = f'{base[:35]}-{post_id[:6].lower()}'

    today = date.today().isoformat()
    stub = {
        'slug': slug,
        'name': name,
        'date': '',  # enrich 時に補完
        'dateEnd': '',
        'dateDisplay': '近日開催',
        'venue': '調整中',
        'mapQuery': '調整中',
        'prefecture': '',
        'region': '',
        'description': (og.get('desc') or '')[:300] or 'Instagram投稿で告知されたイベント。詳細は公式投稿をご確認ください。',
        'tags': ['即売会'],
        'status': 'upcoming',
        'eventStatus': 'confirmed',
        'addedDate': today,
        'instagramUrl': canonical_url,
        'instagramPostId': post_id,
    }
    if og.get('image'):
        stub['imageUrl'] = og['image']

    # Append to new-events.json (or create)
    if os.path.exists(NEW):
        with open(NEW, encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = []
    if not isinstance(data, list):
        data = [data]
    data.append(stub)
    with open(NEW, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2); f.write('\n')
    print(f'Added stub: slug={slug}, name="{name}", instagramPostId={post_id}')

if __name__ == '__main__':
    main()
