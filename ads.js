/**
 * アガベイベントナビ - 広告・アフィリエイト管理
 * Google AdSense + Amazon / 楽天 / Yahoo! アフィリエイト ランダム表示
 */
(function() {
  'use strict';

  // アフィリエイト表示は affiliate.js + amazon-links.json に一本化した(2026-07-29)。
  // 旧実装は商品画像URLと価格をJSにべた書きしており、在庫切れ・価格変動で陳腐化するため廃止。
  // 表示位置の追加は amazon-links.json とテンプレート側の .affiliate-section で行う。

  // === AdSense 広告枠の初期化 ===
  function initAdSense() {
    if (typeof adsbygoogle === 'undefined') return;
    document.querySelectorAll('.adsbygoogle').forEach(function(ad) {
      try {
        (adsbygoogle = window.adsbygoogle || []).push({});
      } catch(e) {}
    });
  }

  // === ページ読み込み時に実行 ===
  function init() {
    initAdSense();
  }

  // サイドバーがaffiliate-sectionに重ならないようsticky位置を制御
  function initSidebarControl() {
    var sidebar = document.querySelector('.detail-sidebar');
    var affSection = document.querySelector('.affiliate-section');
    if (!sidebar || !affSection) return;

    var defaultTop = 70;

    function update() {
      var affTop = affSection.getBoundingClientRect().top;
      var sidebarH = sidebar.offsetHeight;
      var gap = 20;
      var available = affTop - sidebarH - gap;

      if (available < defaultTop) {
        sidebar.style.top = available + 'px';
      } else {
        sidebar.style.top = defaultTop + 'px';
      }
    }

    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update, { passive: true });
    update();
  }

  function initAll() {
    init();
    initSidebarControl();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
