/**
 * Auto Status Label - イベント日付から自動でステータスラベルを計算
 * 毎回ページ表示時に現在日付と比較して判定
 */
(function () {
  'use strict';

  var STATUS = {
    today:    { label: '本日開催', cls: 'status-today' },
    tomorrow: { label: '明日開催', cls: 'status-thisweek' },
    soonD:    { cls: 'status-thisweek' },   // あとN日 (1-3日)
    weekD:    { cls: 'status-soon' },        // あとN日 (4-13日)
    monthD:   { cls: 'status-month' },       // あとN日 (14-31日)
    upcomingD:{ cls: 'status-upcoming' },    // あとN日 (32+)
    ended:    { label: '終了', cls: 'status-ended' }
  };

  function dayLabel(d) { return 'あと' + d + '日'; }

  // data-date がない場合、.event-date テキストから日付をパース
  function parseDateFromText(card) {
    var el = card.querySelector('.event-date');
    if (!el) return { start: '', end: '' };
    var text = el.textContent.trim();
    var m = text.match(/(\d{4})\.(\d{1,2})\.(\d{1,2})(?:-(\d{1,2}))?/);
    if (!m) return { start: '', end: '' };
    var y = m[1], mo = m[2].padStart(2, '0'), d = m[3].padStart(2, '0');
    var start = y + '-' + mo + '-' + d;
    var end = '';
    if (m[4]) { end = y + '-' + mo + '-' + m[4].padStart(2, '0'); }
    return { start: start, end: end };
  }

  function getStatus(dateStr, dateEndStr) {
    // JST calendar-day based comparison
    var now = new Date();
    var jstMs = now.getTime() + (now.getTimezoneOffset()*60000) + (9*3600000);
    var j = new Date(jstMs);
    var todayStr = j.getUTCFullYear() + '-' + String(j.getUTCMonth()+1).padStart(2,'0') + '-' + String(j.getUTCDate()).padStart(2,'0');
    var todayJST = new Date(todayStr + 'T00:00:00+09:00');
    var eventDate = new Date(dateStr + 'T00:00:00+09:00');
    var endDate = (dateEndStr ? new Date(dateEndStr + 'T00:00:00+09:00') : eventDate);
    var diff = Math.round((eventDate - todayJST) / 86400000);
    var diffEnd = Math.round((endDate - todayJST) / 86400000);

    // 本日開催中
    if (diff <= 0 && diffEnd >= 0) return STATUS.today;
    // 終了
    if (diffEnd < 0) return STATUS.ended;
    // 明日
    if (diff === 1) return STATUS.tomorrow;
    // あとN日 — 緊急度に応じてクラス分け
    var s;
    if (diff <= 3) s = Object.assign({}, STATUS.soonD);
    else if (diff <= 13) s = Object.assign({}, STATUS.weekD);
    else if (diff <= 31) s = Object.assign({}, STATUS.monthD);
    else s = Object.assign({}, STATUS.upcomingD);
    s.label = dayLabel(diff);
    return s;
  }

  // index / category ページ: .event-card の .event-status を更新
  var endedCards = [];
  document.querySelectorAll('.event-card').forEach(function (card) {
    var dateStr = card.getAttribute('data-date');
    var dateEndStr = card.getAttribute('data-date-end') || '';
    if (!dateStr) {
      var parsed = parseDateFromText(card);
      if (!parsed.start) return;
      dateStr = parsed.start;
      if (!dateEndStr && parsed.end) dateEndStr = parsed.end;
    }
    var statusEl = card.querySelector('.event-status');
    if (!statusEl) {
      statusEl = document.createElement('span');
      statusEl.className = 'event-status';
      var dateEl = card.querySelector('.event-date');
      if (dateEl && dateEl.parentNode) {
        dateEl.parentNode.insertBefore(statusEl, dateEl.nextSibling);
      } else { return; }
    }

    var status = getStatus(dateStr, dateEndStr);
    statusEl.textContent = status.label;
    statusEl.className = 'event-status ' + status.cls;

    // 終了したイベントを記録
    if (status === STATUS.ended) {
      endedCards.push(card);
    }
  });

  // 新着バッジを追加: addedDate が7日以内のイベントに表示
  document.querySelectorAll('.event-card').forEach(function (card) {
    var addedDateStr = card.getAttribute('data-added-date');
    if (!addedDateStr) return;

    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var addedDate = new Date(addedDateStr + 'T00:00:00');
    var daysSinceAdded = Math.floor((today - addedDate) / (1000 * 60 * 60 * 24));

    // 7日以内なら新着バッジを表示
    if (daysSinceAdded >= 0 && daysSinceAdded <= 7) {
      var badge = document.createElement('span');
      badge.className = 'new-badge';
      badge.textContent = '新着';
      card.appendChild(badge);
    }
  });

  // 終了イベントを自動で「終了したイベント」セクションに移動
  var pastGrid = document.getElementById('pastEventsGrid');
  if (pastGrid && endedCards.length > 0) {
    endedCards.forEach(function (card) {
      // 既に終了セクションにある場合はスキップ
      if (card.closest('#pastEventsGrid')) return;
      // カードを開催中グリッドから終了グリッドに移動
      card.classList.add('event-ended');
      pastGrid.insertBefore(card, pastGrid.firstChild);
    });

    // 終了セクションの見出しを表示（非表示の場合）
    var pastHeading = pastGrid.previousElementSibling;
    if (pastHeading && pastHeading.style) {
      pastHeading.style.display = '';
    }

    // 開催予定の件数を更新
    var countBadge = document.querySelector('.section-heading .count-badge, .event-count');
    if (countBadge) {
      var activeGrid = document.getElementById('eventsGrid');
      if (activeGrid) {
        var activeCards = activeGrid.querySelectorAll('.event-card');
        countBadge.textContent = activeCards.length + '件';
      }
    }
  }

  // 2週間以上前の終了イベントを非表示（ページ肥大化防止）
  var HIDE_AFTER_DAYS = 14;
  if (pastGrid) {
    pastGrid.querySelectorAll('.event-card').forEach(function (card) {
      var dateStr = card.getAttribute('data-date');
      if (!dateStr) return;
      var today = new Date(); today.setHours(0, 0, 0, 0);
      var eventDate = new Date(dateStr + 'T00:00:00');
      var daysSince = Math.floor((today - eventDate) / (1000 * 60 * 60 * 24));
      if (daysSince > HIDE_AFTER_DAYS) {
        card.style.display = 'none';
      }
    });
    // 表示可能な終了イベントが0件なら見出しも非表示
    var visiblePast = pastGrid.querySelectorAll('.event-card:not([style*="display: none"])');
    if (visiblePast.length === 0) {
      pastGrid.style.display = 'none';
      var pastHeading2 = pastGrid.previousElementSibling;
      if (pastHeading2) pastHeading2.style.display = 'none';
    }
  }

  // detail ページ: .detail-status-badge を更新（events.jsonから終了日も取得）
  var badge = document.querySelector('.detail-status-badge');
  var detailDate = document.querySelector('.detail-meta-item, .eh-spec .info-value');
  if (badge) {
    var dateAttr = badge.getAttribute('data-date');
    if (!dateAttr && detailDate) {
      var match = detailDate.textContent.match(/(\d{4})年(\d{1,2})月(\d{1,2})日/);
      if (match) {
        dateAttr = match[1] + '-' + match[2].padStart(2, '0') + '-' + match[3].padStart(2, '0');
      }
    }
    var dateEndAttr = badge.getAttribute('data-date-end') || '';
    // data-date-endがない場合、events.jsonからslugで終了日を取得
    if (dateAttr && !dateEndAttr) {
      var slug = location.pathname.replace(/.*\//, '').replace(/\.html$/, '');
      try {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/events.json', false);
        xhr.send();
        if (xhr.status === 200) {
          var evts = JSON.parse(xhr.responseText);
          var ev = evts.find(function(e) { return e.slug === slug; });
          if (ev && ev.dateEnd) dateEndAttr = ev.dateEnd;
        }
      } catch(e) {}
    }
    if (dateAttr) {
      var status = getStatus(dateAttr, dateEndAttr);
      badge.textContent = status.label;
      var colors = {
        'status-today': '#e84393',
        'status-thisweek': '#d63031',
        'status-soon': '#e17055',
        'status-month': '#f39c12',
        'status-upcoming': '#636e72',
        'status-ended': '#b2bec3'
      };
      badge.style.backgroundColor = colors[status.cls] || '#636e72';
      if (status.cls === 'status-ended') badge.style.color = '#636e72';
    }
  }

  // カード移動完了後にもっと見る制限を再適用
  if (typeof initLoadMore === 'function') {
    initLoadMore();
  }
  if (typeof initPastLoadMore === 'function') {
    initPastLoadMore();
  }
  if (typeof applyFilters === 'function') {
    applyFilters();
  }

  // Inject new-badge CSS
  var style = document.createElement('style');
  style.textContent = '.new-badge { position:absolute; top:8px; left:8px; background:#00b894; color:#fff; font-size:0.7rem; font-weight:700; padding:2px 8px; border-radius:4px; z-index:3; letter-spacing:0.05em; pointer-events:none; }';
  document.head.appendChild(style);

})();
