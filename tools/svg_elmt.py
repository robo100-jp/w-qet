# -*- coding: utf-8 -*-
"""図記号(.elmt) を SVG に写す —— カタログとチートシートの土台

`render_elmt.py` の PNG は**目視確認のための道具**で、外形枠・原点・端子の印を
一緒に描く。こちらは**人に見せるための姿だけ**を出す。

なぜ SVG か。

  ・テキストなので git の差分が効く（PNG は中身が見えない）
  ・GitHub の Markdown がそのまま表示する
  ・拡大しても崩れない。**印刷用のチートシートに使える**

読み取りは `render_elmt.parse()` を使い回す。**あちらが踏んだ落とし穴
（`circle` の x,y は左上／実体参照を戻す／`font=` と `size=` の両方）を
書き直すと踏み直す。**

使い方:
  py -3 tools/svg_elmt.py 07-02-01                # 1個 → render/07-02-01.svg
  py -3 tools/svg_elmt.py --sheet 07-02-01 07-02-03   # 並べて1枚にする
  py -3 tools/svg_elmt.py --marks 07-02-01            # 端子と外形も描く（確認用）

カタログとチートシートは `catalog.py` `cheatsheet.py` が**ここを呼んで**作る。
このファイルは変換だけを持ち、どの記号をどう並べるかは持たない。
"""
import argparse
import math
import os
import re
import sys
from xml.sax.saxutils import escape, unescape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                           # noqa: E402
import render_elmt as R                                     # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

EM = 4.0 / 3.0        # 1em = ポイント数 × 96/72（Qt が pt を画素に直す比）

# 線の太さ（**図記号の単位**）。render_elmt の px 指定（S=4px/単位）と同じ比に合わせる。
# 目分量で決めると規格票と見比べたときに太さだけずれる。
WEIGHT = {"thin": .25, "normal": .5, "hight": 1., "eleve": 1., "none": 0.}

# 破線の刻み。**Qt のペンそのままの比**（DashLine 4:2）。単位は図記号の単位で、
# 4+2 = 6 = 0.6M。規格票の 1.0M より細かいが、QET が刻みを指定できないので
# 画面と揃うほうを採る（docs/寸法基準.md）。
DASH = {"dashed": "4,2", "dotted": "1,2", "dashdotted": "4,2,1,2"}

# **符号化を明記する。** 和名を持つので、読み手が既定を Shift-JIS と見ると化ける
XMLDECL = '<?xml version="1.0" encoding="UTF-8"?>\n'

FONT = "Liberation Sans,Arial,Helvetica,sans-serif"
CAPFONT = "Meiryo,'Yu Gothic',sans-serif"      # 和名を出すので日本語を持つものを先に


def _style(a):
    """style 属性から (線の太さ, 線種, 塗り) を取り出す"""
    s = a.get("style", "")
    m = re.search(r"line-weight:(\w+)", s)
    w = WEIGHT.get(m.group(1) if m else "normal", .5)
    m = re.search(r"line-style:(\w+)", s)
    dash = DASH.get(m.group(1) if m else "normal")
    m = re.search(r"filling:(\w+)", s)
    fill = m.group(1) if m and m.group(1) != "none" else "none"
    return w, dash, fill


def _pen(w, dash, fill="none"):
    out = ' fill="%s"' % fill
    if w > 0:
        out += ' stroke="currentColor" stroke-width="%g"' % w
        if dash:
            out += ' stroke-dasharray="%s"' % dash
    else:
        out += ' stroke="none"'
    return out


def _arc_path(a, w, dash):
    """QET の弧を SVG のパスにする

    **角度の向きが逆。** QET/Qt は 0度＝3時方向で正が反時計回り（画面上）。
    SVG の sweep フラグは 1 が時計回りなので、**正の angle には sweep=0**。
    y が下向きなので点の式も sin を引く。
    """
    f = lambda k, d=0.: float(a.get(k, d))                  # noqa: E731
    x, y, ww, hh = f("x"), f("y"), f("width"), f("height")
    cx, cy, rx, ry = x + ww / 2, y + hh / 2, ww / 2, hh / 2
    st, an = f("start"), f("angle", 360)
    if rx <= 0 or ry <= 0:
        return ""
    if abs(an) >= 359.9:            # 全周はパスにすると始点と終点が重なって消える
        return ('<ellipse cx="%g" cy="%g" rx="%g" ry="%g"%s/>'
                % (cx, cy, rx, ry, _pen(w, dash)))
    pt = lambda t: (cx + rx * math.cos(math.radians(t)),     # noqa: E731
                    cy - ry * math.sin(math.radians(t)))
    x0, y0 = pt(st)
    x1, y1 = pt(st + an)
    large = 1 if abs(an) > 180 else 0
    sweep = 0 if an > 0 else 1
    return ('<path d="M %g %g A %g %g 0 %d %d %g %g"%s/>'
            % (x0, y0, rx, ry, large, sweep, x1, y1, _pen(w, dash)))


def _line_end(kind, tip, other, length, w):
    """線の端末装飾（矢じり・丸・菱形）。render_elmt の作図と同じ組み立て"""
    if not kind or kind in ("none", "ncne") or w <= 0:
        return ""
    L = length
    dx, dy = tip[0] - other[0], tip[1] - other[1]
    d = math.hypot(dx, dy)
    if d == 0 or L <= 0:
        return ""
    ux, uy = dx / d, dy / d
    px, py = -uy, ux
    O = (tip[0] - ux * L, tip[1] - uy * L)
    A = (tip[0] - ux * 2 * L, tip[1] - uy * 2 * L)
    B = (O[0] + px * L, O[1] + py * L)
    C = (O[0] - px * L, O[1] - py * L)
    fmt = lambda ps: " ".join("%g,%g" % p for p in ps)       # noqa: E731
    if kind == "simple":
        return '<polyline points="%s"%s/>' % (fmt([C, tip, B]), _pen(w, None))
    if kind == "triangle":
        return '<polygon points="%s"%s/>' % (fmt([B, tip, C]),
                                             _pen(w, None, "currentColor"))
    if kind == "circle":
        return ('<circle cx="%g" cy="%g" r="%g"%s/>'
                % (O[0], O[1], L, _pen(w, None)))
    if kind == "diamond":
        return '<polygon points="%s"%s/>' % (fmt([A, B, tip, C]),
                                             _pen(w, None, "currentColor"))
    return ""


def body(path, marks=False):
    """1つぶんの SVG 要素と、その広がり (x0,y0,x1,y1) を返す"""
    prims, terms, dtexts, g, ja, info = R.parse(path)
    W, H = int(g["width"]), int(g["height"])
    hx, hy = float(g["hotspot_x"]), float(g["hotspot_y"])
    out, xs, ys = [], [], []

    def take(*pts):
        for x, y in pts:
            xs.append(x)
            ys.append(y)

    for tag, a in prims:
        f = lambda k, d=0.: float(a.get(k, d))              # noqa: E731
        w, dash, fill = _style(a)
        if tag == "line":
            p1, p2 = (f("x1"), f("y1")), (f("x2"), f("y2"))
            take(p1, p2)
            if w > 0:
                out.append('<line x1="%g" y1="%g" x2="%g" y2="%g"%s/>'
                           % (p1[0], p1[1], p2[0], p2[1], _pen(w, dash)))
            for e, ln, tip, oth in ((a.get("end1"), a.get("length1"), p1, p2),
                                    (a.get("end2"), a.get("length2"), p2, p1)):
                out.append(_line_end(e, tip, oth, float(ln or 1.5), w))
        elif tag == "polygon":
            n = len([k for k in a if re.fullmatch(r"x\d+", k)])
            pts = [(f("x%d" % i), f("y%d" % i)) for i in range(1, n + 1)]
            take(*pts)
            s = " ".join("%g,%g" % p for p in pts)
            t = "polyline" if a.get("closed", "true") == "false" else "polygon"
            out.append('<%s points="%s"%s/>' % (t, s, _pen(w, dash, fill)))
        elif tag == "rect":
            take((f("x"), f("y")), (f("x") + f("width"), f("y") + f("height")))
            out.append('<rect x="%g" y="%g" width="%g" height="%g"%s/>'
                       % (f("x"), f("y"), f("width"), f("height"),
                          _pen(w, dash, fill)))
        elif tag == "ellipse":
            take((f("x"), f("y")), (f("x") + f("width"), f("y") + f("height")))
            out.append('<ellipse cx="%g" cy="%g" rx="%g" ry="%g"%s/>'
                       % (f("x") + f("width") / 2, f("y") + f("height") / 2,
                          f("width") / 2, f("height") / 2, _pen(w, dash, fill)))
        elif tag == "arc":
            # 弧は外接矩形で広がりを取ると通らない側まで数える。32分割で実際の点を見る
            cx, cy = f("x") + f("width") / 2, f("y") + f("height") / 2
            rx, ry = f("width") / 2, f("height") / 2
            st, an = f("start"), f("angle", 360)
            take(*[(cx + rx * math.cos(math.radians(st + an * i / 32.)),
                    cy - ry * math.sin(math.radians(st + an * i / 32.)))
                   for i in range(33)])
            out.append(_arc_path(a, w, dash))
        elif tag == "text":
            m = re.search(r"[^,]+,([\d.]+)", a.get("font", ""))
            pt = float(m.group(1)) if m else float(a.get("size", 9))
            em = pt * EM
            # **`<text>` の x,y はベースラインの左端。** SVG の既定と同じなので
            # そのまま渡してよい（`<dynamic_text>` は外接矩形の左上で意味が違う）
            s = unescape(a.get("text", ""))
            take((f("x"), f("y") - em * .8),
                 (f("x") + em * .6 * max(len(s), 1), f("y") + em * .2))
            it = ' font-style="italic"' if "Italic" in a.get("font", "") else ""
            out.append('<text x="%g" y="%g" font-family="%s" font-size="%g"'
                       ' fill="currentColor"%s>%s</text>'
                       % (f("x"), f("y"), FONT, em, it, escape(s)))

    if marks:
        take((-hx, -hy), (W - hx, H - hy))
        out.insert(0, '<rect x="%g" y="%g" width="%d" height="%d" fill="none"'
                      ' stroke="#d8d8d8" stroke-width="0.4"/>'
                      % (-hx, -hy, W, H))
        for x, y, o in terms:
            out.append('<circle cx="%g" cy="%g" r="1.6" fill="none"'
                       ' stroke="#c04040" stroke-width="0.5"/>' % (x, y))
        for x, y, s, a in dtexts:
            out.append('<text x="%g" y="%g" font-family="%s" font-size="9"'
                       ' fill="#3c5ac8">%s</text>' % (x, y + 7, FONT, escape(s)))
    else:
        # 端子は描かないが、**リード線の先まで入れて広がりを取る。**
        # 入れないと記号ごとに天地が揃わず、並べたとき端子の高さがばらつく
        take(*[(x, y) for x, y, _ in terms])
        # **規格票が「例」として示している値**（`5…10 A` など）は描く。
        # QET に置いたときに既定で出るものなので、落とすと実物と食い違う。
        # ラベル欄（`ElementInfo`）は図面で埋まる空欄なので描かない。
        for x, y, s, a in dtexts:
            if a.get("text_from") != "UserText" or not s:
                continue
            m = re.search(r"[^,]+,([\d.]+)", a.get("font", ""))
            em = (float(m.group(1)) if m else 9.) * EM
            # **`<dynamic_text>` の y は外接矩形の上端。** `<text>`（ベースライン）と
            # 意味が違うので、そのまま渡すと 1em ぶん上にずれる
            base = y + em * .905
            take((x, y), (x + em * .6 * len(s), y + em))
            out.append('<text x="%g" y="%g" font-family="%s" font-size="%g"'
                       ' fill="currentColor">%s</text>'
                       % (x, base, FONT, em, escape(s)))

    if not xs:
        xs, ys = [-hx, W - hx], [-hy, H - hy]
    return "".join(out), (min(xs), min(ys), max(xs), max(ys)), ja, info


def one(path, marks=False, scale=3):
    """1個ぶんの SVG 文書"""
    g, (x0, y0, x1, y1), ja, _ = body(path, marks)
    pad = 3
    w, h = (x1 - x0) + pad * 2, (y1 - y0) + pad * 2
    return (XMLDECL + '<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g"'
            ' width="%g" height="%g" role="img" aria-label="%s">'
            '<g stroke-linecap="round" stroke-linejoin="round">%s</g></svg>\n'
            % (x0 - pad, y0 - pad, w, h, w * scale, h * scale,
               escape(ja), g))


def _fit(s, width, fs):
    """セルの幅に収まるところで切る。**文字数で切ると和名がはみ出して隣とぶつかる**

    和字は約1em、英数は約0.55em。厳密でなくてよいが、
    「14文字」のような文字数固定にすると幅の狭い列で必ず重なる。
    """
    out, used = "", 0.
    for c in s:
        a = fs * (1.0 if ord(c) > 0x2E80 else .55)
        if used + a > width:
            return (out[:-1] + "…") if len(out) > 1 else out
        out, used = out + c, used + a
    return out


def sheet(files, cols=6, scale=2.2, cap=True, gap=10, minw=52):
    """複数を格子に並べた1枚。カタログとチートシートの本体

    **セルの大きさを全体の最大で決めない。** 07-12-06（110×140）のような
    大きい記号が1つあるだけで、a接点（20×60）の周りが余白だらけになる。
    **列の幅は列の最大、行の高さは行の最大**で取る。
    """
    items = [body(p, False) + (os.path.basename(p)[:-5],) for p in files]
    cols = max(1, min(cols, len(items)))
    rows = (len(items) + cols - 1) // cols
    caph = 15 if cap else 0

    cw = [0.] * cols
    rh = [0.] * rows
    for k, (_, (x0, y0, x1, y1), _, _, _) in enumerate(items):
        cw[k % cols] = max(cw[k % cols], x1 - x0 + gap, minw if cap else 0)
        rh[k // cols] = max(rh[k // cols], y1 - y0 + gap)
    cx = [sum(cw[:i]) for i in range(cols + 1)]
    cy = [sum(rh[:i]) + i * caph for i in range(rows + 1)]

    out = []
    for k, (g, (x0, y0, x1, y1), ja, _, base) in enumerate(items):
        c, r = k % cols, k // cols
        # セルの中央に置く。**記号ごとに原点がばらばら**なので広がりの中心で寄せる
        ox = cx[c] + cw[c] / 2 - (x0 + x1) / 2
        oy = cy[r] + rh[r] / 2 - (y0 + y1) / 2
        out.append('<g transform="translate(%g %g)">%s</g>' % (ox, oy, g))
        if cap:
            tx, ty = cx[c] + cw[c] / 2, cy[r] + rh[r] + 1
            out.append('<text x="%g" y="%g" text-anchor="middle"'
                       ' font-family="%s" font-size="5" fill="currentColor">%s</text>'
                       % (tx, ty, CAPFONT, escape(_fit(base, cw[c] - 2, 5))))
            out.append('<text x="%g" y="%g" text-anchor="middle"'
                       ' font-family="%s" font-size="4.6" fill="currentColor"'
                       ' opacity="0.75">%s</text>'
                       % (tx, ty + 6, CAPFONT, escape(_fit(ja, cw[c] - 2, 4.6))))
    W, H = cx[cols], cy[rows]
    return (XMLDECL + '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 %g %g"'
            ' width="%g" height="%g">'
            '<g stroke-linecap="round" stroke-linejoin="round">%s</g></svg>\n'
            % (W, H, W * scale, H * scale, "".join(out)))


def sections():
    """{節フォルダ名: [パス…]} を elements/ の並びのまま返す"""
    out = {}
    for p in P.collection():
        rel = os.path.relpath(p, P.ELEMENTS).replace("\\", "/")
        key = rel.rsplit("/", 1)[0] if "/" in rel else "."
        out.setdefault(key, []).append(p)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*")
    ap.add_argument("--sheet", action="store_true", help="並べて1枚にする")
    ap.add_argument("--marks", action="store_true", help="外形と端子も描く")
    ap.add_argument("--cols", type=int, default=6)
    ap.add_argument("-o", "--out", help="出力先")
    a = ap.parse_args()

    files = [P.find(n) for n in a.names] if a.names else P.collection()
    if not files:
        print("記号が見つからない")
        return 1
    os.makedirs(P.RENDER, exist_ok=True)
    if a.sheet or len(files) > 1:
        out = a.out or os.path.join(P.RENDER, "sheet.svg")
        open(out, "w", encoding="utf-8").write(sheet(sorted(files), cols=a.cols))
    else:
        out = a.out or os.path.join(P.RENDER,
                                    os.path.basename(files[0])[:-5] + ".svg")
        open(out, "w", encoding="utf-8").write(one(files[0], a.marks))
    print("出力:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
