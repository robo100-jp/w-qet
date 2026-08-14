# -*- coding: utf-8 -*-
"""点検メモ（`docs/点検メモ.md`）を作る —— パソコン上で書き込む表

**チートシートとは役割が違う。** チートシートは作図中に番号を引くためのもので、
よく使う40個しか載せない。こちらは**176個ぜんぶ**を並べて、
使っていて気づいたことを書き留めるためのもの。

  py -3 tools/checklist.py            # docs/点検メモ.md（と図）
  py -3 tools/checklist.py --print    # 印刷用の A4（docs/点検表/*.svg）も出す

**書き込んだものは作り直しても消えない。** 既にある `docs/点検メモ.md` を読んで、
「済」と「気づいたこと」の中身を番号で引き継ぐ。記号を足したら行が増えるだけ。

> **表の中で `|` を素で書かない。** 列の区切りと見分けが付かず、行が壊れる。
> 書きたいときは `\\|` とする。

直したら該当行を空に戻す。控えを残したいものは
[docs/測定メモ.md](../docs/測定メモ.md) へ。
"""
import argparse
import os
import re
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog as C                                         # noqa: E402
import paths as P                                           # noqa: E402
import svg_elmt as S                                        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

DOCS = os.path.join(P.REPO, "docs")
SYM = os.path.join(DOCS, "images", "sym")            # 1個ずつの図
MEMO = os.path.join(DOCS, "点検メモ.md")

PX_PER_UNIT = .8                # 表の中での図の大きさ
PX_MIN, PX_MAX = 22, 74         # 行が潰れる／伸びすぎるのを防ぐ

HEAD = """# 点検メモ

記号を使っていて気づいたことを書き留める表。**176個ぜんぶ**が載っている。
番号を引くだけなら [チートシート](チートシート.svg)、
姿を見比べるなら [カタログ](カタログ.md)。

> **この表は作り直しても消えない。** `py -3 tools/checklist.py` は
> 既にある「済」と「気づいたこと」を番号で引き継ぐ。記号を足せば行が増えるだけ。

**書き方**

- 「済」に `✔` を入れると見たしるしになる。直したら行を空に戻す
- **`|` を素で書かない。** 列の区切りと見分けが付かず行が壊れる。`\\|` とする
- 残しておきたい控えは [測定メモ.md](測定メモ.md) へ

印刷して紙に書きたいときは `py -3 tools/checklist.py --print` で
`docs/点検表/` に A4 が出る。

"""

# --- 印刷用 A4（--print のときだけ） ---------------------------------------
PW, PH, MARGIN = 210., 297., 9.
HEAD_H, FOOT_H = 11., 6.
X_CHK, X_FIG, X_NAME, X_MEMO = 14., 44., 94., PW - MARGIN
MM_PER_UNIT = .20
MAX_K = .38
ROW_MIN, ROW_PAD = 11., 3.
TITLE = "図記号 点検メモ"
NOTE = "気づいたことをその場で書く。直したら docs/点検メモ.md に写す"


def rows():
    """[(節の表示名 or None, パス)] を elements/ の並びのまま返す

    節が変わる行にだけ表示名を入れる（見出しを出す合図）。
    """
    secs = S.sections()
    out, cur = [], None
    for key in sorted(secs):
        ja = C.dirname_ja(os.path.join(P.ELEMENTS, *key.split("/")))
        for p in sorted(secs[key]):
            out.append((ja if ja != cur else None, p))
            cur = ja
    return out


def read_memo():
    """既にある点検メモから {番号: (済, 気づいたこと)} を読む

    **手で書き換えられている前提で読む。** 列の幅も空白も揃っていないので、
    番号のセルだけを頼りに引く。読めない行は捨てずに黙って飛ばす
    （消えたら書いた人が困るのは同じだが、壊れた行に引きずられて
    全部を落とすほうが害が大きい）。
    """
    if not os.path.isfile(MEMO):
        return {}
    out = {}
    for line in open(MEMO, encoding="utf-8"):
        if not line.lstrip().startswith("|"):
            continue
        # **`\|` で割らない。** 表の中に縦棒を書けるようにエスケープを勧めておいて
        # ここで素の区切りとして割ると、書いた本人のメモが途中で切れる（実際にやった）
        cells = [c.strip() for c in
                 re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 5:
            continue
        m = re.fullmatch(r"`([0-9A-Za-z_\-]+)`", cells[1])
        if m:
            out[m.group(1)] = (cells[3], cells[4])
    return out


def sym_svg(path):
    """1個ずつの図を書き出して (ファイル名, 表示する高さpx) を返す"""
    base = os.path.basename(path)[:-5]
    _, (x0, y0, x1, y1), _, _ = S.body(path, False)
    open(os.path.join(SYM, base + ".svg"), "w", encoding="utf-8").write(
        S.one(path))
    # **高さ0の記号がある**（07-01-03 は横棒1本）。そのまま使うと表示が潰れる
    h = (y1 - y0) or (x1 - x0)
    return base, max(PX_MIN, min(PX_MAX, int(round(h * PX_PER_UNIT))))


def build_md(items, keep):
    out = [HEAD]
    cur = None
    for ja, path in items:
        if ja and ja != cur:
            cur = ja
            out.append("\n## %s\n" % ja)
            out.append("| 図 | 番号 | 名称 | 済 | 気づいたこと |")
            out.append("|---|---|---|---|---|")
        base, px = sym_svg(path)
        _, _, name, _ = S.body(path, False)
        done, memo = keep.get(base, ("", ""))
        out.append('| <img src="images/sym/%s.svg" height="%d"> | `%s` | %s | %s | %s |'
                   % (base, px, base, name, done, memo))
    return "\n".join(out) + "\n"


# --- 以下 --print の印刷用 --------------------------------------------------

def row_svg(path, top, h):
    """1行ぶん。**図はセルいっぱいに引き伸ばす**（上限 MAX_K）

    行の高さは記号の実寸で決めるが、図はセルに合わせて拡大する。
    そうしないと 07-01-03（横棒1本）が 4mm に潰れて紙の上で何か分からなくなる。
    横棒・縦棒だけの記号は広がりが片方 0 になるので、割る前に避ける。
    """
    g, (x0, y0, x1, y1), ja, _ = S.body(path, False)
    figw, figh = X_FIG - X_CHK - 4, h - 2
    k = MAX_K
    if x1 - x0 > 0:
        k = min(k, figw / (x1 - x0))
    if y1 - y0 > 0:
        k = min(k, figh / (y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    base = os.path.basename(path)[:-5]
    return [
        '<g transform="translate(%g %g) scale(%g) translate(%g %g)"'
        ' stroke="black" fill="none">%s</g>'
        % ((X_CHK + X_FIG) / 2, top + h / 2, k, -cx, -cy, g),
        '<rect x="%g" y="%g" width="3.4" height="3.4" fill="none"'
        ' stroke="#666" stroke-width="0.25"/>' % (MARGIN + 0.6, top + h / 2 - 1.7),
        '<text x="%g" y="%g" font-family="%s" font-size="2.6" fill="black">%s</text>'
        % (X_FIG + 2, top + h / 2 - 0.3, S.CAPFONT, escape(base)),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#333">%s</text>'
        % (X_FIG + 2, top + h / 2 + 3.2, S.CAPFONT,
           escape(S._fit(ja, X_NAME - X_FIG - 3, 2.2))),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#ccc" stroke-width="0.15"/>'
        % (X_NAME, top + 0.5, X_NAME, top + h - 0.5),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#999" stroke-width="0.2"/>'
        % (MARGIN, top + h, X_MEMO, top + h),
    ]


def band(ja, top):
    return [
        '<rect x="%g" y="%g" width="%g" height="5" fill="#eee"/>'
        % (MARGIN, top, X_MEMO - MARGIN),
        '<text x="%g" y="%g" font-family="%s" font-size="2.9" font-weight="bold"'
        ' fill="black">%s</text>' % (MARGIN + 1.5, top + 3.6, S.CAPFONT, escape(ja)),
    ]


def page(parts, n, total):
    head = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm"'
        ' viewBox="0 0 %g %g">' % (PW, PH, PW, PH),
        '<rect width="%g" height="%g" fill="white"/>' % (PW, PH),
        '<g stroke-linecap="round" stroke-linejoin="round">',
        '<text x="%g" y="%g" font-family="%s" font-size="4.4" font-weight="bold"'
        ' fill="black">%s</text>' % (MARGIN, MARGIN + 3.4, S.CAPFONT, escape(TITLE)),
        # **節名はここに並べない。**5節に跨るページがあり見出しに食い込む。
        # どの節かは行のあいだの帯が持つ
        '<text x="%g" y="%g" text-anchor="end" font-family="%s" font-size="2.8"'
        ' fill="#555">%s</text>'
        % (X_MEMO, MARGIN + 3.4, S.CAPFONT, escape("%d / %d" % (n, total))),
        '<text x="%g" y="%g" font-family="%s" font-size="2.3" fill="#666">%s</text>'
        % (MARGIN, MARGIN + 7.4, S.CAPFONT, escape(NOTE)),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#333" stroke-width="0.4"/>'
        % (MARGIN, MARGIN + HEAD_H - 1.4, X_MEMO, MARGIN + HEAD_H - 1.4),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#666">番号・名称</text>'
        % (X_FIG + 2, MARGIN + HEAD_H + 1.4, S.CAPFONT),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#666">気づいたこと</text>'
        % (X_NAME + 2, MARGIN + HEAD_H + 1.4, S.CAPFONT),
    ]
    return "\n".join(head + parts + ['</g></svg>', ''])


def build_print(items):
    d = os.path.join(DOCS, "点検表")
    os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):                    # 数が減ったとき古いページを残さない
        if old.endswith(".svg"):
            os.remove(os.path.join(d, old))
    bottom = PH - MARGIN - FOOT_H
    pages, parts = [], []
    y = MARGIN + HEAD_H + 2.4
    cur = ""
    for ja, path in items:
        if ja:
            cur = ja
        _, (_, y0, _, y1), _, _ = S.body(path, False)
        h = max(ROW_MIN, (y1 - y0) * MM_PER_UNIT + ROW_PAD)
        show, cont = ja is not None, False
        if y + h + (5.4 if show else 0) > bottom and parts:
            pages.append(parts)
            parts, y = [], MARGIN + HEAD_H + 2.4
            # **送った先で節名を出し直す。** でないとそのページだけ見たとき
            # どの節を見ているのか分からない
            show, cont = True, ja is None
        if show:
            parts += band(cur + ("（つづき）" if cont else ""), y)
            y += 5.4
        parts += row_svg(path, y, h)
        y += h
    if parts:
        pages.append(parts)
    for i, parts in enumerate(pages, 1):
        open(os.path.join(d, "%02d.svg" % i), "w", encoding="utf-8").write(
            page(parts, i, len(pages)))
    return len(pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print", dest="pr", action="store_true",
                    help="印刷用の A4 も出す")
    a = ap.parse_args()

    os.makedirs(SYM, exist_ok=True)
    items = rows()
    keep = read_memo()
    open(MEMO, "w", encoding="utf-8").write(build_md(items, keep))
    written = sum(1 for v in keep.values() if v[0] or v[1])
    print("書き出し: %s  %d行（書き込み済み %d行を引き継いだ）"
          % (os.path.relpath(MEMO, P.REPO), len(items), written))

    if a.pr:
        n = build_print(items)
        print("印刷用: docs/点検表/  A4 %d枚" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
