# -*- coding: utf-8 -*-
"""生成した .qet を検証する

  ・部品どうしの重なり／図枠からのはみ出し
  ・導体の端子未指定（＝つながっていない線）
  ・相互参照（コイル⇔接点）の数
  ・線番の一覧
  ・埋め込まれた JIS 図記号番号

使い方:  py -3 check_qet.py [..\\制御盤_一式.qet]
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
QETDIR = os.path.dirname(HERE)
UC = os.path.join(os.environ["APPDATA"], "qelectrotech", "QElectroTech", "elements")
DIRS = [os.path.join(QETDIR, "カスタム部品"), os.path.join(QETDIR, "カスタム端子"), UC]


def boxes():
    """部品定義の外形（width, height, hotspot_x, hotspot_y）"""
    b = {}
    for d in DIRS:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if not fn.endswith(".elmt") or fn in b:
                continue
            t = open(os.path.join(d, fn), encoding="utf-8").read()
            g = dict(re.findall(r'(\w+)="([^"]*)"', re.search(r"<definition[^>]*>", t).group(0)))
            b[fn] = (float(g["width"]), float(g["height"]),
                     float(g["hotspot_x"]), float(g["hotspot_y"]))
    return b


def main(path):
    box = boxes()
    root = ET.parse(path).getroot()
    total_bad = 0
    print(f"検証: {path}\n")
    for d in root.findall("diagram"):
        W = int(d.get("cols")) * int(d.get("colsize"))
        H = int(d.get("rows")) * int(d.get("rowsize"))
        rects, links, miss = [], 0, 0
        for e in d.findall(".//elements/element"):
            fn = e.get("type").split("/")[-1]
            if fn not in box:
                print(f"  ✖ 部品定義が見つからない: {fn}")
                total_bad += 1
                continue
            x, y = float(e.get("x")), float(e.get("y"))
            w, h, hx, hy = box[fn]
            lab = ""
            for ei in e.findall(".//elementInformation"):
                if ei.get("name") == "label":
                    lab = ei.text or ""
            rects.append((x - hx, y - hy, x - hx + w, y - hy + h,
                          fn.replace(".elmt", ""), lab))
            links += len(e.findall(".//link_uuid"))
        nums = defaultdict(int)
        for c in d.findall(".//conductor"):
            if not (c.get("element1") and c.get("terminal1")
                    and c.get("element2") and c.get("terminal2")):
                miss += 1
            nums[c.get("num") or "(無)"] += 1
        bad = []
        for r in rects:
            if r[0] < 0 or r[1] < 0 or r[2] > W or r[3] > H:
                bad.append(f"はみ出し {r[4]} {r[5]}")
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                a, b = rects[i], rects[j]
                ox = min(a[2], b[2]) - max(a[0], b[0])
                oy = min(a[3], b[3]) - max(a[1], b[1])
                if ox > 2 and oy > 2:
                    bad.append(f"重なり {a[4]}{a[5]} × {b[4]}{b[5]} ({ox:.0f}×{oy:.0f})")
        print(f"■ {d.get('title')}   枠 {W}×{H}")
        print(f"   部品 {len(rects)} / 導体 {sum(nums.values())} / 相互参照 {links}")
        print(f"   端子未指定 {miss} 件 / 重なり・はみ出し {len(bad)} 件")
        for x in bad[:15]:
            print("     ", x)
        print(f"   線番: {' '.join(sorted(nums, key=lambda s: (len(s), s)))}\n")
        total_bad += len(bad) + miss
    t = open(path, encoding="utf-8").read()
    jis = sorted(set(re.findall(r"JIS C 0617 / IEC 60617 ([\d\-]+)", t)))
    print(f"埋め込まれた JIS 図記号番号 {len(jis)} 種")
    print("  " + " ".join(jis))
    print("\n" + ("問題なし" if total_bad == 0 else f"★ 要確認 {total_bad} 件"))
    return total_bad


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else os.path.join(QETDIR, "制御盤_一式.qet")
    sys.exit(1 if main(p) else 0)
