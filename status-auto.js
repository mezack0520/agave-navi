/**
 * Auto Status Label - ã¤ãã³ãæ¥ä»ããèªåã§ã¹ãã¼ã¿ã¹ã©ãã«ãè¨ç®
 * æ¯åãã¼ã¸è¡¨ç¤ºæã«ç¾å¨æ¥ä»ã¨æ¯è¼ãã¦å¤å®
 */
(function () {
  'use strict';

  var STATUS = {
    today:    { label: 'æ¬æ¥éå¬', cls: 'status-today' },
    thisweek: { label: 'ä»é±æ«', cls: 'status-thisweek' },
    soon:     { label: 'ãããã', cls: 'status-soon' },
    month:    { label: '1ã¶æä»¥å', cls: 'status-month' },
    upcoming: { label: 'éå¬äºå®', cls: 'status-upcoming' },
    ended:    { label: 'çµäº', cls: 'status-ended' }
  };

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
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var eventDate = new Date(dateStr + 'T00:00:00');
    var endDate = dateEndStr ? new Date(dateEndStr + 'T00:00:00') : eventDate;
    var diff = Math.ceil((eventDate - today) / (1000 * 60 * 60 * 24));
    var diffEnd = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));

    // æ¬æ¥éå¬ä¸­: éå§æ¥ <= ä»æ¥ <= çµäºæ¥
    if (diff <= 0 && diffEnd >= 0) return STATUS.today;

    // çµäº: çµäºæ¥ãéå»
    if (diffEnd < 0) return STATUS.ended;

    // ä»é±æ«: ä»æ¥ãæ¬¡ã®æ¥ææ¥ï¼åæ¥å«ãï¼
    var dayOfWeek = today.getDay(); // 0=æ¥, 6=å
    var daysUntilSunday = (7 - dayOfWeek) % 7;
    if (daysUntilSunday === 0 && dayOfWeek === 0) daysUntilSunday = 0; // æ¥æãªãä»æ¥ã¾ã§
    // æãé: æ¬¡ã®åæ¥, å: ä»æ¥ã¨ææ¥, æ¥: ä»æ¥
    if (dayOfWeek === 0) {
      if (diff === 0) return STATUS.thisweek;
    } else {
      if (diff <= daysUntilSunday) return STATUS.thisweek;
    }

    // ãããã: 2é±éä»¥å
    if (diff <= 14) return STATUS.soon;

    // 1ã¶æä»¥å
    if (diff <= 31) return STATUS.month;

    // éå¬äºå®: ããä»¥å¤ã®æªæ¥
    return STATUS.upcoming;
  }

  // index / category ãã¼ã¸: .event-card ã® .event-status ãæ´æ°
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

    // çµäºããã¤ãã³ããè¨é²
    if (status === STATUS.ended) {
      endedCards.push(card);
    }
  });

  // æ°çããã¸ãè¿½å : addedDate ã7æ¥ä»¥åã®ã¤ãã³ãã«è¡¨ç¤º
  document.querySelectorAll('.event-card').forEach(function (card) {
    var addedDateStr = card.getAttribute('data-added-date');
    if (!addedDateStr) return;

    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var addedDate = new Date(addedDateStr + 'T00:00:00');
    var daysSinceAdded = Math.floor((today - addedDate) / (1000 * 60 * 60 * 24));

    // 7æ¥ä»¥åãªãæ°çããã¸ãè¡¨ç¤º
    if (daysSinceAdded >= 0 && daysSinceAdded <= 7) {
      var badge = document.createElement('span');
      badge.className = 'new-badge';
      badge.textContent = 'æ°ç';
      card.appendChild(badge);
    }
  });

  // çµäºã¤ãã³ããèªåã§ãçµäºããã¤ãã³ããã»ã¯ã·ã§ã³ã«ç§»å
  var pastGrid = document.getElementById('pastEventsGrid');
  if (pastGrid && endedCards.length > 0) {
    endedCards.forEach(function (card) {
      // æ¢ã«çµäºã»ã¯ã·ã§ã³ã«ããå ´åã¯ã¹ã­ãã
      if (card.closest('#pastEventsGrid')) return;
      // ã«ã¼ããéå¬ä¸­ã°ãªããããçµäºã°ãªããã«ç§»å
      card.classList.add('event-ended');
      pastGrid.insertBefore(card, pastGrid.firstChild);
    });

    // çµäºã»ã¯ã·ã§ã³ã®è¦åºããè¡¨ç¤ºï¼éè¡¨ç¤ºã®å ´åï¼
    var pastHeading = pastGrid.previousElementSibling;
    if (pastHeading && pastHeading.style) {
      pastHeading.style.display = '';
    }

    // éå¬äºå®ã®ä»¶æ°ãæ´æ°
    var countBadge = document.querySelector('.section-heading .count-badge, .event-count');
    if (countBadge) {
      var activeGrid = document.getElementById('eventsGrid');
      if (activeGrid) {
        var activeCards = activeGrid.querySelectorAll('.event-card');
        countBadge.textContent = activeCards.length + 'ä»¶';
      }
    }
  }

  // 2é±éä»¥ä¸åã®çµäºã¤ãã³ããéè¡¨ç¤ºï¼ãã¼ã¸è¥å¤§åé²æ­¢ï¼
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
    // è¡¨ç¤ºå¯è½ãªçµäºã¤ãã³ãã0ä»¶ãªãè¦åºããéè¡¨ç¤º
    var visiblePast = pastGrid.querySelectorAll('.event-card:not([style*="display: none"])');
    if (visiblePast.length === 0) {
      pastGrid.style.display = 'none';
      var pastHeading2 = pastGrid.previousElementSibling;
      if (pastHeading2) pastHeading2.style.display = 'none';
    }
  }

  // detail ãã¼ã¸: .detail-status-badge ãæ´æ°ï¼events.jsonããçµäºæ¥ãåå¾ï¼
  var badge = document.querySelector('.detail-status-badge');
  var detailDate = document.querySelector('.detail-meta-item');
  if (badge && detailDate) {
    var dateAttr = badge.getAttribute('data-date');
    if (!dateAttr) {
      var match = detailDate.textContent.match(/(\d{4})å¹´(\d{1,2})æ(\d{1,2})æ¥/);
      if (match) {
        dateAttr = match[1] + '-' + match[2].padStart(2, '0') + '-' + match[3].padStart(2, '0');
      }
    }
    var dateEndAttr = badge.getAttribute('data-date-end') || '';
    // data-date-endããªãå ´åãevents.jsonããslugã§çµäºæ¥ãåå¾
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

  // ã«ã¼ãç§»åå®äºå¾ã«ãã£ã¨è¦ãå¶éãåé©ç¨
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
