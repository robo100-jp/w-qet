# -*- coding: utf-8 -*-
"""QElectroTech の部品定義(.elmt) を PNG 画像に描き出す

QETを起動しなくても記号の見た目を確認できるようにするためのツール。
座標を読むだけでは形の誤りに気づけない（ブザーのリード位置を間違えた実例あり）ので、
部品を作ったら必ずこれで描いて目視すること。

円弧の角度の約束（重要）
  QET/Qt : 0度＝3時方向、正の角度＝画面上で反時計回り
  Pillow : 0度＝3時方向、正の角度＝画面上で時計回り
  → 変換は  pil_start = -(qt_start + qt_span),  pil_end = -qt_start

使い方:
  py -3 render_elmt.py 60_直流モーター                  # 1個
  py -3 render_elmt.py 30_a接点 31_b接点 14_ブザー       # 複数を1枚に並べる
  py -3 render_elmt.py --all                            # コレクション全部
出力: qet\_render\ に PNG
"""
import glob
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
QETDIR = os.path.dirname(HERE)
SRCDIRS = [os.path.join(QETDIR, "カスタム部品"),
           os.path.join(QETDIR, "カスタム端子"),
           os.path.join(os.environ["APPDATA"], "qelectrotech", "QElectroTech", "elements")]
OUT = os.path.join(QETDIR, "_render")

S = 4          # 拡大率（1単位=4px）
PAD = 40       # 余白


def find(name):
    if os.path.isfile(name):
        return name
    for d in SRCDIRS:
        p = os.path.join(d, name if name.endswith(".elmt") else name + ".elmt")
        if os.path.isfile(p):
            return p
    raise FileNotFoundError(name)


def font(px):
    for f in ("arial.ttf", "meiryo.ttc", "msgothic.ttc", "YuGothM.ttc"):
        try:
            return ImageFont.truetype(f, px)
        except Exception:
            pass
    return ImageFont.load_default()


def parse(path):
    t = open(path, encoding="utf-8").read()
    d = re.search(r"<description>(.*?)</description>", t, re.S).group(1)
    prims = []
    for m in re.finditer(r"<(line|polygon|arc|ellipse|circle|rect|text)\b[^>]*/>", d):
        prims.append((m.group(1), dict(re.findall(r'(\w[\w-]*)="([^"]*)"', m.group(0)))))
    terms = [(float(x), float(y), o) for x, y, o in
             re.findall(r'<terminal[^>]*x="([-\d.]+)"[^>]*y="([-\d.]+)"[^>]*orientation="(\w)"', t)]
    g = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<definition[^>]*>", t).group(0)))
    nm = re.search(r'<name lang="ja">([^<]*)</name>', t)
    info = re.search(r"<informations>(.*?)</informations>", t, re.S)
    return prims, terms, g, (nm.group(1) if nm else os.path.basename(path)), \
        (info.group(1).strip() if info else "")


def draw_one(path):
    prims, terms, g, ja, info = parse(path)
    W, H = int(g["width"]), int(g["height"])
    hx, hy = float(g["hotspot_x"]), float(g["hotspot_y"])
    # 図形の実際の広がりも入れて画布を決める
    xs, ys = [-hx, W - hx], [-hy, H - hy]
    for tag, a in prims:
        if tag == "line":
            xs += [float(a["x1"]), float(a["x2"])]
            ys += [float(a["y1"]), float(a["y2"])]
        elif tag == "polygon":
            xs += [float(v) for k, v in a.items() if re.fullmatch(r"x\d+", k)]
            ys += [float(v) for k, v in a.items() if re.fullmatch(r"y\d+", k)]
        elif tag in ("arc", "ellipse", "rect"):
            xs += [float(a["x"]), float(a["x"]) + float(a["width"])]
            ys += [float(a["y"]), float(a["y"]) + float(a["height"])]
    for x, y, _ in terms:
        xs.append(x)
        ys.append(y)
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    iw = int((x1 - x0) * S) + PAD * 2
    ih = int((y1 - y0) * S) + PAD * 2 + 34

    im = Image.new("RGB", (iw, ih), "white")
    dr = ImageDraw.Draw(im)

    def P(x, y):
        return ((x - x0) * S + PAD, (y - y0) * S + PAD)

    # 部品の外形枠（薄いグレー）と原点
    dr.rectangle([P(-hx, -hy), P(W - hx, H - hy)], outline=(215, 215, 215))
    dr.line([P(-3, 0), P(3, 0)], fill=(230, 170, 170))
    dr.line([P(0, -3), P(0, 3)], fill=(230, 170, 170))

    for tag, a in prims:
        dashed = "line-style:dashed" in a.get("style", "")
        thin = "line-weight:thin" in a.get("style", "")
        w = 1 if thin else 2
        fillc = None
        mf = re.search(r"filling:(\w+)", a.get("style", ""))
        if mf and mf.group(1) != "none":
            fillc = mf.group(1)
        if tag == "line":
            p1, p2 = P(float(a["x1"]), float(a["y1"])), P(float(a["x2"]), float(a["y2"]))
            if dashed:
                n = 12
                for i in range(n):
                    if i % 2:
                        continue
                    t1, t2 = i / n, (i + 1) / n
                    dr.line([(p1[0] + (p2[0] - p1[0]) * t1, p1[1] + (p2[1] - p1[1]) * t1),
                             (p1[0] + (p2[0] - p1[0]) * t2, p1[1] + (p2[1] - p1[1]) * t2)],
                            fill="black", width=w)
            else:
                dr.line([p1, p2], fill="black", width=w)
        elif tag == "polygon":
            n = len([k for k in a if re.fullmatch(r"x\d+", k)])
            pts = [P(float(a[f"x{i}"]), float(a[f"y{i}"])) for i in range(1, n + 1)]
            if a.get("closed", "true") == "false":
                dr.line(pts, fill="black", width=w)
            else:
                dr.polygon(pts, outline="black", fill=fillc)
        elif tag in ("ellipse", "rect"):
            bb = [P(float(a["x"]), float(a["y"])),
                  P(float(a["x"]) + float(a["width"]), float(a["y"]) + float(a["height"]))]
            if tag == "ellipse":
                dr.ellipse(bb, outline="black", fill=fillc, width=w)
            else:
                dr.rectangle(bb, outline="black", fill=fillc, width=w)
        elif tag == "arc":
            bb = [P(float(a["x"]), float(a["y"])),
                  P(float(a["x"]) + float(a["width"]), float(a["y"]) + float(a["height"]))]
            qs, qa = float(a.get("start", 0)), float(a.get("angle", 360))
            dr.arc(bb, -(qs + qa), -qs, fill="black", width=w)   # Qt→Pillow で向きを反転
        elif tag == "text":
            px = 10
            mfz = re.search(r"[^,]+,(\d+)", a.get("font", ""))
            if mfz:
                px = int(mfz.group(1))
            x, y = P(float(a["x"]), float(a["y"]))
            dr.text((x, y - px * S * 0.78), a.get("text", ""), fill="black", font=font(int(px * S * 0.78)))

    for x, y, o in terms:
        cx, cy = P(x, y)
        dr.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=(200, 60, 60), width=2)
        dr.text((cx + 6, cy - 6), o, fill=(200, 60, 60), font=font(13))

    cap = f"{os.path.basename(path)[:-5]}  {ja}"
    dr.text((6, ih - 30), cap, fill=(30, 30, 30), font=font(15))
    dr.text((6, ih - 14), info.replace("\n", " / ")[:120], fill=(120, 120, 120), font=font(11))
    return im


def main(names):
    os.makedirs(OUT, exist_ok=True)
    ims = []
    for n in names:
        p = find(n)
        im = draw_one(p)
        ims.append(im)
        print(f"  {os.path.basename(p)[:-5]:<26} {im.size[0]}x{im.size[1]}")
    if len(ims) == 1:
        out = os.path.join(OUT, os.path.basename(find(names[0]))[:-5] + ".png")
        ims[0].save(out)
    else:
        cols = min(4, len(ims))
        rows = (len(ims) + cols - 1) // cols
        cw = max(i.size[0] for i in ims)
        ch = max(i.size[1] for i in ims)
        sheet = Image.new("RGB", (cw * cols, ch * rows), "white")
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * cw, (k // cols) * ch))
        out = os.path.join(OUT, "sheet.png")
        sheet.save(out)
    print("出力:", out)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or args[0] == "--all":
        args = sorted(os.path.basename(p)[:-5]
                      for p in glob.glob(os.path.join(QETDIR, "カスタム部品", "*.elmt")))
    main(args)
