/**
 * アフィリエイト枠。設定の単一情報源は affiliate-links.json
 * - .affiliate-section に、頁の文脈(data-tags / data-guide)に合う資材を3点出す。
 *   楽天の商品検索APIで取れた品は画像・価格つきのカード、各行に Amazon などの検索ボタン
 * - 同じ枠の先頭に、株そのものをメルカリで見る1行(イベント詳細・タグ頁・品種ガイド)
 * - スマホは画面下に Amazon の固定バー
 */
(function () {
  'use strict';

  // 表示の一括停止スイッチ。AdSense審査などで止めたいときだけ false にする。
  var AFFILIATE_ENABLED = true;
  if (!AFFILIATE_ENABLED) return;

  var DISPLAY_COUNT = 3;
  var ICONS = {
    pot:   '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
    soil:  '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M3 20h18"/><path d="M5 20c1.2-4.8 3.8-8 7-8s5.8 3.2 7 8"/><path d="M9.5 16.5h.01M12 14.8h.01M14.5 16.8h.01"/></svg>',
    tool:  '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    light: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/><circle cx="12" cy="12" r="5"/></svg>',
    plant: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 20h10"/><path d="M10 20c5.5-2.5 8-8.5 8-12a1 1 0 0 0-1-1c-3.5 0-7.5 2-10 6"/><path d="M10 20c-3-2-5-6-5-9a1 1 0 0 1 1-1c2.5 0 5 1.5 7 4"/></svg>',
    shelf: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/></svg>',
    book:  '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
  };

  // Detect base path
  var scripts = document.getElementsByTagName('script');
  var basePath = '';
  for (var i = 0; i < scripts.length; i++) {
    var src = scripts[i].getAttribute('src') || '';
    if (src.indexOf('affiliate.js') !== -1) {
      // 'affiliate.js?v=xxxx' のようにクエリが付くため、ファイル名以降を丸ごと落とす。
      // replace('affiliate.js','') だとクエリが残り、JSONのURLが壊れる。
      basePath = src.replace(/affiliate\.js.*$/, '');
      break;
    }
  }

  var containers = document.querySelectorAll('.affiliate-section');
  if (!containers.length) return;

  var CACHE_KEY = 'agn_rk_v1';
  var CACHE_TTL = 24 * 60 * 60 * 1000;   // 24時間

  function cacheRead() {
    try { return JSON.parse(localStorage.getItem(CACHE_KEY)) || {}; }
    catch (e) { return {}; }
  }
  function cacheWrite(store) {
    try { localStorage.setItem(CACHE_KEY, JSON.stringify(store)); } catch (e) {}
  }

  // 楽天商品検索API(ブラウザから呼ぶ前提。リファラ制限が鍵の保護になっている)
  function fetchProduct(keyword, rk, opts) {
    var q = new URLSearchParams({
      applicationId: rk.applicationId, accessKey: rk.accessKey,
      affiliateId: rk.affiliateId || '', format: 'json', formatVersion: '2',
      hits: '10', imageFlag: '1', sort: '-reviewCount', keyword: keyword
    });
    // 商品ごとの想定価格帯。セット商品や業務用が混ざるのを防ぐ。
    if (opts && opts.maxPrice) q.set('maxPrice', String(opts.maxPrice));
    if (opts && opts.minPrice) q.set('minPrice', String(opts.minPrice));
    // 無関係な商品を除外する(例: ルーペ検索に化粧用の女優ミラーが混ざる)
    if (opts && opts.ngKeyword) q.set('NGKeyword', opts.ngKeyword);
    return fetch(rk.apiEndpoint + '?' + q)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var arr = (j && (j.items || j.Items)) || [];
        // 極端な価格帯とレビュー0件を避ける
        var lo = (opts && opts.minPrice) || 300;
        var hi = (opts && opts.maxPrice) || 200000;
        var it = arr.filter(function (x) {
          return x.itemPrice >= lo && x.itemPrice <= hi && (x.reviewCount || 0) >= 1;
        })[0] || arr.filter(function (x) {
          return x.itemPrice >= lo && x.itemPrice <= hi;
        })[0];
        if (!it) return null;
        var urls = it.mediumImageUrls || [];
        var img = urls.length ? (typeof urls[0] === 'string' ? urls[0] : urls[0].imageUrl) : '';
        if (!img || !it.affiliateUrl) return null;
        return {
          name: (it.itemName || '').slice(0, 90),
          price: it.itemPrice,
          image: img.replace('_ex=128x128', '_ex=300x300'),
          url: it.affiliateUrl,
          reviewCount: it.reviewCount || 0,
          at: Date.now()
        };
      })
      .catch(function () { return null; });
  }

  fetch(basePath + 'affiliate-links.json?v=' + Date.now())
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var rk = (data.asp || {}).rakuten || {};
      var canFetch = !!(rk.applicationId && rk.accessKey && rk.apiEndpoint);

      // 先にテキスト表示で描画し、商品が取れたら差し替える(表示が遅れない)
      var plan = [];
      Array.prototype.forEach.call(containers, function (el) {
        var tags = (el.getAttribute('data-tags') || '').split(',').filter(Boolean);
        var guide = el.getAttribute('data-guide') || '';
        var items = pickItems(data, tags, guide);
        plan.push({ el: el, items: items, guide: guide,
                    heading: el.getAttribute('data-heading') || '',
                    mercari: mercariPick(data, el, tags, guide) });
      });

      data._products = {};
      var store = cacheRead();
      var now = Date.now();
      var need = [];
      var opts = {};
      plan.forEach(function (p) {
        p.items.forEach(function (it) {
          opts[it.keyword] = { minPrice: it.minPrice, maxPrice: it.maxPrice,
                               ngKeyword: it.ngKeyword };
          var c = store[it.keyword];
          if (c && c.at && (now - c.at) < CACHE_TTL) data._products[it.keyword] = c;
          else if (canFetch && need.indexOf(it.keyword) < 0) need.push(it.keyword);
        });
      });

      function draw() {
        plan.forEach(function (p) {
          render(data, p.el, p.guide, p.heading, p.items, p.mercari);
        });
        buildStickyBar(data, plan);
      }
      draw();

      if (!need.length) return;
      // 楽天APIは applicationId あたり1秒1件。350ms 待ちだと応答が速い回線で
      // 1秒に2〜3件飛び、429 が返って商品カードがテキストのまま残っていた
      // (2026-09-07 実測: 実間隔 905ms / 1002ms で、境界に張り付いていた)。
      // 429 は catch されて null になるだけなので例外もログも出ず、
      // 「その枠だけカードにならない」という形でしか表に出ない。
      // 送信時刻の間隔で 1100ms を保証する(応答時間に左右されない数え方にする)。
      var MIN_INTERVAL = 1100;
      var lastSentAt = 0;
      var i = 0;
      (function next() {
        if (i >= need.length) { cacheWrite(store); draw(); return; }
        var wait = Math.max(0, MIN_INTERVAL - (Date.now() - lastSentAt));
        setTimeout(function () {
          var kw = need[i++];
          lastSentAt = Date.now();
          fetchProduct(kw, rk, opts[kw]).then(function (prod) {
            if (prod) { data._products[kw] = prod; store[kw] = prod; }
            next();
          });
        }, wait);
      })();
    })
    .catch(function (e) { console.warn('affiliate.js:', e); });

  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }

  // 表示の種。ページごと・日ごとに変えて同じ並びを出し続けないようにする。
  // リロードで毎回変わると落ち着かないため、同じページ・同じ日なら同じ並びになる。
  function seed() {
    var d = new Date();
    var s = location.pathname + '|' + d.getFullYear() + '-' + d.getMonth() + '-' + d.getDate();
    var h = 2166136261;
    for (var i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  // ===== スマホ用の固定バー =====
  // Amazon を出す(2026-10-20 目崎の指定。売れているのは Amazon)。
  // Amazon の商品画像と価格は Creators API からしか出せず、使えるのは過去30日に
  // 適格販売10件以上のときだけなので、届くまでは文字とサイトのアイコンで出す。
  // tag が空(アソシエイト停止中)の間だけ、楽天の実商品に戻す。
  var stickyDone = false;

  function stickyAmazon(data, it) {
    var url = amazonUrl((data.asp || {}).amazon, it.keyword);
    if (!url) return '';
    return '<a class="aff-bar-link" href="' + url + '" target="_blank" rel="noopener sponsored" data-shop="amazon">'
      + '<span class="aff-bar-icon">' + (ICONS[it.icon] || ICONS.plant) + '</span>'
      + '<span class="aff-bar-body">'
      + '<span class="aff-bar-why">' + it.label + '<span class="aff-bar-pr">PR</span></span>'
      + '<span class="aff-bar-meta"><span class="aff-bar-shop is-amazon">Amazon</span></span>'
      + '</span>'
      + '<span class="aff-bar-go">探す</span></a>';
  }

  function stickyRakuten(data, items) {
    var products = data._products || {};
    for (var i = 0; i < items.length; i++) {
      var p = products[items[i].keyword];
      if (!(p && p.image && p.url)) continue;
      return '<a class="aff-bar-link" href="' + p.url + '" target="_blank" rel="noopener sponsored" data-shop="rakuten">'
        + '<img class="aff-bar-img" src="' + p.image + '" alt="" loading="lazy"'
        + ' onerror="this.style.visibility=\'hidden\'">'
        + '<span class="aff-bar-body">'
        + '<span class="aff-bar-why">' + items[i].label + '<span class="aff-bar-pr">PR</span></span>'
        + '<span class="aff-bar-meta">'
        + (p.price ? '<span class="aff-bar-price">'
            + Number(p.price).toLocaleString('ja-JP') + '円</span>' : '')
        + '<span class="aff-bar-shop">楽天市場</span></span>'
        + '</span>'
        + '<span class="aff-bar-go">見る</span></a>';
    }
    return '';   // 実商品が取れないうちは出さない
  }

  function buildStickyBar(data, plan) {
    if (stickyDone) return;
    if (window.matchMedia && !window.matchMedia('(max-width: 720px)').matches) return;
    try {
      if (sessionStorage.getItem('agn_aff_bar_closed') === '1') return;
    } catch (e) {}
    if (!plan.length || !plan[0].items.length) return;

    var inner = stickyAmazon(data, plan[0].items[0]) || stickyRakuten(data, plan[0].items);
    if (!inner) return;
    stickyDone = true;

    var bar = document.createElement('div');
    bar.className = 'aff-bar';
    bar.setAttribute('aria-label', '広告');
    bar.innerHTML = inner
      + '<button class="aff-bar-close" type="button" aria-label="閉じる">×</button>';
    document.body.appendChild(bar);

    bar.querySelector('.aff-bar-close').addEventListener('click', function () {
      bar.classList.remove('is-shown');
      try { sessionStorage.setItem('agn_aff_bar_closed', '1'); } catch (e) {}
      setTimeout(function () { bar.remove(); }, 250);
    });

    // 本文中の枠が見えている間は隠す(同じものを二重に出さない)
    var boxVisible = false;
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        boxVisible = entries.some(function (e) { return e.isIntersecting; });
        update();
      }, { threshold: 0.15 });
      plan.forEach(function (p) { io.observe(p.el); });
    }

    function update() {
      var scrolled = window.scrollY || document.documentElement.scrollTop;
      // 少し読み進めたら出す(2026-10-20 目崎「もっと早くていい」)。
      // それまでは頁の45%まで出さず、長い詳細頁では最後のほうまで出なかった
      var past = scrolled > window.innerHeight * 0.25;
      bar.classList.toggle('is-shown', past && !boxVisible);
    }
    window.addEventListener('scroll', update, { passive: true });
    window.addEventListener('resize', update);
    update();
  }

  // ads.js から移設(2026-07-30 AdSense撤去)。
  // サイドバーの sticky 位置をアフィリエイト枠に重ならないよう制御する。
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


  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSidebarControl);
  } else {
    initSidebarControl();
  }

  var RND_STATE = seed();
  function rnd() {
    // xorshift。種が同じなら同じ順序になる
    RND_STATE ^= RND_STATE << 13; RND_STATE >>>= 0;
    RND_STATE ^= RND_STATE >>> 17;
    RND_STATE ^= RND_STATE << 5;  RND_STATE >>>= 0;
    return RND_STATE / 4294967296;
  }
  function seededShuffle(arr) {
    var a = arr.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(rnd() * (i + 1));
      var t = a[i]; a[i] = a[j]; a[j] = t;
    }
    return a;
  }

  // 季節の重み付け。affiliate-links.json の season(旬の月の配列)を持つ品目だけ、
  // 旬なら rank を上げ、旬を外れていれば下げる。season の無い品目は通年扱いで不変。
  // 8月に「冬の室内管理で徒長させないための育成LED」「取り込み株をまとめて置ける簡易温室」が
  // 最上位に出ていたため導入(2026-08-10)。判定は閲覧者の時計ではなく JST の月で行う。
  var JST_MONTH = (function () {
    // status-auto.js の todayJST と同じ理由で getTimezoneOffset は使わない。
    // Date.now() は既にUTCなので9時間足してUTCの読み出しを使う。
    // 旧実装はJSTの閲覧者だと 0:00〜9:00 に前日=月初なら前月を返していた。
    return new Date(Date.now() + 9 * 3600000).getUTCMonth() + 1;
  })();
  function effectiveRank(it) {
    var r = it.rank || 9;
    if (!it.season || !it.season.length) return r;
    return it.season.indexOf(JST_MONTH) >= 0 ? Math.max(1, r - 2) : r + 4;
  }

  // 同ジャンル(group)が枠を食い合わないように1つずつに絞る。
  // rank の階層は保ちつつ、同じ rank の中は種で入れ替えて並びを固定しない。
  function narrow(items, count) {
    var byGroup = {};
    var pool = [];
    items.forEach(function (it) {
      var g = it.group || it.keyword;
      if (byGroup[g]) return;      // 同ジャンルは1つまで
      byGroup[g] = true;
      pool.push(it);
    });
    var tiers = {};
    pool.forEach(function (it) {
      var r = effectiveRank(it);
      (tiers[r] = tiers[r] || []).push(it);
    });
    var out = [];
    Object.keys(tiers).map(Number).sort(function (a, b) { return a - b; })
      .forEach(function (r) { out = out.concat(seededShuffle(tiers[r])); });
    return out.slice(0, count);
  }

  function pickItems(data, tags, guideSlug) {
    // ガイド記事: 記事本文が扱う対象をそのまま検索語にする(文脈が最も近く単価も高い)。
    // 記事側の並び順が編集意図なので rank より優先し、ジャンル重複だけ落とす。
    if (guideSlug && data.guides && data.guides[guideSlug]) {
      var g = data.guides[guideSlug].slice();
      if (g.length >= DISPLAY_COUNT) return g.slice(0, DISPLAY_COUNT);
      // 記事の並びは編集意図なのでそのまま使う。埋める分だけジャンル重複を避ける。
      var used = {};
      g.forEach(function (it) { used[it.group || it.keyword] = true; });
      var fill = (data.common || []).filter(function (c) {
        return !used[c.group || c.keyword];
      });
      return g.concat(narrow(fill, DISPLAY_COUNT - g.length));
    }

    var catItems = [];
    var cats = data.categories || {};
    tags.forEach(function (tag) {
      if (cats[tag]) catItems = catItems.concat(cats[tag]);
    });

    // タグ由来を優先し、足りない分を common で埋める。
    // **先頭の1枠はタグ由来から必ず取る。** 連結してから rank で並べると、
    // season の加点を受けた common が上位を独占して、そのページの
    // カテゴリに結びついた品(即売会なら鉢・用土)が1つも出ない月がある。
    // 2026-09-22、9月の即売会ページが越冬用品3点になっていた。
    // 枠の見出しは「株を持ち帰る前に揃えるもの」なので、
    // 持ち帰りに要る物が消えると見出しと中身が食い違う。
    var lead = narrow(catItems, 1);
    var used = {};
    lead.forEach(function (it) { used[it.group || it.keyword] = true; });
    var rest = catItems.concat(data.common || []).filter(function (it) {
      return !used[it.group || it.keyword];
    });
    return lead.concat(narrow(rest, DISPLAY_COUNT - lead.length));
  }

  // Amazon の検索リンク。tag が空なら出さない(2026-09-23 に旧アカウントが終了した)
  function amazonUrl(amz, keyword) {
    if (!amz || !amz.tag) return '';
    return amz.searchUrl.replace('{keyword}', encodeURIComponent(keyword)).replace('{tag}', amz.tag);
  }

  /**
   * 資材の検索リンクを店ごとに作る。ID が設定されている店だけ返す。
   * key は data-shop(CSS の店の色と GA4 の shop)にそのまま使う。
   */
  function buildAspLinks(keyword, asp) {
    var links = [];

    var amz = amazonUrl(asp.amazon, keyword);
    if (amz) links.push({ key: 'amazon', label: asp.amazon.label || 'Amazon', url: amz });

    var rak = asp.rakuten;
    if (rak) {
      links.push({
        key: 'rakuten',
        label: rak.label || '楽天市場',
        url: rak.affiliateId
          ? 'https://hb.afl.rakuten.co.jp/hgc/' + rak.affiliateId
            + '/?pc=' + encodeURIComponent('https://search.rakuten.co.jp/search/mall/' + keyword + '/')
          : 'https://search.rakuten.co.jp/search/mall/' + encodeURIComponent(keyword) + '/'
      });
    }

    // Yahoo!ショッピング(バリューコマース)。sid/pid が設定済みのときだけ
    var yah = asp.yahoo;
    if (yah && yah.sid && yah.pid) {
      links.push({
        key: 'yahoo',
        label: yah.label || 'Yahoo!ショッピング',
        url: 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=' + yah.sid
          + '&pid=' + yah.pid
          + '&vc_url=' + encodeURIComponent('https://shopping.yahoo.co.jp/search?p=' + keyword)
      });
    }

    return links;
  }

  // ===== メルカリ(株そのもの)の1行 =====
  // 資材は Amazon・楽天で足りるが、株そのものはメルカリで動いている(2026-10-20)。
  // リンクは affiliate-links.json に、アンバサダーのダッシュボードで生成したものを
  // そのまま持つ。規約でリンク先URLの変更・自作は禁止なので、ここで組み立てない。
  // 開催前・開催中の回は売り切れ(行く前の相場)、終わった回・タグ頁・品種ガイドは出品中。
  function todayJST() {
    // status-auto.js の todayJST と同じく getTimezoneOffset は使わない
    return new Date(Date.now() + 9 * 3600000).toISOString().slice(0, 10);
  }

  // イベント詳細なら終わったかどうか。それ以外の頁は null
  function eventOver() {
    var b = document.querySelector('.detail-status-badge');
    if (!b) return null;
    var end = b.getAttribute('data-date-end') || b.getAttribute('data-date') || '';
    return /^\d{4}-\d{2}-\d{2}$/.test(end) ? end < todayJST() : null;
  }

  function mercariPick(data, el, tags, guide) {
    var m = (data.asp || {}).mercari;
    if (!m || !m.links) return null;
    var kw = '', mode = 'onSale', over = null;
    if (guide) {
      var g = (m.guides || {})[guide];
      if (!g) return null;   // 株の話でないガイド(土・薬剤・ライト)
      kw = g.keyword;
      mode = g.mode || 'onSale';
    } else {
      over = eventOver();
      // 置くのはイベント詳細・タグ頁・品種ガイドだけ(2026-10-20 目崎指定)。
      // タグ頁は generate-landing-pages.py が data-mercari を付ける
      if (over === null && !el.hasAttribute('data-mercari')) return null;
      var alias = m.aliases || {};
      var have = tags.map(function (t) { return alias[t] || t; });
      (m.genres || []).some(function (x) {
        if (have.indexOf(x) < 0) return false;
        kw = x;
        return true;
      });
      // 即売会としか書いていない回が多い。イベント詳細だけ既定のジャンルで埋める
      if (!kw && over !== null) kw = m.fallback || '';
      if (over === false) mode = 'soldOut';
    }
    var url = kw && (m.links[kw] || {})[mode];
    return url ? { keyword: kw, mode: mode, over: over, url: url } : null;
  }

  // 枠の先頭に置く。読者が来ているのは株のためで、資材はその次(2026-10-20)
  function mercariRow(mer) {
    var sold = mer.mode === 'soldOut';
    return '<div class="aff-mercari">'
      + '<div class="aff-head"><h3>'
      + (sold ? '行く前に相場を見る' : mer.over ? '次の開催まで待てないとき' : '株を探す')
      + '</h3><span class="aff-pr">PR</span></div>'
      + '<a class="aff-mercari-btn" href="' + mer.url + '" target="_blank" rel="noopener sponsored" data-shop="mercari">'
      + 'メルカリで「' + mer.keyword + '」の' + (sold ? '相場' : '出品') + 'を見る</a>'
      + (sold ? '<p class="aff-mercari-note">売り切れた株の値段は、会場で値札を見るときの目安になります</p>' : '')
      + '</div>';
  }

  function render(data, el, guideSlug, heading, items, mer) {
    if (!items.length) return;
    var aspConfig = data.asp || {};

    var title = heading || (guideSlug ? 'この記事で使う道具・資材' : '株を持ち帰る前に揃えるもの');
    var desc = guideSlug
      ? '本文で触れた資材を各ショップで探せます'
      : '当日の運搬と、帰宅後の植え替え・発根管理で必要になるもの';

    var html = (mer ? mercariRow(mer) : '')
             + '<div class="aff-head"><h3>' + title + '</h3>'
             + '<span class="aff-pr">PR</span></div>';
    html += '<p class="affiliate-desc">' + desc + '</p>';
    html += '<div class="affiliate-links">';

    var products = data._products || {};

    function shopButtons(links) {
      // 先頭(Amazon)を主動線にする。実測でAmazonだけが売れている
      // (2026-08-24: 過去30日 Amazon 14クリック/5点/¥214、楽天 16クリック/0件/¥0)。
      return '<div class="aff-shop-btns">' + links.map(function (asp, i) {
        return '<a href="' + asp.url + '" target="_blank" rel="noopener sponsored"'
          + ' class="aff-shop-btn' + (i === 0 ? ' is-primary' : '') + '"'
          + ' data-shop="' + asp.key + '">' + asp.label + 'で探す</a>';
      }).join('') + '</div>';
    }

    items.forEach(function (item) {
      var aspLinks = buildAspLinks(item.keyword, aspConfig);
      if (!aspLinks.length) return;

      // 実商品カード: 画像・商品名・価格。価格は取得時点である旨を添える
      var p = products[item.keyword];
      if (p && p.image && p.url) {
        html += '<div class="affiliate-item">';
        html += '<a class="rk-card" href="' + p.url + '" target="_blank" rel="noopener sponsored" data-shop="rakuten">';
        html += '<img class="rk-card-img" src="' + p.image + '" alt="" loading="lazy"'
             +  ' referrerpolicy="no-referrer-when-downgrade"'
             +  ' onerror="this.style.visibility=\'hidden\'">';
        html += '<span class="rk-card-body">';
        html += '<span class="rk-card-why">' + item.label + '</span>';
        html += '<span class="rk-card-name">' + p.name + '</span>';
        html += '<span class="rk-card-meta">';
        if (p.price) html += '<span class="rk-card-price">' + Number(p.price).toLocaleString('ja-JP') + '円</span>';
        if (p.reviewCount) html += '<span class="rk-card-rev">レビュー' + p.reviewCount + '件</span>';
        html += '<span class="rk-card-shop">楽天市場</span>';
        html += '</span></span></a>';
        // 楽天以外(Amazon / Yahoo!ショッピング)も残す。
        // カードだけ出して他店リンクを消していたのは実装漏れ。
        var others = aspLinks.filter(function (a) { return a.key !== 'rakuten'; });
        if (others.length) html += shopButtons(others);
        html += '</div>';
        return;
      }

      // 商品が取れなかった行。カード行と見た目を揃え、店は全部ボタンで並べる。
      html += '<div class="affiliate-item">';
      html += '<div class="aff-row aff-row-plain">';
      html += '<span class="affiliate-icon">' + (ICONS[item.icon] || ICONS.plant) + '</span>';
      html += '<span class="aff-row-body">';
      html += '<span class="affiliate-item-label">' + item.label + '</span>';
      html += '</span></div>';
      html += shopButtons(aspLinks);
      html += '</div>';
    });

    html += '</div>';

    // 枠の注記。Amazon の「アソシエイトとして…」の表記はサイト共通のフッターが持つ
    var notices = [];
    if (aspConfig.amazon && aspConfig.amazon.tag) notices.push('Amazonアソシエイト');
    if (aspConfig.rakuten) notices.push('楽天アフィリエイト');
    if (aspConfig.yahoo && aspConfig.yahoo.sid && aspConfig.yahoo.pid) notices.push('バリューコマース');
    if (mer) notices.push('メルカリアンバサダー');
    var priceShown = items.some(function (it) {
      var p = (data._products || {})[it.keyword];
      return p && p.image && p.url && p.price;
    });
    if (priceShown) {
      notices.unshift('価格・在庫は表示時点のものではなく取得時点のためリンク先をご確認ください');
    }
    html += '<p class="affiliate-notice">※ ' + notices.join(' / ') + '</p>';

    el.innerHTML = html;
  }

  // --- アフィリエイトのクリックをGA4に送る（2026-08-24追加） ---------------
  // これまで一切計測しておらず、「Amazonと楽天のどちらが効いているか」を
  // 各モールの管理画面を突き合わせないと判断できなかった。
  // モール側は自分の分しか見えないので、同じ土俵で比べるにはこちら側で数える必要がある。
  // document 単位で1回だけ張る（カードは後から差し替わるので委譲で拾う）。
  // 店は全リンクの data-shop、置き場所はクラスで分ける。
  var _trackBound = false;
  function bindClickTracking() {
    if (_trackBound) return;
    _trackBound = true;
    document.addEventListener('click', function (ev) {
      var a = ev.target && ev.target.closest
        ? ev.target.closest('a.aff-shop-btn, a.rk-card, a.aff-mercari-btn, .aff-bar a')
        : null;
      if (!a) return;
      if (typeof window.gtag !== 'function') return;

      var placement = a.classList.contains('rk-card') ? 'product_card'
                    : a.closest('.aff-bar') ? 'sticky_bar'
                    : a.classList.contains('aff-mercari-btn') ? 'mercari_row'
                    : a.classList.contains('is-primary') ? 'primary_button'
                    : 'shop_button';
      try {
        window.gtag('event', 'affiliate_click', {
          shop: a.getAttribute('data-shop') || 'other',
          placement: placement,
          page_path: location.pathname
        });
      } catch (e) { /* 計測の失敗で遷移を止めない */ }
    }, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindClickTracking);
  } else {
    bindClickTracking();
  }
})();
