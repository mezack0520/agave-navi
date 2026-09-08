// トップの絞り込み。地域・都道府県・タグ・検索・更新のお知らせ。
//
// index.html の中に 420行のインラインで書いてあった(2026-09-08 に外出し)。
// インラインだと版数が付かないのでキャッシュが更新されず、
// list-ui.js / status-auto.js / nav.js との役割分担も見えなかった。
//
// ここが持つのは「何を出すか」の判定だけ。
//   もっと見るの段数        list-ui.js
//   開催中/終了の振り分け   status-auto.js
//   ハンバーガーの開閉      nav.js
// 同じ規則を2箇所に置くと、片方だけ直して直った気になる。
//
// HTMLの onclick 属性から呼ばれる関数(filterEvents / selectRegion /
// selectPref / searchEvents / sortAndFilter)は素の function 宣言のまま
// にしておく。classic script の関数宣言はグローバルになる。

// ハンバーガーの開閉は nav.js?v=20260908g が単一実装。
// 同じ15行が14ページにあり、生成ページには無かった
// (2026-09-08)。

// 地域の初期値は selectRegion 定義後に実行（後述）

let activeTag = 'all';

function filterEvents(tag) {
    activeTag = tag;
    const buttons = document.querySelectorAll('.filter-tab');
    buttons.forEach(btn => btn.classList.remove('active'));
    // event.currentTarget でSVG子要素クリック時もボタン本体を取得
    const clicked = event.currentTarget || event.target.closest('.filter-tab');
    if (clicked) clicked.classList.add('active');
    applyFilters();
}

function searchEvents(query) {
    applyFilters(query);
}

// 並び替え・開催中/終了の振り分けは status-auto.js?v=20260908g (window.AEN_LIST) が単一実装。
// ここに日付の解釈を再実装すると、会期の長い回の扱いが2通りに割れる。
// 以前は getCardDate / autoExpireEvents / sortAndFilter を独自に持ち、
// 開始日だけで並べていたため会期49日の展示が一覧の先頭に居座った(2026-08-20)。
function sortAndFilter() {
  if (window.AEN_LIST) window.AEN_LIST.arrange();
  applyFilters();
}

/* REGION-MAP:START 生成物。sitelib.PREF_TO_REGION から貼り替える */
const regionMap = {"北海道": ["北海道"], "東北": ["青森", "岩手", "宮城", "秋田", "山形", "福島"], "関東": ["茨城", "栃木", "群馬", "埼玉", "千葉", "東京", "神奈川"], "北陸": ["新潟", "富山", "石川", "福井", "山梨", "長野"], "東海": ["岐阜", "静岡", "愛知", "三重"], "関西": ["滋賀", "京都", "大阪", "兵庫", "奈良", "和歌山"], "中国": ["鳥取", "島根", "岡山", "広島", "山口"], "四国": ["徳島", "香川", "愛媛", "高知"], "九州": ["福岡", "佐賀", "長崎", "熊本", "大分", "宮崎", "鹿児島", "沖縄"]};
/* REGION-MAP:END */

// エリアフィルター状態
var activeRegion = 'all';
var activePref = 'all';

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
        document.querySelectorAll('#ongoingEventsGrid .event-card, #eventsGrid .event-card, #pastEventsGrid .event-card').forEach(function(card) {
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

    // 開催予定 + 終了イベント両方にフィルタ適用
    const allCards = document.querySelectorAll('#ongoingEventsGrid .event-card, #eventsGrid .event-card, #pastEventsGrid .event-card');
    let delay = 0;
    let visibleUpcoming = 0;
    let visiblePast = 0;

    allCards.forEach(card => {
        const tags = (card.getAttribute('data-tags') || '').split(',');
        const title = card.querySelector('.event-title').textContent.toLowerCase();
        const desc = card.querySelector('.event-description') ? card.querySelector('.event-description').textContent.toLowerCase() : '';
        const date = card.querySelector('.event-date').textContent.toLowerCase();
        const region = card.querySelector('.event-region') ? card.querySelector('.event-region').textContent : '';
        const cardPref = card.getAttribute('data-pref') || '';

        const tagMatch = activeTag === 'all' || activeTag === 'fav' || tags.includes(activeTag);
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

        const favMatch = activeTag !== 'fav' || getFavs().includes(card.getAttribute('data-slug') || '');
        const shouldShow = tagMatch && searchMatch && regionMatch && prefMatch && favMatch;

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
            else if (!card.classList.contains('event-cancelled')) { visibleUpcoming++; }
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

    // 開催中セクションもフィルタ結果に連動させる
    const ongoingGrid = document.getElementById('ongoingEventsGrid');
    const ongoingHeading = document.getElementById('ongoingHeading');
    const upcomingHeading = document.getElementById('upcomingHeading');
    const visibleOngoing = ongoingGrid
      ? Array.from(ongoingGrid.querySelectorAll('.event-card'))
             .filter(c => c.style.display !== 'none' && !c.classList.contains('filter-hide')).length
      : 0;
    if (ongoingGrid) ongoingGrid.style.display = visibleOngoing > 0 ? '' : 'none';
    if (ongoingHeading) ongoingHeading.style.display = visibleOngoing > 0 ? '' : 'none';
    if (upcomingHeading) upcomingHeading.style.display = visibleOngoing > 0 ? '' : 'none';

    // 行きたい空状態表示
    const emptyState = document.getElementById('emptyState');
    if (emptyState) {
        if (activeTag === 'fav' && visibleUpcoming === 0) {
            emptyState.classList.add('visible');
            emptyState.style.display = 'block';
        } else {
            emptyState.classList.remove('visible');
            emptyState.style.display = 'none';
        }
    }
}

// 行きたい(getFavs / toggleFav / syncFavUI)は list-ui.js?v=20260908g が単一実装。
// ここでは「行きたい」絞り込み中の再描画だけをフックで受ける。
window.AEN_ON_FAV_CHANGE = function() {
    if (activeTag === 'fav') applyFilters();
};

// もっと見る(initLoadMore / loadMoreEvents / initPastLoadMore)は
// list-ui.js?v=20260908g が単一実装。件数も list-ui.js?v=20260908g が持つ。

// 絞り込んだ結果にも段数の制限をかける。
// 以前は絞ったら showAll() で全件出していた。関東を選ぶと50件が
// 一気に並び、「もっと見る」も消えた(2026-09-08 指摘)。
// 絞り込みを先に走らせてから、通ったカードだけを数えて切る。
const _origApplyFilters = applyFilters;
applyFilters = function(query) {
    _origApplyFilters(query);
    if (window.AEN_LIST_UI) window.AEN_LIST_UI.resetLoadMore();
};

// 初期表示(並び替え・もっと見る・行きたいの同期)は
// list-ui.js?v=20260908g と status-auto.js?v=20260908g が行う。ここで先に呼ぶと
// 規則を二重に持つことになる。

// ========== モバイル: カード下部行きたいバー + スワイプ ==========
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

        // 初期状態は list-ui.js?v=20260908g の syncFavUI が反映する

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

// バーの表示同期は list-ui.js?v=20260908g の syncFavUI が行う。
// initMobileFav の呼び出しも list-ui.js?v=20260908g の初期化から。
    // 初期の振り分け・並び替えは status-auto.js?v=20260908g が行う(規則の二重定義を避ける)。
    


// === URLパラメータ対応 (SEO & シェア用) ===
/* === URLパラメータ対応 (SEO & シェア用) === */
(function(){
function updateURL(){
var params=new URLSearchParams();
if(activeTag&&activeTag!=='all') params.set('tag',activeTag);
if(activeRegion&&activeRegion!=='all') params.set('region',activeRegion);
if(activePref&&activePref!=='all') params.set('pref',activePref);
var q=document.getElementById('searchInput').value.trim();
if(q) params.set('q',q);
var url=params.toString()?location.pathname+'?'+params.toString():location.pathname;
history.replaceState({tag:activeTag,region:activeRegion,pref:activePref,q:q},'',url);
}
// Wrap existing functions
var _fE=window.filterEvents;
window.filterEvents=function(tag){_fE(tag);updateURL();updateMeta();};
var _sR=window.selectRegion;
window.selectRegion=function(r){_sR(r);updateURL();updateMeta();};
var _sP=window.selectPref;
window.selectPref=function(p){_sP(p);updateURL();updateMeta();};
var _sE=window.searchEvents;
window.searchEvents=function(q){_sE(q);updateURL();updateMeta();};
// popstate (back/forward)

// AIO: カテゴリURLパラメータ時にtitle/metaを動的変更
var tagMeta={"即売会":{t:"即売会 | アガベイベントナビ",d:"全国のアガベ・多肉植物・塊根植物の即売会イベント一覧。お気に入りの株を見つけに行こう。"},"マルシェ":{t:"マルシェ | アガベイベントナビ",d:"アガベ・多肉植物のマルシェ・フリーマーケットイベント一覧。気軽に植物に出会える場所。"},"大型":{t:"大型イベント | アガベイベントナビ",d:"天下一植物界やビッグバザールなど、全国の大型植物イベント一覧。大規模な即売会・展示会を一挙掲載。"},"展示会":{t:"展示会 | アガベイベントナビ",d:"アガベ・塊根植物・珍奇植物の展示会イベント一覧。希少種を観賞できるイベント情報。"}};
var origTitle=document.title,origDesc=document.querySelector('meta[name="description"]').content;
function updateMeta(){var p=new URLSearchParams(location.search);var tag=p.get("tag");if(tag&&tagMeta[tag]){document.title=tagMeta[tag].t;document.querySelector('meta[name="description"]').setAttribute("content",tagMeta[tag].d);}else{document.title=origTitle;document.querySelector('meta[name="description"]').setAttribute("content",origDesc);}}
window.addEventListener('popstate',function(){
var p=new URLSearchParams(location.search);
var tag=p.get('tag')||'all';
var region=p.get('region')||'all';
var pref=p.get('pref')||'all';
var q=p.get('q')||'';
activeTag=tag;
document.querySelectorAll('.filter-tab').forEach(function(b){
  var oc=b.getAttribute('onclick')||'';
  b.classList.toggle('active',oc.indexOf("'"+tag+"'")>-1||(tag==='all'&&oc.indexOf("'all'")>-1));
});
if(region!==activeRegion) _sR(region);
if(pref!==activePref) _sP(pref);
document.getElementById('searchInput').value=q;
applyFilters(q||undefined);
});
// Init from URL on load
var p=new URLSearchParams(location.search);
if(p.toString()){
var tag=p.get('tag')||'all';
var region=p.get('region')||'all';
var pref=p.get('pref')||'all';
var q=p.get('q')||'';
if(tag!=='all'){
  activeTag=tag;
  document.querySelectorAll('.filter-tab').forEach(function(b){
    var oc=b.getAttribute('onclick')||'';
    b.classList.toggle('active',oc.indexOf("'"+tag+"'")>-1);
  });
}
if(region!=='all') _sR(region);
if(pref!=='all') setTimeout(function(){_sP(pref);},50);
if(q) document.getElementById('searchInput').value=q;
applyFilters(q||undefined);
}
updateMeta();
})();
