#!/usr/bin/env python3
"""audit.py — パイプライン全体の「黙って落ちているもの」を洗い出す。

作った目的(2026-07-30):
  各スクリプトが成功件数だけを出力し、除外・欠落・孤児を黙っていたため、
  問題が人に指摘されるまで表面化しなかった。存在確認ではなく整合確認を毎日回す。

読み取り専用。何も変更しない。検出結果を JSON とテキストで出す。
終了コードは常に0(検出は失敗ではない)。件数は日次メールに載せる。
"""
import html as _html
import hashlib
import html as _htmllib
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
                     is_recent_past, event_span, PAST_KEEP_MAX,
                     is_upcoming, compact_date, DESC_PROTECT_DAYS)

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


def _slurp(path):
    """読めなければ空文字。生成物の有無で検査が落ちないようにする。"""
    try:
        with open(path, encoding='utf-8') as _f:
            return _f.read()
    except OSError:
        return ''


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

    # 5. rejected-eventsとevents.jsonの矛盾。
    #     旧実装は「見送りの key が掲載 slug の部分文字列か」だけを見ていた。
    #     key は見送りを決めた日に手で付け、slug は掲載する日に別途手で付けるので、
    #     同じ回でも綴りが揃うことはまず無い。実際 2026-09-05 に見つかった3組は
    #     taniku-torai-ki-ryuo-2026-09 / taniku-toraiki-ryuoh-2026-09、
    #     gardens-umekita-2nd-anniversary-2026 / gardens-umekita-2nd-anniv-2026-09 のように
    #     どれも部分文字列にならず、**壊れていても常に0を返す検査**だった。
    #     照合は key ではなく eventDate + 名前/会場で行う。見送りの name は
    #     「イベント名 (日付 会場)」の形なので、掲載側の名前と会場のどちらかが
    #     この文字列に現れれば同じ回の疑いがある。
    #     同じ会期・同じ会場で併催される別イベント(愿 と 叢宴 のような組)は正常に出るので、
    #     見送り側に coexistsWith=<掲載slug> を書いて明示的に除外する。
    #     逃げ道があるので0にできる。よって urgent。
    rej = load_json('rejected-events.json', {})
    rej_items = rej.get('items') or []

    def _rnorm(x):
        x = unicodedata.normalize('NFKC', x or '').lower()
        # 数字は落とす。見送り側の name は「(2026-09-06 会場)」の形で日付を含むので、
        # 残すと年や日付が共通部分として拾われ、無関係な回が一致してしまう
        x = re.sub(r'[0-9]+', '', x)
        return re.sub(r'[\s\u3000!！?？「」『』()（）\"\'\-–—〜~・･./、,]+', '', x)

    def _lcs_len(a, b):
        """最長共通部分列ではなく最長共通「部分文字列」の長さ。"""
        if not a or not b:
            return 0
        prev = [0] * (len(b) + 1)
        best = 0
        for ca in a:
            cur = [0] * (len(b) + 1)
            for j, cb in enumerate(b, 1):
                if ca == cb:
                    cur[j] = prev[j - 1] + 1
                    if cur[j] > best:
                        best = cur[j]
            prev = cur
        return best

    _ev_by_date = defaultdict(list)
    for _e in events:
        if _e.get('date'):
            _ev_by_date[_e['date']].append(_e)

    conflict = []
    for r in rej_items:
        d = r.get('eventDate')
        if not d:
            continue
        rn = _rnorm(r.get('name'))
        if not rn:
            continue
        ok = r.get('coexistsWith')
        ok = {ok} if isinstance(ok, str) else set(ok or [])
        for e in _ev_by_date.get(d, []):
            slug = e.get('slug') or ''
            if slug in ok:
                continue
            # 包含では照合できない。掲載側の正式名称のほうが長いことも、
            # 会場名に「道の駅」のような接頭辞が付くこともあるため、
            # どちら向きにも効く最長共通部分文字列で見る。
            # ただし閾値4の一致だけを根拠にすると、この分野の一般語
            # (植物 / 多肉植物 / プランツ / マルシェ / popup / plants / ーパーク)が
            # 必ず引っかかって誤検知だらけになる(実測で7件)。
            # そこで名称と会場の2つが同時に当たった場合か、
            # 名称だけで8字以上の共通部分がある場合に限る。
            ven = (e.get('venue') or '').strip()
            if not ven:
                ven = re.split(r'[（(]', e.get('location') or '')[0]
            n_lcs = _lcs_len(rn, _rnorm(e.get('name')))
            v_lcs = _lcs_len(rn, _rnorm(ven)) if ven else 0
            hit = None
            if n_lcs >= 8:
                hit = f'名称「{e.get("name")}」'
            elif n_lcs >= 4 and v_lcs >= 4:
                hit = f'名称「{e.get("name")}」と会場「{ven}」'
            if hit:
                conflict.append(
                    f"{d}: 見送り {r.get('key')} と掲載 {slug} が{hit}で一致")
    add('rejected_but_listed', '見送り記録があるのに掲載されているイベント',
        sorted(set(conflict)),
        '同じ回なら見送り記録のほうを消す(掲載が正しいと判断し直した結果なので、'
        '見送りを残すと revisit の期限切れが誤って鳴り、判断の履歴も二重になる)。'
        '同じ会期・会場で併催される別イベントなら、見送り側に '
        'coexistsWith=<掲載slug> を書いて除外する')

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
    # 「画像がある件数」も残す。無い件数だけを見ていると、
    # 画像が一斉に消えた(減る)のとイベントが追加された(増える)のが
    # 同じ向き・同じ大きさに見えて区別できない(2026-08-24に検証して判明)。
    # ただし **開催予定に限った「ある件数」は、減ったからといって消失ではない。**
    # 暦が進めば画像を持つ回が past に落ちるだけで減る(2026-09-01に判明)。
    # 実測: 08-30 の 33 → 08-31 の 30 は imageUrl の削除ゼロで、
    # 8/31 に終わった3件が upcoming から外れただけだった。
    # 今日の events.json をそのまま先送りすると 9/28 に 13、10/26 に 4 まで
    # 落ちる。画像は1枚も失われていない。
    # 「追加では減らない」は正しいが、「減ったら消失」は成り立たない。
    add('upcoming_with_image', '開催予定でimageUrlがある',
        sorted(e['slug'] for e in events
               if e.get('status') == 'upcoming' and (e.get('imageUrl') or '').strip()),
        '開催予定の母数と一緒に暦で減る。消失の検出は event_image_lost が行う',
        severity='metric')

    # 消失を見たいなら、暦で動かない母集団で数える。
    # 全件の「imageUrl がある件数」は、追加でも暦でも減らない。
    # 減るのは (1) imageUrl を消した (2) イベントごと消した の2つだけで、
    # (2) は event_set_shrunk が別に見ている。
    add('events_with_image', 'imageUrlがある全イベント',
        sorted(e['slug'] for e in events if (e.get('imageUrl') or '').strip()),
        '暦では減らない。減ったぶんは imageUrl の削除かイベントの削除',
        severity='metric')
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
    # 9k-2. 同日 + 同じ出典URL の別slug。
    #     上の名前照合は、同じ回を別の表記体系で登録すると必ず素通りする。
    #     2026-09-05 に narabikakufes-vol2-2026(NARABIKAKUFES vol.2 / 奈良市役所 芝生広場)
    #     と nara-bikaku-fes-vol2-2026-10(ナラビカクフェス Vol.2 / 奈良市役所前 芝生広場)
    #     が同日・同県で並んでいた。ローマ字とカタカナは正規化しても一致せず、
    #     会場も「前」の1字違いで、名前照合も会場照合も同時に外れる。
    #     しかも入場料が 3,300円 と 入場無料 で食い違い、
    #     二重登録のまま両方が検索結果に出ていた。
    #     出典URLは表記体系に依存しないので、この抜け方を塞げる。
    #     同じ主催が同じ告知URL(IGプロフィール等)を複数の回に使うのは普通なので、
    #     日付まで一致した組だけを見る。
    def _norm_src(x):
        x = (x or '').strip().lower()
        x = re.sub(r'^https?://', '', x)
        x = re.sub(r'^www\.', '', x)
        return x.rstrip('/')

    dup_src = []
    _by_src = {}
    for e in events:
        for k in ('sourceUrl', 'url'):
            u = _norm_src(e.get(k))
            if u:
                _by_src.setdefault((e.get('date') or '', u), set()).add(e.get('slug') or '')
    for (d, u), slugs in _by_src.items():
        if d and len(slugs) > 1:
            dup_src.append(f"{d}: {', '.join(sorted(slugs))} が同じ出典 {u[:60]} を持つ")
    # 9k-3. 詳細頁の本文が「入場は無料です。」と言っているのに admission が有料。
    #     build-detail-pages は同じ規則を2か所に持っていて、FAQ側だけが
    #     admission == '入場無料' の完全一致に直され、本文側は素の
    #     `'無料' in admission` のまま残っていた。そのため
    #     「入園料 大人250円・小中高130円・未就学児無料」のような但し書きに
    #     引っかかり、有料の回が本文で無料を名乗っていた(2026-09-05 に8件)。
    #     スペック表には正しい金額が出るので、同じ頁の中で食い違う。
    #     値ではなく生成物を見る(機能確認)。判定は sitelib が単一情報源。
    #     2026-09-05(同日の後続実行): この検査は文言を1つ('入場は無料です。')しか
    #     見ておらず、直した2か所だけを見張っていた。build-detail-pages.py には
    #     同じ判断があと4か所あり、そのうち tips の「入場無料のイベントです」は
    #     修正後も同じ9件で出続けていた。JSON-LD の offers も素の判定で
    #     price="0" を出しており、リッチリザルトが有料の回を無料と申告していた
    #     (botanicbomb-vol11-fukuchiyama-2026-10)。
    #     **文言を1つだけ見張る検査は、その文言を直した瞬間に盲目になる。**
    #     無料を主張しうる表現を集合で持ち、価格の申告も同じ検査で見る。
    _FREE_CLAIMS = ('入場は無料です。', '入場無料のイベントです')
    from sitelib import admission_is_free as _adm_free
    free_bad = []
    for e in events:
        _adm = (e.get('admission') or '').strip()
        if not _adm or _adm_free(_adm):
            continue
        _p = rp('events', f"{e.get('slug')}.html")
        try:
            with open(_p, encoding='utf-8') as f:
                _pg = f.read()
        except OSError:
            continue
        _hit = [t for t in _FREE_CLAIMS if t in _pg]
        if _hit:
            free_bad.append(f"{e.get('slug')}: admission=「{_adm[:40]}」なのに本文が"
                            f"「{_hit[0]}」と書いている")
        _off = re.search(r'"offers":\s*\{.*?"price":\s*"([^"]*)"', _pg, re.S)
        if _off and _off.group(1) in ('0', ''):
            free_bad.append(f"{e.get('slug')}: admission=「{_adm[:40]}」なのに "
                            f'JSON-LD の offers.price が "{_off.group(1)}"')
    add('admission_free_mismatch', '詳細頁の本文と入場料の記載が食い違っている',
        sorted(free_bad),
        '判定は sitelib.admission_is_free() が単一情報源。'
        '素の「無料 in admission」で書くと有料の回の但し書きに引っかかる。'
        '本文・JSON-LDの両方を見る。検出したら build-detail-pages.py を直して再生成する')

    # 9k-4. 上の食い違いを生む書き方そのものを止める。
    #     sitelib に単一情報源の関数があるのに、同じ判断を素の式で書いた行を拾う。
    #     `sitelib_rule_duplicated` は「同名の def / 定数を自前で持つ」ことしか見ない。
    #     再実装が式のまま埋まっている場合(`'無料' in admission`)は名前を持たないので
    #     素通りする。実際その形で4か所に散り、2回に分けて直すことになった。
    #     文字列や註釈を拾わないよう AST の比較ノードだけを見る(naive_local_date と同じ)。
    _INLINE_RULES = {
        '無料': 'sitelib.admission_is_free()',
    }
    import ast as _ast2
    _inline_dup = []
    for _f in sorted(glob.glob(rp('scripts', '*.py')) + [rp('build-detail-pages.py')]):
        _rel = os.path.relpath(_f, REPO)
        if os.path.basename(_f) in ('sitelib.py', 'audit.py'):
            continue
        try:
            _tree = _ast2.parse(_slurp(_f))
        except SyntaxError:
            continue
        for _n in _ast2.walk(_tree):
            if not isinstance(_n, _ast2.Compare):
                continue
            if not any(isinstance(o, _ast2.In) for o in _n.ops):
                continue
            _lit = _n.left
            if not (isinstance(_lit, _ast2.Constant) and isinstance(_lit.value, str)):
                continue
            _own = _INLINE_RULES.get(_lit.value)
            if _own:
                _inline_dup.append(f"{_rel}:{_n.lineno}: '{_lit.value}' in ... "
                                   f'— 判定は {_own} が単一情報源')
    add('inline_rule_reimplementation', 'sitelib の判定を素の式で書き直している',
        sorted(_inline_dup),
        'sitelib の関数を呼ぶ。素の in 判定は但し書き(「未就学児無料」等)に引っかかり、'
        '同じ規則が複数箇所に散ると片方だけ直して残りが生き残る')

    add('duplicate_event_same_source', '同日の別slugが同じ出典URLを指している',
        sorted(set(dup_src)),
        '表記違い(ローマ字/カタカナ)や会場名の1字違いで duplicate_event_entry を'
        'すり抜けた二重登録の候補。同じ回なら情報量の多い側に寄せて片方を消す。'
        '同じ主催が同じ会場で併催する別イベントは正常に出る'
        '(第6回 天下一植物界 と BORDER BREAK!! 6th が no1plantae.com を共有する組が実例)。'
        'つまりゼロにはならないので info。urgent にすると併催のたびに鳴る', severity='info')

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
    # 手で走らせる前提のスクリプトは自動実行の対象ではない。
    # ここに足すときは、そのスクリプトの docstring に「なぜ自動化しないか」を書くこと。
    MANUAL_ONLY = {
        # アイコンはビルドのたびに変わらない。cairosvg を CI の依存に足すと
        # ビルド全体が壊れる面が増えるだけなので、形を変えたいときだけ回す
        'build-icons.py',
    }
    # スケジュールタスクが直接呼ぶスクリプトは build-all.sh にも workflow にも
    # 出てこない。呼び出し元はプレイブックなので、そこも参照元として数える
    # (2026-09-02 に record-run.py を足して判明)。
    try:
        pb = open(rp('docs', 'task-playbook.md'), encoding='utf-8').read()
    except OSError:
        pb = ''
    unused = []
    for f in sorted(glob.glob(rp('scripts', '*.py'))) + [rp('build-detail-pages.py')]:
        bn = os.path.basename(f)
        if bn in ('sitelib.py', 'audit.py') or bn in MANUAL_ONLY:
            continue
        if bn not in ba and bn not in wf and bn not in pb:
            unused.append(bn)
    add('unreferenced_scripts',
        'build-all.shもworkflowもプレイブックも参照していないスクリプト',
        unused, '使われていないか、呼び出しが失われている。'
        '手動実行が正しいものは audit.py の MANUAL_ONLY に理由つきで足す')

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

    # JSでのローカルタイムゾーン依存の日付計算。
    # 「今日」はJSTで決まるので、閲覧者のタイムゾーンを混ぜてはいけない。
    # 正しい形は new Date(Date.now() + 9*3600000) + getUTC*() だけで足り、
    # getTimezoneOffset() も setHours(0,...) も要らない。出てきたら誤り。
    # 2026-08-29: getTime() に getTimezoneOffset() を足していたため
    # JSTの閲覧者だけ 0:00〜9:00 に前日と判定され、
    # 「本日開催」が「明日開催」と出ていた(status-auto.js と affiliate.js)。
    tz_bad = []
    _tz_re = re.compile(r'getTimezoneOffset|setHours\(\s*0\s*,')
    for f in sorted(glob.glob(rp('*.js'))):
        try:
            src = open(f, encoding='utf-8').read()
        except OSError:
            continue
        for i, line in enumerate(src.splitlines(), 1):
            if line.lstrip().startswith('//'):
                continue          # 注意書きは対象外
            if _tz_re.search(line):
                tz_bad.append(f'{os.path.basename(f)}:{i} {line.strip()[:70]}')
    add('js_local_timezone_math', 'JSが閲覧者のタイムゾーンで日付を計算している',
        sorted(tz_bad),
        'JSTの暦日は new Date(Date.now()+9*3600000) と getUTC*() で出す。'
        '境界は scripts/test-date-boundary.js が検証する')

    # 日付境界テストがビルドチェーンに載っているか(外されたら気づけない)
    try:
        _ba = open(rp('scripts', 'build-all.sh'), encoding='utf-8').read()
    except OSError:
        _ba = ''
    add('date_boundary_test_unwired', '日付境界テストがbuild-all.shから外れている',
        [] if 'test-date-boundary.js' in _ba else ['scripts/build-all.sh'],
        '生成物を見ても分からない不具合なので、生成前に落とす')

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
    # 16b. index.html のカード属性が events.json と食い違っていないか。
    #      カードの data-date / data-status は status-auto.js が
    #      「開催中 / これから開催 / 終了」の振り分けに使う。古いまま残ると
    #      データは正しいのに一覧から消える。JSON-LDや詳細ページは再生成されるので
    #      他の検査は全部通り、誰も気づけない。
    #      2026-08-27に発覚: 木更津園芸市は 8/11→8/29 に直っていたのに
    #      カードが data-date="2026-08-11" data-status="past" のままで、
    #      9日間「終了したイベント」の節に隠れていた。同種が22件あった。
    #      直し方は `python3 scripts/sync-index-cards.py`。
    _card_attr_bad = []
    try:
        with open(rp('index.html'), encoding='utf-8') as f:
            _idx = f.read()
    except OSError:
        _idx = ''
    if _idx:
        _ev_by_slug = {e.get('slug'): e for e in events if e.get('slug')}
        for _tag in re.findall(r'<div class="event-card[^>]*>', _idx):
            _sm = re.search(r'data-slug="([^"]+)"', _tag)
            if not _sm:
                continue
            _e = _ev_by_slug.get(_sm.group(1))
            if not _e:
                continue
            _want = {
                'date': _e.get('date') or '',
                'date-end': _e.get('dateEnd') or _e.get('date') or '',
                'status': _e.get('status') or '',
                'prefecture': _e.get('prefecture') or '',
                'region': _e.get('region') or '',
            }
            for _k, _v in _want.items():
                _am = re.search(r'data-%s="([^"]*)"' % _k, _tag)
                _got = _am.group(1) if _am else None
                if _got != _v:
                    _card_attr_bad.append(
                        f"{_sm.group(1)}: data-{_k} 頁={_got!r} data={_v!r}")
    # 本文（日付・タイトル・説明文）も同じ理由で古いまま残る。
    # 属性より実害が直接的で、来場者が読む文字そのものが間違う。
    # 2026-08-27時点で26件（説明文22・日付5・タイトル1）。
    # 「第8回 花友フェスタ 2026」のように前回開催の名前が残っている回もあった。
    _card_body_bad = []
    if _idx:
        _chunks = re.split(r'(?=<div class="event-card" )', _idx)
        for _ch in _chunks:
            _sm = re.search(r'data-slug="([^"]+)"', _ch)
            if not _sm:
                continue
            _e = _ev_by_slug.get(_sm.group(1))
            if not _e:
                continue
            _dm = re.search(r'<span class="event-date">([^<]*)</span>', _ch)
            _tm = re.search(r'<h\d class="event-title">([^<]*)</h\d>', _ch)
            _pm = re.search(r'<p class="event-description">(.*?)</p>', _ch, re.S)
            # 頁の側は & や < がエスケープされている。戻さずに比べると
            # 名前に & を含む回が永久に不一致として出続ける
            # (2026-08-31「ビカクシダ板付け相談会 & 即売会」で検出)
            _ue = _htmllib.unescape
            if _dm and _ue(_dm.group(1)) != compact_date(_e):
                _card_body_bad.append(
                    f"{_sm.group(1)}: 日付 頁={_dm.group(1)!r} data={compact_date(_e)!r}")
            if _tm and _ue(_tm.group(1)) != (_e.get('name') or ''):
                _card_body_bad.append(
                    f"{_sm.group(1)}: 名称 頁={_tm.group(1)[:24]!r} data={(_e.get('name') or '')[:24]!r}")
            if _pm and _ue(_pm.group(1)).strip() != (_e.get('description') or '').strip():
                _card_body_bad.append(f"{_sm.group(1)}: 説明文が古い")
    add('index_card_body_drift', 'トップのカード本文がevents.jsonと不一致(古い日付・名称が出る)',
        sorted(_card_body_bad),
        '来場者が読む文字そのものが古い。scripts/sync-index-cards.py で直す')

    add('index_card_attr_drift', 'トップのカード属性がevents.jsonと不一致(一覧から消える)',
        sorted(_card_attr_bad),
        'status-auto.js がこの属性で開催中/終了を振り分けるため、'
        '古いと正しいデータでも一覧に出ない。scripts/sync-index-cards.py で直す')

    # 16c. 他所に載っていて当サイトに無いイベント（取りこぼし）。
    #      2026-08-27、「今週末の関東は？」に答えられなかった。掲載2件に対して
    #      実際は関東で10件以上、9月は全国で42件の未掲載があった。
    #      **そのとき audit は urgent 0 / info 0 だった。**
    #      手元のデータの整合性は完璧で、外の世界に対して欠けていることを
    #      誰も見ていなかった。イベント掲載サイトにとってこれがいちばん重い。
    #      scripts/coverage-sweep.py が毎日書き出す coverage-gaps.json を読む。
    _cov = load_json('coverage-gaps.json', {})
    _cov_gaps = _cov.get('gaps') or []
    _cov_err = _cov.get('errors') or []
    _swept = str(_cov.get('sweptOn') or '')
    _cov_items = [f"{g.get('date')} {str(g.get('title'))[:90]}" for g in _cov_gaps]
    add('coverage_gaps', '他所に出ていて当サイトに無いイベント候補',
        sorted(_cov_items),
        '一次情報で裏取りして、掲載するか rejected-events.json に落とす。'
        '見送ったものは rejected に入れれば翌日から候補に出なくなる',
        severity='info')

    # 巡回そのものが失敗していないか。gaps が0件でも
    # 巡回できていなければ「取りこぼしなし」とは言えない
    _cov_stale = []
    if not _cov:
        _cov_stale.append('coverage-gaps.json が無い。coverage-sweep.py が動いていない')
    else:
        if _cov_err:
            _cov_stale.extend(f'巡回失敗: {e}' for e in _cov_err[:10])
        if not (_cov.get('stats') or {}).get('fetched'):
            _cov_stale.append('1日も取得できていない。取得元の構造が変わった可能性')
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', _swept):
            import datetime as _dtc
            try:
                _gap_d = (_dtc.date.fromisoformat(today_jst())
                          - _dtc.date.fromisoformat(_swept)).days
                if _gap_d > 3:
                    _cov_stale.append(f'最終巡回 {_swept} / {_gap_d}日前。巡回が止まっている')
            except ValueError:
                pass
    add('coverage_sweep_broken', '取りこぼし巡回が機能していない',
        sorted(_cov_stale),
        'coverage-sweep.py の取得が失敗している。'
        'この状態では coverage_gaps が0件でも取りこぼしが無い証拠にならない')

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
    # 2026-08-24にGAS連携が稼働し、lastChecked はGASが「フォーム送信を受けた日」に
    # 書き換えるフィールドになった。送信が無ければ更新されないので、
    # lastChecked の古さは異常の証拠ではなくなった(そのまま監視すると必ず誤検知する)。
    # 監視対象は event-listing-review が毎回書く reviewedOn に移す。
    # こちらは「タスクが動いて処理まで到達したか」を表す。
    inq_stale = []
    _ni = load_json('new-inquiries.json', {})
    _rv = str(_ni.get('reviewedOn') or '').strip()
    import datetime as _dtm
    if not _rv:
        inq_stale.append(
            'reviewedOn が無い。event-listing-review が一度も書き込めていない')
    elif not re.fullmatch(r'\d{4}-\d{2}-\d{2}', _rv):
        inq_stale.append(f'reviewedOn が日付として読めない: {_rv!r}')
    else:
        try:
            _gap = (_dtm.date.fromisoformat(today_jst())
                    - _dtm.date.fromisoformat(_rv)).days
        except ValueError:
            _gap = None
            inq_stale.append(f'reviewedOn が日付として読めない: {_rv!r}')
        if _gap is not None and _gap > 3:
            inq_stale.append(
                f'reviewedOn={_rv} / {_gap}日前。event-listing-review が動いていない')

    # items が積まれたまま放置されていないか。GASが書き、タスクが処理して空にする。
    # 4日以上残っているなら、届いた問い合わせが誰にも処理されていない。
    _items = _ni.get('items') or []
    if _items:
        _oldest = None
        for _it in _items:
            _ts = str(_it.get('timestamp') or '')[:10].replace('/', '-')
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', _ts):
                _oldest = _ts if _oldest is None else min(_oldest, _ts)
        if _oldest:
            try:
                _ig = (_dtm.date.fromisoformat(today_jst())
                       - _dtm.date.fromisoformat(_oldest)).days
                if _ig > 3:
                    inq_stale.append(
                        f'未処理の問い合わせが {len(_items)}件、最古 {_oldest}（{_ig}日前）')
            except ValueError:
                pass
    add('inquiry_check_stale', '掲載申請フォームの処理が止まっている',
        inq_stale,
        'reviewedOn は event-listing-review が毎回書く（タスクが動いた証拠）。'
        'lastChecked はGASが書く（フォーム送信を受けた日）ので、古くても異常ではない。'
        'items が残り続けている場合は届いた問い合わせが未処理')

    # --- 抜けた実行日そのものを数える -------------------------------------
    # inquiry_check_stale は「今どれだけ古いか」しか見ないので、
    # 1日抜けても翌日の回が成功した瞬間に痕跡が消え、事後に検出できない。
    # 実際 08-14〜17 / 08-19 / 08-21〜23 / 08-26 の抜けは、どれも
    # 次の回が reviewedOn を上書きしたことで無かったことになっていた。
    # reviewedHistory に実行日を残し、窓の中の抜けを数える。
    # 抜けが増える向きにしか動かない指標なので、放置すれば必ず表に出る。
    # 閾値を1日に下げて stale 側で鳴らす案は採らない。実行時刻とCIの時差だけで
    # 誤検知するため(だから stale は4日目から鳴らす)。日付の集合で見れば時差は影響しない。
    inq_gap = []
    _hist = [h for h in (_ni.get('reviewedHistory') or [])
             if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(h))]
    # 履歴が浅いうちは判定しない。無い日を抜けとみなすと導入初日に必ず誤検知する。
    # reviewedSince より前も判定しない。task-runs.json と同じ扱い。
    # 記録の仕組みが働いていなかった期間を遡って「抜け」と呼ぶと、
    # 実際には毎日走っていた日が抜けとして出続ける(2026-09-02 に是正)。
    _since = str(_ni.get('reviewedSince') or '').strip()
    if len(_hist) >= 3:
        try:
            _today = _dtm.date.fromisoformat(today_jst())
            _seen = {_dtm.date.fromisoformat(h) for h in _hist}
            _start = max(min(_seen), _today - _dtm.timedelta(days=7))
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', _since):
                _start = max(_start, _dtm.date.fromisoformat(_since))
            # 当日は監査より後に走ることがあるので窓に入れない。
            _missing = [
                (_start + _dtm.timedelta(days=i)).isoformat()
                for i in range((_today - _dtm.timedelta(days=1) - _start).days + 1)
                if (_start + _dtm.timedelta(days=i)) not in _seen
            ]
            if _missing:
                inq_gap.append(
                    'event-listing-review が動かなかった日: '
                    + ' '.join(_missing) + f'（直近7日で{len(_missing)}日）')
        except ValueError:
            pass
    # --- 回答シートの実測行数と処理済み件数の突き合わせ ---------------------
    # gviz CSV でシートのデータ行を数えて processed と比べる手順は 2026-08-25 から
    # 毎回やっているが、結果は task-reports の散文にしか残っていなかった。
    # 読むコードが無いので、読み違えても「検算通過」と書けてしまう。
    # プレイブックに「必ず数える」と書いた時点で検査にする、という自分の規則に反していた。
    # そこで event-listing-review が実測値を new-inquiries.json に書き、ここで照合する。
    # 不変量: シートのデータ行 == 処理済み + 未処理。
    #   行 > 期待 … GASがフォーム送信を取りこぼしている(backfillFromSheet の出番)
    #   行 < 期待 … シートの読み取りに失敗している(0行や見出しだけで返る経路がある)
    # CI から Google は見られないので、値そのものはタスクしか取れない。
    # だからこの検査は「タスクが持ち帰った数字」の整合だけを見る。
    inq_sheet = []
    _rows = _ni.get('sheetRows')
    _sco = str(_ni.get('sheetCheckedOn') or '').strip()
    # キーが無い回は判定しない。導入前のデータを0とみなすと初日に必ず誤検知する。
    if isinstance(_rows, int) and not isinstance(_rows, bool):
        _pr = load_json('inquiries-processed.json', {}).get('processed') or []
        _expect = len(_pr) + len(_items)
        if _rows > _expect:
            inq_sheet.append(
                f'回答シートのデータ行 {_rows} > 処理済み {len(_pr)} + 未処理 {len(_items)}。'
                'GASがフォーム送信を取りこぼしている。backfillFromSheet を実行する')
        elif _rows < _expect:
            inq_sheet.append(
                f'回答シートのデータ行 {_rows} < 処理済み {len(_pr)} + 未処理 {len(_items)}。'
                'シートの読み取りに失敗した値を持ち帰っている')
        # 2026-08-31 に書く側が変わった。sheetRows / sheetCheckedOn は
        # GAS の onFormSubmit が countSheetRows() の結果を書く値であり、
        # タスクは書かない(組み込みブラウザは Google にログインしておらず、
        # 回答シートを読む手段がそもそも無い)。
        # ここに元々あった「sheetCheckedOn < reviewedOn なら
        # シートを見ないまま終わっている」は、タスクが自分で数えていた頃の
        # 不変量で、今は**フォーム送信が無い日は必ず成立する**。
        # つまりタスクが正常に動くほど毎日 urgent が鳴る検査になっていた
        # (2026-09-01 に検出。検出側だけ旧設計のまま残っていた)。
        #
        # 新しい設計で意味を持つのは GAS の2つの書き込みの前後関係。
        # lastChecked(送信を受けた日)より sheetCheckedOn が古いなら、
        # 送信は受けているのに行数を書いていない = countSheetRows を持たない
        # 版の GAS が動いている。これは実際に起こりうる壊れ方で、
        # 起きると sheetRows が古い値のまま照合を素通りする。
        _lc = str(_ni.get('lastChecked') or '').strip()
        if (re.fullmatch(r'\d{4}-\d{2}-\d{2}', _lc)
                and re.fullmatch(r'\d{4}-\d{2}-\d{2}', _sco) and _sco < _lc):
            inq_sheet.append(
                f'sheetCheckedOn={_sco} が lastChecked={_lc} より古い。'
                'GASはフォーム送信を受けているのに行数を書いていない'
                '(countSheetRows を持たない版が動いている可能性)')
    add('inquiry_sheet_row_mismatch', '回答シートと処理済み件数が合わない',
        inq_sheet,
        note='回答シートのデータ行数は GAS の onFormSubmit が sheetRows / '
             'sheetCheckedOn に書く(タスクからシートは読めない)。'
             '行数が処理済み+未処理と一致するのが正常。'
             '多ければGASの取りこぼし(backfillFromSheet)、少なければ書き込みの失敗。'
             'sheetCheckedOn が lastChecked より古い回は、送信は受けているのに'
             '行数を書いていない')

    add('inquiry_review_gap', 'event-listing-review の実行が抜けた日', inq_gap,
        note='reviewedHistory は起動日の記録で、scripts/record-run.py が'
             '起動直後に書く。抜けた日は、届いていた問い合わせがその日は'
             '誰にも見られていない。ただし 2026-09-02 までの空白は'
             '「走らなかった」ではなく「走ったが記録できていなかった」で、'
             'reviewedSince より前は判定しない。'
             'ゼロが続くとは限らない（Chromeの許可待ちで落ちる回がある）ため info',
        severity='info')

    # --- スケジュールタスクそのものが動いたか -------------------------------
    # reviewedHistory で event-listing-review の抜けは拾えるようになったが、
    # 同じ穴が他の3タスクに残っていた。実行の記録が repo に一切無いため、
    # 週次の site-health-check が 2026-08-25 に成果物ゼロで終わったことは
    # 今日(08-31)に task-reports のファイル名を人が並べるまで誰も知らなかった。
    # スケジュール側の lastRunAt は最新1回しか持たないので、
    # 次の回が走った時点で抜けた週は事後に判定できなくなる。
    # 対処は reviewedHistory と同じ形。タスクが実行日を台帳に書き、
    # ここで cadence から期待日を作って差を出す。
    # event-listing-review は載せない。同じ記録を2か所に持つと必ず食い違う
    # (generate-rss.py が TAG_ROMAJI の写しを持って壊れたのと同じ型)。
    # severity は info。daily のタスクは Chrome の許可待ちなどで実際に落ちる回があり、
    # 0が正常とは言えない。urgent にすると鳴りっぱなしになって読まれなくなる。
    task_gap = []
    _tr = load_json('task-runs.json', {}).get('tasks') or {}
    try:
        _tday = _dtm.date.fromisoformat(today_jst())
    except ValueError:
        _tday = None
    for _tid in sorted(_tr):
        _cfg = _tr[_tid] or {}
        _cad = str(_cfg.get('cadence') or '').strip()
        if _tday is None or _cad not in ('daily', 'weekly'):
            task_gap.append(f'{_tid}: cadence が daily/weekly でない({_cad!r})')
            continue
        _since_s = str(_cfg.get('since') or '').strip()
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', _since_s):
            task_gap.append(f'{_tid}: since が YYYY-MM-DD でない({_since_s!r})')
            continue
        _seen = {h for h in (_cfg.get('history') or [])
                 if re.fullmatch(r'\d{4}-\d{2}-\d{2}', str(h))}
        _since = _dtm.date.fromisoformat(_since_s)
        # 窓は daily=7日 / weekly=28日(4回ぶん)。当日は監査より後に走ることが
        # あるので窓に入れない。since より前は台帳が無いので判定しない。
        _win = 7 if _cad == 'daily' else 28
        _start = max(_since, _tday - _dtm.timedelta(days=_win))
        _end = _tday - _dtm.timedelta(days=1)
        if _cad == 'daily':
            _miss = []
            _d = _start
            while _d <= _end:
                if _d.isoformat() not in _seen:
                    _miss.append(_d.isoformat())
                _d += _dtm.timedelta(days=1)
            if _miss:
                task_gap.append(
                    f'{_tid}(daily) が動かなかった日: ' + ' '.join(_miss)
                    + f'（直近{_win}日で{len(_miss)}日）')
        else:
            # 週次は曜日で照合しない。GitHub と同じでタスクの起動も遅れるし、
            # 実際 08-17 起動の回のレポートは 08-18 付で残っている。
            # 曜日一致にすると1日ずれただけで鳴り、鳴りっぱなしになる。
            # 見たいのは「1週まるごと抜けたか」なので、
            # 昨日から7日ずつ遡った窓のそれぞれに実行が1回あるかで見る。
            _miss = []
            for _k in range(_win // 7):
                _wend = _end - _dtm.timedelta(days=7 * _k)
                _wstart = _wend - _dtm.timedelta(days=6)
                if _wstart < _since:
                    break
                if not any(_wstart <= _dtm.date.fromisoformat(h) <= _wend
                           for h in _seen):
                    _miss.append(f'{_wstart.isoformat()}〜{_wend.isoformat()}')
            if _miss:
                task_gap.append(
                    f'{_tid}(weekly) の実行が無かった週: ' + ' '.join(_miss)
                    + f'（直近{_win // 7}週で{len(_miss)}週）')
    add('task_run_gap', 'スケジュールタスクの実行が抜けた日', task_gap,
        note='task-runs.json はタスクが毎回自分の実行日を書く台帳。'
             'スケジュール側の lastRunAt は最新1回しか持たないので、'
             '抜けた日は次の回が走った時点で検出できなくなる。'
             '成果物が無いまま終わった回もここに出ないので、'
             'この台帳が repo 側に残る唯一の生存記録になる。'
             '週次は曜日ではなく「7日の窓に1回あるか」で見る(起動の遅れで1日ずれるため)。'
             'event-listing-review は new-inquiries.json の reviewedHistory 側で見る',
        severity='info')

    # --- 手でやる巡回が止まっていないか -------------------------------------
    # CI から読めない情報源(NextMeet・Instagram)は coverage-sweep.py で
    # 自動化できないので、回ったかどうかが repo のどこにも残らない。
    # 2026-09-06、coverage-gaps.json は 0件(LEAFLA 由来の自動巡回)だったのに、
    # NextMeet の月別ページを手で開いたら未掲載が15件出た。
    # 「アグリゲータ3社は互いに取りこぼす」はプレイブック §3 に前から
    # 書いてあるが、機械化されていたのは LEAFLA だけで、残り2社を回ったかは
    # 誰も見ていなかった。reviewedHistory / task-runs.json と同じ型の穴で、
    # **記録が無い手順は、やらなくても誰も気づかない。**
    # 判定は「最後に回った日からの経過日数」だけ。0が正常な検査なので urgent。
    sweep_stale = []
    _ms = load_json('manual-sweeps.json', {}).get('sweeps') or {}
    try:
        _mday = _dtm.date.fromisoformat(today_jst())
    except ValueError:
        _mday = None
    for _sid in sorted(_ms):
        _sc = _ms[_sid] or {}
        _last = str(_sc.get('lastSweptOn') or '').strip()
        _stale = _sc.get('staleDays')
        if not isinstance(_stale, int) or _stale <= 0:
            sweep_stale.append(f'{_sid}: staleDays が正の整数でない({_stale!r})')
            continue
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', _last):
            sweep_stale.append(f'{_sid}: lastSweptOn が YYYY-MM-DD でない({_last!r})')
            continue
        if _mday is None:
            continue
        _age = (_mday - _dtm.date.fromisoformat(_last)).days
        if _age < 0:
            sweep_stale.append(f'{_sid}: lastSweptOn={_last} が未来日')
        elif _age > _stale:
            sweep_stale.append(
                f'{_sid}({_sc.get("label") or ""}): 最後に回ったのは {_last}'
                f'（{_age}日前 / 上限{_stale}日）')
    add('manual_sweep_stale', '手でやる巡回が止まっている', sweep_stale,
        note='manual-sweeps.json は agave-event-update が毎回書く台帳。'
             'NextMeet と まとめブログは CI から読めないので coverage-sweep.py に'
             '入れられず、回ったかどうかを残せるのはこのファイルだけ。'
             'coverage-gaps.json が0件でも「取りこぼし無し」の証拠にならない'
             '(あれは LEAFLA しか見ていない)。'
             '回った日に lastSweptOn / lastScope / history を更新する。'
             '回れなかった回は進めない。進めると回った回と区別が付かなくなる')

    # --- フィードの pubDate がビルドのたびに動いていないか ------------------
    # 2026-08-30 に sitemap の lastmod で塞いだのと同じ型。
    # generate-rss.py は addedDate が無い回に datetime.now() を入れており、
    # 毎日の再生成でその回の pubDate が「今」に更新されていた。
    # 購読側は pubDate で並べ替えと新着判定をするので、
    # 中身が変わっていない回が毎日いちばん上に新着として出ることになる。
    # 判定は時計に依存させない。同じフィードの lastBuildDate と一致する
    # pubDate は、ビルドの瞬間を発行日として名乗っているということ。
    # 実データの日付は 00:00:00 で入るので、正常な回は秒まで一致しない。
    feed_pub = []
    for _fp in sorted(glob.glob(rp('feeds', '*.xml')) + [rp('rss.xml')]):
        try:
            with open(_fp, encoding='utf-8') as f:
                _fs = f.read()
        except OSError:
            continue
        _lb = re.search(r'<lastBuildDate>(.*?)</lastBuildDate>', _fs)
        if not _lb:
            continue
        _n = sum(1 for _p in re.findall(r'<pubDate>(.*?)</pubDate>', _fs)
                 if _p == _lb.group(1))
        if _n:
            feed_pub.append(
                f'{os.path.relpath(_fp, REPO)}: {_n}件の pubDate が '
                'lastBuildDate と同時刻(ビルド時刻を発行日にしている)')
    add('feed_pubdate_unstable', 'フィードのpubDateがビルド時刻になっている',
        feed_pub,
        note='pubDate は addedDate / updatedAt / enrichedAt から作る。'
             'どれも無い回は pubDate ごと出さない(RSS 2.0 で任意)。'
             'now() を入れると再生成のたびに新着として再浮上する')

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

    # --- ランディング頁のイベント集合 ------------------------------------------
    # 同じ穴を塞ぐのはこれで3度目。index.html に index_card_drift を付け(2026-08-24)、
    # 同じ作り方の calendar/map を漏らして embedded_event_set_drift を足し(2026-08-27)、
    # **/tag /pref /region /archive の88頁はどちらの母集団にも入っていなかった**。
    # この88頁は掲載イベントの主要な入口(sitemap掲載・index対象)で、
    # 1頁でも集合がずれると、その県・そのタグから見た人にはイベントが存在しない。
    # 選定規則は写しではない: tag=そのタグを持つ全件 / pref=その県の全件 /
    # region=その地方の全件 / archive/YYYY-MM=開始月 / archive/YYYY=開始年、と
    # generate-landing-pages.py の分類そのものが events.json から一意に決まる。
    # 節への振り分け(開催中/これから/終了)は is_upcoming が見るのでここでは数えない。
    # 集合が一致するかだけを見る。
    _want_landing = defaultdict(set)
    for e in events:
        _sl = e.get('slug')
        if not _sl:
            continue
        for t in e.get('tags') or []:
            _want_landing[('tag', tag_slug(t))].add(_sl)
        if e.get('prefecture'):
            _want_landing[('pref', pref_slug(e['prefecture']))].add(_sl)
        if e.get('region'):
            _want_landing[('region', region_slug(e['region']))].add(_sl)
        _d = e.get('date') or ''
        if len(_d) >= 7:
            _want_landing[('archive', _d[:7])].add(_sl)
        if len(_d) >= 4:
            _want_landing[('archive', _d[:4])].add(_sl)
    landing_drift = []
    for (_kind, _sl2), _want in sorted(_want_landing.items()):
        _rel2 = f'{_kind}/{_sl2}/index.html'
        _pg2 = _slurp(rp(_kind, _sl2, 'index.html'))
        if not _pg2:
            landing_drift.append(f'{_rel2}: 頁が無い(掲載{len(_want)}件)')
            continue
        _got = set(re.findall(r'data-slug="([^"]+)"', _pg2))
        _miss = sorted(_want - _got)
        _extra = sorted(_got - _want)
        if _miss:
            landing_drift.append(f'{_rel2}: 載っていない {len(_miss)}件 (例 {_miss[0]})')
        if _extra:
            landing_drift.append(f'{_rel2}: 余分 {len(_extra)}件 (例 {_extra[0]})')
    add('landing_event_set_drift', 'ランディング頁のイベント集合がevents.jsonと不一致',
        landing_drift,
        'generate-landing-pages.py を再実行する。events.json を直して再生成しないと、'
        '県頁・タグ頁からその回が消えたまま残る')

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

    # --- リポジトリにある .html は全部が公開URL -------------------------------
    # GitHub Pages はリポジトリの中身をそのまま配信するので、
    # 「サイトの頁ではない」つもりで置いた .html も公開URLになる。
    # ところが上の orphan / link / title / description の各検査は
    # templates・staging・guides_content を頁の母集団から外しており、
    # **除外した先だけは誰も見ていない**状態だった。
    # 2026-09-01 実測: templates/detail.html が
    # https://agave-navi.com/templates/detail.html として配信されており、
    #   - <title> が `{{name}} | アガベイベントナビ`
    #   - canonical が存在しない `/events/{{slug}}.html`
    #   - robots が置換前の `{{robotsMeta}}` なので noindex にならない
    # という壊れた頁が index 対象のまま生きていた(.nojekyll があり
    # robots.txt も全許可)。どこからもリンクされていないので
    # orphan_indexable_page が拾うはずだったが、母集団から外れていて出ない。
    # 対処はテンプレートを .html 以外の拡張子にすること(配信されても頁にならない)。
    # 検査は2方向を見る。
    #   1. 未展開の {{placeholder}} を含む .html があるか
    #      (テンプレートの直置き、および置換漏れの生成物を同時に拾う)
    #   2. 頁の検査から外した階層に .html が残っていないか
    _PLACEHOLDER = re.compile(r'\{\{\s*[A-Za-z_]\w*\s*\}\}')
    _NON_PAGE_DIRS = ('templates', 'staging', 'guides_content')
    published_templates = []
    for path in glob.glob(rp('**', '*.html'), recursive=True):
        rel = os.path.relpath(path, REPO).replace(os.sep, '/')
        try:
            with open(path, encoding='utf-8', errors='replace') as f:
                body = f.read()
        except OSError:
            continue
        found = sorted(set(_PLACEHOLDER.findall(body)))
        if found:
            published_templates.append(
                f'{rel}: 未展開の置換子 {len(found)}種({", ".join(found[:3])}…)')
        elif rel.split('/')[0] in _NON_PAGE_DIRS:
            published_templates.append(
                f'{rel}: 頁の検査から外した階層に .html がある')
    add('unrendered_template_published', '未展開のテンプレートが公開URLになっている',
        sorted(published_templates),
        'テンプレートは .tmpl など .html 以外の拡張子にする'
        '(GitHub Pages はリポジトリを丸ごと配信するので、置き場を変えても隠れない)。'
        '生成物側に出たなら build の置換漏れ')

    # --- Instagram埋め込みが黙って消えていないか -----------------------------
    # build-detail-pages.make_instagram_section は、投稿IDが取れないと
    # return '' で節ごと消す。例外も警告も出ないので、頁を開くまで気づけない。
    # 2026-08-27、リールのURL(/reel/<id>/)だけを持つ回で実際に消えていた
    # (extractor が /p/ しか見ていなかった)。IGは主催者の一次情報の主戦場で、
    # 埋め込みが消えると詳細頁からその回の告知への導線が無くなる。
    # ここは「値が在るか」ではなく「頁に出ているか」を見る(機能確認)。
    _IG_ID = re.compile(r'/(?:p|reel|reels|tv)/([A-Za-z0-9_-]+)')
    ig_lost = []
    for e in events:
        _sl = e.get('slug') or ''
        _pid = (e.get('instagramPostId') or '').strip()
        _iurl = (e.get('instagramUrl') or '').strip()
        if not _pid and not _iurl:
            continue
        if not _pid and not _IG_ID.search(_iurl):
            ig_lost.append(f'{_sl}: instagramUrl から投稿IDが取れない形 → {_iurl}')
            continue
        _pg = rp('events', f'{_sl}.html')
        if not os.path.exists(_pg):
            continue        # missing_detail_pages 側で鳴る
        try:
            with open(_pg, encoding='utf-8') as f:
                _h = f.read()
        except OSError:
            continue
        if 'detail-instagram-embed' not in _h:
            ig_lost.append(f'{_sl}: IGの値はあるのに埋め込み節が頁に無い')
        else:
            _want = _pid or _IG_ID.search(_iurl).group(1)
            if f'/p/{_want}/embed/' not in _h:
                ig_lost.append(f'{_sl}: 埋め込みの投稿IDが events.json と違う（期待 {_want}）')
    add('instagram_embed_missing', 'IGの値があるのに詳細頁に埋め込みが出ていない',
        sorted(ig_lost),
        'make_instagram_section が投稿IDを取れずに空を返している。'
        'URLの形を増やしたら extractor の正規表現も足す。'
        '値だけ直して再生成しないと頁は変わらない')

    # --- カレンダー・マップの埋め込み集合 -------------------------------------
    # build-static-html.py は既存HTMLへの挿入で作る。置換に失敗すると
    # 消さずに足すだけになり、過去に calendar/map が 4.2MB まで肥大した。
    # index.html には index_card_drift を付けたが、同じ作り方のこの2頁は
    # 「冪等に書くこと」という注意書きだけで、数える側が無かった。
    # 3つの表現(インラインJSON / SSRの一覧 / ItemListのJSON-LD)が同じ集合を
    # 指しているかも見る。1つだけ古いと、見る経路によって件数が違う頁になる。
    embed_drift = []
    _want_up = {e.get('slug') for e in events
                if e.get('status') != 'past' and is_upcoming(e, today_s)}
    for _f in ('calendar.html', 'map.html'):
        try:
            with open(rp(_f), encoding='utf-8') as fh:
                _h = fh.read()
        except OSError:
            embed_drift.append(f'{_f}: 読めない')
            continue
        _inline = re.findall(
            r'<script[^>]*type="application/json"[^>]*>(.*?)</script>', _h, re.S)
        if len(_inline) != 1:
            embed_drift.append(
                f'{_f}: インラインJSONが{len(_inline)}個（1個が正常。挿入が重なっている）')
        for _b in _inline:
            try:
                _d = json.loads(_b)
            except ValueError:
                embed_drift.append(f'{_f}: インラインJSONが壊れている')
                continue
            _arr = _d if isinstance(_d, list) else (_d.get('events') or [])
            _got = [x.get('slug') for x in _arr if isinstance(x, dict)]
            _dupe = sorted({sl for sl in _got if _got.count(sl) > 1})
            if _dupe:
                embed_drift.append(f'{_f}: インラインJSONに重複 {_dupe[:3]}')
            for sl in sorted(_want_up - set(_got)):
                embed_drift.append(f'{_f}: インラインJSONに無い {sl}')
            for sl in sorted(set(_got) - _want_up):
                embed_drift.append(f'{_f}: インラインJSONに余分 {sl}')
        _href = re.findall(r'href="/?events/([a-z0-9\-]+)\.html"', _h)
        _hdupe = sorted({sl for sl in _href if _href.count(sl) > 1})
        if _hdupe:
            embed_drift.append(f'{_f}: SSR一覧に重複 {_hdupe[:3]}')
        for sl in sorted(_want_up - set(_href)):
            embed_drift.append(f'{_f}: SSR一覧に無い {sl}')
        for sl in sorted(set(_href) - _want_up):
            embed_drift.append(f'{_f}: SSR一覧に余分 {sl}')
    add('embedded_event_set_drift',
        'カレンダー・マップの埋め込み集合がevents.jsonと不一致',
        embed_drift,
        'scripts/build-static-html.py を再実行する。'
        '重複が出ているときは挿入前の除去が効いていない（足すだけになっている）')

    # --- 見送り記録の語彙 -----------------------------------------------------
    # rejected-events.json は自分の中に _reasonTypes という語彙表を持っているが、
    # 2026-08-27 まで repo 全体で reasonType を読む行が1本も無かった。
    # blockedUrlDomains と同じで、書いてあるだけの規則は規則ではない。
    # 綴り違いや未定義の値を書いても誰も止めないので、
    # 「policy と unverified の件数」のような集計が黙ってずれる。
    rej_vocab = []
    _known = set((rej.get('_reasonTypes') or {}).keys())
    for _it in (rej.get('items') or []):
        _k = _it.get('key') or '(keyなし)'
        _rt = _it.get('reasonType')
        if not _rt:
            rej_vocab.append(f'{_k}: reasonType が無い')
        elif _known and _rt not in _known:
            rej_vocab.append(f'{_k}: reasonType={_rt} は _reasonTypes に無い値')
        if not (_it.get('reason') or '').strip():
            rej_vocab.append(f'{_k}: reason（見送りの理由）が空')
        _dc = str(_it.get('decided') or '')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', _dc):
            rej_vocab.append(f'{_k}: decided の書式が不正 → {_dc!r}')
        elif _dc > today_s:
            rej_vocab.append(f'{_k}: decided が未来日 → {_dc}')
    add('rejected_reason_vocab', '見送り記録の reasonType が語彙表にない値',
        sorted(rej_vocab),
        'rejected-events.json の _reasonTypes にある値だけを使う。'
        '新しい類型なら、先に _reasonTypes と listing-policy.json に定義を足す')

    # --- 再評価待ちの見送りの期限 ---------------------------------------------
    # reasonType=unverified で revisit=true の回は「一次情報が出たら再評価する」
    # という約束で保留している。植物軸は認めた上で出典が足りないだけなので、
    # 掲載相当になる可能性が高い。ところが再評価を促す側が repo に無く、
    # reasonType 自体を読む行も1本も無かった(2026-08-27)。
    # 開催日を過ぎた保留は、再評価の機会そのものが消えている。
    # 実際 gujo-de-cactus-night-market-2026-08(2026-08-16開催)は
    # 08-12 に保留したまま開催日を11日過ぎており、誰も見に行かなかった。
    # 「後で見る」と書いた時点で、それを期限付きで表に出す側を作らないと二度と見ない。
    rej_expired, rej_stale = [], []
    for _it in (rej.get('items') or []):
        if not _it.get('revisit'):
            continue
        _ed = str(_it.get('eventDate') or '')
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', _ed) and _ed < today_s:
            rej_expired.append(
                f"{_it.get('key')}: 開催日 {_ed} を過ぎた（保留 {_it.get('decided')}）")
            continue
        # 日付未確定が保留理由そのものの回は期限を持てない。放置されないよう年齢で見る。
        _last = max(str(_it.get('revisitedOn') or ''), str(_it.get('decided') or ''))
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', _last):
            continue        # 書式は rejected_reason_vocab 側で鳴る
        try:
            _age = (_dtm.date.fromisoformat(today_s)
                    - _dtm.date.fromisoformat(_last)).days
        except ValueError:
            continue
        if _age >= 30:
            rej_stale.append(f"{_it.get('key')}: 最終評価 {_last}（{_age}日前）")
    add('rejected_revisit_expired', '再評価待ちの見送りが開催日を過ぎている',
        sorted(rej_expired),
        '開催日を過ぎた回はもう掲載できない。revisit を外して'
        'reasonType を確定させる（一次情報が出ないまま終わったなら unverified のまま revisit=false）。'
        '同じシリーズの次回が告知されていれば新規エントリとして扱う')
    add('rejected_revisit_stale', '再評価待ちの見送りが30日以上動いていない',
        sorted(rej_stale),
        '一次情報を探し直して、掲載するか revisit を外すかを決める。'
        '今回も判断できなければ revisitedOn に実行日を書いて窓を開き直す'
        '（見たことの記録が無いと、見ていないのと区別が付かない）。'
        '日付が未確定の回はここでしか表に出ない（eventDate が無く期限を持てないため）',
        severity='info')

    # 説明文の上書き保護が、新規登録の回で外れていないか。
    # 保護の目印は updatedAt だが、登録時に入れ忘れるのが常態で、
    # 2026-08-28 に「直近14日に足した30件すべてが無防備」という状態で見つかった
    # (週次エンリッチの2日前だった)。書き込み側は sitelib.desc_is_protected が
    # addedDate でも守るようにしたので実害は無いが、updatedAt が無いままだと
    # 「最後に本文を書いた日」がどこにも残らず、保護の根拠が addedDate 頼みになる。
    _unmarked = []
    for e in events:
        _ad = str(e.get('addedDate') or '')[:10]
        if len(_ad) < 10 or (e.get('updatedAt') or '').strip():
            continue
        try:
            _age = (_dtm.date.fromisoformat(today_s)
                    - _dtm.date.fromisoformat(_ad)).days
        except ValueError:
            continue
        if 0 <= _age <= DESC_PROTECT_DAYS and \
                len((e.get('description') or '').strip()) >= DESC_MIN_CHARS:
            _unmarked.append(f"{e['slug']}: addedDate {_ad} / updatedAt なし")
    add('updated_at_missing_on_new', '直近に足した回に updatedAt が無い',
        sorted(_unmarked),
        '本文を書いた日を updatedAt に入れる（登録時なら addedDate と同じ値でよい）。'
        '週次エンリッチの上書き保護は sitelib.desc_is_protected が addedDate でも効かせるので'
        '本文が消える心配は無いが、以後この回を直したとき「最終更新」が動かない',
        severity='info')

    # 配布物のタイムスタンプが、同じビルドの中で食い違っていないか。
    # 2026-08-28、generate-ical.py が JST の時刻に 'Z'(=UTC)を付けており、
    # 3本の .ics すべてが DTSTAMP を9時間先に名乗っていた(RFC 5545 は UTC 必須)。
    # 購読側は DTSTAMP で版の新旧を判断するので、先の時刻を名乗ると
    # 後から出した訂正が古い版として無視されうる。
    # 「今と比べて未来か」で見ると、ビルドから9時間経てば通ってしまい検査が効かない。
    # 同じビルドが書いた2つの時刻を突き合わせれば、時計に依存せず判定できる。
    _stamps = []
    _m = re.search(r'<lastBuildDate>([^<]+)</lastBuildDate>', _slurp(rp('rss.xml')))
    if _m:
        try:
            from email.utils import parsedate_to_datetime as _p2d
            _stamps.append(('rss.xml lastBuildDate',
                            _p2d(_m.group(1)).astimezone(_dtm.timezone.utc)))
        except (TypeError, ValueError):
            pass
    for _f in sorted(glob.glob(rp('*.ics'))):
        _mm = re.search(r'^DTSTAMP:(\d{8}T\d{6}Z)', _slurp(_f), re.M)
        if not _mm:
            continue
        try:
            _stamps.append((os.path.basename(_f) + ' DTSTAMP',
                            _dtm.datetime.strptime(_mm.group(1), '%Y%m%dT%H%M%SZ')
                            .replace(tzinfo=_dtm.timezone.utc)))
        except ValueError:
            pass
    _tz_drift = []
    if len(_stamps) >= 2:
        _base_name, _base_dt = min(_stamps, key=lambda x: x[1])
        for _n, _d in _stamps:
            _gap = abs((_d - _base_dt).total_seconds())
            if _gap >= 1800:        # 30分。ビルド内の生成順の差では開かない
                _tz_drift.append(
                    f'{_n} が {_base_name} と {_gap / 3600:.1f}時間ずれている'
                    f'（{_d.isoformat()} vs {_base_dt.isoformat()}）')
    add('build_timestamp_tz_drift', '配布物のタイムスタンプが同じビルド内で食い違う',
        sorted(_tz_drift),
        'どちらかがタイムゾーンを取り違えている。'
        '.ics の DTSTAMP と RSS の lastBuildDate は同じビルドが書くので本来一致する。'
        'DTSTAMP は必ず UTC(datetime.now(timezone.utc))で作る')

    # 「今日」をランナーのタイムゾーンで決めていないか。
    # GitHub Actions は UTC で走るので、06:00 JST 起動の daily は
    # ランナー日付が前日になる。auto-status-jst.py はこの理由で作られたのに、
    # 同じ書き方が他に5か所残っていた(2026-08-28)。実害も出ていた:
    #   - audit.py が履歴のキーを UTC 日付で書き、前日の実行記録を毎朝上書きしていた
    #   - coverage-sweep.py の sweptOn が常に1日古く、巡回の鮮度検査が1日ぶん鈍っていた
    # 日付は sitelib.today_jst() が単一情報源。
    # 経過時間の計測やログ出力の now() は対象外(日付として比較・保存しないため)。
    # 文字列や docstring に書かれた説明を拾わないよう、本文の正規表現ではなく
    # AST で「実際の呼び出し」だけを見る(この検査自身の note を拾って誤検知した)。
    import ast as _ast
    _naive_date = []
    for _f in sorted(glob.glob(rp('scripts', '*.py')) + [rp('build-detail-pages.py')]):
        _rel = os.path.relpath(_f, REPO)
        try:
            _tree = _ast.parse(_slurp(_f))
        except SyntaxError:
            continue
        for _n in _ast.walk(_tree):
            if not isinstance(_n, _ast.Call) or not isinstance(_n.func, _ast.Attribute):
                continue
            # date.today() / datetime.today()
            if _n.func.attr == 'today' and not _n.args and not _n.keywords:
                _naive_date.append(f'{_rel}:{_n.lineno}: .today()')
            # datetime.now() を引数なしで呼び、その場で日付にしている
            elif (_n.func.attr in ('date', 'isoformat')
                  and isinstance(_n.func.value, _ast.Call)
                  and isinstance(_n.func.value.func, _ast.Attribute)
                  and _n.func.value.func.attr == 'now'
                  and not _n.func.value.args and not _n.func.value.keywords):
                _naive_date.append(f'{_rel}:{_n.lineno}: datetime.now().{_n.func.attr}()')
    add('naive_local_date', '「今日」をランナーのタイムゾーンで決めている',
        sorted(_naive_date),
        'date.today() はランナーの日付。GitHub Actions は UTC なので'
        'JST の午前0〜9時は前日になる。sitelib.today_jst() を使う')

    # --- sitemap の loc と頁の canonical ---------------------------------------
    # sitemap_dead_entries は「ファイルが在るか」、sitemap_noindex_listed は
    # 「noindex を載せていないか」しか見ておらず、
    # **載せたURLがその頁の正規URLと同じ形か**は誰も見ていなかった。
    # 2026-08-30 に発覚: generate_sitemap.py が末尾スラッシュ形に直す
    # ディレクトリの列挙から 'guides' だけが抜けていて、
    # `/guides/index.html` を載せていた。頁側の canonical は `/guides/` なので、
    # sitemap が自分で「正規ではないURL」を申告している状態だった。
    # 収集する側の列挙(9個)と直す側の列挙(8個)を別々に書いたことが原因。
    # canonical を他URLへ寄せた頁を sitemap から外す規則(region/hokkaido)も
    # 同じ向きの規則なので、両方をこの1本で見る。
    _canon_re = re.compile(r'<link rel="canonical" href="([^"]+)"')
    sm_canon = []
    for u in sm_urls:
        path = re.sub(r'^https?://[^/]+/?', '', u)
        local = rp(path if path.endswith('.html') else os.path.join(path, 'index.html'))
        if not os.path.exists(local):
            continue        # sitemap_dead_entries 側で鳴る
        try:
            with open(local, encoding='utf-8', errors='replace') as f:
                _b = f.read()
        except OSError:
            continue
        _m = _canon_re.search(_b)
        if not _m:
            sm_canon.append(f'{u}: 頁に canonical が無い')
        elif _m.group(1).rstrip('/') != u.rstrip('/'):
            sm_canon.append(f'{u} ← 頁の canonical は {_m.group(1)}')
    add('sitemap_canonical_mismatch', 'sitemapのURLが頁のcanonicalと違う形',
        sorted(sm_canon),
        'sitemap は正規URLだけを載せる。末尾スラッシュの有無も別URL扱いになる。'
        'canonical を他URLへ寄せた頁は landing-meta.json の canonicalized 経由で外す')

    # --- sitemap の lastmod が内容を追えているか -------------------------------
    # 2026-08-30 まで lastmod は os.path.getmtime だった。CI は毎回まっさらに
    # clone するので全ファイルの mtime がチェックアウト時刻になり、
    # **313件すべてが毎日「今日更新」を名乗っていた**(08-28/08-29/08-30 の
    # どの版も lastmod は全件同一日)。3月から変わっていない利用規約まで
    # 毎日更新と申告していたので、Google から見て信号として死んでいた。
    # 内容のsha1を台帳(scripts/sitemap-lastmod.json)に持ち、変わった日だけ繰り上げる。
    # 台帳をコミットし忘れる/生成の順序が崩れると静かに元へ戻るので、
    # sitemap の lastmod・台帳・実ファイルの3つが揃っていることを毎回見る。
    _lm_man = (load_json(rp('scripts', 'sitemap-lastmod.json'), {}) or {}).get('pages') or {}
    _sm_lm = dict(re.findall(
        r'<loc>\s*([^<\s]+)\s*</loc>\s*<lastmod>\s*([^<\s]+)\s*</lastmod>', sm))
    lm_bad = []
    if not _lm_man:
        lm_bad.append('scripts/sitemap-lastmod.json が無い'
                      '（mtime 基準に戻ると全URLが毎日「今日更新」になる）')
    else:
        for u in sm_urls:
            _e = _lm_man.get(u)
            if not _e:
                lm_bad.append(f'{u}: 台帳に記録が無い')
                continue
            if _sm_lm.get(u) != _e.get('date'):
                lm_bad.append(f'{u}: sitemapのlastmod {_sm_lm.get(u)} が'
                              f'台帳の {_e.get("date")} と違う')
                continue
            _path = re.sub(r'^https?://[^/]+/?', '', u)
            _local = rp(_path if _path.endswith('.html')
                        else os.path.join(_path, 'index.html'))
            if not os.path.exists(_local):
                continue        # sitemap_dead_entries 側で鳴る
            try:
                with open(_local, 'rb') as f:
                    _sha = hashlib.sha1(f.read()).hexdigest()
            except OSError:
                continue
            if _sha != _e.get('sha'):
                lm_bad.append(f'{u}: 台帳のsha が実ファイルと違う'
                              '（sitemap を作り直していない）')
        for u in sorted(set(_lm_man) - set(sm_urls)):
            lm_bad.append(f'{u}: sitemap に無いURLが台帳に残っている')
    add('sitemap_lastmod_untracked', 'sitemapのlastmodが内容の変更を追えていない',
        sorted(lm_bad)[:40],
        'lastmod は「中身が最後に変わった日」。mtime は CI の clone で毎回変わるので'
        '使えない。scripts/sitemap-lastmod.json を生成物と一緒にコミットする')

    # --- meta description の欠落 -----------------------------------------------
    # duplicate_indexable_title は「同じ title が2つある」ことは見るが、
    # 「description that が無い」ことは誰も見ていなかった。
    # 無いと Google が本文から勝手にスニペットを作るので、
    # 規約・お問い合わせのような定型頁では見出しの羅列が出る。
    # 2026-08-30 時点で terms / contact / privacy / disclaimer / operator の
    # 5頁に無かった(どれも sitemap 掲載・index 対象)。
    # 生成物の頁はテンプレートが必ず入れるので、ここに出るのは手書きの静的頁だけ。
    _desc_re = re.compile(r'<meta[^>]+name="description"[^>]+content="([^"]*)"')
    no_desc = []
    for rel in _pages:
        if rel in _noindex_pages or rel in _EXEMPT_ORPHAN:
            continue
        if re.fullmatch(r'google[0-9a-f]+\.html', rel):
            continue
        try:
            with open(rp(rel), encoding='utf-8', errors='replace') as f:
                _b = f.read()
        except OSError:
            continue
        _m = _desc_re.search(_b)
        if not _m:
            no_desc.append(f'{rel}: description が無い')
        elif not _m.group(1).strip():
            no_desc.append(f'{rel}: description が空')
    add('meta_description_missing', 'index対象の頁に meta description が無い',
        sorted(no_desc),
        '<meta name="viewport"> の直後に1文入れる。'
        '本文の要約であって、キーワードの羅列にしない', severity='info')

    # --- .ics の行長 -----------------------------------------------------------
    # RFC 5545 §3.1 は1行75オクテット以下を求める。generate-ical.py の fold() は
    # 継続行の先頭に付くスペースを数えておらず、2026-08-30 時点で
    # events.ics の816行が76オクテットだった。ヘッダ行(PRODID / X-WR-CALNAME /
    # X-WR-CALDESC)はそもそも fold を通っていなかった。
    # 折りたたみは購読側が必ず解くので、**中身が壊れていないことは検査にならない**。
    # 行の長さそのものを見る。CRLF が LF に落ちている場合もここで出る
    # (テキストモードで書き戻すと起きる。購読側は行を切れなくなる)。
    ics_bad = []
    for _f in ('events.ics', 'this-month.ics', 'upcoming.ics'):
        _p = rp(_f)
        if not os.path.exists(_p):
            continue
        try:
            with open(_p, encoding='utf-8', errors='replace', newline='') as f:
                _raw = f.read()
        except OSError:
            continue
        _lines = _raw.split('\r\n')
        if len(_lines) < 2:
            ics_bad.append(f'{_f}: CRLF が無い(LF だけで書かれている)')
            continue
        _over = [l for l in _lines if len(l.encode('utf-8')) > 75]
        if _over:
            ics_bad.append(f'{_f}: 75オクテット超の行が{len(_over)}行'
                           f'（例 {len(_over[0].encode("utf-8"))}オクテット: {_over[0][:30]}）')
        _lone = [l for l in _lines if '\n' in l or '\r' in l]
        if _lone:
            ics_bad.append(f'{_f}: 行の途中に生の改行が{len(_lone)}箇所')
    add('ics_line_too_long', '.icsがRFC5545の行長・改行の規定から外れている',
        ics_bad,
        'scripts/generate-ical.py の fold()。継続行は先頭のスペースも75に数える。'
        'ヘッダ行も fold を通す', severity='info')

    # --- policy に書いた機械可読な値を、誰も読んでいない -------------------------
    # listing-policy.json の blockedUrlDomains は2026-08-24まで参照する行が
    # repo に1本も無く、rejected-events.json の _reasonTypes も2026-08-27まで
    # 同じ状態だった。どちらも「データに規則を書いた」だけで終わっており、
    # 守っていたのは人の記憶だけだった。同じことが起きていないかを毎回見る。
    # 散文(日本語の説明・先例)は人が読むためのものなので対象外。
    # 対象は **機械が使える形の値**、つまり真偽値・数値・ASCIIの短い語の配列だけ。
    # 2026-08-30 時点では doNotEscalate(7節に真偽値)が未参照だった。
    def _machine_usable(v):
        if isinstance(v, bool) or isinstance(v, (int, float)):
            return True
        if isinstance(v, list) and v:
            return all(isinstance(x, str) and x.isascii() and len(x) < 40
                       and ' ' not in x for x in v)
        return False

    _policy_keys = {}

    def _walk_policy(o, path=''):
        if not isinstance(o, dict):
            return
        for k, v in o.items():
            if k.startswith('_'):
                continue
            if _machine_usable(v):
                _policy_keys.setdefault(k, []).append(f'{path}{k}')
            _walk_policy(v, f'{path}{k}.')

    _walk_policy(_policy)
    # 素の部分文字列で探すと、この検査自身の note や注釈が引っかかって
    # 「読んでいる」ことになってしまう(naive_local_date で一度やった失敗)。
    # 辞書から取り出す書き方は必ずクォート付きの完全一致なので、そこだけを見る。
    # コメント行は落とす。
    _srcs = (sorted(glob.glob(rp('scripts', '*.py')))
             + sorted(glob.glob(rp('*.js'))) + [rp('build-detail-pages.py')])
    _src_blob = ''
    for _sp in _srcs:
        try:
            with open(_sp, encoding='utf-8', errors='replace') as f:
                for _ln in f:
                    _src_blob += _ln.split('#')[0] + '\n'
        except OSError:
            pass
    policy_unread = [
        f'{k}（{", ".join(v)}）' for k, v in sorted(_policy_keys.items())
        if not re.search(r'[\'"]' + re.escape(k) + r'[\'"]', _src_blob)]
    # --- 要人間判断キューが自分の規則を守っているか -----------------------------
    # pending-judgments.json は自分の description に3つの規則を書いている
    # (id は source:キー 形式 / 重複積み上げ禁止 / 解消時に自ら削除する)。
    # listing-policy.json の escalate.requirement は
    # 「積むときは policy への追記案をあわせて書く」を求め、
    # 7つの節が doNotEscalate=true で「この類型は積まない」と決めている。
    # 2026-08-30 時点でこれらを読むコードは1本も無かった。
    # 規則を守らせる側が無いと、同じ問いが翌日also積まれる。
    _pj = load_json('pending-judgments.json', {}) or {}
    _pj_items = _pj.get('items') or []
    _no_escalate = {k for k, v in (_policy or {}).items()
                    if isinstance(v, dict) and v.get('doNotEscalate') is True}
    _seen_ids = set()
    pj_bad = []
    for _it in _pj_items:
        _id = (_it.get('id') or '').strip()
        if not _id:
            pj_bad.append(f'id が無い項目: {(_it.get("title") or "")[:40]}')
            continue
        if not re.fullmatch(r'[a-z0-9-]+:[a-z0-9-]+', _id):
            pj_bad.append(f'{_id}: id が source:キー 形式でない')
        if _id in _seen_ids:
            pj_bad.append(f'{_id}: 同じ id が重複して積まれている')
        _seen_ids.add(_id)
        if not (_it.get('proposal') or '').strip():
            pj_bad.append(f'{_id}: proposal が無い'
                          '（listing-policy.escalate.requirement）')
        _pol = (_it.get('policy') or '').strip()
        if _pol:
            if _pol not in (_policy or {}):
                pj_bad.append(f'{_id}: policy="{_pol}" は listing-policy.json に無い節')
            elif _pol in _no_escalate:
                pj_bad.append(f'{_id}: policy="{_pol}" は doNotEscalate=true'
                              '（積まずに既定の対処に回す類型）')
    # --- 公開されるファイルに個人情報が入っていないか ---------------------------
    # リポジトリは public で、GitHub Pages がその中身をそのまま配信する。
    # つまり new-inquiries.json は https://agave-navi.com/new-inquiries.json
    # として誰でも読めるうえ、コミットは公開履歴に永久に残る。
    # ところがこのファイルは設計上、フォーム送信者の氏名とメールアドレスを
    # 受け渡しの箱として通す(GASが書き、notify-inquiry.yml がそれを読んで
    # メール本文を組む)。2026-08-31 の 9bf760e8 で実際に1件が
    # 12:41〜17:04 のあいだ公開URLに出ており、履歴にはいまも残っている。
    # 受け渡しが通る瞬間を無音にしないための検査。
    # 平常時は items が空なので0。送信があった日だけ鳴り、
    # 消し込みが遅れているあいだ鳴り続ける。
    # 恒久対処(PIIをrepoに通さない)は pending-judgments.json に積んである。
    _PII_KEYS = ('name', 'email', 'tel', 'phone', 'address')
    # 自由記述の欄には本人が署名や連絡先を書き込むことがある。
    # キーの有無だけを見ていると、body に書かれた連絡先はそのまま公開される
    # (listing-policy.json inquiryPii.bodyCaveat)。
    # 規則は読むコードを書くまで規則にならないので、本文も走査する。
    _FREE_KEYS = ('body', 'detail', 'note', 'reason')
    _OWN_MAIL = ('yuji.mezaki@gmail.com', 'mezaki@sterfield.co.jp')
    _RE_MAIL = re.compile(r'[\w.+-]+@[\w-]+\.[A-Za-z]{2,}')
    _RE_TEL = re.compile(r'(?<!\d)0\d{1,4}[-(]\d{1,4}[-)]?\d{3,4}(?!\d)')

    def _free_text_pii(text):
        # 自由記述の中の連絡先。URLの中の @ は拾わない
        # (images/...@2x-....png のような偽陽性を避ける)
        found = []
        for tok in str(text or '').split():
            if '/' in tok:
                continue
            _m = _RE_MAIL.search(tok)
            if _m and _m.group(0).lower() not in _OWN_MAIL:
                found.append('メールアドレス')
                break
        if _RE_TEL.search(str(text or '')):
            found.append('電話番号らしき数字')
        return found

    pii_pub = []
    for _fn, _paths in (('new-inquiries.json', (('items',),)),
                        ('inquiries-processed.json', (('items',), ('outcomes',)))):
        _doc = load_json(_fn, {}) or {}
        for _key, in _paths:
            for _i, _it in enumerate(_doc.get(_key) or []):
                if not isinstance(_it, dict):
                    continue
                _has = [k for k in _PII_KEYS if str(_it.get(k) or '').strip()]
                if _has:
                    pii_pub.append(
                        f'{_fn} の {_key}[{_i}] に {"/".join(_has)} が入っている'
                        f'（timestamp={_it.get("timestamp") or "?"}）')
                _inbody = []
                for _fk in _FREE_KEYS:
                    for _w in _free_text_pii(_it.get(_fk)):
                        _inbody.append(f'{_fk} に{_w}')
                if _inbody:
                    pii_pub.append(
                        f'{_fn} の {_key}[{_i}] の自由記述に連絡先が入っている'
                        f'（{" / ".join(sorted(set(_inbody)))} / '
                        f'timestamp={_it.get("timestamp") or "?"}）')
    add('published_pii', '公開されるファイルに個人情報が入っている',
        sorted(pii_pub),
        'リポジトリは public で、同じ内容が https://agave-navi.com/ にも出る。'
        '規則は listing-policy.json の inquiryPii。'
        'GASは連絡先を書かなくなったので、キーで出るのは古いデータか手作業の混入。'
        '自由記述で出たら、その行を落としてから記録し直す。'
        '処理したら items を空にして push する。'
        '値そのものはここに書かない（監査結果も公開ファイル）')

    add('pending_judgment_policy', '要人間判断キューが掲載基準の規則に反している',
        sorted(set(pj_bad)),
        'id は source:キー 形式。proposal(policyへの追記案)を必ず書く。'
        'doNotEscalate=true の類型は積まない。'
        '該当する節があるなら item に policy: <節名> を書くと、この検査が効く')

    add('policy_machine_value_unread',
        'listing-policy.json の機械可読な値を読むコードが無い',
        policy_unread,
        'データに規則を書いただけでは規則にならない。読む側を同じコミットで足すか、'
        '機械可読な形をやめて散文にする', severity='info')

    # --- 出力 ---
    # 履歴は結果ファイルより先に読む。metric の急変検査が履歴を必要とし、
    # かつ findings に載せる必要があるため(2026-08-24: add() を書き出しの後に
    # 置いていて audit-results.json に載らなかった)。
    hist_path = rp('audit-history.json')
    try:
        with open(hist_path, encoding='utf-8') as f:
            hist = json.load(f)
    except (OSError, ValueError):
        hist = {'_note': '監査結果の推移。scripts/audit.py が追記する。'
                         '直近90件のみ保持。改善/悪化の判断に使う。', 'runs': []}
    # 履歴のキーは JST。ここだけ date.today() を使っていたため、
    # 06:00 JST 起動の daily(=前日 21:00 UTC)が『前日』のキーで書き、
    # 前日の実行記録を毎朝上書きして消していた
    # (2026-08-27 の記録が、翌朝の daily の値 367件 に置き換わっていた)。
    today_key = today_s
    _prev_runs = [r for r in (hist.get('runs') or []) if r.get('date') != today_key]

    # 0件のものも必ず入れる。0を除外すると「全部消えた」という
    # いちばん重い異常だけが比較対象から外れる(2026-08-24に検証して発覚)。
    _cur_metric = {k: v['count'] for k, v in findings.items()
                   if v.get('severity') == 'metric'}
    # metric の急変だけを拾う。
    # 値そのものは「対応不要」なので毎日メールに並べる意味が無い(2026-08-24に本文から外した)。
    # ただし急に動いたときは異常の唯一の手がかりになる。
    #   例: upcoming_no_image が 72→200 なら画像が一斉に消えている。
    #       thin_archived が急減したらイベントが消えている。
    # 直近7回の中央値と比べ、相対30%以上かつ絶対10件以上動いたときだけ鳴らす。
    # 片方だけの条件だと、小さい値の±1や大きい値の自然増で毎日鳴る。
    _hist = [r for r in _prev_runs if r.get('metric')][-7:]

    # 掲載件数に比例して動く指標は、母数の変化を割り引いてから比べる。
    # 2026-08-27 に取りこぼし52件をまとめて掲載したとき、
    # upcoming_no_image が 72→103 に増えて urgent が鳴った。増えて当然の増え方で、
    # しかも中央値が追いつくまで4日鳴り続ける。意図した掲載で毎回4日鳴る検査は、
    # そのうち中身を見ずに閉じられる。
    _METRIC_SCALES_WITH_EVENTS = {
        'thin_past_with_source', 'thin_archived',
    }
    # 開催予定だけを数える指標の母数は「開催予定の件数」であって全件ではない。
    # 全件は past を貯め込むので単調に増えるが、開催予定は暦で毎日減る。
    # 全件で割り引くと、掲載が増えた回の換算が実際より小さく出て、
    # 2026-08-27 に潰したはずの誤検知が残る(50件をまとめて載せると
    # 全件は+13%なのに開催予定は+38%で、換算が追いつかず鳴る)。
    # 母数は 2026-09-01 から履歴に upcoming として残す。
    # 持っていない古い回が混ざる間は全件で換算する(移行前の挙動)。
    # 欠けた回だけを全件で埋めると2つの母数が中央値の中で混ざるので、
    # 全部が upcoming を持つときだけ upcoming を使う。
    _METRIC_SCALES_WITH_UPCOMING = {
        'upcoming_with_image', 'upcoming_no_image', 'ongoing_events',
    }
    # その指標が「異常を示す向き」。反対向きの動きは、
    # その指標を足した理由からして異常の証拠にならない。
    _METRIC_ALARM_DIR = {'upcoming_no_image': +1, 'events_with_image': -1}

    # 暦だけで動く指標は、ここでは判定できない。
    # upcoming_with_image は「増えたら正常・減ったら消失」という前提で
    # 2026-08-24 に -1 を与えていたが、開催予定という母集団そのものが
    # 毎日縮むので、画像が1枚も失われなくても減り続ける(2026-09-01に判明)。
    # 統計で当てるのをやめ、消失は event_image_lost が全件の実数で見る。
    _METRIC_NO_ALARM = {'upcoming_with_image'}

    _ev_now = len(events)
    _up_now = sum(1 for e in events if is_upcoming(e))
    metric_moves = []
    for _k, _v in _cur_metric.items():
        # そのキーを実際に持っている履歴だけで基準を作る。
        # 欠けている履歴を0とみなすと、検査を追加した初日に必ず誤検知する
        # (2026-08-24: upcoming_with_image を足した日に「0→13」で鳴った)。
        if _k in _METRIC_NO_ALARM:
            continue        # 暦で動くので急変を異常と読めない
        _rows = [r for r in _hist if _k in r.get('metric', {})]
        if len(_rows) < 3:
            continue        # 基準を作れるだけの履歴がまだ無い
        _series = sorted(r['metric'][_k] for r in _rows)
        _base = _series[len(_series) // 2]
        _scaled = _base
        _denom = None
        if _k in _METRIC_SCALES_WITH_EVENTS:
            _denom = ('events', _ev_now)
        elif _k in _METRIC_SCALES_WITH_UPCOMING:
            _denom = (('upcoming', _up_now)
                      if all(isinstance(r.get('upcoming'), int) for r in _rows)
                      else ('events', _ev_now))
        if _denom:
            # 中央値を取った回と同じ並びで母数の中央値も取る。
            _field, _now_denom = _denom
            _ds = sorted(r.get(_field) or 0 for r in _rows)
            _d_base = _ds[len(_ds) // 2]
            if _d_base > 0 and _now_denom > 0:
                _scaled = _base * _now_denom / _d_base
        _delta = _v - _scaled
        _dir = _METRIC_ALARM_DIR.get(_k, 0)
        if _dir and (_delta > 0) != (_dir > 0):
            continue        # 異常を示さない向きの動き
        _note = '' if _scaled == _base else f'（掲載{_ev_now}件で換算 {_scaled:.0f}）'
        if _scaled > 0 and abs(_delta) >= 10 and abs(_delta) / _scaled >= 0.30:
            metric_moves.append(
                f'{_k}: 直近中央値 {_base} → {_v}{_note}（{_delta:+.0f}）')
        elif _scaled == 0 and _v >= 10:
            metric_moves.append(f'{_k}: ずっと0だったものが {_v} に増えた')
    # イベントが黙って消えていないか。
    # events.json が正なので、消えれば詳細ページも sitemap もカードも
    # 一緒に消え、整合検査は全部通る。「全部揃って無くなる」は
    # どの検査にも引っかからない唯一の壊れ方で、2026-08-28 まで見る側が無かった。
    # 削除は方針(contradictoryData)に沿った意図的なもので、履歴19回で最大1件。
    # 3件以上まとめて減ったら、意図した削除かどうかを人が見る。
    _shrunk = []
    _prev_ev = next((r.get('events') for r in reversed(_prev_runs)
                     if isinstance(r.get('events'), int)), None)
    if _prev_ev and _prev_ev - len(events) >= 3:
        _shrunk.append(f'掲載イベントが {_prev_ev} → {len(events)} 件に減った'
                       f'（{len(events) - _prev_ev:+d}）')
    # imageUrl の消失を実数で見る。
    # metric_moved は「相対30%以上かつ絶対10件以上」でしか鳴らないので、
    # 母数が小さいと全滅しても届かない(2026-09-01 の upcoming_with_image は30。
    # 10月には4まで落ちるので、その頃には全部消えても絶対10件に届かない)。
    # events_with_image は暦では動かないから、前回との差をそのまま読める。
    # イベントごと消えたぶんだけは差し引く(それは event_set_shrunk の担当)。
    _img_lost = []
    _prev_img_row = next((r for r in reversed(_prev_runs)
                          if isinstance((r.get('metric') or {}).get(
                              'events_with_image'), int)), None)
    if _prev_img_row:
        _prev_img = _prev_img_row['metric']['events_with_image']
        _now_img = _cur_metric.get('events_with_image', 0)
        _removed = max(0, (_prev_img_row.get('events') or 0) - len(events))
        _drop = _prev_img - _now_img - _removed
        if _drop > 0:
            _img_lost.append(
                f"imageUrl のある回が {_prev_img} → {_now_img} 件"
                f"（{_prev_img_row.get('date')} 比、イベント削除ぶん{_removed}件を"
                f"差し引いて {_drop}件が消失）")
    add('event_image_lost', 'imageUrlが消えている', _img_lost,
        'サイトロゴ等を意図して消した回はこれで正しい(1日だけ鳴る)。'
        '心当たりが無ければ git diff HEAD~1 -- events.json で imageUrl を見る。'
        'カード・og:image・twitter:image・JSON-LD・sitemap の5箇所が同時に落ちる')

    add('event_set_shrunk', 'イベントがまとめて消えている', _shrunk,
        '意図した削除なら対処不要。心当たりが無ければ events.json の直前の版と'
        '差分を取る（git diff HEAD~1 -- events.json）。'
        '生成物は events.json から作り直されるので、消えたことは他の検査に出ない')

    add('metric_moved', '参考値が急に動いた(異常の可能性)', sorted(metric_moves),
        '値そのものは対応不要だが、この動き方は異常の手がかりになる。'
        '該当項目の items を見て、想定できる増減かを確かめる', severity='urgent')


    total = sum(v['count'] for k, v in findings.items()
                if k not in ('workflow_secrets',))
    with open(rp('audit-results.json'), 'w', encoding='utf-8') as f:
        json.dump({'total': total, 'findings': findings}, f, ensure_ascii=False, indent=2)
        f.write('\n')

    # 推移を残す。1回の値だけでは改善か悪化かが判断できない。
    entry = {'date': today_key,
             'urgent': {k: v['count'] for k, v in findings.items()
                        if v.get('severity', 'urgent') == 'urgent' and v['count']},
             'info': {k: v['count'] for k, v in findings.items()
                      if v.get('severity') == 'info' and v['count']},
             'metric': {k: v['count'] for k, v in findings.items()
                        if v.get('severity') == 'metric'},
             'events': len(events),
             'upcoming': _up_now}
    runs = list(_prev_runs)
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
