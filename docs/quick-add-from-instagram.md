# Instagram投稿からイベント追加 - 現行フロー

## 現行の方法(2026-07-29更新)

**投稿URLを Cowork の Claude に貼るだけ。**

```
[Instagram投稿を見つけた]
     ↓
[URLをCoworkチャットに貼る]
     ↓
Claude が実行:
1. ユーザーのChromeで投稿を開いて内容を読む(IGはサーバーから取得不可)
2. 新規イベントなら: 主催者の一次情報で裏取り → rejected-events.json 照合
   → new-events.json 追加 → git push → repository_dispatch(sync-events)
3. 掲載済みイベントの告知(出店者投稿など)なら: 既存データと突き合わせ、
   不足フィールド(time/admission等)を主催者ソースで裏取りして補正
     ↓
[サイト反映] 新規はsync-eventsで数分、既存補正は翌朝の daily ビルド
```

実例: 2026-07-29 felicita_plants の出店告知 → 既存 life-circle-world-2026-08 の
time を主催者告知投稿で裏取りして補完(fa22e6d)。

なお日次タスク agave-event-update も watch-sources.json のIG主催者ローテで
新規投稿を自動検知する。URLを貼るのは「今すぐ載せたい/直したい」とき。

## 旧方式(廃止)

iOS Shortcut / curl から `ig-event` を repository_dispatch する1-tap方式は、
受け側の add-from-instagram.yml が **2026-05-18 に未使用のため削除済み**(c1001f2e。
auto-event.yml も同日削除)。dispatchを送っても何も起きない。

処理スクリプト scripts/add-from-instagram.py は残っているため、1-tap方式を
復活させる場合は workflow を再追加すればよい。ただし Shortcut に PAT を
埋め込む構成のため、PAT失効のたびに手元の Shortcut も更新が必要になる点に注意。
