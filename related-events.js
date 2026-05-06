/** 
 * アガベイベントナビ - 関連イベント表示
 * イベント詳細ページの下部に同カテゴリ・同地域のイベントを表示し回遊率を向上
 */
(function () {
  'use strict';
  if (!/\/events\//.test(location.pathname)) return;
  var BASE = location.pathname.replace(/\/events\/.*/, '');
  var EVENTS_JSON = BASE + '/events.json';
  var CURRENT_SLUG = location.pathname.replace(/^.*\/events\//, '').replace(/\.html$/, '');

  function fetchJSON(url, cb) {
    var x = new XMLHttpRequest();
    x.open('GET', url, true);
    x.onreadystatechange = function () {
      if (x.readyState === 4 && x.status === 200) {
        try { cb(JSON.parse(x.responseText)); } catch (e) { /* ignore */ }
      }
    };
    x.send();
  }

  function score(ev, cur) {
    var s = 0;
    if (cur.tags && ev.tags) {
      cur.tags.forEach(function (t) { if (ev.tags.indexOf(t) !== -1) s += 3; });
    }
    if (cur.region && ev.region === cur.region) s += 2;
    var diff = Math.abs(new Date(ev.date) - new Date(cur.date));
    if (diff < 14 * 86400000) s += 1;
    return s;
  }

  function buildCard(ev) {
    var href = BASE + '/events/' + ev.slug + '.html';
    var imgSrc = ev.imageUrl ? ev.imageUrl : BASE + '/images/events/' + ev.slug + '.jpg';
    return (
      '<a href="' + href + '" class="re-card">' +
      '<div class="re-card-img">' +
      '<img src="' + imgSrc + '" alt="' + ev.name + '" loading="lazy" ' +
      'onerror="this.onerror=null;this.style.display=\'none\';this.parentElement.classList.add(\'re-no-image\')">' +
      '</div>' +
      '<div class="re-card-body">' +
      '<p class="re-card-date">' + (ev.dateDisplay || ev.date) + '</p>' +
      '<p class="re-card-title">' + ev.name + '</p>' +
      '<div class="re-card-meta">' +
      '<span class="re-region">' + (ev.prefecture || ev.region || '') + '</span>' +
      '</div>' +
      '</div>' +
      '</a>'
    );
  }

  function injectStyles() {
    var css =
      '.re-section{margin:40px 0 0;padding:30px 0;border-top:1px solid #eee}' +
      '.re-section-title{font-size:1.15rem;font-weight:700;margin:0 0 18px;color:#1a1a1a;display:flex;align-items:center;gap:8px}' +
      '.re-section-title::before{content:"";display:inline-block;width:4px;height:20px;background:var(--accent-pop,#e74c3c);border-radius:2px}' +
      '.re-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px}' +
      '.re-card{display:flex;flex-direction:column;border:1px solid #eee;border-radius:12px;text-decoration:none;color:inherit;transition:box-shadow .2s,transform .15s;background:#fff;overflow:hidden}' +
      '.re-card:hover{box-shadow:0 4px 16px rgba(0,0,0,.08);transform:translateY(-2px)}' +
      '.re-card-img{width:100%;aspect-ratio:16/9;overflow:hidden;background:#f5f5f5}' +
      '.re-card-img img{width:100%;height:100%;object-fit:cover}' +
      '.re-no-image{background:linear-gradient(160deg,#1a1a1a 0%,#252525 40%,#1e1e1e 100%);display:flex;align-items:center;justify-content:center}' +
      '.re-no-image::after{content:"NO IMAGE";color:#555;font-size:.7rem;font-weight:600;letter-spacing:2px}' +
      '.re-card-body{padding:12px;flex:1;min-width:0}' +
      '.re-card-date{font-size:.75rem;color:#888;margin:0 0 4px}' +
      '.re-card-title{font-size:.9rem;font-weight:600;margin:0 0 6px;line-height:1.35;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}' +
      '.re-card-meta{display:flex;flex-wrap:wrap;gap:4px}' +
      '.re-region{font-size:.7rem;padding:2px 8px;border-radius:20px;background:#f0f0f0;color:#555}';
    var s = document.createElement('style');
    s.textContent = css;
    document.head.appendChild(s);
  }

  function render(events) {
    var cur = null;
    var rest = [];
    var today = new Date().toISOString().slice(0, 10);
    events.forEach(function (ev) {
      if (ev.slug === CURRENT_SLUG) { cur = ev; return; }
      var end = ev.dateEnd || ev.date;
      if (end >= today) rest.push(ev);
    });
    if (!cur || rest.length === 0) return;
    rest.sort(function (a, b) { return score(b, cur) - score(a, cur); });
    var picks = rest.slice(0, 4);
    if (picks.length === 0) return;
    injectStyles();
    var html =
      '<div class="re-section">' +
      '<p class="re-section-title">他のおすすめイベント</p>' +
      '<div class="re-grid">' + picks.map(buildCard).join('') + '</div>' +
      '</div>';
    var anchor =
      document.querySelector('.affiliate-section') ||
      document.querySelector('.detail-back') ||
      document.querySelector('main');
    if (anchor) {
      if (anchor.classList && anchor.classList.contains('affiliate-section')) {
        anchor.insertAdjacentHTML('beforebegin', html);
      } else if (anchor.classList && anchor.classList.contains('detail-back')) {
        anchor.insertAdjacentHTML('afterend', html);
      } else {
        anchor.insertAdjacentHTML('beforeend', html);
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { fetchJSON(EVENTS_JSON, render); });
  } else {
    fetchJSON(EVENTS_JSON, render);
  }
})();
