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
import sys
from collections import defaultdict

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'scripts'))
from sitelib import today_jst, VAGUE_VENUES

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
    _AREA_ONLY = re.compile(r'(都|道|府|県|市|区|町|村)内$')

    def _vague(v):
        return v in VAGUE_VENUES or bool(_AREA_ONLY.search(v))

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
        '開催予定のものから優先する', severity='info')
    add('thin_archived', '薄い判定のうちアーカイブ許容(終了済み・出典なし)',
        sorted(e['slug'] for e in thin_all if not has_src(e) and not is_future(e)),
        '検索に出ず広告も出ない履歴データ。対処不要', severity='info')
    add('thin_needs_source', '薄い判定で開催予定なのに出典がない(要対処)',
        sorted(e['slug'] for e in thin_all if not has_src(e) and is_future(e)),
        '一次情報を見つけるか、見つからなければ掲載基準により削除')

    # 8. 説明文が短い開催予定
    add('short_descriptions', '開催予定で説明文70字未満(SERPスニペット枠を使い切れない)',
        sorted(f"{e['slug']}({len((e.get('description') or '').strip())}字)"
               for e in events
               if e.get('status') == 'upcoming' and len((e.get('description') or '').strip()) < 70), severity='info')

    # 8b. サムネイルの無い開催予定
    # トップと一覧のカードが「NO IMAGE」になる。weekly-enrichment の
    # backfill-images.py が効いているかは、この件数が週ごとに減るかでしか分からない。
    # 常時0にはならないので info。(2026-08-18 追加。追加時 61/77件)
    add('upcoming_no_image', '開催予定でimageUrlが無い(カードがNO IMAGE表示になる)',
        sorted(e['slug'] for e in events
               if e.get('status') == 'upcoming' and not (e.get('imageUrl') or '').strip()),
        'weekly-enrichment の backfill-images.py が拾えていない回。'
        '減っていなければ og:image を出さない出典が続いている', severity='info')

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

    # 14. workflowが参照するsecretの一覧(未設定だと黙って空になる)
    add('workflow_secrets', 'workflowが参照しているsecret',
        sorted(set(re.findall(r'secrets\.([A-Z_][A-Z0-9_]*)', wf))),
        '未設定でも多くのstepは失敗せず黙って空値で動く', severity='info')

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
    ld_bad, ld_drift = [], []
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

    add('rakuten_config_missing', '楽天API設定の欠落(欠けると商品画像が出ずテキスト表示になる)',
        missing_cfg, f'検索語 {len([k for k in kws if k])} 件がこの設定に依存する', severity='info')

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
