# -*- coding: utf-8 -*-
"""`.elmt` を座標から組み立てる

[寸法基準](../docs/寸法基準.md) の約束を既定値として埋め込んである。
**1M = 10**。規格票を測って出た M 単位の数値を10倍すればそのまま渡せる。

  import elmtgen as G
  G.write("elements/JIS_C_0617/07-02_接点/07-02-01_a接点.elmt",
          num="07-02-01", ja="a接点（メーク接点）", en="Make contact",
          w=20, h=60, link="slave",
          body=[G.line(0, -30, 0, -10),
                G.line(-10, -10, 0, 10),
                G.line(0, 10, 0, 30)],
          terms=[G.term(0, -30, "n", "1"), G.term(0, 30, "s", "2")])

`antialias` は自動で決める。水平・垂直・45°の線だけ false（guidelines）。
外形は `w`/`h` をそのまま使い、`hotspot` は中央に置く。
"""
import io
import os
import uuid

SOLID = "line-style:normal;line-weight:normal;filling:%s;color:black"


def _u():
    return "{%s}" % uuid.uuid4()


def _aa(dx, dy):
    """水平・垂直・45°なら false、それ以外は true"""
    if dx == 0 or dy == 0 or abs(abs(dx) - abs(dy)) < 1e-9:
        return "false"
    return "true"


def line(x1, y1, x2, y2, end1="none", end2="none", len1=1.5, len2=1.5,
         weight="normal", dashed=False):
    """`dashed=True` で機械的な結合の破線

    **刻みは指定できない。**QET は Qt のペンをそのまま使うので 4:2 に固定される
    （規格票は 1.0M 刻み）。[docs/寸法基準.md] の「線」を見ること。
    """
    st = ("line-style:%s;line-weight:%s;filling:none;color:black"
          % ("dashed" if dashed else "normal", weight))
    return ('        <line x1="%g" y1="%g" x2="%g" y2="%g" antialias="%s"\n'
            '              style="%s" end1="%s" end2="%s" length1="%g" length2="%g"/>'
            % (x1, y1, x2, y2, _aa(x2 - x1, y2 - y1), st, end1, end2, len1, len2))


def rect(x, y, w, h, fill="none"):
    return ('        <rect x="%g" y="%g" width="%g" height="%g" antialias="false"\n'
            '              style="%s"/>' % (x, y, w, h, SOLID % fill))


def ellipse(x, y, w, h, fill="none"):
    return ('        <ellipse x="%g" y="%g" width="%g" height="%g" antialias="true"\n'
            '                 style="%s"/>' % (x, y, w, h, SOLID % fill))


def arc(x, y, w, h, start, angle):
    """QET の流儀：0度＝3時方向、正の角度＝反時計回り"""
    return ('        <arc x="%g" y="%g" width="%g" height="%g" start="%g" angle="%g"\n'
            '             antialias="true" style="%s"/>' % (x, y, w, h, start, angle, SOLID % "none"))


def polygon(pts, closed=True, fill="none"):
    a = " ".join('x%d="%g" y%d="%g"' % (i, p[0], i, p[1]) for i, p in enumerate(pts, 1))
    c = "" if closed else ' closed="false"'
    return ('        <polygon %s%s antialias="true"\n'
            '                 style="%s"/>' % (a, c, SOLID % fill))


def text(x, y, s, size=9, italic=False):
    """固定の文字。x,y は**ベースラインの左端**

    規格の図に出てくる Θ（温度）のような記号に使う。
    機器記号（ラベル）は別で、write() が dynamic_text を置く。
    """
    f = ("Liberation Sans,%d,-1,5,50,%d,0,0,0,0,%s"
         % (size, 1 if italic else 0, "Italic" if italic else "Regular"))
    # `I >` のような文字を属性に入れる。**エスケープしないとXMLが壊れる。**
    # `>` を素で書くと、タグの終わりと見分けがつかず読み手が途中で切ってしまう。
    e = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    return ('        <text text="%s" x="%g" y="%g" rotation="0"\n'
            '              font="%s" color="#000000"/>' % (e, x, y, f))


def term(x, y, ori, name):
    return ('        <terminal x="%g" y="%g" orientation="%s" name="%s" type="Generic"\n'
            '                  uuid="%s"/>' % (x, y, ori, name, _u()))


def dyntext(x, y, info="label", text="", size=9, halign="AlignLeft",
            valign="AlignTop", keep=True):
    """図面で差し替わる文字

    `info` を渡すと `text_from="ElementInfo"`（機器記号・相互参照）、
    `info=None` なら `text_from="UserText"`（規格票が例として示す値など）。

    **x,y は外接矩形の左上。** `text()`（ベースラインの左端）と意味が違う。
    置き換えるときは `y_上端 = y_ベースライン − 0.905 × em`（[docs/寸法基準.md]）。
    """
    e = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    body = "            <text>%s</text>\n" % e
    if info:
        body += "            <info_name>%s</info_name>\n" % info
    return ('        <dynamic_text x="%g" y="%g" z="1" text_width="-1"\n'
            '                      Halignment="%s" Valignment="%s"\n'
            '                      frame="false" rotation="0" keep_visual_rotation="%s"\n'
            '                      text_from="%s" uuid="%s"\n'
            '                      font="Liberation Sans,%d,-1,5,50,0,0,0,0,0,Regular">\n'
            '%s        </dynamic_text>'
            % (x, y, halign, valign, "true" if keep else "false",
               "ElementInfo" if info else "UserText", _u(), size, body))


def _label(w, h, hx=None):
    """機器記号の置き場所。外形の右上、右端から5離す"""
    right = w / 2 if hx is None else w - hx
    return ('        <dynamic_text x="%g" y="%g" z="1" text_width="-1"\n'
            '                      Halignment="AlignLeft" Valignment="AlignTop"\n'
            '                      frame="false" rotation="0" keep_visual_rotation="true"\n'
            '                      text_from="ElementInfo" uuid="%s"\n'
            '                      font="Liberation Sans,9,-1,5,50,0,0,0,0,0,Regular">\n'
            '            <text></text>\n            <info_name>label</info_name>\n'
            '        </dynamic_text>' % (right + 5, -(h / 2), _u()))


NOTE = "JIS C 0617 を参考に作成。規格の図版を複製したものではない。"
NOTE_QUAL = ("限定図記号。端子を持たない。ほかの図記号に重ねて使う。\n" + NOTE)


def write(path, num, ja, en, w, h, body, terms=(), link="simple",
          label=True, note=None, hx=None, hy=None, combo=None):
    """`.elmt` を書き出す

    num   図記号番号（例 "07-02-01"）。check_qet.py と status.py がこれで判別する。
          **規格に基づかない作図用の部品は `num=None`。**
          そのとき `<informations>` に規格の行を書かない
    combo 規格の要素を**組み合わせた**もの（例 ("07-07-02", "07-07-07")）。
          規格がその組合せに番号を振っていないときに使う。`num` とは併用しない。
          **番号の行を書かない**（無い番号を騙ることになるし、status.py が
          採録として数えてしまう）。置き場所は組合せ元と同じ節のフォルダ、
          ファイル名は番号を **`_`（アンダースコア1つ）**でつないだもの。
          **`__`（2つ）は規格に無いものを足すときの印**なので使い分ける
          （`08-10-01__green` の色は規格外）。`+` は HTTP サーバで
          エスケープが要るので使わない。`check_elmt.py` が照合する
    w, h  外形。10の倍数。hotspot は既定で中央（w/2, h/2）
    hx    hotspot を横にずらす。**図が導体の軸に対して左右非対称のとき**に使う。
          座標の原点から左へ hx、右へ w-hx が外形。既定は w/2（＝中央）
    link  simple / master / slave / terminal
    label 機器記号の欄を置くか。限定図記号のように端子を持たないものは False
    """
    # **外形は10の倍数でなければならない。** 同梱8597個が全部そうなっていて、
    # 実装側の要求と見てよい（[docs/寸法基準.md]）。うっかり半端な値で書き出すと
    # あとで全部直すことになるので、ここで止める。
    if w % 10 or h % 10:
        raise ValueError("外形は10の倍数にする: %s は %dx%d" % (path, w, h))
    hx = w // 2 if hx is None else hx
    hy = h // 2 if hy is None else hy
    parts = list(body) + [t for t in terms]
    if label:
        parts.append(_label(w, h, hx))
    if num and combo:
        raise ValueError("num と combo は併用しない: %s" % path)
    if num:
        info = "JIS C 0617 / IEC 60617 %s\n%s" % (num, note or NOTE)
    elif combo:
        # **番号の行は書かない。**無い番号を騙ることになるし、
        # status.py が採録として数えてしまう
        info = "JIS C 0617 の組合せ %s\n%s" % (" ＋ ".join(combo), note or NOTE)
    else:
        info = note or ""
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<definition width="%d" height="%d" hotspot_x="%d" hotspot_y="%d"\n'
           '            type="element" link_type="%s" version="0.100.0">\n'
           '    <uuid uuid="%s"/>\n'
           '    <names>\n        <name lang="ja">%s</name>\n'
           '        <name lang="en">%s</name>\n    </names>\n'
           '    <informations>%s</informations>\n'
           '    <description>\n%s\n    </description>\n</definition>\n'
           % (w, h, hx, hy, link, _u(), ja, en, info, "\n".join(parts)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(xml)
    return path
