/**
 * ================================================================
 * アガベイベントナビ - Google Form → GitHub 自動連携スクリプト
 * ================================================================
 *
 * 【設置手順】
 *
 * 1. Google Formに以下のフィールドを追加（質問タイトルを正確に合わせてください）:
 *    - お問い合わせ種別（既存 - ラジオボタン）
 *    - イベント名（テキスト - 短文）
 *    - 開催日（日付）
 *    - 終了日（日付 - 複数日開催の場合）
 *    - 会場名（テキスト - 短文）
 *    - 住所（テキスト - 短文）
 *    - 都道府県（プルダウン）
 *    - 入場料（テキスト - 短文）
 *    - カテゴリ（チェックボックス: 即売会, マルシェ, 展示会, 大型イベント, ワークショップ）
 *    - イベント概要（テキスト - 長文）
 *    - 公式サイトURL（テキスト - 短文）
 *    - 主催者名（テキスト - 短文）
 *    - メールアドレス（テキスト - 短文）
 *
 * 2. Google Formのスプレッドシートを開く:
 *    「回答」タブ → スプレッドシートアイコン → 新しいスプレッドシートを作成
 *
 * 3. スプレッドシートで Apps Script を開く:
 *    「拡張機能」→「Apps Script」
 *
 * 4. このファイルの内容をすべてコピーして貼り付ける
 *
 * 5. GITHUB_TOKEN を設定:
 *    - Apps Script エディタで「プロジェクトの設定」（歯車アイコン）
 *    - 「スクリプトプロパティ」→「スクリプトプロパティを追加」
 *    - プロパティ名: GITHUB_TOKEN
 *    - 値: GitHub Personal Access Token (repo権限付き)
 *
 * 6. トリガーを設定:
 *    - Apps Script エディタで「トリガー」（時計アイコン）
 *    - 「トリガーを追加」
 *    - 関数: onFormSubmit
 *    - イベントソース: スプレッドシートから
 *    - イベントの種類: フォーム送信時
 *
 * ================================================================
 */

// === 設定 ===
var CONFIG = {
  GITHUB_OWNER: 'mezack0520',
  GITHUB_REPO: 'agave-navi',
  // GITHUB_TOKENはスクリプトプロパティから取得
};

/**
 * フォーム送信時に自動実行される関数
 */
function onFormSubmit(e) {
  try {
    var response = e.namedValues;

    // お問い合わせ種別が「イベント掲載リクエスト」の場合のみ処理
    var type = getFieldValue(response, 'お問い合わせ種別');
    if (type !== 'イベント掲載リクエスト') {
      Logger.log('Not an event listing request, skipping. Type: ' + type);
      return;
    }

    // イベントデータを構築
    var eventData = {
      name: getFieldValue(response, 'イベント名'),
      date: formatDate(getFieldValue(response, '開催日')),
      end_date: formatDate(getFieldValue(response, '終了日')) || formatDate(getFieldValue(response, '開催日')),
      venue: getFieldValue(response, '会場名'),
      address: getFieldValue(response, '住所'),
      prefecture: getFieldValue(response, '都道府県'),
      admission: getFieldValue(response, '入場料') || '詳細は公式サイトをご確認ください',
      category: getFieldValue(response, 'カテゴリ'),
      tags: getFieldValue(response, 'カテゴリ'),
      description: getFieldValue(response, 'イベント概要'),
      official_url: getFieldValue(response, '公式サイトURL'),
      organizer: getFieldValue(response, '主催者名')
    };

    // バリデーション
    if (!eventData.name || !eventData.date || !eventData.venue) {
      Logger.log('Missing required fields. Data: ' + JSON.stringify(eventData));
      sendNotification('掲載リクエスト受信（不完全）',
        'イベント名: ' + eventData.name + '\n必須項目が不足しています。手動で確認してください。');
      return;
    }

    // GitHub Repository Dispatch を送信
    var success = triggerGitHubAction(eventData);

    if (success) {
      Logger.log('Successfully triggered GitHub Action for: ' + eventData.name);
      sendNotification('イベント自動掲載開始',
        'イベント名: ' + eventData.name + '\n開催日: ' + eventData.date + '\nGitHub Actionsでページ生成中...');
    } else {
      Logger.log('Failed to trigger GitHub Action');
      sendNotification('GitHub連携エラー',
        'イベント名: ' + eventData.name + '\nGitHub Actionsのトリガーに失敗しました。手動で掲載してください。');
    }

  } catch (error) {
    Logger.log('Error in onFormSubmit: ' + error.toString());
    sendNotification('フォーム処理エラー', error.toString());
  }
}

/**
 * GitHub Repository Dispatch イベントを送信
 */
function triggerGitHubAction(eventData) {
  var token = PropertiesService.getScriptProperties().getProperty('GITHUB_TOKEN');
  if (!token) {
    Logger.log('GITHUB_TOKEN not set in script properties');
    return false;
  }

  var url = 'https://api.github.com/repos/' + CONFIG.GITHUB_OWNER + '/' + CONFIG.GITHUB_REPO + '/dispatches';

  var payload = {
    event_type: 'new-event',
    client_payload: eventData
  };

  var options = {
    method: 'post',
    contentType: 'application/json',
    headers: {
      'Authorization': 'token ' + token,
      'Accept': 'application/vnd.github.v3+json'
    },
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  var response = UrlFetchApp.fetch(url, options);
  var code = response.getResponseCode();

  Logger.log('GitHub API response code: ' + code);

  // 204 = 成功（No Content）
  return code === 204;
}

/**
 * フォームの回答から値を取得（キー名の揺れに対応）
 */
function getFieldValue(namedValues, fieldName) {
  // 完全一致
  if (namedValues[fieldName]) {
    return namedValues[fieldName].join(', ').trim();
  }
  // 部分一致
  for (var key in namedValues) {
    if (key.indexOf(fieldName) !== -1 || fieldName.indexOf(key) !== -1) {
      return namedValues[key].join(', ').trim();
    }
  }
  return '';
}

/**
 * 日付文字列をYYYY-MM-DD形式に変換
 */
function formatDate(dateStr) {
  if (!dateStr) return '';
  try {
    var d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    var year = d.getFullYear();
    var month = ('0' + (d.getMonth() + 1)).slice(-2);
    var day = ('0' + d.getDate()).slice(-2);
    return year + '-' + month + '-' + day;
  } catch (e) {
    return dateStr;
  }
}

/**
 * 管理者にメール通知を送信
 */
function sendNotification(subject, body) {
  try {
    MailApp.sendEmail({
      to: 'mezaki@sterfield.co.jp',
      subject: '[アガベイベントナビ] ' + subject,
      body: body + '\n\n---\nこのメールはアガベイベントナビの自動システムから送信されています。'
    });
  } catch (e) {
    Logger.log('Failed to send notification: ' + e.toString());
  }
}

/**
 * テスト用: 手動でイベントを追加（Apps Scriptエディタから実行可能）
 */
function testAddEvent() {
  var testData = {
    name: 'テストイベント2026',
    date: '2026-07-01',
    end_date: '2026-07-02',
    venue: 'テスト会場',
    address: '東京都渋谷区神南1-1-1',
    prefecture: '東京都',
    admission: '入場無料',
    category: '即売会',
    tags: '即売会,マルシェ',
    description: 'これはテスト用のイベントです。自動掲載のテストとして使用しています。',
    official_url: 'https://example.com',
    organizer: 'テスト主催者'
  };

  var success = triggerGitHubAction(testData);
  Logger.log('Test result: ' + (success ? 'SUCCESS' : 'FAILED'));
}
