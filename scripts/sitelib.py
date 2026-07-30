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
CSS_VERSION = '20260730d'
JS_VERSION = '20260707b'
ADSENSE_CLIENT = 'ca-pub-0790348660030345'
GA_ID = 'G-NKY8V1H8HY'

WEEKDAYS_JA = ['月', '火', '水', '木', '金', '土', '日']

# 「会場」として意味をなさない曖昧値(venueページ・同会場セクションの対象外)
VAGUE_VENUES = {'東京', '東京都内', '都内', '大阪', '名古屋', '会場未定', '未定'}

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
      <a href="/" class="logo"><span class="logo-en">AGAVE EVENT NAVI</span><span class="logo-jp">アガベイベントナビ</span></a>
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
