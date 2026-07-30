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
      basePath = src.replace('affiliate.js', '');
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
  function fetchProduct(keyword, rk) {
    var q = new URLSearchParams({
      applicationId: rk.applicationId, accessKey: rk.accessKey,
      affiliateId: rk.affiliateId || '', format: 'json', formatVersion: '2',
      hits: '5', imageFlag: '1', sort: '-reviewCount', keyword: keyword
    });
    return fetch(rk.apiEndpoint + '?' + q)
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var arr = (j && (j.items || j.Items)) || [];
        // 極端な価格帯とレビュー0件を避ける
        var it = arr.filter(function (x) {
          return x.itemPrice >= 300 && x.itemPrice <= 200000 && (x.reviewCount || 0) >= 1;
        })[0] || arr[0];
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
      plan.forEach(function (p) {
        p.items.forEach(function (it) {
          var c = store[it.keyword];
          if (c && c.at && (now - c.at) < CACHE_TTL) data._products[it.keyword] = c;
          else if (canFetch && need.indexOf(it.keyword) < 0) need.push(it.keyword);
        });
      });

      function draw() {
        plan.forEach(function (p) {
          render(data, [], p.el, p.guide, p.heading, p.items);
        });
      }
      draw();

      if (!need.length) return;
      // レート制限(1秒1件程度)に配慮して直列に取得する
      var i = 0;
      (function next() {
        if (i >= need.length) { cacheWrite(store); draw(); return; }
        var kw = need[i++];
        fetchProduct(kw, rk).then(function (prod) {
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

  // 同ジャンル(group)が枠を食い合わないように1つずつに絞り、rank順に並べる。
  // rank が小さいほど単価と購買意図が高い想定。先頭が主役枠になる。
  function narrow(items, count) {
    var byGroup = {};
    var out = [];
    items.forEach(function (it) {
      var g = it.group || it.keyword;
      if (byGroup[g]) return;      // 同ジャンルは1つまで
      byGroup[g] = true;
      out.push(it);
    });
    out.sort(function (a, b) { return (a.rank || 9) - (b.rank || 9); });
    return out.slice(0, count);
  }

  function pickItems(data, tags, guideSlug) {
    // ガイド記事: 記事本文が扱う対象をそのまま検索語にする(文脈が最も近く単価も高い)。
    // 記事側の並び順が編集意図なので rank より優先し、ジャンル重複だけ落とす。
    if (guideSlug && data.guides && data.guides[guideSlug]) {
      var g = data.guides[guideSlug].slice();
      var seenG = {};
      g = g.filter(function (it) {
        var k = it.group || it.keyword;
        if (seenG[k]) return false;
        seenG[k] = true;
        return true;
      });
      if (g.length >= DISPLAY_COUNT) return g.slice(0, DISPLAY_COUNT);
      var fill = (data.common || []).filter(function (c) {
        return !seenG[c.group || c.keyword];
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
        html += '<a class="aff-card" href="' + p.url + '" target="_blank" rel="noopener sponsored">';
        html += '<img class="aff-card-img" src="' + p.image + '" alt="" loading="lazy"'
             +  ' referrerpolicy="no-referrer-when-downgrade">';
        html += '<span class="aff-card-body">';
        html += '<span class="aff-card-why">' + item.label + '</span>';
        html += '<span class="aff-card-name">' + p.name + '</span>';
        html += '<span class="aff-card-meta">';
        if (p.price) html += '<span class="aff-card-price">' + Number(p.price).toLocaleString('ja-JP') + '円</span>';
        if (p.reviewCount) html += '<span class="aff-card-rev">レビュー' + p.reviewCount + '件</span>';
        html += '<span class="aff-card-shop">楽天市場</span>';
        html += '</span></span></a>';
        return;
      }

      // 主リンク(先頭ASP)を行の主動線にする。店を選ばせる前に商品へ向かわせる
      var primary = aspLinks[0];
      var alts = aspLinks.slice(1);

      var featured = (idx === 0);
      html += '<div class="affiliate-item' + (featured ? ' is-featured' : '') + '">';
      html += '<a class="aff-row" href="' + primary.url + '" target="_blank" rel="noopener sponsored">';
      html += '<span class="affiliate-icon">' + icon + '</span>';
      html += '<span class="aff-row-body">';
      html += '<span class="affiliate-item-label">' + item.label + '</span>';
      html += '<span class="aff-cta-go">' + primary.label + 'で見る</span>';
      html += '</span></a>';
      if (alts.length) {
        html += '<div class="affiliate-asp-links"><span class="aff-alt-lead">ほかで探す</span>';
        alts.forEach(function (asp, i) {
          html += (i ? '<span class="aff-alt-sep">/</span>' : '')
            + '<a href="' + asp.url + '" target="_blank" rel="noopener sponsored"'
            + ' class="aff-alt-link">' + asp.label + '</a>';
        });
        html += '</div>';
      }
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
})();
