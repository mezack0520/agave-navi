#!/usr/bin/env python3
"""audit.py — パイプライン全体の「黙って落ちているもの」を洗い出す。

作った目的(2026-07-30):
  各スクリプトが成功件数だけを出力し、除外・欠落・孤児を黙っていたため、
  問題が人に指摘されるまで表面化しなかった。存在確認ではなく整合確認を毎日回す。

読み取り専用。何も変更しない。検出結果を JSON とテキストで出す。
終了コードは常に0(検出は失敗ではない)。件数は日次メールに載せる。
"""
import json
import os
import re
import glob
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rp(*a):
    return os.path.join(REPO, *a)


def load_json(path, default=None):
    try:
        with open(rp(path), encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default if default is not None else {}


def main():
    events = load_json('events.json', [])
    findings = {}

    def add(key, title, items, note=''):
        findings[key] = {'title': title, 'count': len(items),
                         'items': items[:40], 'note': note}

    slugs = [e.get('slug') for e in events]
    slug_set = set(slugs)

    # 1. slug重複
    dup = sorted({s for s in slugs if slugs.count(s) > 1})
    add('duplicate_slugs', 'events.json内のslug重複', dup)

    # 2. 同名同日で別slug(実質重複掲載)
    seen = defaultdict(list)
    for e in events:
        k = ((e.get('name') or '').strip(), e.get('date') or '')
        if k[0] and k[1]:
            seen[k].append(e.get('slug'))
    add('duplicate_name_date', '同名・同日で別slug(二重掲載の疑い)',
        [f'{n} {d}: ' + ', '.join(v) for (n, d), v in seen.items() if len(v) > 1])

    # 3. 詳細ページの孤児と欠落
    files = {os.path.basename(f)[:-5] for f in glob.glob(rp('events', '*.html'))}
    add('orphan_detail_pages', 'events.jsonに無いのに残っている詳細ページ',
        sorted(files - slug_set))
    add('missing_detail_pages', 'events.jsonにあるのに詳細ページが無い',
        sorted(slug_set - files))

    # 4. sitemapの整合
    sm = ''
    try:
        with open(rp('sitemap.xml'), encoding='utf-8') as f:
            sm = f.read()
    except OSError:
        pass
    sm_urls = re.findall(r'<loc>\s*([^<\s]+)\s*</loc>', sm)
    bad_sm = []
    for u in sm_urls:
        path = re.sub(r'^https?://[^/]+/?', '', u)
        if not path:
            continue
        local = rp(path if path.endswith('.html') else os.path.join(path, 'index.html'))
        if not os.path.exists(local):
            bad_sm.append(path)
    add('sitemap_dead_entries', 'sitemapに載っているがファイルが存在しないURL', sorted(bad_sm))

    # 5. rejected-eventsとevents.jsonの矛盾
    rej = load_json('rejected-events.json', {})
    rej_keys = [i.get('key', '') for i in (rej.get('items') or [])]
    conflict = [k for k in rej_keys if k and any(k in s for s in slug_set)]
    add('rejected_but_listed', '見送り記録があるのに掲載されているイベント', conflict)

    # 6. ウォッチ対象に載らない回
    watch = load_json('watch-sources.json', {})
    add('unresolved_ig_handles', 'IGのURLはあるが主催者ハンドルが取れずウォッチ対象外',
        [u.get('slug') for u in (watch.get('unresolvedIgHandles') or [])],
        'organizerIg を入れれば解消する')

    # 7. 薄い判定(noindex かつ収益枠なし)
    def is_thin(e):
        d = e.get('description') or ''
        has_src = bool((e.get('url') or '').strip()) or bool((e.get('sourceUrl') or '').strip())
        subs = (bool((e.get('time') or '').strip()) or bool((e.get('imageUrl') or '').strip())
                or len(d) >= 50)
        return not (has_src and subs)

    # 薄い判定を「直すべきもの」と「アーカイブとして許容するもの」に分ける。
    # 終了済みで出典もない回は、noindexで検索に出ず広告も出ないアーカイブであり、
    # 裏取りできない=誤りではない。全件を毎日警告すると監査が無視されるようになる。
    today_s = os.environ.get('AUDIT_TODAY') or __import__('datetime').date.today().isoformat()

    def has_src(e):
        return bool((e.get('url') or '').strip()) or bool((e.get('sourceUrl') or '').strip())

    def is_future(e):
        return (e.get('dateEnd') or e.get('date') or '') >= today_s

    thin_all = [e for e in events if is_thin(e)]
    add('thin_fixable', '薄い判定のうち直せるもの(出典あり・説明文を50字以上にすれば解消)',
        sorted(f"{e['slug']}({len((e.get('description') or '').strip())}字"
               f"{'・開催予定' if is_future(e) else ''})"
               for e in thin_all if has_src(e)),
        '開催予定のものから優先する')
    add('thin_archived', '薄い判定のうちアーカイブ許容(終了済み・出典なし)',
        sorted(e['slug'] for e in thin_all if not has_src(e) and not is_future(e)),
        '検索に出ず広告も出ない履歴データ。対処不要')
    add('thin_needs_source', '薄い判定で開催予定なのに出典がない(要対処)',
        sorted(e['slug'] for e in thin_all if not has_src(e) and is_future(e)),
        '一次情報を見つけるか、見つからなければ掲載基準により削除')

    # 8. 説明文が短い開催予定
    add('short_descriptions', '開催予定で説明文70字未満(SERPスニペット枠を使い切れない)',
        sorted(f"{e['slug']}({len((e.get('description') or '').strip())}字)"
               for e in events
               if e.get('status') == 'upcoming' and len((e.get('description') or '').strip()) < 70))

    # 9. status と日付の矛盾
    today = os.environ.get('AUDIT_TODAY') or __import__('datetime').date.today().isoformat()
    mism = []
    for e in events:
        end = e.get('dateEnd') or e.get('date') or ''
        st = e.get('status')
        if not end:
            continue
        if end < today and st == 'upcoming':
            mism.append(f"{e['slug']}: 終了済みだが status=upcoming")
        if end >= today and st == 'past':
            mism.append(f"{e['slug']}: 未来だが status=past")
    add('status_date_mismatch', 'statusと日付の矛盾', sorted(mism))

    # 10. 配布フィードの件数整合
    feed = {}
    try:
        # 行数ではなくCSVレコード数で数える(引用符内の改行で誤検知するため)
        import csv as _csv
        with open(rp('events.csv'), encoding='utf-8-sig', newline='') as f:
            feed['csv'] = max(0, sum(1 for _ in _csv.reader(f)) - 1)
    except OSError:
        pass
    try:
        with open(rp('events.ics'), encoding='utf-8') as f:
            feed['ics'] = f.read().count('BEGIN:VEVENT')
    except OSError:
        pass
    add('feed_count_mismatch', '配布フィードの件数がevents.jsonと不一致',
        [f'{k}: {v}件 (events.json {len(events)}件)'
         for k, v in feed.items() if v != len(events)])

    # 11. ガイド記事リンクの死活(詳細ページから貼っているガイド)
    guide_files = {os.path.basename(f) for f in glob.glob(rp('guides', '*.html'))}
    try:
        with open(rp('build-detail-pages.py'), encoding='utf-8') as f:
            src = f.read()
        linked = re.findall(r"\('([a-z0-9\-]+\.html)',\s*'", src)
    except OSError:
        linked = []
    add('dead_guide_links', '詳細ページから貼っているガイドが存在しない',
        sorted(set(linked) - guide_files))

    # 12. CSS版数の乖離
    try:
        sys.path.insert(0, rp('scripts'))
        import sitelib
        want = sitelib.CSS_VERSION
    except Exception:
        want = None
    drift = []
    if want:
        for f in glob.glob(rp('**', '*.html'), recursive=True):
            if '/.git/' in f or '/templates/' in f:
                continue
            try:
                h = open(f, encoding='utf-8').read()
            except OSError:
                continue
            for m in re.finditer(r'style\.css(\?v=([0-9a-zA-Z]*))?', h):
                if (m.group(2) or '') != want:
                    drift.append(os.path.relpath(f, REPO))
                    break
    add('css_version_drift', f'CSS版数が正規値({want})と違うページ', sorted(set(drift)),
        'sync-footers.py が正規化する')

    # 13b. JS版数の乖離。版数が付いていないと変更が閲覧者のキャッシュに届かない。
    want_js = None
    try:
        want_js = sitelib.JS_VERSION
    except Exception:
        pass
    js_drift = []
    if want_js:
        jsre = re.compile(r'((?:affiliate|ads|status-auto)\.js)(\?v=([0-9a-zA-Z]*))?')
        for f in glob.glob(rp('**', '*.html'), recursive=True):
            if '/.git/' in f or '/templates/' in f:
                continue
            try:
                h = open(f, encoding='utf-8').read()
            except OSError:
                continue
            for m in jsre.finditer(h):
                if (m.group(3) or '') != want_js:
                    js_drift.append(os.path.relpath(f, REPO))
                    break
    add('js_version_drift', f'JS版数が正規値({want_js})と違う/付いていないページ',
        sorted(set(js_drift)),
        '版数なしだとJSの変更がキャッシュを越えず届かない')

    # 13. build-all.sh から呼ばれていないスクリプト(死んだ資産)
    try:
        with open(rp('scripts', 'build-all.sh'), encoding='utf-8') as f:
            ba = f.read()
    except OSError:
        ba = ''
    wf = ''
    for f in glob.glob(rp('.github', 'workflows', '*.yml')):
        wf += open(f, encoding='utf-8').read()
    unused = []
    for f in sorted(glob.glob(rp('scripts', '*.py'))) + [rp('build-detail-pages.py')]:
        bn = os.path.basename(f)
        if bn in ('sitelib.py', 'audit.py'):
            continue
        if bn not in ba and bn not in wf:
            unused.append(bn)
    add('unreferenced_scripts', 'build-all.shもworkflowも参照していないスクリプト',
        unused, '使われていないか、呼び出しが失われている')

    # 14. workflowが参照するsecretの一覧(未設定だと黙って空になる)
    add('workflow_secrets', 'workflowが参照しているsecret',
        sorted(set(re.findall(r'secrets\.([A-Z_][A-Z0-9_]*)', wf))),
        '未設定でも多くのstepは失敗せず黙って空値で動く')

    # 15. 楽天商品キャッシュの網羅率
    links = load_json('amazon-links.json', {})
    kws = set()
    for it in (links.get('common') or []):
        kws.add(it.get('keyword'))
    for grp in ('guides', 'categories'):
        for v in (links.get(grp) or {}).values():
            for it in v:
                kws.add(it.get('keyword'))
    # 楽天は2026-07-30からブラウザ側で都度取得+localStorageキャッシュに移行した。
    # サーバー側の事前キャッシュは403で不可のため、ここでは設定の有無だけ検査する。
    rk = (links.get('asp') or {}).get('rakuten') or {}
    missing_cfg = [k for k in ('applicationId', 'accessKey', 'apiEndpoint', 'affiliateId')
                   if not rk.get(k)]
    add('rakuten_config_missing', '楽天API設定の欠落(欠けると商品画像が出ずテキスト表示になる)',
        missing_cfg, f'検索語 {len([k for k in kws if k])} 件がこの設定に依存する')

    # --- 出力 ---
    total = sum(v['count'] for k, v in findings.items()
                if k not in ('workflow_secrets',))
    with open(rp('audit-results.json'), 'w', encoding='utf-8') as f:
        json.dump({'total': total, 'findings': findings}, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f'=== 監査結果: 検出 {total}件 ===')
    for k, v in findings.items():
        mark = '  ' if v['count'] == 0 else '⚠ '
        print(f"{mark}{v['title']}: {v['count']}")
        if v['count'] and k != 'workflow_secrets':
            for it in v['items'][:6]:
                print(f'      - {it}')
            if v['count'] > 6:
                print(f'      … 他{v["count"] - 6}件')
        elif k == 'workflow_secrets':
            print('      ' + ', '.join(v['items']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
