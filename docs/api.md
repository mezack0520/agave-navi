# Public API / フィード一覧

アガベイベントナビ(agave-navi.com)は静的サイトですが、機械可読なデータフィードを公開しています。
イベント情報の自動取り込みや独自アプリでの利用が可能です。

## events.json (JSON API)

- URL: https://agave-navi.com/events.json
- フォーマット: JSON配列
- 更新頻度: イベント追加時(GitHub Actionsで自動更新)
- ライセンス: 個人・非営利利用は自由。商用利用時はクレジット表記推奨。

### スキーマ

```json
{
  "slug": "event-name-2026",          // 一意ID(URLにも使用)
  "name": "イベント名",
  "date": "2026-04-20",                // YYYY-MM-DD
  "dateEnd": "2026-04-21",             // 終了日(単日なら date と同じ)
  "dateDisplay": "2026.04.20-21",      // 表示用
  "location": "会場名",
  "prefecture": "東京",                // 都道府県(漢字)
  "region": "関東",                    // 地域(関東/関西/東海/九州/中国/四国/北海道/東北/北陸)
  "description": "説明文",
  "tags": ["即売会"],
  "status": "upcoming",                // upcoming | ongoing | past
  "url": "https://...",                // 公式URL or IG投稿URL
  "imageUrl": "https://..."            // ヒーロー画像(任意)
}
```

## RSS

- 全体: https://agave-navi.com/rss.xml
- 地域別: https://agave-navi.com/feeds/region-{slug}.xml
  - 例: `region-kanto.xml`, `region-kansai.xml`, `region-tokai.xml` 他、9地方
- タグ別: https://agave-navi.com/feeds/tag-{slug}.xml
  - 例: `tag-sokubaikai.xml`, `tag-marche.xml` 他

## iCalendar (.ics)

カレンダーアプリ(Google Calendar / Apple Calendar / Outlook)で購読可能。

- 全イベント: https://agave-navi.com/events.ics
- 開催予定のみ: https://agave-navi.com/upcoming.ics
- 今月のみ: https://agave-navi.com/this-month.ics

## CSV

- https://agave-navi.com/events.csv
- BOM付UTF-8、Excel/Numbers/Googleスプレッドシートで直接開けます。

## 利用例

```bash
# 開催予定の上位10件取得
curl -s https://agave-navi.com/events.json | \
  jq '[.[] | select(.date >= "2026-05-07")] | sort_by(.date) | .[0:10]'

# 関東のイベントのみフィルタ
curl -s https://agave-navi.com/events.json | \
  jq '[.[] | select(.region == "関東")]'
```

## 問い合わせ

商用利用、独自フィード追加、API改善要望などは [contact ページ](/contact.html) からご連絡ください。
