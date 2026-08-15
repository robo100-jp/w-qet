# -*- coding: utf-8 -*-
"""チートシート（`docs/チートシート.svg`）を作る —— 印刷して机上に置く A4 1枚

**`docs/sym/` とは役割が違う。** あちらはぜんぶを1個1枚で出すもの。
こちらは**制御盤でよく使うものだけ**を機能ごとにまとめ、
作図中に手元で番号を引くためのもの。**A4 1枚に収める**。

  py -3 tools/cheatsheet.py

載せるものはこのファイルの `GROUPS` が持つ。**数が増えたら1枚に収まらなくなる**ので、
足すときは何かを落とすこと。「よく使う」から外れたら載せない。
"""
import os
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                           # noqa: E402
import svg_elmt as S                                        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

# A4 縦（mm）。SVG の viewBox を mm に取り、図記号の単位は MM_PER_UNIT で縮める
PW, PH, MARGIN = 210., 297., 9.
MM_PER_UNIT = .25            # 1M（10単位）= 2.5mm。**A4 1枚に収まる上限**
GAPX = 3.0                   # セルの左右の間（mm）
CAPH = 5.6                   # 記号の下のキャプション2行ぶん（mm）

# 見出しと、そこに載せる (図記号番号, 呼び名)。**制御盤でよく使うもの**に絞る。
#
# **呼び名は `<name lang="ja">` をそのまま使わない。** 規格の名称は長く、
# 幅に収めようと切ると「メーク接点（限時開…」が4つ並んで**見分けがつかなくなる**。
# 早見表は読んで選ぶためのものなので、短く・違いが出る言い方にする。
# 正式な名称は docs/sym/index.html と docs/採録状況.md にある。
GROUPS = [
    ("接点", [("07-02-01", "a接点"), ("07-02-03", "b接点"),
             ("07-02-04", "切換え接点"), ("07-02-05", "オフ位置付き切換え")]),
    ("限時接点（タイマ）", [("07-05-01", "a接点 限時閉路"),
                     ("07-05-03", "b接点 限時開路"),
                     ("07-05-02", "a接点 限時開路"),
                     ("07-05-04", "b接点 限時閉路")]),
    ("手動操作", [("07-07-01", "手動操作スイッチ"), ("07-07-02", "押しボタン 自動復帰"),
                ("07-07-04", "ひねり 非自動復帰"), ("07-07-06", "非常停止"),
                ("07-07-05", "押しボタン 確実動作")]),
    ("位置・状態の検出", [("07-08-01", "リミットSW a接点"),
                    ("07-08-02", "リミットSW b接点"),
                    ("07-08-04", "リミットSW 確実開放"),
                    ("07-20-02", "近接スイッチ"),
                    ("07-09-01", "温度スイッチ a接点"),
                    ("07-09-02", "温度スイッチ b接点")]),
    ("開閉装置", [("07-13-02", "電磁接触器 主a接点"), ("07-13-04", "電磁接触器 主b接点"),
                ("07-13-03", "引外し付き接触器"), ("07-13-05", "遮断器"),
                ("07-13-06", "断路器・アイソレータ"), ("07-13-08", "負荷開閉器")]),
    ("保護", [("07-21-01", "ヒューズ"), ("07-21-04", "警報接点付きヒューズ"),
             ("07-21-07", "ヒューズ付き開閉器"), ("07-15-21", "熱動継電器（サーマル）"),
             ("07-17-05", "過電流継電器"), ("07-17-08", "電流継電器")]),
    ("コイル（作動装置）", [("07-15-01", "コイル 一般"), ("07-15-08", "遅緩動作"),
                     ("07-15-07", "遅緩復旧"), ("07-15-09", "遅緩動作・復旧"),
                     ("07-15-11", "交流不感動"), ("07-15-14", "機械的ラッチング")]),
    # 第8部。**始動器（07-14）と入れ替えた。**A4 が埋まっていて、
    # 実際の図面には表示灯とブザーのほうが多く出る（引継ぎ.md の置き換え調査）
    ("表示灯・計器（第8部）", [("08-10-01_green", "表示灯 緑"),
                     ("08-10-01_red", "表示灯 赤"),
                     ("08-10-01_yellow", "表示灯 黄"),
                     ("08-10-01_white", "表示灯 白"),
                     ("08-10-10", "ブザー"),
                     ("08-01-01", "指示計器（中に V・A）")]),
    ("作図用部品（規格外）", [("junction_pass", "通過"), ("junction_tee", "T字分岐"),
                      ("junction_cross", "十字"), ("junction_corner", "L字"),
                      ("wire_end", "終端")]),
]

# 記号の姿だけでは分からない決めごと。**これがあるから1枚で用が足りる**
NOTES = [
    ("端子とグリッド", [
        "グリッド 10 ＝ 規格の作図モジュール 1M。端子間は縦置き機器 60（6M）",
        "作図用部品の端子間は 30。端子は原点に対して対称に置く",
    ]),
    ("ラベルの慣習", [
        "コイルは大文字（R1・T1・M1）、その接点は小文字（r1・t1・m1）",
        "接点のラベルはコイルから自動で同期される。独自表示は text_from=\"UserText\"",
    ]),
    ("QET で引っかかるところ", [
        "導体は端子と端子の間にしか引けない。ジャンクション部品は無いので、",
        "　分岐は同じ端子に2本目の導体をつなぐ（作図用部品は見た目を整えるためのもの）",
        "QET はスタートメニューから起動する。exe を直に叩くと部品が0個になる",
        "記号を回してもラベルは正立のまま。記号の中の文字（Θ・I >）は一緒に倒れる",
    ]),
]

TITLE = "JIS C 0617 図記号 早見表（第7部・第8部）"
# **個数を手で書かない。**記号を足すたびに古くなる（CLAUDE.md）
SUB = ("w-qet — JIS C 0617（＝IEC 60617）を参考に描き起こしたもの。"
       "全%d個の一覧は docs/sym/index.html")


CELL_MAX = 34.               # セル幅の上限（mm）。3個の行が間延びするのを防ぐ


def cell(path, label):
    """1個ぶんの (SVG片, 幅mm, 高さmm, 中心x, 中心y, 番号, 呼び名)"""
    g, (x0, y0, x1, y1), _, _ = S.body(path, False)
    w = (x1 - x0) * MM_PER_UNIT
    h = (y1 - y0) * MM_PER_UNIT
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return g, w, h, cx, cy, os.path.basename(path)[:-5], label


def main():
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm"'
           ' viewBox="0 0 %g %g">' % (PW, PH, PW, PH),
           '<rect width="%g" height="%g" fill="white"/>' % (PW, PH),
           '<g stroke-linecap="round" stroke-linejoin="round" fill="none">']
    y = MARGIN
    out.append('<text x="%g" y="%g" font-family="%s" font-size="5.2"'
               ' font-weight="bold" fill="black">%s</text>'
               % (MARGIN, y + 4, S.CAPFONT, escape(TITLE)))
    y += 6.4
    out.append('<text x="%g" y="%g" font-family="%s" font-size="2.5"'
               ' fill="#555">%s</text>'
               % (MARGIN, y, S.CAPFONT, escape(SUB % len(P.collection()))))
    y += 3.2

    avail = PW - MARGIN * 2
    for title, nums in GROUPS:
        y += 3.0
        out.append('<text x="%g" y="%g" font-family="%s" font-size="3.2"'
                   ' font-weight="bold" fill="black">%s</text>'
                   % (MARGIN, y, S.CAPFONT, escape(title)))
        out.append('<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#bbb"'
                   ' stroke-width="0.2"/>' % (MARGIN, y + 1.1, PW - MARGIN, y + 1.1))
        y += 2.4
        cells = [cell(P.find(n), lab) for n, lab in nums]
        rowh = max(c[2] for c in cells)
        # **セル幅は行いっぱいに割る。** 記号の幅で決めると呼び名を切る余地が無くなり、
        # 「メーク接点（限時開…」のように**隣と見分けが付かなくなる**
        cw = min(CELL_MAX, avail / len(cells))
        cw = max(cw, max(c[1] for c in cells) + GAPX)
        per = max(1, int(avail // cw))
        x = MARGIN
        for k, (g, w, h, cx, cy, base, ja) in enumerate(cells):
            if k and k % per == 0:                   # 収まらなければ折り返す
                x = MARGIN
                y += rowh + CAPH
            # セルの中央に置く。**記号ごとに原点が違う**ので広がりの中心で寄せる
            out.append('<g transform="translate(%g %g) scale(%g) translate(%g %g)"'
                       ' stroke="black">%s</g>'
                       % (x + cw / 2, y + rowh / 2, MM_PER_UNIT, -cx, -cy, g))
            out.append('<text x="%g" y="%g" text-anchor="middle" font-family="%s"'
                       ' font-size="2.3" fill="black">%s</text>'
                       % (x + cw / 2, y + rowh + 2.6, S.CAPFONT, escape(base)))
            out.append('<text x="%g" y="%g" text-anchor="middle" font-family="%s"'
                       ' font-size="2.1" fill="#444">%s</text>'
                       % (x + cw / 2, y + rowh + 5.2, S.CAPFONT,
                          escape(S._fit(ja, cw - 1, 2.1))))
            x += cw
        y += rowh + CAPH

    y += 2.5
    for title, lines in NOTES:
        y += 3.2
        out.append('<text x="%g" y="%g" font-family="%s" font-size="3.0"'
                   ' font-weight="bold" fill="black">%s</text>'
                   % (MARGIN, y, S.CAPFONT, escape(title)))
        y += 1.0
        for ln in lines:
            y += 3.3
            out.append('<text x="%g" y="%g" font-family="%s" font-size="2.5"'
                       ' fill="#222">%s</text>'
                       % (MARGIN + 2, y, S.CAPFONT, escape(ln)))

    out.append('</g></svg>')
    dst = os.path.join(P.REPO, "docs", "チートシート.svg")
    open(dst, "w", encoding="utf-8").write("\n".join(out) + "\n")
    print("書き出し:", os.path.relpath(dst, P.REPO))
    print("使った高さ %.0fmm / %.0fmm" % (y + MARGIN, PH))
    if y + MARGIN > PH:
        print("**A4 に収まっていない。** GROUPS か NOTES を減らすこと")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
