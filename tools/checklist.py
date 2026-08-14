# -*- coding: utf-8 -*-
"""点検表（`docs/点検表/*.svg`）を作る —— 見つけたことを手で書き込む A4

**チートシートとは役割が違う。** チートシートは作図中に番号を引くためのもので、
よく使う40個しか載せない。こちらは**176個ぜんぶ**を並べて、
使っていて気づいたことをその場で書き留めるためのもの。

  py -3 tools/checklist.py

1行が1個。**☐ ／ 図 ／ 番号・名称 ／ 気づいたこと**。
書ける幅を優先して1列にしてあるので A4 で数ページになる。節の変わり目に帯を入れ、
`docs/点検表.md` がどのページにどの節が載っているかを持つ。

書き込んだものをリポジトリに戻すときは [docs/測定メモ.md](../docs/測定メモ.md) へ。
**紙のほうは残さない**（撮った画像もリポジトリに入れない）。
"""
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog as C                                         # noqa: E402
import paths as P                                           # noqa: E402
import svg_elmt as S                                        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

PW, PH, MARGIN = 210., 297., 9.       # A4 縦（mm）
HEAD_H = 11.                          # 見出しの高さ
FOOT_H = 6.                           # ページ番号の帯

# 列の右端（mm）。**メモ欄をいちばん広く取る。**書けない幅なら表の意味がない
X_CHK, X_FIG, X_NAME, X_MEMO = 14., 44., 94., PW - MARGIN

MM_PER_UNIT = .20                     # 行の高さを決める縮尺。1M（10単位）= 2.0mm
MAX_K = .38                           # 図の拡大の上限。**小さい記号は引き伸ばす**
ROW_MIN = 11.                         # 行の高さの下限（手で書ける高さ）
ROW_PAD = 3.

TITLE = "図記号 点検メモ"
NOTE = "気づいたことをその場で書く。直したら docs/測定メモ.md に写して紙は残さない"


def rows():
    """[(節の表示名 or None, パス)] を elements/ の並びのまま返す

    節が変わる行にだけ表示名を入れる（帯を出す合図）。
    """
    out, cur = [], None
    for key in sorted(S.sections()):
        ja = C.dirname_ja(os.path.join(P.ELEMENTS, *key.split("/")))
        for p in sorted(S.sections()[key]):
            out.append((ja if ja != cur else None, p))
            cur = ja
    return out


def row_svg(path, top, h):
    """1行ぶん。**図はセルいっぱいに引き伸ばす**（上限 MAX_K）

    行の高さは MM_PER_UNIT で決めるが、図そのものはセルに合わせて拡大する。
    そうしないと 07-01-03（横棒1本）のような小さい記号が 4mm で潰れ、
    紙の上で何の記号か分からなくなる。**識別できることを優先する。**
    横棒や縦棒だけの記号は広がりが片方 0 になるので、割り算の前に避ける。
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
        ' stroke="#666" stroke-width="0.25"/>'
        % (MARGIN + 0.6, top + h / 2 - 1.7),
        '<text x="%g" y="%g" font-family="%s" font-size="2.6"'
        ' fill="black">%s</text>' % (X_FIG + 2, top + h / 2 - 0.3,
                                     S.CAPFONT, escape(base)),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#333">%s</text>'
        % (X_FIG + 2, top + h / 2 + 3.2, S.CAPFONT,
           escape(S._fit(ja, X_NAME - X_FIG - 3, 2.2))),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#ccc" stroke-width="0.15"/>'
        % (X_NAME, top + 0.5, X_NAME, top + h - 0.5),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#999" stroke-width="0.2"/>'
        % (MARGIN, top + h, X_MEMO, top + h),
    ]


def page(parts, n, total, secs):
    head = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm"'
        ' viewBox="0 0 %g %g">' % (PW, PH, PW, PH),
        '<rect width="%g" height="%g" fill="white"/>' % (PW, PH),
        '<g stroke-linecap="round" stroke-linejoin="round">',
        '<text x="%g" y="%g" font-family="%s" font-size="4.4" font-weight="bold"'
        ' fill="black">%s</text>' % (MARGIN, MARGIN + 3.4, S.CAPFONT, escape(TITLE)),
        # **節名はここに並べない。**5節に跨るページがあり、見出しに食い込む。
        # どの節を見ているかは行のあいだの帯が持つ
        '<text x="%g" y="%g" text-anchor="end" font-family="%s" font-size="2.8"'
        ' fill="#555">%s</text>'
        % (X_MEMO, MARGIN + 3.4, S.CAPFONT, escape("%d / %d" % (n, total))),
        '<text x="%g" y="%g" font-family="%s" font-size="2.3" fill="#666">%s</text>'
        % (MARGIN, MARGIN + 7.4, S.CAPFONT, escape(NOTE)),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#333" stroke-width="0.4"/>'
        % (MARGIN, MARGIN + HEAD_H - 1.4, X_MEMO, MARGIN + HEAD_H - 1.4),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#666">%s</text>'
        % (X_FIG + 2, MARGIN + HEAD_H + 1.4, S.CAPFONT, "番号・名称"),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#666">%s</text>'
        % (X_NAME + 2, MARGIN + HEAD_H + 1.4, S.CAPFONT, "気づいたこと"),
    ]
    return "\n".join(head + parts + ['</g></svg>', ''])


def band(ja, top):
    """節の変わり目の帯"""
    return [
        '<rect x="%g" y="%g" width="%g" height="5" fill="#eee"/>'
        % (MARGIN, top, X_MEMO - MARGIN),
        '<text x="%g" y="%g" font-family="%s" font-size="2.9" font-weight="bold"'
        ' fill="black">%s</text>' % (MARGIN + 1.5, top + 3.6, S.CAPFONT, escape(ja)),
    ]


def main():
    d = os.path.join(P.REPO, "docs", "点検表")
    os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):                    # 数が減ったとき古いページを残さない
        if old.endswith(".svg"):
            os.remove(os.path.join(d, old))

    items = rows()
    bottom = PH - MARGIN - FOOT_H
    pages, parts, secs = [], [], []
    y = MARGIN + HEAD_H + 2.4

    cur = ""
    for ja, path in items:
        if ja:
            cur = ja
        _, (x0, y0, x1, y1), _, _ = S.body(path, False)
        h = max(ROW_MIN, (y1 - y0) * MM_PER_UNIT + ROW_PAD)
        show, cont = ja is not None, False
        if y + h + (5.4 if show else 0) > bottom and parts:      # ページを送る
            pages.append((parts, secs))
            parts, secs, y = [], [], MARGIN + HEAD_H + 2.4
            # **送った先で節名を出し直す。** でないと、そのページだけ見たときに
            # どの節を見ているのか分からない
            show, cont = True, ja is None
        if show:
            if cur not in secs:
                secs.append(cur)
            parts += band(cur + ("（つづき）" if cont else ""), y)
            y += 5.4
        parts += row_svg(path, y, h)
        y += h
    if parts:
        pages.append((parts, secs))

    for i, (parts, secs) in enumerate(pages, 1):
        name = os.path.join(d, "%02d.svg" % i)
        open(name, "w", encoding="utf-8").write(
            page(parts, i, len(pages), secs))
        print("  %s  %s" % (os.path.basename(name), "・".join(secs)))

    idx = ["# 点検表\n",
           "記号を使っていて気づいたことを書き留めるための A4 %d枚。" % len(pages),
           "1行が1個で、**☐ ／ 図 ／ 番号・名称 ／ 気づいたこと**。\n",
           "> **この文書は手で書かない。** `py -3 tools/checklist.py` が"
           "`elements/` から作り直す。\n",
           "書き込んだものは [測定メモ.md](測定メモ.md) に写す。"
           "**紙のほうは残さない**（撮った画像もリポジトリに入れない）。\n",
           "| ページ | 載っている節 |", "|---|---|"]
    for i, (_, secs) in enumerate(pages, 1):
        idx.append("| [%02d](点検表/%02d.svg) | %s |" % (i, i, "・".join(secs)))
    out = os.path.join(P.REPO, "docs", "点検表.md")
    open(out, "w", encoding="utf-8").write("\n".join(idx) + "\n")
    print("書き出し:", os.path.relpath(out, P.REPO), "／ %d枚" % len(pages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
