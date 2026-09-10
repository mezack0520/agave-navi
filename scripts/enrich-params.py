#!/usr/bin/env python3
"""enrich-params.py — 週次エンリッチメントの実行パラメータを決める。

**2026-09-10 に weekly-enrichment.yml から出した。**「今週は何件やるのか」を
YAML の中で決めていたので、ローカルで確かめられなかった。

優先順位は workflow_dispatch の入力 > enrich-request.json > 既定値。
cron 実行も同じファイルを読むので、恒久的に変えたいなら
enrich-request.json を直す。

  python3 scripts/enrich-params.py            # limit=/slug=/orphans= を出す
  python3 scripts/enrich-params.py --self-test
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_LIMIT = 20


def load_cfg(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def resolve(cfg, env):
    """(limit, slug, orphans) を返す。dispatch入力が最優先。"""
    limit = str(env.get('IN_LIMIT') or cfg.get('limit') or DEFAULT_LIMIT)
    slug = env.get('IN_SLUG') or cfg.get('slug') or ''
    orphans = (env.get('IN_ORPH') == 'true') or bool(cfg.get('removeOrphans'))
    return limit, slug, orphans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', default=os.path.join(REPO, 'enrich-request.json'))
    ap.add_argument('--self-test', action='store_true')
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    limit, slug, orphans = resolve(load_cfg(a.config), os.environ)
    print(f'limit={limit}')
    print(f'slug={slug}')
    print(f'orphans={str(orphans).lower()}')
    return 0


def self_test():
    assert resolve({}, {}) == ('20', '', False), '既定値'
    assert resolve({'limit': 5}, {}) == ('5', '', False), 'ファイルの値'
    assert resolve({'limit': 5}, {'IN_LIMIT': '9'}) == ('9', '', False), 'dispatchが勝つ'
    assert resolve({'limit': 5}, {'IN_LIMIT': ''}) == ('5', '', False), '空入力は無視'
    assert resolve({'slug': 'x'}, {'IN_SLUG': 'y'})[1] == 'y'
    assert resolve({'removeOrphans': True}, {})[2] is True
    assert resolve({}, {'IN_ORPH': 'true'})[2] is True
    assert resolve({}, {'IN_ORPH': 'false'})[2] is False
    assert resolve({'limit': 0}, {}) == ('20', '', False), 'limit=0 は既定に落ちる(従来動作)'
    assert load_cfg(os.path.join(REPO, 'no-such-file.json')) == {}, '無ければ空'
    print('self-test: 10 assertions OK')
    return 0


if __name__ == '__main__':
    sys.exit(main())
