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

# --- 定数 ---
DOMAIN = 'https://agave-navi.com'
JST = timezone(timedelta(hours=9))
CSS_VERSION = '20260824c'
JS_VERSION = '20260829a'
ADSENSE_CLIENT = 'ca-pub-0790348660030345'
GA_ID = 'G-NKY8V1H8HY'

WEEKDAYS_JA = ['月', '火', '水', '木', '金', '土', '日']

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
CARDS_PER_PAGE = 12    # 一覧の初期表示件数。list-ui.js と同値
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
    """一覧・フィード・ランディングの「開催予定」側に出すか。開催中を含む。"""
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

def site_header(root=''):
    """共通ヘッダー。root: ルートへの相対プレフィックス('', '../' 等)。絶対パス推奨のため通常は''"""
    return f'''  <header class="header">
    <div class="header-inner">
      <a href="/" class="logo"><span class="logo-en">AGA NAVI</span><span class="logo-jp">アガベイベントナビ</span></a>
      <div class="header-actions">
        <a href="/ikitai.html" class="ikitai-blob-btn"><span class="blob-bg"></span>
          <svg class="ikitai-heart" viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>
          <span class="ikitai-label">行きたい</span></a>
      </div>
    </div>
  </header>'''

def site_footer():
    """正規フッター(全ページ共通・単一情報源)。404含む全静的ページは sync-footers.py で同期。"""
    year = now_jst().year
    return f"""  <footer class="footer">
    <div class="footer-inner">
      <div class="footer-logo">
        <span class="logo-en">AGAVE EVENT NAVI</span>
      </div>
      <nav class="footer-nav">
        <a href="/">イベント一覧</a>
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


def is_generic_image_url(u):
    """サイト共通アセット(ロゴ・OGP既定・ファビコン・テーマ内画像)なら True。

    True の値を imageUrl に入れてはいけない。露出は5箇所
    (カード / og:image / twitter:image / JSON-LD image / sitemap の image:image)。
    """
    return bool(u) and bool(GENERIC_IMAGE_RE.search(u))


# --- 一覧カード (単一情報源) -------------------------------------------------
# トップ(index.html)・行きたい・ランディング全ページで同じ .event-card を使う。
# 以前はランディング106枚だけ landing-card という別実装で、画像・ステータス
# バッジ・行きたいボタンが無く、status-auto.js も効かなかった。生成もCSSも
# 別だったため片方を直しても他方に効かない状態だった(2026-08-20に統合)。
# 会場は is_vague_venue を通す。通さないと「東京 / 東京」「東京 / 調整中」が出る。

HEART_SVG = ('<svg viewBox="0 0 24 24"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 '
             '5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 '
             '1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>')


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
                 f'width="640" height="360" {perf} referrerpolicy="no-referrer" '
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
    return (
        f'<div class="event-card" data-tags="{_attr(tags)}" data-status="{status}"'
        f' data-region="{_attr(region)}" data-pref="{_attr(pref)}" data-slug="{_attr(slug)}"'
        f' data-date="{_attr(d)}" data-date-end="{_attr(de if de != d else "")}"'
        f' data-added-date="{_attr(e.get("addedDate") or "")}">'
        f'{thumb}'
        f'<button class="fav-btn" onclick="toggleFav(event,\'{_attr(slug)}\')" aria-label="行きたい">'
        f'{HEART_SVG}</button>'
        f'<div class="event-card-body">'
        f'<div class="event-header"><span class="event-date">{html_escape(compact_date(e))}</span>'
        f'<span class="event-status"></span></div>'
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
