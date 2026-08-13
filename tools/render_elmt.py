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
  py -3 tools/render_elmt.py 60_直流モーター             # 1個（名前でもパスでもよい）
  py -3 tools/render_elmt.py 30_a接点 31_b接点 14_ブザー  # 複数を1枚に並べる
  py -3 tools/render_elmt.py --all                      # elements/ 全部
出力: render/ に PNG

記号の探し方は paths.py に集約してある。どのフォルダから叩いてもよく、
elements/ のどのサブフォルダに置いた記号でも名前だけで見つかる。
"""
import os
import re
import sys

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

OUT = P.RENDER

S = 4          # 拡大率（1単位=4px）
PAD = 40       # 余白


def font(px):
    # 日本語を持つフォントを先に試す。arial を先頭にすると記号名も
    # <text> の日本語も豆腐（□）になる（arial は CJK を持たない）
    for f in ("meiryo.ttc", "YuGothM.ttc", "msgothic.ttc", "arial.ttf"):
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
        tag = m.group(1)
        a = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', m.group(0)))
        if tag == "circle":
            # QET の circle は x,y が外接矩形の左上、径は diameter。
            # （同梱コレクションの円 404 個で確認：左上と解釈すると同心円になる組が
            #   18 組あり、中心と解釈すると 0 組）
            # ellipse に正規化しておけば以降は同じ経路で描ける
            a["width"] = a["height"] = a.get("diameter", "0")
            tag = "ellipse"
        prims.append((tag, a))
    # ラベルの置き場所。<dynamic_text> は自己終了ではないので別に拾う
    dtexts = []
    for m in re.finditer(r"<dynamic_text\b([^>]*)>(.*?)</dynamic_text>", d, re.S):
        a = dict(re.findall(r'(\w[\w-]*)="([^"]*)"', m.group(1)))
        body = m.group(2)
        lit = re.search(r"<text>(.*?)</text>", body, re.S)
        info_name = re.search(r"<info_name>(.*?)</info_name>", body, re.S)
        if a.get("text_from") == "ElementInfo" and info_name:
            show = "[%s]" % info_name.group(1).strip()      # 図面で差し替わる欄
        else:
            show = (lit.group(1).strip() if lit else "") or "[text]"
        dtexts.append((float(a.get("x", 0)), float(a.get("y", 0)), show, a))
    terms = [(float(x), float(y), o) for x, y, o in
             re.findall(r'<terminal[^>]*x="([-\d.]+)"[^>]*y="([-\d.]+)"[^>]*orientation="(\w)"', t)]
    g = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<definition[^>]*>", t).group(0)))
    nm = re.search(r'<name lang="ja">([^<]*)</name>', t)
    info = re.search(r"<informations>(.*?)</informations>", t, re.S)
    return prims, terms, dtexts, g, (nm.group(1) if nm else os.path.basename(path)), \
        (info.group(1).strip() if info else "")


# 線種のパターン（px 単位の 描く/空ける の繰り返し）
PATTERN = {"dashed": (6, 4), "dotted": (2, 3), "dashdotted": (7, 3, 2, 3)}


def dashes(dr, p1, p2, lstyle, w):
    """線種に従って p1→p2 を引く"""
    if w <= 0:
        return
    pat = PATTERN.get(lstyle)
    if not pat:
        dr.line([p1, p2], fill="black", width=w)
        return
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    total = (dx * dx + dy * dy) ** 0.5
    if total == 0:
        return
    pos, i = 0.0, 0
    while pos < total:
        seg = pat[i % len(pat)]
        if i % 2 == 0:                       # 偶数番目が「描く」
            t1, t2 = pos / total, min(pos + seg, total) / total
            dr.line([(p1[0] + dx * t1, p1[1] + dy * t1),
                     (p1[0] + dx * t2, p1[1] + dy * t2)], fill="black", width=w)
        pos += seg
        i += 1


def line_end(dr, tip, other, kind, length, w):
    """線の端末装飾を描く

    QET の partline.cpp の作図に合わせる。tip からの距離 length の線上の点を O、
    2*length の点を A、O から線に直交して ±length の点を B・C とし、
      simple   C→tip→B の折れ線（開いた矢じり）
      triangle B・tip・C を塗った三角
      circle   O を中心とする半径 length の円
      diamond  A・B・tip・C の菱形
    """
    if not kind or kind in ("none", "ncne") or w <= 0:
        return
    L = length * S
    dx, dy = tip[0] - other[0], tip[1] - other[1]
    d = (dx * dx + dy * dy) ** 0.5
    if d == 0 or L <= 0:
        return
    ux, uy = dx / d, dy / d              # other → tip 向きの単位ベクトル
    px, py = -uy, ux                     # その直交
    O = (tip[0] - ux * L, tip[1] - uy * L)
    A = (tip[0] - ux * 2 * L, tip[1] - uy * 2 * L)
    B = (O[0] + px * L, O[1] + py * L)
    C = (O[0] - px * L, O[1] - py * L)
    if kind == "simple":
        dr.line([C, tip, B], fill="black", width=w)
    elif kind == "triangle":
        dr.polygon([B, tip, C], fill="black", outline="black")
    elif kind == "circle":
        dr.ellipse([O[0] - L, O[1] - L, O[0] + L, O[1] + L], outline="black", width=w)
    elif kind == "diamond":
        dr.polygon([A, B, tip, C], fill="black", outline="black")


def draw_one(path):
    prims, terms, dtexts, g, ja, info = parse(path)
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
    for x, y, s, _ in dtexts:               # ラベルが画布からはみ出さないように
        xs += [x, x + 4 * len(s)]
        ys += [y - 4, y + 6]
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
        style = a.get("style", "")
        ms = re.search(r"line-style:(\w+)", style)
        lstyle = ms.group(1) if ms else "normal"
        mw = re.search(r"line-weight:(\w+)", style)
        w = {"thin": 1, "normal": 2, "hight": 4, "eleve": 4, "none": 0}.get(
            mw.group(1) if mw else "normal", 2)
        fillc = None
        mf = re.search(r"filling:(\w+)", style)
        if mf and mf.group(1) != "none":
            fillc = mf.group(1)
        if tag == "line":
            p1, p2 = P(float(a["x1"]), float(a["y1"])), P(float(a["x2"]), float(a["y2"]))
            dashes(dr, p1, p2, lstyle, w)
            # 端末装飾（矢印・丸・菱形）。end1 が (x1,y1) 側、end2 が (x2,y2) 側
            for e, ln, tip, other in ((a.get("end1"), a.get("length1"), p1, p2),
                                      (a.get("end2"), a.get("length2"), p2, p1)):
                line_end(dr, tip, other, e, float(ln or 1.5), w)
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
            # 0.100 は font="Liberation Sans,9,…" で持つ。size="9" は旧形式だが
            # 手書きの .elmt に出てくるので両方拾う
            mfz = re.search(r"[^,]+,([\d.]+)", a.get("font", ""))
            px = float(mfz.group(1)) if mfz else float(a.get("size", 10))
            x, y = P(float(a["x"]), float(a["y"]))
            # `I &gt;` のような実体参照を戻す。&amp; は最後（二重展開を避ける）
            s = (a.get("text", "").replace("&lt;", "<").replace("&gt;", ">")
                 .replace("&quot;", '"').replace("&amp;", "&"))
            dr.text((x, y - px * S * 0.78), s, fill="black", font=font(int(px * S * 0.78)))

    # ラベル欄は青。図形ではないので色で区別する
    for x, y, s, a in dtexts:
        mfz = re.search(r"[^,]+,([\d.]+)", a.get("font", ""))
        px = float(mfz.group(1)) if mfz else 9.0
        cx, cy = P(x, y)
        dr.text((cx, cy), s, fill=(60, 90, 200), font=font(int(px * S * 0.78)))
        dr.line([(cx - 5, cy), (cx + 5, cy)], fill=(160, 180, 230))
        dr.line([(cx, cy - 5), (cx, cy + 5)], fill=(160, 180, 230))

    for x, y, o in terms:
        cx, cy = P(x, y)
        dr.ellipse([cx - 4, cy - 4, cx + 4, cy + 4], outline=(200, 60, 60), width=2)
        dr.text((cx + 6, cy - 6), o, fill=(200, 60, 60), font=font(13))

    cap = f"{os.path.basename(path)[:-5]}  {ja}"
    dr.text((6, ih - 30), cap, fill=(30, 30, 30), font=font(15))
    dr.text((6, ih - 14), info.replace("\n", " / ")[:120], fill=(120, 120, 120), font=font(11))
    return im


def main(names):
    files = [P.find(n) for n in names]        # 先に全部見つけてから描く
    os.makedirs(OUT, exist_ok=True)
    ims = []
    for p in files:
        im = draw_one(p)
        ims.append(im)
        print(f"  {os.path.basename(p)[:-5]:<26} {im.size[0]}x{im.size[1]}")
    if len(ims) == 1:
        out = os.path.join(OUT, os.path.basename(files[0])[:-5] + ".png")
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
        args = P.collection()
        if not args:
            print(f"elements/ に .elmt が1つも無い: {P.ELEMENTS}")
            print("記号の名前かパスを指定してください。")
            sys.exit(1)
    try:
        main(args)
    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
