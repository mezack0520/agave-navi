#!/usr/bin/env python3
"""
sync-index-cards.py — index.html のカードのサムネイル <img> を
events.json の imageUrl と同期させる。

events.json で imageUrl を持つイベントのカードは <img> 入り、
持たないイベントは event-no-image の見た目に統一する。

冪等。既に正しい状態なら何も書き換えない。

Usage:
  python3 scripts/sync-index-cards.py
  python3 scripts/sync-index-cards.py --dry-run
"""

import argparse
import json
import os
import re
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(SCRIPT_DIR, '..'))
sys.path.insert(0, SCRIPT_DIR)
from sitelib import (today_jst, is_recent_past, event_span,
                     PAST_KEEP_DAYS, PAST_KEEP_MAX, PAST_KEEP_LABEL,
                     LONG_RUN_DAYS, no_image_thumb, compact_date, html_escape,
                     list_sort_key, is_cancelled, cancel_label,
                     updates_section_html, load_updates,
                     updates_scopes, area_filter_html, region_map_js,
                     time_consts_js)
EVENTS_JSON = os.path.join(ROOT, 'events.json')
INDEX_HTML = os.path.join(ROOT, 'index.html')


def html_attr_escape(s):
    return (s or '').replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def img_html(image_url, alt, eager=False):
    # 先頭カード(LCP候補)はeager+fetchpriority、それ以外はlazyで初期ロードを軽くする
    perf = 'decoding="async" fetchpriority="high"' if eager else 'loading="lazy" decoding="async"'
    return (f'<div class="event-thumb"><img src="{html_attr_escape(image_url)}" '
            f'alt="{html_attr_escape(alt)}" width="640" height="640" {perf} referrerpolicy="no-referrer" '
            f"onerror=\"this.parentElement.classList.add('event-no-image');this.remove();\""
            f'></div>')


def no_img_html(ev):
    """画像なし枠。生成は sitelib が単一情報源"""
    return no_image_thumb(ev or {})

# Match the FIRST event-thumb element inside a card (with or without img),
# the card being identified by data-slug="...".
# We'll handle this by finding the card section then replacing within it.

CARD_HEADER_RE = re.compile(
    r'<div class="event-card[^"]*"[^>]*data-slug="(?P<slug>[^"]+)"[^>]*>',
    re.IGNORECASE
)
# 中身の形に依存させない。以前は <img></div> と空の </div> だけを想定していたため、
# 画像なし枠に県名+日付の <span> を入れた瞬間に一致しなくなり、
# 置換されずカードが増殖した(2026-08-24: 101→908カード)。
# thumb の中に <div> は入らないので、最初の </div> まで貪欲でなく取れば安全。
THUMB_RE = re.compile(
    r'<div class="event-thumb(?:\s+event-no-image)?"\s*>'
    r'(?:(?!<div\b).)*?</div>',
    re.IGNORECASE | re.DOTALL
)



def find_card_span(html, start_idx):
    """<div class="event-card" ...> の開始位置から、div入れ子を数えて閉じ位置を返す。"""
    import re as _re
    depth = 0
    i = start_idx
    tag_re = _re.compile(r'<(/?)div\b[^>]*>', _re.I)
    for m in tag_re.finditer(html, start_idx):
        if m.group(1):
            depth -= 1
            if depth == 0:
                return start_idx, m.end()
        else:
            depth += 1
    return start_idx, len(html)


def remove_stale_cards(html, valid_slugs):
    """events.json に存在しないイベントのカードをindex.htmlから除去する(削除イベントの残留防止)。"""
    import re as _re
    removed = []
    while True:
        stale = None
        for m in _re.finditer(r'<div class="event-card[^"]*"[^>]*data-slug="([^"]+)"', html):
            if m.group(1) not in valid_slugs:
                stale = m
                break
        if not stale:
            break
        s, e = find_card_span(html, stale.start())
        # 直後の空白行も片付ける
        while e < len(html) and html[e] in '\n\r\t ':
            e += 1
        html = html[:s] + html[e:]
        removed.append(stale.group(1))
    return html, removed

# カードの data-* を events.json に合わせる。
# これまでサムネイルしか同期しておらず、日付や status を直しても
# カードの属性は古いまま残っていた。属性は status-auto.js が
# 「開催中/これから/終了」の判定に使うので、古いと表示から消える。
# 2026-08-27に発覚: 木更津園芸市は 8/11→8/29 に直っていたのに
# カードが data-date="2026-08-11" data-status="past" のままで、
# 9日間「終了したイベント」に隠れていた。同種の食い違いが22件あった。
_SYNC_ATTRS = ('date', 'date-end', 'status', 'prefecture', 'region',
               'tags', 'added-date')


def _expected_attrs(ev):
    return {
        'date': ev.get('date') or '',
        'date-end': ev.get('dateEnd') or ev.get('date') or '',
        'status': ev.get('status') or '',
        'prefecture': ev.get('prefecture') or '',
        'region': ev.get('region') or '',
        'tags': ','.join(ev.get('tags') or []),
        'added-date': ev.get('addedDate') or '',
    }


def sync_card_body(chunk, ev):
    """カード本文（日付・タイトル・説明文・県名）を events.json に揃える。

    属性だけ直しても、来場者が読むのは本文のほう。
    2026-08-27時点で26件が古いままだった。内訳は説明文22・日付5・タイトル1で、
    「第8回 花友フェスタ 2026」のように前回開催の名前が残っている回もあった。
    サムネイルの枠には events.json の日付を出しているので、
    同じカードの中で日付が食い違う状態になっていた。
    """
    if not ev:
        return chunk, []
    changed = []

    def _sub(pattern, want, label, escape=True):
        nonlocal chunk, changed
        m = re.search(pattern, chunk, re.S)
        if not m:
            return
        got = m.group(1)
        if got.strip() == (want or '').strip():
            return
        changed.append(label)
        val = html_escape(want or '') if escape else (want or '')
        chunk = chunk[:m.start(1)] + val + chunk[m.end(1):]

    _sub(r'<span class="event-date">([^<]*)</span>', compact_date(ev), 'date')

    # 中止バッジ。events.json 側で eventStatus を変えたら、
    # トップのカードにも出す/消すの両方が起きる
    want_badge = (f'<span class="event-cancel-badge">{html_escape(cancel_label(ev))}</span>'
                  if is_cancelled(ev) else '')
    has_badge = re.search(r'<span class="event-cancel-badge">[^<]*</span>', chunk)
    if want_badge and not has_badge:
        chunk = chunk.replace('<span class="event-status">',
                              want_badge + '<span class="event-status">', 1)
        changed.append('中止バッジを付けた')
    elif has_badge and not want_badge:
        chunk = re.sub(r'<span class="event-cancel-badge">[^<]*</span>', '', chunk, count=1)
        changed.append('中止バッジを外した')
    if is_cancelled(ev) and 'event-cancelled' not in chunk:
        chunk = chunk.replace('class="event-card', 'class="event-card event-cancelled', 1)
        changed.append('中止クラスを付けた')
    elif not is_cancelled(ev) and 'event-cancelled' in chunk:
        chunk = chunk.replace(' event-cancelled', '', 1)
        changed.append('中止クラスを外した')
    _sub(r'<h\d class="event-title">([^<]*)</h\d>', ev.get('name') or '', 'title')
    _sub(r'<p class="event-description">(.*?)</p>', ev.get('description') or '', 'desc')
    _sub(r'<span class="event-region">([^<]*)</span>',
         ev.get('prefecture') or ev.get('region') or '', 'region')
    return chunk, changed


def sync_card_attrs(tag, ev):
    """カードの開始タグの data-* を events.json の値に揃える。

    既にある属性は書き換え、無い属性で値があるものは足す。
    タグの他の部分(class や onclick)には触らない。
    """
    if not ev:
        return tag, []
    changed = []
    want = _expected_attrs(ev)
    for name in _SYNC_ATTRS:
        val = want[name]
        pat = re.compile(r'(data-%s=")([^"]*)(")' % re.escape(name))
        mm = pat.search(tag)
        if mm:
            if mm.group(2) != val:
                changed.append(f'{name}: {mm.group(2)!r}->{val!r}')
                tag = tag[:mm.start(2)] + html_attr_escape(val) + tag[mm.end(2):]
        elif val:
            changed.append(f'{name}: (無し)->{val!r}')
            tag = tag[:-1] + ' data-%s="%s">' % (name, html_attr_escape(val))
    return tag, changed


def new_card_html(ev):
    """新規イベントのカードを1枚組む。

    サムネイルと属性は、この直後に走る sync_card_attrs / THUMB_RE の置換が
    events.json から埋め直すので、ここでは器だけを正しい形で置く。
    """
    slug = ev.get('slug', '')
    tags_csv = ','.join(ev.get('tags') or [])
    dd = ev.get('dateDisplay') or compact_date(ev)
    pref = ev.get('prefecture', '')
    region = ev.get('region', '')
    badge = ('<span class="event-cancel-badge">'
             + e(cancel_label(ev)) + '</span>') if is_cancelled(ev) else ''
    heart = ('<svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 '
             '5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 '
             '1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>')
    e = html_attr_escape
    return (
        f'<div class="event-card{" event-cancelled" if is_cancelled(ev) else ""}"'
        f' data-tags="{e(tags_csv)}" data-status="upcoming"'
        f' data-region="{e(region)}" data-prefecture="{e(pref)}" data-slug="{e(slug)}"'
        f' data-date="{e(ev.get("date") or "")}"'
        f' data-date-end="{e(ev.get("dateEnd") or "")}"'
        f' data-added-date="{e(ev.get("addedDate") or "")}">\n'
        f'          <div class="event-thumb event-no-image"></div>\n'
        f'          <button class="fav-btn" onclick="toggleFav(event,\'{e(slug)}\')"'
        f' aria-label="行きたい">{heart}</button>\n'
        f'          <div class="swipe-hint"><div class="swipe-hint-icon">{heart}</div></div>\n'
        f'          <div class="event-card-body">\n'
        f'            <div class="event-header"><span class="event-date">{e(dd)}</span>'
        f'{badge}'
        f'<span class="event-status"></span></div>\n'
        f'            <h2 class="event-title">{e(ev.get("name") or "")}</h2>\n'
        f'            <p class="event-description">{e(ev.get("description") or "")}</p>\n'
        f'            <div class="event-meta-row">'
        f'<span class="event-region">{e(pref or region)}</span></div>\n'
        f'          </div>\n'
        f'          <div class="card-fav-bar" onclick="event.stopPropagation()">'
        f'{heart}<span>行きたい</span></div>\n'
        f'        </div>\n        ')


def insert_missing_cards(html, events):
    """events.json にあって index.html に無い開催予定のカードを足す。

    2026-08-31まで、この処理は sync-events.yml のYAML内にPythonで直書き
    されていた。ローカルのビルドチェーンでは走らないので、手で足した回は
    カードが作られず、監査の index_card_drift が「sync-index-cards.py を
    再実行する」と案内していても直らなかった。スクリプト側に持ってくる。
    """
    have = set(re.findall(r'data-slug="([^"]+)"', html))
    add = [e for e in events
           if e.get('slug') and e['slug'] not in have
           and e.get('status') == 'upcoming' and e.get('date')]
    if not add:
        return html, []
    marker = '</div><!-- /eventsGrid -->'
    if marker not in html:
        print('::warning::eventsGrid の目印が無く、カードを挿入できません')
        return html, []
    # 開始日だけで並べると会期の長い回が先頭に居座る。
    # 「今」の定義は sitelib.list_sort_key が単一情報源
    add.sort(key=list_sort_key)
    html = html.replace(marker, ''.join(new_card_html(e) for e in add) + marker)
    return html, [e['slug'] for e in add]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    with open(EVENTS_JSON, encoding='utf-8') as f:
        events = json.load(f)
    by_slug = {e.get('slug'): e for e in events if e.get('slug')}

    with open(INDEX_HTML, encoding='utf-8') as f:
        html = f.read()
    original_html = html

    # エリア絞り込みと地域表。sitelib が唯一の元。
    # index.html に手書きの地域表があり、北海道・東北・四国が丸ごと
    # 抜けていた(その3地域のイベントには一生たどり着けない)。
    # 山梨・長野も北陸から漏れていた(2026-09-08 に発見)。
    # REGION-MAP は top-filter.js に移した(2026-09-08 の外出し)。
    # 貼り替え先が index.html でないので別に扱う。
    _tf = os.path.join(ROOT, 'top-filter.js')
    if os.path.exists(_tf):
        with open(_tf, encoding='utf-8') as f:
            _tfs = f.read()
        _i = _tfs.find('/* REGION-MAP:START')
        _j = _tfs.find('/* REGION-MAP:END */')
        if _i < 0 or _j <= _i:
            print('::warning::REGION-MAP の受け口が top-filter.js に無い')
        else:
            _he = _tfs.find('*/', _i) + 2
            _w = '\n' + region_map_js() + '\n'
            if _tfs[_he:_j] != _w:
                with open(_tf, 'w', encoding='utf-8') as f:
                    f.write(_tfs[:_he] + _w + _tfs[_j:])
                print('REGION-MAP: top-filter.js を更新')

    # 時間軸の定数。status-auto.js が sitelib の event_phase /
    # list_sort_key を書き直しているので、せめて数値は写さない。
    # 挙動の一致は scripts/test-time-parity.py が毎ビルド見る。
    _sa = os.path.join(ROOT, 'status-auto.js')
    if os.path.exists(_sa):
        with open(_sa, encoding='utf-8') as f:
            _sas = f.read()
        _i = _sas.find('/* TIME-CONSTS:START')
        _j = _sas.find('/* TIME-CONSTS:END */')
        if _i < 0 or _j <= _i:
            print('::warning::TIME-CONSTS の受け口が status-auto.js に無い')
        else:
            _he = _sas.find('*/', _i) + 2
            _w = '\n' + time_consts_js() + '\n'
            if _sas[_he:_j] != _w:
                with open(_sa, 'w', encoding='utf-8') as f:
                    f.write(_sas[:_he] + _w + _sas[_j:])
                print('TIME-CONSTS: status-auto.js を更新')

    for _tag, _body in (
            ('AREA-FILTER', area_filter_html(events)),
    ):
        _s = f'<!-- {_tag}:START' if _tag == 'AREA-FILTER' else f'/* {_tag}:START'
        _e = f'<!-- {_tag}:END -->' if _tag == 'AREA-FILTER' else f'/* {_tag}:END */'
        _i = html.find(_s)
        _j = html.find(_e)
        if _i < 0 or _j <= _i:
            print(f'::warning::{_tag} の受け口が index.html に無い')
            continue
        _he = html.find('*/' if _tag == 'REGION-MAP' else '-->', _i) + \
            (2 if _tag == 'REGION-MAP' else 3)
        _wrapped = '\n' + _body + '\n' if _tag == 'AREA-FILTER' \
            else '\n        ' + _body + '\n        '
        if html[_he:_j] != _wrapped:
            html = html[:_he] + _wrapped + html[_j:]
            print(f'{_tag}: 更新')

    # 更新のお知らせ。site-updates.json から毎ビルド貼り替える。
    # index.html を手で書き換える運用にすると、中止を記録したのに
    # お知らせに出ていない状態が起きる。生成物として扱う。
    _u_start = '<!-- UPDATES-SECTION:START'
    _u_end = '<!-- UPDATES-SECTION:END -->'
    _i = html.find(_u_start)
    _j = html.find(_u_end)
    if _i >= 0 and _j > _i:
        _head_end = html.find('-->', _i) + 3
        _body = updates_section_html(load_updates())
        _before = html[_head_end:_j]
        if _before != _body:
            html = html[:_head_end] + _body + html[_j:]
            print(f'updates section: {_body.count("upd-item")} 件に更新')
    else:
        print('::warning::UPDATES-SECTION の受け口が index.html に無い')

    # 範囲別の行。トップで地域チップを押したときにJSが差し替える。
    # トップに埋めるのは全国の最新10件なので、関東で絞ると0件になる
    # ことがあった(関東の更新自体はあるのに)。
    # 行の組み立ては sitelib.update_rows だけが持つので、地域ページと
    # 同じ並び・同じ行になる。
    _scopes = updates_scopes(load_updates())
    _sp = os.path.join(ROOT, 'site-updates-scopes.json')
    _new = json.dumps({'_note': 'scripts/sync-index-cards.py が生成する。手で書かない',
                       'updated': str(today_jst()),
                       'scopes': _scopes}, ensure_ascii=False, indent=1)
    _old = ''
    if os.path.exists(_sp):
        with open(_sp, encoding='utf-8') as f:
            _old = f.read()
    if _old != _new:
        with open(_sp, 'w', encoding='utf-8') as f:
            f.write(_new + '\n')
        print(f'site-updates-scopes.json: {len(_scopes)} 範囲')

    # events.json にあって index.html に無い回のカードを作る
    html, inserted = insert_missing_cards(html, events)
    if inserted:
        print(f'cards inserted: {len(inserted)} -> ' + ', '.join(inserted))

    # 削除されたイベントのカードを除去(events.jsonが正)
    html, stale_removed = remove_stale_cards(html, set(by_slug.keys()))
    if stale_removed:
        print(f'stale cards removed: {stale_removed}')

    # 終了イベントカードの間引き。
    # 全終了カード(168件超)を埋め込むとHTML450KB/DOM4900ノードになり
    # モバイルのパース・レイアウトが重くなる(2026-07-15 PageSpeed対応)。
    # 残す範囲は sitelib.PAST_KEEP_DAYS が単一情報源。以前はここが件数(12件)、
    # status-auto.js が日数(14日)で、全日程の26%で食い違っていた(2026-08-20統合)。
    # 件数は異常時の安全弁として上限だけ見る。
    # 古い終了イベントはアーカイブページ(/archive/)で閲覧できる。
    _today = today_jst()  # JSTで判定(UTCだと前日扱いになる)
    past_cards = []  # (end_date, slug)
    keep_slugs = set()
    for m in re.finditer(r'<div class="event-card[^"]*"[^>]*data-slug="([^"]+)"[^>]*>', html):
        slug_m = m.group(1)
        ev_m = by_slug.get(slug_m)
        if not ev_m:
            continue
        _st, end_m = event_span(ev_m)
        if end_m and end_m < _today:
            past_cards.append((end_m, slug_m))
            if is_recent_past(ev_m, _today):
                keep_slugs.add(slug_m)
    past_cards.sort(reverse=True)
    # 上限を超える分は新しい順に切る
    keep_ordered = [sl for _, sl in past_cards if sl in keep_slugs][:PAST_KEEP_MAX]
    keep_slugs = set(keep_ordered)
    prune = {sl for _, sl in past_cards if sl not in keep_slugs}
    if prune:
        html, _removed2 = remove_stale_cards(html, set(by_slug.keys()) - prune)
        print(f'pruned old past cards: {len(prune)} '
              f'(kept {len(keep_slugs)} = {PAST_KEEP_LABEL}, 上限{PAST_KEEP_MAX})')

    new_chunks = []
    last_end = 0
    swapped_to_img = 0
    swapped_to_noimg = 0
    unchanged = 0
    img_count = 0
    attr_fixed = 0
    for m in CARD_HEADER_RE.finditer(html):
        slug = m.group('slug')
        # 開始タグの data-* を events.json に揃えてから積む
        _tag, _ch = sync_card_attrs(m.group(0), by_slug.get(slug))
        if _ch:
            attr_fixed += 1
            print(f'  attrs {slug}: ' + ' / '.join(_ch))
        new_chunks.append(html[last_end:m.start()])
        new_chunks.append(_tag)
        # Find the FIRST <div class="event-thumb..."> after the card open
        thumb_match = THUMB_RE.search(html, m.end())
        if not thumb_match:
            # No thumb? skip
            last_end = m.end()
            continue
        # Append text between card-open and thumb-start
        new_chunks.append(html[m.end():thumb_match.start()])

        ev = by_slug.get(slug)
        img_url = (ev or {}).get('imageUrl') or ''
        ev_name = (ev or {}).get('name', '') or slug

        existing = thumb_match.group(0)
        if img_url:
            new_html = img_html(img_url, ev_name, eager=(img_count == 0))
            img_count += 1
            if existing != new_html:
                if 'event-no-image' in existing:
                    swapped_to_img += 1
                else:
                    # different image? swap
                    swapped_to_img += 1
                new_chunks.append(new_html)
            else:
                unchanged += 1
                new_chunks.append(existing)
        else:
            _ni = no_img_html(ev)
            if existing != _ni:
                swapped_to_noimg += 1
                new_chunks.append(_ni)
            else:
                unchanged += 1
                new_chunks.append(existing)
        last_end = thumb_match.end()

    new_chunks.append(html[last_end:])
    new_html = ''.join(new_chunks)

    # 本文の同期は別パスでやる。上のループはサムネイルの前後しか触っておらず、
    # 本文（日付・タイトル・説明文・県名）はカードの後半にあるため。
    _starts = [mm.start() for mm in CARD_HEADER_RE.finditer(new_html)]
    body_fixed = 0
    if _starts:
        _out = [new_html[:_starts[0]]]
        for _i, _st in enumerate(_starts):
            _en = _starts[_i + 1] if _i + 1 < len(_starts) else len(new_html)
            _chunk = new_html[_st:_en]
            _sm = re.search(r'data-slug="([^"]+)"', _chunk)
            _slug = _sm.group(1) if _sm else None
            _chunk, _bch = sync_card_body(_chunk, by_slug.get(_slug))
            if _bch:
                body_fixed += 1
                print(f'  body  {_slug}: ' + ' / '.join(_bch))
            _out.append(_chunk)
        new_html = ''.join(_out)

    # 終了セクションの見出しに、載っている範囲を明記する。
    # 「終了したイベント」だけでは全件あるように見えるが、実際は
    # sitelib.PAST_KEEP_DAYS で切った直近ぶんしか載っていない。
    def _note(label):
        return f'<span class="section-heading-note">{label}</span>'

    new_html, n_ph = re.subn(
        r'(id="pastEventsHeading">)終了したイベント'
        r'(?:<span class="section-heading-note">[^<]*</span>)?(</h3>)',
        lambda m: m.group(1) + '終了したイベント' + _note(PAST_KEEP_LABEL) + m.group(2),
        new_html)
    new_html, n_oh = re.subn(
        r'(id="ongoingHeading"[^>]*>)開催中'
        r'(?:<span class="section-heading-note">[^<]*</span>)?(</h2>)',
        lambda m: m.group(1) + '開催中' + _note(f'会期{LONG_RUN_DAYS}日以上') + m.group(2),
        new_html)
    print(f'section headings:    終了={n_ph} 開催中={n_oh}')

    # 開催予定件数のバッジ。以前は daily.yml のステップが更新していたが、
    # そのステップは build-all.sh(=auto-status-jst.py)より前に走るため
    # 終了に変わる回を数え落とし、さらに sync-events / weekly-enrichment 経由の
    # ビルドでは誰も更新しなかった。build-all.sh に載っているここへ移した。
    up_count = sum(1 for e in events if e.get('status') == 'upcoming')
    new_html, n_badge = re.subn(
        r'(<span class="event-count" id="eventCount">)\d+(件</span>)',
        lambda m: m.group(1) + str(up_count) + m.group(2), new_html)
    print(f'upcoming badge:      {up_count}件 ({n_badge} 箇所)')

    print(f'cards processed:     {swapped_to_img + swapped_to_noimg + unchanged}')
    print(f'  → swapped to img:  {swapped_to_img}')
    print(f'  → swapped to no-image: {swapped_to_noimg}')
    print(f'  → unchanged:       {unchanged}')
    print(f'  → 属性を直したカード: {attr_fixed}')
    print(f'  → 本文を直したカード: {body_fixed}')

    if new_html != original_html:
        if args.dry_run:
            print('(dry-run, not writing)')
        else:
            with open(INDEX_HTML, 'w', encoding='utf-8') as f:
                f.write(new_html)
            print(f'index.html updated.')
    else:
        print('No changes needed.')


if __name__ == '__main__':
    main()
