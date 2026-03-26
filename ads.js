/**
 * アガベイベントナビ - 広告・アフィリエイト管理
 * Google AdSense + 楽天/Yahoo!/Amazon アフィリエイト ランダム表示
 */
(function() {
  'use strict';

  // === アフィリエイト商品データ ===
  var AFFILIATE_ITEMS = [
    // --- 楽天アフィリエイト ---
    {
      type: 'rakuten',
      title: 'アガベ チタノタ 実生選抜',
      img: 'https://thumbnail.image.rakuten.co.jp/@0_mall/auc-gifuryokuenonline/cabinet/agave/titanota01.jpg',
      url: 'https://hb.afl.rakuten.co.jp/hgc/agavenavi/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2582%25A2%25E3%2582%25AC%25E3%2583%2599+%25E3%2583%2581%25E3%2582%25BF%25E3%2583%258E%25E3%2582%25BF%2F',
      price: '3,980円〜',
      shop: '楽天市場'
    },
    {
      type: 'rakuten',
      title: 'パキポディウム グラキリス 実生',
      img: 'https://thumbnail.image.rakuten.co.jp/@0_mall/auc-gifuryokuenonline/cabinet/pachypodium/gracilius01.jpg',
      url: 'https://hb.afl.rakuten.co.jp/hgc/agavenavi/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2591%25E3%2582%25AD%25E3%2583%259D%25E3%2583%2587%25E3%2582%25A3%25E3%2582%25A6%25E3%2583%25A0+%25E3%2582%25B0%25E3%2583%25A9%25E3%2582%25AD%25E3%2583%25AA%25E3%2582%25B9%2F',
      price: '5,980円〜',
      shop: '楽天市場'
    },
    {
      type: 'rakuten',
      title: 'プレステラ 90 スリット鉢 10個',
      img: 'https://thumbnail.image.rakuten.co.jp/@0_mall/chanet/cabinet/289/289957-1.jpg',
      url: 'https://hb.afl.rakuten.co.jp/hgc/agavenavi/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E3%2583%2597%25E3%2583%25AC%25E3%2582%25B9%25E3%2583%2586%25E3%2583%25A990+%25E3%2582%25B9%25E3%2583%25AA%25E3%2583%2583%25E3%2583%2588%2F',
      price: '780円〜',
      shop: '楽天市場'
    },
    {
      type: 'rakuten',
      title: '鶴仙園 オリジナル培養土 5L',
      img: 'https://thumbnail.image.rakuten.co.jp/@0_mall/auc-kakusenen/cabinet/soil/soil01.jpg',
      url: 'https://hb.afl.rakuten.co.jp/hgc/agavenavi/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E5%25A4%259A%25E8%2582%2589%25E6%25A4%258D%25E7%2589%25A9+%25E5%259F%25B9%25E9%25A4%258A%25E5%259C%259F%2F',
      price: '1,280円〜',
      shop: '楽天市場'
    },
    {
      type: 'rakuten',
      title: 'アガベ用 LED育成ライト',
      img: 'https://thumbnail.image.rakuten.co.jp/@0_mall/auc-gifuryokuenonline/cabinet/led/led-grow01.jpg',
      url: 'https://hb.afl.rakuten.co.jp/hgc/agavenavi/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F%25E6%25A4%258D%25E7%2589%25A9+LED+%25E8%2582%25B2%25E6%2588%2590%25E3%2583%25A9%25E3%2582%25A4%25E3%2583%2588%2F',
      price: '2,980円〜',
      shop: '楽天市場'
    },
    // --- Yahoo!ショッピング ---
    {
      type: 'yahoo',
      title: 'アガベ チタノタ 白鯨',
      img: 'https://item-shopping.c.yimg.jp/i/n/agave-titanota-hakugei',
      url: 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=agavenavi&pid=vc_agavenavi&vc_url=https%3A%2F%2Fshopping.yahoo.co.jp%2Fsearch%3Fp%3D%25E3%2582%25A2%25E3%2582%25AC%25E3%2583%2599+%25E3%2583%2581%25E3%2582%25BF%25E3%2583%258E%25E3%2582%25BF',
      price: '4,980円〜',
      shop: 'Yahoo!ショッピング'
    },
    {
      type: 'yahoo',
      title: '多肉植物 寄せ植えセット',
      img: 'https://item-shopping.c.yimg.jp/i/n/taniku-yoseue-set',
      url: 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=agavenavi&pid=vc_agavenavi&vc_url=https%3A%2F%2Fshopping.yahoo.co.jp%2Fsearch%3Fp%3D%25E5%25A4%259A%25E8%2582%2589%25E6%25A4%258D%25E7%2589%25A9+%25E5%25AF%2584%25E3%2581%259B%25E6%25A4%258D%25E3%2581%2588',
      price: '2,480円〜',
      shop: 'Yahoo!ショッピング'
    },
    {
      type: 'yahoo',
      title: 'BLACK PLASTIC POT 丸型',
      img: 'https://item-shopping.c.yimg.jp/i/n/black-plastic-pot',
      url: 'https://ck.jp.ap.valuecommerce.com/servlet/referral?sid=agavenavi&pid=vc_agavenavi&vc_url=https%3A%2F%2Fshopping.yahoo.co.jp%2Fsearch%3Fp%3D%25E3%2583%2596%25E3%2583%25A9%25E3%2583%2583%25E3%2582%25AF%25E3%2583%259D%25E3%2583%2583%25E3%2583%2588+%25E6%25A4%258D%25E7%2589%25A9',
      price: '580円〜',
      shop: 'Yahoo!ショッピング'
    },
    // --- Amazon ---
    {
      type: 'amazon',
      title: '多肉植物＆コーデックス GuideBook',
      img: 'https://m.media-amazon.com/images/I/51succulent-guidebook.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E5%A4%9A%E8%82%89%E6%A4%8D%E7%89%A9+%E5%9B%B3%E9%91%91&tag=agavenavi-22',
      price: '1,650円〜',
      shop: 'Amazon'
    },
    {
      type: 'amazon',
      title: 'アガベ・ユッカ その魅力と育て方',
      img: 'https://m.media-amazon.com/images/I/51agave-yucca-book.jpg',
      url: 'https://www.amazon.co.jp/s?k=%E3%82%A2%E3%82%AC%E3%83%99+%E8%82%B2%E3%81%A6%E6%96%B9&tag=agavenavi-22',
      price: '1,980円〜',
      shop: 'Amazon'
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
    // AdSenseスクリプトが読み込まれている場合のみ実行
    if (typeof adsbygoogle === 'undefined') return;
    document.querySelectorAll('.adsbygoogle').forEach(function(ad) {
      try {
        (adsbygoogle = window.adsbygoogle || []).push({});
      } catch(e) {}
    });
  }

  // === ページ読み込み時に実行 ===
  function init() {
    // アフィリエイトバーを配置
    var affSlots = document.querySelectorAll('.aff-slot');
    affSlots.forEach(function(slot) {
      var count = parseInt(slot.getAttribute('data-count')) || 4;
      renderAffiliateBar(slot, count);
    });

    // AdSense初期化
    initAdSense();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
