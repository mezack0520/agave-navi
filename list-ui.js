/**
 * list-ui.js — イベント一覧の共通UI(単一情報源)。
 *
 * 行きたい(localStorage)・カード全体クリック・もっと見るを持つ。
 * 以前は index.html と ikitai.html に getFavs / toggleFav / syncFavUI が
 * 二重定義され、もっと見るは index.html にしか無かった。そのため
 * /pref/ 等のランディング106枚は行きたいももっと見るも使えず、
 * 別のカード実装(landing-card)を持つしかなかった(2026-08-20に統合)。
 *
 * 読み込みは <head>。body内のインラインスクリプトから syncFavUI() 等を
 * 呼べるようにするため、defer にしない。DOM操作の初期化だけ
 * DOMContentLoaded まで遅らせる。
 *
 * ページ固有の処理はフックで受ける:
 *   window.AEN_ON_FAV_CHANGE — 行きたいの増減後に呼ばれる
 *   window.initMobileFav     — 定義されていれば初期化時に呼ばれる
 */
(function () {
  'use strict';

  var FAV_KEY = 'aen_favs';
  var CARDS_PER_PAGE = 12;
  var PAST_CARDS_INIT = 4;

  // --- 行きたい(localStorage) ---
  function getFavs() {
    try { return JSON.parse(localStorage.getItem(FAV_KEY) || '[]'); } catch (e) { return []; }
  }
  function setFavs(favs) {
    try { localStorage.setItem(FAV_KEY, JSON.stringify(favs)); } catch (e) {}
  }
  function toggleFav(e, slug) {
    if (e && e.stopPropagation) e.stopPropagation();
    if (!slug) return;
    var favs = getFavs();
    var i = favs.indexOf(slug);
    if (i > -1) favs.splice(i, 1); else favs.push(slug);
    setFavs(favs);
    syncFavUI();
    if (typeof window.AEN_ON_FAV_CHANGE === 'function') window.AEN_ON_FAV_CHANGE(slug);
  }
  function syncFavUI() {
    var favs = getFavs();
    document.querySelectorAll('.fav-btn').forEach(function (btn) {
      var card = btn.closest('.event-card');
      var slug = card && card.getAttribute('data-slug');
      btn.classList.toggle('favorited', !!(slug && favs.indexOf(slug) > -1));
    });
    // モバイルのカード下部バー
    document.querySelectorAll('.card-fav-bar').forEach(function (bar) {
      var card = bar.closest('.event-card');
      var slug = card && card.getAttribute('data-slug');
      if (!slug) return;
      var on = favs.indexOf(slug) > -1;
      bar.classList.toggle('is-fav', on);
      var span = bar.querySelector('span');
      if (span) span.textContent = on ? '行きたい登録済み' : '行きたい';
    });
    // ヘッダーのバッジ
    var b = document.getElementById('ikitaiBadge');
    if (b) {
      if (favs.length > 0) { b.textContent = favs.length; b.classList.add('has-count'); }
      else { b.textContent = ''; b.classList.remove('has-count'); }
    }
  }

  // --- カード全体クリックで詳細へ ---
  function wireCardClicks(scope) {
    (scope || document).querySelectorAll('.event-card[data-slug]').forEach(function (card) {
      if (card.__aenClickWired) return;
      card.__aenClickWired = true;
      card.style.cursor = 'pointer';
      card.addEventListener('click', function (e) {
        if (e.target.closest('a, button, .card-fav-bar, .fav-btn')) return;
        var slug = this.getAttribute('data-slug');
        if (slug) window.location.href = '/events/' + slug + '.html';
      });
    });
  }

  // --- もっと見る ---
  var shown = CARDS_PER_PAGE;

  function reloadCardImages(card) {
    var img = card.querySelector('.event-thumb img');
    if (img && !img.naturalWidth) {
      var src = img.getAttribute('src');
      img.setAttribute('src', '');
      img.setAttribute('src', src);
    }
  }
  function mainCards() {
    var g = document.getElementById('eventsGrid');
    return g ? Array.prototype.slice.call(g.querySelectorAll('.event-card')) : [];
  }
  function updateLoadMoreBtn() {
    var wrap = document.getElementById('loadMoreWrap');
    if (wrap) wrap.style.display = shown >= mainCards().length ? 'none' : '';
  }
  function initLoadMore() {
    shown = CARDS_PER_PAGE;
    mainCards().forEach(function (card, i) {
      card.classList.toggle('load-more-hidden', i >= CARDS_PER_PAGE);
    });
    updateLoadMoreBtn();
  }
  function loadMoreEvents() {
    var limit = shown + CARDS_PER_PAGE, delay = 0;
    mainCards().forEach(function (card, i) {
      if (i >= shown && i < limit) {
        card.classList.remove('load-more-hidden');
        card.style.display = '';
        card.classList.add('filter-show');
        card.style.animationDelay = delay + 'ms';
        delay += 60;
        reloadCardImages(card);
      }
    });
    shown = limit;
    updateLoadMoreBtn();
  }
  // 絞り込み中は制限を外して全件を対象にする
  function showAllMain() {
    mainCards().forEach(function (c) { c.classList.remove('load-more-hidden'); reloadCardImages(c); });
    var wrap = document.getElementById('loadMoreWrap');
    if (wrap) wrap.style.display = 'none';
  }

  // --- 終了セクションのもっと見る ---
  function pastCards() {
    var g = document.getElementById('pastEventsGrid');
    return g ? Array.prototype.slice.call(g.querySelectorAll('.event-card')) : [];
  }
  function initPastLoadMore() {
    var cards = pastCards();
    if (!cards.length) {
      var w0 = document.getElementById('pastLoadMoreWrap');
      if (w0) w0.style.display = 'none';
      return;
    }
    cards.forEach(function (card, i) {
      if (i >= PAST_CARDS_INIT) card.classList.add('past-load-more-hidden');
      else card.classList.remove('past-load-more-hidden');
    });
    var wrap = document.getElementById('pastLoadMoreWrap');
    if (wrap) wrap.style.display = cards.length <= PAST_CARDS_INIT ? 'none' : '';
  }
  function loadMorePastEvents() {
    var delay = 0;
    pastCards().forEach(function (card) {
      if (card.classList.contains('past-load-more-hidden')) {
        card.classList.remove('past-load-more-hidden');
        card.style.display = '';
        card.classList.add('filter-show');
        card.style.animationDelay = delay + 'ms';
        delay += 60;
        reloadCardImages(card);
      }
    });
    var wrap = document.getElementById('pastLoadMoreWrap');
    if (wrap) wrap.style.display = 'none';
  }

  // --- 公開 ---
  // HTMLの onclick 属性から呼ばれるためグローバルに置く。
  window.getFavs = getFavs;
  window.toggleFav = toggleFav;
  window.syncFavUI = syncFavUI;
  window.initLoadMore = initLoadMore;
  window.loadMoreEvents = loadMoreEvents;
  window.initPastLoadMore = initPastLoadMore;
  window.loadMorePastEvents = loadMorePastEvents;
  window.reloadCardImages = reloadCardImages;
  window.AEN_LIST_UI = {
    CARDS_PER_PAGE: CARDS_PER_PAGE,
    PAST_CARDS_INIT: PAST_CARDS_INIT,
    getFavs: getFavs, toggleFav: toggleFav, syncFavUI: syncFavUI,
    initLoadMore: initLoadMore, resetLoadMore: initLoadMore, showAll: showAllMain,
    initPastLoadMore: initPastLoadMore, wireCardClicks: wireCardClicks
  };

  function init() {
    wireCardClicks();
    syncFavUI();
    if (typeof window.initMobileFav === 'function') window.initMobileFav();
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
