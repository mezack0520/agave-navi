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
