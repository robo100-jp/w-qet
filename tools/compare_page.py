# -*- coding: utf-8 -*-
"""描いた記号を規格票と突き合わせる

規格票の図とこちらの記号を**同じ縮尺で**並べ、墨の載っている範囲を数値で出す。

  py -3 tools/compare_page.py 07-02-01 07-02-03    # 画像に並べる
  py -3 tools/compare_page.py --num 07-02-01       # 数値だけ
  py -3 tools/compare_page.py --num --all          # 全件（数分かかる）

**1M = 40px にそろえる。** 規格票は縦横で縮尺が違うので列と行で別々に伸縮させる
（`stdpage.py` 参照）。こちらは `render_elmt.py` が 1単位=4px＝1M=40px で描く。

**出力先は `%TEMP%\\w-qet-pdf\\` で、リポジトリの外。**
並べた画像には規格票の図が入るので、公開リポジトリに置くと再配布になる。

---

## 数値がちがう＝誤り、ではない

出た差は**仕分けてから**直す。順番を間違えると、正しい記号を壊す。

| 仕分け | 見分け方 |
|---|---|
| **測り方の誤り** | まずこれを疑う。`stdpage.py` 冒頭の落とし穴 |
| **決めごとどおり** | 引出し線の長さ（端子間 60）・可動接片の角度。`docs/寸法基準.md` |
| **規格票に図が複数** | 向きちがいを2つ並べているページがある |
| **規格票に格子が無い** | 第16節。この方法では測れない。`—` と出る |
| **本当の誤り** | 上のどれでもないとき |

> 「要修正」と判断した2件が、格子の測り直しで**どちらも正しかった**。

**規格票の説明欄も読む。** 図だけ見ていると落としに気づけない。
補足事項に書いてある部品を描いていなかった例（07-13-12）、
形状分類の「点」を落としていた例（07-15-16）がある。
"""
import argparse
import os
import sys
import tempfile
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402
import stdpage as SP                                       # noqa: E402
import check_elmt as CE                                    # noqa: E402
import render_elmt as RE                                   # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
OUT = os.path.join(tempfile.gettempdir(), "w-qet-pdf")
PXM = 40.0                     # 1M を何ピクセルにそろえるか
CAPTION = 34                   # render_elmt.py が下に付ける説明の高さ
TOL = 0.2                      # これ以上ちがったら疑う（M）
_page = {}


def mine(num):
    """こちらの記号 → (画像, 幅M, 高さM)

    墨の範囲は `.elmt` から出す。描き出した画像には外形枠と端子の印が
    入っているので、画像から測ると外形まで数えてしまう。
    """
    from PIL import Image                                  # noqa: F401
    path = P.find(num)
    im = RE.draw_one(path)
    im = im.crop((0, 0, im.size[0], max(1, im.size[1] - CAPTION)))
    d = ET.parse(path).getroot().find("description")
    pts = []
    for e in (d if d is not None else []):
        if e.tag == "dynamic_text":            # ラベル欄は図形ではない
            continue
        pts += CE.shape_points(e)
    if not pts:
        return im.convert("L"), None, None
    return (im.convert("L"),
            (max(p[0] for p in pts) - min(p[0] for p in pts)) / 10.0,
            (max(p[1] for p in pts) - min(p[1] for p in pts)) / 10.0)


def std(page, part):
    """規格票 → (画像, 幅M, 高さM)。格子が無ければ M は None"""
    key = (page, part)
    if key not in _page:
        _page[key] = SP.Page(page, part)
    p = _page[key]
    if not p.ok:
        return p.cell(), None, None
    w, h = p.size
    return p.scaled(PXM), w, h


def row(num, part, index):
    """1行ぶん → (画像, 説明の文字列, ちがうか)"""
    from PIL import Image, ImageDraw
    if num not in index:
        return None, "%-12s 索引に無い" % num, False
    page = index[num]
    a, aw, ah = std(page, part)
    b, bw, bh = mine(num)
    # 規格票側は線の太さぶん 0.1M ほど大きく出る。それを差し引いて見る
    bad = (None not in (aw, bw, ah, bh)
           and (abs(aw - 0.1 - bw) > TOL or abs(ah - 0.1 - bh) > TOL))

    def fm(v):
        return "—" if v is None else "%.1fM" % v
    line = ("%-10s p.%-4d 規格票 %s×%s  ／  こちら %s×%s%s"
            % (num, page, fm(aw), fm(ah), fm(bw), fm(bh),
               "  ★ちがう" if bad else ("  （格子なし）" if aw is None else "")))
    h = max(a.size[1], b.size[1], 90) + 30
    out = Image.new("L", (max(30 + a.size[0] + b.size[0], 760), h), 255)
    out.paste(a, (10, 26))
    out.paste(b, (20 + a.size[0], 26))
    dr = ImageDraw.Draw(out)
    dr.text((10, 4), line, fill=0, font=RE.font(17))
    dr.line((0, h - 1, out.size[0], h - 1), fill=170)
    return out, line, bad


def main():
    ap = argparse.ArgumentParser(description="記号を規格票と突き合わせる")
    ap.add_argument("names", nargs="*")
    ap.add_argument("--all", action="store_true", help="索引にある番号を全部")
    ap.add_argument("--num", action="store_true", help="数値だけ。画像を作らない")
    ap.add_argument("--part", type=int, default=7)
    ap.add_argument("-o", "--out", default=OUT)
    a = ap.parse_args()

    index = P.index(a.part)
    if not index:
        raise SystemExit("docs/規格データ/第%d部索引.tsv が無い" % a.part)
    names = sorted(index) if a.all else a.names
    if not names:
        raise SystemExit("記号の番号を指定するか --all")

    from PIL import Image
    rows, bad = [], 0
    for n in names:
        try:
            im, line, ng = row(n, a.part, index)
        except FileNotFoundError as e:
            print(" ", n, "—", e)
            continue
        print(" ", line)
        bad += 1 if ng else 0
        if im is not None and not a.num:
            rows.append(im)
    print()
    print("%d 件中 %d 件が %.1fM 以上ちがう。**数値がちがう＝誤りではない。**"
          "上の仕分けに沿って見ること（このファイルの先頭）" % (len(names), bad, TOL))
    if a.num or not rows:
        return 1 if bad else 0
    W = max(r.size[0] for r in rows)
    sheet = Image.new("L", (W, sum(r.size[1] for r in rows)), 255)
    y = 0
    for r in rows:
        sheet.paste(r, (0, y))
        y += r.size[1]
    os.makedirs(a.out, exist_ok=True)
    p = os.path.join(a.out, "突き合わせ_%s.png" % names[0])
    sheet.save(p)
    print("保存:", p, sheet.size)
    print("**リポジトリの外に出している。** 規格票の図が入るので中に置かない")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
