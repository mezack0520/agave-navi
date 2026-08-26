/**
 * Multi-ASP Affiliate Dynamic Link Generator
 * - Loads amazon-links.json (supports Amazon, Rakuten, Yahoo!)
 * - Picks random items based on page category (data-tags)
 * - Each item shows links to all configured ASPs
 * - Renders into .affiliate-section container
 */
(function () {
  'use strict';

  // 表示の一括停止スイッチ。AdSense審査などで止めたいときだけ false にする。
  var AFFILIATE_ENABLED = true;
  if (!AFFILIATE_ENABLED) return;

  var DISPLAY_COUNT = 3;
  var ICONS = {
    pot:   '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>',
    soil:  '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>',
    tool:  '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>',
    light: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/><circle cx="12" cy="12" r="5"/></svg>',
    plant: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M7 20h10"/><path d="M10 20c5.5-2.5 8-8.5 8-12a1 1 0 0 0-1-1c-3.5 0-7.5 2-10 6"/><path d="M10 20c-3-2-5-6-5-9a1 1 0 0 1 1-1c2.5 0 5 1.5 7 4"/></svg>',
    shelf: '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/></svg>',
    book:  '<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/></svg>'
  };

  // ASP brand colors for badges
  var ASP_COLORS = {
    amazon:  '#ff9900',
    rakuten: '#bf0000',
    yahoo:   '#ff0033',
    yahuoku: '#ff0033'
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

  fetch(basePath + 'amazon-links.json?v=' + Date.now())
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
                    heading: el.getAttribute('data-heading') || '' });
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
          render(data, [], p.el, p.guide, p.heading, p.items);
        });
        buildStickyBar(data, plan);
      }
      draw();

      if (!need.length) return;
      // レート制限(1秒1件程度)に配慮して直列に取得する
      var i = 0;
      (function next() {
        if (i >= need.length) { cacheWrite(store); draw(); return; }
        var kw = need[i++];
        fetchProduct(kw, rk, opts[kw]).then(function (prod) {
          if (prod) { data._products[kw] = prod; store[kw] = prod; }
          setTimeout(next, 350);
        });
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
  var stickyDone = false;

  function buildStickyBar(data, plan) {
    if (stickyDone) return;
    if (window.matchMedia && !window.matchMedia('(max-width: 720px)').matches) return;
    try {
      if (sessionStorage.getItem('agn_aff_bar_closed') === '1') return;
    } catch (e) {}
    if (!plan.length) return;

    var products = data._products || {};
    var pick = null;
    for (var i = 0; i < plan[0].items.length && !pick; i++) {
      var it = plan[0].items[i];
      var p = products[it.keyword];
      if (p && p.image && p.url) pick = { item: it, prod: p };
    }
    if (!pick) return;   // 実商品が取れないうちは出さない
    stickyDone = true;

    var bar = document.createElement('div');
    bar.className = 'aff-bar';
    bar.setAttribute('aria-label', '広告');
    bar.innerHTML =
      '<a class="aff-bar-link" href="' + pick.prod.url + '" target="_blank" rel="noopener sponsored">'
      + '<img class="aff-bar-img" src="' + pick.prod.image + '" alt="" loading="lazy"'
      + ' onerror="this.style.visibility=\'hidden\'">'
      + '<span class="aff-bar-body">'
      + '<span class="aff-bar-why">' + pick.item.label + '<span class="aff-bar-pr">PR</span></span>'
      + '<span class="aff-bar-meta">'
      + (pick.prod.price ? '<span class="aff-bar-price">'
          + Number(pick.prod.price).toLocaleString('ja-JP') + '円</span>' : '')
      + '<span class="aff-bar-shop">楽天市場</span></span>'
      + '</span>'
      + '<span class="aff-bar-go">見る</span></a>'
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
      var doc = document.documentElement;
      var scrolled = (window.scrollY || doc.scrollTop);
      var total = Math.max(1, doc.scrollHeight - window.innerHeight);
      var past = (scrolled / total) > 0.45;   // 1画面目は日時・会場を読む場所なので出さない
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

  function shopKey(label) {
    if (label.indexOf('Amazon') >= 0) return 'amazon';
    if (label.indexOf('楽天') >= 0) return 'rakuten';
    if (label.indexOf('ヤフオク') >= 0) return 'yahuoku';
    if (label.indexOf('Yahoo') >= 0) return 'yahoo';
    return 'other';
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

  // 季節の重み付け。amazon-links.json の season(旬の月の配列)を持つ品目だけ、
  // 旬なら rank を上げ、旬を外れていれば下げる。season の無い品目は通年扱いで不変。
  // 8月に「冬の室内管理で徒長させないための育成LED」「取り込み株をまとめて置ける簡易温室」が
  // 最上位に出ていたため導入(2026-08-10)。判定は閲覧者の時計ではなく JST の月で行う。
  var JST_MONTH = (function () {
    var now = new Date();
    return new Date(now.getTime() + (now.getTimezoneOffset() * 60000) + (9 * 3600000)).getMonth() + 1;
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
    // 主役枠が毎回ラベルや図鑑になるのを避けるため rank 順に整える。
    return narrow(catItems.concat(data.common || []), DISPLAY_COUNT);
  }

  /**
   * Build search URLs for all configured ASPs.
   * Returns array of {label, url, color} only for ASPs that have credentials configured.
   */
  function buildAspLinks(keyword, aspConfig) {
    var links = [];
    var kw = encodeURIComponent(keyword);

    // Amazon (always active — tag is already set)
    var amz = aspConfig.amazon;
    if (amz && amz.tag) {
      links.push({
        label: amz.label || 'Amazon',
        url: amz.searchUrl.replace('{keyword}', kw).replace('{tag}', amz.tag),
        color: ASP_COLORS.amazon
      });
    }

    // Rakuten
    var rak = aspConfig.rakuten;
    if (rak) {
      var rakUrl;
      if (rak.affiliateId) {
        rakUrl = 'https://hb.afl.rakuten.co.jp/hgc/' + rak.affiliateId
          + '/?pc=' + encodeURIComponent('https://search.rakuten.co.jp/search/mall/' + keyword + '/');
      } else {
        rakUrl = 'https://search.rakuten.co.jp/search/mall/' + kw + '/';
      }
      links.push({
        label: rak.label || '楽天市場',
        url: rakUrl,
        color: ASP_COLORS.rakuten
      });
    }

    // Yahoo! Shopping (ValueCommerce) — sid/pid が設定済みの場合のみ表示
    var yah = aspConfig.yahoo;
    if (yah && yah.sid && yah.pid) {
      var yahUrl = 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=' + yah.sid
        + '&pid=' + yah.pid
        + '&vc_url=' + encodeURIComponent('https://shopping.yahoo.co.jp/search?p=' + keyword);
      links.push({
        label: yah.label || 'Yahoo!ショッピング',
        url: yahUrl,
        color: ASP_COLORS.yahoo
      });
    }

    // ヤフオク(バリューコマース) — sid/pid が設定済みの場合のみ表示。
    // 株そのものが数千〜数万円で動く場なので、相場を見る導線として効く。
    var auc = aspConfig.yahuoku;
    if (auc && auc.sid && auc.pid) {
      links.push({
        label: auc.label || 'ヤフオク',
        url: 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=' + auc.sid
          + '&pid=' + auc.pid
          + '&vc_url=' + encodeURIComponent('https://auctions.yahoo.co.jp/search/search?p=' + keyword),
        color: ASP_COLORS.yahuoku
      });
    }

    return links;
  }

  function render(data, tags, el, guideSlug, heading, presetItems) {
    var items = presetItems || pickItems(data, tags, guideSlug);
    if (!items.length) return;
    var aspConfig = data.asp || { amazon: { tag: data.tag || 'agavenavi-22', searchUrl: 'https://www.amazon.co.jp/s?k={keyword}&tag={tag}', label: 'Amazon' } };

    var title = heading || (guideSlug ? 'この記事で使う道具・資材' : '株を持ち帰る前に揃えるもの');
    var desc = guideSlug
      ? '本文で触れた資材を各ショップで探せます'
      : '当日の運搬と、帰宅後の植え替え・発根管理で必要になるもの';

    var html = '<div class="aff-head"><h3>' + title + '</h3>'
             + '<span class="aff-pr">PR</span></div>';
    html += '<p class="affiliate-desc">' + desc + '</p>';
    html += '<div class="affiliate-links">';

    var products = data._products || {};

    items.forEach(function (item, idx) {
      var icon = ICONS[item.icon] || ICONS.plant;
      var aspLinks = buildAspLinks(item.keyword, aspConfig);
      if (!aspLinks.length) return;

      // 実商品カード: 画像・商品名・価格。価格は取得時点である旨を添える
      var p = products[item.keyword];
      if (p && p.image && p.url) {
        html += '<div class="affiliate-item">';
        html += '<a class="rk-card" href="' + p.url + '" target="_blank" rel="noopener sponsored">';
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
        // 楽天以外(Amazon / Yahoo!ショッピング / ヤフオク)も残す。
        // カードだけ出して他店リンクを消していたのは実装漏れ。
        var others = aspLinks.filter(function (a) { return a.label !== '楽天市場'; });
        if (others.length) {
          html += '<div class="aff-shop-btns">';
          others.forEach(function (asp, i) {
            // 先頭(Amazon)を主動線にする。実測でAmazonだけが売れている
            // (2026-08-24: 過去30日 Amazon 14クリック/5点/¥214、楽天 16クリック/0件/¥0)。
            html += '<a href="' + asp.url + '" target="_blank" rel="noopener sponsored"'
              + ' class="aff-shop-btn' + (i === 0 ? ' is-primary' : '') + '"'
              + ' data-shop="' + shopKey(asp.label) + '">'
              + asp.label + 'で探す</a>';
          });
          html += '</div>';
        }
        html += '</div>';
        return;
      }

      // 主リンク(先頭ASP)を行の主動線にする。店を選ばせる前に商品へ向かわせる
      var primary = aspLinks[0];
      var alts = aspLinks.slice(1);

      // 商品が取れなかった行。カード行と見た目を揃え、店は全部ボタンで並べる。
      html += '<div class="affiliate-item">';
      html += '<div class="aff-row aff-row-plain">';
      html += '<span class="affiliate-icon">' + icon + '</span>';
      html += '<span class="aff-row-body">';
      html += '<span class="affiliate-item-label">' + item.label + '</span>';
      html += '</span></div>';
      html += '<div class="aff-shop-btns">';
      aspLinks.forEach(function (asp, i) {
        html += '<a href="' + asp.url + '" target="_blank" rel="noopener sponsored"'
          + ' class="aff-shop-btn' + (i === 0 ? ' is-primary' : '') + '"'
          + ' data-shop="' + shopKey(asp.label) + '">'
          + asp.label + 'で探す</a>';
      });
      html += '</div>';
      html += '</div>';
    });

    html += '</div>';

    // Build notice text
    var notices = [];
    if (aspConfig.amazon && aspConfig.amazon.tag) notices.push('Amazon.co.jpアソシエイト');
    if (aspConfig.rakuten) notices.push('楽天アフィリエイト');
    if ((aspConfig.yahoo && aspConfig.yahoo.sid && aspConfig.yahoo.pid)
        || (aspConfig.yahuoku && aspConfig.yahuoku.sid && aspConfig.yahuoku.pid)) notices.push('バリューコマース');
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
  var _trackBound = false;
  function bindClickTracking() {
    if (_trackBound) return;
    _trackBound = true;
    document.addEventListener('click', function (ev) {
      var a = ev.target && ev.target.closest
        ? ev.target.closest('a.aff-shop-btn, a.rk-card, .aff-bar a')
        : null;
      if (!a) return;
      if (typeof window.gtag !== 'function') return;

      var shop = a.getAttribute('data-shop');
      if (!shop) {
        // 楽天カードと固定バーは data-shop を持たない。リンク先から判定する
        var h = a.getAttribute('href') || '';
        shop = h.indexOf('rakuten') >= 0 ? 'rakuten'
             : h.indexOf('amazon') >= 0 ? 'amazon'
             : h.indexOf('valuecommerce') >= 0 ? 'valuecommerce'
             : 'other';
      }
      var placement = a.classList.contains('rk-card') ? 'product_card'
                    : a.closest('.aff-bar') ? 'sticky_bar'
                    : a.classList.contains('is-primary') ? 'primary_button'
                    : 'shop_button';
      try {
        window.gtag('event', 'affiliate_click', {
          shop: shop,
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
