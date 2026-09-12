#!/usr/bin/env python3
"""sitelib.py — サイト共通ユーティリティ(単一情報源)。

全ジェネレータ(build-detail-pages / generate-landing-pages / build-guides /
generate_sitemap / guides_content の動的記事)がここを import する。
ヘッダー・フッター・スラッグ・日付整形・エスケープを一元化し、
ページ間の不一致(過去に404フッター乖離で発生)を構造的に防ぐ。
"""
import re
import unicodedata
import hashlib
from datetime import datetime, date, timezone, timedelta
import os
import json

# --- 定数 ---
DOMAIN = 'https://agave-navi.com'
DOMAIN_HOST = 'agave-navi.com'      # スキーム無しが要る場所(iCal の UID 等)
JST = timezone(timedelta(hours=9))
CSS_VERSION = '20260910b'
JS_VERSION = '20260910b'
ADSENSE_CLIENT = 'ca-pub-0790348660030345'
GA_ID = 'G-NKY8V1H8HY'

WEEKDAYS_JA = ['月', '火', '水', '木', '金', '土', '日']

# Instagram の投稿URL。1グループ目が投稿ID。
# fetch-event-images と list-missing-eyecatch が別々に持っていて、
# 片方は ID を取らない版だった(2026-09-10 に統合)。
IG_POST_RE = re.compile(
    r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)')

# 「会場」として意味をなさない曖昧値(venueページ・同会場セクションの対象外)
# 都道府県名そのものは会場名ではないので全県ぶんを下で追加する(2026-08-12)。
# 従来は東京・大阪・名古屋だけを列挙しており、venue="岩手"/"広島"/"和歌山" の回が
# 会場名として扱われ、地図が県全体を指し JSON-LD の Place.name も県名になっていた。
VAGUE_VENUES = {'東京', '東京都内', '都内', '大阪', '名古屋', '会場未定', '未定', '調整中'}

PREF_ROMAJI = {
    '北海道':'hokkaido','青森':'aomori','岩手':'iwate','宮城':'miyagi','秋田':'akita',
    '山形':'yamagata','福島':'fukushima','茨城':'ibaraki','栃木':'tochigi','群馬':'gunma',
    '埼玉':'saitama','千葉':'chiba','東京':'tokyo','神奈川':'kanagawa',
    '新潟':'niigata','富山':'toyama','石川':'ishikawa','福井':'fukui',
    '山梨':'yamanashi','長野':'nagano','岐阜':'gifu','静岡':'shizuoka','愛知':'aichi','三重':'mie',
    '滋賀':'shiga','京都':'kyoto','大阪':'osaka','兵庫':'hyogo','奈良':'nara','和歌山':'wakayama',
    '鳥取':'tottori','島根':'shimane','岡山':'okayama','広島':'hiroshima','山口':'yamaguchi',
    '徳島':'tokushima','香川':'kagawa','愛媛':'ehime','高知':'kochi',
    '福岡':'fukuoka','佐賀':'saga','長崎':'nagasaki','熊本':'kumamoto',
    '大分':'oita','宮崎':'miyazaki','鹿児島':'kagoshima','沖縄':'okinawa',
}
REGION_ROMAJI = {'北海道':'hokkaido','東北':'tohoku','関東':'kanto','北陸':'hokuriku',
                 '東海':'tokai','関西':'kansai','中国':'chugoku','四国':'shikoku','九州':'kyushu'}

# 都道府県 → 地域。サイトの地域分類の単一情報源。
# 各スクリプトが独自に持っていたため沖縄(九州/沖縄)と山梨・長野(北陸/中部)で定義が割れ、
# REGION_ROMAJI に無い地域名がハッシュURLの頁を生む事故が起きた(2026-07-31に統合)。
# 沖縄は九州に含める。中部は使わない(山梨・長野は北陸)。
PREF_TO_REGION = {
    '北海道': '北海道',
    '青森': '東北', '岩手': '東北', '宮城': '東北', '秋田': '東北', '山形': '東北', '福島': '東北',
    '茨城': '関東', '栃木': '関東', '群馬': '関東', '埼玉': '関東', '千葉': '関東',
    '東京': '関東', '神奈川': '関東',
    '新潟': '北陸', '富山': '北陸', '石川': '北陸', '福井': '北陸', '山梨': '北陸', '長野': '北陸',
    '岐阜': '東海', '静岡': '東海', '愛知': '東海', '三重': '東海',
    '滋賀': '関西', '京都': '関西', '大阪': '関西', '兵庫': '関西', '奈良': '関西', '和歌山': '関西',
    '鳥取': '中国', '島根': '中国', '岡山': '中国', '広島': '中国', '山口': '中国',
    '徳島': '四国', '香川': '四国', '愛媛': '四国', '高知': '四国',
    '福岡': '九州', '佐賀': '九州', '長崎': '九州', '熊本': '九州', '大分': '九州',
    '宮崎': '九州', '鹿児島': '九州', '沖縄': '九州',
}


# 都道府県名そのもの(短縮形・接尾辞付きの両方)を曖昧値に加える。
# PREF_ROMAJI が定義済みの位置でないと組み立てられないためここで足す。
VAGUE_VENUES |= set(PREF_ROMAJI)
VAGUE_VENUES |= {p if p == '北海道'
                 else p + '都' if p == '東京'
                 else p + '府' if p in ('大阪', '京都')
                 else p + '県'
                 for p in PREF_ROMAJI}


def pref_to_region(pref):
    """都道府県名から地域を返す。「京都府」「東京都」等の接尾辞も受ける。"""
    p = (pref or '').strip()
    if p in PREF_TO_REGION:
        return PREF_TO_REGION[p]
    for suf in ('都', '道', '府', '県'):
        if p.endswith(suf) and p[:-1] in PREF_TO_REGION:
            return PREF_TO_REGION[p[:-1]]
    return None
TAG_ROMAJI = {'即売会':'sokubaikai','マルシェ':'marche','大型':'big','展示会':'tenjikai',
              'ブロメリア':'bromelia','珍奇植物':'chinki','多肉':'tanniku',
              'コーデックス':'caudex','アガベ':'agave',
              '塊根植物':'kaikon','多肉植物':'succulent','サボテン':'cactus',
              'ビカクシダ':'platycerium','アロイド':'aroid','着生植物':'epiphyte',
              'ナイトマーケット':'night-market'}
# キーは venue_key() を通した形(NFKC・末尾の括弧書き除去・空白除去)で持つ。
# 生の表記で持つと、同じ会場でも空白や住所の有無で引けなくなる。
# 正規化は _VENUE_ROMAJI_RAW の定義直後にまとめてかける。
# 'サンシャインシティ' は削除(2026-08-21)。実データの location は
# 「サンシャインシティ文化会館ビル 2階 展示ホールD-1〜4」等で、この完全一致キーに
# 当たる回が無く、頁が立たない死んだ対応だった(audit venue_romaji_unused が検出)。
_VENUE_ROMAJI_RAW = {'五反田TOCビル 13階':'gotanda-toc',
                '久屋大通庭園フラリエ':'flarie','研究学園駅前公園（つくば市）':'kenkyu-gakuen-park',
                '千住本氷川神社':'senju-hikawa-jinja',
                # 掲載3件以上の会場だけローマ字URLにする(2026-08-20)。
                # ここに足すと既存URLが変わるので、2件の会場は据え置く。
                # 2件は増減しやすく、増えるたびにURLが変わるのを避ける。
                'オリナス錦糸町':'olinas-kinshicho',
                'さくら植物園':'sakura-shokubutsuen',
                'フィールド妙高':'field-myoko'}

# ローマ字URLに切り替える掲載件数のしきい値。audit がこの値で候補を出す。
VENUE_ROMAJI_MIN_EVENTS = 3

# 会場ページの旧URL → 宛先の会場名。スラッグを変えたら必ずここに残す。
# 値は会場名。宛先のスラッグが将来また変わっても venue_slug() で追随する。
# None は宛先なし(曖昧な会場名で頁が立つべきでなかったもの)で /venue/ へ送る。
# GitHub Pages はサーバ側リダイレクトを持てないので、
# generate-landing-pages.py が meta refresh + canonical の中継頁を出す。
_VENUE_REDIRECTS_RAW = {
    # 2026-08-20 ハッシュ → ローマ字
    'v-5d0f0de9': 'オリナス錦糸町',
    'v-98e5c913': 'さくら植物園',
    'v-d7fa600c': 'フィールド妙高',
    # 2026-08-20 スラッグ衝突の解消で消えた旧URL
    'v-0992a535': 'フィールド妙高',
    '4':          '町田パリオ 4階',
    '1028-2':     'リサイクルショップ虹風船 館林店 駐車場',
    # 曖昧な会場名で立っていた頁(宛先なし)
    'v-4f33267b': None,
    'v-5abbdd6f': None,
    'v-707ba17c': None,
    'v-af503a5c': None,
}

# --- 基本ユーティリティ ---

def now_jst():
    return datetime.now(JST)

def today_jst():
    """YYYY-MM-DD (JST)"""
    return now_jst().strftime('%Y-%m-%d')

def html_escape(text):
    return ((text or '')
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))

def slug_hash(slug):
    """slugから安定したハッシュ値(バリアント分散用)"""
    return sum(ord(c) for c in (slug or ''))

def safe_slug(s, kind='gen'):
    """日本語名から URL スラッグを作る。

    NFKD は日本語をほぼ全部落とすので、残るのは名前に紛れていた
    半角英数字だけになる。「町田パリオ 4階」→ 4、
    「…（群馬県館林市野辺町1028-2）」→ 1028-2 のような残渣は、
    (1) URL として何も意味を伝えず、
    (2) 別の会場と衝突して片方のページを黙って上書きする
    (2026-08-20 時点で 1 / 1f / 2 / 2f / i / taut の6組が衝突していた)。
    英字3文字以上の連なりが無い残渣は名前として使えないと見なし、
    元文字列のハッシュに落として一意性を優先する。
    """
    if not s: return ''
    nfkd = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', nfkd).strip('-')[:50]
    h = hashlib.md5(s.encode('utf-8')).hexdigest()
    if not slug or not re.search(r'[a-z]{3}', slug):
        return f'{kind}-{h[:8]}'
    if re.search(r'[^\x00-\x7f]', s):
        # 残渣は元の名前の一部でしかない。「ABCハウジングウェルビーみのお」→ abc、
        # 「セラミックパークMINO」→ mino のように、無関係な会場と同じ綴りになる。
        # ハッシュを足して、別の名前が同じURLに書かれないようにする。
        return f'{slug}-{h[:4]}'
    return slug

def pref_slug(p): return PREF_ROMAJI.get(p) or safe_slug(p, 'pref')
def region_slug(r): return REGION_ROMAJI.get(r) or safe_slug(r, 'region')
def tag_slug(t): return TAG_ROMAJI.get(t) or safe_slug(t, 'tag')
def venue_slug(v):
    v = venue_key(v)
    return VENUE_ROMAJI.get(v) or safe_slug(v, 'v')


_VENUE_PAREN = re.compile(r'[（(][^（()）]*[)）]\s*$')


def venue_display(v):
    """会場ページに出す表示名。住所の括弧書きだけを落とす。"""
    v = (v or '').strip()
    return _VENUE_PAREN.sub('', v).strip() or v


def venue_key(v):
    """会場ページを束ねるキー。表記の揺れで同じ会場が割れるのを防ぐ。

    events.json の location は、新しく足した回ほど
    「会場名（都道府県…住所）」の形で住所を括弧書きしている。
    生の文字列でキーにすると、同じ会場でも住所の有無・空白の入れ方の
    違いだけで別ページに割れ、「複数回開催実績のある会場のみ」という
    会場ページの前提そのものが崩れる(2026-08-20 に9組の分裂を確認)。

    グルーピングのキーとスラッグの元は必ず同じ値にすること。
    別々にすると、キーは2つでスラッグは1つになり、
    後から書いたほうが前のページを黙って上書きする。
    """
    v = unicodedata.normalize('NFKC', (v or '')).strip()
    v = _VENUE_PAREN.sub('', v)
    return re.sub(r'\s+', '', v)


VENUE_ROMAJI = {venue_key(k): v for k, v in _VENUE_ROMAJI_RAW.items()}
VENUE_SLUG_REDIRECTS = {k: (venue_key(v) if v else None)
                        for k, v in _VENUE_REDIRECTS_RAW.items()}

# --- 日付整形 ---

def date_to_japanese(date_str):
    """2026-05-03 → 2026年5月3日（日）"""
    if not date_str:
        return ''
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d')
        wd = WEEKDAYS_JA[dt.weekday()]
        return f'{dt.year}年{dt.month}月{dt.day}日（{wd}）'
    except ValueError:
        return date_str

def compact_date(e):
    """一覧用の YYYY.MM.DD(-DD / -MM.DD)。dateが無ければdateDisplayへフォールバック。"""
    d = e.get('date') or ''
    if not d:
        return e.get('dateDisplay') or '開催日未発表'
    de = e.get('dateEnd') or d
    s = f"{d[:4]}.{d[5:7]}.{d[8:10]}"
    if de and de != d:
        s += f"-{de[8:10]}" if de[5:7] == d[5:7] else f"-{de[5:7]}.{de[8:10]}"
    return s

# --- 本文に書かれた日付 (単一情報源) ---
# 「その文章はこの回の日付を名指ししているか」は、少なくとも2か所で要る。
#   1. 説明文が別の回の日付を書いていないか (audit.desc_date_mismatch)
#   2. 出典の頁がこの回の日付を書いているか (check-cancelled → audit)
# 2 を足すときに 1 の正規表現を写すところだった。写すと片方だけ賢くなるので
# ここに置く(sitelib_rule_duplicated が写しを止める)。
#
# 年は持たない。告知は「9月20日(日)」と書くほうが多く、年まで書く頁のほうが
# 少ない。年の食い違いは find_year_month_days() が別に見る。
_MD_KANJI = re.compile(r'(\d{1,2})月\s*(\d{1,2})日')
# 「6/1(土)」形式。前年告知の貼り付けを実際に取り逃がしたので拾う
# (fujiyama-days-little-green-park-2026)。時刻 9:30 と比を巻き込まないよう
# 前後に数字・コロン・スラッシュが来る形は外す。
_MD_SLASH = re.compile(r'(?<![\d:/])(\d{1,2})/(\d{1,2})(?![\d/])')
# 「2026.10.10」「2026-10-10」「2026/10/10」形式
_YMD_SEP = re.compile(r'(\d{4})[./-](\d{1,2})[./-](\d{1,2})')
_YMD_KANJI = re.compile(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日')


def _md_ok(m, d):
    return 1 <= m <= 12 and 1 <= d <= 31


def find_month_days(text, kanji_only=False):
    """本文から (月, 日) の集合を拾う。

    kanji_only=True は「◯月◯日」だけを見る。散文で日付を名乗っている頁か
    どうかの判定に使う。スラッシュ形は画像パス(/2026/09/)やページ送りにも
    現れるので、「日付が書いてある」ことの根拠には弱い。
    """
    t = text or ''
    out = {(int(a), int(b)) for a, b in _MD_KANJI.findall(t) if _md_ok(int(a), int(b))}
    if kanji_only:
        return out
    out |= {(int(a), int(b)) for a, b in _MD_SLASH.findall(t) if _md_ok(int(a), int(b))}
    out |= {(int(a), int(b)) for _y, a, b in _YMD_SEP.findall(t) if _md_ok(int(a), int(b))}
    return out


def find_year_month_days(text):
    """本文から (年, 月, 日) を拾う。年を名乗っている形だけ。"""
    out = set()
    for y, m, d in _YMD_KANJI.findall(text or ''):
        if _md_ok(int(m), int(d)):
            out.add((int(y), int(m), int(d)))
    for y, m, d in _YMD_SEP.findall(text or ''):
        if _md_ok(int(m), int(d)):
            out.add((int(y), int(m), int(d)))
    return out


def event_month_days(e, max_days=400):
    """会期の全日を (月, 日) の集合で返す。単日なら1要素。"""
    d, de = event_span(e)
    if not d:
        return set()
    try:
        cur = date.fromisoformat(d)
        end = date.fromisoformat(de or d)
    except ValueError:
        return set()
    out = set()
    while cur <= end and (end - cur).days < max_days:
        out.add((cur.month, cur.day))
        cur += timedelta(days=1)
    return out


# --- 時間軸 (単一情報源) ---
# 一覧の並び順と「開催予定」の判定に開始日だけを使うと、同じ原因から
# 逆向きの事故が2つ出る。
#   1. 会期の長い回が開始日の古さで一覧の先頭に居座る
#      (MOLLIS EXHIBIT 2026 は会期49日、トップ一覧の1位を1か月以上占有)
#   2. date >= today を外れるので、開催中の回がランディングで終了扱いに落ちる
#      (/pref/tokyo/ で開催中の MOLLIS が終了済みの回に混ざり23番目)
# this-month が 2026-08-18 に同じ型の不具合で dateEnd 基準へ直されたが、
# 規則が各ジェネレータとフロントに散っていたため他が直らなかった。
# 「今」の定義はここだけに置く。ジェネレータもフロント(status-auto.js)も従う。

LONG_RUN_DAYS = 4      # 会期がこの日数以上を「長期開催」とみなす
FAR_FUTURE = '9999-12-31'

# 説明文の下限字数。「短い説明文」の単一情報源。
# 2026-08-24 に 70字→50字へ揃えたとき、同じ数字が
#   audit.py の is_thin / short_descriptions、check_events.py、
#   enrich_events.py の _quality_ok、listing-policy.json の shortDescriptions.threshold
# の5か所にリテラルで散っていた。以前この不一致(thin=50 / check=70 / enrich=120)が
# 「短い回を優先処理しているのに 'too short' で捨てる」という取りこぼしを生んでいる。
# 数字ではなくこの定数を参照する。audit.py の desc_min_chars_drift が写しを検出する。
DESC_MIN_CHARS = 50

# 人が裏取りして書いた説明文を、週次エンリッチのスクレイプで上書きしない期間。
# 2026-08-27 に enrich_events.py へ入れたが、目印が updatedAt だけだったため
# 新規登録で入れ忘れると保護が一切効かなかった(2026-08-28 に30件が無防備で発覚。
# 週次エンリッチの2日前だった)。
# 「入れ忘れない」は運用で守れないので、addedDate でも守れるようにする。
# ただし addedDate 側は実体のある本文に限る。短いスタブを保護すると、
# いちばん埋めてほしい回を14日間エンリッチの対象外にしてしまう。
DESC_PROTECT_DAYS = 14


def desc_is_protected(e, today=None):
    """説明文をスクレイプで上書きしてはならない回か。

    enrich_events.py(書き込み側)と audit.py(検出側)の単一情報源。
    どちらか片方に書くと、翌週の巡回が同じ本文を書き戻す。
    """
    ref = today or today_jst()
    try:
        ref = date.fromisoformat(str(ref)[:10])
    except ValueError:
        return False
    limit = ref - timedelta(days=DESC_PROTECT_DAYS)

    def _within(v):
        v = (v or '').strip()[:10]
        if len(v) < 10:
            return False
        try:
            return date.fromisoformat(v) >= limit
        except ValueError:
            return False

    if _within(e.get('updatedAt')):
        return True
    return (_within(e.get('addedDate'))
            and len((e.get('description') or '').strip()) >= DESC_MIN_CHARS)


# 終了イベントを一覧に残す期間。「いつまで見せるか」の単一情報源。
# 従来は status-auto.js の HIDE_AFTER_DAYS=14(display:none)と
# sync-index-cards.py の KEEP_PAST=12(HTMLから物理削除)に別々の単位で置かれ、
# 全日程の26%で両者が食い違っていた(2026-08-20に統合)。
# display:none はDOMもHTMLの重さも減らさないので、肥大化を止めるのは物理削除の側。
# 日数を主にし、件数は異常時の安全弁として上限だけ持つ。
# 実測: ある日から見て直近14日に終わった回は中央値1件・最大34件(2026-08-03)。
# 一覧の初期表示は list-ui.js が「段数×列数」で決める(PC 3段 / SP 5段)。
# 列数は画面幅で変わるので、いちばん少なくなる組み合わせ(SP 2列×5段=10)を
# ここでの下限とする。「もっと見る」ボタンを出すかどうかの判定にだけ使う。
# 12固定にすると、11件のときSPでは10件しか出ないのにボタンが無くなる。
CARDS_PER_PAGE = 10
PAST_CARDS_INIT = 4    # 終了セクションの初期表示件数。list-ui.js と同値
PAST_KEEP_DAYS = 14
PAST_KEEP_MAX = 40     # 上限。実測最大34件を通し、暴走だけ止める
PAST_KEEP_LABEL = f'過去{PAST_KEEP_DAYS}日以内'


def event_span(e):
    """(開始日, 終了日) を ISO 文字列で返す。開始日が無ければ ('', '')。"""
    d = (e.get('date') or '').strip()
    if not d:
        return '', ''
    return d, ((e.get('dateEnd') or '').strip() or d)


def event_days(e):
    """会期日数。開始日が無い / 日付が壊れている回は None。"""
    d, de = event_span(e)
    if not d:
        return None
    try:
        return (date.fromisoformat(de) - date.fromisoformat(d)).days + 1
    except ValueError:
        return None


def is_long_run(e, threshold=LONG_RUN_DAYS):
    """長期開催か。2〜3日の週末開催は一覧本体に混ぜるので長期に含めない。"""
    n = event_days(e)
    return n is not None and n >= threshold


CANCELLED_STATUSES = ('cancelled', 'postponed')


def is_cancelled(e):
    """開催されないことが確定した回。

    削除ではなく中止として残す。消すと URL が 404 になり、共有された
    リンクやブックマークを踏んだ人に何も伝わらないまま当日を迎える。
    「◯◯ 中止」で検索して来た人に答えるのも一覧サイトの仕事。
    """
    return str(e.get('eventStatus') or '').lower() in CANCELLED_STATUSES


def cancel_label(e):
    st = str(e.get('eventStatus') or '').lower()
    return {'cancelled': '中止', 'postponed': '延期'}.get(st, '')


def event_phase(e, today=None):
    """'past' | 'ongoing' | 'upcoming' | 'undated'

    終了日で判定する。開始日で判定すると開催中の回が終了扱いになる。
    """
    d, de = event_span(e)
    if not d:
        return 'undated'
    t = today or today_jst()
    if de < t:
        return 'past'
    if d <= t:
        return 'ongoing'
    return 'upcoming'


def is_upcoming(e, today=None):
    """一覧・フィード・ランディングの「開催予定」側に出すか。開催中を含む。

    中止・延期の回は外す。詳細ページは残すが、予定として数えない。
    件数バッジ・カレンダー・iCal・RSS がすべてここを見ているので、
    1か所で外せば全部に効く。
    """
    if is_cancelled(e):
        return False
    return event_phase(e, today) in ('ongoing', 'upcoming', 'undated')


def is_ongoing(e, today=None):
    return event_phase(e, today) == 'ongoing'


def is_long_ongoing(e, today=None, threshold=LONG_RUN_DAYS):
    """一覧本体から外して「開催中」の枠に出す回。"""
    return event_phase(e, today) == 'ongoing' and is_long_run(e, threshold)


def is_recent_past(e, today=None, keep_days=None):
    """終了しているが一覧に残す範囲か。会期の終わりからの経過日数で判定する。

    開始日で数えると、会期の長い回が終わった直後から消える。
    """
    d, de = event_span(e)
    if not d:
        return False
    t = today or today_jst()
    if de >= t:
        return False
    try:
        gone = (date.fromisoformat(t) - date.fromisoformat(de)).days
    except ValueError:
        return False
    return gone <= (keep_days if keep_days is not None else PAST_KEEP_DAYS)


def list_sort_key(e, today=None):
    """一覧の並び順(昇順)の単一情報源。

    開催中の回は「今日始まる回」と同じ位置に置く。開始日のままだと
    会期の長さに比例して先頭へ寄り、会期のあいだ居座る。
    同じ日付では今日始まる回を先に、会期の途中の回を後ろに置く。
    """
    t = today or today_jst()
    d, de = event_span(e)
    name = e.get('name') or ''
    if not d:
        return (FAR_FUTURE, 2, FAR_FUTURE, name)
    if de < t:
        return (d, 0, d, name)          # past はここでは順序を変えない
    return ((d if d > t else t), (1 if d < t else 0), d, name)


def ongoing_sort_key(e, today=None):
    """「開催中」枠の並び順。会期の終わりが近い回を先に出す。"""
    d, de = event_span(e)
    return (de or FAR_FUTURE, d or FAR_FUTURE, e.get('name') or '')


def split_ongoing(evs, today=None, threshold=LONG_RUN_DAYS):
    """(開催中の長期, 一覧本体) に分ける。どちらも規定の順に並べて返す。"""
    t = today or today_jst()
    ong = [e for e in evs if is_long_ongoing(e, t, threshold)]
    rest = [e for e in evs if not is_long_ongoing(e, t, threshold)]
    ong.sort(key=lambda e: ongoing_sort_key(e, t))
    rest.sort(key=lambda e: list_sort_key(e, t))
    return ong, rest


# --- シリーズ名正規化 (開催履歴の同名イベント束ね) ---

_SEASON_WORDS = r'(spring|summer|autumn|fall|winter|春|夏|秋|冬|new\s*year)'

def normalize_series_name(name):
    """イベント名からシリーズ判定用キーを作る。回数・年・季節・開催地表記を除去。"""
    s = unicodedata.normalize('NFKC', (name or '')).lower()
    s = re.sub(r'vol\.?\s*\d+', ' ', s)
    s = re.sub(r'第\s*\d+\s*回', ' ', s)
    s = re.sub(r'\d+(st|nd|rd|th)\b', ' ', s)
    s = re.sub(r'(19|20)\d{2}', ' ', s)
    s = re.sub(_SEASON_WORDS, ' ', s)
    s = re.sub(r'\bin\s+\S+', ' ', s)
    s = re.sub(r'[#＃]?\d+', ' ', s)
    s = re.sub(r'[^0-9a-zぁ-んァ-ヶ一-龠ー]+', '', s)
    return s

# --- 共通HTMLフラグメント (単一情報源) ---

ADSENSE_HEAD = (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js'
                f'?client={ADSENSE_CLIENT}" crossorigin="anonymous"></script>\n'
                f'  <meta name="google-adsense-account" content="{ADSENSE_CLIENT}">')

GTAG_HEAD = (f'<script async src="https://www.googletagmanager.com/gtag/js?id={GA_ID}"></script>\n'
             f"  <script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
             f"gtag('js',new Date());gtag('config','{GA_ID}');</script>")

# ナビの行き先。ヘッダーのメニューはこれを唯一の元にする。
NAV_LINKS = (
    ('/', 'ホーム'),
    ('/calendar.html', 'カレンダー'),
    ('/map.html', 'マップ'),
    ('/about.html', 'サイトについて'),
    ('/contact.html', 'お問い合わせ'),
    ('/listing.html', '掲載申請'),
    ('/category/sokubai.html', '即売会一覧'),
    ('/category/marche.html', 'マルシェ一覧'),
    ('/category/large.html', '大型イベント一覧'),
    ('/category/exhibition.html', '展示会一覧'),
)

IKITAI_HEART_SVG = ('<svg class="ikitai-heart" viewBox="0 0 24 24">'
                    '<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06'
                    'a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06'
                    'a5.5 5.5 0 0 0 0-7.78z"/></svg>')


def site_nav():
    """SPのメニュー。ヘッダーのハンバーガーで開く。

    以前は site_header() にこれが入っておらず、生成ページ全部
    (詳細145・地域/県/タグ/カテゴリ106・ガイド)にナビが無かった。
    SPで詳細を開くと、トップに戻る導線がロゴだけだった(2026-09-08 指摘)。
    開閉の実装は nav.js が唯一の持ち主。
    """
    links = ''.join('\n      <a href="%s">%s</a>' % (u, html_escape(n))
                    for u, n in NAV_LINKS)
    return (
        '  <nav class="nav-overlay" id="navOverlay">\n'
        '    <div class="nav-overlay-inner">' + links + '\n'
        '      <a href="https://www.instagram.com/m.z.plants/" target="_blank"'
        ' rel="noopener">INSTAGRAM</a>\n'
        '      <a href="/ikitai.html" class="nav-ikitai-link">'
        + IKITAI_HEART_SVG + ' 行きたいリスト</a>\n'
        '    </div>\n'
        '  </nav>\n'
        '  <script src="/nav.js?v=' + JS_VERSION + '" defer></script>')


def site_header(root=''):
    """共通ヘッダー。リンクは絶対パスなので root は使わない(互換で残す)。"""
    return (
        '  <header class="header">\n'
        '    <div class="header-inner">\n'
        '      <a href="/" class="logo"><span class="logo-en">AGA NAVI</span>'
        '<span class="logo-jp">アガベイベントナビ</span></a>\n'
        '      <div class="header-actions">\n'
        '        <a href="/ikitai.html" class="ikitai-blob-btn">'
        '<span class="blob-bg"></span>\n'
        '          ' + IKITAI_HEART_SVG + '\n'
        '          <span class="ikitai-label">行きたい</span>\n'
        '          <span class="ikitai-badge" id="ikitaiBadge"></span></a>\n'
        '        <button class="menu-toggle" id="menuToggle" aria-label="メニュー"'
        ' aria-expanded="false">\n'
        '          <span></span><span></span><span></span>\n'
        '        </button>\n'
        '      </div>\n'
        '    </div>\n'
        '  </header>\n' + site_nav())


UPDATE_KIND = {
    'listed':    ('掲載', 'upd-listed'),
    'cancelled': ('中止', 'upd-cancelled'),
    'postponed': ('延期', 'upd-cancelled'),
    'removed':   ('取り消し', 'upd-removed'),
    'date':      ('日程変更', 'upd-changed'),
    'venue':     ('会場変更', 'upd-changed'),
}
UPDATES_MAX = 10


def load_updates(root_path=None):
    """site-updates.json の items。新しい順。"""
    p = root_path or os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), 'site-updates.json')
    try:
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        return d.get('items') or []
    except (OSError, ValueError):
        return []


# 掲載以外は「開催されなくなった/条件が変わった」の知らせで、
# 掲載より届ける価値が高い。掲載が大量に出た日に埋もれさせない。
UPDATE_IMPORTANT = ('cancelled', 'postponed', 'removed', 'date', 'venue')
UPDATE_IMPORTANT_DAYS = 60


def pick_updates(items, limit, today=None):
    """新しい順に切り出すが、中止系は枠を確保して落とさない。

    2026-09-08、掲載が50件並んだ日にコレクトプランツの中止が
    フィードから消えた。**いちばん届けたいものが埋もれるのは設計ミス。**
    掲載はサイトを見れば分かるが、中止は知らせが届かないと分からない。
    """
    # 呼び出し側の並びに依存しない。新しい順に揃えてから絞る。
    # 入力が新しい順である前提を置くと、古い中止が先頭にあるだけで
    # 埋め合わせに拾われる（2026-09-08 の自己テストで踏んだ）。
    items = sorted(list(items or []),
                   key=lambda x: ((x.get('on') or ''), (x.get('slug') or '')),
                   reverse=True)
    if len(items) <= limit:
        return items
    t = today or today_jst()
    try:
        cut = (date.fromisoformat(t)
               - timedelta(days=UPDATE_IMPORTANT_DAYS)).isoformat()
    except ValueError:
        cut = ''
    keep, rest = [], []
    for it in items:
        kind = str(it.get('kind') or '')
        on = (it.get('on') or '')[:10]
        if kind in UPDATE_IMPORTANT and on >= cut:
            keep.append(it)
        else:
            rest.append(it)
    keep = keep[:limit]
    out = keep + rest[:max(0, limit - len(keep))]
    # 元の並び（新しい順）に戻す
    order = {id(x): i for i, x in enumerate(items)}
    return sorted(out, key=lambda x: order[id(x)])


def filter_updates(items, region=None, prefecture=None):
    """地域・県で絞る。

    地域ページには**その地域の県の更新だけ**を出す。東海のページに
    愛知と三重の更新が出て、熊本の更新は出ない。県ページはその県だけ。
    そのページと関係ない更新が並ぶと読む理由が無くなる(2026-09-08 指摘)。
    """
    out = []
    for it in (items or []):
        pref = (it.get('prefecture') or '').strip()
        if prefecture:
            if pref == prefecture:
                out.append(it)
            continue
        if region:
            if pref and pref_to_region(pref) == region:
                out.append(it)
            continue
        out.append(it)
    return out


# パンくずの根っこは2種類ある。**混ぜてはいけない**(2026-09-09 指摘)。
#
# CRUMB_ROOT「全国」… イベント一覧の範囲。全国 > 関東 > 埼玉 > イベント名。
#   地域・県・タグ・アーカイブも全国一覧を絞ったものなのでこちら。
#   トップの絞り込みの現在地が「全国」なので、呼び名を揃えてある。
#
# CRUMB_HOME「ホーム」… サイトの案内頁。about / 規約 / お問い合わせ /
#   掲載申請 / 運営者情報 / カレンダー / マップ / 行きたいリスト /
#   植物ガイド / 404。これらは全国一覧を絞ったものではないので、
#   根っこに「全国」を置くと階層が嘘になる。
CRUMB_ROOT = ('全国', '/')
CRUMB_HOME = ('ホーム', '/')


# 外部リンクの表記。**ここが唯一の組み立て。**
#
# 2026-09-08 時点で「Instagram投稿 ↗」「関連サイト ↗」「Instagramで見る ↗」
# 「Googleマップで開く ↗」「公式Instagram」がページの中に混在していた。
# 同じ「外に出る」動作が5通りの言い方をしていた。
#
# 「関連サイト」はやめた。関係が曖昧で、読んだ人に何も伝わらない。
# 出るのはたいてい公式サイトか Instagram なので、そう書く。
#
# 印は「↗」だけだと外部だと気づかれないので、枠を付けて
# 読み上げ用に「外部サイト」を隠し文字で添える。
EXT_MARK = ('<span class="ext-mark" aria-hidden="true">↗</span>'
            '<span class="sr-only">（外部サイトを新しいタブで開く）</span>')


def link_kind(url, field=None):
    """URLの種別と、リンクに出す文字を返す。

    field は events.json のどの項目から来たか。
    'url' は掲載方針で「その回の公式ページ」と決めているので公式サイトと呼ぶ。
    それ以外の素のURLは公式と言い切れないので「出典」にする。
    """
    u = (url or '')
    ul = u.lower()
    if not ul:
        return ('', '')
    if 'instagram.com' in ul:
        handle = ''
        m = re.search(r'instagram\.com/([A-Za-z0-9._]+)', u)
        if m and m.group(1) not in ('p', 'reel', 'tv', 'explore'):
            handle = '@' + m.group(1)
        if '/p/' in ul or '/reel/' in ul or '/tv/' in ul:
            return ('Instagram', handle or 'この回の告知')
        return ('Instagram', handle or 'instagram.com')
    if 'facebook.com' in ul:
        return ('Facebook', 'facebook.com')
    if 'twitter.com' in ul or '://x.com/' in ul:
        m = re.search(r'(?:twitter|x)\.com/([A-Za-z0-9_]+)', u)
        return ('X', ('@' + m.group(1)) if m else 'x.com')
    if 'google.com/search' in ul:
        return ('検索', 'Googleで探す')
    host = re.sub(r'^www\.', '', re.sub(r'^https?://', '', u).split('/')[0])
    return ('公式サイト' if field == 'url' else '出典', host or u)


def ext_link(url, text, cls=''):
    """外部リンク1本。印と rel はここでしか付けない。"""
    c = ('ext ' + cls).strip()
    return (f'<a class="{c}" href="{_attr(url)}" target="_blank"'
            f' rel="noopener">{html_escape(text)}{EXT_MARK}</a>')


# 訂正の受け口。**言い方をここに固定する。**
# 「万が一誤りがある場合は申し訳ございません」と謝る文だった時期があり、
# それを直したときは「誤りがあれば教えてください」と口語に振れた。
# 立ち位置は「主催者の発表を確認して作っている。それでも誤りがあれば
# 知らせてほしい」(2026-09-09 指摘)。謝る場所でも、砕ける場所でもない。
CORRECTION_LEAD = '掲載内容は主催者の発表を確認して作成しています。'
CORRECTION_ASK = ('万一誤りがありましたら、{link}からお知らせください。'
                  '確認のうえ修正します。')


def correction_note(root='', lead=True, here=False):
    """訂正のお願い1文。

    lead=False で前置きを省く。
    here=True はお問い合わせ頁自身で使う。同じ頁へのリンクを出さない。
    """
    if here:
        link = '上のフォーム'
    else:
        link = f'<a href="{root}contact.html">お問い合わせ</a>'
    body = CORRECTION_ASK.replace('{link}', link)
    return (CORRECTION_LEAD + body) if lead else body


CRUMB_SEP = '<span class="pref-sep" aria-hidden="true">&gt;</span>'


def crumb_search_html(live=False):
    """パンくずの右端に置く検索。トップと同じ見た目にする。

    トップは入力しながら絞るので live=True。他の頁は絞る対象が
    無いので `/?q=` に飛ばす。トップ側が q を読んで絞る。
    JSを足さずに form の GET で済ませる。
    """
    if live:
        # トップだけ入力しながら絞る。id と oninput は top-filter.js が見る
        return ('<div class="search-field">'
                '<input type="text" id="searchInput"'
                ' placeholder="イベント名・会場で検索"'
                ' aria-label="イベントを検索"'
                ' oninput="searchEvents(this.value)"></div>')
    return ('<form class="search-field" action="/" method="get" role="search">'
            '<input type="search" name="q" placeholder="イベント名・会場で検索"'
            ' aria-label="イベントを検索"></form>')


def crumb_link(name, url):
    """上位。押すと1段上がる。"""
    return f'<a href="{_attr(url)}">{html_escape(name)}</a>'


def crumb_here(name):
    """現在地。**クラスで示す。**素の span を現在地の印にすると
    区切りの span まで黒く塗られる(2026-09-08 本番で発生)。"""
    return f'<span class="crumb-current">{html_escape(name)}</span>'


def crumb_button(name, onclick, *, active=False, node_id='', cls='pref-crumb',
                 data=''):
    """押して絞る段。トップのエリア絞り込みが使う。

    行き先がリンクではなくJSなので button。見た目は上位・現在地と
    同じ部品を使う。ここを div や span で作ると、同じ形のものが
    別のCSSを持つ(それが .crumb-row / .region-tabs / .pref-row だった)。
    """
    return ('<button class="' + cls + (' active' if active else '') + '"'
            + (f' id="{node_id}"' if node_id else '')
            + ((' ' + data) if data else '')
            + f' onclick="{_attr(onclick)}">{html_escape(name)}</button>')


def crumb_nav(nodes, label='パンくずリスト', node_id='', hidden=False):
    """パンくず1段。**区切りを入れるのはここだけ。**

    label はトップのエリア絞り込みだけ変える。見た目は同じでも
    あちらは階層ではなく絞り込みなので、読み上げでパンくずと
    名乗らせない。sync-footers.py が作り直す対象の目印も兼ねる。
    """
    return ('<nav class="breadcrumb"'
            + (f' id="{node_id}"' if node_id else '')
            + f' aria-label="{_attr(label)}"'
            + (' style="display:none"' if hidden else '')
            + '>' + CRUMB_SEP.join(nodes) + '</nav>')


def crumb_bar_html(navs, search=True, live=False):
    """パンくずの帯。navs は crumb_nav の並び。**帯の唯一の組み立て。**

    詳細・地域・県・タグ・ガイドは .crumb-bar、トップだけ
    .filter-bar > .area-filter-bar > .area-drilldown > .crumb-row という
    別の作りで、同じ「全国 > 関東 > 埼玉」を4通りの器で出していた。
    固定する位置もトップだけ手打ちの 40px で、実測 50.8px の
    ヘッダーの下に約11px潜り込んでいた(2026-09-10 実測)。
    """
    rows = ['    ' + n + '\n' for n in navs]
    if search:
        rows.append('    ' + crumb_search_html(live) + '\n')
    return '  <div class="crumb-bar">\n' + ''.join(rows) + '  </div>'


def crumb_parts(item):
    """パンくず1項目を (表示名, 可視リンク先, 構造化データのURL) に開く。

    項目は (名前, URL) か (名前, 可視URL, LD用URL) のどちらでもよい。
    **2つ書けるのは、人の導線と検索の階層が一致しない場所があるため。**
    詳細・県・地域の上位はトップの絞り込み(`/?region=関東&pref=東京`)を
    指す。絞り込んで降りてきた人が次に隣の県へ行けるのはそこだけで、
    `/pref/tokyo/` にはチップが無く袋小路になる(2026-09-10 指摘)。
    一方その絞り込みURLは canonical がトップなので、BreadcrumbList に
    入れると階層が潰れる。そちらには実在する `/pref/tokyo/` を出す。

    **items は1つ。**表示用とLD用でリストを別に組むと、片方だけ直る。
    """
    if len(item) == 3:
        name, url, ld = item
        return name, url, (ld if ld is not None else url)
    name, url = item
    return name, url, url


def breadcrumb_html(items, search=True):
    """いちばん普通の1段のパンくず。items は [(表示名, リンク先 or None)]。

    最後が現在地。途中でリンク先が無いものも現在地として塗る
    (カテゴリ頁の「全国 > カテゴリ > 即売会」がこれに当たる)。
    """
    n = len(items)
    nodes = []
    for i, item in enumerate(items):
        name, url, _ld = crumb_parts(item)
        last = (i == n - 1)
        nodes.append(crumb_link(name, url) if (url and not last)
                     else crumb_here(name))
    return crumb_bar_html([crumb_nav(nodes)], search=search)


def crumb_jsonld(items, domain=None):
    """パンくずの構造化データ。表示と同じ items から作る。

    表示とJSON-LDを別々に書いていたので、片方だけ「ホーム」が残る。
    項目が3つ組なら、URLは3つ目(LD用)を使う。crumb_parts を見ること。
    """
    d = domain or DOMAIN
    els = []
    n = len(items)
    for i, item in enumerate(items):
        name, _url, ld = crumb_parts(item)
        e = {'@type': 'ListItem', 'position': i + 1, 'name': name}
        # 現在地(最後)はURLを持たない。表示と同じ規則で切る
        if ld and i != n - 1:
            e['item'] = ld if ld.startswith('http') else d + ld
        els.append(e)
    return ('  <script type="application/ld+json">\n  '
            + json.dumps({'@context': 'https://schema.org',
                          '@type': 'BreadcrumbList',
                          'itemListElement': els}, ensure_ascii=False)
            + '\n  </script>')


def region_prefs():
    """地域 -> 都道府県。PREF_TO_REGION の並び(北→南)を保つ。"""
    out = {}
    for p, r in PREF_TO_REGION.items():
        out.setdefault(r, []).append(p)
    return out


def time_consts_js():
    """status-auto.js の時間軸の定数。**数値を2か所に書かない。**

    ブラウザ側は event_phase / list_sort_key を自前で持たざるを得ないが、
    定数まで写すと片方だけ変えたときに黙ってずれる。ここから貼る。
    挙動そのものの一致は scripts/test-time-parity.py が毎ビルド見る。
    """
    return (f'    var LONG_RUN_DAYS = {LONG_RUN_DAYS};\n'
            f'    var PAST_KEEP_DAYS = {PAST_KEEP_DAYS};')


def region_map_js():
    """トップの絞り込みが使う地域表。PREF_TO_REGION から作る。

    以前は index.html に手書きの表があり、北海道・東北・四国が
    丸ごと抜けていた。その3地域はチップも無いので、載っている
    イベントに一生たどり着けなかった。山梨・長野も北陸から
    漏れていた(2026-09-08 に発見)。表を2箇所に置くと必ずこうなる。
    """
    return ('const regionMap = '
            + json.dumps(region_prefs(), ensure_ascii=False)
            + ';')


def area_filter_html(events=None):
    """トップのエリア絞り込み。全国 > 地域 > 県 のパンくず。

    下層ページのパンくずと同じ器(.crumb-bar > nav.breadcrumb)で出す。
    現在地を黒、選択肢を白のチップで出す。「すべて」チップは置かない。
    地域名自体が現在地になる。

    events を渡すと、載っている回がある地域だけを出す。
    空振りするチップを並べても押す意味が無い。
    """
    have = None
    if events is not None:
        have = set()
        for e in events:
            if not (is_upcoming(e) or is_cancelled(e)):
                continue
            r = pref_to_region((e.get('prefecture') or '').strip())
            if r:
                have.add(r)
    chips = []
    for r in region_prefs():
        if have is not None and r not in have:
            continue
        chips.append(crumb_button(r, f"selectRegion('{r}')", cls='region-tab',
                                  data=f'data-region="{_attr(r)}"'))
    region_nav = crumb_nav(
        [crumb_button('全国', "selectRegion('all')", active=True),
         '<div class="pref-chips" id="regionChips">' + ''.join(chips) + '</div>'],
        label='エリア絞り込み', node_id='regionTabs')
    pref_nav = crumb_nav(
        [crumb_button('全国', "selectRegion('all')"),
         crumb_button('', "selectPref('all')", node_id='prefRegionCrumb'),
         '<div class="pref-chips" id="prefChips"></div>'],
        label='エリア絞り込み', node_id='prefRow', hidden=True)
    return crumb_bar_html([region_nav, pref_nav], live=True)


def update_rows(picked, root=''):
    """更新のお知らせの行。1行1件。

    節の組み立てと範囲別の差し替え用の両方がここを通る。
    同じ行を2箇所で組むと、片方だけ列が増えて必ずずれる。
    """
    rows = []
    for it in picked:
        kind = str(it.get('kind') or '')
        label, cls = UPDATE_KIND.get(kind, (kind, 'upd-changed'))
        slug = (it.get('slug') or '').strip()
        name = it.get('name') or slug
        on = (it.get('on') or '')[:10]
        on_disp = on[5:].replace('-', '.') if len(on) == 10 else on
        pref = (it.get('prefecture') or '').strip()
        detail = (it.get('detail') or '').strip()
        # 取り消した回は詳細ページが無いのでリンクしない
        if kind == 'removed' or not slug:
            title = html_escape(name)
        else:
            title = (f'<a href="{root}events/{_attr(slug)}.html">'
                     f'{html_escape(name)}</a>')
        side = ' / '.join(x for x in [pref, detail] if x)
        rows.append(
            f'<li class="upd-item">'
            f'<span class="upd-date">{html_escape(on_disp)}</span>'
            f'<span class="upd-kind {cls}">{html_escape(label)}</span>'
            f'<span class="upd-title">{title}</span>'
            + (f'<span class="upd-meta">{html_escape(side)}</span>' if side else '')
            + '</li>')
    return rows


def updates_section_html(items, limit=UPDATES_MAX, region=None, prefecture=None,
                         show_feed=True, root=''):
    """更新のお知らせ。追加と中止をここで受け取らせる。

    一覧サイトの値打ちは「いまの状態が正しいこと」だが、変わったことは
    どこにも出ていなかった。カードの新着バッジは7日で消えるだけで、
    中止に至っては受け取り手がいない。詳細ページに中止と出しても、
    2週間前に見た人はそのページに戻ってこない(2026-09-08)。

    region / prefecture を渡すとその範囲に絞る。トップは全国で出し、
    地域チップで絞られたときは updates_scopes が作った範囲別の行に
    JS側が差し替える。
    """
    rows = update_rows(pick_updates(filter_updates(items, region, prefecture),
                                    limit), root)
    if not rows:
        return ''
    scope = prefecture or region or ''
    note = f'{scope}の掲載・中止・日程変更' if scope else '掲載・中止・日程変更'
    feed = (f'<a class="updates-feed" href="{root}feeds/updates.xml">'
            f'RSSで受け取る</a>' if show_feed else '')
    return (
        '<section class="updates-section" id="updates" aria-labelledby="updatesHeading">'
        '<div class="updates-head">'
        '<h2 class="updates-title" id="updatesHeading">更新のお知らせ'
        f'<span class="updates-note">{html_escape(note)}</span></h2>'
        + feed +
        '</div>'
        '<ul class="updates-list">' + ''.join(rows) + '</ul>'
        '</section>')


def updates_scopes(items, limit=UPDATES_MAX, root=''):
    """範囲別の行をまとめて返す。キーは all / region:関東 / pref:愛知。

    トップに埋まっているのは全国の最新10件なので、関東で絞ると
    0件になることがあった。関東の更新自体はあるのに「無い」と出る
    (2026-09-08 本番で確認)。範囲ごとの行を作っておいてJS側で
    差し替える。取り出しと組み立てはここを通るので、地域ページと
    同じ並び・同じ行になる。
    """
    out = {}
    rows = update_rows(pick_updates(items, limit), root)
    if rows:
        out['all'] = ''.join(rows)
    regions, prefs = set(), set()
    for it in (items or []):
        pf = (it.get('prefecture') or '').strip()
        if not pf:
            continue
        prefs.add(pf)
        rg = pref_to_region(pf)
        if rg:
            regions.add(rg)
    for rg in sorted(regions):
        r = update_rows(pick_updates(filter_updates(items, region=rg), limit), root)
        if r:
            out['region:' + rg] = ''.join(r)
    for pf in sorted(prefs):
        r = update_rows(pick_updates(filter_updates(items, prefecture=pf), limit),
                        root)
        if r:
            out['pref:' + pf] = ''.join(r)
    return out


def site_footer():
    """正規フッター(全ページ共通・単一情報源)。404含む全静的ページは sync-footers.py で同期。"""
    year = now_jst().year
    return f"""  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-logo">
        <span class="logo-en">AGAVE EVENT NAVI</span>
      </div>
      <nav class="footer-nav">
        <!-- 「イベント一覧」と呼んでいたが、行き先はメニューの「ホーム」・
             ロゴ・パンくずの「全国」と同じ / だった。同じ場所を4つの名前で
             呼んでいて、どれを押しても同じところに着く(2026-09-09 指摘)。
             ナビでの呼び名は「ホーム」に統一する。
             「全国」はイベントの範囲を指す言葉なので、パンくずだけで使う -->
        <a href="/">ホーム</a>
        <a href="/new/">新着</a>
        <a href="/calendar.html">カレンダー</a>
        <a href="/map.html">マップ</a>
        <a href="/ikitai.html">行きたいリスト</a>
        <a href="/guides/">植物ガイド</a>
        <a href="/about.html">サイトについて</a>
        <a href="/contact.html">お問い合わせ</a>
      </nav>
      <nav class="footer-nav footer-nav-tertiary">
        <a href="/listing.html">掲載申請</a>
        <a href="/operator.html">運営者情報</a>
        <a href="/privacy.html">プライバシー</a>
        <a href="/terms.html">利用規約</a>
        <a href="/disclaimer.html">免責事項</a>
      </nav>
      <p class="footer-copy">&copy; 2025-{year} アガベイベントナビ</p>
    </div>
  </footer>"""


_VAGUE_MARKER = re.compile(r'(未定|未確定|調整中)')
# 「岐阜県内」「別府市内」「茨城県内会場」のような広域指定。会場名ではない。
# 2026-08-20まで audit.py だけがこの規則を持っていて sitelib は知らなかったため、
# 検出はできるのに地図・JSON-LD・会場ページ側は素通しという食い違いがあった。
_AREA_ONLY = re.compile(r'(都|道|府|県|市|区|町|村)内(会場)?$')


def is_vague_venue(v):
    """会場として使えない値か。

    完全一致の VAGUE_VENUES だけでは「金沢（会場未確定）」のように
    未定であることを括弧書きで補った値を取りこぼす。
    地図・JSON-LDのPlace・FAQに、会場名として出してはいけない値を1か所で判定する。
    """
    v = (v or '').strip()
    if not v:
        return True
    return (v in VAGUE_VENUES or bool(_VAGUE_MARKER.search(v))
            or bool(_AREA_ONLY.search(v)))


# --- imageUrl がイベント固有画像か ------------------------------------------
# WordPress のアップロード先は wp-content/uploads なので、themes/ 配下や
# common/images/ 配下はテーマ同梱のアセットで、イベント固有画像になり得ない。
# ファイル名だけを見る判定(/logo.png 等)では
# /wp-content/themes/theme_rakuza/common/images/facebook.png を通してしまう。
# 2026-08-18に13件を削除したが、2026-08-20の weekly-enrichment が
# 同じ2件を書き戻した。検出(audit)側だけに規則があり、
# 書き込み(enrich / backfill)側に無かったのが原因。ここを単一情報源にする。
GENERIC_IMAGE_RE = re.compile(
    r'(/wp-content/themes?/|/theme/[^/]+/assets/|/common/images?/'
    r'|/images?/common/|/shared/images?/|web_clip|apple-touch|favicon'
    r'|logo[_-]?ogp|ogp[_-]?logo|ogp[_-]?img|og_?_?images?\.|ogImg'
    r'|opengraph-image|site_config|/og\.(png|jpe?g|gif|webp)'
    r'|no[-_]?image|placeholder|/logo\.|logo_[a-z]+\.svg'
    # 区切りの直後に来る ogp（going_under_ground-ogp.png のような接頭辞付き）と、
    # themes/ 配下に無い素のSNSシェアアイコン。どちらも2026-08-20に素通りした
    r'|[-_]ogp\.(png|jpe?g|gif|webp)'
    r'|/(facebook|twitter|instagram)\.(png|jpe?g|gif|webp))', re.I)



# 入場料の文字列が「無条件に無料」を意味するかの単一情報源。
# 素の `'無料' in admission` で判定すると、有料イベントの但し書きに引っかかる。
# 2026-09-05 の実測で「入園料 大人250円・小中高130円・未就学児無料」
# 「500円（高校生以下は無料）」「前売600円／当日800円（中学生以下無料）」など
# 8件の有料イベントの詳細頁が本文で「入場は無料です。」と名乗っていた。
# スペック表には正しい金額が出ているので、同じ頁の中で矛盾していた。
# 判定: 「無料」を含み、かつ金額・チケット制・有料を示す語を一切含まないこと。
# 但し書きに金額が1つでも出るなら、要約で言い切らずに原文をそのまま出す。
_ADMISSION_PAID_HINT = re.compile(r'[0-9０-９]|円|チケット|有料|別途|要予約|前売')


def admission_is_free(admission):
    """admission が無条件に無料を意味するなら True。"""
    a = (admission or '').strip()
    if '無料' not in a:
        return False
    return not _ADMISSION_PAID_HINT.search(a)

def is_generic_image_url(u):
    """サイト共通アセット(ロゴ・OGP既定・ファビコン・テーマ内画像)なら True。

    True の値を imageUrl に入れてはいけない。露出は5箇所
    (カード / og:image / twitter:image / JSON-LD image / sitemap の image:image)。
    """
    return bool(u) and bool(GENERIC_IMAGE_RE.search(u))


# --- 出典ドメインと画像URLの受け入れ (単一情報源) ---------------------------
# アグリゲータの一覧は listing-policy.json の blockedUrlDomains が正。
#
# 2026-09-10 まで、**同じ一覧が6スクリプトに写してあり**、判定関数も
# is_aggregator / is_aggregator_url / _url_contains_aggregator の3通りに
# 割れていた。しかも写しの側だけが agavemaniacs.com を持ち、
# listing-policy.json には入っていなかった。
# 「単一情報源」と名乗りながら、**実際にそれを読むコードが1つも無かった。**
# 画像の受け入れ判定も backfill と enrich に別々にあり、片方だけに
# http:// を弾く行があって 2026-09-08 に事故を出している。ここに寄せる。

def listing_policy():
    """listing-policy.json。壊れていたら黙って通さず落とす。

    出典の判定が空で通ると、アグリゲータのURLが素通りする。
    **黙って0件になるのが最悪**なので、ここは握りつぶさない。
    """
    global _LISTING_POLICY
    if _LISTING_POLICY is None:
        p = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'listing-policy.json')
        with open(p, encoding='utf-8') as f:
            _LISTING_POLICY = json.load(f)
    return _LISTING_POLICY


_LISTING_POLICY = None

AGGREGATOR_DOMAINS = tuple(
    listing_policy().get('blockedUrlDomains', {}).get('domains') or ())
if not AGGREGATOR_DOMAINS:
    raise RuntimeError(
        'listing-policy.json の blockedUrlDomains.domains が空。'
        'アグリゲータ判定が効かなくなるので落とす')

# イベントとは無関係だが og:image に出てくる先。画像だけで弾く。
UNRELATED_IMAGE_DOMAINS = ('jleague.jp', 'static.cdninstagram.com', 'mercari')

# ファイル名で見る共通アセット。GENERIC_IMAGE_RE はパスで見るので両方要る。
# backfill 側だけが sitelogo / noimage / placeholder / cropped- を持っていて、
# enrich 側はそれらを通していた(2026-09-10 に統合。広いほうを採る)。
GENERIC_IMAGE_NAME_RE = re.compile(
    r'/(ogp|ogimage|og_image|og-image|default|logo|sitelogo|share|thumb|main'
    r'|noimage|placeholder)\.(png|jpg|jpeg|webp|gif)(\?|$)'
    r'|/cropped-',  # WordPressサイトアイコン(favicon)へのフォールバック
    re.I)


def is_aggregator_url(url):
    """ホストでもパスでもアグリゲータ名を含んだら True。

    ホストだけを見ると、CDN 経由でパスに入る形を取りこぼす。
    """
    return bool(url) and any(a in url.lower() for a in AGGREGATOR_DOMAINS)


def is_quality_image_url(img_url):
    """imageUrl として受け入れてよいか。書き込む側は必ずここを通す。"""
    if not img_url:
        return False
    # 混在コンテンツ防止。サイトは https なので http の画像は落とされるか警告になる
    if img_url.startswith('http://'):
        return False
    if is_aggregator_url(img_url):
        return False
    if GENERIC_IMAGE_NAME_RE.search(img_url):
        return False
    if is_generic_image_url(img_url):
        return False
    u = img_url.lower()
    return not any(d in u for d in UNRELATED_IMAGE_DOMAINS)


# --- 一覧カード (単一情報源) -------------------------------------------------
# トップ(index.html)・行きたい・ランディング全ページで同じ .event-card を使う。
# 以前はランディング106枚だけ landing-card という別実装で、画像・ステータス
# バッジ・行きたいボタンが無く、status-auto.js も効かなかった。生成もCSSも
# 別だったため片方を直しても他方に効かない状態だった(2026-08-20に統合)。
# 会場は is_vague_venue を通す。通さないと「東京 / 東京」「東京 / 調整中」が出る。

HEART_SVG = ('<svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 '
             '5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 '
             '1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>')


_OG_IMAGE_KEYS = ('og:image:secure_url', 'og:image:url', 'og:image',
                  'twitter:image')


def extract_og_image(html, base_url=None):
    """ページのHTMLから代表画像のURLを取る。優先順は _OG_IMAGE_KEYS。

    backfill-images.py が BeautifulSoup 版、fetch-event-images.py が
    正規表現版を別々に持っていて、拾う対象が違った(2026-09-10 に統合)。
    正規表現版は og:image しか見ず、secure_url / twitter:image を落とす。
    **同じ「代表画像を取る」という規則が、取る対象の違う2実装だった。**

    sitelib は bs4 に依存させない(全ジェネレータが import するため)ので、
    属性の順序を問わない正規表現で書く。base_url を渡すと相対URLを解決する。
    """
    if not html:
        return None
    for key in _OG_IMAGE_KEYS:
        pat = re.compile(
            r'<meta\b(?=[^>]*\b(?:property|name)\s*=\s*["\']'
            + re.escape(key) + r'["\'])'
            r'[^>]*\bcontent\s*=\s*["\']([^"\']+)["\']',
            re.I)
        for m in pat.finditer(html):
            # &amp; を戻す。戻さないと ?a=1&amp;b=2 のURLをそのまま取りに行く
            import html as _htmllib
            u = _htmllib.unescape(m.group(1).strip())
            if not u:
                continue          # 空の og:image で打ち切らない。次を見る
            if base_url:
                from urllib.parse import urljoin
                return urljoin(base_url, u)
            return u if u.startswith('http') else ''
    return None


def page_text_blob(html):
    """頁の散文。本文 + title/og:title/og:description/description。

    出典が「その回の頁か」を見るための素材。check-cancelled.py が
    strip_html + meta_texts で持っていたものを sitelib に寄せた
    (2026-09-10)。enrich_events.py が **同じ判定を持たないまま** url を
    書いていたため、別の回の記事(4月開催)と無関係のサイトを掴んだ
    2件が本番に出た。書く側と見張る側で規則が違うと、
    書いた直後に監査が鳴るだけで、事故は止まらない。
    """
    h = re.sub(r'(?is)<(script|style|noscript)\b.*?</\1>', ' ', html or '')
    h = re.sub(r'(?s)<!--.*?-->', ' ', h)
    body = re.sub(r'<[^>]+>', ' ', h)
    parts = [body]
    t = re.search(r'(?is)<title[^>]*>(.*?)</title>', html or '')
    if t:
        parts.append(re.sub(r'<[^>]+>', ' ', t.group(1)))
    for prop in ('og:title', 'og:description', 'description'):
        for m in re.finditer(
                r'(?i)<meta[^>]+(?:property|name)=["\']' + re.escape(prop)
                + r'["\'][^>]+content=["\']([^"\']*)', html or ''):
            parts.append(m.group(1))
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', ' '.join(parts))).strip()


def page_dates(html):
    """(散文で名乗った日付の数, 全書式で拾った (月,日) の集合)

    **判定は非対称にする。** 「日付を名乗っている頁か」は「◯月◯日」だけで
    見る(スラッシュ形は画像パス /2026/09/ やページ送りにも出るので
    名乗りの根拠にならない)。「この回の日付が出ているか」は全書式で見る。
    鳴りにくく・消えやすい側に倒れる。実測(2026-09-08・巡回23件)で
    非対称なら誤検知0、両方を狭い側で見ると 2026.10.10 表記の回が、
    両方を広い側で見ると公式トップ頁が誤検知になった。
    """
    blob = page_text_blob(html)
    return len(find_month_days(blob, kanji_only=True)), find_month_days(blob)


def page_matches_event(html, event):
    """出典の頁にその回の開催日が出てくるか。(datesNamed, eventDateSeen)

    eventDateSeen が None は「会期が分からないので判定しない」。
    **名乗り数での足切りはここでやらない。** 呼ぶ側の判断
    (page_is_wrong_edition / 監査)に残す。check-cancelled.py が
    cancel-watch.json に書く値と同じ意味にしておく。
    """
    named, found = page_dates(html)
    span = event_month_days(event) if event is not None else set()
    return named, (bool(span & found) if span else None)


def page_is_wrong_edition(html, event):
    """**url や imageUrl を書く前に呼ぶ。** 別の回・無関係の頁なら True。

    頁が散文で日付を1つも名乗っていない(告知が画像だけ)回は判定しない。
    鳴りにくく・消えやすい側に倒す。監査 source_page_wrong_edition と同じ条件。
    """
    named, seen = page_matches_event(html, event)
    return named >= 1 and seen is False


def page_prefectures(html):
    """頁の散文が名乗っている都道府県の集合。接尾辞の有無は問わない。"""
    blob = page_text_blob(html)
    return {p for p in PREF_TO_REGION if p in blob}


def page_is_wrong_place(html, event):
    """**頁から admission / access / time / venue を採る前に呼ぶ。** 別の土地の頁なら True。

    頁が都道府県を1つも名乗っていない回は判定しない(False)。
    page_is_wrong_edition と同じ形で、鳴りにくい側に倒す。

    日付の検査だけでは足りない。名前が一般的な回は、**日付を散文で
    名乗っていない別サイト**を掴むと page_is_wrong_edition が
    datesNamed=0 で判定を降り、素通りする。2026-09-12、徳島の
    「Plants marché」に andplants.jp(東京・中目黒のマルシェ)の
    入場料 3,300円 と「東京メトロ 中目黒駅隣接」が入った。
    検索の再試行が `<名称> 公式` まで文脈を捨てるので、
    一般名の回では土地だけが唯一の手掛かりになる。
    """
    pref = (event or {}).get('prefecture') or ''
    pref = pref.rstrip('都道府県') if pref not in PREF_TO_REGION else pref
    if not pref or pref not in PREF_TO_REGION:
        return False
    named = page_prefectures(html)
    return bool(named) and pref not in named


def head_open(og_type='website'):
    """全ページ共通の <head> 冒頭を返す。**まだ format されていない雛形。**

    プレースホルダは {title} {description} {keywords} {canonical}
    {root} {robots_meta}。呼び出し側が自分の残り(JSON-LD・ページ固有CSS・
    追加のscript)を継ぎ足して format する。

    build-guides.py と generate-landing-pages.py が同じ24行を別々に持ち、
    ガイド側は root を `../` で直書き、CSS版数はどちらも
    `20260611a` と書いてから文字列置換で差し替えていた
    (2026-09-10 に統合)。**版数のような「必ず変わる値」を雛形に
    直書きすると、置換を忘れた側が古い版で出る。**ここでは直に埋める。
    """
    return (
        '<!DOCTYPE html>\n'
        '<html lang="ja">\n'
        '<head>\n'
        '  <script async src="https://www.googletagmanager.com/gtag/js?id='
        + GA_ID + '"></script>\n'
        '  <script>window.dataLayer=window.dataLayer||[];'
        'function gtag(){{dataLayer.push(arguments);}}'
        "gtag('js',new Date());gtag('config','" + GA_ID + "');</script>\n"
        '  <meta charset="UTF-8">\n'
        '  {robots_meta}\n'
        '  <link rel="canonical" href="{canonical}">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '  <title>{title} | アガベイベントナビ</title>\n'
        '  <meta name="description" content="{description}">\n'
        '  <meta name="keywords" content="{keywords}">\n'
        '  <meta property="og:title" content="{title} | アガベイベントナビ">\n'
        '  <meta property="og:description" content="{description}">\n'
        '  <meta property="og:type" content="' + og_type + '">\n'
        '  <meta property="og:url" content="{canonical}">\n'
        '  <meta property="og:image" content="' + DOMAIN + '/og-image.png">\n'
        '  <meta name="twitter:card" content="summary_large_image">\n'
        '  <link rel="icon" type="image/svg+xml" href="{root}favicon.svg?v=2">\n'
        '  <link rel="icon" type="image/x-icon" href="{root}favicon.ico?v=2">\n'
        '  <link rel="apple-touch-icon" sizes="180x180" href="{root}apple-touch-icon.png?v=2">\n'
        '  <link rel="manifest" href="{root}manifest.webmanifest?v=2">\n'
        '  <meta name="theme-color" content="#111">\n'
        '  <link rel="alternate" type="application/rss+xml" '
        'title="アガベイベントナビ" href="{root}rss.xml">\n'
        '  <link rel="stylesheet" href="{root}style.css?v=' + CSS_VERSION + '">\n')


def _attr(s):
    return html_escape(s)


def event_card_html(e, heading='h3', eager=False, today=None, compact=False,
                    extra_meta=''):
    """一覧カード1枚のHTML。

    heading: カード見出しのタグ。1ページに何十枚も並ぶので既定は h3。
    eager:   先頭カード(LCP候補)だけ True。画像を遅延させない。
    compact: 説明文を省く。終了イベントの節は既定で折り畳まれており、
             説明文がページ重量の大半を占めるため(region/kanto は73件)。
    extra_meta: メタ行に足すHTML。/new/ の「掲載: 2026.08.10」等。
    """
    slug = e.get('slug') or ''
    if not slug:
        return ''
    name = e.get('name') or slug
    pref = e.get('prefecture') or ''
    region = e.get('region') or pref_to_region(pref) or ''
    tags = ','.join(e.get('tags') or [])
    d, de = event_span(e)
    img = e.get('imageUrl') or ''
    if img and (not img.startswith('https://') or is_generic_image_url(img)):
        img = ''   # 混在コンテンツとサイト共通アセットはカードに出さない

    if img:
        perf = ('decoding="async" fetchpriority="high"' if eager
                else 'loading="lazy" decoding="async"')
        thumb = (f'<div class="event-thumb"><img src="{_attr(img)}" alt="{_attr(name)}" '
                 f'width="640" height="640" {perf} referrerpolicy="no-referrer" '
                 f'onerror="this.parentElement.classList.add(\'event-no-image\');this.remove();">'
                 f'</div>')
    else:
        thumb = no_image_thumb(e)

    desc = '' if compact else (e.get('description') or '').strip()
    desc_html = f'<p class="event-description">{html_escape(desc)}</p>' if desc else ''

    # 会場名は venue_display で住所の括弧書きを落とす。生の location だと
    # 「TITANOTA BASE（埼玉県草加市西町1270-3）」がカードに丸ごと出る。
    venue = (e.get('location') or '').strip()
    meta = f'<span class="event-region">{html_escape(pref or region)}</span>'
    if not is_vague_venue(venue):
        meta += f'<span class="event-venue">{html_escape(venue_display(venue))}</span>'
    meta += extra_meta

    status = 'past' if event_phase(e, today) == 'past' else 'upcoming'
    cancel = cancel_label(e)
    cancel_cls = ' event-cancelled' if cancel else ''
    cancel_badge = (f'<span class="event-cancel-badge">{html_escape(cancel)}</span>'
                    if cancel else '')
    return (
        f'<div class="event-card{cancel_cls}" data-tags="{_attr(tags)}" data-status="{status}"'
        f' data-region="{_attr(region)}" data-pref="{_attr(pref)}" data-slug="{_attr(slug)}"'
        f' data-date="{_attr(d)}" data-date-end="{_attr(de if de != d else "")}"'
        f' data-added-date="{_attr(e.get("addedDate") or "")}">'
        f'{thumb}'
        f'<button class="fav-btn" onclick="toggleFav(event,\'{_attr(slug)}\')" aria-label="行きたい">'
        f'{HEART_SVG}</button>'
        f'<div class="event-card-body">'
        f'<div class="event-header"><span class="event-date">{html_escape(compact_date(e))}</span>'
        f'{cancel_badge}<span class="event-status"></span></div>'
        f'<{heading} class="event-title"><a class="event-title-link" href="/events/{_attr(slug)}.html">'
        f'{html_escape(name)}</a></{heading}>'
        f'{desc_html}'
        f'<div class="event-meta-row">{meta}</div>'
        f'</div>'
        f'<div class="card-fav-bar" onclick="event.stopPropagation()">{HEART_SVG}'
        f'<span>行きたい</span></div>'
        f'</div>'
    )


def event_grid_html(evs, grid_id, extra_class='', grid_attrs='',
                    heading='h3', eager_first=False, today=None, compact=False):
    """カードのグリッド1つ。空でも要素は出す(status-auto.js が振り分け先に使う)。"""
    cards = ''.join(event_card_html(e, heading=heading, compact=compact,
                                    eager=(eager_first and i == 0), today=today)
                    for i, e in enumerate(evs))
    cls = f'events-grid {extra_class}'.strip()
    hidden = '' if evs else ' style="display:none"'
    return f'<div class="{cls}" id="{grid_id}"{grid_attrs}{hidden}>{cards}</div>'


def section_heading_html(text, note='', tag='h2', el_id=''):
    """節の見出し。その節に何が載っているかを見出し自身に書く。"""
    note_html = (f'<span class="section-heading-note">{html_escape(note)}</span>'
                 if (note and text) else '')
    id_attr = f' id="{el_id}"' if el_id else ''
    hidden = '' if text else ' style="display:none"'
    return (f'<{tag} class="section-heading section-heading--sub"{id_attr}{hidden}>'
            f'{html_escape(text)}{note_html}</{tag}>')


def past_range_label(evs):
    """終了イベント群の範囲。「2026年2月〜8月・31件」の形。"""
    ends = sorted((event_span(e)[1] for e in evs if event_span(e)[1]))
    if not ends:
        return ''
    a, b = ends[0], ends[-1]
    if a[:4] == b[:4]:
        span = (f'{int(a[:4])}年{int(a[5:7])}月' if a[:7] == b[:7]
                else f'{int(a[:4])}年{int(a[5:7])}月〜{int(b[5:7])}月')
    else:
        span = f'{int(a[:4])}年{int(a[5:7])}月〜{int(b[:4])}年{int(b[5:7])}月'
    return f'{span}・{len(evs)}件'


def no_image_thumb(e):
    """画像が無い回のサムネ枠。

    以前は「NO IMAGE」と出していたが、これは訪問者には壊れて見えるだけで
    何の情報も無い。imageUrl が無い開催予定は常時60〜80件あり、
    新規イベントは必ず画像なしで入るので件数はゼロにならない。
    件数を追うのをやめて、枠のほうを情報として成立させる。
    県名と日付はカードのデータに既にあるので、それを大きく置く。
    """
    pref = (e.get('prefecture') or '').strip()
    if not pref:
        pref = (pref_to_region(e.get('prefecture') or '') or e.get('region') or '').strip()
    d = (e.get('date') or '').strip()
    label = ''
    if len(d) >= 10:
        label = f'{int(d[5:7])}.{int(d[8:10])}'
    parts = []
    if pref:
        parts.append(f'<span class="eni-pref">{html_escape(pref)}</span>')
    if label:
        parts.append(f'<span class="eni-date">{label}</span>')
    return f'<div class="event-thumb event-no-image">{"".join(parts)}</div>'
