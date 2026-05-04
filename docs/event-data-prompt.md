# イベント情報収集プロンプト

## 概要

新しいイベントを `events.json` に追加する際に使うプロンプトです。
Instagram投稿や公式サイトの情報を元に、必要なフィールドを正確に埋めます。

---

## 使い方

以下のプロンプトをClaude等のAIに渡し、イベント情報のURL（InstagramやWebサイト）を添えて実行してください。

---

## プロンプト本文

```
あなたはアガベ・多肉植物・塊根植物のイベント情報を収集するアシスタントです。
以下の情報源から、events.json に追加するためのJSON形式でイベント情報を出力してください。

### 入力
情報源URL（Instagram投稿、公式サイト、X/Twitter投稿など）を提供します。

### 出力形式
以下のJSONフォーマットで出力してください。確認できない項目は空文字 "" にしてください。
推測や補完はせず、情報源に明記されている情報だけを記載してください。

{
  "slug": "イベント名の英語スラッグ-年",
  "name": "イベント正式名称",
  "date": "YYYY-MM-DD（開始日）",
  "dateEnd": "YYYY-MM-DD（終了日、1日開催なら開始日と同じ）",
  "dateDisplay": "YYYY.MM.DD（表示用、複数日なら YYYY.MM.DD-DD）",
  "venue": "会場名",
  "location": "会場名（venueと同じ）",
  "prefecture": "都道府県名（県は省略: 東京、大阪、福岡 等）",
  "region": "地域（北海道/東北/関東/東海/北陸/関西/中国/四国/九州/沖縄 のいずれか）",
  "mapQuery": "Google Mapsで検索するクエリ（会場名 or 住所）",
  "description": "イベント概要（100〜200文字程度。会場・内容・特徴を含む）",
  "time": "開催時間（例: 10:00〜16:00）",
  "admission": "入場料（無料/500円/前売1000円 等）",
  "tags": ["即売会", "マルシェ"],
  "sourceUrl": "公式サイトURL or 公式InstagramプロフィールURL",
  "instagramPostId": "Instagram投稿のID（/p/XXXXX/ のXXXXX部分）",
  "instagramUrl": "Instagram投稿の完全URL（任意）",
  "imageUrl": "ヒーロー画像URL（任意。空でもOK — 後で自動補完される）",
  "url": "公式情報URL（任意。空でもOK — 後で自動補完される）",
  "addedDate": "今日の日付 YYYY-MM-DD",
  "status": "upcoming",
  "eventStatus": "confirmed"
}

### slug のルール
- イベント名をローマ字/英語でハイフン区切り
- 末尾に開催年を付ける（例: fukuoka-green-party-6th-2026）
- 同名イベントの回数がある場合は含める
- 小文字のみ、特殊文字なし

### region の判定表
| 都道府県 | region |
|---------|--------|
| 北海道 | 北海道 |
| 青森/岩手/宮城/秋田/山形/福島 | 東北 |
| 茨城/栃木/群馬/埼玉/千葉/東京/神奈川 | 関東 |
| 愛知/静岡/岐阜/三重 | 東海 |
| 新潟/富山/石川/福井/山梨/長野 | 北陸 |
| 滋賀/京都/大阪/兵庫/奈良/和歌山 | 関西 |
| 鳥取/島根/岡山/広島/山口 | 中国 |
| 徳島/香川/愛媛/高知 | 四国 |
| 福岡/佐賀/長崎/熊本/大分/宮崎/鹿児島 | 九州 |
| 沖縄 | 沖縄 |

### tags の選択肢
主要タグ（1〜3個を選択）:
- 即売会（植物の販売がメイン）
- マルシェ（フードや雑貨も含む複合イベント）
- 大型（100ブース以上 or 大規模会場）
- 展示会（展示・鑑賞がメイン）
- ワークショップ（体験型）
- ポップアップ（期間限定ショップ）
- フリーマーケット（個人出店中心）

### description のガイドライン
- 「〇〇県〇〇市・△△（会場名）で開催される」で始める
- イベントの特徴や内容を簡潔に説明
- 閲覧者に有用な情報（規模、出店ジャンル、特色）を優先
- 確認できない情報は書かない
- 100〜200文字を目安

### 注意事項
- 情報源に記載がない項目は必ず空文字にする
- 日付が「〇月上旬」等の曖昧な表現の場合、dateは空文字にしてdateDisplayに原文を記載
- 入場料の記載がなければ空文字（「無料」と推測しない）
- Instagram投稿がある場合、instagramPostId は必ず抽出する
- imageUrl と url は **任意**(空でもOK)
  - 追加後、毎週火曜の自動 enrichment(Brave Search API + GitHub Actions)が
    公式サイトを検索して og:image / 公式URL を自動補完する
  - 手で先に入れる場合は:
    1. 公式サイトの og:image (View Source で `<meta property="og:image"` を探す)
    2. 公式サイトのメインビジュアル(横長16:9前後・1200px以上推奨)
    3. ブラウザで直接開いて画像が表示されることを確認
- **aggregator系URLを url / sourceUrl に入れない**(品質劣化の元):
  - 入れない: nextmeet.app / botanical-zone.tokyo / leaf-laboratory.com /
    pukubook.jp / tochinavi.net / fukuoka-now.com / churatoku.net
  - 入れてOK: イベント主催者の公式サイト、公式Instagramプロフィール
- sourceUrl は情報の出典として記録するだけ(任意、Instagramプロフィール等可)
```

### imageUrl が見つからない場合

そのままでもイベントは追加できますが、ヒーロー画像欄が空になります。後から自動補完を試すには:

```bash
# 該当slugだけ自動取得を試す(url/sourceUrlからog:imageを抽出)
python3 scripts/backfill-images.py --slug <slug>
```

毎週日曜は GitHub Actions の "Backfill Event Images" が自動実行されます。

---

## 追加後のビルド手順

```bash
# events.json にエントリを追加した後
python3 build-detail-pages.py

# 特定のイベントだけ生成する場合
python3 build-detail-pages.py --slug イベントのslug

# プレビュー（ファイル書き出しなし）
python3 build-detail-pages.py --dry-run
```

---

## 複数イベント一括追加の場合

プロンプトに以下を追加:

```
以下の複数のイベント情報を、それぞれJSON形式で出力してください。
最終的に配列 [] で囲んで出力してください。

[情報源URL1]
[情報源URL2]
...
```

出力されたJSONを `events.json` の配列に追加し、`build-detail-pages.py` を実行。
