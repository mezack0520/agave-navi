#!/usr/bin/env python3
"""ig-organizer-watch.py — 主催者の Instagram の最新投稿を Business Discovery で取る。

使い方:
  IG_PAGE_TOKEN=... python3 scripts/ig-organizer-watch.py [--limit N]
  python3 scripts/ig-organizer-watch.py --self-test

何のためか(2026-09-23):
  当サイトの出典は大半が主催の Instagram だが、Instagram は未ログインだと
  本文が取れず、check-cancelled.py は SKIP_DOMAINS で最初から見ていない。
  つまり**Instagram で告知された回は、中止になっても誰も気づかない。**
  ブラウザで embed/captioned を叩く経路は人が居る時しか動かず、
  web_profile_info は 429 で止まる。
  Business Discovery は @agave_navi(プロアカウント)の権限で、相手がプロ
  アカウントならユーザー名だけで最新投稿の本文・日時・URLを返す。フォロー不要。

見張る主催(2026-09-23 に拡大):
  開催予定の回の主催と watch-sources.json の全IGアカウント(次回待ちのシリーズ・
  watch-seeds)。呼び出し上限に収めるため plan_fetch() の周期で分けて取る。
  以前は agave-event-update タスクが組み込みブラウザで同じアカウントを回っていた。

出すもの: organizer-posts.json
  results[username] = {ok, error, code, checkedOn, posts:[{timestamp, permalink, caption}]}
                      今回取らなかった主催は前回の結果を持ち越す
  signals.cancel    = 開催予定の回に対して、その主催の最近の投稿に中止・延期の
                      言い切りがあり、かつ投稿がその回を指している(日付か名前)もの
  signals.unlisted  = 主催の最近の投稿に先の日付が出ているのに、その主催の
                      掲載済みの回のどれとも日付が合わないもの(取りこぼし候補)
  errors            = 取れなかった主催(個人アカウント・非公開・名前違い)
  同じ呼び出しの原寸画像から、アイキャッチの候補を staging/eyecatch/ に置く
  (eyecatchlib.py。採否は人が apply-eyecatch.py で書く)

判定の語彙は check-cancelled.py と共有する(CANCEL_WORDS / drop_conditional)。
写しを置かない。雨天中止の条件文や出展者1組の取り止めで鳴らないための
除外規則は向こうで育っている。
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import sitelib  # noqa: E402
import iglib  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'organizer-posts.json')

WATCH_HORIZON_DAYS = 120      # これより先の回の主催は見ない
POSTS_PER_USER = 12
CANCEL_LOOKBACK = 45    # 中止の言い切りを探す投稿の古さ
UNLISTED_LOOKBACK = 14  # 取りこぼし候補を探す投稿の古さ
UNLISTED_AHEAD = 150    # 投稿に出た日付が今日から何日先までなら候補にするか
# 1回の実行で叩く上限。アプリの呼び出し上限(ほぼ200回/時)の内側に置く
BUDGET = 180
# これより古い持ち越し結果からは信号を出さない
FRESH_DAYS = 3


def _load_cancel_rules():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'check-cancelled.py')
    spec = importlib.util.spec_from_file_location('check_cancelled', p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.CANCEL_WORDS, m.drop_conditional


CANCEL_WORDS, drop_conditional = _load_cancel_rules()


def norm(s):
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s or '')).strip()


_MD = re.compile(r'(?<!\d)(\d{1,2})\s*(?:月\s*(\d{1,2})\s*日?|/\s*(\d{1,2})(?!\d))')


_DEADLINE = re.compile(r'締め?切|〆切|まで(?:募集|受付|応募)|応募')


def month_days(text):
    """本文に出る (月, 日)。『9月26日』『9/26』。年やURLの数字は拾わない"""
    out = set()
    for m in _MD.finditer(text):
        # 「募集は9月30日で締め切ります」のような締切日は開催日ではない
        if _DEADLINE.search(text[m.end():m.end() + 12]):
            continue
        mo = int(m.group(1))
        d = int(m.group(2) or m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            out.add((mo, d))
    return out


def event_md(e):
    s = set()
    for k in ('date', 'dateEnd'):
        v = e.get(k) or ''
        if re.fullmatch(r'\d{4}-\d{2}-\d{2}', v):
            s.add((int(v[5:7]), int(v[8:10])))
    return s


def name_key(e):
    """投稿がその回を名前で指しているかを見る鍵。数字と記号を落とした先頭6字"""
    n = norm(e.get('name') or '')
    n = re.sub(r'[0-9第回vol.Vol\s()（）【】「」・\-–—!！?？#＃]+', '', n)
    return n[:6]


def upcoming_by_org(events, today):
    """開催予定の回を主催ごとに束ねる"""
    lim = (today + timedelta(days=WATCH_HORIZON_DAYS)).strftime('%Y-%m-%d')
    t = today.strftime('%Y-%m-%d')
    by = {}
    for e in events:
        u = (e.get('organizerIg') or '').strip().lstrip('@')
        if not u or sitelib.is_cancelled(e):
            continue
        end = e.get('dateEnd') or e.get('date') or ''
        if not end or end < t or (e.get('date') or '') > lim:
            continue
        by.setdefault(u, []).append(e)
    return by


_IG_HANDLE = re.compile(r'instagram\.com/([A-Za-z0-9_.]+)/?(?:$|[?#])')


def all_by_org(events):
    """主催ごとの回。organizerIg に加えて、出典URLがその人のプロフィールの回も含める。

    organizerIg が空で url だけがプロフィールを指す回が多い
    (plant to new home は url=@bwoocraftplants / organizerIg 無し)。
    organizerIg だけで束ねると、その人の投稿に出る掲載済みの日付が
    「当サイトに無い日付」として出た(2026-09-24)。
    """
    by = {}
    for e in events:
        hs = set()
        u = (e.get('organizerIg') or '').strip().lstrip('@').lower()
        if u:
            hs.add(u)
        for k in ('url', 'sourceUrl'):
            m = _IG_HANDLE.search(e.get(k) or '')
            if m and m.group(1).lower() not in ('p', 'reel', 'tv', 'explore', 'stories'):
                hs.add(m.group(1).lower())
        for h in hs:
            by.setdefault(h, []).append(e)
    return by


def known_elsewhere(cap, iso, day_index, rejected_by_day):
    """その日付の話が、別の主催で掲載済みの回か、見送り済みの回を指しているか。

    出店者やコラボ相手の投稿には、主催が別の回の日付が出る(叢宴の出店者が
    書いた10/3は、ぼっち植堂主催の回として掲載済みだった)。
    その日の回の名前か会場が本文に出ていれば既知とみなす。
    """
    c = norm(cap).replace(' ', '').lower()
    for e in day_index.get(iso, []):
        k = name_key(e).lower()
        v = norm(e.get('venue') or '').replace(' ', '').lower()
        if (k and len(k) >= 3 and k in c) or (v and len(v) >= 4 and v[:8] in c):
            return True
        # 主催のアカウントに触れていれば、その主催の回の話(叢宴の出店者は
        # 「主催のぼっちさん @bocchi_syokudou」と書き、会場名は表記が揺れていた)
        # Graph API の本文はメンションの @ が落ちて届く(「主催のぼっちさん bocchi_syokudou」)。
        # @ を要求せず、ハンドルが語として出ているかで見る
        org = (e.get('organizerIg') or '').strip().lstrip('@').lower()
        if org and len(org) >= 4 and re.search(r'(?<![a-z0-9_.])' + re.escape(org) + r'(?![a-z0-9_])',
                                               norm(cap).lower()):
            return True
    for r in rejected_by_day.get(iso, []):
        for nm in [r.get('name') or ''] + list(r.get('aliases') or []):
            k = norm(re.sub(r'\s*\(.*$', '', nm)).replace(' ', '').lower()[:6]
            if k and len(k) >= 3 and k in c:
                return True
    return False


def day_indexes(events, rejected_items):
    """日付 → その日にかかる回 / 見送り"""
    di, ri = {}, {}
    for e in events:
        try:
            a = datetime.strptime(e['date'], '%Y-%m-%d')
            b = datetime.strptime(e.get('dateEnd') or e['date'], '%Y-%m-%d')
        except (KeyError, ValueError):
            continue
        d = a
        while d <= b and (d - a).days <= 62:
            di.setdefault(d.strftime('%Y-%m-%d'), []).append(e)
            d += timedelta(days=1)
    for r in rejected_items:
        if r.get('eventDate'):
            ri.setdefault(r['eventDate'], []).append(r)
    return di, ri


def analyze_posts(username, posts, org_events, all_org_events, today, day_index=None, rejected_by_day=None):
    """(cancel信号, unlisted候補) を返す"""
    cancel, unlisted = [], []
    known_md = set()
    for e in all_org_events:
        known_md |= event_md(e)
        # 会期の途中の日も既知として扱う(長期開催の「本日も開催」で鳴らさない)
        try:
            a = datetime.strptime(e['date'], '%Y-%m-%d')
            b = datetime.strptime(e.get('dateEnd') or e['date'], '%Y-%m-%d')
            if (b - a).days <= 62:
                d = a
                while d <= b:
                    known_md.add((d.month, d.day))
                    d += timedelta(days=1)
        except (KeyError, ValueError):
            pass
    for p in posts:
        ts = p.get('timestamp') or ''
        try:
            pdt = datetime.strptime(ts[:10], '%Y-%m-%d')
        except ValueError:
            continue
        age = (today - pdt).days
        cap = norm(p.get('caption'))
        if not cap:
            continue
        mds = month_days(cap)
        if age <= CANCEL_LOOKBACK:
            blob = drop_conditional(cap)
            words = sorted({w for w in CANCEL_WORDS if w in blob})
            if words:
                for e in org_events:
                    hit_date = bool(event_md(e) & mds)
                    k = name_key(e)
                    hit_name = bool(k) and k in norm(cap).replace(' ', '')
                    # 投稿がこの回を指していると言えるときだけ鳴らす。
                    # 主催が年に何度も開く場合、別の回の中止で全回が鳴るのを防ぐ
                    if hit_date or hit_name:
                        cancel.append({'slug': e['slug'], 'date': e['date'],
                                       'username': username, 'words': words,
                                       'permalink': p.get('permalink'),
                                       'postedOn': ts[:10],
                                       'by': 'date' if hit_date else 'name'})
        if age <= UNLISTED_LOOKBACK and _looks_like_own_announcement(cap):
            fut = []
            for (mo, d) in sorted(mds - known_md):
                y = today.year if (mo, d) >= (today.month, today.day) else today.year + 1
                try:
                    cand = datetime(y, mo, d)
                except ValueError:
                    continue
                if 0 <= (cand - today).days <= UNLISTED_AHEAD:
                    iso = cand.strftime('%Y-%m-%d')
                    if known_elsewhere(cap, iso, day_index or {}, rejected_by_day or {}):
                        continue
                    fut.append(iso)
            if fut:
                unlisted.append({'username': username, 'dates': fut,
                                 'permalink': p.get('permalink'),
                                 'postedOn': ts[:10],
                                 'excerpt': cap[:120]})
    # 取りこぼし候補は主催ごとに1件へ畳む(同じ日付を何投稿も繰り返すため)
    if unlisted:
        dates = sorted({d for u in unlisted for d in u['dates']})
        first = unlisted[0]
        unlisted = [{'username': username, 'dates': dates,
                     'permalink': first['permalink'], 'postedOn': first['postedOn'],
                     'excerpt': first['excerpt']}]
    # 同じ回に同じ投稿で複数回鳴らさない
    seen, uniq = set(), []
    for c in cancel:
        k = (c['slug'], c['permalink'])
        if k not in seen:
            seen.add(k)
            uniq.append(c)
    return uniq, unlisted


# 取りこぼし候補は「主催が自分の催しを告知している投稿」に限る。
# 初回(2026-09-23)は40件出て、大半が別イベントへの出店告知・ワークショップ・
# 株の紹介文・リポストだった。出店側の言い回しを先に落とし、開催の名乗りを要る
_VENDOR_SIDE = ('出店のお知らせ', 'に出店', '出店します', '出店させて', '出店致します',
                '出店いたします', '参加させて', '参加します', '出店イベント', '出展します',
                '次の出店', '出店は', 'Repost', 'repost', 'リポスト', '出店者様募集', '出店者募集', '出展者募集')
_OWN_EVENT = ('開催', '日時', '日程', '会場')
# 主催が工務店や商業施設だと植物と無関係の催し(住宅展示会など)も拾うため
_PLANT_WORDS = ('植物', 'アガベ', '塊根', '多肉', 'サボテン', '園芸', '植木', 'グリーン',
                'ボタニカル', 'プランツ', 'plant', 'Plant', 'PLANT', '観葉', '盆栽', '苗')


def _looks_like_own_announcement(cap):
    if any(w in cap for w in _VENDOR_SIDE):
        return False
    if not any(w in cap for w in _PLANT_WORDS):
        return False
    return sum(1 for w in _OWN_EVENT if w in cap) >= 2




def fetch_posts(ig_id, username, token):
    """最新投稿。image は原寸画像のURL(署名付きで期限があるので保存しない)"""
    bd, err = iglib.business_discovery(
        ig_id, username, token,
        f'username,media.limit({POSTS_PER_USER})'
        '{caption,timestamp,permalink,media_type,media_url,thumbnail_url}')
    if err:
        return None, err
    media = (bd.get('media') or {}).get('data') or []
    posts = [{'timestamp': m.get('timestamp'), 'permalink': m.get('permalink'),
              'caption': (m.get('caption') or '')[:800],
              'image': (m.get('thumbnail_url') if m.get('media_type') == 'VIDEO'
                        else m.get('media_url'))} for m in media]
    return posts, None


def _days(a, b):
    try:
        return (datetime.strptime(a, '%Y-%m-%d') - datetime.strptime(b, '%Y-%m-%d')).days
    except (TypeError, ValueError):
        return 10 ** 6


def is_personal(r):
    """Business Discovery で読めない相手(個人アカウント・名前違い)。毎日叩いても変わらない"""
    if not r or r.get('ok'):
        return False
    msg = r.get('error') or ''
    return r.get('code') == 110 or '見つかりません' in msg or 'Cannot find User' in msg


def plan_fetch(tg, watch_handles, prev, today_s, budget):
    """今回取る主催を決める。(今回取る, 見張り対象の全体)。

    見張り対象は開催予定の回の主催(tg)と watch-sources.json の全IGアカウント。
    1回の呼び出し上限(ほぼ200回/時)に収めるため、全部を毎日は取らない。
      開催予定の回の主催  毎日(中止の見張り)
      それ以外            2日に1回(次回開催の告知待ち)
      読めない相手        7日に1回(プロアカウントに切り替わることがある)
    """
    accounts = set(tg) | set(watch_handles)
    due = []
    for u in accounts:
        r = prev.get(u)
        age = _days(today_s, (r or {}).get('checkedOn'))
        need = 7 if is_personal(r) else (1 if u in tg else 2)
        if age >= need:
            due.append((0 if u in tg else 1, -min(age, 999), u))
    due.sort()
    return [u for _, _, u in due][:budget], accounts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='今回取る主催の数を絞る(試験用)')
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        sys.exit(0 if self_test() else 1)

    token = os.environ.get('IG_PAGE_TOKEN', '').strip()
    if not token:
        sys.exit('IG_PAGE_TOKEN が無い')
    today = datetime.strptime(sitelib.today_jst(), '%Y-%m-%d')
    today_s = today.strftime('%Y-%m-%d')
    with open(os.path.join(REPO, 'events.json'), encoding='utf-8') as f:
        events = json.load(f)
    tg = upcoming_by_org(events, today)
    allorg = all_by_org(events)
    try:
        with open(os.path.join(REPO, 'rejected-events.json'), encoding='utf-8') as f:
            _rej = json.load(f).get('items') or []
    except (OSError, ValueError):
        _rej = []
    day_index, rejected_by_day = day_indexes(events, _rej)
    try:
        with open(os.path.join(REPO, 'watch-sources.json'), encoding='utf-8') as f:
            watch = [x['handle'] for x in json.load(f).get('igAccounts') or [] if x.get('handle')]
    except (OSError, ValueError, KeyError):
        watch = []
    try:
        with open(OUT, encoding='utf-8') as f:
            prev = json.load(f).get('results') or {}
    except (OSError, ValueError):
        prev = {}
    names, accounts = plan_fetch(tg, watch, prev, today_s, a.limit or BUDGET)

    out = {'_note': ('主催者の Instagram の最新投稿。scripts/ig-organizer-watch.py が毎日書く。'
                     '全アカウントを毎日は取らない(plan_fetch() の周期)。今回取らなかった主催は'
                     '前回の結果を checkedOn つきで持ち越す。signals は取得から'
                     f'{FRESH_DAYS}日以内の結果で出す。errors の多くは相手が個人アカウントで、異常ではない'),
           'checkedOn': today_s,
           'stats': {'accounts': len(accounts), 'targets': len(names), 'fetched': 0},
           'results': {u: r for u, r in prev.items() if u in accounts},
           'signals': {'cancel': [], 'unlisted': []}, 'errors': []}

    me, err = iglib.call('GET', 'me', token, fields='instagram_business_account')
    ig_id = ((me or {}).get('instagram_business_account') or {}).get('id')
    if not ig_id:
        out['fatal'] = f'Instagram アカウントを解決できない: {err}'
        _write(out)
        sys.exit(out['fatal'])

    stopped = None
    fresh = {}
    fresh_err10 = 0
    for i, u in enumerate(names):
        posts, err = fetch_posts(ig_id, u, token)
        if err:
            code = err.get('code')
            msg = (err.get('error_user_msg') or err.get('message') or '')[:160]
            if code in iglib.RATE_CODES:
                stopped = f'{u} でレート制限({code})。残り {len(names) - i} 件は次回'
                break
            # 権限不足(#10)は相手によらず全件で同じ結果になる。最初の3件が
            # そろって #10 なら打ち切って fatal にする。2026-09-23 の初回は
            # instagram_manage_insights が無く、102件すべて #10 で回り切っていた
            if code == 10:
                fresh_err10 += 1
                if i == 2 and fresh_err10 == 3:
                    out['fatal'] = ('権限不足(#10)。Business Discovery には '
                                    'instagram_basic / instagram_manage_insights / '
                                    'pages_read_engagement を付けたトークンが要る: ' + msg)
                    break
            out['results'][u] = {'ok': False, 'error': msg, 'code': code, 'checkedOn': today_s}
        else:
            fresh[u] = posts
            out['results'][u] = {'ok': True, 'checkedOn': today_s,
                                 'posts': [{k: p[k] for k in ('timestamp', 'permalink', 'caption')}
                                           for p in posts]}
            out['stats']['fetched'] += 1
        time.sleep(1.0)
    if stopped:
        out['stopped'] = stopped

    ok_recent = 0
    for u, r in sorted(out['results'].items()):
        if not r.get('ok'):
            if not is_personal(r) or r.get('checkedOn') == today_s:
                out['errors'].append(f'@{u}: {r.get("error")}')
            continue
        if _days(today_s, r.get('checkedOn')) > FRESH_DAYS:
            continue
        ok_recent += 1
        c, n = analyze_posts(u, r['posts'], tg.get(u, []), allorg.get(u.lower(), []), today,
                       day_index, rejected_by_day)
        out['signals']['cancel'] += c
        out['signals']['unlisted'] += n
    out['stats']['readable'] = ok_recent
    out['stats']['personal'] = sum(1 for r in out['results'].values() if is_personal(r))
    out['stats']['neverChecked'] = len(accounts - set(out['results']))

    # 同じ呼び出しで取れた原寸画像から、アイキャッチの候補を staging に置く
    try:
        import eyecatchlib
        out['stats']['eyecatchStaged'] = eyecatchlib.stage_candidates(events, fresh, today_s)
    except Exception as ex:  # noqa: BLE001  候補作りの失敗で見張りを止めない
        out['eyecatchError'] = f'{type(ex).__name__}: {ex}'[:200]

    _write(out)
    s = out['stats']
    print(f'見張り {s["accounts"]} 件 / 今回 {s["targets"]} 件中 {s["fetched"]} 件取得 / '
          f'読める {s["readable"]} / 個人 {s["personal"]} / 未取得 {s["neverChecked"]} / '
          f'中止の兆候 {len(out["signals"]["cancel"])} / '
          f'未掲載の日付 {len(out["signals"]["unlisted"])} / '
          f'アイキャッチ候補 +{s.get("eyecatchStaged", 0)}'
          + (f' / {stopped}' if stopped else ''))


def _write(out):
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)


def self_test():
    ok = True

    def chk(label, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print(f'NG {label}: {got!r} != {want!r}')

    today = datetime(2026, 9, 23)
    ev = {'slug': 'x-2026-10', 'name': '第3回 テストプランツ市', 'date': '2026-10-18',
          'dateEnd': '2026-10-18'}
    other = {'slug': 'y-2026-12', 'name': '冬のテスト市', 'date': '2026-12-06',
             'dateEnd': '2026-12-06'}
    chk('月日 9月26日', month_days('9月26日(土)開催'), {(9, 26)})
    chk('月日 10/18', month_days('10/18 10:00〜'), {(10, 18)})
    chk('月日 年は拾わない', month_days('2026年'), set())
    # 日付で指した中止は鳴る
    p = [{'timestamp': '2026-09-20T01:00:00+0000', 'permalink': 'u1',
          'caption': '10月18日のテストプランツ市は台風のため開催中止となりました'}]
    c, _ = analyze_posts('org', p, [ev, other], [ev, other], today)
    chk('日付で指した中止', [x['slug'] for x in c], ['x-2026-10'])
    # 雨天中止の条件文は鳴らない
    p = [{'timestamp': '2026-09-20T01:00:00+0000', 'permalink': 'u2',
          'caption': '10/18開催。雨天中止となる場合があります'}]
    c, _ = analyze_posts('org', p, [ev], [ev], today)
    chk('条件文は鳴らない', c, [])
    # 別の回を指した中止は、この回では鳴らない
    p = [{'timestamp': '2026-09-20T01:00:00+0000', 'permalink': 'u3',
          'caption': '11月3日のマルシェは中止となりました'}]
    c, _ = analyze_posts('org', p, [ev], [ev], today)
    chk('別の回の中止', c, [])
    # 荒天時の連絡手段を述べた注意書きは鳴らない(福岡グリーンパーティー第7回)
    p = [{'timestamp': '2026-09-20T01:00:00+0000', 'permalink': 'u2b',
          'caption': '10月18日。雨天でも開催致します。(荒天の場合はインスタグラムにて中止のお知らせを致します)'}]
    c, _ = analyze_posts('org', p, [ev], [ev], today)
    chk('荒天時の予告は鳴らない', c, [])
    chk('締切日は日付に数えない', month_days('募集は9月30日で締め切ります。12/26開催'), {(12, 26)})
    # 別イベントへの出店告知は取りこぼし候補にしない
    p = [{'timestamp': '2026-09-21T01:00:00+0000', 'permalink': 'u4b',
          'caption': 'イベント出店のお知らせ 11/22 開催 会場はどこそこ'}]
    _, n = analyze_posts('org', p, [ev], [ev], today)
    chk('出店告知は候補にしない', n, [])
    # 掲載済みの日付は取りこぼし候補にしない。未掲載の先の日付は候補
    p = [{'timestamp': '2026-09-21T01:00:00+0000', 'permalink': 'u4',
          'caption': '【植物市 開催決定】日程 10/18と11/22 会場 市民ホール'}]
    _, n = analyze_posts('org', p, [ev], [ev], today)
    chk('未掲載の日付', [x['dates'] for x in n], [['2026-11-22']])
    # 古い投稿は取りこぼし候補にしない
    p = [{'timestamp': '2026-08-01T01:00:00+0000', 'permalink': 'u5',
          'caption': '【植物市 開催決定】日程 11/22 会場 市民ホール'}]
    _, n = analyze_posts('org', p, [ev], [ev], today)
    chk('古い投稿', n, [])

    # 別の主催で掲載済みの回の日付は、名前か会場か主催アカウントが出ていれば候補にしない
    di = {'2026-10-03': [{'slug': 'b', 'name': '秋のボタニカルマーケット', 'venue': '富士中央公園 芝生広場',
                          'organizerIg': 'bocchi_syokudou', 'date': '2026-10-03'}]}
    chk('主催アカウントで既知', known_elsewhere('来月10/3に開催 主催のぼっちさん @bocchi_syokudou', '2026-10-03', di, {}), True)
    chk('@の落ちたメンションでも既知', known_elsewhere('主催のぼっちさん bocchi_syokudou 10/3', '2026-10-03', di, {}), True)
    chk('無関係なら未知', known_elsewhere('10/3に別の催し', '2026-10-03', di, {}), False)
    chk('見送り済みは既知', known_elsewhere('花と緑のフラワーオークション 9/27', '2026-09-27', {},
                                     {'2026-09-27': [{'name': '花と緑のフラワーオークション (2026-09-27・福岡)'}]}), True)
    # 周期: 開催予定の主催は毎日、他は2日、読めない相手は7日
    prev = {'up': {'ok': True, 'checkedOn': '2026-09-22'},
            'other1': {'ok': True, 'checkedOn': '2026-09-22'},
            'other2': {'ok': True, 'checkedOn': '2026-09-21'},
            'priv': {'ok': False, 'error': 'ユーザーネームがprivのユーザーが見つかりません',
                     'checkedOn': '2026-09-20'},
            'gone': {'ok': True, 'checkedOn': '2026-09-01'}}
    names, accts = plan_fetch({'up': [ev]}, ['other1', 'other2', 'priv', 'new'], prev, '2026-09-23', 50)
    chk('今回取る主催', names, ['up', 'new', 'other2'])
    chk('見張り対象から外れた主催は持たない', 'gone' in accts, False)
    names, _ = plan_fetch({'up': [ev]}, ['other1', 'new'], prev, '2026-09-23', 1)
    chk('上限では開催予定の主催が先', names, ['up'])

    # アイキャッチ候補の投稿選び
    import eyecatchlib as ec
    e2 = {'slug': 's', 'name': '第3回 テストプランツ市', 'date': '2026-10-18'}
    posts = [{'permalink': 'https://www.instagram.com/p/A1/', 'timestamp': '2026-09-20',
              'caption': '出店者募集 テストプランツ市 10/18', 'image': 'x'},
             {'permalink': 'https://www.instagram.com/p/B2/', 'timestamp': '2026-09-19',
              'caption': '今日の植物', 'image': 'x'},
             {'permalink': 'https://www.instagram.com/p/C3/', 'timestamp': '2026-09-18',
              'caption': 'テストプランツ市 10月18日 開催', 'image': 'x'}]
    got, why = ec.pick_post(e2, posts)
    chk('募集投稿を避けて告知を採る', (got or {}).get('permalink'), 'https://www.instagram.com/p/C3/')
    got, _ = ec.pick_post(e2, posts, ['https://www.instagram.com/p/C3/'])
    chk('不採用にした投稿は出さない', got, None)
    got, why = ec.pick_post(dict(e2, url='https://www.instagram.com/p/B2/'), posts)
    chk('出典の投稿があればそれ', ((got or {}).get('permalink'), (why or {}).get('by')),
        ('https://www.instagram.com/p/B2/', 'sourcePost'))
    got, _ = ec.pick_post(dict(e2, date='2026-09-01'), posts)
    chk('会期後の投稿は採らない', got, None)
    print('self-test', 'OK' if ok else 'NG')
    return ok


if __name__ == '__main__':
    main()
