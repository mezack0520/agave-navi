// outbound.js — 外部リンクへの送客を、イベント単位で数える。
//
// **なぜ要るか。**このサイトの値打ちは主催者への送客だが、
// 「どの回から何人が主催の告知へ出て行ったか」をこれまで一度も数えていなかった。
// GA4 の拡張計測にある outbound click は link_url と page_location しか持たず、
// 「出典へのリンク」「埋め込みからの導線」「会場の地図」の区別が付かない。
// 掲載を有料にするときに出せる数字は「その回の詳細頁を見た人数」ではなく
// 「その回から主催へ送った人数」なので、役割ごとに分けて取る。
//
// アフィリエイトのリンクは affiliate.js が affiliate_click として別に数えている。
// **ここで重ねて数えない。**同じクリックが2つの指標に乗ると、
// どちらを見ても実数が分からなくなる。
//
// 送るのは GA4 の outbound_click。パラメータは4つ。
//   ev_slug   … イベントのslug。詳細頁以外は ''
//   dest      … 送り先のホスト(www. は落とす)。instagram.com など
//   role      … リンクの役割。下の ROLES を見る
//   page_path … 送り出した頁
//
// **GA4 でこの4つを見るには、管理画面でカスタム ディメンションに
// 登録する必要がある。**登録するまでイベント数は出るが内訳が出ない。
(function () {
  'use strict';

  // 役割の決め方。**上から順に最初に当たったものを採る。**
  // セレクタは「どこに置かれたリンクか」で分ける。リンク先では分けない。
  // 同じ instagram.com でも、出典として出しているのか、
  // 埋め込みの下の導線なのかで意味が違う。
  //
  // **主催への送客は source_note と instagram_embed の2つ。**
  // 有料化の話で出すのはこの2つの合計で、カレンダー登録(hero_action)や
  // ナビのSNSリンク(nav)は送客ではない。混ぜないために分けてある。
  var ROLES = [
    ['.detail-instagram-embed', 'instagram_embed'],  // 埋め込み下の「Instagramで見る」
    ['.eh-meta-note', 'source_note'],   // 出典リンクと画像の出所。主催へ出る主動線
    ['.eh-actions', 'hero_action'],     // カレンダー登録など。送客ではない
    ['.eh-spec', 'spec'],               // 日時・会場の表(会場公式など)
    ['.detail-venue-map', 'venue_map'],
    ['.detail-section', 'detail'],      // 本文中の導線
    ['.site-footer', 'footer'],
    ['.nav-overlay', 'nav'],
    ['.header', 'header']
  ];

  // affiliate.js が拾うリンク。ここでは無視する
  var AFF = 'a.aff-shop-btn, a.rk-card, .aff-bar a, .affiliate-section a';

  function roleOf(a) {
    for (var i = 0; i < ROLES.length; i++) {
      if (a.closest(ROLES[i][0])) return ROLES[i][1];
    }
    return 'other';
  }

  // 詳細頁の slug は URL から取る。テンプレートに属性を足すと
  // 出し忘れた頁だけ黙って空になるので、頁の住所そのものを使う。
  function slugOf() {
    var m = location.pathname.match(/\/events\/([^\/]+)\.html$/);
    return m ? m[1] : '';
  }

  function hostOf(href) {
    try { return new URL(href, location.href).hostname.replace(/^www\./, ''); }
    catch (e) { return ''; }
  }

  var bound = false;
  function bind() {
    if (bound) return;
    bound = true;
    document.addEventListener('click', function (ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest('a[href]') : null;
      if (!a) return;
      if (a.matches && a.matches(AFF)) return;        // 二重計上を避ける
      if (a.closest && a.closest(AFF)) return;

      var href = a.getAttribute('href') || '';
      if (!/^https?:/i.test(href)) return;            // 相対・mailto・tel は対象外
      var host = hostOf(href);
      if (!host || host === location.hostname.replace(/^www\./, '')) return;

      if (typeof window.gtag !== 'function') return;
      try {
        window.gtag('event', 'outbound_click', {
          ev_slug: slugOf(),
          dest: host,
          role: roleOf(a),
          page_path: location.pathname
        });
      } catch (e) { /* 計測の失敗で遷移を止めない */ }
    }, true);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bind);
  } else {
    bind();
  }
})();
