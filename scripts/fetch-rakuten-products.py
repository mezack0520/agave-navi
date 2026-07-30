#!/usr/bin/env python3
"""
楽天商品検索APIを叩いて、amazon-links.json の各検索語に対応する実商品を
product-cache.json にキャッシュする。

なぜビルド時に取るのか:
  静的サイトなのでクライアントからAPIを呼ぶとappIdが露出しレート制限も踏む。
  ビルド時に取ってJSONに固めれば、閲覧時はJSONを読むだけで実画像・実価格が出せる。

規約上の注意:
  価格と画像はAPIレスポンス由来のものだけを使う(スクレイピングした値は使わない)。
  価格は変動するため取得時刻を持たせ、表示側で「取得時点」を明示する。

認証(2026-07-01版):
  applicationId と accessKey の両方が必須。accessKey は秘密情報なので
  クライアント側(ブラウザ)からは呼べない。サーバー側でのみ実行する。

使い方:
  RAKUTEN_APP_ID=xxxx RAKUTEN_ACCESS_KEY=yyyy python3 scripts/fetch-rakuten-products.py
  どちらか未設定なら何もせず正常終了する(表示側はテキストリンクにフォールバック)。
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINKS_PATH = os.path.join(REPO_ROOT, 'amazon-links.json')
CACHE_PATH = os.path.join(REPO_ROOT, 'product-cache.json')

# 2026-07-01版。旧 app.rakuten.co.jp/services/api/.../20220601 は
# 新規発行のUUID形式applicationIdを受け付けない(specify valid applicationId)。
API = 'https://openapi.rakuten.co.jp/ichibams/api/IchibaItem/Search/20260701'
SLEEP_SEC = 1.1          # 楽天APIは1秒1リクエスト程度が安全
MIN_PRICE = 300          # 付属品・単品パーツの混入を除く
MAX_PRICE = 200000       # 業務用・セット売りの混入を除く
MIN_REVIEWS = 1          # レビュー0件は当たり外れが大きいので次候補を見る


def collect_keywords(links):
    seen = []
    def add(items):
        for it in items or []:
            kw = it.get('keyword')
            if kw and kw not in seen:
                seen.append(kw)
    add(links.get('common'))
    for v in (links.get('guides') or {}).values():
        add(v)
    for v in (links.get('categories') or {}).values():
        add(v)
    return seen


LAST_ERROR = {}


def _request(url, access_key, referer=None):
    headers = {'User-Agent': 'agave-navi/1.0', 'accessKey': access_key}
    if referer:
        # アプリ種別が Web Application の場合、許可ドメインからのリクエストしか通らない。
        # 自サイト(agave-navi.com)のための自前ビルドからの呼び出しであることを示す。
        headers['Referer'] = referer
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode('utf-8'))


def search(keyword, app_id, access_key, affiliate_id):
    params = {
        'applicationId': app_id,
        'keyword': keyword,
        'hits': 10,
        'imageFlag': 1,
        'sort': '-reviewCount',
        'format': 'json',
        'formatVersion': 2,
        'elements': ','.join([
            'itemName', 'itemPrice', 'itemUrl', 'affiliateUrl',
            'mediumImageUrls', 'shopName', 'reviewCount', 'reviewAverage',
        ]),
    }
    if affiliate_id:
        params['affiliateId'] = affiliate_id
    url = API + '?' + urllib.parse.urlencode(params)
    # accessKey はヘッダで送る(URLに載せるとログや履歴に残るため)。
    # まず素で叩き、拒否されたら Referer 付きで再試行して、どちらで通るかを記録する。
    attempts = [(None, 'no-referer'), ('https://agave-navi.com/', 'with-referer')]
    last = None
    for referer, label in attempts:
        try:
            res = _request(url, access_key, referer)
            LAST_ERROR['succeededWith'] = label
            return res
        except urllib.error.HTTPError as e:
            body = ''
            try:
                body = e.read().decode('utf-8', 'replace')[:200]
            except Exception:
                pass
            last = f'{label}: HTTP {e.code} {body}'
            LAST_ERROR['detail'] = last
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f'{label}: {type(e).__name__} {str(e)[:120]}'
            LAST_ERROR['detail'] = last
    raise RuntimeError(last or 'unknown error')


def pick(items):
    def ok(it):
        p = it.get('itemPrice') or 0
        return MIN_PRICE <= p <= MAX_PRICE and (it.get('reviewCount') or 0) >= MIN_REVIEWS
    for it in items:
        if ok(it):
            return it
    for it in items:
        p = it.get('itemPrice') or 0
        if MIN_PRICE <= p <= MAX_PRICE:
            return it
    return items[0] if items else None


def image_url(it):
    """mediumImageUrls は 128px。_ex を付け替えて表示に足るサイズにする。"""
    urls = it.get('mediumImageUrls') or []
    if not urls:
        return ''
    u = urls[0] if isinstance(urls[0], str) else (urls[0].get('imageUrl') or '')
    return u.replace('_ex=128x128', '_ex=300x300')


def _write_cache(payload):
    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write('\n')


def main():
    try:
        return _run()
    except Exception as e:  # noqa: BLE001
        # ここに来るのは想定外の不具合。診断だけは必ず残す。
        print(f'::error::想定外の例外: {type(e).__name__} {e}')
        try:
            _write_cache({
                '_note': '楽天商品検索APIのキャッシュ(異常終了時)。',
                'updatedAt': datetime.now(JST).isoformat(timespec='seconds'),
                'stats': {'updated': 0, 'failed': 0, 'cached': 0},
                '_diagnostic': {
                    'reason': 'unexpected-exception',
                    'exception': f'{type(e).__name__}: {str(e)[:300]}',
                    'lastError': LAST_ERROR.get('detail'),
                },
                'items': {},
            })
        except OSError:
            pass
        return 0


def _run():
    app_id = os.environ.get('RAKUTEN_APP_ID', '').strip()
    access_key = os.environ.get('RAKUTEN_ACCESS_KEY', '').strip()
    if not app_id or not access_key:
        present = {'RAKUTEN_APP_ID': len(app_id), 'RAKUTEN_ACCESS_KEY': len(access_key)}
        missing = [n for n, v in present.items() if not v]
        msg = f'{" / ".join(missing)} が未設定'
        print(f'{msg}のためスキップ(表示側はテキストリンクにフォールバック)')
        # 何が欠けているかを成果物に残す。書かずに返すと前回の内容が残り原因が追えない。
        now_s = datetime.now(JST).isoformat(timespec='seconds')
        cache_prev = {}
        if os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, encoding='utf-8') as f:
                    cache_prev = (json.load(f).get('items') or {})
            except (OSError, ValueError):
                pass
        with open(CACHE_PATH, 'w', encoding='utf-8') as f:
            json.dump({
                '_note': ('楽天商品検索APIのキャッシュ。'
                          'scripts/fetch-rakuten-products.py が生成。'),
                'updatedAt': now_s,
                'stats': {'updated': 0, 'failed': 0, 'cached': len(cache_prev)},
                '_diagnostic': {
                    'reason': 'credentials-missing',
                    'missing': missing,
                    'lengths': present,
                    'hint': ('GitHub の Settings > Secrets and variables > Actions で '
                             'Repository secrets に登録されているか、名前が完全一致か、'
                             'Variables 側に入っていないかを確認する'),
                },
                'items': cache_prev,
            }, f, ensure_ascii=False, indent=2)
            f.write('\n')
        return 0

    with open(LINKS_PATH, encoding='utf-8') as f:
        links = json.load(f)
    affiliate_id = ((links.get('asp') or {}).get('rakuten') or {}).get('affiliateId', '')

    keywords = collect_keywords(links)
    limit = int(os.environ.get('LIMIT', '0') or 0)
    if limit:
        keywords = keywords[:limit]
    print(f'対象検索語: {len(keywords)}件')

    cache = {}
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding='utf-8') as f:
                cache = (json.load(f).get('items') or {})
        except (OSError, ValueError):
            cache = {}

    now = datetime.now(JST).isoformat(timespec='seconds')
    ok_n = fail_n = 0
    for i, kw in enumerate(keywords, 1):
        try:
            res = search(kw, app_id, access_key, affiliate_id)
            it = pick(res.get('items') or res.get('Items') or [])
            if not it:
                print(f'  [{i}/{len(keywords)}] {kw}: 該当なし')
                fail_n += 1
                time.sleep(SLEEP_SEC)
                continue
            img = image_url(it)
            if not img:
                print(f'  [{i}/{len(keywords)}] {kw}: 画像なしのため採用せず')
                fail_n += 1
                time.sleep(SLEEP_SEC)
                continue
            cache[kw] = {
                'name': (it.get('itemName') or '')[:90],
                'price': it.get('itemPrice'),
                'image': img,
                'shop': it.get('shopName') or '',
                'url': it.get('affiliateUrl') or it.get('itemUrl') or '',
                'reviewCount': it.get('reviewCount') or 0,
                'reviewAverage': it.get('reviewAverage') or 0,
                'fetchedAt': now,
            }
            ok_n += 1
            print(f'  [{i}/{len(keywords)}] {kw}: '
                  f'{cache[kw]["name"][:34]} / {cache[kw]["price"]}円')
        except Exception as e:  # noqa: BLE001 — 1件の失敗で全体を止めない
            print(f'  [{i}/{len(keywords)}] {kw}: 取得失敗 {type(e).__name__} {e}')
            LAST_ERROR.setdefault('detail', f'{type(e).__name__}: {e}')
            fail_n += 1
        time.sleep(SLEEP_SEC)

    payload = {
        '_note': ('楽天商品検索APIのキャッシュ。scripts/fetch-rakuten-products.py が生成。'
                  '手で編集しても次回実行で上書きされる。'),
        'updatedAt': now,
        'stats': {'updated': ok_n, 'failed': fail_n, 'cached': len(cache)},
        'items': cache,
    }
    # 全滅したときは原因を残す。Actionsのログを読めない状況でも追跡できるようにする。
    if ok_n == 0:
        payload['_diagnostic'] = {
            'endpoint': API,
            'appIdLength': len(app_id),
            'accessKeyLength': len(access_key),
            'affiliateIdSet': bool(affiliate_id),
            'lastError': LAST_ERROR.get('detail', '(記録なし)'),
            'succeededWith': LAST_ERROR.get('succeededWith'),
        }

    with open(CACHE_PATH, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'完了: 更新{ok_n}件 / 失敗{fail_n}件 / キャッシュ総数{len(cache)}件')
    if ok_n == 0:
        print(f'::error::楽天APIから1件も取得できませんでした: {LAST_ERROR.get("detail")}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
