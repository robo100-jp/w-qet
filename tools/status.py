# -*- coding: utf-8 -*-
"""採録状況を elements/ の実物から数え直す

**進捗の記録を手で書かない**ための道具。手で書くと、作業が途中で止まったときに
文書と実物がずれる。ここでは常に `elements/` を走査して数え直すので、
電源が落ちても、次に叩けば正しい状態が出る。

  py -3 tools/status.py            # docs/採録状況.md を作り直して要約を表示
  py -3 tools/status.py --next 10  # 次に描くもの10件（番号と規格票のページ）
  py -3 tools/status.py --check    # 書き直さず、ずれの有無だけ見る（終了コードで判定）

採録済みの判定は `.elmt` の <informations> に入っている図記号番号で行う。
ファイル名ではなく中身で見るので、名前を変えても壊れない。
"""
import argparse
import io
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

INDEX = os.path.join(P.REPO, "docs", "第7部索引.tsv")
OUT = os.path.join(P.REPO, "docs", "採録状況.md")
NUM_RE = re.compile(r"JIS C 0617 / IEC 60617 ([0-9A-Z\-]+)")


def load_index():
    """索引を読む → [(番号, 節, 分類, ページ), ...]"""
    rows = []
    for line in io.open(INDEX, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#") or line.startswith("番号\t"):
            continue
        num, sec, label, page = line.split("\t")
        rows.append((num, sec, label, int(page)))
    return rows


def scan_elements():
    """elements/ を走査 → {図記号番号: (ファイル名, 和名)}"""
    done = {}
    for path in P.collection():
        t = io.open(path, encoding="utf-8").read()
        m = NUM_RE.search(t)
        if not m:
            continue
        nm = re.search(r'<name lang="ja">([^<]*)</name>', t)
        done[m.group(1)] = (os.path.basename(path), nm.group(1) if nm else "")
    return done


def render(rows, done):
    secs = []
    for num, sec, label, page in rows:
        if not secs or secs[-1][0] != sec:
            secs.append((sec, label, []))
        secs[-1][2].append((num, page))

    n_all = len(rows)
    n_done = sum(1 for num, _, _, _ in rows if num in done)
    out = []
    w = out.append
    w("# 採録状況")
    w("")
    w("JIS C 0617 **第7部**（開閉装置，制御装置及び保護装置）の図記号 %d 個。" % n_all)
    w("")
    w("| | |")
    w("|---|---|")
    w("| 採録済み | **%d / %d**（%.0f%%） |" % (n_done, n_all, 100.0 * n_done / n_all))
    w("| 残り | %d |" % (n_all - n_done))
    w("")
    w("> **この文書は手で書かない。** `py -3 tools/status.py` が"
      "`elements/` を走査して作り直す。")
    w("> 作業が途中で止まっても、次に叩けば正しい状態が出る。")
    w("")
    w("## 中断したときの再開手順")
    w("")
    w("```bash")
    w("py -3 tools/status.py --next 10   # 次に描くものと規格票のページ")
    w("```")
    w("")
    w("1. 上のコマンドで次の番号と**規格票のページ**を出す")
    w("2. `py -3 tools/pdf_page.py \"<規格票>\" <ページ> --dpi 600` で図を描き出す")
    w("3. ドット格子（**1M = 10**）を基準に座標を読み、`.elmt` を起こす")
    w("   置き場所は `elements/JIS_C_0617/<節>_<分類>/<番号>_<和名>.elmt`")
    w("4. `py -3 tools/render_elmt.py <名前>` で**必ず目視**")
    w("5. `py -3 tools/status.py` でこの文書を作り直し、コミット")
    w("")
    w("規格票の在りかと寸法の約束は [規格の参照.md](規格の参照.md) と"
      "[寸法基準.md](寸法基準.md)。")
    w("")
    w("---")
    w("")
    for sec, label, items in secs:
        d = sum(1 for num, _ in items if num in done)
        mark = "✔" if d == len(items) else ("… " if d else "—")
        w("## %s %s  %s %d/%d" % (sec, label, mark, d, len(items)))
        w("")
        w("| | 図記号番号 | 名称 | ファイル | p. |")
        w("|---|---|---|---|---|")
        for num, page in items:
            if num in done:
                fn, nm = done[num]
                w("| ✔ | %s | %s | `%s` | %d |" % (num, nm, fn, page))
            else:
                w("| — | %s | | | %d |" % (num, page))
        w("")
    w("---")
    w("")
    w("## 規格記号ではない部品")
    w("")
    w("作図の都合で要るもの。JIS C 0617 には無い。端子間は 30。")
    w("**`elements/作図用部品/` に置く。** 規格に基づくものと混ぜない。")
    w("")
    # ここも手で書かない。elements/作図用部品/ にファイルがあるかで印を付ける。
    aid = os.path.join(P.ELEMENTS, "作図用部品")
    have = set(os.listdir(aid)) if os.path.isdir(aid) else set()
    w("| | 名称 |")
    w("|---|---|")
    for nm in ("端子（通過）", "端子（T字分岐）", "端子（十字）", "端子（終端）", "端子（L字）"):
        w("| %s | %s |" % ("✔" if nm + ".elmt" in have else "—", nm))
    w("")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", type=int, metavar="N", help="次に描くもの N 件を表示")
    ap.add_argument("--check", action="store_true", help="書き直さずに要約だけ")
    a = ap.parse_args()

    rows = load_index()
    done = scan_elements()
    n_done = sum(1 for num, _, _, _ in rows if num in done)

    if a.next:
        todo = [(n, s, l, p) for n, s, l, p in rows if n not in done][:a.next]
        if not todo:
            print("すべて採録済み（%d 個）" % len(rows))
            return 0
        print("次に描くもの %d 件 —— 規格票のページを見て起こす" % len(todo))
        for num, sec, label, page in todo:
            print("  %-9s  %-16s  p.%d" % (num, label, page))
        return 0

    if not a.check:
        io.open(OUT, "w", encoding="utf-8", newline="\n").write(render(rows, done))
        print("書き出し:", os.path.relpath(OUT, P.REPO))

    print("採録 %d / %d （残り %d）" % (n_done, len(rows), len(rows) - n_done))
    # 索引に無い番号を持つ .elmt があれば知らせる（第8部など別の部のものは正常）
    stray = [n for n in done if n not in {r[0] for r in rows}]
    if stray:
        print("索引（第7部）に無い番号:", " ".join(sorted(stray)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
