import re

def items(css):
    """トップレベルの要素を返す。(kind, start, end, selector, brace_open, brace_close)"""
    out, i, n = [], 0, len(css)
    while i < n:
        if css[i] in ' \n\t\r':
            i += 1; continue
        if css.startswith('/*', i):
            e = css.find('*/', i); i = (e + 2) if e >= 0 else n; continue
        if css[i] == '@':
            b = css.find('{', i); sc = css.find(';', i)
            if b < 0 or (0 <= sc < b):
                i = (sc + 1) if sc >= 0 else n; continue
            d, j = 1, b + 1
            while d and j < n:
                if css[j] == '{': d += 1
                elif css[j] == '}': d -= 1
                j += 1
            out.append(('at', i, j, css[i:b].strip(), b, j)); i = j; continue
        b = css.find('{', i)
        if b < 0: break
        d, j = 1, b + 1
        while d and j < n:
            if css[j] == '{': d += 1
            elif css[j] == '}': d -= 1
            j += 1
        out.append(('rule', i, j, css[i:b].strip(), b, j)); i = j
    return out


def edit(css, fn, depth=0):
    """規則ごとに fn(selectors:list, body:str) -> (selectors, body) | None を当てる。
    None を返すと規則ごと削除。**セレクタ列は必ず丸ごと書き換える。**
    正規表現で1行だけ消すと、複数行グループの残りが宙に浮く
    (2026-09-08 に2箇所やった)。"""
    edits = []
    for kind, a, b, sel, bo, bc in items(css):
        if kind == 'at':
            inner = css[bo + 1:bc - 1]
            new_inner = edit(inner, fn, depth + 1)
            if new_inner != inner:
                if not new_inner.strip():
                    edits.append((a, b, ''))
                else:
                    edits.append((bo + 1, bc - 1, new_inner))
            continue
        sels = [x.strip() for x in sel.split(',') if x.strip()]
        body = css[bo + 1:bc - 1]
        r = fn(sels, body)
        if r is None:
            edits.append((a, b, ''))
        else:
            ns, nb = r
            if ns != sels or nb != body:
                if not ns:
                    edits.append((a, b, ''))
                else:
                    edits.append((a, b, ',\n'.join(ns) + ' {' + nb + '}'))
    out = css
    for a, b, new in sorted(edits, key=lambda x: -x[0]):
        out = out[:a] + new + out[b:]
    return out


def check(css):
    """セレクタの形が壊れていないか。壊れている行を返す。"""
    bad = []
    for kind, a, b, sel, bo, bc in items(css):
        if kind == 'at':
            bad += [(l, m) for l, m in check(css[bo + 1:bc - 1])]
            continue
        ln = css[:a].count('\n') + 1
        if '/*' in sel or '*/' in sel:
            bad.append((ln, 'セレクタにコメント'))
        elif not sel.strip():
            bad.append((ln, 'セレクタが空'))
        elif sel.strip().endswith(','):
            bad.append((ln, 'カンマで終わる'))
    return bad
