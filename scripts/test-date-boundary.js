#!/usr/bin/env node
/**
 * test-date-boundary.js — 開催バッジの日付境界テスト。
 *
 * 2026-08-29 の朝、JSTの閲覧者に「本日開催」が「明日開催」と出た。
 * todayJST() が getTimezoneOffset() を足していたため、JSTでは
 * -9h と +9h が打ち消し合ってUTCの暦日を返し、0:00〜9:00 JST の
 * 9時間ずっと前日と判定されていた。JST以外では偶然正しく出るので、
 * 東京で朝に見たときだけ壊れるという見つけにくい形だった。
 *
 * 依存なし。閲覧者のタイムゾーン差を見るため、TZ を変えて自分を再実行する。
 * build-all.sh から呼ぶ。失敗したら非0で終了してビルドを止める。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const TZS = ['Asia/Tokyo', 'UTC', 'America/Los_Angeles', 'Australia/Sydney'];

// --- 親: TZ を変えて自分を再実行する ---
if (!process.env.AEN_TZ_CHILD) {
  let failed = 0;
  for (const tz of TZS) {
    try {
      const out = execFileSync(process.execPath, [__filename], {
        env: { ...process.env, TZ: tz, AEN_TZ_CHILD: '1' },
        encoding: 'utf8'
      });
      process.stdout.write(out);
    } catch (e) {
      process.stdout.write(e.stdout || '');
      process.stderr.write(e.stderr || '');
      failed++;
    }
  }
  if (failed) {
    console.error(`\ntest-date-boundary: ${failed} タイムゾーンで失敗`);
    process.exit(1);
  }
  console.log('test-date-boundary: 全タイムゾーンで通過');
  process.exit(0);
}

// --- 子: status-auto.js を最小のDOMスタブで読み込む ---
const noop = () => {};
const fakeEl = () => ({
  style: {}, className: '', textContent: '',
  classList: { add: noop, remove: noop, toggle: noop, contains: () => false },
  setAttribute: noop, getAttribute: () => null, hasAttribute: () => false,
  appendChild: noop, insertBefore: noop, querySelector: () => null,
  querySelectorAll: () => []
});
global.window = global;
global.document = {
  readyState: 'complete',
  head: fakeEl(),
  addEventListener: noop,
  createElement: fakeEl,
  querySelector: () => null,
  querySelectorAll: () => [],
  getElementById: () => null
};
global.location = { pathname: '/' };
global.XMLHttpRequest = function () {
  return { open: noop, send: noop, status: 0 };
};

const src = fs.readFileSync(path.join(ROOT, 'status-auto.js'), 'utf8');
// eslint-disable-next-line no-eval
eval(src);
const T = global.AEN_TIME;
if (!T || !T.statusFor) {
  console.error('status-auto.js が AEN_TIME.statusFor を公開していない');
  process.exit(1);
}

// --- 時刻を固定して検証する ---
const realNow = Date.now;
function at(iso, fn) {
  const ms = new Date(iso).getTime();
  Date.now = () => ms;
  try { return fn(); } finally { Date.now = realNow; }
}

const TZ = process.env.TZ;
let fail = 0;
function eq(actual, expected, what) {
  if (actual !== expected) {
    console.error(`  ✗ [${TZ}] ${what}: 期待「${expected}」/ 実際「${actual}」`);
    fail++;
  }
}

// 境界時刻。0時直後・早朝(不具合が出ていた時刻)・日中・深夜。
const MOMENTS = [
  '2026-08-29T00:00:01+09:00',
  '2026-08-29T00:01:00+09:00',
  '2026-08-29T06:57:00+09:00',
  '2026-08-29T08:59:59+09:00',
  '2026-08-29T09:00:01+09:00',
  '2026-08-29T12:00:00+09:00',
  '2026-08-29T23:59:59+09:00'
];

for (const m of MOMENTS) {
  at(m, () => {
    eq(T.todayJST(), '2026-08-29', `${m} の todayJST`);
    eq(T.statusFor('2026-08-29', '2026-08-29').label, '本日開催', `${m} 当日の単発`);
    eq(T.statusFor('2026-08-30', '2026-08-30').label, '明日開催', `${m} 翌日`);
    eq(T.statusFor('2026-08-31', '2026-08-31').label, 'あと2日', `${m} 翌々日`);
    eq(T.statusFor('2026-08-28', '2026-08-28').label, '終了', `${m} 前日`);
    eq(T.phase('2026-08-29', '2026-08-29'), 'ongoing', `${m} 当日のphase`);
    eq(T.phase('2026-08-28', '2026-08-28'), 'past', `${m} 前日のphase`);
    eq(T.phase('2026-08-30', '2026-08-30'), 'upcoming', `${m} 翌日のphase`);
    // 会期中の長期開催: 初日は本日開催、2日目以降は開催中
    eq(T.statusFor('2026-08-01', '2026-09-30').label, '開催中 〜9/30', `${m} 会期中`);
    eq(T.statusFor('2026-08-29', '2026-09-30').label, '本日開催', `${m} 会期初日`);
    eq(T.statusFor('2026-08-20', '2026-08-29').label, '開催中 〜8/29', `${m} 会期最終日`);
    eq(T.isLongRun('2026-08-01', '2026-09-30'), true, `${m} 長期判定`);
    eq(T.isLongRun('2026-08-29', '2026-08-30'), false, `${m} 2日開催は長期でない`);
  });
}

// 日付をまたぐ瞬間: 23:59:59 の翌秒に「今日」が繰り上がる
at('2026-08-29T23:59:59+09:00', () => eq(T.todayJST(), '2026-08-29', '大晦日前の境界'));
at('2026-08-30T00:00:00+09:00', () => eq(T.todayJST(), '2026-08-30', '0時ちょうど'));
// 年またぎ
at('2026-12-31T23:59:59+09:00', () => eq(T.todayJST(), '2026-12-31', '年末'));
at('2027-01-01T00:00:30+09:00', () => eq(T.todayJST(), '2027-01-01', '年始'));

if (fail) {
  console.error(`test-date-boundary [${TZ}]: ${fail}件 失敗`);
  process.exit(1);
}
console.log(`  ok [${TZ}] ${MOMENTS.length}時刻 × 12項目`);
