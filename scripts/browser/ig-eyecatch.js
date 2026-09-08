// Instagram の当該回の告知投稿から、アイキャッチを取って localStorage に積む。
//
// ## なぜブラウザなのか
// GitHub Actions のIPからも Cowork のサンドボックスからも instagram.com に
// 届かない(2026-09-08 実測。Actionsは30件すべてタイムアウトして取得0件)。
// 届くのは Cowork の組み込みブラウザだけ。
//
// ## なぜプロフィールに遷移するのか
// プロフィールHTMLを fetch しても投稿リンクが入っていない(credentials 付きでも同じ)。
// 投稿は JS で描画されるので、実際に遷移した後の DOM からしか取れない。
// web_profile_info API は 401 require_login。
//
// ## 使い方
// 1. navigate で https://www.instagram.com/<handle>/ を開く
// 2. この関数を注入して window.igEyecatch(slug, name, [dates]) を呼ぶ
// 3. 結果は localStorage['__acc'] に積まれる。全件終わったら
//    JSON.parse(localStorage.__acc) を返し、上限超えでファイルに落ちたものを
//    サンドボックス側で読んでデコードする
//
// ## 投稿の選び方
// 直近8件のキャプションを見て、イベント名の特徴語と開催日の両方が出るもの、
// または4文字以上の特徴語が出るものだけを採る。**適当な最新投稿を貼らない。**
// 店舗アカウントの最新投稿はただの植物写真であることが多く、それを
// そのイベントの画像として出すと来場者に誤った印象を与える。
(function () {
  const D = s => s.replace(/&#x([0-9a-f]+);/gi, (m, h) => String.fromCodePoint(parseInt(h, 16)))
    .replace(/&amp;/g, '&');
  const N = s => (s || '').normalize('NFKC').toLowerCase();
  // 照合の役に立たない共通語。これを残すと関係ない投稿に当たる
  const GENERIC = new Set(['vol', '2026', '2027', 'the', 'and', 'plants', 'plant',
    'popup', 'pop', 'market', 'fes', 'show', 'shop', 'store',
    '第', '回', '開催', '販売', '即売', '即売会', 'マルシェ', 'フェス', 'フェスタ',
    'イベント', '会場', '出店', '植物']);

  function tokens(name) {
    const n = N(name).replace(/[（）()【】\[\]・,、.。!！?？~〜_/&-]/g, ' ');
    const raw = n.match(/[぀-ヿ]{2,}|[一-鿿]{2,}|[a-z0-9]{3,}/g) || [];
    return [...new Set(raw.filter(t => !GENERIC.has(t) && !/^[0-9]+$/.test(t)))];
  }

  function dateHits(capNorm, dates) {
    const out = [];
    for (const d of new Set(dates)) {
      const p = d.split('-');
      for (const s of [(+p[1]) + '月' + (+p[2]) + '日', (+p[1]) + '/' + (+p[2])]) {
        if (capNorm.includes(s)) out.push(s);
      }
    }
    return out;
  }

  function postCodes(max) {
    const as = [...document.querySelectorAll('a[href*="/p/"],a[href*="/reel/"]')];
    const cs = as.map(a => ((a.getAttribute('href') || '').split(/\/(?:p|reel)\//)[1] || '')
      .split('/')[0]).filter(Boolean);
    return [...new Set(cs)].slice(0, max);
  }

  window.igEyecatch = async function (slug, name, dates, opt) {
    const o = Object.assign({ maxPosts: 8, maxEdge: 560, quality: 0.62 }, opt || {});
    const codes = postCodes(o.maxPosts);
    const want = tokens(name);
    let best = null;
    for (const c of codes) {
      const r = await fetch('https://www.instagram.com/p/' + c + '/', { credentials: 'omit' });
      if (r.status !== 200) continue;
      const t = await r.text();
      const cap = D((t.match(/<meta property="og:description" content="([^"]*)"/) || [])[1] || '');
      const nc = N(cap);
      const nh = want.filter(w => nc.includes(w));
      const dh = dateHits(nc, dates);
      const long = nh.some(w => w.length >= 4);
      const score = nh.length * 2 + dh.length * 2 + (long ? 2 : 0);
      if (((nh.length && dh.length) || long) && (!best || score > best.score)) {
        const im = (t.match(/<meta property="og:image" content="([^"]+)"/) || [])[1];
        best = { c, score, nh, dh, img: im ? im.replace(/&amp;/g, '&') : '' };
      }
    }
    if (!best || !best.img) return { slug, err: 'no match', posts: codes.length, want };
    const ir = await fetch(best.img);
    if (ir.status !== 200) return { slug, err: 'img ' + ir.status };
    const bmp = await createImageBitmap(await ir.blob());
    let w = bmp.width, h = bmp.height;
    const s = Math.min(1, o.maxEdge / Math.max(w, h));
    w = Math.round(w * s); h = Math.round(h * s);
    const cv = new OffscreenCanvas(w, h);
    cv.getContext('2d').drawImage(bmp, 0, 0, w, h);
    const blob = await cv.convertToBlob({ type: 'image/jpeg', quality: o.quality });
    const bf = new Uint8Array(await blob.arrayBuffer());
    let bin = '';
    for (let i = 0; i < bf.length; i++) bin += String.fromCharCode(bf[i]);
    const acc = JSON.parse(localStorage.getItem('__acc') || '[]');
    acc.push({ slug, post: 'https://www.instagram.com/p/' + best.c + '/',
               score: best.score, b64: btoa(bin) });
    localStorage.setItem('__acc', JSON.stringify(acc));
    return { slug, ok: 1, score: best.score, nameHit: best.nh, dateHit: best.dh,
             bytes: bf.length, stored: acc.length };
  };
})();
