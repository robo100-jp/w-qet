# -*- coding: utf-8 -*-
"""規格票のページから図記号の形を測る

規格の図には**作図モジュール M のドット格子**が添えられている。
その格子を検出して原点と M を求め、図形の座標を **M 単位**で書き出す。
**1M = 10**（[寸法基準](../docs/寸法基準.md)）なので、出た数値を10倍すれば
そのまま `.elmt` の座標になる。

  py -3 tools/measure_page.py "<規格票>" 20          # p.20 を測る
  py -3 tools/measure_page.py "<規格票>" 20 --scan   # 斜線の追跡も出す

目測を避けるための道具。**ただしこれだけで済ませない。**
必ず `--png` が出す切り出し画像を目で見ること。連結した図形は1つの塊として
出るので、折れ点や重なりは数値だけでは分からない。

出力先はリポジトリの外（`%TEMP%\\w-qet-pdf\\`）。規格票の図は持ち込まない。
"""
import argparse
import math
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(tempfile.gettempdir(), "w-qet-pdf")


def components(dark, W, H):
    """4近傍の連結成分 → [(x0,y0,x1,y1,画素数)]"""
    seen = bytearray(W * H)
    out = []
    for y0 in range(H):
        row = y0 * W
        for x0 in range(W):
            if not dark[row + x0] or seen[row + x0]:
                continue
            st = [(x0, y0)]
            seen[row + x0] = 1
            xa = xb = x0
            ya = yb = y0
            n = 0
            while st:
                cx, cy = st.pop()
                n += 1
                if cx < xa: xa = cx
                if cx > xb: xb = cx
                if cy < ya: ya = cy
                if cy > yb: yb = cy
                for nx, ny in ((cx+1, cy), (cx-1, cy), (cx, cy+1), (cx, cy-1)):
                    if 0 <= nx < W and 0 <= ny < H:
                        i = ny * W + nx
                        if dark[i] and not seen[i]:
                            seen[i] = 1
                            st.append((nx, ny))
            out.append((xa, ya, xb, yb, n))
    return out


def cluster(vals, tol):
    vals = sorted(vals)
    out = [[vals[0]]]
    for v in vals[1:]:
        if v - out[-1][-1] <= tol:
            out[-1].append(v)
        else:
            out.append([v])
    return [sum(g) / len(g) for g in out]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("page", type=int)
    ap.add_argument("--dpi", type=int, default=600)
    ap.add_argument("--scan", action="store_true", help="斜線を1/4M刻みで追跡")
    ap.add_argument("-o", "--out", default=OUT)
    a = ap.parse_args()

    try:
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError:
        raise SystemExit("py -3 -m pip install pypdfium2 pillow")

    pdf = pdfium.PdfDocument(a.pdf)
    im = pdf[a.page - 1].render(scale=a.dpi / 72).to_pil().convert("L")
    W0, H0 = im.size
    # 図記号は表の最初のセル。見出しと下の説明表を外すため、割合で切り出す。
    # （どのページも同じ表組みなので比率で足りる）
    top = im.crop((int(W0 * 0.22), int(H0 * 0.13), int(W0 * 0.92), int(H0 * 0.37)))
    W, H = top.size
    px = top.load()
    dark = bytearray(W * H)
    for y in range(H):
        r = y * W
        for x in range(W):
            if px[x, y] < 128:
                dark[r + x] = 1

    comps = components(dark, W, H)
    lim = max(6, a.dpi // 30)                    # ドットの上限（600dpi で 20px）
    small = [c for c in comps if max(c[2]-c[0], c[3]-c[1]) <= lim]
    if not small:
        raise SystemExit("ドット格子が見つからない。--dpi を変えるか目視で測る")
    # **格子のドットは大きさが均一で、かつ孤立している。**
    # 文字の断片は大きさがばらつき、隣どうしが密着する。両方で絞る。
    from collections import Counter
    sizes = Counter((c[2]-c[0], c[3]-c[1]) for c in small)
    (dw, dh), _ = sizes.most_common(1)[0]
    cand = [c for c in small if abs(c[2]-c[0]-dw) <= 1 and abs(c[3]-c[1]-dh) <= 1]
    cen = [((c[0]+c[2])/2, (c[1]+c[3])/2) for c in comps]
    iso = max(30, a.dpi // 12)              # これより近くに他の塊があれば文字とみなす
    dots = []
    for c in cand:
        cx, cy = (c[0]+c[2])/2, (c[1]+c[3])/2
        near = sum(1 for ox, oy in cen
                   if (ox-cx)**2 + (oy-cy)**2 < iso*iso)
        if near <= 1:                        # 自分だけ＝孤立
            dots.append(c)
    keep = {id(c) for c in dots}
    figs = [c for c in comps if id(c) not in keep
            and max(c[2]-c[0], c[3]-c[1]) > lim]
    if len(dots) < 8:
        raise SystemExit("ドット格子が見つからない（%d 個）。目視で測る" % len(dots))

    tol = a.dpi // 12
    cols = cluster([(c[0]+c[2])/2 for c in dots], tol)
    rows = cluster([(c[1]+c[3])/2 for c in dots], tol)
    # **縦と横で M が違うページがある。** 規格票では図が表のセルに入れられており、
    # 縦横が同じ比で拡縮されていない。横は列の間隔、縦は行の間隔で別々に測る。
    #
    # **1目を「隣どうしの差」から決めてはいけない。** ドットは図に隠れて飛ぶし、
    # 図の小さな部品や表の切れ端がドットに混じる。平均も中央値も最頻値も
    # それに引きずられる（あるページで 1M が半分に、別のページで 7% 大きく出た）。
    # **周期そのものを合わせる。**|Σ exp(2πi x/p)| が最大になる p が1目。
    # ドットが何個か欠けても、余計な点が混ざっても効く。
    def pitch(v):
        lo, hi = 0.16 * a.dpi, 0.25 * a.dpi     # 600dpi で 95〜145px
        best, bs, p = 0.0, -1.0, lo
        while p <= hi:
            c = sum(math.cos(2 * math.pi * x / p) for x in v)
            s = sum(math.sin(2 * math.pi * x / p) for x in v)
            m = math.hypot(c, s) / len(v)
            if m > bs:
                best, bs = p, m
            p += lo / 2000.0
        if bs < 0.5:
            raise SystemExit("ドット格子が格子に見えない。目視で測る")
        return best
    MX, MY = pitch([(c[0]+c[2])/2 for c in dots]), \
        pitch([(c[1]+c[3])/2 for c in dots])
    M = (MX + MY) / 2
    OX, OY = cols[0], rows[0]

    print("p.%d  横 M = %.2f px / 縦 M = %.2f px  格子 %d列 × %d行  原点=左上のドット"
          % (a.page, MX, MY, len(cols), len(rows)))
    if abs(MX - MY) / MY > 0.01:
        print("  ※ 縦横で %.1f%% 違う。図がセルに合わせて歪んでいる。"
              "**縦横それぞれの格子で測っている**ので、下の数値はそのまま使ってよい"
              % (100 * abs(MX - MY) / MY))
    print("  1M = 10 なので、下の数値を10倍すれば .elmt の座標になる")
    print()
    # 図記号は格子の内側にある。外の表罫線や文字は落とす
    lo_x, hi_x = OX - 1.5*MX, OX + (len(cols) + 0.5) * MX
    lo_y, hi_y = OY - 1.5*MY, OY + (len(rows) + 0.5) * MY
    figs = [c for c in figs
            if c[0] >= lo_x and c[2] <= hi_x and c[1] >= lo_y and c[3] <= hi_y]

    print("図形の外接矩形（M 単位）  %d 個" % len(figs))
    for x0, y0, x1, y1, n in sorted(figs, key=lambda c: (c[1], c[0])):
        print("  (%6.2f, %6.2f) - (%6.2f, %6.2f)   画素 %d" %
              ((x0-OX)/MX, (y0-OY)/MY, (x1-OX)/MX, (y1-OY)/MY, n))

    if a.scan:
        print()
        print("横方向の走査（0.25M 刻み。斜線の折れ点を見るため）")
        y = int(OY - MY)
        while y < int(OY + (len(rows)) * MY):
            if 0 <= y < H:
                xs = [x for x in range(W) if dark[y*W + x]]
                runs = []
                if xs:
                    s = pv = xs[0]
                    for v in xs[1:]:
                        if v - pv > 3:
                            runs.append((s, pv)); s = v
                        pv = v
                    runs.append((s, pv))
                big = [r for r in runs if r[1]-r[0] > lim // 2]
                if big:
                    print("  y=%6.2f : %s" % ((y-OY)/MY, "  ".join(
                        "%.2f–%.2f" % ((p-OX)/MX, (q-OX)/MX) for p, q in big)))
            y += max(1, int(MY/4))

    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, "p%04d_図記号.png" % a.page)
    top.crop((int(max(0, OX-2*MX)), int(max(0, OY-2*MY)),
              int(min(W, OX+(len(cols)+2)*MX)), int(min(H, OY+(len(rows)+2)*MY)))).save(p)
    print()
    print("切り出し:", p)
    print("**必ずこの画像を目で見ること。** 連結した図形は1つの塊として出るので、")
    print("折れ点・重なり・線の向きは数値だけでは分からない。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
