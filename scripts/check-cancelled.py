#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""開催予定の回について、主催者の出典に中止・延期の兆候が出ていないか毎日見る。

coverage-sweep.py の逆。あちらは「他所にあってこちらに無い回」を探し、
こちらは「こちらにあって、もう開催されない回」を探す。

## なぜ要るか

2026-09-08まで、掲載は追加の一方通行だった。Collect Plants Vol.3 は
2026-07-28 の令和8年熊本地震を受けて 08-12 に中止が告知されていたが、
当サイトは 09-08 まで27日間「開催予定」として載せ続けた。気づいたのは
主催者からフォームで削除依頼が来たからで、こちらからは何も見ていなかった。

## 2つの信号を使う

1. **文言**: ページの本文・title・og・画像のalt・画像のファイル名から
   「中止」「延期」等を探す。安いが、取りこぼす。
2. **変化**: 本文と画像URLの集合のハッシュを前回と比べる。開催が近い回の
   公式ページが動いたら、それだけで人が見る理由になる。

3. **日付**: 頁が散文で日付を名乗っているのに、そこに**この回の開催日が
   一度も出てこない**なら、その出典はこの回を裏付けていない。同じシリーズの
   前回の記事を出典にしている型と、名前が同じだけの無関係な頁を掴んでいる型を
   拾う(2026-09-08 に2件検出。Wi-Wi BOTANICAL Vol.2 は6月開催回のニュース記事、
   ONE LOVE 佐野は同名のアイドルグループのライブ日程頁だった)。
   `url` は「在るか」しか見られていないので、中身が別の回でも薄頁判定を外れ、
   詳細頁は「裏取り済み」の顔で出る。判定は audit.source_page_wrong_edition。

**2 が要るのは、日本の主催者が告知を画像で出すから。** collect-plants.com は
トップのメインビジュアルに「開催中止のお知らせ」と大書していたが、
HTMLの文字列には一言も無く、1 では絶対に見つからない。
画像の中の文字はOCRなしには読めないので、ここは「変わった」ことだけを見て
人に回す。ノイズは出る。出ないようにすると今回の型を落とす。

## 使い方

    python3 scripts/check-cancelled.py            # 巡回して cancel-watch.json を更新
    python3 scripts/check-cancelled.py --self-test  # 判定だけ検証(通信なし)
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, SCRIPT_DIR)
import sitelib                                            # noqa: E402
from sitelib import (today_jst, is_cancelled, event_span,   # noqa: E402
                     find_month_days, event_month_days)

WATCH_JSON = os.path.join(REPO, 'cancel-watch.json')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

# 開催まで何日先まで見るか。過ぎた回と遠い回は毎日取りに行っても意味が薄い
HORIZON_DAYS = 60

# 中止・延期を示す語。「順延」は雨天順延の告知でも出るので単独では弱いが、
# 人が見る材料としては拾ってよい
CANCEL_WORDS = (
    '開催中止', '中止のお知らせ', '中止となりました', '中止いたします',
    '中止させていただ', '開催を中止', '中止が決定',
    '延期のお知らせ', '延期となりました', '延期させていただ', '開催を延期',
    '開催見合わせ', '見合わせとなりました', '開催を見送',
)
# 「中止」単独は「雨天中止」「中止の場合は」など条件付きの文でも出る。
# 単独語は弱い信号として別に数える
WEAK_WORDS = ('中止', '延期', '見合わせ', 'キャンセル')

# 出典がSNSのものは本文が取れないので巡回しない(ログインが要る)
SKIP_DOMAINS = ('instagram.com', 'twitter.com', 'x.com', 'facebook.com',
                'tiktok.com', 'peatix.com')


def norm(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s or '')).strip()


def strip_html(html):
    """本文のテキスト。script/style/noscript は落とす"""
    h = re.sub(r'(?is)<(script|style|noscript)\b.*?</\1>', ' ', html or '')
    h = re.sub(r'(?s)<!--.*?-->', ' ', h)
    h = re.sub(r'<[^>]+>', ' ', h)
    return norm(h)


def image_tokens(html):
    """画像のURLとalt。告知が画像のとき、ファイル名やaltに手がかりが残る"""
    out = []
    for m in re.finditer(r'(?is)<img\b[^>]*>', html or ''):
        tag = m.group(0)
        src = (re.search(r'(?i)\bsrc\s*=\s*["\']([^"\']+)', tag) or [None, ''])[1]
        alt = (re.search(r'(?i)\balt\s*=\s*["\']([^"\']*)', tag) or [None, ''])[1]
        if src:
            out.append(norm(src))
        if alt:
            out.append(norm(alt))
    for m in re.finditer(r'(?i)<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', html or ''):
        out.append(norm(m.group(1)))
    return out


def meta_texts(html):
    out = []
    t = re.search(r'(?is)<title[^>]*>(.*?)</title>', html or '')
    if t:
        out.append(norm(re.sub(r'<[^>]+>', ' ', t.group(1))))
    for prop in ('og:title', 'og:description', 'description'):
        for m in re.finditer(
                r'(?i)<meta[^>]+(?:property|name)=["\']' + re.escape(prop)
                + r'["\'][^>]+content=["\']([^"\']*)', html or ''):
            out.append(norm(m.group(1)))
    return out


# 天候の条件を述べているだけの言い回し。**告知ではない。**
# 「※雨天時は中止となる場合があります」で毎日鳴っていた
# (GreenSnap Marche 横浜。中止したのはイベントではなく、
#  雨のときのマスコットのグリーティング。2026-09-09 確認)。
#
# 「場合」「際」「とき」が付く条件文と、雨天中止・荒天中止の熟語だけを
# 落とす。「悪天候のため中止しました」は残す。過去形で言い切っている
# ものは本物の告知なので、消してはいけない。
CONDITIONAL_CANCEL = (
    r'[雨荒悪][天候][時中]?[はの]?(?:場合|際|とき)?[はに]?(?:中止|順延|延期)',
    r'(?:中止|順延|延期)(?:と)?(?:なる|する|の)?(?:場合|際|とき)',
    r'雨天中止',
    r'荒天中止',
    # 「荒天の場合はインスタグラムにて中止のお知らせを致します」。条件と語の間に
    # 手段や経路が挟まる形。福岡グリーンパーティー第7回の注意事項が
    # organizer_cancel_signal(urgent) で鳴った(2026-09-23、ig-organizer-watch の初回)
    r'(?:雨天|荒天|悪天候|台風)(?:の)?(?:場合|際|時|とき)[^。\n]{0,30}?(?:中止|延期|順延)(?:の(?:お知らせ|ご連絡|告知))?',
    # これから知らせるという予告。まだ中止していない
    r'(?:中止|延期)(?:の)?(?:お知らせ|ご連絡|告知)を(?:致|いた)?します',
    # 「掲載イベントは状況により変更・中止されることもございます」。施設の月間チラシ・
    # 広報誌の定型の断り書き。可能性を述べているだけで告知ではない
    # (みずの森の月間チラシ PDF、2026-10-04)
    r'(?:変更|延期|中止)[・、]?(?:変更|延期|中止)?(?:される|となる|になる|する)(?:こと|場合)(?:も|が)(?:ございます|あります|あり得ます|ありえます)',
)


# 中止しているのがイベントではなく**出展者1組**である言い回し。
# 「9月19日(土)、20日(日)に出展予定のkuwa.botanicalさんは都合により
#  出展中止となりました。予めご了承ください。」(しまね花の郷『俺の！
#  プランツ・コレクション！！』2026-09-14 確認)。
# これは条件文ではなく言い切りなので CONDITIONAL_CANCEL では落ちず、
# CANCEL_WORDS の「中止となりました」に当たって urgent で鳴っていた。
# 会場が出展者の入れ替わりを本文に書き続ける頁では毎日鳴る。
#
# **主語が出展・出店・出品・参加であるときだけ落とす。**
# 「開催中止」「イベント中止」は主語が違うので残る。
VENDOR_CANCEL = (
    r'(?:出展|出店|出品|参加)(?:を)?(?:中止|取り止め|取りやめ|辞退)'
    r'(?:と)?(?:なりました|なります|いたします|します|させていただ\w*)?',
)


# 中止しているのがイベント本体ではなく**同じ主催の別の催し**である言い回し。
# 京都カクタスクラブの頁(第51回 日本シャボテン大会の出典)は過去の年間予定を
# 載せ続けていて、「( 1月、2月、5月の例会は開催が中止となりました )」(2021年)
# が CANCEL_WORDS に当たる。2026-09-30 に文字コードの誤読を直すまで化けていて
# 見えていなかった。主語が例会・講習会などのときだけ落とす。
SUBPROGRAM_CANCEL = (
    r'(?:例会|講習会|教室|ワークショップ|体験会)(?:は|が|を)?(?:開催(?:が|を)?)?'
    r'(?:中止|延期)(?:と)?(?:なりました|なります|いたします|します|させていただ\w*)?',
)


# キャンセルしているのがイベントではなく**通販の注文**である言い回し。
# FIGURE HANARE の入店抽選は 0円の商品を注文させて応募を受け付ける仕組みで、
# 頁に「ご注文は自動的にキャンセルされます」「キャンセル完了までにお時間」が並ぶ。
# 弱い語「キャンセル」に当たり、SPICY GEM feat. KAKUSEN-EN の回が
# 「弱い語(キャンセル)＋ページが変わった」で鳴った(2026-10-01 確認。会期は変わっていない)。
# 主語が注文のもの、手続きの名詞(完了・料・待ちなど)が続くものだけ落とす。
# 「イベントはキャンセルとなりました」は残る。
ORDER_CANCEL = (
    r'(?:ご)?注文(?:は|が|を|の)?(?:自動(?:的)?(?:に|で)?)?[「『]?キャンセル',
    r'キャンセル(?:完了|処理|料|待ち|規定|ポリシー|について)',
    # 否定形は中止の告知にならない(「※キャンセルされていない場合は」)
    r'キャンセルされ(?:てい)?ない',
)


# 止まっているのがイベントではなく**施設の利用**である言い回し。
# 須磨離宮公園の頁は全頁の共通欄に施設の状況を出していて、
# 「駐車場 空いています … 子供の森 利用中止」が弱い語「中止」に当たり、
# サボテン・多肉植物展示会(10/16-18)が「弱い語(中止)＋ページが変わった」で
# 鳴った(2026-10-05 確認。告知本文は会期も内容も変わっていない)。
# 催しの中止は「開催中止」「中止となりました」と書く。「利用」「使用」が
# 主語の側に付く中止は、施設・設備の話なので落とす。
FACILITY_CANCEL = (
    r'(?:利用|使用|ご利用)(?:を)?(?:中止|休止|停止)(?:中)?',
)


def drop_conditional(text):
    """イベントの中止を指していない言い回しを落とす。判定に使う前に通す。

    落とすのは5種類。(1) 天候の条件文 (2) 主語が出展者1組の取り止め
    (3) 主語が例会・講習会など同じ主催の別の催し (4) 通販の注文のキャンセル
    (5) 施設・設備の利用の中止。
    どちらも「イベントが中止になったか」とは別のことを言っている。
    """
    out = text
    for pat in (CONDITIONAL_CANCEL + VENDOR_CANCEL + SUBPROGRAM_CANCEL
                + ORDER_CANCEL + FACILITY_CANCEL):
        out = re.sub(pat, ' ', out)
    return out


def find_words(texts):
    """強い語と弱い語をそれぞれ拾う。条件文は数えない"""
    blob = drop_conditional(' '.join(texts))
    strong = sorted({w for w in CANCEL_WORDS if w in blob})
    weak = sorted({w for w in WEAK_WORDS if w in blob})
    return strong, weak


def drop_today(text, today=None):
    """今日の日付を落とす。

    「本日の開園時間 2026.09.09 9:30〜17:00」のような表示を持つ頁があり、
    本文が毎日変わる。**未来のイベントが中止かどうかと、頁に今日の日付が
    出ていることは何の関係もない**(しまね花の郷で2件が毎日鳴っていた。
    2026-09-09 確認)。署名を作る前にこれだけ落とす。
    イベントの日付は落とさない。日程変更は拾いたい信号なので。
    """
    d = today or today_jst()
    if isinstance(d, str):
        # sitelib.today_jst() は文字列を返す。date に揃える
        d = date.fromisoformat(d[:10])
    pats = [
        f'{d.year}.{d.month:02d}.{d.day:02d}', f'{d.year}.{d.month}.{d.day}',
        f'{d.year}/{d.month:02d}/{d.day:02d}', f'{d.year}/{d.month}/{d.day}',
        f'{d.year}-{d.month:02d}-{d.day:02d}',
        f'{d.year}年{d.month}月{d.day}日',
    ]
    out = text
    for x in pats:
        out = out.replace(x, ' ')
    return out


def og_images(html):
    return [norm(m.group(1)) for m in re.finditer(
        r'(?i)<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
        html or '')]


def main_entry(html, event=None):
    """頁の主たる記事。署名をこの範囲に絞ってよいときだけ HTML 片を返す。

    WordPress の単独記事頁は、本文の `<article>` の外に「新着のお知らせ」の
    抜粋とサムネイルを並べる。新しいお知らせが1本出るたびに本文と画像が
    **同時に**変わるので、本文だけ・画像だけの変化を数えない規則
    (textOnlyChanges / imageOnlyChanges)にも掛からず、毎回
    「公式ページが変わった(本文・画像)」で鳴る。ROOTS MARKET の頁
    (sunsetbeachpark.jp)は 09-24 から 10-05 までに5回鳴り、5回とも
    告知本文は1字も変わっていなかった(2026-10-05)。

    絞るのは次の2つを両方満たすときだけ。
    - `<article>` が頁にちょうど1つ(一覧頁は記事が並ぶので絞らない)
    - その中にこの回の開催日が出ている(記事が別物なら絞ると見えなくなる)
    実測(2026-10-05 の巡回対象25件): 当たるのは3件(ROOTS MARKET と
    GreenSnap Marche 2件)。`<article>` が1つでも開催日が無い3件
    (weekend.osaka・咲くやこの花館・FIGURE HANARE)は絞らない。

    中止の語は従来どおり頁全体から拾う(analyze)。新着欄に
    「◯◯中止のお知らせ」が出れば強い語で鳴る。絞るのは署名だけ。
    """
    starts = [m.start() for m in re.finditer(r'(?i)<article\b', html or '')]
    if len(starts) != 1:
        return None
    m = re.search(r'(?i)</article\s*>', html[starts[0]:])
    if not m:
        return None
    frag = html[starts[0]:starts[0] + m.end()]
    if event is None:
        return None
    span = event_month_days(event)
    if not span:
        return None
    _named, found = page_dates(frag)
    return frag if (span & found) else None


def page_signature(html, today=None, scope=None):
    """本文と画像の集合から署名を作る。

    画像の中の文字は読めないので、URLの集合が変わったことをもって
    「差し替わった」と見る。メインビジュアルが告知画像に変わる型を拾うため。
    `scope` (main_entry の返り値)があれば本文と画像はその範囲だけを見る。
    og:image は頁の `<head>` にあり記事の外なので、頁全体から足す
    (告知画像を「中止」の絵に差し替えた回は og:image で拾う)。
    """
    src = scope if scope else html
    body = drop_today(strip_html(src), today)
    imgs = image_tokens(src)
    if scope:
        imgs = imgs + og_images(html)
    imgs = sorted(set(imgs))
    return {
        'text': hashlib.sha256(body.encode('utf-8')).hexdigest()[:16],
        'images': hashlib.sha256('\n'.join(imgs).encode('utf-8')).hexdigest()[:16],
        'textLen': len(body),
        'imageCount': len(imgs),
    }


# 頁が名乗っている日付の規則は sitelib.page_dates が単一情報源
# (2026-09-10)。ここにしか無かったので、url を**書く側**の
# enrich_events.py は同じ判定を持たず、別の回の記事を掴んだ2件を
# 本番に出した。見張る側と書く側で同じ関数を呼ぶ。
page_dates = sitelib.page_dates


# 更新日・投稿日として名乗られた日付。**単一情報源は sitelib**
# (2026-09-13 に移管)。ここが持っていた間、書く側の
# check_date_updates.py は同じ判定を持たず、頁の更新日を開始日として
# 書き戻していた。見張る側と書く側で同じ関数を呼ぶ。
meta_dates = sitelib.meta_dates


def analyze(html, event=None):
    texts = [strip_html(html)] + meta_texts(html) + image_tokens(html)
    strong, weak = find_words(texts)
    scope = main_entry(html, event)
    sig = page_signature(html, scope=scope)
    named, found = page_dates(html)
    out = {'strong': strong, 'weak': weak, 'signature': sig,
           'datesNamed': named, 'sigScope': 'article' if scope else 'page'}
    if event is not None:
        span = event_month_days(event)
        out['eventDateSeen'] = bool(span & found) if span else None
        # 会期の開始日が、頁の**更新日・投稿日**と同じでないか。
        # audit の event_start_is_page_meta が読む(2026-09-12)。
        # 道の駅仁保の郷の回は、告知が開催日を「9月19日（土）」1つしか
        # 書いていないのに events.json が date=2026-09-02(頁の更新日) 〜
        # dateEnd=2026-09-19 になっており、単日の回が18日間「開催中」で出ていた。
        # 更新日も「◯月◯日」なので find_month_days には入る。つまり
        # 「開始日が頁に無い」では落ちない。**日付の在処ではなく肩書を見る。**
        start, _end = event_span(event)
        sm = None
        if start:
            try:
                _d = date.fromisoformat(start)
                sm = (_d.month, _d.day) in meta_dates(html)
            except ValueError:
                sm = None
        out['startDateIsPageMeta'] = sm
    return out


def fetch(url, timeout=20, retries=2, wait=3.0):
    """取得。**接続系の失敗は retries 回まで待って引き直す(2026-09-12)。**

    errors に載ると audit.cancel_watch_unreachable が鳴るが、CI の
    取りこぼしは一過性で、失敗する先が日替わりになる:
    09-10 は sakuya-green-jam / kourep / souransai / jurian の4件、
    09-11 は jurian の1件、09-12 は isij / ontheplants / bookkasama の3件。
    09-12 にこの3件を同じ UA で手元から引くと3件とも200で返った。
    **落ちているのは相手ではなく、その回の接続。**引き直さずに記録すると
    「巡回が失敗している」という本物の警告が、毎日入れ替わる雑音に埋まる。

    **2026-09-17 訂正: 「HTTPError は相手の返事なので引き直さない」は
    503 では誤り。**503/502/504/429 は「今は無理、あとで来い」という返事で、
    引き直すべき側にある。404/403 とは意味が違う。同じ日に coverage-sweep が
    LEAFLA の 503 を2枚拾って urgent を鳴らし、手元から引くと200で返った。
    引き直す status の一覧と実装は sitelib.fetch_text が単一情報源。
    **同じ判断を2本の巡回スクリプトが別々に持っていたので寄せた。**
    """
    return sitelib.fetch_text(url, timeout=timeout, retries=retries,
                              wait=wait, ua=UA)


def watch_targets(events, today, horizon=HORIZON_DAYS):
    """巡回対象。開催予定で、出典が取れるURLを持つ回だけ"""
    t = date.fromisoformat(today)
    out = []
    for e in events:
        if is_cancelled(e):
            continue
        d, de = event_span(e)
        if not d:
            continue
        try:
            end = date.fromisoformat(de or d)
            start = date.fromisoformat(d)
        except ValueError:
            continue
        if end < t or (start - t).days > horizon:
            continue
        url = (e.get('url') or e.get('sourceUrl') or '').strip()
        if not url or url == '#':
            continue
        if any(dom in url for dom in SKIP_DOMAINS):
            continue
        out.append((e, url))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('--sleep', type=float, default=0.8)
    ap.add_argument('--horizon', type=int, default=HORIZON_DAYS)
    args = ap.parse_args()
    if args.self_test:
        return self_test()

    # 判定が壊れたまま巡回すると、もっともらしい「兆候なし」が書き込まれ、
    # 読む側からは正常と区別が付かない。coverage-sweep が 2026-09-01 に
    # 同じ穴(どのCIからも呼ばれない自己テスト)を塞いだのに、こちらは
    # 外れたままだった(2026-09-08)。daily の push を巻き込みたくないので
    # ジョブは止めず、logicErrors に積んで audit の
    # cancel_watch_broken(urgent) に出す。
    logic_errors = []
    if self_test(verbose=False) != 0:
        logic_errors.append('自己テストが失敗した。判定ロジックが壊れている。'
                            'suspects と eventDateSeen は当てにならない'
                            '(python3 scripts/check-cancelled.py --self-test)')

    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    try:
        with open(WATCH_JSON, encoding='utf-8') as f:
            prev = json.load(f)
    except (OSError, ValueError):
        prev = {}
    prev_pages = (prev.get('pages') or {})

    today = today_jst()
    targets = watch_targets(events, today, args.horizon)
    pages, suspects, errors = {}, [], []
    stats = {'targets': len(targets), 'fetched': 0}

    for e, url in targets:
        slug = e.get('slug') or ''
        try:
            html = fetch(url)
            stats['fetched'] += 1
        except urllib.error.HTTPError as err:
            errors.append(f'{slug}: HTTP {err.code} {url}')
            continue
        except Exception as err:                      # noqa: BLE001
            errors.append(f'{slug}: {type(err).__name__} {url}')
            continue

        res = analyze(html, e)
        before = prev_pages.get(slug) or {}
        bsig = before.get('signature') or {}
        sig = res['signature']
        changed = []
        # 化けた字(U+FFFD)の数。audit.cancel_watch_undecodable が読む(2026-09-30)。
        # 文字コードを読み違えた頁は、語も日付も拾えないまま「見張っている」ことになる。
        bad_chars = html.count('\ufffd')
        # UTF-8 以外の頁は 2026-09-30 に読み方を直したので、直した後の初回だけ
        # 本文の署名が変わる。中身の変化ではないので、その回は本文の変化に数えない。
        reread = ('badChars' not in before and bool(bsig) and bool(re.search(
            r'charset=["\']?\s*(?:shift_jis|shift-jis|sjis|windows-31j|euc-jp|iso-2022-jp)',
            html[:4096], re.I)))
        # 前回まで化けていた頁が読めるようになった回も同じ(2026-10-04)。
        # PDF の出典を UTF-8 で読んでいた回は署名が化けた字のハッシュなので、
        # 読めるようになった初回に「本文が変わった」を中止の兆候として鳴らしてしまう。
        if (isinstance(before.get('badChars'), int) and before['badChars'] >= 20
                and bad_chars < 20):
            reread = True
        # 署名の範囲(頁全体 / 主たる記事)が前回と変わった回は、本文も画像も
        # 範囲が違うものどうしの比較になる。中身の変化ではないので数えない
        # (2026-10-05 に main_entry を入れた。前回の記録に範囲が無ければ頁全体)。
        rescoped = bool(bsig) and (before.get('sigScope') or 'page') != res['sigScope']
        if bsig and not rescoped:
            if bsig.get('text') != sig['text'] and not reread:
                changed.append('本文')
            if bsig.get('images') != sig['images']:
                changed.append('画像')

        # 前回の本文の長さを持ち回る(2026-09-15)。**署名はハッシュなので、
        # 「増えたのか減ったのか」が分からない。**告知が足された回と、
        # 告知が消えた/差し替わった回が、同じ「本文が変わった」1行になる。
        # 監査側 audit.cancel_watch_body_shrunk が この差を読む。
        pages[slug] = {
            'url': url, 'checkedOn': today, 'signature': sig,
            # 読み方か範囲が変わった回の前回の字数は、別の物差しで測った値。
            # 比べると audit.cancel_watch_body_shrunk が鳴る。みずの森の PDF は
            # 化けた生バイト 660406字 → 本文 1642字で -100% と出た(2026-10-05)。
            'prevTextLen': (None if (reread or rescoped) else bsig.get('textLen')),
            'sigScope': res['sigScope'],
            'strong': res['strong'], 'weak': res['weak'],
            # 出典がこの回を裏付けているか。audit.source_page_wrong_edition が読む。
            # CI から頁を取れるのはこのスクリプトだけなので、判定材料を
            # ここに置かないと監査側からは見えない
            'datesNamed': res['datesNamed'],
            'eventDateSeen': res.get('eventDateSeen'),
            'startDateIsPageMeta': res.get('startDateIsPageMeta'),
            'firstSeenOn': before.get('firstSeenOn') or today,
            'badChars': bad_chars,
        }

        # 「本文だけ毎回変わる」ページがある。Wix や WordPress の一部は
        # 日付・カウンタ・ランダムなIDを埋め込むので、中止と無関係に
        # 署名が動く。同じ回で本文だけの変化が続いたら数えない。
        # 毎日鳴る指摘は読まれなくなり、本物の変化を埋める(2026-09-08)。
        noisy = int(before.get('textOnlyChanges') or 0)
        text_only = (changed == ['本文'])
        if text_only:
            noisy += 1
        elif changed:
            noisy = 0
        pages[slug]['textOnlyChanges'] = noisy

        # 画像だけの変化にも同じ扱いを当てる(2026-09-29)。ROOTS MARKET の頁
        # (sunsetbeachpark.jp、画像45枚)は本文が1字も変わらないまま、横の
        # 新着記事のサムネイルが入れ替わるたびに「公式ページが変わった(画像)」で
        # 毎日鳴り、確認して cancel-reviewed.json に書いても翌日また鳴った。
        # 告知画像の差し替えは一度きりの変化なので、続けて起きる画像の変化は数えない。
        img_noisy = int(before.get('imageOnlyChanges') or 0)
        image_only = (changed == ['画像'])
        if image_only:
            img_noisy += 1
        elif changed:
            img_noisy = 0
        pages[slug]['imageOnlyChanges'] = img_noisy

        why = []
        if res['strong']:
            why.append('中止・延期の語: ' + ' / '.join(res['strong']))
        elif res['weak'] and changed:
            why.append('弱い語(' + ' / '.join(res['weak']) + ')＋ページが変わった')
        elif '画像' in changed and not (image_only and img_noisy > 2):
            why.append('公式ページが変わった(' + '・'.join(changed) + ')')
        elif text_only and before and noisy <= 2:
            # 字数の増減を添える。**「変わった」だけでは、足されたのか
            # 消えたのかが読めず、一次情報を開くまで軽重が分からない。**
            # 2026-09-15 の食虫植物祭は 3041→1334字(-56%)で、
            # 文面は「チケット販売のお知らせが増えた」形に見えていた。
            _b, _a = bsig.get('textLen'), sig.get('textLen')
            if isinstance(_b, int) and isinstance(_a, int) and _b:
                why.append('公式ページが変わった(本文: '
                           f'{_b}→{_a}字 {(_a - _b) * 100 // _b:+d}%)')
            else:
                why.append('公式ページが変わった(本文)')
        if why:
            suspects.append({
                'slug': slug, 'name': e.get('name') or '',
                'date': e.get('date') or '', 'url': url,
                'why': ' / '.join(why),
                'changed': changed,
            })
        time.sleep(args.sleep)

    out = {
        '_note': ('開催予定の回について、主催者の出典に中止・延期の兆候が出ていないかを'
                  '毎日見た結果。scripts/check-cancelled.py が書く。'
                  'suspects は「人が見る理由がある」だけで、中止の証拠ではない。'
                  '一次情報を確認して、中止なら events.json の eventStatus を '
                  'cancelled にする(削除しない)。'
                  '**画像の中の文字は読めない。**主催者が告知を画像で出す型は '
                  'signature の変化でしか拾えないので、ノイズは織り込んでいる。'
                  'errors が空でないときは巡回そのものが失敗しているので、'
                  'suspects が0件でも「兆候なし」とは言えない。'),
        'sweptOn': today, 'stats': stats, 'errors': errors,
        'logicErrors': logic_errors,
        'suspects': sorted(suspects, key=lambda x: x['date']),
        'pages': pages,
    }
    with open(WATCH_JSON, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f"巡回対象 {stats['targets']} 件 / 取得できた {stats['fetched']} 件")
    print(f"★ 中止の疑い: {len(suspects)}件")
    for s in suspects:
        print(f"    {s['date']} {s['name'][:34]} — {s['why']}")
    if errors:
        print(f"⚠ 取得できなかった: {len(errors)}件")
        for e in errors[:10]:
            print('    ' + e)
    return 0


# ---------------------------------------------------------------- self-test
FIX_TEXT_NOTICE = '''<html><head><title>◯◯フェス</title></head><body>
<h1>◯◯フェス</h1><p>このたびの台風の影響により、開催中止のお知らせを申し上げます。</p>
<img src="/img/key.jpg" alt="キービジュアル"></body></html>'''

FIX_IMAGE_NOTICE_BEFORE = '''<html><head><title>コレクトプランツ</title></head><body>
<img src="/uploads/2025/06/collectplants_mv2_pc.png" alt="">
<p>熊本最大級の植物イベント</p></body></html>'''

FIX_IMAGE_NOTICE_AFTER = '''<html><head><title>コレクトプランツ</title></head><body>
<img src="/uploads/2026/08/cancel_mv.png" alt="">
<p>熊本最大級の植物イベント</p></body></html>'''

FIX_WEAK = '''<html><head><title>△△マルシェ</title></head><body>
<p>雨天中止の場合はInstagramでお知らせします。</p>
<img src="/img/a.jpg" alt=""></body></html>'''

FIX_PLAIN = '''<html><head><title>□□植物祭</title></head><body>
<p>今年も開催します。出店者を募集中です。</p>
<img src="/img/b.jpg" alt=""></body></html>'''

# 出典が「同じ名前の前回の回」を指している型。頁は日付を名乗っているのに、
# それは6月開催回のもの(2026-09-08 の wi-wi-botanical-minokamo-2026-09)
FIX_WRONG_EDITION = '''<html><head><title>【美濃加茂市】「Wi-Wi BOTANICAL」開催</title></head><body>
<p>2026年6月7日（日）、リバーポートパーク美濃加茂にて開催されます。</p>
<p>関連記事 8月30日のマルシェ / 9月28日で休業</p></body></html>'''

# 出典は正しいが、日付は画像の中にしか無い公式トップ頁。
# ここで鳴らすと、告知を画像で出す主催が全部誤検知になる
FIX_DATE_IN_IMAGE = '''<html><head><title>【公式】On the Plants</title></head><body>
<p>九州最大級の複合販売イベント。出店者を募集しています。</p>
<img src="/wp-content/uploads/2026/09/keyvisual.jpg" alt=""></body></html>'''

# 日付を「2026.10.10」形式だけで書く頁。名乗りの数は0でも、
# この回の日付は拾えていなければならない
FIX_DOT_DATE = '''<html><head><title>◇◇サボテン展</title></head><body>
<p>会期 2026.10.10 - 2026.10.11 / 入場無料</p></body></html>'''


FIX_COND = """<html><body><h1>◯◯マルシェ</h1>
<p>2026年10月10日(土) 開催します。</p>
<p>※雨天時は中止となる場合があります。最新情報はSNSでご確認ください。</p>
</body></html>"""

FIX_REAL_WEATHER = """<html><body><h1>◯◯マルシェ</h1>
<p>悪天候のため中止しました。ご来場を予定されていた皆様にお詫び申し上げます。</p>
</body></html>"""

# 出展者1組が降りただけの頁。イベントは開催される(2026-09-14)
FIX_VENDOR_CANCEL = """<html><body><h1>俺の！プランツ・コレクション！！</h1>
<p>9月19日（土）、20日（日）に出展予定のkuwa.botanicalさん（展示物：アガベなど）は
都合により出展中止となりました。予めご了承ください。</p>
<p>開催期間 2026/09/19 〜 2026/09/21</p></body></html>"""

# 「本日の開園時間」を持つ頁。中身は同じで日付だけが違う
FIX_TODAY_A = """<html><body><p>本日の開園時間 2026.09.09 9:30〜17:00</p>
<h1>サボテン・多肉植物展</h1><p>開催期間 2026/10/10 〜 2026/10/12</p>
</body></html>"""

FIX_TODAY_B = """<html><body><p>本日の開園時間 2026.09.10 9:30〜17:00</p>
<h1>サボテン・多肉植物展</h1><p>開催期間 2026/10/10 〜 2026/10/12</p>
</body></html>"""

FIX_DATE_CHANGED = """<html><body><p>本日の開園時間 2026.09.09 9:30〜17:00</p>
<h1>サボテン・多肉植物展</h1><p>開催期間 2026/10/17 〜 2026/10/19</p>
</body></html>"""



# 単日の告知。開催日は「9月19日（土）」しか書いていない。
# 頁の更新日を開始日に拾った事故の再現に使う(2026-09-12)
FIX_ONE_DAY_PAGE = """<html><body>
<p>更新日：9月2日</p>
<h1>第1回「緑と多肉を楽しむマルシェ」開催</h1>
<p>【開催日時】9月19日（土）　9:00〜15:00　雨天中止</p>
</body></html>"""

# 会期を省略形で書く告知。開始日は全形で出るが終了日は数字だけ
FIX_SPAN_PAGE = """<html><body>
<h1>SPECIAL EVENT</h1>
<p>9月20日（日）から3日間。9/20-22 の開催です。</p>
</body></html>"""


def _tiny_pdf(text):
    """自己テスト用の1頁の PDF(ASCII 本文)を組み立てる"""
    objs = [b'<</Type/Catalog/Pages 2 0 R>>', b'<</Type/Pages/Kids[3 0 R]/Count 1>>',
            b'<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]/Contents 4 0 R'
            b'/Resources<</Font<</F1 5 0 R>>>>>>', None,
            b'<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>']
    st = b'BT /F1 12 Tf 10 100 Td (' + text.encode('ascii') + b') Tj ET'
    objs[3] = b'<</Length %d>>stream\n' % len(st) + st + b'\nendstream'
    out, offs = bytearray(b'%PDF-1.4\n'), []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b'%d 0 obj' % i + o + b'endobj\n'
    x = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1)
    for o in offs:
        out += b'%010d 00000 n \n' % o
    out += b'trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF' % (len(objs) + 1, x)
    return bytes(out)


# WordPress の単独記事頁。本文の <article> の外に新着のお知らせが並ぶ(2026-10-05)
FIX_WP_ENTRY = '''<html><head><title>ROOTS MARKET開催決定</title>
<meta property="og:image" content="https://x.jp/uploads/2026/09/roots_market.png"></head><body>
<main><article class="post-7291 post type-post">
<h1>10月25日(日)にROOTS MARKET開催決定</h1>
<img src="https://x.jp/uploads/2026/09/roots_market.png" alt="">
<p>開催日 2026年10月25日(日) 時間 10:00~16:00 場所 時計台広場</p>
</article></main>
<aside><section class="c-entry-summary"><img src="https://x.jp/uploads/2026/09/{news}.jpg" alt="">
<h3>{news}のお知らせ</h3><p>{news}についてお知らせいたします。</p></section></aside>
</body></html>'''


def self_test(verbose=True):
    ok = True

    def chk(label, got, want):
        nonlocal ok
        mark = 'OK ' if got == want else '★NG'
        if got != want:
            ok = False
        if verbose or got != want:
            print(f'  {mark} {label}: {got!r} 期待={want!r}')

    def say(msg):
        if verbose:
            print(msg)

    say('--- PDF の出典 (2026-10-04) ---')
    # PDF の生バイトを UTF-8 で読むと U+FFFD だらけになり、語も日付も拾えない
    try:
        _pt = sitelib.decode_html(_tiny_pdf('Closed 10/23-25'), 'application/pdf')
    except sitelib.UnreadableDocument:
        _pt = None   # 読む手段が無い環境。本番では errors に積まれ urgent で出る
    if _pt is not None:
        chk('PDF の本文を文字にできる', 'Closed 10/23-25' in _pt, True)
        chk('PDF を読んで化けた字が出ない', _pt.count('\ufffd'), 0)
    chk('PDF の判定(先頭バイト)', sitelib.is_pdf(b'%PDF-1.4\n'), True)
    chk('HTML は PDF と判定しない', sitelib.is_pdf(b'<html>', 'text/html'), False)

    say('--- 文言の検出 ---')
    _disc = analyze('<html><body><p>※掲載イベントは状況により変更・中止されることもございます。</p></body></html>')
    chk('施設チラシの断り書き(変更・中止されることも) → 数えない',
        bool(_disc['strong'] or _disc['weak']), False)
    a = analyze(FIX_TEXT_NOTICE)
    chk('本文に中止告知 → 強い語', bool(a['strong']), True)
    b = analyze(FIX_WEAK)
    chk('雨天中止 → 強い語ではない', bool(b['strong']), False)
    # 2026-09-09 に方針を変えた。天候の条件文は数えない。
    # 「※雨天時は中止となる場合があります」で毎日鳴っていた
    chk('雨天中止は条件文なので弱い語でも数えない', bool(b['weak']), False)
    d = analyze(FIX_COND)
    chk('雨天時は中止となる場合 → 数えない', bool(d['strong'] or d['weak']), False)
    e = analyze(FIX_REAL_WEATHER)
    chk('悪天候のため中止しました → 拾う', bool(e['strong'] or e['weak']), True)
    f = analyze(FIX_VENDOR_CANCEL)
    chk('出展者1組の出展中止 → 数えない', bool(f['strong'] or f['weak']), False)
    c = analyze(FIX_PLAIN)
    chk('平常のページ → どちらも出ない', bool(c['strong'] or c['weak']), False)

    say('')
    say('--- 今日の日付は署名に入れない ---')
    import datetime as _dt
    _t = _dt.date(2026, 9, 9)
    # 実際の巡回は「その日の頁をその日の today で署名する」。
    # 昨日は昨日の日付が、今日は今日の日付が落ちるので署名は揃う。
    # 同じ today で別の日の頁を比べても意味がない(最初そう書いて外した)
    s1 = page_signature(FIX_TODAY_A, today=_t)
    s2 = page_signature(FIX_TODAY_B, today=_dt.date(2026, 9, 10))
    chk('今日の日付を出す頁 → 日をまたいでも署名は同じ', s1['text'], s2['text'])
    s3 = page_signature(FIX_DATE_CHANGED, today=_t)
    chk('開催日が変わった頁 → 署名は変わる', s1['text'] != s3['text'], True)

    say('\n--- 別の催し(例会など)の中止 ---')
    s1, _w1 = find_words(['( 1月、2月、5月の例会は開催が中止となりました )'])
    chk('例会の中止は強い語に数えない', s1, [])
    s2, _w2 = find_words(['第51回 日本シャボテン大会は開催を中止いたします'])
    chk('大会本体の中止は拾う', bool(s2), True)

    say('\n--- 施設の利用中止 (2026-10-05) ---')
    _s5, w5 = find_words(['駐車場 空いています ※休園日は利用不可 子供の森 利用中止 詳しくみる'])
    chk('施設の状況欄の「利用中止」は弱い語に数えない', w5, [])
    _s6, w6 = find_words(['サボテン・多肉植物展示会は中止します'])
    chk('催しの中止は弱い語で拾う', w6, ['中止'])

    say('\n--- 署名を主たる記事に絞る (2026-10-05) ---')
    _ev = {'slug': 'r', 'date': '2026-10-25', 'dateEnd': '2026-10-25'}
    _a1 = analyze(FIX_WP_ENTRY.replace('{news}', 'TALK OVER COFFEE FES'), _ev)
    _a2 = analyze(FIX_WP_ENTRY.replace('{news}', 'BOTANICA 10月営業時間変更'), _ev)
    chk('単独記事に開催日 → 記事に絞る', _a1['sigScope'], 'article')
    chk('新着欄の本文が変わっても本文の署名は同じ',
        _a1['signature']['text'] == _a2['signature']['text'], True)
    chk('新着欄のサムネイルが変わっても画像の署名は同じ',
        _a1['signature']['images'] == _a2['signature']['images'], True)
    _a3 = analyze(FIX_WP_ENTRY.replace('{news}', 'TALK OVER COFFEE FES')
                  .replace('10:00~16:00', '中止となりました'), _ev)
    chk('記事の本文が変われば本文の署名は変わる',
        _a1['signature']['text'] != _a3['signature']['text'], True)
    chk('記事の本文の中止は強い語で拾う', bool(_a3['strong']), True)
    _a4 = analyze(FIX_WP_ENTRY.replace('{news}', 'TALK OVER COFFEE FES')
                  .replace('roots_market.png"></head>', 'roots_cancel.png"></head>'), _ev)
    chk('og:image の差し替えは画像の署名に出る',
        _a1['signature']['images'] != _a4['signature']['images'], True)
    _a5 = analyze(FIX_WP_ENTRY.replace('{news}', 'ROOTS MARKET 中止'), _ev)
    chk('新着欄に出た中止の告知も語は拾う', bool(_a5['strong'] or _a5['weak']), True)
    _two = FIX_WP_ENTRY.replace('{news}', 'X').replace(
        '<aside>', '<article><p>別の記事 2026年10月25日</p></article><aside>')
    chk('記事が2つ以上の頁(一覧) → 絞らない', analyze(_two, _ev)['sigScope'], 'page')
    chk('記事に開催日が無い → 絞らない',
        analyze(FIX_WP_ENTRY.replace('{news}', 'X'),
                {'slug': 'q', 'date': '2026-11-03', 'dateEnd': '2026-11-03'})['sigScope'], 'page')
    chk('回が渡されない → 絞らない',
        analyze(FIX_WP_ENTRY.replace('{news}', 'X'))['sigScope'], 'page')

    say('\n--- 通販の注文のキャンセル ---')
    _s3, w3 = find_words(['エントリー受付後、ご注文は自動的にキャンセルされます。'
                          '※ご注文のキャンセルをもって、エントリー完了となります。'
                          '※キャンセル完了までにお時間(5分程度)'
                          '対象注文が「キャンセル」となっていることをご確認ください。'
                          '※キャンセルされていない場合は'])
    chk('入店抽選の注文キャンセルは弱い語に数えない', w3, [])
    _s4, w4 = find_words(['本イベントはキャンセルとなりました'])
    chk('イベント本体のキャンセルは弱い語で拾う', w4, ['キャンセル'])

    say('\n--- 画像だけの告知(文言では拾えないことの確認) ---')
    before = analyze(FIX_IMAGE_NOTICE_BEFORE)
    after = analyze(FIX_IMAGE_NOTICE_AFTER)
    chk('画像差し替えでは強い語は出ない', bool(after['strong']), False)
    chk('画像の署名は変わる',
        before['signature']['images'] != after['signature']['images'], True)
    chk('本文の署名は変わらない',
        before['signature']['text'] == after['signature']['text'], True)

    say('\n--- 出典がこの回を裏付けているか ---')
    ev_sep = {'slug': 'x', 'date': '2026-09-20', 'dateEnd': '2026-09-20'}
    w = analyze(FIX_WRONG_EDITION, ev_sep)
    chk('別の回の記事 → 開催日が出てこない', w['eventDateSeen'], False)
    chk('別の回の記事 → 散文で日付は名乗っている', w['datesNamed'] > 0, True)
    i = analyze(FIX_DATE_IN_IMAGE, ev_sep)
    chk('日付が画像の中だけ → 名乗り0(判定しない)', i['datesNamed'], 0)
    d = analyze(FIX_DOT_DATE, {'slug': 'y', 'date': '2026-10-10',
                               'dateEnd': '2026-10-11'})
    chk('2026.10.10 形式でも開催日は拾う', d['eventDateSeen'], True)
    chk('2026.10.10 形式は名乗りには数えない', d['datesNamed'], 0)
    # 2026-09-30: 魚町みらい広場の頁は数字と 年/月/日 を別々の span で
    # 装飾していて、タグを空白にすると「10 月 17 日」になり日付0件に見えていた
    sp = analyze('<p>日程：<span>2026</span><span>年</span><span>10</span>'
                 '<span>月</span><span>17</span><span>日（土）</span></p>',
                 {'slug': 'u', 'date': '2026-10-17', 'dateEnd': '2026-10-18'})
    chk('数字と月日が別の span でも開催日を拾う', sp['eventDateSeen'], True)
    chk('数字と月日が別の span でも名乗りに数える', sp['datesNamed'], 1)

    say('\n--- 開始日が頁の更新日から来ていないか ---')
    # 2026-09-12: 道の駅仁保の郷の告知は開催日を「9月19日（土）」1つしか
    # 書いていないのに、events.json は date=2026-09-02(頁の更新日) 〜
    # dateEnd=2026-09-19 の18日間になっていた。単日の回が18日間
    # 「開催中」として出ていた。9/19 は頁にあるので eventDateSeen は True になり、
    # source_page_wrong_edition では落ちない。更新日も「◯月◯日」なので
    # 「開始日が頁に無いか」でも落ちない。肩書を見るしかない。
    chk('更新日を拾う', meta_dates(FIX_ONE_DAY_PAGE), {(9, 2)})
    bad = analyze(FIX_ONE_DAY_PAGE, {'slug': 'z', 'date': '2026-09-02',
                                     'dateEnd': '2026-09-19'})
    chk('開始日が更新日と同じ → True', bad['startDateIsPageMeta'], True)
    chk('会期のどこかは出ている → eventDateSeen は True',
        bad['eventDateSeen'], True)
    good = analyze(FIX_ONE_DAY_PAGE, {'slug': 'z', 'date': '2026-09-19',
                                      'dateEnd': '2026-09-19'})
    chk('直した後 → False', good['startDateIsPageMeta'], False)
    span = analyze(FIX_SPAN_PAGE, {'slug': 'w', 'date': '2026-09-20',
                                   'dateEnd': '2026-09-22'})
    chk('更新日を持たない頁では鳴らない', span['startDateIsPageMeta'], False)
    g = analyze(FIX_WRONG_EDITION, {'slug': 'z', 'date': '2026-06-07',
                                    'dateEnd': '2026-06-07'})
    chk('同じ頁でも6月開催の回なら裏付けになる', g['eventDateSeen'], True)

    say('\n--- 巡回対象の絞り込み ---')
    today = '2026-09-08'
    evs = [
        {'slug': 'near', 'date': '2026-09-22', 'url': 'https://example.com/'},
        {'slug': 'past', 'date': '2026-09-01', 'url': 'https://example.com/'},
        {'slug': 'far', 'date': '2027-03-01', 'url': 'https://example.com/'},
        {'slug': 'ig', 'date': '2026-09-22',
         'url': 'https://www.instagram.com/p/xxx/'},
        {'slug': 'nourl', 'date': '2026-09-22', 'url': ''},
        {'slug': 'done', 'date': '2026-09-22', 'url': 'https://example.com/',
         'eventStatus': 'cancelled'},
    ]
    got = sorted(e.get('slug') for e, _ in watch_targets(evs, today))
    chk('対象は開催前・出典あり・SNS以外・未中止だけ', got, ['near'])

    say('\n結果: ' + ('すべて通過' if ok else '★失敗あり'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
