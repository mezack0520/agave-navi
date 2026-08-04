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
sys.path.insert(0, os.path.join(REPO, 'scripts'))
from sitelib import today_jst


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

    # 4b. sitemapに noindex 頁が載っていないか(生成順の崩れの検出)。
    #     health.yml の image health ステップは build-detail-pages.py と sync-index-cards.py
    #     だけを再実行して sitemap を作り直さない。終了30日超に入った回が noindex になっても
    #     sitemap には翌朝の daily.yml まで載り続ける(2026-08-04 に4件で発生)。
    #     build-all.sh 経由なら常に0。単独実行したときだけ意味を持つ検査。
    noindexed = []
    for _m in ('events-meta.json', 'landing-meta.json'):
        _d = load_json(rp('scripts', _m), {}) or {}
        noindexed += list(_d.get('noindex') or [])
    _ni = set(noindexed)
    sm_ni = []
    for u in sm_urls:
        path = re.sub(r'^https?://[^/]+/?', '', u)
        base = os.path.basename(path)[:-5] if path.endswith('.html') else path.strip('/')
        if base in _ni or path.strip('/') in _ni:
            sm_ni.append(path)
    add('sitemap_noindex_listed', 'noindexの頁がsitemapに載っている(sitemap再生成の漏れ)',
        sorted(set(sm_ni)),
        '詳細頁を作り直したら scripts/generate_sitemap.py も回す')

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
    today_s = os.environ.get('AUDIT_TODAY') or today_jst()

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
    today = os.environ.get('AUDIT_TODAY') or today_jst()
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

    # 9b. dateDisplay の書式が sitelib.compact_date と違う
    #     (ランディング/RSSは dateDisplay をそのまま出すため書式が割れると表示が不揃いになる)
    try:
        sys.path.insert(0, rp('scripts'))
        from sitelib import compact_date as _cd
        dd_bad = []
        for e in events:
            dd = (e.get('dateDisplay') or '').strip()
            if not dd or not e.get('date'):
                continue
            exp = _cd(e)
            if dd != exp and not re.search(r'(中旬|上旬|下旬|未定|調整中|頃|予定)', dd):
                dd_bad.append(f"{e['slug']}: {dd} → {exp}")
    except ImportError:
        dd_bad = []
    add('datedisplay_format', 'dateDisplayの書式がsitelib.compact_dateと不一致',
        sorted(dd_bad), '一覧表記は sitelib.compact_date が単一情報源。曖昧表記(中旬等)は除外')

    # 9c. 説明文・timeフィールドと date/dateEnd の矛盾
    #     (自動生成ではなく人/LLMが書いた本文なので、日付欄だけ直して本文が古いまま残る事故が起きる)
    import datetime as _dt

    def _span(e):
        d = e.get('date') or ''
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', d):
            return None, set()
        y = int(d[:4])
        de = e.get('dateEnd') or d
        try:
            cur = _dt.date(*map(int, d.split('-')))
            end = _dt.date(*map(int, de.split('-')))
        except ValueError:
            return y, set()
        out = set()
        while cur <= end and (end - cur).days < 400:
            out.add((cur.month, cur.day))
            cur += _dt.timedelta(days=1)
        return y, out

    # 前回開催・雨天予備日・別年の告知など、範囲外にあって当然の言及を落とす
    _EXCUSE = re.compile(r'(予備日|延期|順延|前回|初回|第\s*1\s*回|昨年|去年|翌年|来年|同時開催|次回)')
    desc_bad, stale_year, time_bad = [], [], []
    for e in events:
        desc = (e.get('description') or '').strip()
        year, span = _span(e)
        if not span:
            continue
        # 別年の日付を名指ししている(前年の告知文の使い回し)
        for yy, mm, dd in re.findall(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', desc):
            if int(yy) != year:
                stale_year.append(f"{e['slug']}: 本文に{yy}年{mm}月{dd}日 (開催は{year}年)")
        if desc and not _EXCUSE.search(desc):
            # 「6月1日」形式に加えて「6/1(土)」形式も拾う。スラッシュ表記は前年告知の
            # 貼り付けを実際に取り逃がした(fujiyama-days-little-green-park-2026)
            _found = {(int(a), int(b)) for a, b in re.findall(r'(\d{1,2})月(\d{1,2})日', desc)}
            _found |= {(int(a), int(b))
                       for a, b in re.findall(r'(?<![\d:/])(\d{1,2})/(\d{1,2})(?![\d/])', desc)
                       if 1 <= int(a) <= 12 and 1 <= int(b) <= 31}
            out = sorted(_found - span)
            if out:
                desc_bad.append(f"{e['slug']}: 本文 {'/'.join(f'{m}月{d}日' for m, d in out)} "
                                f"が {e.get('date')}〜{e.get('dateEnd') or e.get('date')} の外")
        # timeが「最終日」に言及しているのに単日
        if '最終日' in (e.get('time') or '') and (e.get('dateEnd') or e.get('date')) == e.get('date'):
            time_bad.append(f"{e['slug']}: time=\"{e.get('time')}\" だが dateEnd={e.get('dateEnd')} で単日")

    add('desc_date_mismatch', '説明文の日付が開催日の範囲外(予備日・前回言及は除外)', sorted(desc_bad),
        '本文か日付欄のどちらかが古い。一次情報で確認して直す')
    add('desc_stale_year', '説明文が別年の日付を名指ししている(前年の告知文の使い回し)', sorted(stale_year))
    add('time_multiday_mismatch', 'timeが複数日を示すのに dateEnd が単日', sorted(time_bad))

    # 9c-2. time / access のスクレイプ由来の混入。
    #       time は詳細ページ本文・FAQ・JSON-LD(構造化データ)に直行するので、
    #       誤値は検索結果にそのまま出る。access も同じ経路でFAQに入る。
    #       2026-08-04: 経路検索ウィジェットの結果が time(09:25〜09:40)と
    #       access(都営三田線 高島平…／会場は埼玉)として貼られていた事故を機に追加。
    _TIME_RANGE = re.compile(r'^\s*(\d{1,2}):(\d{2})\s*[〜~\-ー–]\s*(\d{1,2}):(\d{2})')
    time_odd = []
    for e in events:
        m = _TIME_RANGE.match(e.get('time') or '')
        if not m:
            continue
        a = int(m.group(1)) * 60 + int(m.group(2))
        b = int(m.group(3)) * 60 + int(m.group(4))
        if b < a:            # 日付をまたぐ表記(23:00〜01:00)
            b += 24 * 60
        dur = b - a
        days = 1
        if re.match(r'^\d{4}-\d{2}-\d{2}$', e.get('date') or '') and e.get('dateEnd'):
            try:
                days = (_dt.date(*map(int, e['dateEnd'].split('-')))
                        - _dt.date(*map(int, e['date'].split('-')))).days + 1
            except ValueError:
                days = 1
        if dur < 120:
            time_odd.append(f"{e['slug']}: time=\"{e.get('time')}\" は{dur}分"
                            + (f"(会期{days}日)" if days > 1 else ''))
    add('time_implausible', '開催時間の幅が2時間未満(経路検索など別データの貼り付けの疑い)',
        sorted(time_odd),
        '即売会・マルシェの実データは最短でも150分。裏取りできなければ time を消す')

    # 事業者・路線ごとの営業県。ここに無い事業者は判定しない(誤検出を出さないため)。
    # JRは全国なので事業者では見ず、線名だけを見る。
    _RAIL_PREFS = {
        '都営': {'東京'}, '東京メトロ': {'東京', '千葉', '埼玉'},
        '西武': {'東京', '埼玉'}, '東武': {'東京', '埼玉', '千葉', '栃木', '群馬'},
        '京王': {'東京', '神奈川'}, '小田急': {'東京', '神奈川', '静岡'},
        '東急': {'東京', '神奈川'}, '京急': {'東京', '神奈川'},
        '相鉄': {'神奈川', '東京'}, '京成': {'東京', '千葉'},
        '名鉄': {'愛知', '岐阜'}, '近鉄': {'大阪', '奈良', '京都', '三重', '愛知'},
        '南海': {'大阪', '和歌山'}, '阪急': {'大阪', '兵庫', '京都'},
        '阪神': {'大阪', '兵庫'}, '西鉄': {'福岡'},
        '東海道線': {'東京', '神奈川', '静岡', '愛知', '岐阜', '滋賀', '京都', '大阪', '兵庫'},
        '東海道本線': {'東京', '神奈川', '静岡', '愛知', '岐阜', '滋賀', '京都', '大阪', '兵庫'},
        '山手線': {'東京'}, '中央線': {'東京', '神奈川', '山梨', '長野', '岐阜', '愛知'},
        '琵琶湖線': {'滋賀'}, '環状線': {'大阪'},
    }
    access_bad = []
    for e in events:
        acc = (e.get('access') or '').strip()
        pref = (e.get('prefecture') or '').strip()
        if not acc or not pref:
            continue
        for key, prefs in _RAIL_PREFS.items():
            if key in acc and pref not in prefs:
                access_bad.append(f"{e['slug']}: access に「{key}」(営業県 "
                                  f"{'/'.join(sorted(prefs))}) だが prefecture={pref}")
    add('access_pref_mismatch', 'アクセス文の路線が開催県を通っていない(別会場の案内の貼り付け)',
        sorted(set(access_bad)),
        'access は当該会場の一次情報から書く。裏取りできなければ消す')

    # 9d. スクレイプ結果の貼り付け残り(ページタイトル+URL、出典表記の前置き)。
    #     本文は詳細ページ本文とmeta descriptionに直行するので閲覧者と検索結果に露出する
    junk = []
    for e in events:
        desc = (e.get('description') or '').strip()
        if not desc:
            continue
        if re.search(r'https?://', desc):
            junk.append(f"{e['slug']}: 本文にURLが混入")
        if re.match(r'^(提供元|引用元|出典)\s*[:：]', desc):
            junk.append(f"{e['slug']}: 本文が出典表記で始まる(スクレイプ結果の貼り付け)")
    add('desc_scraped_junk', '説明文にスクレイプ由来の混入(URL・出典表記)', sorted(junk),
        '本文はイベント説明だけにする。URLは url / sourceUrl に置く')

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

    # 地域分類の整合。events.json の region が sitelib の定義と一致しているか、
    # REGION_ROMAJI に無い地域名(=ハッシュURLの頁を生む)が混ざっていないかを見る。
    # 各スクリプトが独自定義を持っていて沖縄と山梨・長野で割れていた(2026-07-31に統合)。
    region_bad = []
    try:
        for e in events:
            pref = (e.get('prefecture') or '').strip()
            reg = (e.get('region') or '').strip()
            want = sitelib.pref_to_region(pref) if pref else None
            if want and reg and reg != want:
                region_bad.append(f"{e.get('slug')}: {pref}={reg} (定義では{want})")
            elif reg and reg not in sitelib.REGION_ROMAJI:
                region_bad.append(f"{e.get('slug')}: region={reg} はREGION_ROMAJIに無い")
    except Exception as _e:
        region_bad.append(f'検査失敗: {_e}')
    add('region_mismatch', 'regionが地域定義と不一致 / スラッグ未定義', sorted(set(region_bad)),
        '定義の単一情報源は scripts/sitelib.py の PREF_TO_REGION')

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
