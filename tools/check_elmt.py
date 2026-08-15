# -*- coding: utf-8 -*-
"""`.elmt` を機械で点検する

**目視では見つからない誤りを拾うための道具。** `render_elmt.py` の目視は
「形が規格どおりか」を見るもので、外形・端子・属性の不備は絵に出ない。
両方かける。

見るもの

  ・XML として読めるか
  ・外形が10の倍数か（同梱8597個が全部そう。実装側の要求と見てよい）
  ・hotspot が外形の中にあるか／`link_type` が既知の4つか
  ・端子に `uuid` `name` `type="Generic"` `orientation` `x` `y` がそろっているか
  ・端子が外形からはみ出していないか／端子名と端子 uuid の重複
  ・図形（線・矩形・円・弧・多角形・文字）が外形に収まっているか
  ・記号どうしの uuid 重複
  ・`<name lang="ja">` と `en` があるか
  ・ラベルの `keep_visual_rotation="true"`（無いと倒したとき文字まで倒れる）
  ・`JIS_C_0617/` の下は図記号番号が `<informations>` にあり、ファイル名と一致するか
  ・**規格の要素を組み合わせたもの**（ファイル名に `+`）は、番号の行ではなく
    「JIS C 0617 の組合せ A ＋ B」を持ち、組合せ元が実在するか
  ・`JIS_C_0617/` の外に規格の行が紛れ込んでいないか（出所を偽ることになる）

使い方

  py -3 tools/check_elmt.py            # elements/ を全部見る
  py -3 tools/check_elmt.py 07-02-01   # 名前・番号・パスで絞る

問題があれば終了コード 1。
"""
import argparse
import math
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# 文字が外形に収まるかを見るための、字面の測り方。
#
# **表で見積もらず、実際のフォントで測る。**送り幅の表は空白や記号を取りこぼすし、
# 上下の高さは em の割合で当てるしかない。QET が使う Liberation Sans は
# Windows に無いので **Arial** で測る（字幅互換で、字面の高さもほぼ同じ）。
# フォントが見つからないときだけ下の表に落ちる。
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    ImageFont = None
_FCACHE = {}


def text_box(s, pt, italic):
    """(左, 上, 右, 下) をベースライン左端からの単位で返す。取れなければ None"""
    if ImageFont is None or not s:
        return None
    key = (s, pt, italic)
    if key in _FCACHE:
        return _FCACHE[key]
    em, k = pt * 96.0 / 72.0, 20
    try:
        f = ImageFont.truetype("ariali.ttf" if italic else "arial.ttf",
                               int(em * k))
    except Exception:
        _FCACHE[key] = None
        return None
    im = Image.new("L", (int(em * k * (len(s) + 3)), int(em * k * 3)), 0)
    b = int(em * k * 2)
    ImageDraw.Draw(im).text((int(em * k), b), s, fill=255, font=f, anchor="ls")
    bb = im.getbbox()
    r = None if bb is None else ((bb[0] - em * k) / k, (bb[1] - b) / float(k),
                                 (bb[2] - em * k) / k, (bb[3] - b) / float(k))
    _FCACHE[key] = r
    return r


# フォントが読めないときの当て（Liberation Sans の送り幅・em 単位）
ADV = {"I": .278, "U": .722, "P": .667, "Q": .778, "Z": .611, "N": .722,
       "X": .667, "Y": .667, "V": .667, "M": .833, "A": .667, "F": .611,
       "m": .833, "n": .556, "d": .556, "x": .500, "s": .500, "r": .333,
       "a": .556, "v": .500, "e": .556, "t": .278, "i": .222,
       "=": .584, "<": .584, ">": .584, "≈": .584, "%": .889, "*": .389,
       "(": .333, ")": .333, ".": .278, " ": .278, "/": .278, "-": .333,
       "α": .600, "…": 1.0}
for _c in "0123456789":
    ADV[_c] = .556

# QET が解釈する役割。`next_report` / `previous_report` は**フォリオ参照**で、
# ページをまたいだ導体のつながりを QET が自動で書き込む（相互参照と同じ仕組み）。
LINK = ("simple", "master", "slave", "terminal",
        "next_report", "previous_report")
NUM_RE = re.compile(r"JIS C 0617 / IEC 60617 ([0-9A-Za-z\-]+)")

# **規格の要素を組み合わせたもの。**規格が「操作子の限定図記号＋接点」のように
# 組み合わせる建て付けにしているのに、その組合せには番号が振られていない——
# という図記号がある（押しボタン＋ブレーク接点など）。
#
# 番号が無いので `JIS C 0617 / IEC 60617 <番号>` を書いてはいけない
# （status.py が採録として数えてしまうし、無い番号を騙ることになる）。
# 代わりにこの行を書き、**ファイル名は番号を + でつないだもの**にする。
# 探すときは節のフォルダを開くはずなので、置き場所は組合せ元と同じ節。
COMBO_RE = re.compile(r"JIS C 0617 の組合せ ([0-9A-Za-z\-]+(?: ＋ [0-9A-Za-z\-]+)+)")
MARGIN = 0.6           # 線の太さぶんの余裕。これを超えたらはみ出しとみなす


def shape_points(e):
    """図形要素が通る座標。**弧は外接矩形ではなく実際に通る点を出す。**

    弧を外接矩形で見ると、楕円の通らない側まで数えてしまって必ずはみ出す。
    """
    g = e.attrib
    f = lambda k, d=0.0: float(g.get(k, d))                # noqa: E731
    t = e.tag
    if t == "line":
        return [(f("x1"), f("y1")), (f("x2"), f("y2"))]
    if t in ("rect", "ellipse"):
        return [(f("x"), f("y")), (f("x") + f("width"), f("y") + f("height"))]
    if t == "arc":
        cx, cy = f("x") + f("width") / 2, f("y") + f("height") / 2
        rx, ry = f("width") / 2, f("height") / 2
        s, a = f("start"), f("angle", 360)
        return [(cx + rx * math.cos(math.radians(s + a * i / 32.0)),
                 cy - ry * math.sin(math.radians(s + a * i / 32.0)))
                for i in range(33)]
    if t == "polygon":
        out, i = [], 1
        while "x%d" % i in g:
            out.append((f("x%d" % i), f("y%d" % i)))
            i += 1
        return out
    if t == "text":
        # x,y はベースラインの左端
        fo = g.get("font", ",9,")
        m = re.search(r",(\d+),", fo)
        pt = int(m.group(1)) if m else 9
        em = (4.0 / 3.0) * pt                              # Qt: pt × 96/72
        s = g.get("text", "")
        bb = text_box(s, pt, "Italic" in fo)
        if bb:
            return [(f("x") + bb[0], f("y") + bb[1]),
                    (f("x") + bb[2], f("y") + bb[3])]
        adv = sum(ADV.get(c, 0.55) for c in s) * em
        return [(f("x"), f("y") - em * 0.75), (f("x") + adv, f("y") + em * 0.22)]
    return []


def check(path, seen_uuid):
    """1つ見る。見つけた不備を文字列のリストで返す"""
    bad = []
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as ex:
        return ["XML が壊れている: %s" % ex]

    d = root.attrib
    try:
        w, h = int(d["width"]), int(d["height"])
        hx, hy = float(d["hotspot_x"]), float(d["hotspot_y"])
    except (KeyError, ValueError) as ex:
        return ["definition の寸法が読めない: %s" % ex]

    if w % 10 or h % 10:
        bad.append("外形が10の倍数でない: %dx%d" % (w, h))
    # **10×10 は小さすぎる。** QET がプレビュー画像を作れず、部品パネルで
    # 名前がファイル名に化ける（ログに QPainter::begin ... engine == 0 が出る）。
    # 同梱8597個でも 10×10 は4個しかない外れ値。短辺が10でも長辺があれば通る。
    if w <= 10 and h <= 10:
        bad.append("外形が小さすぎる: %dx%d（20x20 以上にする）" % (w, h))
    if not (0 <= hx <= w and 0 <= hy <= h):
        bad.append("hotspot が外形の外: (%g,%g) / %dx%d" % (hx, hy, w, h))
    if d.get("link_type") not in LINK:
        bad.append("link_type が変: %r" % d.get("link_type"))

    u = root.find("uuid")
    if u is None or not u.get("uuid"):
        bad.append("definition の uuid が無い")
    elif u.get("uuid") in seen_uuid:
        bad.append("uuid が %s と重複" % os.path.basename(seen_uuid[u.get("uuid")]))
    else:
        seen_uuid[u.get("uuid")] = path

    langs = {n.get("lang") for n in root.iter("name")}
    for lang in ("ja", "en"):
        if lang not in langs:
            bad.append('<name lang="%s"> が無い' % lang)

    x0, x1, y0, y1 = -hx, w - hx, -hy, h - hy         # 原点は hotspot

    names, tuuid = set(), set()
    for t in root.iter("terminal"):
        a = t.attrib
        for k in ("uuid", "name", "type", "orientation", "x", "y"):
            if not a.get(k):
                bad.append("端子に %s が無い" % k)
        if a.get("orientation") not in ("n", "e", "s", "w"):
            bad.append("端子の向きが変: %r" % a.get("orientation"))
        if a.get("type") != "Generic":
            bad.append("端子の type が Generic でない: %r" % a.get("type"))
        nm = a.get("name")
        if nm in names:
            bad.append("端子名が重複: %s" % nm)
        names.add(nm)
        if a.get("uuid") in tuuid:
            bad.append("端子 uuid が重複")
        tuuid.add(a.get("uuid"))
        tx, ty = float(a.get("x", 0)), float(a.get("y", 0))
        if not (x0 - .01 <= tx <= x1 + .01 and y0 - .01 <= ty <= y1 + .01):
            bad.append("端子 %s が外形の外: (%g,%g) 外形 x[%g,%g] y[%g,%g]"
                       % (nm, tx, ty, x0, x1, y0, y1))
        if tx % 5 or ty % 5:
            bad.append("端子 %s が格子から外れている: (%g,%g)" % (nm, tx, ty))

    desc = root.find("description")
    for e in (desc if desc is not None else []):
        for px, py in shape_points(e):
            if not (x0 - MARGIN <= px <= x1 + MARGIN
                    and y0 - MARGIN <= py <= y1 + MARGIN):
                bad.append("%s が外形からはみ出す: (%g,%g) 外形 x[%g,%g] y[%g,%g]"
                           % (e.tag, px, py, x0, x1, y0, y1))
                break

    # **ラベル（機器記号）は倒しても正立させる。** `keep_visual_rotation="true"`。
    # 規格票の例示値のような `UserText` はここに含めない。あれは記号の中の文字と
    # 同じ扱いで、記号と一緒に倒れてよい（[docs/寸法基準.md]）。
    for dt in root.iter("dynamic_text"):
        if (dt.get("text_from") == "ElementInfo"
                and dt.get("keep_visual_rotation") != "true"):
            bad.append("ラベルの keep_visual_rotation が true でない")

    info = root.findtext("informations") or ""
    base = os.path.basename(path)
    # **ファイル名に日本語を入れない。** QET が中身を読めず、部品パネルで
    # 名前が `<name lang="ja">` ではなくファイル名（拡張子つき）に化ける。
    # フォルダ名も同じ（そちらは qet_directory が読めず名前が空欄になる）。
    nonascii = [c for c in path.replace("\\", "/").split("/elements/")[-1]
                if ord(c) > 127]
    if nonascii:
        bad.append("パスに非ASCIIの文字がある: %s" % "".join(sorted(set(nonascii))))
    if "JIS_C_0617" in path.replace("\\", "/"):
        # **区切りは `__`（アンダースコア2つ）。**`+` は HTTP サーバで
        # エスケープが要るので避ける。`_green` のような修飾は `_` 1つなので
        # 字面で見分けが付く
        if "__" in base:                       # 規格の要素を組み合わせたもの
            m = COMBO_RE.search(info)
            if not m:
                bad.append("組合せなのに informations に「JIS C 0617 の組合せ」が無い")
            elif m.group(1).replace(" ＋ ", "__") != base[:-5]:
                bad.append("ファイル名と組合せの元が食い違う: %s" % m.group(1))
            if NUM_RE.search(info):
                bad.append("組合せに図記号番号の行がある（この組合せに番号は無い）")
            for n in (m.group(1).split(" ＋ ") if m else []):
                try:
                    P.find(n)
                except Exception:
                    bad.append("組合せの元が見つからない: %s" % n)
        else:
            m = NUM_RE.search(info)
            if not m:
                bad.append("informations に図記号番号が無い")
            elif not base.startswith(m.group(1)):
                bad.append("ファイル名と図記号番号が食い違う: %s" % m.group(1))
        if "JIS準拠" in info:
            bad.append("informations に「JIS準拠」がある")
    elif NUM_RE.search(info) or COMBO_RE.search(info):
        bad.append("規格に基づかない部品に規格の行が入っている")
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("names", nargs="*", help="見るもの（省略すると elements/ 全部）")
    a = ap.parse_args()

    paths = [P.find(n) for n in a.names] if a.names else P.collection()
    seen, total = {}, 0
    for p in sorted(paths):
        for msg in check(p, seen):
            print("  %-46s %s" % (os.path.basename(p), msg))
            total += 1

    print("点検 %d 個 —— %s" % (len(paths), "問題なし" if not total else "**%d 件**" % total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
