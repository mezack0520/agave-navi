"""データで見る植物イベント — events.json からビルド時に統計を計算する動的記事。
ビルドのたびに最新データで本文が更新されるため、内容が古くならない。"""
import json, os
from datetime import datetime, timezone, timedelta

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_JST = timezone(timedelta(hours=9))
_NOW = datetime.now(_JST)

with open(os.path.join(_ROOT, 'events.json'), encoding='utf-8') as _f:
    _EVS = json.load(_f)

_Y = '2026'
_yr = [e for e in _EVS if (e.get('date') or '').startswith(_Y)]
_today = _NOW.strftime('%Y-%m-%d')
_up = [e for e in _yr if (e.get('date') or '') >= _today]

# 月別
_by_m = {}
for _e in _yr:
    _m = int(_e['date'][5:7])
    _by_m[_m] = _by_m.get(_m, 0) + 1
_peak_m = max(_by_m, key=_by_m.get) if _by_m else 0

# 都道府県
_by_p = {}
for _e in _yr:
    _p = _e.get('prefecture')
    if _p: _by_p[_p] = _by_p.get(_p, 0) + 1
_top_p = sorted(_by_p.items(), key=lambda x: -x[1])[:5]

# 入場料
_adm = [e for e in _yr if (e.get('admission') or '').strip()]
_free = [e for e in _adm if '無料' in e['admission']]
_free_pct = round(100 * len(_free) / len(_adm)) if _adm else 0

# 土日率
_wk = 0
for _e in _yr:
    try:
        _d0 = datetime.strptime(_e['date'], '%Y-%m-%d')
        _d1 = datetime.strptime(_e.get('dateEnd') or _e['date'], '%Y-%m-%d')
        _dd = _d0
        _hit = False
        while _d0 <= _d1:
            if _d0.weekday() >= 5: _hit = True; break
            _d0 += timedelta(days=1)
        if _hit: _wk += 1
    except ValueError:
        pass
_wk_pct = round(100 * _wk / len(_yr)) if _yr else 0

# 複数日開催率
_multi = sum(1 for e in _yr if e.get('dateEnd') and e['dateEnd'] != e['date'])
_multi_pct = round(100 * _multi / len(_yr)) if _yr else 0

# カテゴリ
_cats = {'即売会': 0, 'マルシェ': 0, '展示会': 0, '大型': 0}
for _e in _yr:
    for _t in (_e.get('tags') or []):
        if _t in _cats: _cats[_t] += 1

# シリーズ(同名イベントの複数回開催) — 正規化はsitelibと共通
try:
    from sitelib import normalize_series_name as _norm
except ImportError:
    import sys as _sys
    _sys.path.insert(0, os.path.join(_ROOT, 'scripts'))
    from sitelib import normalize_series_name as _norm
_series = {}
for _e in _EVS:
    _k = _norm(_e.get('name'))
    if len(_k) >= 4:
        _series.setdefault(_k, []).append(_e)
_series_multi = {k: v for k, v in _series.items() if len(v) >= 2}

# 最混雑週末: 同じ土曜に重なるイベント数の最大
_sat_count = {}
for _e in _yr:
    try:
        _d0 = datetime.strptime(_e['date'], '%Y-%m-%d')
        _d1 = datetime.strptime(_e.get('dateEnd') or _e['date'], '%Y-%m-%d')
        while _d0 <= _d1:
            if _d0.weekday() == 5:
                _key = _d0.strftime('%Y-%m-%d')
                _sat_count[_key] = _sat_count.get(_key, 0) + 1
            _d0 += timedelta(days=1)
    except ValueError:
        pass
_busy = sorted(_sat_count.items(), key=lambda x: -x[1])[:3]
_busy_txt = '、'.join(f"{datetime.strptime(d,'%Y-%m-%d').month}月{datetime.strptime(d,'%Y-%m-%d').day}日({n}件)" for d, n in _busy)

# 会期長
_len_dist = {1: 0, 2: 0, 3: 0}
for _e in _yr:
    try:
        _d0 = datetime.strptime(_e['date'], '%Y-%m-%d')
        _d1 = datetime.strptime(_e.get('dateEnd') or _e['date'], '%Y-%m-%d')
        _n = (_d1 - _d0).days + 1
        _len_dist[1 if _n == 1 else (2 if _n == 2 else 3)] += 1
    except ValueError:
        pass

_upd = _NOW.strftime('%Y年%m月%d日')
_top_p_txt = '、'.join(f'{p}({n}件)' for p, n in _top_p)
_m_rows = '\n'.join(f'- **{m}月**: {_by_m[m]}件' for m in sorted(_by_m))

META = {
    'slug': 'event-data-2026',
    'title': f'データで見る{_Y}年の植物イベント: 開催数・地域・入場料の傾向',
    'description': f'当サイトに掲載した{_Y}年のアガベ・塊根植物・多肉植物イベント{len(_yr)}件のデータから、月別の開催数、地域分布、入場料、開催曜日の傾向を集計しました。{_upd}時点。',
    'keywords': f'植物イベント,{_Y},統計,開催数,アガベ,即売会,データ',
    'category': 'イベント',
    'read_min': 6,
    'lead': f'本記事は、当サイトのイベントデータベースに掲載している{_Y}年開催の植物イベント{len(_yr)}件(集計: {_upd}時点)を独自に集計したものです。「いつ・どこで・どんな形式の」イベントが多いのかを、実数で把握できます。掲載ベースの集計のため日本全国の全イベントを網羅するものではありませんが、参加計画の土台として使える規模のサンプルです。',
}
RELATED = [
    ('開催予定のイベント一覧', '/'),
    ('今月のイベント', '/this-month/'),
    ('植物イベントの種類と選び方', '/guides/event-types-guide.html'),
    ('即売会の歩き方チェックリスト', '/guides/sokubaikai-tips.html'),
]
CONTENT = f"""
## {_Y}年の掲載イベントは{len(_yr)}件

当サイトが{_Y}年開催分として掲載しているイベントは、本記事の集計時点で**{len(_yr)}件**です。このうち今後開催予定のものは{len(_up)}件あります。クラフト系や園芸全般のフェアは原則対象外で、アガベ・塊根植物(コーデックス)・多肉植物・ビザールプランツが主役のイベントに絞って収集しています(掲載基準は[サイトについて](/about.html)を参照)。

## 月別の開催数 — ピークは{_peak_m}月

{_m_rows}

春(3〜5月)と秋(9〜11月)に開催が集中する傾向は園芸イベント全般と共通ですが、植物イベントでは**真夏(7・8月)にも屋内会場での開催が続く**のが特徴です。アガベや塊根植物は夏型(夏に生育する)植物が多く、植え替え・育成シーズンと重なるためと考えられます。

!!! tip
    猛暑期の屋外マルシェは午前中の来場がおすすめです。植物にとっても、購入後に車内へ長時間置くことは大きなダメージになります(夏の車内は短時間で50℃超)。

## 地域分布 — 上位は{_top_p[0][0] if _top_p else ''}

掲載イベントの開催地上位は **{_top_p_txt}** です。

大都市圏に集中する一方で、当サイトでは{len(_by_p)}都道府県のイベントを掲載しており、地方開催も着実に増えています。お住まいの地域のイベントは[都道府県別一覧](/pref/)から、近隣地域まで広げる場合は[地域別一覧](/region/)から確認できます。

## 入場料 — 約{_free_pct}%が入場無料

入場料の情報が確認できたイベント{len(_adm)}件のうち、**約{_free_pct}%が入場無料**でした。有料の場合も数百円〜2,000円程度が中心で、先行入場(アーリーチケット)だけ有料・一般入場は無料という形式も定着しています。

!!! note
    先行入場券は人気株の争奪戦に参加するためのもので、ゆっくり見たいだけなら一般入場で十分なことがほとんどです。

## 開催曜日と会期

- 土日いずれかを含むイベント: **約{_wk_pct}%**
- 複数日開催: **約{_multi_pct}%**

大半が週末開催のため、人気イベントが同じ週末に重なることも珍しくありません。[今週末のイベント](/this-weekend/)と[カレンダー](/calendar.html)を併用すると、回る順番の計画が立てやすくなります。

## 形式別の内訳

- 即売会: {_cats['即売会']}件
- マルシェ: {_cats['マルシェ']}件
- 大型イベント: {_cats['大型']}件
- 展示会: {_cats['展示会']}件

(1つのイベントが複数形式に該当する場合があります)

即売会が圧倒的多数を占めます。形式ごとの違いと選び方は[植物イベントの種類と選び方](/guides/event-types-guide.html)で詳しく解説しています。

## 1日開催か、複数日開催か

- 1日開催: **{_len_dist[1]}件**
- 2日間: **{_len_dist[2]}件**
- 3日以上: **{_len_dist[3]}件**

1日開催が中心ですが、大型イベントや百貨店・商業施設でのポップアップは長めの会期を取る傾向があります。複数日イベントは「初日に品揃え・最終日に価格」という回り方の選択肢があるのも特徴です。

## 同じ週末にイベントが重なる

{_Y}年で最もイベントが重なった土曜日は **{_busy_txt}** でした。

愛好家にとっては嬉しい悩みですが、遠征を伴う場合は「どちらの会場に朝イチで入るか」が重要な判断になります。出店者リストを見比べて、目当ての生産者がいる方を優先するのが定石です。

## リピート開催されるイベントが多い

当サイトのデータベースでは、**{len(_series_multi)}シリーズ**のイベントが複数回掲載されています(vol.◯や第◯回など、同名イベントの繰り返し開催)。植物イベントは単発で終わらず、年1〜2回ペースで定着するものが多いのが特徴です。気になるイベントを逃した場合も、各イベント詳細ページの「開催履歴・関連回」から次回の動向を追えます。

## この集計について

- 集計対象: 当サイト掲載の{_Y}年開催イベント(集計: {_upd}時点)
- 本記事はイベントデータベースから自動集計しており、データ更新のたびに数値も更新されます
- 掲載ベースの集計であり、日本全国の全イベント数を示すものではありません
"""
