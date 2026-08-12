# -*- coding: utf-8 -*-
"""PDF のページを画像に描き出す

規格票（JIS C 0617）の図を見ながら記号を描き起こすための道具。
記号を描くのは Claude Code なので、規格の図が**画像として**読めないと始まらない。
テキスト抽出では図が取れないため、ページを丸ごとラスタライズする。

  py -3 tools/pdf_page.py 規格.pdf 42          # 42ページ目
  py -3 tools/pdf_page.py 規格.pdf 42-45       # 範囲
  py -3 tools/pdf_page.py 規格.pdf 42 --dpi 300
  py -3 tools/pdf_page.py 規格.pdf --search "07-02"   # 文字列を含むページを探す

必要: py -3 -m pip install pypdfium2

  描画には pypdfium2（BSD-3-Clause / Apache-2.0）を使う。
  PyMuPDF のほうが手軽だが **AGPL-3.0** で、公開リポジトリに置くツールが
  強い copyleft の義務を負う。このプロジェクトは上流の CC-BY を避けて
  記号を描き起こしている以上、依存側で義務を拾っては意味がない。

出力先について（重要）
  既定の出力先は **リポジトリの外**（%TEMP%\\w-qet-pdf\\）。
  規格票の図はこのリポジトリに入れてはいけない。公開リポジトリなので、
  入れた時点で著作物を再配布することになる。既定を外に置いて事故を防いでいる。
  規格票の PDF 自体もリポジトリに置かないこと。
"""
import argparse
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")

OUT = os.path.join(tempfile.gettempdir(), "w-qet-pdf")   # リポジトリの外


def pages(spec, n):
    """"42" や "42-45" をページ番号（1始まり）の一覧にする"""
    out = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    bad = [p for p in out if not 1 <= p <= n]
    if bad:
        raise SystemExit(f"ページ番号が範囲外: {bad}（この PDF は 1〜{n} ページ）")
    return out


def page_text(pdf, i):
    """0始まりのページ番号 i のテキスト"""
    tp = pdf[i].get_textpage()
    try:
        return tp.get_text_range() or ""
    finally:
        tp.close()


def search(pdf, needle):
    """文字列を含むページを探す。図記号番号から目的のページに当たるため"""
    hits = []
    for i in range(len(pdf)):
        t = page_text(pdf, i)
        if needle in t:
            line = next((l.strip() for l in t.splitlines() if needle in l), "")
            hits.append((i + 1, line[:70]))
    return hits


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("pdf")
    ap.add_argument("pages", nargs="?", help='"42" / "42-45" / "3,7,9"')
    ap.add_argument("--dpi", type=int, default=200, help="既定 200。図が細かいときは上げる")
    ap.add_argument("--search", help="この文字列を含むページを一覧する（描き出しはしない）")
    ap.add_argument("-o", "--out", default=OUT, help=f"出力先（既定 {OUT}）")
    a = ap.parse_args()

    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise SystemExit("pypdfium2 が要る:  py -3 -m pip install pypdfium2")

    if not os.path.isfile(a.pdf):
        raise SystemExit(f"PDF が無い: {a.pdf}")
    pdf = pdfium.PdfDocument(a.pdf)
    print(f"{os.path.basename(a.pdf)}  {len(pdf)} ページ")

    if a.search:
        hits = search(pdf, a.search)
        print(f'"{a.search}" を含むページ {len(hits)} 件')
        for i, line in hits[:40]:
            print(f"  p.{i:<5} {line}")
        return 0

    if not a.pages:
        raise SystemExit("ページ番号か --search を指定すること")

    os.makedirs(a.out, exist_ok=True)
    stem = os.path.splitext(os.path.basename(a.pdf))[0]
    for p in pages(a.pages, len(pdf)):
        im = pdf[p - 1].render(scale=a.dpi / 72).to_pil()
        path = os.path.join(a.out, f"{stem}_p{p:04d}.png")
        im.save(path)
        print(f"  p.{p:<5} {im.width}x{im.height}  {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
