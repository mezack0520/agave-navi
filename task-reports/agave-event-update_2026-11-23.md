# agave-event-update 2026-11-23

## 掲載(new-events.json 9件、sync-events で取り込み済み)
- 焼津 植物忘年会 12/26-27 焼津PORTERS … 主催 @botalife_pachy Df_8tmxSl18(organizer_unlisted_dates)
- 第9回 多肉と雑貨 福山deマルシェ 2027-01-10 エフピコアリーナふくやま … 主催 @nagomitaniku DgC1qwak49S(26組)
- 多肉と雑貨 MAGIC CARAVAN 2027-01-16/17 イズミヤSC広陵 … 主催 @magic._.caravan DcuEaxmE2yG(出店者 @greensanta2020 の予定表から主催を辿った)
- 多肉感謝祭2026 12/19-20 多肉屋GPK … 主催 @seiji4240 DgBywC1GqC9(POPUP出店・販売会あり、storeSale.include)
- 時の輪郭 – 叢 と 寒川義雄 11/29・12/4-6 COLUMN gallery … qusamura.com/information/exhibition/3802/(enrich が入場料1,000円を書き戻し、公式どおり)
- Roots plus vol.2 2027-03-07(tbd)… @roots_plus_livingwithstyle Df_Ag4HoGkc
- 多肉もぶれ vol.14 2027-03-07(tbd)… @temo2929 DfwrIJtTrlo
- Bota Para 2027 4/10-11 アクセスサッポロ … @botapara_botanical_paradise DgC8Ba-I5_U
- 富士山Garden marche 2027-04-10 … @fujisan_gardenmarche Df_yyoqNrSv

## 既存の回の修正(events.json)
- bizarre-plants-night-day-2026-12: 主催の最新告知 DgCfy7GRFr3 に sourceUrl を替え、admission(18歳以下無料)、aliases、説明文の主催3組を直した
- hanatomofesta-2026: 公式の前売1,500円・当日2,500円に
- fujisan-garden-marche-2026-10: location から区画(芝生広場)を外した(次回と venue_key_split を出さない)
- qusamura-kuwata-takuro-taniku-to-purabachi-2026-10: organizerIg qusamura_official

## 見送り(rejected-events.json 3件)
VESSEL meets だいだら植物店(切り花の移動花屋)、土に還る言葉 vol.01(土づくり・コンポスト)、タニクCAMP 2027-04-17(出店者の予定のみ、revisit)

## Step0
- coverage-gaps: errors 0、gaps 4件を全件処理(掲載1・見送り2・見送り済みに alias 1)。truncatedUnresolved 3件はすべて掲載で解消
- scan-organizer-posts 145行を読んだ。新規は上の焼津・福山・Roots plus・Bota Para・ふじさん・もぶれ・MAGIC CARAVAN
- LEAFLA 連番 topics7351〜7400。200 は 7358・7364・7366・7373・7379・7382・7385・7390、右端 topics7390
- Google 検索は1本目から `a h3` 0件で打ち切り(前回に続き2日目)。中止・延期の検索は未実施
- search-demand 1件(カトーエンゲー東京): 次の催しの告知なし、--no-change

## 日次メール項目
- build-health-mail は send=False(urgent 0)。info を処理: coverage_gaps 4、organizer_unlisted_dates 2、cancel_suspects 2(cancel-reviewed に記録)、rejected_revisit_stale 1(monster-plants-kagawa、revisitedOn 更新)
- needs_browser: open 0件

## 気づき(恒久化)
- @goodthings.jp の「前売りチケットは11/23(月)24時まで」が開催日として organizer_unlisted_dates に出た。ig-organizer-watch.py の month_days に前売りの販売の終わりを落とす規則とテスト2件を足した(--self-test OK)
- device_bash の $HOME(/sessions)が 99% で、clone のコピーが書けなかった。作業は /tmp で行った

clone 削除済み
