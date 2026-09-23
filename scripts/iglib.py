#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Instagram Graph API の呼び出しを1か所にまとめる。

ig-weekly.py(投稿)と ig-organizer-watch.py(主催者の見張り)が
それぞれ自前の呼び出しを持っていた(2026-09-23 に統合)。
API版の更新やエラーの扱いを片方だけ直すと、もう片方が古いまま残る。

トークンは Facebook ページ「アガナビ」の期限なしページトークン(Secret IG_PAGE_TOKEN)。
"""
import json
import urllib.error
import urllib.parse
import urllib.request

GRAPH = 'https://graph.facebook.com/v23.0'

# 呼び出し回数の上限に当たったときのエラーコード。当たったら打ち切る
RATE_CODES = {4, 17, 32, 613, 80002}


def call(method, path, token, timeout=60, **params):
    """(data, err) を返す。例外は投げない。err は Graph API の error オブジェクト"""
    params['access_token'] = token
    q = urllib.parse.urlencode(params)
    url = f'{GRAPH}/{path}'
    if method == 'GET':
        req = urllib.request.Request(url + '?' + q)
    else:
        req = urllib.request.Request(url, data=q.encode(), method='POST')
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r), None
    except urllib.error.HTTPError as ex:
        body = ex.read().decode('utf-8', 'replace')
        try:
            err = json.loads(body).get('error') or {}
        except Exception:
            err = {}
        err.setdefault('message', f'HTTP {ex.code} {body[:200]}')
        err.setdefault('http', ex.code)
        return None, err
    except Exception as ex:  # 接続系
        return None, {'message': str(ex)}


def req(method, path, token, **params):
    """失敗したら RuntimeError。投稿のように途中で止めるべき処理用"""
    data, err = call(method, path, token, **params)
    if err:
        raise RuntimeError(f'{method} {path}: {err.get("code", "")} {err.get("message")}')
    return data


def own_account(token):
    """ページに紐付いた @agave_navi の (ig_user_id, username, page_name)。紐付いていなければ id は None"""
    me = req('GET', 'me', token, fields='id,name,instagram_business_account{id,username}')
    iga = me.get('instagram_business_account') or {}
    return iga.get('id'), iga.get('username'), me.get('name')


def business_discovery(ig_id, username, token, fields):
    """他アカウントの公開情報。(business_discovery の中身, err)。
    個人アカウントは読めない(ユーザーが見つからない、というエラーになる)"""
    data, err = call('GET', ig_id, token, timeout=40,
                     fields=f'business_discovery.username({username}){{{fields}}}')
    if err:
        return None, err
    return data.get('business_discovery') or {}, None
