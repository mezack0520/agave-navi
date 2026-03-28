/**
 * アガベイベントナビ - 広告・アフィリエイト管理
 * Google AdSense + Amazon / 楽天 / Yahoo! アフィリエイト ランダム表示
 */
(function() {
  'use strict';

  // Amazon Associates トラッキングID
  var AMAZON_TAG = 'agavenavi-22';

  // === アフィリエイト商品データ ===
  // type: 'amazon' | 'rakuten' | 'yahoo' （将来追加用に構造を保持）
  var AFFILIATE_ITEMS = [
    // --- Amazon ---
    {
      type: 'amazon',
      title: '多肉植物＆コーデックス GuideBook',
      img: 'https://m.media-amazon.com/images/I/91s1WyYoiML._SY425_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E5%A4%9A%E8%82%89%E6%A4%8D%E7%89%A9+%E5%9B%B3%E9%91%91&tag=' + AMAZON_TAG,
      price: '1,650円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: 'アガベ・ユッカ その魅力と育て方',
      img: 'https://m.media-amazon.com/images/I/81yXx7ifL6L._SY385_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E3%82%A2%E3%82%AC%E3%83%99+%E8%82%B2%E3%81%A6%E6%96%B9&tag=' + AMAZON_TAG,
      price: '1,980円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: 'プレステラ 105 スリット鉢 10個セット',
      img: 'https://m.media-amazon.com/images/I/515Ea+4-zgL._AC_UL320_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E3%83%97%E3%83%AC%E3%82%B9%E3%83%86%E3%83%A9+%E3%82%B9%E3%83%AA%E3%83%83%E3%83%88%E9%89%A2&tag=' + AMAZON_TAG,
      price: '780円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: '植物育成LEDライト',
      img: 'https://m.media-amazon.com/images/I/61BSjmcfsyL._AC_UL320_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E6%A4%8D%E7%89%A9%E8%82%B2%E6%88%90+LED%E3%83%A9%E3%82%A4%E3%83%88&tag=' + AMAZON_TAG,
      price: '2,980円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: '多肉植物用 培養土 5L',
      img: 'https://m.media-amazon.com/images/I/71qoFhg9aQL._AC_UL320_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E5%A4%9A%E8%82%89%E6%A4%8D%E7%89%A9+%E5%9F%B9%E9%A4%8A%E5%9C%9F&tag=' + AMAZON_TAG,
      price: '1,280円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: '珍奇植物 ビザールプランツ入門',
      img: 'https://m.media-amazon.com/images/I/81Yah8Moc-L._AC_UL320_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E3%83%93%E3%82%B6%E3%83%BC%E3%83%AB%E3%83%97%E3%83%A9%E3%83%B3%E3%83%84&tag=' + AMAZON_TAG,
      price: '1,760円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: 'BLACK PLASTIC POT 丸型 3号',
      img: 'https://m.media-amazon.com/images/I/21Cv5iQ0UsL._AC_UL320_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E3%83%96%E3%83%A9%E3%83%83%E3%82%AF%E3%83%9D%E3%83%83%E3%83%88+%E6%A4%8D%E7%89%A9&tag=' + AMAZON_TAG,
      price: '580円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: 'マグァンプK 中粒 600g',
      img: 'https://m.media-amazon.com/images/I/71Lm4sw5ZYL._AC_UL320_.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E3%83%9E%E3%82%B0%E3%82%A1%E3%83%B3%E3%83%97K+%E4%B8%AD%E7%B2%92&tag=' + AMAZON_TAG,
      price: '980円〜',
      shop: 'Amazon'
    },

    // --- 楽天アフィリエイト ---
    {
      type: 'rakuten',
      title: 'アガベ 品種見計らい5種セット',
      img: 'https://image.rakuten.co.jp/plantsmind/cabinet/biiino/item/main-image-5/20250725105107_1.jpg',
      url: 'https://hb.afl.rakuten.co.jp/ichiba/5251fbf3.21164c54.5251fbf4.7818a8f3/?pc=https%3A%2F%2Fitem.rakuten.co.jp%2Fauc-shikoku-garden%2Fs19-003%2F&link_type=hybrid_url&ut=eyJwYWdlIjoiaXRlbSIsInR5cGUiOiJoeWJyaWRfdXJsIiwic2l6ZSI6IjI0MHgyNDAiLCJuYW0iOjEsIm5hbXAiOiJyaWdodCIsImNvbSI6MSwiY29tcCI6ImRvd24iLCJwcmljZSI6MSwiYm9yIjoxLCJjb2wiOjEsImJidG4iOjEsInByb2QiOjAsImFtcCI6ZmFsc2V9',
      price: '4,948円',
      shop: '楽天市場'
    },

    // --- Yahoo!ショッピング ---
    {
      type: 'yahoo',
      title: 'アガベ ベネズエラ バリエガータ 6号鉢',
      img: 'https://item-shopping.c.yimg.jp/i/l/itanse_kan00152',
      url: 'https://yahoo.jp/H3otoq',
      price: '8,880円',
      shop: 'Yahoo!'
    }
  ];

  // === ユーティリティ ===
  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
    return arr;
  }

  function getShopBadgeClass(type) {
    if (type === 'rakuten') return 'aff-badge-rakuten';
    if (type === 'yahoo') return 'aff-badge-yahoo';
    if (type === 'amazon') return 'aff-badge-amazon';
    return '';
  }

  function getShopLabel(type) {
    if (type === 'rakuten') return '楽天市場';
    if (type === 'yahoo') return 'Yahoo!';
    if (type === 'amazon') return 'Amazon';
    return '';
  }

  // === アフィリエイト横スクロールバナー生成 ===
  function renderAffiliateBar(container, count) {
    if (!container) return;
    if (AFFILIATE_ITEMS.length === 0) return;
    var items = shuffle(AFFILIATE_ITEMS.slice()).slice(0, count || 4);

    var html = '<div class="aff-section">';
    html += '<p class="aff-section-title">おすすめアイテム <span class="aff-pr">PR</span></p>';
    html += '<div class="aff-scroll">';

    items.forEach(function(item) {
      html += '<a href="' + item.url + '" target="_blank" rel="noopener sponsored" class="aff-card">';
      html += '<div class="aff-card-img"><img src="' + item.img + '" alt="' + item.title + '" loading="lazy" onerror="this.style.display=\'none\'"></div>';
      html += '<div class="aff-card-info">';
      html += '<span class="aff-badge ' + getShopBadgeClass(item.type) + '">' + getShopLabel(item.type) + '</span>';
      html += '<p class="aff-card-title">' + item.title + '</p>';
      html += '<p class="aff-card-price">' + item.price + '</p>';
      html += '</div></a>';
    });

    html += '</div></div>';
    container.innerHTML = html;
  }

  // === AdSense 広告枠の初期化 ===
  function initAdSense() {
    if (typeof adsbygoogle === 'undefined') return;
    document.querySelectorAll('.adsbygoogle').forEach(function(ad) {
      try {
        (adsbygoogle = window.adsbygoogle || []).push({});
      } catch(e) {}
    });
  }

  // === ページ読み込み時に実行 ===
  function init() {
    var affSlots = document.querySelectorAll('.aff-slot');
    affSlots.forEach(function(slot) {
      var count = parseInt(slot.getAttribute('data-count')) || 4;
      renderAffiliateBar(slot, count);
    });
    initAdSense();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
