/**
 * Auto Status Label - イベント日付から自動でステータスラベルを計算
 * 毎回ページ表示時に現在日付と比較して判定
 */
(function () {
  'use strict';

  var STATUS = {
    thisweek: { label: '今週末', cls: 'status-thisweek' },
    soon:     { label: 'もうすぐ', cls: 'status-soon' },
    month:    { label: '1ヶ月以内', cls: 'status-month' },
    upcoming: { label: '開催予定', cls: 'status-upcoming' },
    ended:    { label: '終了', cls: 'status-ended' }
  };

  function getStatus(dateStr) {
    var today = new Date();
    today.setHours(0, 0, 0, 0);
    var eventDate = new Date(dateStr + 'T00:00:00');
    var diff = Math.ceil((eventDate - today) / (1000 * 60 * 60 * 24));

    // 終了: 過去の日付
    if (diff < 0) return STATUS.ended;

    // 今週末: 今日〜次の日曜日（土日含む）
    var dayOfWeek = today.getDay(); // 0=日, 6=土
    var daysUntilSunday = (7 - dayOfWeek) % 7;
    if (daysUntilSunday === 0 && dayOfWeek === 0) daysUntilSunday = 0; // 日曜なら今日まで
    // 月〜金: 次の土日, 土: 今日と明日, 日: 今日
    if (dayOfWeek === 0) {
      // 今日が日曜 → 今日のイベントが「今週末」
      if (diff === 0) return STATUS.thisweek;
    } else {
      // 月〜土 → 次の日曜日まで（inclusive）
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
  document.querySelectorAll('.event-card').forEach(function (card) {
    var dateStr = card.getAttribute('data-date');
    if (!dateStr) return;
    var statusEl = card.querySelector('.event-status');
    if (!statusEl) return;

    var status = getStatus(dateStr);
    statusEl.textContent = status.label;
    statusEl.className = 'event-status ' + status.cls;
  });

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
      var status = getStatus(dateAttr);
      badge.textContent = status.label;
      // 色を直接適用（詳細ページはCSSクラスではなくインラインスタイル）
      var colors = {
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
})();
