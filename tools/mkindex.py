# -*- coding: utf-8 -*-
"""図記号番号 → 規格票のページ の索引を、規格票そのものから作り直す

**索引を手で作らない。** 手で作ったせいで、第7部の索引が附属書A の途中で
切れていて **19個を丸ごと見落としていた**（07-A11・07-A12・07-A13・07-A15）。
`status.py` は索引を分母にするので、**採録率が 161/161 と嘘をついていた。**

  py -3 tools/mkindex.py --part 7            # 突き合わせるだけ（既定）
  py -3 tools/mkindex.py --part 7 --write    # docs/第7部索引.tsv を作り直す

**規格票 PDF が要る**（家PCのみ）。索引そのものはリポジトリに入っているので、
会社PCでは作り直せないが読める。

---

拾い方に落とし穴がある。

- **「図記号番号」という語だけでページを選ばない。** 巻頭の表1（項目名の説明）にも
  この語と図記号番号が出る。実際 07-01-01 が p.7 と誤判定された
- **番号のすぐ後ろに識別番号（S00227）が続くページだけ**を図記号のページとみなす。
  この形は図記号の欄にしか出ない
- 巻末の「注釈」の節にも図記号番号がずらりと並ぶが、そちらは
  「図記号番号」の見出しを持たない
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                           # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")


def scan(part):
    """規格票 → [(番号, 節, 分類, ページ)]"""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise SystemExit("py -3 -m pip install pypdfium2")
    d = pdfium.PdfDocument(P.standard(part))
    out, seen = [], set()
    for i in range(len(d)):
        t = re.sub(r"\s+", " ", d[i].get_textpage().get_text_range())
        if "図記号番号" not in t:
            continue
        m = re.search(r"\b(%02d-([A-Z]?)\d+-\d+)\s*（S\d{5}）" % part, t)
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        # **節は番号から切り出す。**`07-A1-04` → `07-A1`。
        # 数字を0詰めすると `07-A01` になり、記号のファイル名と食い違う
        sec = m.group(1).rsplit("-", 1)[0]
        h = re.search(r"第\s*[0-9A-Z]+\s*節\s*(.+?)\s*図記号番号", t)
        name = h.group(1) if h else ""
        # **附属書A は「旧図記号・」を頭に付ける。**新しい図面には使わないものだと
        # 部品パネルでも一覧でも一目で分かるようにするため
        if m.group(2):
            name = "旧図記号・" + name
        out.append((m.group(1), sec, name, i + 1, title(d, i)))
    return out


def title(d, i):
    """その図記号の日本語の名称

    **説明の表が次のページに回っていることがある。**図が大きくて1ページを
    使い切る例（07-A11-01・07-A11-02）がそれで、同じページだけ見ると空になる。
    """
    for k in (i, i + 1):
        if k >= len(d):
            break
        t = re.sub(r"\s+", " ", d[k].get_textpage().get_text_range())
        m = re.search(r"名称 (.+?) 別の名称", t)
        if not m:
            continue
        # 和名のうしろに英名が続く。**最初の ASCII 語から後ろを捨てる**
        return re.split(r"\s(?=[A-Za-z][A-Za-z\-])", m.group(1))[0].strip()
    return ""


def load(part):
    p = os.path.join(P.REPO, "docs", "第%d部索引.tsv" % part)
    rows = []
    if os.path.isfile(p):
        for line in io.open(p, encoding="utf-8"):
            line = line.rstrip("\n")
            if not line or line.startswith("#") or line.startswith("番号\t"):
                continue
            f = line.split("\t")
            rows.append((f[0], f[1], f[2], int(f[3]),
                         f[4] if len(f) > 4 else ""))
    return p, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--part", type=int, default=7)
    ap.add_argument("--write", action="store_true", help="索引を作り直す")
    a = ap.parse_args()

    got = scan(a.part)
    p, old = load(a.part)
    go, oo = {r[0]: r for r in got}, {r[0]: r for r in old}
    miss = sorted(set(go) - set(oo))
    extra = sorted(set(oo) - set(go))
    page = sorted(n for n in set(go) & set(oo) if go[n][3] != oo[n][3])
    print("第%d部  規格票 %d 個 / 索引 %d 個" % (a.part, len(got), len(old)))
    for label, ns in (("索引に無い", miss), ("規格票に無い", extra),
                      ("ページ違い", page)):
        if ns:
            print("  %s %d 個: %s" % (label, len(ns), " ".join(ns)))
    if a.write:
        io.open(p, "w", encoding="utf-8", newline="\n").write(
            "番号\t節\t分類\tページ\t名称\n"
            + "".join("%s\t%s\t%s\t%d\t%s\n" % r for r in got))
        print("書き出し:", os.path.relpath(p, P.REPO))
        return 0
    if miss or extra or page:
        print("**索引が規格票と合っていない。**--write で作り直す")
        return 1
    print("索引は規格票と合っている")
    return 0


if __name__ == "__main__":
    sys.exit(main())
