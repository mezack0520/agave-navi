/**
 * Auto Status Label - イベント日付から自動でステータスラベルを計算
 * 毎回ページ表示時に現在日付と比較して判定
 */
(function () {
  'use strict';

  // --- 時間軸 (フロント側の単一情報源) ---
  // scripts/sitelib.py の event_phase / list_sort_key / is_long_run と同じ規則。
  // 以前は index.html のインラインJSに getCardDate / autoExpireEvents / sortAndFilter
  // の別実装があり、開始日だけで並べていたため会期の長い回が一覧の先頭に居座った。
  // 規則をここに集約し、index.html は UI のフックだけを持つ。
  var AEN_TIME = (function () {
    var LONG_RUN_DAYS = 4;      // sitelib.LONG_RUN_DAYS と同値
    var PAST_KEEP_DAYS = 14;    // sitelib.PAST_KEEP_DAYS と同値
    var FAR_FUTURE = '9999-12-31';
    // JSTの「今日」。Date.now() は常にUTCエポックなので、9時間足して
    // UTCの読み出しを使えばJSTの暦日になる。閲覧者のタイムゾーンには依存しない。
    //
    // 直してはいけない形(2026-08-29に発覚):
    //   new Date(n.getTime() + n.getTimezoneOffset()*60000 + 9*3600000)
    // getTime() は既にUTCなのに、ローカル壁時計だと思って時差を足している。
    // JSTの閲覧者では -9h と +9h が打ち消し合ってUTCの日付が返り、
    // 0:00〜9:00 JST のあいだ丸9時間ずっと前日と判定されていた。
    // 「本日開催」が「明日開催」に、翌日の回が「あと2日」にずれる。
    // JST以外の閲覧者では偶然正しく出るので、東京で朝に見たときだけ壊れる。
    function todayJST() {
      var j = new Date(Date.now() + 9 * 3600000);
      return j.getUTCFullYear() + '-' + String(j.getUTCMonth() + 1).padStart(2, '0')
             + '-' + String(j.getUTCDate()).padStart(2, '0');
    }
    function diffDays(from, to) {
      return Math.round((new Date(to + 'T00:00:00+09:00') - new Date(from + 'T00:00:00+09:00')) / 86400000);
    }
    function days(start, end) {
      if (!start) return null;
      return diffDays(start, end || start) + 1;
    }
    function isLongRun(start, end) {
      var n = days(start, end);
      return n !== null && n >= LONG_RUN_DAYS;
    }
    function phase(start, end, today) {
      if (!start) return 'undated';
      var t = today || todayJST();
      var e = end || start;
      if (e < t) return 'past';
      if (start <= t) return 'ongoing';
      return 'upcoming';
    }
    // 開催中の回は「今日始まる回」と同じ位置に置く。同じ日付では
    // 今日始まる回を先に、会期の途中の回を後ろに。
    function listSortKey(start, end, today, name) {
      var t = today || todayJST();
      if (!start) return [FAR_FUTURE, 2, FAR_FUTURE, name || ''];
      var e = end || start;
      if (e < t) return [start, 0, start, name || ''];
      return [(start > t ? start : t), (start < t ? 1 : 0), start, name || ''];
    }
    function ongoingSortKey(start, end, name) {
      return [(end || start || FAR_FUTURE), (start || FAR_FUTURE), name || ''];
    }
    function cmpKey(a, b) {
      for (var i = 0; i < a.length; i++) {
        if (a[i] < b[i]) return -1;
        if (a[i] > b[i]) return 1;
      }
      return 0;
    }
    function md(iso) {
      if (!iso || iso.length < 10) return '';
      return String(parseInt(iso.slice(5, 7), 10)) + '/' + String(parseInt(iso.slice(8, 10), 10));
    }
    return {
      LONG_RUN_DAYS: LONG_RUN_DAYS, PAST_KEEP_DAYS: PAST_KEEP_DAYS,
      todayJST: todayJST, diffDays: diffDays,
      days: days, isLongRun: isLongRun, phase: phase, listSortKey: listSortKey,
      ongoingSortKey: ongoingSortKey, cmpKey: cmpKey, md: md
    };
  })();
  window.AEN_TIME = AEN_TIME;

  var STATUS = {
    today:    { label: '本日開催', cls: 'status-today' },
    ongoing:  { cls: 'status-ongoing' },     // 開催中 〜M/D (会期2日目以降)
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
    var today = AEN_TIME.todayJST();
    var ph = AEN_TIME.phase(dateStr, dateEndStr, today);
    if (ph === 'past') return STATUS.ended;
    if (ph === 'ongoing') {
      // 初日は「本日開催」。2日目以降を「本日開催」のままにすると、
      // 会期49日の展示が最緊急ラベルで1か月以上出続ける。
      if (dateStr === today) return STATUS.today;
      var o = Object.assign({}, STATUS.ongoing);
      o.label = '開催中 〜' + AEN_TIME.md(dateEndStr || dateStr);
      return o;
    }
    var diff = AEN_TIME.diffDays(today, dateStr);
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

  // 日付境界のテスト(scripts/test-date-boundary.js)から呼ぶ。
  AEN_TIME.statusFor = getStatus;

  function cardSpan(card) {
    var st = card.getAttribute('data-date') || '';
    var en = card.getAttribute('data-date-end') || '';
    if (!st) {
      var p = parseDateFromText(card);
      st = p.start;
      if (!en) en = p.end;
    }
    return { start: st, end: en || st };
  }

  // 一覧の振り分けと並び替え。開催中の長期開催は「開催中」枠へ、
  // 終了は「終了したイベント」へ、残りを一覧本体に置いて時系列に並べる。
  function arrangeList() {
    var grid = document.getElementById('eventsGrid');
    if (!grid) return;
    var ongoingGrid = document.getElementById('ongoingEventsGrid');
    var pastGrid = document.getElementById('pastEventsGrid');
    var today = AEN_TIME.todayJST();
    var orderEl = document.getElementById('sortOrder');
    var desc = !!orderEl && orderEl.value === 'date-desc';

    var pools = [grid];
    if (ongoingGrid) pools.push(ongoingGrid);
    if (pastGrid) pools.push(pastGrid);
    var cards = [];
    pools.forEach(function (g) {
      Array.prototype.push.apply(cards, Array.prototype.slice.call(g.querySelectorAll('.event-card')));
    });

    var ongoing = [], main = [], past = [];
    cards.forEach(function (card) {
      var sp = cardSpan(card);
      card.__aenSpan = sp;
      var ph = AEN_TIME.phase(sp.start, sp.end, today);
      if (ph === 'past') {
        card.classList.add('event-ended');
        card.setAttribute('data-status', 'past');
        past.push(card);
      } else {
        card.classList.remove('event-ended');
        if (card.getAttribute('data-status') === 'past') card.setAttribute('data-status', 'upcoming');
        if (ongoingGrid && ph === 'ongoing' && AEN_TIME.isLongRun(sp.start, sp.end)) ongoing.push(card);
        else main.push(card);
      }
    });

    function nameOf(c) {
      var t = c.querySelector('.event-title');
      return t ? t.textContent : '';
    }
    ongoing.sort(function (a, b) {
      return AEN_TIME.cmpKey(AEN_TIME.ongoingSortKey(a.__aenSpan.start, a.__aenSpan.end, nameOf(a)),
                             AEN_TIME.ongoingSortKey(b.__aenSpan.start, b.__aenSpan.end, nameOf(b)));
    });
    main.sort(function (a, b) {
      var r = AEN_TIME.cmpKey(AEN_TIME.listSortKey(a.__aenSpan.start, a.__aenSpan.end, today, nameOf(a)),
                              AEN_TIME.listSortKey(b.__aenSpan.start, b.__aenSpan.end, today, nameOf(b)));
      return desc ? -r : r;
    });
    past.sort(function (a, b) { return AEN_TIME.cmpKey([b.__aenSpan.end], [a.__aenSpan.end]); });

    if (ongoingGrid) ongoing.forEach(function (c) { ongoingGrid.appendChild(c); });
    main.forEach(function (c) { grid.appendChild(c); });
    if (pastGrid) past.forEach(function (c) { pastGrid.appendChild(c); });

    var show = ongoing.length > 0;
    var oh = document.getElementById('ongoingHeading');
    var uh = document.getElementById('upcomingHeading');
    if (ongoingGrid) ongoingGrid.style.display = show ? '' : 'none';
    if (oh) oh.style.display = show ? '' : 'none';
    // トップは開催中が無ければ「これから開催」の見出しも消して元の見た目に戻す。
    // ランディングは下に終了の節があるので見出しを残す。意図はDOM側に書く。
    if (uh && uh.hasAttribute('data-hide-when-no-ongoing')) {
      uh.style.display = show ? '' : 'none';
    }
    // 見出しには、その節に何件載っているかを書く。
    if (uh) {
      var note = uh.querySelector('.section-heading-note');
      if (!note) {
        note = document.createElement('span');
        note.className = 'section-heading-note';
        uh.appendChild(note);
      }
      note.textContent = main.length + '件';
    }
  }
  window.AEN_LIST = { arrange: arrangeList };

  // index / category ページ: .event-card の .event-status を更新
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
  });

  // 新着バッジを追加: addedDate が7日以内のイベントに表示
  document.querySelectorAll('.event-card').forEach(function (card) {
    var addedDateStr = card.getAttribute('data-added-date');
    if (!addedDateStr) return;

    // 閲覧者のローカル日付ではなくJSTで数える。掲載日はJSTで書かれている。
    var daysSinceAdded = AEN_TIME.diffDays(addedDateStr, AEN_TIME.todayJST());

    // 7日以内なら新着バッジを表示
    if (daysSinceAdded >= 0 && daysSinceAdded <= 7) {
      var badge = document.createElement('span');
      badge.className = 'new-badge';
      badge.textContent = '新着';
      card.appendChild(badge);
    }
  });

  // 開催中/開催予定/終了への振り分けと並び替え(単一実装)
  arrangeList();

  var pastGrid = document.getElementById('pastEventsGrid');
  if (pastGrid) {
    var pastHeading0 = document.getElementById('pastEventsHeading') || pastGrid.previousElementSibling;
    if (pastHeading0 && pastHeading0.style && pastGrid.querySelector('.event-card')) {
      pastHeading0.style.display = '';
    }
    // 開催予定の件数を更新
    var countBadge = document.querySelector('.section-heading .count-badge, .event-count');
    var activeGrid = document.getElementById('eventsGrid');
    var ongoingGrid0 = document.getElementById('ongoingEventsGrid');
    if (countBadge && activeGrid) {
      var n = activeGrid.querySelectorAll('.event-card').length
              + (ongoingGrid0 ? ongoingGrid0.querySelectorAll('.event-card').length : 0);
      countBadge.textContent = n + '件';
    }
  }

  // 残す期間を過ぎた終了イベントを非表示。
  // 期間は sitelib.PAST_KEEP_DAYS が単一情報源(HTMLからの物理削除は
  // sync-index-cards.py が同じ定義で行う)。display:none 自体はDOMも
  // HTMLの重さも減らさないので、ここは編集判断としての非表示。
  // 適用するのは data-past-keep-days が付いている節だけ。
  // ランディングは地域の開催実績も情報なので打ち切らない。
  var HIDE_AFTER_DAYS = pastGrid && pastGrid.hasAttribute('data-past-keep-days')
    ? (parseInt(pastGrid.getAttribute('data-past-keep-days'), 10) || AEN_TIME.PAST_KEEP_DAYS)
    : null;
  if (pastGrid && HIDE_AFTER_DAYS !== null) {
    var _today = AEN_TIME.todayJST();
    pastGrid.querySelectorAll('.event-card').forEach(function (card) {
      var sp = card.__aenSpan || cardSpan(card);
      if (!sp.start) return;
      if (AEN_TIME.diffDays(sp.end || sp.start, _today) > HIDE_AFTER_DAYS) {
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
        'status-ongoing': '#4a8a7b',
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
