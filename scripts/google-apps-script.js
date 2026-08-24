/**
 * ================================================================
 * アガベイベントナビ - Google Form → GitHub 自動連携
 * ================================================================
 *
 * これを入れると、フォーム送信の瞬間に new-inquiries.json へ追記され、
 * notify-inquiry.yml が発火してメールが飛ぶ。
 * 日次タスクがブラウザで回答シートを開く必要がなくなる。
 *
 * 【なぜ必要か】
 * event-listing-review タスクは毎日 Chrome で回答シートを開いて新着を探していた。
 * ブラウザ操作の許可待ちで無人実行が止まり、2026-08-21〜24 は
 * lastChecked が更新されないまま気づかれなかった。
 * ポーリングをやめてイベント駆動にすれば、この止まり方が構造的に無くなる。
 *
 * 【設置手順】（一度だけ。5分）
 *
 * 1. 回答スプレッドシートを開く
 *    https://docs.google.com/spreadsheets/d/1iTWAAbd5FV4NkNyt186H8wR6KqTPOLcFWSvHghZMDvI/edit
 *
 * 2. 「拡張機能」→「Apps Script」
 *
 * 3. 既定の Code.gs の中身を消して、このファイルの内容を全部貼る
 *
 * 4. 歯車アイコン「プロジェクトの設定」→「スクリプトプロパティを追加」
 *      プロパティ: GITHUB_TOKEN
 *      値:        mzplants\agave-navi\github.pat の中身
 *                 (contents 権限だけで足りる。Actions権限は不要)
 *
 * 5. 時計アイコン「トリガー」→「トリガーを追加」
 *      関数:            onFormSubmit
 *      イベントのソース: スプレッドシートから
 *      イベントの種類:   フォーム送信時
 *    → 初回だけGoogleの認可画面が出るので許可する
 *
 * 6. 動作確認: エディタで関数 `testConnection` を選んで実行。
 *    実行ログに "OK" と現在の items 件数が出れば疎通している。
 *
 * ================================================================
 */

var CONFIG = {
  OWNER: 'mezack0520',
  REPO: 'agave-navi',
  PATH: 'new-inquiries.json',
  BRANCH: 'main',
  // 通知先。GitHub Actions 側でもメールは出るが、
  // GitHubへの書き込みが失敗したときはこちらだけが頼りになる
  ALERT_TO: 'yuji.mezaki@gmail.com'
};

/** フォーム送信時に自動実行される */
function onFormSubmit(e) {
  try {
    var v = e && e.namedValues ? e.namedValues : {};

    var item = {
      timestamp: pick(v, 'タイムスタンプ') || formatNow(),
      type: pick(v, 'お問い合わせ種別') || '(種別なし)',
      eventName: pick(v, 'イベント名'),
      name: pick(v, 'お名前'),
      email: pick(v, 'メールアドレス'),
      body: buildBody(v)
    };

    appendInquiry(item);
    Logger.log('appended: ' + JSON.stringify(item));

  } catch (err) {
    // ここで落とすと回答が消えるので、必ず自分に知らせる
    Logger.log('ERROR: ' + err);
    notify('[アガベイベントナビ] フォーム連携に失敗',
      'GitHubへの書き込みに失敗しました。回答はスプレッドシートに残っています。\n\n' +
      'エラー: ' + err + '\n\n' +
      '回答シート: https://docs.google.com/spreadsheets/d/' +
      '1iTWAAbd5FV4NkNyt186H8wR6KqTPOLcFWSvHghZMDvI/edit');
  }
}

/**
 * 既知の項目以外も本文に残す。
 * フォームに質問を足したときスクリプトを直さなくても取りこぼさないため。
 */
function buildBody(v) {
  var KNOWN = ['タイムスタンプ', 'お問い合わせ種別', 'イベント名', 'お名前', 'メールアドレス'];
  var lines = [];
  var main = pick(v, 'イベント概要');
  if (main) lines.push(main);
  for (var k in v) {
    if (KNOWN.indexOf(k) >= 0 || k === 'イベント概要') continue;
    var val = pick(v, k);
    if (val) lines.push(k + ': ' + val);
  }
  return lines.join('\n');
}

function pick(v, key) {
  var a = v[key];
  if (!a) return '';
  return String(Array.isArray(a) ? a.join(', ') : a).trim();
}

function formatNow() {
  return Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss');
}

/** new-inquiries.json を読んで item を足して書き戻す */
function appendInquiry(item) {
  var cur = getFile();
  var data = cur.json;

  data.items = data.items || [];
  // 同じタイムスタンプが既にあれば二重に積まない（トリガー再実行への備え）
  for (var i = 0; i < data.items.length; i++) {
    if (data.items[i].timestamp === item.timestamp) {
      Logger.log('already present, skip');
      return;
    }
  }
  data.items.push(item);
  data.lastChecked = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd');

  putFile(data, cur.sha,
    'feat(inquiry): フォーム受信 ' + item.type + ' [gas]');
}

function apiUrl() {
  return 'https://api.github.com/repos/' + CONFIG.OWNER + '/' + CONFIG.REPO +
         '/contents/' + CONFIG.PATH;
}

function authHeaders() {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) throw new Error('スクリプトプロパティ GITHUB_TOKEN が未設定');
  return {
    'Authorization': 'token ' + token,
    'Accept': 'application/vnd.github+json'
  };
}

function getFile() {
  var res = UrlFetchApp.fetch(apiUrl() + '?ref=' + CONFIG.BRANCH, {
    method: 'get', headers: authHeaders(), muteHttpExceptions: true
  });
  if (res.getResponseCode() !== 200) {
    throw new Error('GET ' + res.getResponseCode() + ': ' + res.getContentText().slice(0, 200));
  }
  var meta = JSON.parse(res.getContentText());
  var text = Utilities.newBlob(Utilities.base64Decode(meta.content)).getDataAsString('UTF-8');
  return { sha: meta.sha, json: JSON.parse(text) };
}

function putFile(data, sha, message) {
  var text = JSON.stringify(data, null, 2) + '\n';
  var res = UrlFetchApp.fetch(apiUrl(), {
    method: 'put',
    headers: authHeaders(),
    contentType: 'application/json',
    muteHttpExceptions: true,
    payload: JSON.stringify({
      message: message,
      content: Utilities.base64Encode(text, Utilities.Charset.UTF_8),
      sha: sha,
      branch: CONFIG.BRANCH
    })
  });
  var code = res.getResponseCode();
  if (code !== 200 && code !== 201) {
    throw new Error('PUT ' + code + ': ' + res.getContentText().slice(0, 200));
  }
}

function notify(subject, body) {
  try {
    MailApp.sendEmail(CONFIG.ALERT_TO, subject, body);
  } catch (e) {
    Logger.log('notify failed: ' + e);
  }
}

/** 設置後の疎通確認用。何も書き換えない */
function testConnection() {
  var cur = getFile();
  Logger.log('OK  items=' + (cur.json.items || []).length +
             '  lastChecked=' + cur.json.lastChecked);
}

/**
 * 取りこぼし回収用。トリガーが止まっていた期間の回答をまとめて送る。
 * シートの全行を見て、未処理のタイムスタンプだけ items に積む。
 */
function backfillFromSheet() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  var values = sheet.getDataRange().getValues();
  if (values.length < 2) { Logger.log('回答なし'); return; }

  var header = values[0].map(function (h) { return String(h).trim(); });
  var cur = getFile();
  var seen = {};
  (cur.json.items || []).forEach(function (it) { seen[it.timestamp] = true; });

  var added = 0;
  for (var r = 1; r < values.length; r++) {
    var v = {};
    for (var c = 0; c < header.length; c++) {
      if (header[c]) v[header[c]] = values[r][c];
    }
    var ts = v['タイムスタンプ'];
    ts = ts instanceof Date
      ? Utilities.formatDate(ts, 'Asia/Tokyo', 'yyyy/MM/dd HH:mm:ss')
      : String(ts).trim();
    if (!ts || seen[ts]) continue;

    appendInquiry({
      timestamp: ts,
      type: pick(v, 'お問い合わせ種別') || '(種別なし)',
      eventName: pick(v, 'イベント名'),
      name: pick(v, 'お名前'),
      email: pick(v, 'メールアドレス'),
      body: buildBody(v)
    });
    seen[ts] = true;
    added++;
    cur = getFile();  // sha を取り直す
  }
  Logger.log('backfill: ' + added + '件追加');
}
