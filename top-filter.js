// トップの絞り込み。地域・都道府県・日程・検索・更新のお知らせ。
//
// ここが持つのは「何を出すか」の判定だけ。
//   もっと見るの段数        list-ui.js
//   開催中/終了の振り分け・並び  status-auto.js
//   「今日」               status-auto.js の AEN_TIME
//   週末の範囲             sitelib.weekend_blocks(#whenFilter の data-weekends)
//   ハンバーガー・行きたいの件数  nav.js
// 同じ規則を2箇所に置くと、片方だけ直して直った気になる。
//
// HTMLの onclick 属性から呼ばれる関数(selectRegion / selectPref /
// selectWhen / searchEvents)は素の function 宣言のままにしておく。
// classic script の関数宣言はグローバルになる。

/* REGION-MAP:START 生成物。sitelib.PREF_TO_REGION から貼り替える */
const regionMap = {"北海道": ["北海道"], "東北": ["青森", "岩手", "宮城", "秋田", "山形", "福島"], "関東": ["茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川"], "北陸": ["新潟", "富山", "石川", "福井", "山梨", "長野"], "東海": ["岐阜", "静岡", "愛知", "三重"], "関西": ["滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山"], "中国": ["鳥取", "島根", "岡山", "広島", "山口"], "四国": ["徳島", "香川", "愛媛", "高知"], "九州": ["福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄"]};
/* REGION-MAP:END */

// エリアフィルター状態
var activeRegion = 'all';
var activePref = 'all';
// 日程。保存しない。「今週末」を覚えておくと、翌週に開いた人が先週の続きで絞られる
var activeWhen = 'all';
var WHEN_KEYS = { 'all': 1, 'this-weekend': 1, 'next-weekend': 1, 'this-month': 1 };

function searchEvents(query) {
    applyFilters(query);
}

function selectRegion(region) {
    activeRegion = region;
    activePref = 'all';

    // 押されたタブに active を移す。ここが無かったので、
    // localStorage から関東を復元したときに一覧は関東だけなのに
    // タブは「全国」のまま光っていた(2026-09-08 本番で確認)。
    document.querySelectorAll('.region-tab').forEach(function (t) {
        t.classList.toggle('active',
            (t.getAttribute('data-region') || 'all') === region);
    });

    var regionTabs = document.getElementById('regionTabs');
    var prefRow = document.getElementById('prefRow');
    var prefCrumb = document.getElementById('prefRegionCrumb');
    var chipsContainer = document.getElementById('prefChips');
    chipsContainer.innerHTML = '';

    if (region === 'all') {
        // 地域選択モードに戻す
        regionTabs.style.display = '';
        prefRow.style.display = 'none';
        document.querySelectorAll('.region-tab').forEach(function(btn) {
            btn.classList.toggle('active', btn.getAttribute('data-region') === 'all');
        });
    } else {
        // 都道府県ドリルダウンモードに切替
        regionTabs.style.display = 'none';
        prefRow.style.display = '';
        // 地域名そのものを選択状態にする。「すべて」チップは置かない
        prefCrumb.textContent = region;
        prefCrumb.classList.add('active');

        // 該当地域の都道府県を取得
        var prefsInRegion = new Set();
        document.querySelectorAll('#eventsGrid .event-card, #pastEventsGrid .event-card').forEach(function(card) {
            var cardRegion = card.getAttribute('data-region') || '';
            var cardPref = card.getAttribute('data-pref') || '';
            var regionText = card.querySelector('.event-region') ? card.querySelector('.event-region').textContent : '';
            var prefs = regionMap[region] || [];
            if (cardRegion === region || prefs.some(function(p) { return regionText.includes(p); })) {
                if (cardPref) prefsInRegion.add(cardPref);
                else if (regionText) prefsInRegion.add(regionText);
            }
        });

        // 各都道府県チップ
        Array.from(prefsInRegion).sort().forEach(function(pref) {
            var chip = document.createElement('button');
            chip.className = 'pref-chip';
            chip.setAttribute('data-pref', pref);
            chip.textContent = pref;
            chip.onclick = function() { selectPref(pref); };
            chipsContainer.appendChild(chip);
        });
    }

    try { localStorage.setItem('aen_region', region); } catch(e) {}
    applyFilters();
}

function selectPref(pref) {
    activePref = pref;
    document.querySelectorAll('.pref-chip').forEach(function(chip) {
        chip.classList.toggle('active', chip.getAttribute('data-pref') === pref);
    });
    // 県を外したら地域名が選択状態に戻る
    var crumb = document.getElementById('prefRegionCrumb');
    if (crumb) crumb.classList.toggle('active', pref === 'all');
    applyFilters();
}

// --- 日程 ---
// 週末の範囲は Python 側(sitelib.weekend_blocks)が祝日込みで決め、
// #whenFilter の data-weekends に [始まり, 終わり, 表記] で先の分まで持たせてある。
// ここでは閲覧日(AEN_TIME)より後に終わるものを選ぶだけで、週末の規則は持たない。
function weekendsAhead() {
    var el = document.getElementById('whenFilter');
    if (!el || !window.AEN_TIME) return [];
    var today = window.AEN_TIME.todayJST();
    var list = [];
    try { list = JSON.parse(el.getAttribute('data-weekends') || '[]'); } catch (e) { list = []; }
    return list.filter(function (b) { return b && b[1] >= today; });
}

function monthEnd(iso) {
    var d = new Date(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7), 0));  // 翌月の0日 = 今月の末日
    return iso.slice(0, 8) + String(d.getUTCDate()).padStart(2, '0');
}

// [から, まで]。絞らないときは null
function whenRange(key) {
    if (key === 'all' || !window.AEN_TIME) return null;
    var today = window.AEN_TIME.todayJST();
    if (key === 'this-month') return [today, monthEnd(today)];
    var b = weekendsAhead()[key === 'next-weekend' ? 1 : 0];
    if (!b) return null;
    return [b[0] < today ? today : b[0], b[1]];
}

// 会期が範囲に1日でも掛かれば出す。会期の長い展示も、その週末に開いていれば今週末に入る
function cardInRange(card, range) {
    var s = card.getAttribute('data-date') || '';
    if (!s) return false;
    var e = card.getAttribute('data-date-end') || s;
    return s <= range[1] && e >= range[0];
}

// ビルドから日が経っていても、閲覧日の今週末・来週末に描き直す。範囲が無い週末は出さない
function paintWhen() {
    var ahead = weekendsAhead();
    document.querySelectorAll('.when-chip').forEach(function (c) {
        var key = c.getAttribute('data-when');
        var on = key === activeWhen;
        c.classList.toggle('active', on);
        c.setAttribute('aria-pressed', on ? 'true' : 'false');
        if (key === 'this-weekend' || key === 'next-weekend') {
            var b = ahead[key === 'next-weekend' ? 1 : 0];
            c.style.display = b ? '' : 'none';
            var sp = c.querySelector('.when-dates');
            if (b && sp && sp.textContent !== b[2]) sp.textContent = b[2];
        }
    });
}

function selectWhen(key) {
    activeWhen = WHEN_KEYS[key] ? key : 'all';
    if (activeWhen !== 'all' && !whenRange(activeWhen)) activeWhen = 'all';
    paintWhen();
    applyFilters();
}

paintWhen();

// 地域の初期値復元
(function initRegion() {
    var saved = 'all';
    try { saved = localStorage.getItem('aen_region') || 'all'; } catch(e) {}
    if (saved !== 'all') selectRegion(saved);
})();

// 更新のお知らせの範囲差し替え。
// トップに埋めてあるのは全国の最新10件だけなので、関東で絞ると
// 0件になっていた(関東の更新自体はあるのに「無い」と見える)。
// 範囲別の行は site-updates-scopes.json に生成してある。
// 行の組み立ては sitelib.update_rows が唯一の持ち主なので、
// 地域ページと同じ並び・同じ行が出る。
var _updBase = null;      // 全国の行。初回に控える
var _updScopes = null;    // 取得済みの範囲別の行
var _updWant = 'all';     // いま出したい範囲
var _updFetching = false;

function setUpdatesScope(key, hasQuery) {
    var sec = document.getElementById('updates');
    if (!sec) return;
    if (_updBase === null) {
        var l0 = sec.querySelector('.updates-list');
        _updBase = l0 ? l0.innerHTML : '';
    }
    _updWant = key;
    // 検索語で絞っているときはイベント名との対応が取れないので隠す
    if (hasQuery) { sec.style.display = 'none'; return; }
    if (key === 'all' || _updScopes) { paintUpdatesScope(); return; }
    if (!_updFetching) {
        _updFetching = true;
        fetch('site-updates-scopes.json')
            .then(function (r) { return r.json(); })
            .then(function (j) { _updScopes = (j && j.scopes) || {}; })
            .catch(function () { _updScopes = {}; })
            .then(function () { paintUpdatesScope(); });
    }
    // 取得中はいまの表示のまま。ちらつかせない
}

function paintUpdatesScope() {
    var sec = document.getElementById('updates');
    if (!sec) return;
    var key = _updWant;
    var label = (key === 'all') ? '' : key.slice(key.indexOf(':') + 1);
    var rows = (key === 'all') ? _updBase
             : ((_updScopes && _updScopes[key]) || '');
    var list = sec.querySelector('.updates-list');
    if (list) list.innerHTML = rows;
    var note = sec.querySelector('.updates-note');
    if (note) {
        note.textContent = label
            ? label + 'の掲載・中止・日程変更'
            : '掲載・中止・日程変更';
    }
    // その範囲に更新が無いなら節ごと隠す。見出しだけ残して
    // 「該当なし」と書いた箱は、無いより読みにくい
    sec.style.display = rows ? '' : 'none';
}

function applyFilters(query) {
    const searchVal = (query !== undefined ? query : document.getElementById('searchInput').value).trim().toLowerCase();
    const regionVal = activeRegion;
    const prefVal = activePref;
    const range = whenRange(activeWhen);

    // 開催予定 + 終了イベント両方にフィルタ適用
    const allCards = document.querySelectorAll('#eventsGrid .event-card, #pastEventsGrid .event-card');
    let delay = 0;
    let visibleUpcoming = 0;
    let visibleMain = 0;
    let visiblePast = 0;

    allCards.forEach(card => {
        const title = card.querySelector('.event-title').textContent.toLowerCase();
        const desc = card.querySelector('.event-description') ? card.querySelector('.event-description').textContent.toLowerCase() : '';
        const date = card.querySelector('.event-date').textContent.toLowerCase();
        const region = card.querySelector('.event-region') ? card.querySelector('.event-region').textContent : '';
        const cardPref = card.getAttribute('data-pref') || '';

        const searchMatch = !searchVal || title.includes(searchVal) || desc.includes(searchVal) || date.includes(searchVal) || region.toLowerCase().includes(searchVal);

        // 地域フィルタ
        let regionMatch = true;
        if (regionVal !== 'all') {
            const prefectures = regionMap[regionVal] || [];
            regionMatch = prefectures.some(p => region.includes(p)) || card.getAttribute('data-region') === regionVal;
        }

        // 都道府県フィルタ
        let prefMatch = true;
        if (prefVal !== 'all') {
            prefMatch = cardPref === prefVal || region === prefVal;
        }

        const whenMatch = !range || cardInRange(card, range);
        const shouldShow = searchMatch && regionMatch && prefMatch && whenMatch;

        if (shouldShow) {
            card.classList.remove('filter-hide');
            card.classList.add('filter-show');
            card.style.display = '';
            card.style.animationDelay = delay + 'ms';
            delay += 40;
            // 中止の回はカードを出すが「開催予定 N件」には数えない。
            // 行ける場所の数を数えるところなので、中止を混ぜると
            // トップの145件と絞り込み時の件数で意味が食い違う
            if (card.closest('#pastEventsGrid')) { visiblePast++; }
            else {
                visibleMain++;
                if (!card.classList.contains('event-cancelled')) { visibleUpcoming++; }
            }
        } else {
            card.classList.remove('filter-show');
            card.classList.add('filter-hide');
            setTimeout(() => {
                if (card.classList.contains('filter-hide')) {
                    card.style.display = 'none';
                }
            }, 200);
        }
    });

    document.getElementById('eventCount').textContent = visibleUpcoming + '件';

    // 更新のお知らせも絞り込みに追随させる。地域や県で絞っているのに
    // 他県の更新が並ぶのは読みにくい(2026-09-08、関東で絞ると
    // 愛知・熊本・鹿児島が出ていた)。
    {
        const q = (query || '').trim();
        setUpdatesScope(
            (activePref !== 'all') ? 'pref:' + activePref
            : (activeRegion !== 'all') ? 'region:' + activeRegion : 'all',
            !!q);
    }
    // 終了セクションの見出しも連動表示
    const pastHeading = document.getElementById('pastEventsHeading');
    const pastGrid = document.getElementById('pastEventsGrid');
    if (pastHeading) pastHeading.style.display = visiblePast > 0 ? '' : 'none';
    if (pastGrid) pastGrid.style.display = visiblePast > 0 ? '' : 'none';

    // 開催中の節はここでは扱わない。status-auto.js が常に本体へ混ぜる。
    // 以前はここで「見えている開催中の枚数」で節を出し入れしていたが、
    // 混ぜる判断は読み込み時に1回しか走らないため、絞り込みで1〜2件に
    // なった状態の節がそのまま残り、4カラムの行がほぼ空になっていた
    // (2026-09-18 指摘)。「これから開催」の見出しも status-auto.js が持つ。

    // 条件に合う回が無いとき。日程で絞っているときだけ外す導線を出す
    const emptyState = document.getElementById('emptyState');
    if (emptyState) {
        const none = visibleMain === 0;
        emptyState.classList.toggle('visible', none);
        emptyState.style.display = none ? 'block' : 'none';
        const clear = document.getElementById('whenClear');
        if (clear) clear.style.display = activeWhen !== 'all' ? '' : 'none';
    }

    // 絞り込んだ結果にも段数の制限をかける。段数は list-ui.js が持つ。
    // **ここで呼ぶ。後付けのラッパーにしない。**後から包む形は、
    // 包むより前にある呼び出し(上の initRegion)を必ず取りこぼす。
    if (window.AEN_LIST_UI) window.AEN_LIST_UI.resetLoadMore();
}

// もっと見る(initLoadMore / loadMoreEvents / initPastLoadMore)と
// 行きたい(getFavs / toggleFav / syncFavUI)は list-ui.js が単一実装。
// 行きたいの件数バッジは nav.js が AEN_ON_FAV_CHANGE で塗る。ここで上書きしない。

// ========== モバイル: カード下部行きたいバー + スワイプ ==========
// 呼び出しと表示の同期は list-ui.js の初期化と syncFavUI から。
function initMobileFav() {
    const cards = document.querySelectorAll('.event-card[data-slug]');
    cards.forEach(card => {
        const slug = card.getAttribute('data-slug');
        const bar = card.querySelector('.card-fav-bar');
        if (!bar) return;

        // Bar tap → toggle fav
        bar.addEventListener('click', (e) => {
            e.stopPropagation();
            e.preventDefault();
            toggleFav(e, slug);
        });

        // Swipe gesture
        let startX = 0, startY = 0, swiping = false;
        card.addEventListener('touchstart', (e) => {
            startX = e.touches[0].clientX;
            startY = e.touches[0].clientY;
            swiping = false;
        }, { passive: true });

        card.addEventListener('touchmove', (e) => {
            const dx = e.touches[0].clientX - startX;
            const dy = e.touches[0].clientY - startY;
            // Only detect horizontal swipe
            if (Math.abs(dx) > 20 && Math.abs(dx) > Math.abs(dy) * 1.5) {
                swiping = true;
                if (dx > 0) {
                    card.classList.add('swiping-right');
                    card.style.transform = 'translateX(' + Math.min(dx * 0.3, 40) + 'px)';
                }
            }
        }, { passive: true });

        card.addEventListener('touchend', (e) => {
            const dx = e.changedTouches[0].clientX - startX;
            card.classList.remove('swiping-right');
            card.style.transform = '';
            if (swiping && dx > 60) {
                // Swipe right confirmed → toggle fav
                toggleFav(e, slug);
                card.classList.add('swipe-confirm');
                setTimeout(() => card.classList.remove('swipe-confirm'), 400);
            }
            swiping = false;
        }, { passive: true });
    });
}

// === URLパラメータと計測 ===
// 絞り込みの状態は URL に残す(共有用)。サイト内のリンクはここを指さない。
// canonical がトップなので評価が渡らない。地域・県は /region/ /pref/ の頁へ張る(2026-11-18)。
// 利用者が押したときだけ GA4 に送る。URL・localStorage からの復元は送らない。
// 送るもの: filter_region / filter_pref / filter_date(filter_value)、search(search_term)。
// filter_value の内訳を GA4 で見るには、管理画面でカスタム ディメンションに登録する。
(function(){
function track(name, params) {
    try { if (typeof gtag === 'function') gtag('event', name, params); } catch (e) {}
}
// 1文字ごとに送らない。打ち終えて1.5秒止まった語を、同じ語は1回だけ
var searchTimer = null, searchSent = '';
function trackSearch(q) {
    clearTimeout(searchTimer);
    q = (q || '').trim();
    if (!q) return;
    searchTimer = setTimeout(function () {
        if (q === searchSent) return;
        searchSent = q;
        track('search', { search_term: q });
    }, 1500);
}
function updateURL(){
var params=new URLSearchParams();
if(activeRegion&&activeRegion!=='all') params.set('region',activeRegion);
if(activePref&&activePref!=='all') params.set('pref',activePref);
if(activeWhen&&activeWhen!=='all') params.set('when',activeWhen);
var q=document.getElementById('searchInput').value.trim();
if(q) params.set('q',q);
var url=params.toString()?location.pathname+'?'+params.toString():location.pathname;
history.replaceState({region:activeRegion,pref:activePref,when:activeWhen,q:q},'',url);
}
var _sR=window.selectRegion;
window.selectRegion=function(r){_sR(r);updateURL();track('filter_region',{filter_value:r});};
var _sP=window.selectPref;
window.selectPref=function(p){_sP(p);updateURL();track('filter_pref',{filter_value:p});};
var _sW=window.selectWhen;
window.selectWhen=function(w){_sW(w);updateURL();track('filter_date',{filter_value:activeWhen});};
var _sE=window.searchEvents;
window.searchEvents=function(q){_sE(q);updateURL();trackSearch(q);};
function setWhenFromURL(w){
activeWhen=WHEN_KEYS[w]?w:'all';
if(activeWhen!=='all'&&!whenRange(activeWhen)) activeWhen='all';
paintWhen();
}
window.addEventListener('popstate',function(){
var p=new URLSearchParams(location.search);
var region=p.get('region')||'all';
var pref=p.get('pref')||'all';
var q=p.get('q')||'';
setWhenFromURL(p.get('when')||'all');
if(region!==activeRegion) _sR(region);
if(pref!==activePref) _sP(pref);
document.getElementById('searchInput').value=q;
applyFilters(q||undefined);
});
// Init from URL on load
var p=new URLSearchParams(location.search);
if(p.toString()){
var region=p.get('region')||'all';
var pref=p.get('pref')||'all';
var q=p.get('q')||'';
setWhenFromURL(p.get('when')||'all');
if(region!=='all') _sR(region);
if(pref!=='all') setTimeout(function(){_sP(pref);},50);
if(q) document.getElementById('searchInput').value=q;
applyFilters(q||undefined);
}
})();
