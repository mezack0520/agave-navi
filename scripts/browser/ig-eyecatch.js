// Instagram の当該回の告知から、切り出されていないアイキャッチを取る。
//
// ## なぜブラウザなのか
// GitHub Actions のIPからも Cowork のサンドボックスからも instagram.com に
// 届かない(2026-09-08 実測。Actionsは30件すべてタイムアウトして取得0件)。
// 届くのは Cowork の組み込みブラウザだけ。
//
// ## og:image を使ってはいけない
// og:image のURLには `stp=c180.0.540.540a_dst-jpg_e35_s640x640_tt6` のような
// **切り出し指定**が入っている(この例は y=180 から 540x540 を切る)。
// 元が 1080x1350 の縦長フライヤーでも 540x540 に切られ、タイトルや
// 会場名が落ちる。2026-09-08 に74件をこれで保存してしまい、
// 半分近くの告知が見切れていた。
// URLの stp を差し替えても署名が合わず 403。
//
// **正しいのは投稿ページのDOMに描画されている画像**(stp=dst-jpg_e35_tt6)。
// 切り出しが入っていない。プロフィールのグリッドのサムネイルも
// 切り出し版なので使えない。
// つまり「投稿ページに遷移してDOMから採る」が唯一の道。
//
// ## 主画像の選び方（ここを外すと別イベントの画像を出す）
// 投稿ページの下には「More posts from …」のグリッドがあり、そこの画像は
// **別の投稿のもの**。リンクの中にある img は必ず除く。
//
// 以前は「表示面積が最大の img」だけで選んでいたが、組み込みブラウザが
// レイアウトを走らせていないと getBoundingClientRect() が全て 0 になり、
// 面積が並んで **DOM順の先頭に無言で落ちる**。その結果、関連投稿の画像を
// つかむことがあった(one-love-sano で雑談投稿の 940x529 を採っていた。
// 2026-09-08 に12件を誤った真因はこれ)。
//
// **カルーセルは「見えている面積」で選ぶ(2026-10-08)。**隣のスライドも同じ寸法で
// DOM に描画され、枠の overflow で隠れているだけなので、矩形の面積は表示中の
// スライドと並ぶ。並ぶと実寸の大きいほうに落ち、表示中の1枚目(フライヤー)ではなく
// 隣の写真を掴んでいた(西大寺ガーデンの SG fair、SPINE NOTE の ARCHIVE。5件中2件)。
// 画像の矩形を overflow で切る祖先とビューポートで切り詰めた面積で並べる。
// レイアウトが無く(面積が全て0)候補が複数なら、推測で選ばずに err を返す。
//
// ## リール投稿
// /reel/<code> では img が描画されない。**/p/<code>/ に読み替えると
// 表紙(無切り出し)が取れる。**それでも取れなければ動画なので諦める。
// 関連投稿の画像で埋めると、別イベントの画像を出すことになる。
//
// ## プロフィールから投稿を探すとき
// プロフィールHTMLを fetch しても投稿リンクが入っていない(credentials 付きでも
// 同じ)。web_profile_info API は 401 require_login。実際に遷移した後の
// DOM からしか取れない。
//
// ## 使い方
// 0. **ペインが隠れていると描画されない(2026-10-08)。**`document.visibilityState` が
//    'hidden' のままで、投稿の主画像もプロフィールのグリッドも DOM に出ず、
//    20秒待っても `no main image` / 投稿リンク0件になる。resize_window で寸法を
//    与えても hidden のまま。**navigate の直後に computer の screenshot を1回撮ると
//    'visible' になって描画される。**browser_batch では navigate → screenshot →
//    javascript の順に並べる(screenshot は scale 0.3 で足りる)
// 1. navigate で https://www.instagram.com/<handle>/ を開く
// 2. 注入して window.igPickPost(name, [dates]) を呼ぶ。直近の投稿から
//    キャプションで当該回を選び、投稿コードを返す
// 3. navigate で https://www.instagram.com/p/<code>/ を開く
// 4. window.igGrabHere(slug, post) を呼ぶ。主画像を取って積む
// 5. 結果は localStorage['__acc'] に積まれる。全件終わったら
//    JSON.parse(localStorage.__acc) を返し、上限超えでファイルに落ちたものを
//    サンドボックス側で読んでデコードする
//
// imageSource に投稿URLが既にあるなら 1〜2 は要らない。直接 3 から。
//
// ## 投稿の選び方
// 直近8件のキャプションを見て、イベント名の特徴語と開催日の両方が出るもの、
// または4文字以上の特徴語が出るものだけを採る。**適当な最新投稿を貼らない。**
// 店舗アカウントの最新投稿はただの植物写真であることが多く、それを
// そのイベントの画像として出すと来場者に誤った印象を与える。
//
// **そして、取れた画像は必ず人が1枚ずつ見る。**スコアと成功の返り値は
// 採否の根拠にならない。出店者募集のフライヤー、出店者紹介カード、
// 前回開催の御礼投稿、暑中見舞いを実際に掴んだことがある。
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

  // 開いているプロフィールから当該回の告知投稿を選ぶ。画像は取らない
  window.igPickPost = async function (name, dates, maxPosts) {
    const codes = postCodes(maxPosts || 8);
    const want = tokens(name);
    let best = null;
    const tried = [];
    for (const c of codes) {
      const r = await fetch('https://www.instagram.com/p/' + c + '/',
                            { credentials: 'omit' });
      if (r.status !== 200) continue;
      const t = await r.text();
      const cap = D((t.match(/<meta property="og:description" content="([^"]*)"/) || [])[1] || '');
      const nc = N(cap);
      const nh = want.filter(w => nc.includes(w));
      const dh = dateHits(nc, dates);
      const long = nh.some(w => w.length >= 4);
      const score = nh.length * 2 + dh.length * 2 + (long ? 2 : 0);
      tried.push({ c, score, nh, dh });
      if (((nh.length && dh.length) || long) && (!best || score > best.score)) {
        best = { c, score, nh, dh };
      }
    }
    if (!best) {
      return { err: 'no match', posts: codes.length, want, tried: tried.slice(0, 5) };
    }
    return { post: 'https://www.instagram.com/p/' + best.c + '/', code: best.c,
             score: best.score, nameHit: best.nh, dateHit: best.dh };
  };

  // 画面に実際に見えている面積。overflow で切る祖先(カルーセルの枠)とビューポートで切り詰める。
  // カルーセルは隣のスライドも同じ寸法で描画しておき、枠の overflow で隠している
  function visibleArea(el) {
    const r = el.getBoundingClientRect();
    let L = r.left, T = r.top, R = r.right, B = r.bottom;
    for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
      const cs = getComputedStyle(p);
      if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') {
        const q = p.getBoundingClientRect();
        L = Math.max(L, q.left); T = Math.max(T, q.top);
        R = Math.min(R, q.right); B = Math.min(B, q.bottom);
      }
    }
    L = Math.max(L, 0); T = Math.max(T, 0);
    R = Math.min(R, innerWidth || R); B = Math.min(B, innerHeight || B);
    return Math.max(0, R - L) * Math.max(0, B - T);
  }

  // いま開いている投稿ページの主画像を取って localStorage に積む
  window.igGrabHere = async function (slug, post, opt) {
    const o = Object.assign({ maxEdge: 900, quality: 0.72, waitSec: 20 }, opt || {});
    // 描画が遅い。固定の待ちでは足りず、8秒待っても img が0件の投稿がある
    // (2026-10-03: 3件中2件。数秒後に同じページで取れた)。主画像が出るまで1秒刻みで待つ
    const ready = () => [...document.querySelectorAll('img')].some(i =>
      /scontent|cdninstagram/.test(i.src) && i.naturalWidth >= 300
      && !i.closest('a[href*="/p/"]') && !i.closest('a[href*="/reel/"]'));
    for (let k = 0; k < o.waitSec && !ready(); k++) {
      await new Promise(r => setTimeout(r, 1000));
    }
    const cand = [...document.querySelectorAll('img')]
      .filter(i => /scontent|cdninstagram/.test(i.src)
                   && i.naturalWidth >= 300
                   && !i.closest('a[href*="/p/"]')
                   && !i.closest('a[href*="/reel/"]'))
      .map(i => ({ src: i.src, vis: visibleArea(i),
                   w: i.naturalWidth, h: i.naturalHeight,
                   stp: (i.src.match(/stp=([^&]+)/) || [])[1] || '' }))
      // 見えている面積で選ぶ。素の面積(矩形の幅x高さ)では、カルーセルの隣のスライドと
      // 表示中のスライドが同寸で並び、実寸の大きい隣のスライドに落ちる。
      // 実寸で並べるのはレイアウト未計算(見えている面積が全て0)のときだけ
      .sort((a, b) => b.vis - a.vis || b.w * b.h - a.w * a.h);
    if (!cand.length) {
      return { slug, err: 'no main image (' + o.waitSec + '秒待っても無い。動画投稿か描画前。ペインが隠れているなら screenshot を1回撮ってから呼び直す)' };
    }
    const pick = cand[0];
    // レイアウトが無いと、どのスライドが表示中か分からない。候補が複数なら推測で選ばない
    if (!(pick.vis > 0) && cand.length > 1) {
      return { slug, err: 'layout not computed (' + cand.length + ' 候補。どれが表示中か分からない。screenshot を1回撮ってから呼び直す)' };
    }
    // 切り出し指定つきのURLしか無いなら、それは主画像ではない
    if (/^c\d/.test(pick.stp)) {
      return { slug, err: 'cropped variant only', stp: pick.stp };
    }
    const ir = await fetch(pick.src);
    if (ir.status !== 200) return { slug, err: 'img ' + ir.status };
    const bmp = await createImageBitmap(await ir.blob());
    let w = bmp.width, h = bmp.height;
    const s = Math.min(1, o.maxEdge / Math.max(w, h));
    w = Math.round(w * s); h = Math.round(h * s);
    // 枠は1:1。切らずに余白を足す。余白の色はふちから拾う。
    // 白で埋めると濃い地のフライヤーで枠が浮く
    const n = Math.max(w, h);
    const cv = new OffscreenCanvas(n, n);
    const ctx = cv.getContext('2d');
    const probe = new OffscreenCanvas(w, h);
    const pc = probe.getContext('2d');
    pc.drawImage(bmp, 0, 0, w, h);
    const band = Math.max(1, Math.round((h > w ? w : h) / 12));
    const px = h > w ? pc.getImageData(0, 0, band, h).data
                     : pc.getImageData(0, 0, w, band).data;
    let r = 0, g = 0, b = 0, cnt = 0;
    for (let i = 0; i < px.length; i += 4) { r += px[i]; g += px[i + 1]; b += px[i + 2]; cnt++; }
    ctx.fillStyle = `rgb(${Math.round(r / cnt)},${Math.round(g / cnt)},${Math.round(b / cnt)})`;
    ctx.fillRect(0, 0, n, n);
    ctx.drawImage(bmp, Math.round((n - w) / 2), Math.round((n - h) / 2), w, h);
    const blob = await cv.convertToBlob({ type: 'image/jpeg', quality: o.quality });
    const bf = new Uint8Array(await blob.arrayBuffer());
    let bin = '';
    for (let i = 0; i < bf.length; i++) bin += String.fromCharCode(bf[i]);
    const acc = JSON.parse(localStorage.getItem('__acc') || '[]');
    acc.push({ slug, post: post || location.href, b64: btoa(bin) });
    localStorage.setItem('__acc', JSON.stringify(acc));
    return { slug, ok: 1, 元寸: bmp.width + 'x' + bmp.height, 保存: n + 'x' + n,
             stp: pick.stp, 候補: cand.length, bytes: bf.length, stored: acc.length };
  };
})();
