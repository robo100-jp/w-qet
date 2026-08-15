# -*- coding: utf-8 -*-
"""規格票のページから「図の帯」と「作図モジュール M の格子」を取り出す

規格の図には **M のドット格子**が添えられている。これを検出できれば
図形の座標が M 単位で読め、**1M = 10** なので10倍すれば `.elmt` の座標になる。

ライブラリとしても CLI としても使う。

  py -3 tools/stdpage.py 78            # 格子と、図の墨の成分を M で並べる
  py -3 tools/stdpage.py 78 --rows     # 行走査（斜線の折れ点を見る）
  py -3 tools/stdpage.py 78 --png      # 図だけ切り出して保存（リポジトリ外）

**規格票 PDF はリポジトリに入れない。**在りかは `paths.standard()` が解決する。
切り出した画像の出力先も `%TEMP%` 側で、リポジトリには一切書かない。

---

ここは**素朴に書くと必ず外す**ところなので、理由を残しておく。

1. **1目を「隣どうしの差」から決めてはいけない。**
   ドットは図に隠れて飛ぶし、図の小さな部品や表の切れ端がドットに混じる。
   平均も中央値も最頻値もそれに引きずられる。実際、あるページで **1M が半分**に、
   別のページで **7% 大きく**出て、突き合わせが誤検出だらけになった。
   **周期そのものを合わせる**（|Σ exp(2πi x/p)| が最大の p）。欠けても混ざっても効く。

2. **図の帯は「横罫線と横罫線のあいだ」。**
   最初の罫線で切ると、表の見出し行の罫線が図より上にあるので図ごと落ちる。
   ページ内の決め打ちの割合で切ると、背の高い図（14M や 17M）が切れる。
   罫線は連結成分として拾えない（表の枠が全部つながっている）ので、
   **行ごとに暗い画素の連続の長さ**を見る。

3. **帯をドットの数だけで選ばない。**
   説明表の句読点が図のドットより多いページがあり、表のほうを図と取り違えた。
   **格子らしさ（周期のそろい具合）で重みを付ける。**

4. **ドットは「孤立しているか」で判定しない。**
   図に寄ったドットは孤立判定に落ち、そのまま墨に数えられて
   図の外形が上下左右に最大1Mずつ膨らむ。**大きさだけで外す。**

5. **縦横で縮尺が違う。** 図が表のセルに入れられていて同じ比で拡縮されていない。
   実測で最大6%。**列の間隔と行の間隔を別々に測る。**

6. **倍尺のページがある。** 規格票の「概要」に、小さい図記号は2倍に拡大して
   図記号欄に `200 %` と付けると書いてある。**格子のドットは拡大されない**ので、
   図だけがドット2目で1M になる。気づかずに測ると**倍の大きさの記号を作る**。
   `200 %` の文字そのものも墨に数えられて外接矩形が伸びる。
   ここでは PDF の文字から倍率と文字の位置を拾い、`mx`/`my` に掛けて墨から外す。
   （説明欄にも「再設定比は 130 %」のような数字＋%が出るので、**図の帯の中に
   あるものだけ**を倍率と見る。）
"""
import argparse
import math
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(tempfile.gettempdir(), "w-qet-pdf")
DPI = 600


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
                if cx < xa:
                    xa = cx
                if cx > xb:
                    xb = cx
                if cy < ya:
                    ya = cy
                if cy > yb:
                    yb = cy
                for nx, ny in ((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)):
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


def period(v, dpi=DPI):
    """位置の並びから周期と「そろい具合」を返す。(周期px, 0〜1)

    |Σ exp(2πi x/p)| が最大になる p。**隣どうしの差を平均しない**（冒頭 1.）。
    """
    if len(v) < 3:
        return 0.0, 0.0
    lo, hi = 0.16 * dpi, 0.25 * dpi           # 600dpi で 96〜150px
    best, bs, p = 0.0, -1.0, lo
    step = lo / 2000.0
    while p <= hi:
        c = sum(math.cos(2 * math.pi * x / p) for x in v)
        s = sum(math.sin(2 * math.pi * x / p) for x in v)
        m = math.hypot(c, s) / len(v)
        if m > bs:
            best, bs = p, m
        p += step
    return best, bs


class Page(object):
    """規格票の1ページ。図の帯を切り出し、格子と墨の成分を持つ

    属性
      mx, my  1M が何ピクセルか（**縦横で違う**）
      band    図の帯の画像（PIL, グレースケール）
      ink     図形の連結成分 [(x0,y0,x1,y1,画素数)]。ドットは除いてある
      dots    格子のドット
      ok      格子が取れたか。第16節のように格子の無いページは False
      scale   図の倍率。`200 %` と付いたページは 2.0（冒頭 6.）
    """

    def __init__(self, page, part=7, dpi=DPI):
        try:
            import pypdfium2 as pdfium
        except ImportError:
            raise SystemExit("py -3 -m pip install pypdfium2 pillow")
        self.page, self.dpi = page, dpi
        pdf = pdfium.PdfDocument(P.standard(part))
        pg = pdf[page - 1]
        im = pg.render(scale=dpi / 72.0).to_pil().convert("L")
        W0, H0 = im.size
        # 表の外（ページ番号・柱）を落とす。図はこの内側にある
        self.ox, self.oy = int(W0 * 0.20), int(H0 * 0.13)
        self.band = im.crop((self.ox, self.oy, int(W0 * 0.95), int(H0 * 0.62)))
        self._find()
        self._rescale(pg)

    def _find(self):
        W, H = self.band.size
        q = self.band.load()
        m = bytearray(W * H)
        for y in range(H):
            r = y * W
            for x in range(W):
                if q[x, y] < 128:
                    m[r + x] = 1
        # 横罫線（帯の区切り）。**行ごとの連続の長さ**で見る（冒頭 2.）
        rule = []
        for y in range(0, H, 2):
            r, run, best = y * W, 0, 0
            for x in range(W):
                run = run + 1 if m[r + x] else 0
                if run > best:
                    best = run
            if best > 0.5 * W and (not rule or y - rule[-1] > 10):
                rule.append(y)
        comps = components(m, W, H)
        k = self.dpi / 600.0
        cand = [c for c in comps
                if 6 * k <= c[2] - c[0] <= 14 * k and 6 * k <= c[3] - c[1] <= 14 * k
                and abs((c[2] - c[0]) - (c[3] - c[1])) <= 4 * k]
        # 罫線で区切られた区間のうち**格子らしさ×個数**が最大のものが図の帯（冒頭 3.）
        edge = [0] + rule + [H]
        y0, y1, bn = 0, H, -1.0
        for i in range(len(edge) - 1):
            g = [c for c in cand if edge[i] < c[1] < edge[i + 1]]
            if len(g) < 6:
                continue
            _, cx = period([(c[0] + c[2]) / 2 for c in g], self.dpi)
            _, cy = period([(c[1] + c[3]) / 2 for c in g], self.dpi)
            if len(g) * cx * cy > bn:
                y0, y1, bn = edge[i], edge[i + 1], len(g) * cx * cy
        self.rules, self.y0, self.y1 = rule, y0, y1
        self.all = comps                      # 帯ぜんぶ（cell() が使う）
        self.dots = [c for c in cand if y0 <= c[1] and c[3] <= y1]
        # **ドット候補は孤立していなくても墨から外す**（冒頭 4.）
        self.ink = [c for c in comps if y0 <= c[1] and c[3] <= y1
                    and not (c[2] - c[0] <= 14 * k and c[3] - c[1] <= 14 * k)]
        # **格子が無いページがある**（第16節）。そこで拾った「ドット」は
        # 説明表の句読点なので、周期に乗らない。**そろい具合で切る。**
        # 実測: 格子のあるページは縦横とも 1.00、無いページは x が 0.36〜0.48。
        self.fit = (0.0, 0.0)
        if len(self.dots) < 6:
            self.mx = self.my = 0.0
        else:
            self.mx, fx = period([(c[0] + c[2]) / 2 for c in self.dots], self.dpi)
            self.my, fy = period([(c[1] + c[3]) / 2 for c in self.dots], self.dpi)
            self.fit = (fx, fy)
            if min(fx, fy) < 0.9:
                self.mx = self.my = 0.0
        self.ok = bool(self.mx and self.my and self.ink)

    def _rescale(self, pg):
        """倍尺のページを見つけて `mx`/`my` に掛け、`NNN %` の文字を墨から外す

        **図の帯の中にある `NNN %` だけ**を倍率と見る（冒頭 6.）。
        説明欄の「再設定比は 130 %」を拾うと図が 1.3 倍だと誤る。
        """
        self.scale = 1.0
        tp = pg.get_textpage()
        txt = tp.get_text_range()
        k = self.dpi / 72.0
        H = pg.get_size()[1]
        for m in set(re.findall(r"\d+\s*%", txt)):
            s = tp.search(m)
            while True:
                r = s.get_next()
                if not r:
                    break
                i, n = r
                bs = [tp.get_charbox(j) for j in range(i, i + n)]
                x0 = min(b[0] for b in bs) * k - self.ox
                x1 = max(b[2] for b in bs) * k - self.ox
                y0 = (H - max(b[3] for b in bs)) * k - self.oy
                y1 = (H - min(b[1] for b in bs)) * k - self.oy
                if not (self.y0 <= y0 and y1 <= self.y1):
                    continue                       # 図の帯の外＝説明欄の数字
                self.scale = int(re.match(r"\d+", m).group()) / 100.0
                # 倍率の文字そのものを墨から外す。ここを忘れると外接矩形が伸びる
                self.ink = [c for c in self.ink
                            if not (x0 - 4 <= c[0] and c[2] <= x1 + 4
                                    and y0 - 4 <= c[1] and c[3] <= y1 + 4)]
        if self.scale != 1.0:
            # **ドットは拡大されていない。**図だけが2目で1M になっている
            self.mx *= self.scale
            self.my *= self.scale
        self.ok = bool(self.mx and self.my and self.ink)

    # --- 座標 -----------------------------------------------------------
    @property
    def box(self):
        """墨の外接矩形（ピクセル）"""
        return (min(c[0] for c in self.ink), min(c[1] for c in self.ink),
                max(c[2] for c in self.ink), max(c[3] for c in self.ink))

    @property
    def size(self):
        """墨の (幅M, 高さM)。**外形ではなく墨の載っている範囲**"""
        x0, y0, x1, y1 = self.box
        return (x1 - x0) / self.mx, (y1 - y0) / self.my

    def toM(self, x, y):
        """ピクセル → 墨の左上を原点とする M"""
        x0, y0 = self.box[0], self.box[1]
        return (x - x0) / self.mx, (y - y0) / self.my

    def crop(self, margin=0.3):
        """図だけを切り出す。まわりに margin M の余白を付ける"""
        x0, y0, x1, y1 = self.box
        W, H = self.band.size
        return self.band.crop((max(0, int(x0 - margin * self.mx)),
                               max(0, int(y0 - margin * self.my)),
                               min(W, int(x1 + margin * self.mx)),
                               min(H, int(y1 + margin * self.my))))

    def scaled(self, pxm=40.0, margin=0.3):
        """1M = pxm ピクセルにそろえた切り出し。**縦横で別々に伸縮する**（冒頭 5.）"""
        im = self.crop(margin)
        return im.resize((max(1, int(im.size[0] * pxm / self.mx)),
                          max(1, int(im.size[1] * pxm / self.my))))

    def cell(self, maxw=900):
        """**格子が取れないページ**（第16節）の逃げ道。図記号のセルだけ返す

        M が分からないので縮尺は合わせられない。目で見比べるためだけのもの。

        **「上から何本目の罫線」で決めてはいけない。** 表の上端の罫線が帯に
        入るかどうかがページによって違い、1本ずれる（実際にずれた）。
        **いちばん大きな図形が入っている区間**を採る。説明欄は文字しかないので、
        図記号のセルが必ず勝つ。
        """
        W, H = self.band.size
        edge = [0] + list(self.rules) + [H]
        y0, y1, best = self.y0, self.y1, -1
        for i in range(len(edge) - 1):
            a, b = edge[i], edge[i + 1]
            if b - a < 40:
                continue
            big = max([(c[2] - c[0]) * (c[3] - c[1]) for c in self.all
                       if a <= c[1] and c[3] <= b
                       and c[3] - c[1] < 0.7 * (b - a) and c[2] - c[0] < 0.9 * W]
                      or [0])
            if big > best:
                y0, y1, best = a, b, big
        im = self.band.crop((0, y0, W, y1))
        if im.size[0] > maxw:
            k = maxw / float(im.size[0])
            im = im.resize((maxw, max(1, int(im.size[1] * k))))
        return im

    def rows(self, step=0.2):
        """行走査。[(yM, [(x0M,x1M), …]), …]

        **ドットも拾う。**格子の上を通る行では区間にドットが混じる。
        """
        x0, y0, x1, y1 = self.box
        q = self.band.load()
        out = []
        for y in range(y0, y1 + 1, max(1, int(step * self.my))):
            r, s = [], None
            for x in range(x0 - 8, x1 + 8):
                d = q[x, y] < 128
                if d and s is None:
                    s = x
                if not d and s is not None:
                    r.append(((s - x0) / self.mx, (x - x0) / self.mx))
                    s = None
            out.append(((y - y0) / self.my, r))
        return out


def main():
    ap = argparse.ArgumentParser(description="規格票のページを測る")
    ap.add_argument("page", type=int)
    ap.add_argument("--part", type=int, default=7)
    ap.add_argument("--dpi", type=int, default=DPI)
    ap.add_argument("--rows", action="store_true", help="行走査も出す")
    ap.add_argument("--step", type=float, default=0.2, help="行走査の刻み（M）")
    ap.add_argument("--png", action="store_true", help="図を切り出して保存")
    ap.add_argument("-o", "--out", default=OUT)
    a = ap.parse_args()

    p = Page(a.page, a.part, a.dpi)
    if not p.ok:
        print("p.%d 格子が取れない。**第16節のように格子の無いページがある。**"
              "その場合はこの方法では測れないので目視で見比べる" % a.page)
        if a.png:
            os.makedirs(a.out, exist_ok=True)
            q = os.path.join(a.out, "p%04d_帯.png" % a.page)
            p.band.crop((0, p.y0, p.band.size[0], p.y1)).save(q)
            print("切り出し:", q)
        return 1
    w, h = p.size
    print("p.%d  1M = %.2f x %.2f px（縦横のちがい %+.1f%%）  墨 %.2fM x %.2fM"
          % (a.page, p.mx, p.my, 100 * (p.my / p.mx - 1), w, h))
    if p.scale != 1.0:
        print("  **このページの図は %d %% の倍尺。**下の数値は実寸に直してある"
              % int(p.scale * 100))
    print("  1M = 10 なので、下の数値を10倍すれば .elmt の座標になる")
    print()
    print("図形の外接矩形（M。原点は墨の左上）  %d 個" % len(p.ink))
    for c in sorted(p.ink, key=lambda c: (c[1], c[0])):
        ax, ay = p.toM(c[0], c[1])
        bx, by = p.toM(c[2], c[3])
        print("  x %6.2f 〜 %6.2f (%5.2f)   y %6.2f 〜 %6.2f (%5.2f)"
              % (ax, bx, bx - ax, ay, by, by - ay))
    if a.rows:
        print()
        print("行走査（%.2fM 刻み。**格子のドットも混じる**）" % a.step)
        for y, r in p.rows(a.step):
            print("  y %6.2f  %s" % (y, " ".join("%.2f-%.2f" % s for s in r)))
    if a.png:
        os.makedirs(a.out, exist_ok=True)
        q = os.path.join(a.out, "p%04d_図記号.png" % a.page)
        p.crop().save(q)
        print()
        print("切り出し:", q)
    print()
    print("**必ず切り出しを目で見ること。** 連結した図形は1つの塊として出るので、")
    print("折れ点・重なり・線の向きは数値だけでは分からない。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
