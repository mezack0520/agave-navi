#!/usr/bin/env python3
"""audit.py — パイプライン全体の「黙って落ちているもの」を洗い出す。

作った目的(2026-07-30):
  各スクリプトが成功件数だけを出力し、除外・欠落・孤児を黙っていたため、
  問題が人に指摘されるまで表面化しなかった。存在確認ではなく整合確認を毎日回す。

読み取り専用。何も変更しない。検出結果を JSON とテキストで出す。
終了コードは常に0(検出は失敗ではない)。件数は日次メールに載せる。
"""
import html as _html
import json
import os
import re
import glob
import unicodedata
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
from sitelib import (today_jst, VAGUE_VENUES, is_generic_image_url,
                     event_phase, is_long_run, event_days, LONG_RUN_DAYS,
                     is_vague_venue, venue_key, venue_slug, venue_display,
                     VENUE_ROMAJI, VENUE_ROMAJI_MIN_EVENTS, VENUE_SLUG_REDIRECTS,
                     tag_slug, region_slug, pref_slug, DESC_MIN_CHARS,
                     is_recent_past, event_span, PAST_KEEP_MAX)

# events.json で使ってよいキー。どのスクリプトも読まないキーが混ざると、
# 値が入っているのにどこにも出ない(2026-08-11に organizerUrl / urlCheckOk /
# _htmlName の3種を検出)。フィールド名の打ち間違いもここで止まる。
# 追加するときは、そのキーを読む側のコードを先に書くこと。
KNOWN_EVENT_FIELDS = {
    'slug', 'name', 'date', 'dateEnd', 'dateDisplay', 'time',
    'location', 'venue', 'mapQuery', 'access', 'prefecture', 'region',
    'description', 'tags', 'status', 'eventStatus', 'admission',
    'url', 'sourceUrl', 'imageUrl', 'instagramUrl', 'instagramPostId',
    'organizer', 'organizerIg', 'recurring', 'autoDateUpdate',
    'addedDate', 'updatedAt', 'enrichedAt', 'dataSource',
}


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

    # severity='urgent' は日次メールに出す。'info' は参考行にまとめる。
    # health.yml 側に項目名をハードコードすると、検査を追加するたびに
    # ワークフローの編集が必要になり改善が止まるため移した(2026-08-10)。
    def add(key, title, items, note='', severity='urgent'):
        """検査結果を1件登録する。

        severity の使い分け:
          urgent … 壊れている。直すまで毎日報告する
          info   … 直せる負債。減らすべきで、ゼロにできる
          metric … 観測値。構造上ゼロにならないので「減らす対象」に混ぜない
                   (新規イベントは必ず画像なしで入る、終了済みの出典なしは改善しない等)
        metric を info に混ぜると一覧が常に埋まり、読み手が一覧全体を無視するようになる。
        """
        findings[key] = {'title': title, 'count': len(items),
                         'items': items[:40], 'note': note,
                         'severity': severity}

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

    # 2b. 同日・同会場で名前だけ違う二重掲載。2 の完全一致では
    #     「Plants garage market 2026」と「Plants garage market 2026 -SPRING & SUMMER-」
    #     のような表記ゆれを拾えず、同一回が2ページ生まれていた(2026-08-10に検出)。
    #     会場は記号と括弧内の地名を落として比較する。会場が同じで日付も同じなら
    #     別イベントである可能性は低い。
    def _venue_key(e):
        v = (e.get('location') or e.get('venue') or '').strip()
        v = re.sub(r'<[^>]+>', ' ', v)
        v = re.sub(r'[（(].*?[)）]', '', v)
        v = re.sub(r'[\s　・\-—〜~]', '', v)
        return v

    # 会場名の粒度が違うだけの同一回も拾う(2026-08-11に検出)。
    # 「京セラドーム大阪」と「京セラドーム大阪スカイホール」は完全一致では別会場に見える。
    # 誤検出を防ぐため、短いほう(=接頭辞側)が6文字以上で、かつ
    # 「東京都内」「岐阜県内」のような広域指定でないときだけ同一とみなす。
    _vague = is_vague_venue

    seen_vd = defaultdict(list)
    for e in events:
        vk = _venue_key(e)
        d = e.get('date') or ''
        if vk and d and not _vague(vk):
            seen_vd[(vk, d)].append(e.get('slug'))
    dup_vd = sorted(f"{k[1]} {k[0]}: {' / '.join(sorted(v))}"
                    for k, v in seen_vd.items() if len(v) > 1)

    by_date_v = defaultdict(list)
    for (vk, d), slugs_v in seen_vd.items():
        by_date_v[d].append((vk, slugs_v))
    for d, lst in by_date_v.items():
        for i in range(len(lst)):
            for j in range(i + 1, len(lst)):
                a, b = lst[i], lst[j]
                short, long_ = sorted((a[0], b[0]), key=len)
                # 長い側が「ホール」「館」「階」などの下位区画を足しているだけの場合は
                # 同一建物内の別会場なので二重掲載ではない(2026-08-10 誤検知対応)。
                # 例: 京セラドーム大阪 と 京セラドーム大阪スカイホール は別イベント
                suffix = long_[len(short):] if long_.startswith(short) else ''
                import re as _re_sub
                if suffix and _re_sub.search(
                        r'ホール|会館|館|階|[0-9]+F|催事場|広場|会議室|展示場|棟|ルーム|コート|アリーナ',
                        suffix):
                    continue
                if len(short) < 6 or not long_.startswith(short):
                    continue
                dup_vd.append(f"{d} {short} ⊂ {long_}: "
                              + ' / '.join(sorted(a[1] + b[1])))
    dup_vd = sorted(set(dup_vd))
    add('duplicate_venue_date', '同日・同会場で別slug(名称の表記ゆれによる二重掲載の疑い)',
        dup_vd,
        '同一回なら片方を削除し、残す側に一次情報を寄せる。'
        '本当に同会場で別イベントなら名称で区別できるようにする')

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
                or len(d) >= DESC_MIN_CHARS)
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
    # 出典ありの薄い回を、開催予定と終了済みで分ける。
    # 終了30日超は noindex で検索に出ないので、説明文を伸ばしても読む人がいない。
    # 混ぜて info にしていたため「34件の負債」に見えていたが、
    # 2026-08-24時点で34件すべてが終了30日超だった。減らす対象は開催予定だけ。
    add('thin_fixable', f'薄い判定で開催予定(出典あり・説明文を{DESC_MIN_CHARS}字以上にすれば解消)',
        sorted(f"{e['slug']}({len((e.get('description') or '').strip())}字)"
               for e in thin_all if has_src(e) and is_future(e)),
        '一次情報から出店数・扱う植物のジャンル・企画を足す。'
        '日時と会場はスペック表に出ているので説明文に繰り返さない', severity='info')
    add('thin_past_with_source', '薄い判定で終了済み(出典あり)',
        sorted(f"{e['slug']}({len((e.get('description') or '').strip())}字)"
               for e in thin_all if has_src(e) and not is_future(e)),
        '終了30日超は noindex。伸ばしても検索にも訪問者にも届かないので対応不要',
        severity='metric')
    add('thin_archived', '薄い判定のうちアーカイブ許容(終了済み・出典なし)',
        sorted(e['slug'] for e in thin_all if not has_src(e) and not is_future(e)),
        '終了済みで出典も無い回。一次情報が後から出ることはほぼ無く、'
        'noindex なので検索にも出ない。ゼロにはならない', severity='metric')
    add('thin_needs_source', '薄い判定で開催予定なのに出典がない(要対処)',
        sorted(e['slug'] for e in thin_all if not has_src(e) and is_future(e)),
        '一次情報を見つけるか、見つからなければ掲載基準により削除')

    # 8. 説明文が短い開催予定
    add('short_descriptions',
        f'開催予定で説明文{DESC_MIN_CHARS}字未満(モバイルのSERPスニペットが埋まらない)',
        sorted(f"{e['slug']}({len((e.get('description') or '').strip())}字)"
               for e in events
               if e.get('status') == 'upcoming'
               and len((e.get('description') or '').strip()) < DESC_MIN_CHARS), severity='info')

    # 8b. サムネイルの無い開催予定
    # トップと一覧のカードが「NO IMAGE」になる。weekly-enrichment の
    # backfill-images.py が効いているかは、この件数が週ごとに減るかでしか分からない。
    # 常時0にはならないので info。(2026-08-18 追加。追加時 61/77件)
    add('upcoming_no_image', '開催予定でimageUrlが無い',
        sorted(e['slug'] for e in events
               if e.get('status') == 'upcoming' and not (e.get('imageUrl') or '').strip()),
        '新規イベントは必ず画像なしで入るので、この件数はゼロにならない。'
        'カード側は県名と開催日を出す枠になっており(2026-08-24)、'
        '画像が無いこと自体は表示の不具合ではない。'
        '出典が og:image を出しているのに拾えていないなら backfill-images.py 側の問題',
        severity='metric')

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

    # 9c-3. venue / mapQuery / location が別県の住所を名乗っていないか。
    #       venue は location より優先して詳細ページのスペック表・FAQ・JSON-LD の
    #       Place.name に入り、mapQuery は埋め込み地図の座標そのものになる。
    #       2026-08-04: 2件が同一の「岩手県花巻市松園町50」を持つなど、別ページの住所を
    #       まとめて貼った回が9件あった(静岡の道の駅に岩手の住所、北海道の回に
    #       インテックス大阪)。JSON-LD では Place.name=岩手の住所 /
    #       addressRegion=北海道 という矛盾した構造化データを出していた。
    #       「東京都府中市」から「京都府」を拾うような部分一致を避けるため、
    #       都道府県は「〜県 / 〜府 / 東京都 / 北海道」の明示形だけを見る。
    #       会場名だけの表記(インテックス大阪)は会場辞書が要るのでこの検査では拾えない。
    from sitelib import PREF_TO_REGION as _P2R
    from sitelib import VAGUE_VENUES as _VAGUE

    def _named_prefs(text):
        t = text.replace('東京都', '\x00')
        out = set()
        if '\x00' in t:
            out.add('東京')
        if '北海道' in t:
            out.add('北海道')
        for _p in _P2R:
            if _p in ('東京', '北海道'):
                continue
            if _p + '県' in t or (_p in ('大阪', '京都') and _p + '府' in t):
                out.add(_p)
        return out

    place_bad = []
    for e in events:
        pref = (e.get('prefecture') or '').strip()
        if not pref or pref == '調整中':
            continue
        for f in ('venue', 'mapQuery', 'location'):
            val = (e.get(f) or '').strip()
            if not val:
                continue
            named = _named_prefs(val)
            if named and pref not in named:
                place_bad.append(f"{e['slug']}: {f}=\"{val[:40]}\" は"
                                 f"{'/'.join(sorted(named))}の住所だが prefecture={pref}")
    add('venue_pref_mismatch', '会場・地図クエリが別県の住所になっている(別ページの貼り付け)',
        sorted(set(place_bad)),
        'venue は location より優先して表示・JSON-LDに入り、mapQuery は地図の座標になる。'
        '裏取りできなければ消して location + prefecture のフォールバックに任せる')

    # 9c-4. venue が会場名ではなく郵便番号付きの住所になっていないか。
    #       venue_pref_mismatch は県が食い違う場合しか拾えないため、同一県内で
    #       別地点の住所を貼った回(2026-08-10時点で9件)が通り抜けていた。
    #       venue は build-detail-pages.py:339 で location より優先されるので、
    #       スペック表・FAQ本文・JSON-LD の Place.name に生の住所が出る
    #       (例: code-tokyo-popup-2026-08 は大井町開催なのに「会場は東京
    #       (〒171-0022 東京都豊島区南池袋1丁目)です」と出ていた)。住所は mapQuery の役割。
    postal_venue = []
    for e in events:
        val = (e.get('venue') or '').strip()
        if val.startswith('〒') or re.match(r'^\d{3}-\d{4}', val):
            postal_venue.append(f"{e['slug']}: venue=\"{val[:40]}\"")
    add('venue_postal_address', 'venue が会場名でなく郵便番号付き住所(スペック表とJSON-LDに住所が出る)',
        sorted(postal_venue),
        '住所は mapQuery に置き、venue は会場名だけにする。'
        '会場名が location にあるなら venue を削除して location へフォールバックさせる')

    # 9c-5. venue / mapQuery が「会場名」として成立していないもの。
    #       venue は location より優先して スペック表・FAQ・JSON-LD の Place.name に入り、
    #       mapQuery は埋め込み地図の検索語そのものになる。したがってここに会場名以外が
    #       入ると、地図が県全体や無関係な語を指し、構造化データの Place.name が
    #       会場でなくなる。venue_postal_address は 〒 始まりしか見ないため素通りしていた。
    #       2026-08-12 に検出した実例:
    #         - venue=mapQuery="愛知県" (location に「すいとぴあ江南」があるのに未使用)。
    #           地図は県全体を指し、JSON-LD は Place.name="愛知県" を出していた。9件
    #         - venue=mapQuery="6月10日（水）～" (hankyu-green-expo-2026)。
    #           日付をスクレイプして会場欄に貼った回。地図が日付文字列を検索していた
    #         - venue=mapQuery="B1F 1番地　マルチスクエア前"。建物名を欠く館内スポットのみ
    _PREF_SUFFIXED = {p + '都' if p == '東京' else
                      p + '府' if p in ('大阪', '京都') else
                      p if p == '北海道' else p + '県'
                      for p in _P2R}
    place_bad2 = []
    for e in events:
        for f in ('venue', 'mapQuery', 'location'):
            val = (e.get(f) or '').strip()
            if not val:
                continue
            # (a) venue / mapQuery が都道府県名だけ。venue は JSON-LD の Place.name に
            #     そのまま入り、mapQuery は地図の検索語になるので、県名だけだと
            #     地図が県全体を指し構造化データの会場名が県名になる。
            #     location は会場が本当に分からない回の置き場なので対象外
            #     (sitelib.VAGUE_VENUES 側で「記録なし」表示に落ちる)。
            if f != 'location' and (val in _PREF_SUFFIXED or val in _P2R):
                place_bad2.append(
                    f"{e['slug']}: {f}=\"{val}\" は都道府県名だけで会場名がない")
            # (b) 実在する都道府県名に誤った接尾辞が付いた表記(「京都県」「大阪県」)。
            #     「やまぎん県民ホール」のような施設名を拾わないよう、
            #     実在の県名+誤接尾辞の組み合わせだけを名指しで見る
            for _wrong in ('京都県', '大阪県', '東京県', '東京府', '北海道県'):
                if _wrong in val:
                    place_bad2.append(
                        f"{e['slug']}: {f}=\"{val[:30]}\" に存在しない"
                        f"都道府県表記「{_wrong}」")
            # (c) 日付・時刻表現。会場欄に日付をスクレイプして貼った回
            if re.search(r'\d{1,2}月\d{1,2}日|\d{1,2}/\d{1,2}[^0-9]|\d{1,2}:\d{2}|'
                         r'[（(][月火水木金土日][）)]|\d{4}年', val):
                place_bad2.append(f"{e['slug']}: {f}=\"{val[:30]}\" に日付・時刻表現")
    add('place_field_not_a_venue', 'venue/mapQuery/location が会場名になっていない'
        '(地図とJSON-LDのPlace.nameが壊れる)', sorted(set(place_bad2)),
        '会場名が location にあるなら venue と mapQuery を削除して '
        'location + prefecture のフォールバックに任せる')

    # 9c-6. venue と location が一文字も共有せず、別々の施設名を名乗っている回。
    #       どちらか一方が別イベントからの貼り付けである可能性が高い。
    #       venue が優先されるので、間違っているのが venue 側だと
    #       スペック表・JSON-LD・地図の3つが揃って別会場を指す。
    #       2026-08-12 の実例: hachimon-plants-festa-5th-ueda-2026-06 は
    #       venue="B1F 1番地　マルチスクエア前"(建物名を欠く館内スポット)に対し
    #       location="カクイチA-SITE上田店" で、地図が館内スポット名を検索していた。
    #       一次情報を見ないとどちらが正しいか決まらないので info に置く。
    def _place_norm(t):
        return re.sub(r'[\s\u3000+（）()、,・]', '', t)

    def _longest_common(a, b):
        best = 0
        for i in range(len(a)):
            for j in range(i + best + 1, len(a) + 1):
                if a[i:j] in b:
                    best = j - i
                else:
                    break
        return best

    disagree = []
    for e in events:
        v = _place_norm((e.get('venue') or '').strip())
        loc = _place_norm((e.get('location') or '').strip())
        if not v or not loc:
            continue
        if (e.get('venue') or '').strip() in _VAGUE or \
                (e.get('location') or '').strip() in _VAGUE:
            continue
        if _longest_common(v, loc) < 2:
            disagree.append(f"{e['slug']}: venue=\"{e['venue'][:28]}\" と "
                            f"location=\"{e['location'][:28]}\" が別の施設名")
    add('venue_location_disagree', 'venue と location が別々の施設名(片方が別イベントの貼り付けの疑い)',
        sorted(disagree),
        '一次情報で正しい会場を確認し、誤っている側を消す。'
        '同一建物内の区画なら venue を「建物名 区画」の形にまとめる',
        severity='info')

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
        # リンク先を伴わない角括弧ラベルは、記事のアンカーテキストだけが
        # 残ったもの(2026-08-11に mollis-exhibit-kinto-2026 で検出)
        m = re.search(r'\[[^\]]{2,120}\]', desc)
        if m:
            junk.append(f"{e['slug']}: 本文にリンクテキストの残骸 {m.group(0)[:30]}")
    add('desc_scraped_junk', '説明文にスクレイプ由来の混入(URL・出典表記・リンク残骸)',
        sorted(junk),
        '本文はイベント説明だけにする。URLは url / sourceUrl に置く')

    # 9c. 説明文が途中で切れている。スクレイプが本文の途中で打ち切られた回は
    #     括弧が閉じないまま終わる / 句点で終わらない。閲覧者には文の欠けた
    #     案内が出る(2026-08-11に検査化。既知の2件がこれに当たる)。
    trunc = []
    for e in events:
        desc = (e.get('description') or '').strip()
        if not desc:
            continue
        for o, c in (('「', '」'), ('（', '）'), ('(', ')'), ('『', '』')):
            if desc.count(o) != desc.count(c):
                trunc.append(f"{e['slug']}: 括弧 {o}{c} が閉じていない …{desc[-24:]}")
                break
        else:
            if desc[-1] not in '。」』）)！!？?…':
                trunc.append(f"{e['slug']}: 文末が句点で終わらない …{desc[-24:]}")
    add('desc_truncated', '説明文が途中で切れている(括弧未閉じ・文末が句点でない)',
        sorted(trunc),
        '一次情報から本文を書き直す。裏取りできなければ本文を空にして週次エンリッチに回す')

    # 9f. 必須フィールドが空。値が空でもキーは在るので unknown_event_fields も
    #     data-integrity-check も通り、thin判定も time/imageUrl があれば
    #     substance 有りとみなすため素通りする。description が空だと
    #     meta description / og:description / JSON-LD description が
    #     まとめて空文字で出る(2026-08-18に fujiyama-days-little-green-park-2026 で検出。
    #     この回は終了30日超でnoindexだったためSERPには影響しなかったが、
    #     og:description はnoindexでも効くのでSNSシェアは説明なしで出ていた。
    #     開催予定の回で起きればそのままSERPのスニペットが空になる)。
    REQUIRED_EVENT_FIELDS = ('slug', 'name', 'date', 'dateDisplay',
                             'prefecture', 'region', 'status', 'description')
    empty_req = []
    for e in events:
        for k in REQUIRED_EVENT_FIELDS:
            v = e.get(k)
            if v is None or (isinstance(v, str) and not v.strip()):
                empty_req.append(f"{e.get('slug') or '(slug無し)'}: {k} が空")
    add('required_field_empty', '必須フィールドが空(キーは在るが値が無い)',
        sorted(empty_req),
        'description が空だと meta/og/JSON-LD の説明が空文字で出る。'
        '一次情報から埋める。埋められないなら出典を外して薄頁(noindex)に落とす')

    # 9g. 「値が無い」の表現が null と空文字で混在している。
    #     image-health-check.py は死んだ imageUrl を None にし、
    #     エンリッチ側は空文字を書くため2通りが同居する。
    #     読む側は (x or '') で吸収しているので今は実害が無いが、
    #     `is None` や `in e` で書かれた検査を1つ足すと片方だけ拾って静かに漏れる。
    blanks = []
    for e in events:
        for k, v in e.items():
            if k in REQUIRED_EVENT_FIELDS:
                continue
            if v is None:
                blanks.append(f"{e.get('slug')}: {k} = null")
            elif isinstance(v, str) and not v.strip():
                blanks.append(f"{e.get('slug')}: {k} = 空文字")
            elif isinstance(v, list) and not v:
                blanks.append(f"{e.get('slug')}: {k} = 空配列")
    add('blank_optional_fields', '任意フィールドが空(nullと空文字が混在)',
        sorted(blanks),
        '値が無いならキーごと消す。残すなら null に統一する',
        severity='info')

    # 9h. imageUrl が https でない。サイトはHTTPSなので http:// の画像は
    #     混在コンテンツとしてブラウザに止められ、<img> の onerror でヒーロー画像ごと
    #     消える。加えて og:image / twitter:image / JSON-LD の image にも
    #     そのまま入るので、SNSカードとリッチリザルトの画像も落ちる
    #     (2026-08-18に code-tokyo-popup-2026-08 で4箇所への露出を確認)。
    #     url / sourceUrl は外部サイトへのリンクで、http でも遷移は成立するため対象外。
    insecure = []
    for e in events:
        u = (e.get('imageUrl') or '').strip()
        if u and not u.startswith('https://'):
            insecure.append(f"{e.get('slug')}: imageUrl = {u[:60]}")
    add('insecure_image_url', 'imageUrl が https でない(混在コンテンツで画像が出ない)',
        sorted(insecure),
        'https:// で取得できるなら書き換える。取得できないなら imageUrl を消す')

    # 9j. imageUrl がイベントの画像ではなくサイト共通アセット(ロゴ・OGP既定・
    #     ファビコン・テーマ内の共通画像)を指している。enrich が og:image を
    #     そのまま採るため、告知ページに固有画像が無いサイトではサイトロゴが入る。
    #     imageUrl は カード / og:image / twitter:image / JSON-LD の image の
    #     4箇所に同じ値が出るので、1件で4箇所が別イベントの絵になる
    #     (2026-08-18に13件を検出。うち3件は開催予定)。
    #     WordPress のアップロード先は wp-content/uploads なので、
    #     themes/ 配下や common/images/ 配下はイベント固有画像になり得ない。
    #     直し方は差し替えではなく imageUrl のキー削除。無い状態が正しい。
    #     判定は sitelib.is_generic_image_url() が単一情報源。
    #     enrich_events.py / backfill-images.py も同じ関数で弾く
    #     (検出側だけに規則があった間、weekly-enrichment が削除済みの
    #      2件を2日で書き戻していた。2026-08-20)。
    generic_img = []
    for e in events:
        u = (e.get('imageUrl') or '').strip()
        if is_generic_image_url(u):
            generic_img.append(f"{e.get('slug')}: {u[:70]}")
    add('generic_image_asset', 'imageUrlがサイト共通ロゴ・OGP既定(4箇所に別物の絵が出る)',
        sorted(generic_img),
        'イベント固有の画像に差し替えるか、無ければ imageUrl をキーごと削除する')

    # 9k. 別イベントが同じ imageUrl を指している。主催者のブランド画像を
    #     シリーズで共用する正当な場合があるので info。
    #     同一シリーズでない組が出たら、片方が別イベントからの貼り付け。
    _by_img = defaultdict(list)
    for e in events:
        u = (e.get('imageUrl') or '').strip()
        if u:
            _by_img[u].append(e.get('slug'))
    def _src_host(slug):
        e = next((x for x in events if x.get('slug') == slug), {})
        u = (e.get('sourceUrl') or e.get('url') or '')
        m = re.match(r'https?://([^/]+)', u)
        return m.group(1).lower() if m else ''

    # 出典ホストが同じ組は同一主催のシリーズ共用。これは正当なので報告しない。
    # 実例: おきぼた2回が h27664.wixsite.com のシリーズ用キービジュアルを共有(2026-08-24)。
    # ホストが違う組だけが「別イベントからの貼り付け」の疑い。
    dup_img = []
    for u, v in _by_img.items():
        slugs = sorted(set(v))
        if len(slugs) < 2:
            continue
        hosts = {_src_host(sl) for sl in slugs}
        if len(hosts) == 1 and '' not in hosts:
            continue
        dup_img.append(f"{u[:55]} → {', '.join(slugs)}")
    add('duplicate_image_url', '同じimageUrlを複数イベントが使用', sorted(dup_img),
        '同一主催のシリーズなら許容。無関係な組なら片方が貼り付けミス',
        severity='info')

    # 9k. 同じ回が別slugで二重登録されている。
    #     sanity-check-new-events.py は new-events.json 経由の流入だけを見るので、
    #     その検査より前に入った重複と、events.json を直接編集して入れた重複は
    #     どこも見ていない(2026-08-20に2組を手作業で発見)。
    #     二重登録は詳細ページ・sitemap・県頁・icsの全てで同じ回が2回出る。
    #     判定は sanity-check と同じ「同日 + 名前の正規化一致または包含」に、
    #     県の一致を足したもの。県まで一致していれば別会場の同名回ではない。
    def _norm_name(x):
        x = unicodedata.normalize('NFKC', x or '').lower()
        return re.sub(r'[\s\u3000!！?？「」『』()（）\"\'\-–—〜~・･./、,]+', '', x)

    dup_ev = []
    _seen_pair = set()
    for i, a in enumerate(events):
        for b in events[i + 1:]:
            if not a.get('date') or a.get('date') != b.get('date'):
                continue
            if a.get('prefecture') != b.get('prefecture'):
                continue
            na, nb = _norm_name(a.get('name')), _norm_name(b.get('name'))
            if not na or not nb:
                continue
            if na == nb or (min(len(na), len(nb)) >= 4 and (na in nb or nb in na)):
                key = tuple(sorted((a.get('slug') or '', b.get('slug') or '')))
                if key in _seen_pair:
                    continue
                _seen_pair.add(key)
                dup_ev.append(f"{a.get('date')} {a.get('prefecture')}: "
                              f"{a.get('slug')} ({a.get('name')}) / "
                              f"{b.get('slug')} ({b.get('name')})")
    add('duplicate_event_entry', '同じ回が別slugで二重登録されている', sorted(dup_ev),
        '内容の濃いほうに寄せて片方を削除し、events/<slug>.html も消す。'
        '残す側は命名規約(イベント名-地名-年月)に合うほうを選ぶ')

    # 9l. slug に埋め込んだ年月が date とも dateEnd とも一致しない。
    #     日付を直したのに slug(=URL)が旧月のまま残ると、URL・
    #     /archive/{ym}/ の所属・パンくずが実際の開催月とずれる。
    #     延期でこれが起きる(2026-08-18時点では0件)。
    #     会期が月をまたぐ回は dateEnd 側で一致すればよい
    #     (例 myoko-taniku-oichi-2026-11 は 10/31〜11/01)。
    slug_ym = []
    for e in events:
        sl = e.get('slug') or ''
        d = e.get('date') or ''
        de = e.get('dateEnd') or d
        m = re.search(r'(20\d{2})-(\d{2})(?!\d)', sl)
        if m and len(d) >= 7:
            if m.group(1) + '-' + m.group(2) not in (d[:7], de[:7]):
                slug_ym.append(f"{sl}: slug={m.group(1)}-{m.group(2)} date={d}..{de}")
            continue
        m2 = re.search(r'-(20\d{2})$', sl)
        if m2 and len(d) >= 4 and m2.group(1) not in (d[:4], de[:4]):
            slug_ym.append(f"{sl}: slug年={m2.group(1)} date={d}..{de}")
    add('slug_date_mismatch', 'slugの年月が開催日と不一致(日付だけ直してURLが旧月のまま)',
        sorted(slug_ym),
        '延期でずれたなら slug を作り直し、旧URLから301で送る。'
        'slugを変えないなら archive の所属が実態とずれることを承知で残す')

    # 9i. eventStatus が build-detail-pages.py の status_map に無い値。
    #     知らない値は黙って EventScheduled にフォールバックするので、
    #     'canceled'(l1つ)のような綴り違いを書くと、中止のイベントを
    #     「開催予定」としてリッチリザルトに出す。tbd はサイト独自の値で
    #     check_events.py が別途扱うため既知として許す。
    KNOWN_EVENT_STATUS = {'confirmed', 'tbd', 'cancelled', 'postponed',
                          'rescheduled', 'movedonline'}
    bad_status = []
    for e in events:
        v = e.get('eventStatus')
        if v is not None and str(v).strip().lower() not in KNOWN_EVENT_STATUS:
            bad_status.append(f"{e.get('slug')}: eventStatus = {v!r}")
    add('unknown_event_status', 'eventStatusが未知の値(黙ってEventScheduledになる)',
        sorted(bad_status),
        'build-detail-pages.py の status_map にある値に直す。'
        '新しい状態を足すなら status_map と この検査の両方に足す')

    # 9d. events.json のスキーマ外キー。読む側が無いキーは値が入っていても
    #     どこにも出ないので、入力ミスが黙って通る(2026-08-11に3種を検出)。
    unknown = []
    for e in events:
        for k in e:
            if k not in KNOWN_EVENT_FIELDS:
                unknown.append(f"{e.get('slug')}: {k} = {str(e[k])[:40]}")
    add('unknown_event_fields', 'events.jsonにスキーマ外のキー(どのスクリプトも読まない)',
        sorted(unknown),
        '既存キーに寄せるか、読む側のコードを書いて audit.py の '
        'KNOWN_EVENT_FIELDS に追加する')

    # 9e. データにHTMLタグ・実体参照が混入。build側は html_escape するので
    #     生タグは literal で表示され、JSON-LD の Place.name にも出る
    #     (2026-08-11に venue の <br> を2件検出)。
    _TAG = re.compile(r'</?[a-zA-Z][a-zA-Z0-9]*\s*/?>')
    _ENT = re.compile(r'&(?:amp|lt|gt|quot|apos|nbsp|#\d+|#x[0-9a-fA-F]+);')
    htmlish = []
    for e in events:
        for k, v in e.items():
            if not isinstance(v, str):
                continue
            if _TAG.search(v):
                htmlish.append(f"{e.get('slug')}: {k} にHTMLタグ {v[:40]}")
            elif _ENT.search(v):
                htmlish.append(f"{e.get('slug')}: {k} に実体参照 {v[:40]}")
            elif '\n' in v or '\t' in v:
                htmlish.append(f"{e.get('slug')}: {k} に改行/タブ {v[:40]!r}")
    add('html_in_data', 'events.jsonの値にHTMLタグ・実体参照・改行が混入',
        sorted(htmlish),
        'データは素のテキストで持つ。改行や強調はbuild側で付ける')

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

    # 10b. 開催中(開始済み・未終了)のイベントが「今」の枠から落ちていないか。
    #      リポジトリ内には「今」の定義が4通りあり、うち this-month と
    #      配布ics の2つだけが開始日基準だった(2026-08-18に検出)。
    #        auto-status-jst.py : dateEnd or date >= today → status
    #        this-weekend       : 会期と土日の重なり
    #        this-month(頁/ics) : date.startswith(今月)   ← 開始日基準
    #        upcoming.ics       : date >= today            ← 開始日基準
    #      会期が月をまたぐ展示(39〜49日の回が実在する)は、開催中でも
    #      今月の一覧と配布フィードから消える。今まさに行ける催しが
    #      「今月のイベント」に出ないのが一番効く壊れ方なので urgent。
    _today = today_jst()
    _cur_ym = _today[:7]
    dropped = []
    _ongoing = [e for e in events
                if (e.get('date') or '') < _today
                <= (e.get('dateEnd') or e.get('date') or '')]
    for name, path, kind in (('/this-month/', 'this-month/index.html', 'html'),
                             ('this-month.ics', 'this-month.ics', 'ics'),
                             ('upcoming.ics', 'upcoming.ics', 'ics')):
        try:
            with open(rp(path), encoding='utf-8') as f:
                body = f.read()
        except OSError:
            dropped.append(f'{name}: 生成されていない')
            continue
        for e in _ongoing:
            sl = e.get('slug') or ''
            # this-month は今月に会期が掛かる回だけが対象
            if name != 'upcoming.ics' and not (
                    (e.get('date') or '')[:7] <= _cur_ym
                    <= (e.get('dateEnd') or e.get('date') or '')[:7]):
                continue
            if sl and sl not in body:
                dropped.append(f'{name}: {sl} ({e.get("date")}..{e.get("dateEnd")}) が無い')
    add('ongoing_event_dropped', '開催中のイベントが今月頁・配布フィードから落ちている',
        sorted(dropped),
        '会期の重なりで採る(date[:7] <= 今月 <= dateEnd[:7])。'
        '開始日基準にすると先月始まりの会期物が消える')

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
        jsre = re.compile(r'((?:affiliate|ads|status-auto|list-ui)\.js)(\?v=([0-9a-zA-Z]*))?')
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

    # 13c. index対象の別URLが同じ <title> を持っている。
    #      同じtitleで内容も同じURLが2つあると、検索側はどちらを出すか選べず
    #      両方の評価が割れる。noindexの頁と、canonicalを他URLに向けた頁は
    #      検索対象ではないので除く。
    #      北海道は PREF_TO_REGION 上 1県=1地方なので /pref/hokkaido/ と
    #      /region/hokkaido/ が構造的に必ず同一内容になり、
    #      2026-08-18時点で両方index対象・同titleだった(掲載8件も完全一致)。
    titles = {}
    for f in glob.glob(rp('**', '*.html'), recursive=True):
        rel = os.path.relpath(f, REPO)
        if rel.startswith(('.git', 'templates', 'staging')):
            continue
        try:
            h = open(f, encoding='utf-8').read()
        except OSError:
            continue
        if re.search(r'<meta[^>]+name="robots"[^>]+noindex', h):
            continue
        m_can = re.search(r'<link rel="canonical" href="([^"]+)"', h)
        if m_can:
            # canonicalが自分自身を指していない = 検索対象は別URL
            own = '/' + rel.replace(os.sep, '/')
            if own.endswith('/index.html'):
                own = own[:-len('index.html')]
            if not m_can.group(1).endswith(own):
                continue
        m = re.search(r'<title>(.*?)</title>', h, re.S)
        if not m:
            continue
        titles.setdefault(m.group(1).strip(), []).append(rel)
    dup_titles = [f"{t[:44]} → {', '.join(sorted(v))}"
                  for t, v in titles.items() if len(v) > 1]
    add('duplicate_indexable_title', 'index対象の別URLが同じtitle(重複コンテンツ)',
        sorted(dup_titles),
        '内容も同じなら片方のcanonicalをもう片方に向ける。'
        '内容が違うなら title を書き分ける')

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

    # 時間軸の規則の一貫性。開始日(date)を単一の時間キーにすると、同じ原因から
    # 逆向きの事故が2つ出る(2026-08-20に是正)。
    #   1. 会期の長い回が開始日の古さで一覧の先頭に居座る
    #   2. date >= today を外れるので、開催中の回がランディングで終了扱いに落ちる
    # 「今」の定義は sitelib(event_phase / list_sort_key)が単一情報源。
    # 規則を持ち込み直したコードを毎ビルドで拾う。
    ongoing_now = [e for e in events if event_phase(e) == 'ongoing']
    add('ongoing_events', f'現在開催中のイベント(会期{LONG_RUN_DAYS}日以上は一覧の「開催中」枠)',
        sorted(f"{e.get('slug')}({e.get('date')}〜{e.get('dateEnd') or e.get('date')}"
               f"/{event_days(e)}日{'/長期' if is_long_run(e) else ''})"
               for e in ongoing_now),
        'status は upcoming のままでよい。past にすると一覧から消える。'
        '開催期間中は必ず出るので、減らす対象ではない', severity='metric')

    add('ongoing_marked_past', '開催中なのに status が upcoming でないイベント',
        sorted(e.get('slug') or '' for e in ongoing_now
               if e.get('status') != 'upcoming'),
        'auto-status-jst.py は dateEnd で判定する。ここに出るのは手で書き換えた回')

    # 開始日を単独の時間キーにしているコードの検出。
    # sitelib の event_phase / is_upcoming / list_sort_key / split_ongoing を
    # 経由しない生の比較・ソートが入ると、上の2つの事故がまた起きる。
    START_ONLY_PATTERNS = [
        # sorted(..., key=lambda e: e.get('date'...)) のような開始日単独ソート
        (re.compile(r"key\s*=\s*lambda\s+\w+\s*:\s*\w+\.get\(\s*'date'"),
         '開始日だけでソートしている'),
        # e.get('date') >= today のような開始日での開催予定判定
        (re.compile(r"\.get\(\s*'date'\s*(?:,[^)]*)?\)\s*[<>]=?\s*today"),
         '開始日だけで開催予定を判定している'),
    ]
    # 終了側・開催履歴の降順、max/min、明示マーカーは開始日基準で正しい。
    START_ONLY_ALLOW = re.compile(r'reverse\s*=\s*True|\bmax\(|\bmin\(|start-date-ok')
    start_only = []
    for f in (sorted(glob.glob(rp('scripts', '*.py'))) + [rp('build-detail-pages.py')]):
        bn = os.path.basename(f)
        if bn in ('sitelib.py', 'audit.py'):
            continue
        try:
            src = open(f, encoding='utf-8').read()
        except OSError:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            if START_ONLY_ALLOW.search(line):
                continue
            for rx, why in START_ONLY_PATTERNS:
                if rx.search(line):
                    start_only.append(f'{bn}:{i} {why}')
    # フロント側(index.html のインラインJS)にも規則を再実装させない。
    try:
        idx = open(rp('index.html'), encoding='utf-8').read()
    except OSError:
        idx = ''
    for bad, why in (('function getCardDate', 'index.html に日付解釈の再実装がある'),
                     ('function autoExpireEvents', 'index.html に終了判定の再実装がある')):
        if bad in idx:
            start_only.append(f'index.html {why}')
    if 'AEN_LIST' not in idx and idx:
        start_only.append('index.html が status-auto.js の並び替え(AEN_LIST)を使っていない')
    add('start_date_only_ordering', '開始日を単独の時間キーにしているコード',
        sorted(set(start_only)),
        'sitelib の event_phase / is_upcoming / list_sort_key / split_ongoing を使う')

    # 一覧UIの二重実装。イベントカード・行きたい・もっと見るは
    # sitelib.event_card_html と list-ui.js が単一情報源(2026-08-20に統合)。
    # 以前はランディング106枚が landing-card という別実装で、画像・ステータス
    # バッジ・行きたいが出ず、status-auto.js も効かなかった。
    dup_ui = []
    try:
        glp = open(rp('scripts', 'generate-landing-pages.py'), encoding='utf-8').read()
    except OSError:
        glp = ''
    if 'landing-card' in glp and 'event_card_html' not in glp:
        dup_ui.append('generate-landing-pages.py がイベントカードを自前で組んでいる')
    if re.search(r'\.landing-card[^\n]*\{', glp):
        dup_ui.append('generate-landing-pages.py にインラインCSSが戻っている(style.cssへ)')
    for f in ('index.html', 'ikitai.html'):
        try:
            h = open(rp(f), encoding='utf-8').read()
        except OSError:
            continue
        for fn in ('getFavs', 'toggleFav', 'syncFavUI', 'initLoadMore', 'loadMoreEvents'):
            if f'function {fn}(' in h:
                dup_ui.append(f'{f} に {fn} の再実装がある(list-ui.jsが単一実装)')
        if 'list-ui.js' not in h:
            dup_ui.append(f'{f} が list-ui.js を読んでいない')
    # ランディングがイベントカードを .landing-card で出していないか(生成物側)
    lc_event = []
    for f in glob.glob(rp('pref', '*', 'index.html')) + glob.glob(rp('region', '*', 'index.html')):
        try:
            h = open(f, encoding='utf-8').read()
        except OSError:
            continue
        if 'lc-date' in h:
            lc_event.append(os.path.relpath(f, REPO))
    add('list_ui_duplication', '一覧UIが二重実装になっている',
        sorted(set(dup_ui)) + sorted(lc_event)[:10],
        'カードは sitelib.event_card_html、行きたい/もっと見るは list-ui.js')

    # 節の見出しに、その節に何が載っているかが書かれているか。
    # 「終了したイベント」だけだと全件あるように見えるが、トップは
    # PAST_KEEP_DAYS で切った直近ぶんしか載っていない(2026-08-20)。
    note_missing = []
    for f in ([rp('index.html')] + glob.glob(rp('pref', '*', 'index.html'))
              + glob.glob(rp('region', '*', 'index.html'))):
        try:
            h = open(f, encoding='utf-8').read()
        except OSError:
            continue
        for m in re.finditer(r'id="(pastEventsHeading|ongoingHeading|upcomingHeading)"([^>]*)>(.*?)</h[23]>',
                             h, re.S):
            body = m.group(3)
            if 'display:none' in m.group(2):
                continue          # 空の節は見出しごと非表示
            if 'section-heading-note' not in body:
                note_missing.append(f'{os.path.relpath(f, REPO)} #{m.group(1)}')
    add('section_note_missing', '節の見出しに載っている範囲が書かれていない',
        sorted(set(note_missing))[:20],
        'sitelib.section_heading_html を使う。トップは sync-index-cards.py が同期')

    # 会場URLの読みやすさ。safe_slug は日本語を落とすので VENUE_ROMAJI に
    # 無い会場はハッシュURL(/venue/v-xxxxxxxx/)になる。
    # 掲載が増えた会場を人が拾えるよう候補を出す。しきい値は sitelib。
    # ローマ字を足すと既存URLが変わるので、追加は必ず
    # VENUE_SLUG_REDIRECTS に旧slugを残してから行う。
    v_groups = defaultdict(list)
    for e in events:
        loc = (e.get('location') or '').strip()
        if is_vague_venue(loc):
            continue
        v_groups[venue_key(loc)].append(e)
    romaji_cand = []
    for k, evs in v_groups.items():
        if len(evs) < VENUE_ROMAJI_MIN_EVENTS:
            continue
        if venue_slug(k).startswith('v-'):
            romaji_cand.append(f'{venue_display(k)}({len(evs)}件) → /venue/{venue_slug(k)}/')
    add('venue_slug_romaji_candidates',
        f'掲載{VENUE_ROMAJI_MIN_EVENTS}件以上でURLがハッシュのままの会場',
        sorted(romaji_cand),
        'sitelib._VENUE_ROMAJI_RAW にローマ字を足す。旧slugは必ず '
        '_VENUE_REDIRECTS_RAW に残す(URLが変わるため)')

    # VENUE_ROMAJI に書いたが頁が立たないキー(会場ページは2件以上のみ)。
    # 表記が変わって当たらなくなった項目が残ると、次に同じ会場を足すときに
    # 二重定義になる。
    unused_romaji = sorted(k for k in VENUE_ROMAJI
                           if len(v_groups.get(k, [])) < 2)
    add('venue_romaji_unused', 'VENUE_ROMAJIにあるが会場ページが立たないキー',
        unused_romaji, '会場名の表記が変わって当たらなくなった項目。消すか合わせる',
        severity='info')

    # 中継頁の健全性。宛先が無い / 現役slugと衝突しているとリダイレクトが壊れる。
    rd_bad = []
    for old_slug, dest_key in VENUE_SLUG_REDIRECTS.items():
        if not os.path.isdir(rp('venue', old_slug)):
            rd_bad.append(f'{old_slug}: 中継頁が生成されていない')
            continue
        if dest_key is None:
            continue
        dest = venue_slug(dest_key)
        if dest == old_slug:
            rd_bad.append(f'{old_slug}: 宛先が自分自身')
        elif not os.path.isfile(rp('venue', dest, 'index.html')):
            rd_bad.append(f'{old_slug} → /venue/{dest}/ が存在しない')
    add('venue_redirect_broken', '会場ページの旧URL中継が壊れている', sorted(rd_bad),
        'sitelib._VENUE_REDIRECTS_RAW の宛先会場名を実データに合わせる')

    # 14. workflowが参照するsecretの一覧(未設定だと黙って空になる)
    add('workflow_secrets', 'workflowが参照しているsecret',
        sorted(set(re.findall(r'secrets\.([A-Z_][A-Z0-9_]*)', wf))),
        '未設定でも多くのstepは失敗せず黙って空値で動く。'
        'これは使用中のsecretの棚卸しで、減らす対象ではない', severity='metric')

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
    # 17. 構造化データ。JSON-LDが壊れても画面は何も変わらないため、
    #     リッチリザルトだけが黙って落ちる。全ページのブロックをパースして、
    #     さらに Event の日付・名称が events.json と一致するかを見る。
    #     不一致は詳細ページの再生成漏れ(2026-08-11に検査化)。
    _LD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
    ld_bad, ld_drift, ld_blank = [], [], []
    ev_by_slug = {e.get('slug'): e for e in events}
    for f in sorted(glob.glob(rp('**', '*.html'), recursive=True)):
        rel = os.path.relpath(f, REPO).replace(os.sep, '/')
        # templates/ は {{placeholder}} を含む素材なのでJSONにならない
        if rel.startswith(('archive/', 'staging/', 'new/', 'templates/')):
            continue
        try:
            txt = open(f, encoding='utf-8').read()
        except OSError:
            continue
        blocks = []
        for m in _LD.finditer(txt):
            try:
                blocks.append(json.loads(m.group(1)))
            except ValueError as ex:
                ld_bad.append(f'{rel}: {ex}'[:140])
        slug = os.path.basename(rel)[:-5]
        ev = ev_by_slug.get(slug) if rel.startswith('events/') else None
        if not ev:
            continue
        node = None
        for b in blocks:
            for c in (b if isinstance(b, list) else [b]):
                if isinstance(c, dict) and c.get('@type') == 'Event':
                    node = c
        if node is None:
            ld_drift.append(f'{slug}: Event の JSON-LD が無い')
            continue
        # 空文字のキーは「値が無い」ではなく「空という値がある」と解釈される。
        # 会場不明の回は Place.name をキーごと省くのが正で、'' を出しては駄目。
        for _k, _v in (('location', node.get('location')), ('organizer', node.get('organizer'))):
            if isinstance(_v, dict):
                for _kk, _vv in _v.items():
                    if isinstance(_vv, str) and _vv.strip() == '':
                        ld_blank.append(f'{slug}: {_k}.{_kk} が空文字')

        want_end = ev.get('dateEnd') or ev.get('date')
        for label, got, want in (
                ('startDate', (node.get('startDate') or '')[:10], ev.get('date')),
                ('endDate', (node.get('endDate') or '')[:10], want_end),
                ('name', _html.unescape(node.get('name') or ''), ev.get('name'))):
            if label == 'endDate' and not got:
                continue
            if got != want:
                ld_drift.append(f'{slug}: {label} 頁={got!r} data={want!r}')
    add('jsonld_invalid', 'JSON-LDがJSONとして壊れているページ(リッチリザルトが落ちる)',
        sorted(ld_bad),
        'データ側にエスケープされていない引用符・制御文字が無いか見る')
    add('jsonld_data_drift', '詳細ページのJSON-LDがevents.jsonと不一致(再生成漏れ)',
        sorted(ld_drift),
        'build-detail-pages.py を回す。差分が残るならテンプレート側を疑う')
    add('jsonld_blank_value', 'JSON-LDに空文字の値(値が無いのではなく空を主張してしまう)',
        sorted(ld_blank),
        '会場や主催が不明な回は、空文字を入れずキーごと省く。build-detail-pages.py のテンプレート側で分岐する')

    add('rakuten_config_missing', '楽天API設定の欠落(欠けると商品画像が出ずテキスト表示になる)',
        missing_cfg, f'検索語 {len([k for k in kws if k])} 件がこの設定に依存する', severity='info')

    # 掲載申請フォームの確認が止まっていないか。
    # event-listing-review は回答シートを読むたびに new-inquiries.json の
    # lastChecked を当日にして push する。新着ゼロの日でもこの値だけは動く。
    # 逆に言うと、ここが止まっていれば「申請が来ていない」ではなく
    # 「確認する側が動いていない」。2026-08-14〜17 と 08-19 に実行が抜けたが、
    # repo には痕跡が残らず、次に動いた日まで誰も気づけなかった(2026-08-20に検査を追加)。
    # 4日目から鳴らす。1日の抜けで鳴らすと、実行時刻とCIの時差だけで誤検知する。
    inq_stale = []
    _ni = load_json('new-inquiries.json', {})
    _lc = str(_ni.get('lastChecked') or '').strip()
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', _lc):
        inq_stale.append(f'lastChecked が日付として読めない: {_lc!r}')
    else:
        import datetime as _dtm
        try:
            _gap = (_dtm.date.fromisoformat(today_jst())
                    - _dtm.date.fromisoformat(_lc)).days
        except ValueError:
            _gap = None
            inq_stale.append(f'lastChecked が日付として読めない: {_lc!r}')
        if _gap is not None and _gap > 3:
            inq_stale.append(
                f'lastChecked={_lc} / {_gap}日前。掲載申請フォームの確認が止まっている')
    add('inquiry_check_stale', '掲載申請フォームの確認が止まっている',
        inq_stale,
        'event-listing-review が毎日 new-inquiries.json の lastChecked を更新する。'
        '止まっていれば、タスクが起動していないか、起動しても書き戻しまで到達していない')

    # --- sitelib の規則を他スクリプトが写し取っていないか -------------------
    # 検出側と書き込み側に同じ規則を二重に書くと、片方だけ更新されて必ず食い違う。
    # 2026-08-20、generate-rss.py が TAG_ROMAJI と safe_slug を自前で持っており、
    # sitelib に後から足した6タグを知らないまま feeds/tag-tag-<md5>.xml を吐いていた。
    # タグ頁は /tag/aroid/ を名乗っていたので、フィードのURLと一致していなかった。
    # DOMAIN / JST のような値だけの定数は挙動を持たないので対象外。
    _SITELIB_TRIVIAL = {'DOMAIN', 'JST', 'REPO', 'REPO_ROOT'}
    _sitelib_src = ''
    try:
        with open(rp('scripts', 'sitelib.py'), encoding='utf-8') as f:
            _sitelib_src = f.read()
    except OSError:
        pass
    _sitelib_names = set()
    for m in re.finditer(r'^(?:def\s+(\w+)|([A-Z][A-Z0-9_]{2,})\s*=)', _sitelib_src, re.M):
        _sitelib_names.add(m.group(1) or m.group(2))
    _sitelib_names -= _SITELIB_TRIVIAL
    dupe_rule = []
    for path in sorted(glob.glob(rp('scripts', '*.py'))):
        fn = os.path.basename(path)
        if fn == 'sitelib.py':
            continue
        try:
            with open(path, encoding='utf-8') as f:
                src = f.read()
        except OSError:
            continue
        for m in re.finditer(r'^(?:def\s+(\w+)|([A-Z][A-Z0-9_]{2,})\s*=)', src, re.M):
            name = m.group(1) or m.group(2)
            if name in _sitelib_names:
                dupe_rule.append(f'{fn}: sitelib.{name} を自前で定義している')
    add('sitelib_rule_duplicated', 'sitelib の規則を他スクリプトが二重に定義',
        sorted(set(dupe_rule)),
        'sitelib から import する。写しを置くと、規則を足した日にどちらか片方だけが更新される')

    # --- ランディングURLの衝突・退化 ----------------------------------------
    # 別のキーが同じURLに書かれると、後から書いたほうが前のページを黙って上書きする。
    # cleanup_orphans は「生成されなかったファイル」を消すだけなので、
    # 上書きされたページは生成済み扱いになり、消えたことに誰も気づけない。
    # 2026-08-20 時点で venue に 1 / 1f / 2 / 2f / i / taut の6組の衝突があった
    # (どれも片側が1件だったので、まだページにはなっていなかった)。
    slug_owner = defaultdict(set)
    for e in events:
        for t in (e.get('tags') or []):
            slug_owner[('tag', tag_slug(t))].add(t)
        if e.get('region'):
            slug_owner[('region', region_slug(e['region']))].add(e['region'])
        if e.get('prefecture'):
            slug_owner[('pref', pref_slug(e['prefecture']))].add(e['prefecture'])
        loc = (e.get('location') or '').strip()
        if loc and not is_vague_venue(loc):
            slug_owner[('venue', venue_slug(loc))].add(venue_key(loc))
    collide = [f'/{kind}/{sl}/ に {len(names)}つの名前: ' + ' / '.join(sorted(names))
               for (kind, sl), names in slug_owner.items() if len(names) > 1]
    add('landing_slug_collision', '複数の名前が同じランディングURLに書かれる',
        sorted(collide),
        'sitelib.safe_slug が非ASCII名から作る残渣は元の名前を代表しない。'
        '衝突する側を *_ROMAJI に足すか、キーの正規化を見直す')

    # --- 配布フィードとタグ・地域の対応 --------------------------------------
    # generate-rss.py はタグ・地域ごとに feeds/*.xml を吐く。
    # 対象が消えたフィードを消す掃除が無かったため、2026-06-11の「多肉」タグと
    # 2026-07-31の沖縄地方のフィードが、その日の中身のまま公開され続けていた。
    want_feeds = {f'tag-{tag_slug(t)}.xml' for e in events for t in (e.get('tags') or [])}
    want_feeds |= {f'region-{region_slug(e["region"])}.xml'
                   for e in events if e.get('region')}
    have_feeds = {fn for fn in os.listdir(rp('feeds'))
                  if fn.endswith('.xml') and fn.startswith(('tag-', 'region-'))} \
        if os.path.isdir(rp('feeds')) else set()
    feed_drift = ([f'孤児: feeds/{fn}(対応するタグ・地域が無い)' for fn in sorted(have_feeds - want_feeds)]
                  + [f'欠落: feeds/{fn}(タグ・地域はあるがフィードが無い)' for fn in sorted(want_feeds - have_feeds)])
    add('feed_slug_drift', '配布フィードが現行のタグ・地域と一対一でない', feed_drift,
        'generate-rss.py が生成しなかった region-*/tag-*.xml を消す。'
        'スラッグは sitelib の tag_slug / region_slug が単一情報源')

    # --- サイト内リンクの参照先 ----------------------------------------------
    # sitemap_dead_entries は sitemap に載っているURLしか見ない。
    # ヘッダ・フッタ・ガイド・ランディングから貼っているリンクは対象外だった。
    _LINK = re.compile(r'(?:href|src)="([^"]+)"')
    dead_links = defaultdict(set)
    for path in glob.glob(rp('**', '*.html'), recursive=True):
        rel_html = os.path.relpath(path, REPO)
        if rel_html.startswith('templates' + os.sep):
            continue  # 置換前のプレースホルダが入っている
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                body = f.read()
        except OSError:
            continue
        for href in set(_LINK.findall(body)):
            if href.startswith(('http', '//', 'mailto:', 'tel:', 'javascript:', 'data:', '#')):
                continue
            if '${' in href or '{{' in href:
                continue  # JSのテンプレートリテラル
            target = href.split('#')[0].split('?')[0]
            if not target:
                continue
            base = (os.path.join(REPO, target.lstrip('/')) if target.startswith('/')
                    else os.path.normpath(os.path.join(os.path.dirname(path), target)))
            if target.endswith('/'):
                base = os.path.join(base, 'index.html')
            if not os.path.exists(base):
                dead_links[target].add(rel_html)
    add('dead_internal_link', 'サイト内リンクの参照先が存在しない',
        sorted(f'{k} ← {len(v)}頁 (例 {sorted(v)[0]})' for k, v in dead_links.items()),
        '生成物の消し忘れか、リンク側がスラッグの変更に追随していない')

    # --- 出典ドメインの禁止規則 -----------------------------------------------
    # listing-policy.json の blockedUrlDomains は「url / sourceUrl に使ってはならない
    # ドメイン」を定めているが、2026-08-24 時点でこの規則を読むコードが1本も無かった
    # (grep で blockedUrlDomains の参照は listing-policy.json 自身だけ)。
    # つまり守っているのは人の記憶だけで、crawl / enrich が拾ったアグリゲータのURLが
    # 出典として入っても誰も気づかない。アグリゲータは中止・休会・延期を反映しないため、
    # 出典にすると「裏取り済み」の見た目で誤情報が残る(2026-08-12 ISIJ東京例会 休会の例)。
    # 参照(探索の入口として読む)は禁止ではない。url / sourceUrl に入ることだけを見る。
    _policy = load_json('listing-policy.json', {})
    _blocked = [d.lower() for d in
                ((_policy.get('blockedUrlDomains') or {}).get('domains') or [])]
    blocked_src = []
    for e in events:
        for k in ('url', 'sourceUrl'):
            u = (e.get(k) or '').strip()
            m = re.match(r'https?://([^/]+)', u, re.I)
            if not m:
                continue
            host = m.group(1).lower().split(':')[0]
            if host.startswith('www.'):
                host = host[4:]
            for b in _blocked:
                if host == b or host.endswith('.' + b):
                    blocked_src.append(f"{e.get('slug')}: {k} = {b}")
    add('blocked_source_domain', '出典が掲載基準で禁止されたドメイン(アグリゲータ)',
        sorted(set(blocked_src)),
        '主催者の一次情報に差し替える。見つからないなら出典ごと外して薄頁に落とす。'
        'ドメインの一覧は listing-policy.json の blockedUrlDomains が単一情報源')

    # --- index.html のカード集合 ----------------------------------------------
    # sync-index-cards.py が置換に失敗するとカードが増殖する。2026-08-24 に
    # THUMB_RE が画像なし枠の <span> に一致しなくなり 101→908 枚まで増え、
    # トップで同じカードが縦に何度も出た。件数の正常値をプレイブックに書いて
    # 人が数える運用にしていたが、それは毎回は守られない。
    # 想定集合は events.json から算出できる(未終了の全件 + 直近の終了分)。
    # 生成側と同じ sitelib の規則で数えるので、規則を変えた日も追随する。
    try:
        with open(rp('index.html'), encoding='utf-8') as f:
            _idx = f.read()
    except OSError:
        _idx = ''
    card_drift = []
    if _idx:
        card_slugs = re.findall(
            r'<div class="event-card[^"]*"[^>]*data-slug="([^"]+)"', _idx)
        _by_slug = {e.get('slug'): e for e in events if e.get('slug')}
        _not_past, _past = [], []
        for e in events:
            _end = event_span(e)[1] or e.get('date') or ''
            (_not_past if _end >= today_s else _past).append(
                (_end, e.get('slug')))
        _recent = [sl for _, sl in sorted(_past, reverse=True)
                   if is_recent_past(_by_slug.get(sl) or {}, today_s)][:PAST_KEEP_MAX]
        want_cards = {sl for _, sl in _not_past} | set(_recent)
        dup_cards = sorted({sl for sl in card_slugs if card_slugs.count(sl) > 1})
        card_drift += [f'カードが重複: {sl}({card_slugs.count(sl)}枚)' for sl in dup_cards]
        card_drift += [f'カードが無い: {sl}' for sl in sorted(want_cards - set(card_slugs))]
        card_drift += [f'余分なカード: {sl}' for sl in sorted(set(card_slugs) - want_cards)]
    add('index_card_drift', 'index.htmlのカードがevents.jsonの想定集合と不一致',
        card_drift,
        'sync-index-cards.py を再実行する。重複が出ているときは THUMB_RE が'
        'thumb の中身に一致しなくなっている(置換されず挿入だけが起きる)')

    # --- 説明文の下限字数の写し ------------------------------------------------
    # 下限は sitelib.DESC_MIN_CHARS が単一情報源。数字を直接書くと、
    # 揃えた日から少しずつずれる。実際 2026-08-24 まで thin=50 / check_events=70 /
    # enrich=120 と3つに割れており、「短い回を優先処理しておきながら too short で捨てる」
    # 取りこぼしを9週間続けていた。listing-policy.json の閾値も同じ値を指すこと。
    _dm = str(DESC_MIN_CHARS)
    drift_dm = []
    _thr = ((_policy.get('shortDescriptions') or {}).get('threshold'))
    if _thr is not None and str(_thr) != _dm:
        drift_dm.append(f'listing-policy.json: shortDescriptions.threshold = {_thr}'
                        f'(sitelib は {_dm})')
    # 比較の左辺の書き方(len(x) < 50 / _dlen < 50 / x >= 50)は書き手によって変わるので、
    # 左辺の形ではなく「この数字と比較していること」だけを見る。
    # 2026-08-24 時点で sitelib 以外にこの数字との比較は1件も無いので、
    # ここに出るものは全部が写しか、無関係な定数の衝突のどちらか。
    # 無関係な用途でこの数字を使いたくなったら、その定数に名前を付けて sitelib へ置く。
    _DESC_LEN = re.compile(r'(?:[<>]=?\s*' + _dm + r'\b|\b' + _dm + r'\s*[<>]=?)')
    for path in sorted(glob.glob(rp('scripts', '*.py'))) + [rp('build-detail-pages.py')]:
        fn = os.path.basename(path)
        if fn == 'sitelib.py':
            continue
        try:
            with open(path, encoding='utf-8') as f:
                src = f.read()
        except OSError:
            continue
        for line in src.splitlines():
            code = line.split('#')[0]
            if not code.strip() or not _DESC_LEN.search(code):
                continue
            drift_dm.append(f'{fn}: {_dm} との比較をリテラルで書いている → '
                            f'{code.strip()[:70]}')
    add('desc_min_chars_drift', '説明文の下限字数を sitelib 以外が持っている',
        sorted(set(drift_dm)),
        'sitelib.DESC_MIN_CHARS を import する。'
        'listing-policy.json の shortDescriptions.threshold も同じ値にする')

    # --- 生成したのに辿れない頁 ------------------------------------------------
    # 「生成された」と「読者に届く」は別。タグ別・地域別フィード23本が
    # サイト内のどこからも参照されずsitemapにも無かった(2026-08-20に解消)。
    # 同じことは頁でも起きる。index対象なのに内部リンクが1本も無い頁は、
    # 検索エンジンにも読者にも事実上存在しない。
    # 404 と Search Console の所有確認ファイルは、リンクされないのが正しい。
    _EXEMPT_ORPHAN = {'404.html'}
    _link_re = re.compile(r'<a\b[^>]+href="([^"]+)"', re.I)
    _pages, _noindex_pages, inbound = [], set(), defaultdict(int)

    def _norm_target(src_rel, href):
        if href.startswith(('#', 'mailto:', 'tel:', 'javascript:', 'data:', '//')):
            return None
        if href.startswith('http'):
            if not href.startswith('https://agave-navi.com/'):
                return None
            href = href[len('https://agave-navi.com/'):] or 'index.html'
            href = '/' + href
        if '${' in href or '{{' in href:
            return None
        t = href.split('#')[0].split('?')[0]
        if not t:
            return None
        base = (t.lstrip('/') if t.startswith('/')
                else os.path.normpath(os.path.join(os.path.dirname(src_rel), t)))
        base = base.replace(os.sep, '/')
        if base.endswith('/'):
            base += 'index.html'
        elif os.path.isdir(rp(base)):
            base += '/index.html'
        return base

    for path in glob.glob(rp('**', '*.html'), recursive=True):
        rel = os.path.relpath(path, REPO).replace(os.sep, '/')
        if rel.split('/')[0] in ('templates', 'staging', 'guides_content'):
            continue
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                body = f.read()
        except OSError:
            continue
        _pages.append(rel)
        if re.search(r'<meta[^>]+name="robots"[^>]+noindex', body):
            _noindex_pages.add(rel)
        for href in set(_link_re.findall(body)):
            t = _norm_target(rel, href)
            if t and t.endswith('.html') and t != rel:
                inbound[t] += 1
    orphan_pages = sorted(
        f for f in _pages
        if f not in _noindex_pages and not inbound[f]
        and f not in _EXEMPT_ORPHAN
        and not re.fullmatch(r'google[0-9a-f]+\.html', f))
    add('orphan_indexable_page', 'index対象なのにサイト内のどこからも辿れない頁',
        orphan_pages,
        '一覧・ナビ・関連リンクのどこかから貼る。'
        '辿らせる先が無い頁なら noindex にして sitemap から外す')

    # --- 出力 ---
    total = sum(v['count'] for k, v in findings.items()
                if k not in ('workflow_secrets',))
    with open(rp('audit-results.json'), 'w', encoding='utf-8') as f:
        json.dump({'total': total, 'findings': findings}, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # 推移を残す。1回の値だけでは改善か悪化かが判断できない。
    hist_path = rp('audit-history.json')
    try:
        with open(hist_path, encoding='utf-8') as f:
            hist = json.load(f)
    except (OSError, ValueError):
        hist = {'_note': '監査結果の推移。scripts/audit.py が追記する。'
                         '直近90件のみ保持。改善/悪化の判断に使う。', 'runs': []}
    today_key = __import__('datetime').date.today().isoformat()
    entry = {'date': today_key,
             'urgent': {k: v['count'] for k, v in findings.items()
                        if v.get('severity', 'urgent') == 'urgent' and v['count']},
             'info': {k: v['count'] for k, v in findings.items()
                      if v.get('severity') == 'info' and v['count']},
             'metric': {k: v['count'] for k, v in findings.items()
                        if v.get('severity') == 'metric' and v['count']},
             'events': len(events)}
    runs = [r for r in (hist.get('runs') or []) if r.get('date') != today_key]
    runs.append(entry)
    hist['runs'] = runs[-90:]
    with open(hist_path, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False, indent=1)
        f.write('\n')

    # 前回との差分を出す
    prev = runs[-2] if len(runs) >= 2 else None
    if prev:
        cur_u, prev_u = entry['urgent'], prev.get('urgent', {})
        worse = [f'{k} {prev_u.get(k, 0)}→{v}' for k, v in cur_u.items()
                 if v > prev_u.get(k, 0)]
        fixed = [k for k in prev_u if k not in cur_u]
        if worse:
            print('  ⚠ 悪化: ' + ', '.join(worse))
        if fixed:
            print('  ✔ 解消: ' + ', '.join(fixed))

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
