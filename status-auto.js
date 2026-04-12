/**
 * Auto Status Label - イベント日付から自動でステータスラベルを計算
 * 毎回ページ表示時に現在日付と比較して判定
 */
(function () {
  'use strict';

  var STATUS = {
    today:    { label: '本日開催', cls: 'status-today' },
    thisweek: { label: '今週末', cls: 'status-thisweek' },
    soon:     { label: 'もうすぐ', cls: 'status-soon' },
    month:    { label: '1ヶ月以内', cls: 'status-month' },
    upcoming: { label: '開催予定', cls: 'status-upcoming' },
    ended:    { label: '終了', cls: 'status-ended' }
  };

  function getStatus(dateStr, dateEndStr) {
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var eventDate = new Date(dateStr + 'T00:00:00');
    var endDate = dateEndStr ? new Date(dateEndStr + 'T00:00:00') : eventDate;
    var diff = Math.ceil((eventDate - today) / (1000 * 60 * 60 * 24));
    var diffEnd = Math.ceil((endDate - today) / (1000 * 60 * 60 * 24));

    // 本日開催中: 開始日 <= 今日 <= 終了日
    if (diff <= 0 && diffEnd >= 0) return STATUS.today;

    // 終了: 終了日が過去
    if (diffEnd < 0) return STATUS.ended;

    // 今週末: 今日〜次の日曜日（土日含む）
    var dayOfWeek = today.getDay(); // 0=日, 6=土
    var daysUntilSunday = (7 - dayOfWeek) % 7;
    if (daysUntilSunday === 0 && dayOfWeek === 0) daysUntilSunday = 0; // 日曜なら今日まで
    // 月〜金: 次の土日, 土: 今日と明日, 日: 今日
    if (dayOfWeek === 0) {
      if (diff === 0) return STATUS.thisweek;
    } else {
      if (diff <= daysUntilSunday) return STATUS.thisweek;
    }

    // もうすぐ: 2週間以内
    if (diff <= 14) return STATUS.soon;

    // 1ヶ月以内
    if (diff <= 31) return STATUS.month;

    // 開催予定: それ以外の未来
    return STATUS.upcoming;
  }

  // index / category ページ: .event-card の .event-status を更新
  var endedCards = [];
  document.querySelectorAll('.event-card').forEach(function (card) {
    var dateStr = card.getAttribute('data-date');
    if (!dateStr) return;
    var dateEndStr = card.getAttribute('data-date-end') || '';
    var statusEl = card.querySelector('.event-status');
    if (!statusEl) return;

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

  // detail ページ: .detail-status-badge を更新
  var badge = document.querySelector('.detail-status-badge');
  var detailDate = document.querySelector('.detail-meta-item');
  if (badge && detailDate) {
    // data-date 属性があればそれを使う、なければテキストからパース
    var dateAttr = badge.getAttribute('data-date');
    if (!dateAttr) {
      // テキストから "2026年4月4日" のような日付を抽出
      var match = detailDate.textContent.match(/(\d{4})年(\d{1,2})月(\d{1,2})日/);
      if (match) {
        dateAttr = match[1] + '-' + match[2].padStart(2, '0') + '-' + match[3].padStart(2, '0');
      }
    }
    if (dateAttr) {
      var dateEndAttr = badge.getAttribute('data-date-end') || '';
      var status = getStatus(dateAttr, dateEndAttr);
      badge.textContent = status.label;
      // 色を直接適用（詳細ページはCSSクラスではなくインラインスタイル）
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
