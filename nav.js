// ハンバーガーとナビの開閉。全ページで同じ実装を使う。
//
// 生成ページ(詳細145・地域/県/タグ/カテゴリ106・ガイド)には
// ナビ自体が無く、SPで開くと行き先がどこにも無い状態だった。
// sitelib.site_header() にメニューが入っていなかったのが原因で、
// 手書きの13ページだけが自前のインライン実装を持っていた
// (2026-09-08 指摘)。
//
// 同じ15行が14箇所にあったので、ここに集めた。
// 増えるページは site_header() 経由でこのファイルを読む。
(function () {
  'use strict';

  function init() {
    var toggle = document.getElementById('menuToggle');
    var overlay = document.getElementById('navOverlay');
    if (!toggle || !overlay) return;

    function set(open) {
      toggle.classList.toggle('active', open);
      overlay.classList.toggle('active', open);
      document.body.classList.toggle('no-scroll', open);
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }

    toggle.addEventListener('click', function () {
      set(!overlay.classList.contains('active'));
    });
    // 行き先を押したら閉じる。同一ページ内リンクだと開いたままになる
    overlay.querySelectorAll('a').forEach(function (a) {
      a.addEventListener('click', function () { set(false); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' || e.key === 'Esc') set(false);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// 行きたいの件数バッジ。ヘッダーの一部なのでここで面倒を見る。
// 同じ14行が14ページにインラインで写されていた(2026-09-08 に集約)。
(function () {
  'use strict';
  function paint() {
    var b = document.getElementById('ikitaiBadge');
    if (!b) return;
    var n = 0;
    try { n = (JSON.parse(localStorage.getItem('aen_favs') || '[]') || []).length; }
    catch (e) { n = 0; }
    b.textContent = n > 0 ? String(n) : '';
    b.classList.toggle('has-count', n > 0);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', paint);
  } else {
    paint();
  }
  // 「行きたい」を押した直後にも合わせる。list-ui.js が呼ぶ
  window.AEN_ON_FAV_CHANGE = paint;
})();

// 固定する帯の高さを実測して CSS 変数に返す。
//
// sticky の top と scroll-margin-top は --header-h / --crumb-h から
// 計算している。style.css に書いてある値は JS が走る前の初期値で、
// 実際の高さは文字の大きさ・折り返し・端末の実装で変わる。
// 手打ちの数値を置いていた頃は、トップの帯が top:40px 固定で
// 実測 50.8px のヘッダーの下に約11px潜っていた(2026-09-10 実測)。
// 読み込み後と、大きさが変わるたびに測り直す。
(function () {
  'use strict';
  var root = document.documentElement;

  function h(sel) {
    var el = document.querySelector(sel);
    return el ? Math.round(el.getBoundingClientRect().height) : 0;
  }

  function measure() {
    var head = h('.header');
    // パンくずの帯が無い頁もある。その場合は 0。初期値を残すと
    // 見出しへのリンクが帯1本ぶん行き過ぎる
    root.style.setProperty('--crumb-h', h('.crumb-bar') + 'px');
    if (head) root.style.setProperty('--header-h', head + 'px');
  }

  function watch() {
    measure();
    if (typeof ResizeObserver !== 'function') return;
    var ro = new ResizeObserver(measure);
    ['.header', '.crumb-bar'].forEach(function (sel) {
      var el = document.querySelector(sel);
      if (el) ro.observe(el);
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', watch);
  } else {
    watch();
  }
  window.addEventListener('load', measure);
})();
