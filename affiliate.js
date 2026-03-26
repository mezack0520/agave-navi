/**
 * Multi-ASP Affiliate Dynamic Link Generator
 * - Loads amazon-links.json (supports Amazon, Rakuten, Yahoo!)
 * - Picks random items based on page category (data-tags)
 * - Each item shows links to all configured ASPs
 * - Renders into .affiliate-section container
 */
(function () {
  'use strict';

  var DISPLAY_COUNT = 4;
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
    amazon: '#ff9900',
    rakuten: '#bf0000',
    yahoo:  '#ff0033'
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

  var container = document.querySelector('.affiliate-section');
  if (!container) return;

  var pageTags = (container.getAttribute('data-tags') || '').split(',').filter(Boolean);

  var jsonUrl = basePath + 'amazon-links.json?v=' + Date.now();
  fetch(jsonUrl)
    .then(function (r) { return r.json(); })
    .then(function (data) { render(data, pageTags, container); })
    .catch(function (e) { console.warn('affiliate.js:', e); });

  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var t = arr[i]; arr[i] = arr[j]; arr[j] = t;
    }
    return arr;
  }

  function pickItems(data, tags) {
    var catItems = [];
    var cats = data.categories || {};
    tags.forEach(function (tag) {
      if (cats[tag]) catItems = catItems.concat(cats[tag]);
    });

    var seen = {};
    var deduped = [];
    catItems.concat(data.common || []).forEach(function (item) {
      if (!seen[item.keyword]) {
        seen[item.keyword] = true;
        deduped.push(item);
      }
    });

    if (catItems.length >= 2) {
      var catPicks = shuffle(catItems.slice()).slice(0, 2);
      var catKws = {};
      catPicks.forEach(function (p) { catKws[p.keyword] = true; });
      var commonFiltered = (data.common || []).filter(function (c) { return !catKws[c.keyword]; });
      var commonPicks = shuffle(commonFiltered).slice(0, DISPLAY_COUNT - catPicks.length);
      return shuffle(catPicks.concat(commonPicks));
    }

    return shuffle(deduped).slice(0, DISPLAY_COUNT);
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

    // Yahoo! Shopping (ValueCommerce)
    var yah = aspConfig.yahoo;
    if (yah) {
      var yahUrl;
      if (yah.sid && yah.pid) {
        yahUrl = 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=' + yah.sid
          + '&pid=' + yah.pid
          + '&vc_url=' + encodeURIComponent('https://shopping.yahoo.co.jp/search?p=' + keyword);
      } else {
        yahUrl = 'https://shopping.yahoo.co.jp/search?p=' + kw;
      }
      links.push({
        label: yah.label || 'Yahoo!',
        url: yahUrl,
        color: ASP_COLORS.yahoo
      });
    }

    return links;
  }

  function render(data, tags, el) {
    var items = pickItems(data, tags);
    var aspConfig = data.asp || { amazon: { tag: data.tag || 'agavenavi-22', searchUrl: 'https://www.amazon.co.jp/s?k={keyword}&tag={tag}', label: 'Amazon' } };

    var html = '<h3>イベント準備におすすめ</h3>';
    html += '<p class="affiliate-desc">イベントをもっと楽しむためのアイテムをチェック</p>';
    html += '<div class="affiliate-links">';

    items.forEach(function (item) {
      var icon = ICONS[item.icon] || ICONS.plant;
      var aspLinks = buildAspLinks(item.keyword, aspConfig);

      html += '<div class="affiliate-item">';
      html += '<div class="affiliate-icon">' + icon + '</div>';
      html += '<div class="affiliate-item-body">';
      html += '<span class="affiliate-item-label">' + item.label + '</span>';
      html += '<div class="affiliate-asp-links">';
      aspLinks.forEach(function (asp) {
        html += '<a href="' + asp.url + '" target="_blank" rel="noopener sponsored"'
          + ' class="asp-badge" style="background:' + asp.color + '">'
          + asp.label + '</a>';
      });
      html += '</div></div></div>';
    });

    html += '</div>';

    // Build notice text
    var notices = [];
    if (aspConfig.amazon && aspConfig.amazon.tag) notices.push('Amazon.co.jpアソシエイト');
    if (aspConfig.rakuten) notices.push('楽天アフィリエイト');
    if (aspConfig.yahoo) notices.push('バリューコマース');
    html += '<p class="affiliate-notice">※ ' + notices.join(' / ') + '</p>';

    el.innerHTML = html;
  }
})();
