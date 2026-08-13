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


def line(x1, y1, x2, y2, end1="none", end2="none", len1=1.5, len2=1.5, weight="normal"):
    st = ("line-style:normal;line-weight:%s;filling:none;color:black" % weight)
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


def term(x, y, ori, name):
    return ('        <terminal x="%g" y="%g" orientation="%s" name="%s" type="Generic"\n'
            '                  uuid="%s"/>' % (x, y, ori, name, _u()))


def _label(w, h):
    """機器記号の置き場所。外形の右上、右端から5離す"""
    return ('        <dynamic_text x="%g" y="%g" z="1" text_width="-1"\n'
            '                      Halignment="AlignLeft" Valignment="AlignTop"\n'
            '                      frame="false" rotation="0" keep_visual_rotation="true"\n'
            '                      text_from="ElementInfo" uuid="%s"\n'
            '                      font="Liberation Sans,9,-1,5,50,0,0,0,0,0,Regular">\n'
            '            <text></text>\n            <info_name>label</info_name>\n'
            '        </dynamic_text>' % (w / 2 + 5, -(h / 2), _u()))


NOTE = "JIS C 0617 を参考に作成。規格の図版を複製したものではない。"
NOTE_QUAL = ("限定図記号。端子を持たない。ほかの図記号に重ねて使う。\n" + NOTE)


def write(path, num, ja, en, w, h, body, terms=(), link="simple",
          label=True, note=None):
    """`.elmt` を書き出す

    num   図記号番号（例 "07-02-01"）。check_qet.py と status.py がこれで判別する
    w, h  外形。10の倍数。hotspot は中央（w/2, h/2）
    link  simple / master / slave / terminal
    label 機器記号の欄を置くか。限定図記号のように端子を持たないものは False
    """
    parts = list(body) + [t for t in terms]
    if label:
        parts.append(_label(w, h))
    info = "JIS C 0617 / IEC 60617 %s\n%s" % (num, note or NOTE)
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<definition width="%d" height="%d" hotspot_x="%d" hotspot_y="%d"\n'
           '            type="element" link_type="%s" version="0.100.0">\n'
           '    <uuid uuid="%s"/>\n'
           '    <names>\n        <name lang="ja">%s</name>\n'
           '        <name lang="en">%s</name>\n    </names>\n'
           '    <informations>%s</informations>\n'
           '    <description>\n%s\n    </description>\n</definition>\n'
           % (w, h, w // 2, h // 2, link, _u(), ja, en, info, "\n".join(parts)))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(xml)
    return path
