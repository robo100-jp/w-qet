# -*- coding: utf-8 -*-
"""生成した .qet を検証する

  ・部品どうしの重なり／図枠からのはみ出し
  ・導体の端子未指定（＝つながっていない線）
  ・相互参照（コイル⇔接点）の数
  ・線番の一覧
  ・埋め込まれた JIS 図記号番号

部品定義は **.qet に埋め込まれたものを先に見る**。qetgen.save() は使った .elmt を
.qet の中に丸ごと入れるので、これだけで検証が完結する（記号のフォルダに依存しない）。
埋め込みに無いものだけ、paths.py の探索先からディスク上を探す。

使い方:  py -3 tools/check_qet.py 出力.qet
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def _box(text):
    """<definition> の width/height/hotspot を取り出す"""
    m = re.search(r"<definition[^>]*>", text)
    if not m:
        return None
    g = dict(re.findall(r'(\w+)="([^"]*)"', m.group(0)))
    try:
        return (float(g["width"]), float(g["height"]),
                float(g["hotspot_x"]), float(g["hotspot_y"]))
    except KeyError:
        return None


def embedded_boxes(root):
    """.qet に埋め込まれた部品定義の外形

    <collection><category name="import"><element name="○○.elmt"><definition .../>
    図面上の部品も同じ element というタグ名なので、definition を持つものだけ拾う。
    """
    b = {}
    for e in root.iter("element"):
        d = e.find("definition")
        fn = e.get("name")
        if d is None or not fn or fn in b:
            continue
        try:
            b[fn] = (float(d.get("width")), float(d.get("height")),
                     float(d.get("hotspot_x")), float(d.get("hotspot_y")))
        except (TypeError, ValueError):
            pass
    return b


def disk_box(fname, table, cache):
    """ディスク上の .elmt から外形を読む（見つからなければ None）"""
    if fname not in cache:
        p = table.get(fname)
        cache[fname] = _box(open(p, encoding="utf-8").read()) if p else None
    return cache[fname]


def main(path):
    root = ET.parse(path).getroot()
    box = embedded_boxes(root)
    table, cache = P.table(), {}
    n_embed, n_disk = len(box), 0
    unknown = defaultdict(int)      # 定義が見つからない部品 → 図面上の個数
    total_bad = 0
    print(f"検証: {path}\n")
    for d in root.findall("diagram"):
        W = int(d.get("cols")) * int(d.get("colsize"))
        H = int(d.get("rows")) * int(d.get("rowsize"))
        rects, links, miss = [], 0, 0
        for e in d.findall(".//elements/element"):
            fn = e.get("type").split("/")[-1]
            # 定義が無くても相互参照は数える（数だけは意味があるので落とさない）
            links += len(e.findall(".//link_uuid"))
            if fn not in box:
                b = disk_box(fn, table, cache)
                if b is None:
                    unknown[fn] += 1
                    continue
                box[fn] = b
                n_disk += 1
            x, y = float(e.get("x")), float(e.get("y"))
            w, h, hx, hy = box[fn]
            lab = ""
            for ei in e.findall(".//elementInformation"):
                if ei.get("name") == "label":
                    lab = ei.text or ""
            rects.append((x - hx, y - hy, x - hx + w, y - hy + h,
                          fn.replace(".elmt", ""), lab))
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
    print(f"部品定義: 埋め込み {n_embed} 種 / ディスク {n_disk} 種")
    if unknown:
        # 定義が無いと重なり・はみ出しを一切見られない。素通りさせない
        total_bad += len(unknown)
        print(f"  ✖ 定義が見つからない {len(unknown)} 種"
              f"（この部品は重なり・はみ出しを検証できていない）")
        for fn, n in sorted(unknown.items()):
            print(f"      {fn}  図面上 {n} 個")
        print("    探した場所: " + " / ".join(P.search_dirs()))

    t = open(path, encoding="utf-8").read()
    jis = sorted(set(re.findall(r"JIS C 0617 / IEC 60617 ([\d\-]+)", t)))
    print(f"JIS 図記号番号 {len(jis)} 種")
    print("  " + " ".join(jis))
    print("\n" + ("問題なし" if total_bad == 0 else f"★ 要確認 {total_bad} 件"))
    return total_bad


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        sys.exit(2)
    if not os.path.isfile(sys.argv[1]):
        print(f"ファイルが無い: {sys.argv[1]}")
        sys.exit(2)
    sys.exit(1 if main(sys.argv[1]) else 0)
