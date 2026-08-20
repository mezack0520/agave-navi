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
from datetime import datetime, timezone, timedelta

# --- 定数 ---
DOMAIN = 'https://agave-navi.com'
JST = timezone(timedelta(hours=9))
CSS_VERSION = '20260730k'
JS_VERSION = '20260810a'
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
              'ビカクシダ':'platycerium','アロイド':'aroid','着生植物':'epiphyte'}
VENUE_ROMAJI = {'五反田TOCビル 13階':'gotanda-toc','サンシャインシティ':'sunshine-city',
                '久屋大通庭園フラリエ':'flarie','研究学園駅前公園（つくば市）':'kenkyu-gakuen-park',
                '千住本氷川神社':'senju-hikawa-jinja'}

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
    if not s: return ''
    nfkd = unicodedata.normalize('NFKD', s).encode('ascii','ignore').decode('ascii').lower()
    slug = re.sub(r'[^a-z0-9]+', '-', nfkd).strip('-')[:50]
    if slug: return slug
    h = hashlib.md5(s.encode('utf-8')).hexdigest()[:8]
    return f'{kind}-{h}'

def pref_slug(p): return PREF_ROMAJI.get(p) or safe_slug(p, 'pref')
def region_slug(r): return REGION_ROMAJI.get(r) or safe_slug(r, 'region')
def tag_slug(t): return TAG_ROMAJI.get(t) or safe_slug(t, 'tag')
def venue_slug(v): return VENUE_ROMAJI.get(v) or safe_slug(v, 'v')

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


def is_vague_venue(v):
    """会場として使えない値か。

    完全一致の VAGUE_VENUES だけでは「金沢（会場未確定）」のように
    未定であることを括弧書きで補った値を取りこぼす。
    地図・JSON-LDのPlace・FAQに、会場名として出してはいけない値を1か所で判定する。
    """
    v = (v or '').strip()
    if not v:
        return True
    return v in VAGUE_VENUES or bool(_VAGUE_MARKER.search(v))


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
