# Instagram投稿からイベント追加 - 現行フロー

## 現行の方法(2026-09-26更新)

**投稿URLを Cowork の Claude に貼るだけ。**

```
[Instagram投稿を見つけた]
     ↓
[URLをCoworkチャットに貼る]
     ↓
Claude が実行:
1. 投稿を読む。主催がプロアカウントなら Graph API(scripts/iglib.py の Business Discovery)で
   本文が取れる。個人アカウントは組み込みブラウザで開く
2. 新規イベントなら: 主催者の一次情報で裏取り → rejected-events.json 照合
   → new-events.json 追加 → push(new-events.json の push で sync-events が走る)
3. 掲載済みイベントの告知(出店者投稿など)なら: 既存データと突き合わせ、
   不足フィールド(time/admission等)を主催者ソースで裏取りして補正
     ↓
[サイト反映] 新規はsync-eventsで数分、既存補正は翌朝の daily ビルド
```

実例: 2026-07-29 felicita_plants の出店告知 → 既存 life-circle-world-2026-08 の
time を主催者告知投稿で裏取りして補完(fa22e6d)。

なお毎日の scripts/ig-organizer-watch.py が主催と watch-sources.json のIGアカウントの
最新投稿を見て、未掲載の日付を organizer_unlisted_dates に出す。URLを貼るのは「今すぐ載せたい/直したい」とき。

## 旧方式(廃止)

iOS Shortcut / curl から `ig-event` を repository_dispatch する1-tap方式は、
受け側の add-from-instagram.yml と処理スクリプト add-from-instagram.py ともに削除済み。
repository_dispatch 自体もこの環境からは使わない(task-playbook.md)。
