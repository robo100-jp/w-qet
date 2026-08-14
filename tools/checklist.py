# -*- coding: utf-8 -*-
"""点検メモ（`docs/点検メモ.md`）を作る —— パソコン上で書き込む表

**チートシートとは役割が違う。** チートシートは作図中に番号を引くためのもので、
よく使う40個しか載せない。こちらは**176個ぜんぶ**を並べて、
使っていて気づいたことを書き留めるためのもの。

  py -3 tools/checklist.py            # docs/点検メモ.md（と図）
  py -3 tools/checklist.py --xlsx     # docs/点検メモ.xlsx も出す（GUI で書く用）
  py -3 tools/checklist.py --print    # 印刷用の A4（docs/点検表/*.svg）も出す

**書き込んだものは作り直しても消えない。**「済」と「気づいたこと」を番号で引き継ぐ。
記号を足したら行が増えるだけ。

**どこから読むか。** `.xlsx` があって `.md` より新しければ Excel から、
そうでなければ `.md` から読む。**どちらから読んだかを必ず表示する。**

> **`.xlsx` は git に入れない**（`.gitignore`）。バイナリなので差分が出ず、
> 2台のPCで別々に書き込むと突き合わせができない。**git に載るのは `.md` のほう。**
> 相手のPCでは `--xlsx` を叩き直せば同じものができる。

> **表の中で `|` を素で書かない**（`.md` のとき）。列の区切りと見分けが付かず行が壊れる。
> 書きたいときは `\\|` とする。

直したら該当行を空に戻す。控えを残したいものは
[docs/測定メモ.md](../docs/測定メモ.md) へ。
"""
import argparse
import os
import re
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import catalog as C                                         # noqa: E402
import paths as P                                           # noqa: E402
import svg_elmt as S                                        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

DOCS = os.path.join(P.REPO, "docs")
SYM = os.path.join(DOCS, "images", "sym")            # 1個ずつの図（.md 用）
MEMO = os.path.join(DOCS, "点検メモ.md")
XLSX = os.path.join(DOCS, "点検メモ.xlsx")
PNG = os.path.join(P.RENDER, "png")                  # Excel に貼る図（git 管理外）

# Excel の列。**番号の列を動かさない。**書き込みを引き継ぐときの手がかり
COLS = [("節", 20), ("図", 15), ("番号", 13), ("名称", 42), ("済", 6),
        ("気づいたこと", 62)]
C_NUM, C_DONE, C_MEMO = 3, 5, 6                      # 1始まり
FONT = "Meiryo"          # 和名を出すので日本語を持つもの。Arial だと豆腐になる

PX_PER_UNIT = .8                # 表の中での図の大きさ
PX_MIN, PX_MAX = 22, 74         # 行が潰れる／伸びすぎるのを防ぐ

SHEET = "点検メモ"

HEAD = """# 点検メモ

記号を使っていて気づいたことを書き留める表。**176個ぜんぶ**が載っている。
番号を引くだけなら [チートシート](チートシート.svg)、
姿を見比べるなら [カタログ](カタログ.md)。

> **この表は作り直しても消えない。** `py -3 tools/checklist.py` は
> 既にある「済」と「気づいたこと」を番号で引き継ぐ。記号を足せば行が増えるだけ。

## ブラウザで書く（おすすめ）

記号の姿を見ながら書けて、**保存するとこの表が直接書き換わる。**
書き出しも取り込みも要らない。止めるのは Ctrl+C。

```bash
py -3 tools/memo_server.py
```

番号・名称で絞れる。「書いた行だけ」で見直せる。保存は Ctrl+S。

## Excel で書く

Excel のほうがよければこちら。**書き込んだあと引数なしで叩き直すと
この表に写る。**

```bash
py -3 tools/checklist.py --xlsx    # docs/点検メモ.xlsx を作る
py -3 tools/checklist.py           # Excel の書き込みをこの表に写す
```

**`.xlsx` は git に入れていない。** バイナリなので差分が出ず、2台のPCで
別々に書き込むと突き合わせができないため。**git に載るのはこの `.md` のほう。**
相手のPCでは `--xlsx` を叩き直せば同じものができる。

`.xlsx` と `.md` の**新しいほうから読む**（どちらから読んだかは実行時に出る）。

## 書き方

- 「済」に `✔` を入れると見たしるしになる。直したら行を空に戻す
- この `.md` を直接書くときは **`|` を素で書かない。** 列の区切りと見分けが
  付かず行が壊れる。`\\|` とする（Excel 側は素の `|` でよい。写すときに逃がす）
- 残しておきたい控えは [測定メモ.md](測定メモ.md) へ

印刷して紙に書きたいときは `py -3 tools/checklist.py --print` で
`docs/点検表/` に A4 が出る。

"""

# --- Excel（--xlsx のときだけ） ---------------------------------------------
#
# **git に入れない。**バイナリで差分が出ず、2台のPCで別々に書き込むと
# 突き合わせができない。載るのは `.md` のほうで、Excel は書くための面。

XL_K = .25               # PNG を Excel に貼るときの縮尺
XL_HMIN, XL_HMAX = 20, 60        # 貼ったあとの高さ（px）の下限・上限
XL_WMAX = 210                    # 幅の上限（px）。横長の記号で列が広がるのを防ぐ

USAGE = [
    ("この表の使い方", True),
    ("", False),
    ("記号を使っていて気づいたことを、黄色の2列に書きます。", False),
    ("", False),
    ("済　　　　　見たしるし。プルダウンから ✔ を選ぶ", False),
    ("気づいたこと　直したいところ・迷ったところを書く", False),
    ("", False),
    ("書いたら閉じて、下を叩くと docs/点検メモ.md に写ります。", False),
    ("git に載るのは .md のほうです（.xlsx はバイナリなので差分が出ません）。", False),
    ("", False),
    ("    py -3 tools/checklist.py", False),
    ("", False),
    ("叩き直しても書き込みは消えません。番号で引き継ぎます。", False),
    ("記号を足したときは行が増えるだけです。", False),
    ("", False),
    ("書き方の例", True),
    ("済 = ✔ ／ 気づいたこと = 「可動接片が規格票より寝ている。07-25-01 と揃える」", False),
    ("直したら、その行を空に戻します。", False),
]


def build_xlsx(items, keep):
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
    import render_elmt as R

    os.makedirs(PNG, exist_ok=True)
    wb = Workbook()

    ws = wb.active
    ws.title = "使い方"
    ws.column_dimensions["A"].width = 96
    for i, (line, bold) in enumerate(USAGE, 1):
        c = ws.cell(row=i, column=1, value=line)
        c.font = Font(name=FONT, size=11, bold=bold)

    ws = wb.create_sheet(SHEET)
    head = Font(name=FONT, size=10, bold=True)
    body = Font(name=FONT, size=10)
    # **書き込む列に色を付ける。**どこを触るのか分からない表は使われない
    fill = PatternFill("solid", fgColor="FFF7CC")
    wrap = Alignment(vertical="center", wrap_text=True)
    mid = Alignment(vertical="center")
    ctr = Alignment(horizontal="center", vertical="center")

    for i, (name, width) in enumerate(COLS, 1):
        c = ws.cell(row=1, column=i, value=name)
        c.font, c.alignment = head, ctr
        ws.column_dimensions[get_column_letter(i)].width = width
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = "A1:%s%d" % (get_column_letter(len(COLS)),
                                      len(items) + 1)

    dv = DataValidation(type="list", formula1='"✔"', allow_blank=True)
    ws.add_data_validation(dv)

    cur, wmax = "", 0
    for r, (ja, path) in enumerate(items, 2):
        if ja:
            cur = ja
        base = os.path.basename(path)[:-5]
        _, _, name, _ = S.body(path, False)
        done, memo = keep.get(base, ("", ""))
        for col, val, al in ((1, cur, mid), (3, base, mid), (4, name, wrap),
                             (5, done, ctr), (6, memo, wrap)):
            c = ws.cell(row=r, column=col, value=val)
            c.font, c.alignment = body, al
            if col in (C_DONE, C_MEMO):
                c.fill = fill
        dv.add(ws.cell(row=r, column=C_DONE))

        png = os.path.join(PNG, base + ".png")
        R.draw_one(path, marks=False, caption=False, pad=8).save(png)
        img = XLImage(png)
        k = XL_K
        if img.height * k > XL_HMAX:
            k = XL_HMAX / img.height
        if img.height * k < XL_HMIN:
            k = XL_HMIN / img.height
        if img.width * k > XL_WMAX:                  # 横長は幅で頭打ちにする
            k = XL_WMAX / img.width
        img.width, img.height = int(img.width * k), int(img.height * k)
        wmax = max(wmax, img.width)
        ws.add_image(img, "B%d" % r)
        ws.row_dimensions[r].height = img.height * .75 + 6   # px → pt

    ws.column_dimensions["B"].width = wmax / 7. + 2
    wb.save(XLSX)
    return len(items)


# --- 印刷用 A4（--print のときだけ） ---------------------------------------
PW, PH, MARGIN = 210., 297., 9.
HEAD_H, FOOT_H = 11., 6.
X_CHK, X_FIG, X_NAME, X_MEMO = 14., 44., 94., PW - MARGIN
MM_PER_UNIT = .20
MAX_K = .38
ROW_MIN, ROW_PAD = 11., 3.
TITLE = "図記号 点検メモ"
NOTE = "気づいたことをその場で書く。直したら docs/点検メモ.md に写す"


def rows():
    """[(節の表示名 or None, パス)] を elements/ の並びのまま返す

    節が変わる行にだけ表示名を入れる（見出しを出す合図）。
    """
    secs = S.sections()
    out, cur = [], None
    for key in sorted(secs):
        ja = C.dirname_ja(os.path.join(P.ELEMENTS, *key.split("/")))
        for p in sorted(secs[key]):
            out.append((ja if ja != cur else None, p))
            cur = ja
    return out


def md_escape(s):
    """表のセルに入れられる形にする

    **Excel には縦棒も改行も素で書ける。** それをそのまま `.md` に流すと
    列が1つ増えて行が壊れ、次に読むときに名称とメモがずれる（実際にやった）。
    書き出す側で必ず逃がす。
    """
    return (s.replace("\\", "\\\\").replace("|", "\\|")
            .replace("\r\n", "<br>").replace("\n", "<br>").replace("\r", "<br>"))


def md_unescape(s):
    return (s.replace("<br>", "\n").replace("\\|", "|").replace("\\\\", "\\"))


def read_memo():
    """既にある点検メモから {番号: (済, 気づいたこと)} を読む

    **手で書き換えられている前提で読む。** 列の幅も空白も揃っていないので、
    番号のセルだけを頼りに引く。読めない行は捨てずに黙って飛ばす
    （消えたら書いた人が困るのは同じだが、壊れた行に引きずられて
    全部を落とすほうが害が大きい）。
    """
    if not os.path.isfile(MEMO):
        return {}
    out = {}
    for line in open(MEMO, encoding="utf-8"):
        if not line.lstrip().startswith("|"):
            continue
        # **`\|` で割らない。** 表の中に縦棒を書けるようにエスケープを勧めておいて
        # ここで素の区切りとして割ると、書いた本人のメモが途中で切れる（実際にやった）
        cells = [c.strip() for c in
                 re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 5:
            continue
        m = re.fullmatch(r"`([0-9A-Za-z_\-]+)`", cells[1])
        if m:
            out[m.group(1)] = (md_unescape(cells[3]), md_unescape(cells[4]))
    return out


def read_xlsx():
    """Excel から {番号: (済, 気づいたこと)} を読む"""
    from openpyxl import load_workbook
    wb = load_workbook(XLSX, data_only=True)
    ws = wb[SHEET] if SHEET in wb.sheetnames else wb.worksheets[0]
    out = {}
    for row in ws.iter_rows(min_row=2, values_only=True):
        if len(row) < C_MEMO or not row[C_NUM - 1]:
            continue
        num = str(row[C_NUM - 1]).strip()
        done = str(row[C_DONE - 1] or "").strip()
        memo = str(row[C_MEMO - 1] or "").strip()
        out[num] = (done, memo)
    return out


def read_notes():
    """書き込みを読む。**どちらから読んだかも返す**

    `.xlsx` があって `.md` より新しければ Excel が勝つ。
    片方だけを直したときに、古いほうで上書きしてしまわないため。
    """
    has_x = os.path.isfile(XLSX)
    has_m = os.path.isfile(MEMO)
    if has_x and (not has_m
                  or os.path.getmtime(XLSX) > os.path.getmtime(MEMO)):
        return read_xlsx(), "点検メモ.xlsx"
    if has_m:
        return read_memo(), "点検メモ.md"
    return {}, "（まだ無い）"


def sym_svg(path):
    """1個ずつの図を書き出して (ファイル名, 表示する高さpx) を返す"""
    base = os.path.basename(path)[:-5]
    _, (x0, y0, x1, y1), _, _ = S.body(path, False)
    open(os.path.join(SYM, base + ".svg"), "w", encoding="utf-8").write(
        S.one(path))
    # **高さ0の記号がある**（07-01-03 は横棒1本）。そのまま使うと表示が潰れる
    h = (y1 - y0) or (x1 - x0)
    return base, max(PX_MIN, min(PX_MAX, int(round(h * PX_PER_UNIT))))


def build_md(items, keep):
    out = [HEAD]
    cur = None
    for ja, path in items:
        if ja and ja != cur:
            cur = ja
            out.append("\n## %s\n" % ja)
            out.append("| 図 | 番号 | 名称 | 済 | 気づいたこと |")
            out.append("|---|---|---|---|---|")
        base, px = sym_svg(path)
        _, _, name, _ = S.body(path, False)
        done, memo = keep.get(base, ("", ""))
        out.append('| <img src="images/sym/%s.svg" height="%d"> | `%s` | %s | %s | %s |'
                   % (base, px, base, md_escape(name),
                      md_escape(done), md_escape(memo)))
    return "\n".join(out) + "\n"


# --- 以下 --print の印刷用 --------------------------------------------------

def row_svg(path, top, h):
    """1行ぶん。**図はセルいっぱいに引き伸ばす**（上限 MAX_K）

    行の高さは記号の実寸で決めるが、図はセルに合わせて拡大する。
    そうしないと 07-01-03（横棒1本）が 4mm に潰れて紙の上で何か分からなくなる。
    横棒・縦棒だけの記号は広がりが片方 0 になるので、割る前に避ける。
    """
    g, (x0, y0, x1, y1), ja, _ = S.body(path, False)
    figw, figh = X_FIG - X_CHK - 4, h - 2
    k = MAX_K
    if x1 - x0 > 0:
        k = min(k, figw / (x1 - x0))
    if y1 - y0 > 0:
        k = min(k, figh / (y1 - y0))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    base = os.path.basename(path)[:-5]
    return [
        '<g transform="translate(%g %g) scale(%g) translate(%g %g)"'
        ' stroke="black" fill="none">%s</g>'
        % ((X_CHK + X_FIG) / 2, top + h / 2, k, -cx, -cy, g),
        '<rect x="%g" y="%g" width="3.4" height="3.4" fill="none"'
        ' stroke="#666" stroke-width="0.25"/>' % (MARGIN + 0.6, top + h / 2 - 1.7),
        '<text x="%g" y="%g" font-family="%s" font-size="2.6" fill="black">%s</text>'
        % (X_FIG + 2, top + h / 2 - 0.3, S.CAPFONT, escape(base)),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#333">%s</text>'
        % (X_FIG + 2, top + h / 2 + 3.2, S.CAPFONT,
           escape(S._fit(ja, X_NAME - X_FIG - 3, 2.2))),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#ccc" stroke-width="0.15"/>'
        % (X_NAME, top + 0.5, X_NAME, top + h - 0.5),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#999" stroke-width="0.2"/>'
        % (MARGIN, top + h, X_MEMO, top + h),
    ]


def band(ja, top):
    return [
        '<rect x="%g" y="%g" width="%g" height="5" fill="#eee"/>'
        % (MARGIN, top, X_MEMO - MARGIN),
        '<text x="%g" y="%g" font-family="%s" font-size="2.9" font-weight="bold"'
        ' fill="black">%s</text>' % (MARGIN + 1.5, top + 3.6, S.CAPFONT, escape(ja)),
    ]


def page(parts, n, total):
    head = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm"'
        ' viewBox="0 0 %g %g">' % (PW, PH, PW, PH),
        '<rect width="%g" height="%g" fill="white"/>' % (PW, PH),
        '<g stroke-linecap="round" stroke-linejoin="round">',
        '<text x="%g" y="%g" font-family="%s" font-size="4.4" font-weight="bold"'
        ' fill="black">%s</text>' % (MARGIN, MARGIN + 3.4, S.CAPFONT, escape(TITLE)),
        # **節名はここに並べない。**5節に跨るページがあり見出しに食い込む。
        # どの節かは行のあいだの帯が持つ
        '<text x="%g" y="%g" text-anchor="end" font-family="%s" font-size="2.8"'
        ' fill="#555">%s</text>'
        % (X_MEMO, MARGIN + 3.4, S.CAPFONT, escape("%d / %d" % (n, total))),
        '<text x="%g" y="%g" font-family="%s" font-size="2.3" fill="#666">%s</text>'
        % (MARGIN, MARGIN + 7.4, S.CAPFONT, escape(NOTE)),
        '<line x1="%g" y1="%g" x2="%g" y2="%g" stroke="#333" stroke-width="0.4"/>'
        % (MARGIN, MARGIN + HEAD_H - 1.4, X_MEMO, MARGIN + HEAD_H - 1.4),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#666">番号・名称</text>'
        % (X_FIG + 2, MARGIN + HEAD_H + 1.4, S.CAPFONT),
        '<text x="%g" y="%g" font-family="%s" font-size="2.2" fill="#666">気づいたこと</text>'
        % (X_NAME + 2, MARGIN + HEAD_H + 1.4, S.CAPFONT),
    ]
    return "\n".join(head + parts + ['</g></svg>', ''])


def build_print(items):
    d = os.path.join(DOCS, "点検表")
    os.makedirs(d, exist_ok=True)
    for old in os.listdir(d):                    # 数が減ったとき古いページを残さない
        if old.endswith(".svg"):
            os.remove(os.path.join(d, old))
    bottom = PH - MARGIN - FOOT_H
    pages, parts = [], []
    y = MARGIN + HEAD_H + 2.4
    cur = ""
    for ja, path in items:
        if ja:
            cur = ja
        _, (_, y0, _, y1), _, _ = S.body(path, False)
        h = max(ROW_MIN, (y1 - y0) * MM_PER_UNIT + ROW_PAD)
        show, cont = ja is not None, False
        if y + h + (5.4 if show else 0) > bottom and parts:
            pages.append(parts)
            parts, y = [], MARGIN + HEAD_H + 2.4
            # **送った先で節名を出し直す。** でないとそのページだけ見たとき
            # どの節を見ているのか分からない
            show, cont = True, ja is None
        if show:
            parts += band(cur + ("（つづき）" if cont else ""), y)
            y += 5.4
        parts += row_svg(path, y, h)
        y += h
    if parts:
        pages.append(parts)
    for i, parts in enumerate(pages, 1):
        open(os.path.join(d, "%02d.svg" % i), "w", encoding="utf-8").write(
            page(parts, i, len(pages)))
    return len(pages)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xlsx", action="store_true",
                    help="Excel も出す（GUI で書く用）")
    ap.add_argument("--print", dest="pr", action="store_true",
                    help="印刷用の A4 も出す")
    a = ap.parse_args()

    os.makedirs(SYM, exist_ok=True)
    items = rows()
    keep, src = read_notes()
    written = sum(1 for v in keep.values() if v[0] or v[1])
    print("読み取り: %s（書き込み %d行）" % (src, written))

    open(MEMO, "w", encoding="utf-8").write(build_md(items, keep))
    print("書き出し: %s  %d行" % (os.path.relpath(MEMO, P.REPO), len(items)))

    # **既にあるなら黙って作り直す。**片方だけ新しい状態を残すと、
    # 次に叩いたとき古いほうから読んで書き込みが消える
    if a.xlsx or os.path.isfile(XLSX):
        build_xlsx(items, keep)
        print("書き出し: %s" % os.path.relpath(XLSX, P.REPO))

    if a.pr:
        n = build_print(items)
        print("印刷用: docs/点検表/  A4 %d枚" % n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
