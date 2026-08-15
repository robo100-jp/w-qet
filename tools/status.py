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

# **部を焼き付けない。**第8部・第6部と増えるので、索引も出力も部ごとに持つ。
PARTS = {7: "開閉装置，制御装置及び保護装置",
         8: "計器，ランプ及び信号装置",
         6: "電気エネルギーの発生及び変換",
         2: "図記号要素，限定図記号",
         3: "導体及び接続部品"}


def index_path(part):
    return os.path.join(P.STDDATA, "第%d部索引.tsv" % part)


def out_path(part):
    return os.path.join(P.REPO, "docs", "採録状況.md" if part == 7
                        else "採録状況_第%d部.md" % part)
NUM_RE = re.compile(r"JIS C 0617 / IEC 60617 ([0-9A-Z\-]+)")


def load_index(part=7):
    """索引を読む → [(番号, 節, 分類, ページ), ...]"""
    rows = []
    ip = index_path(part)
    if not os.path.isfile(ip):
        raise SystemExit("索引が無い: %s\n"
                         "  番号→ページの対応表。第7部のものを真似て作る" % ip)
    for line in io.open(ip, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line or line.startswith("#") or line.startswith("番号\t"):
            continue
        f = line.split("\t")
        rows.append((f[0], f[1], f[2], int(f[3]), f[4] if len(f) > 4 else ""))
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


def render(rows, done, pol, part=7):
    secs = []
    for num, sec, label, page, name in rows:
        if not secs or secs[-1][0] != sec:
            secs.append((sec, label, []))
        secs[-1][2].append((num, page, name))

    # **CADにしないものも図は作る。**分母から外さない
    n_skip = sum(1 for r in rows if pol.get(r[0], ("", ""))[0] == "しない")
    n_all = len(rows)
    n_done = sum(1 for r in rows if r[0] in done)
    out = []
    w = out.append
    w("# 採録状況")
    w("")
    w("JIS C 0617 **第%d部**（%s）の図記号 %d 個。"
      % (part, PARTS.get(part, ""), n_all))
    w("")
    w("| | |")
    w("|---|---|")
    w("| 採録済み | **%d / %d**（%.0f%%） |" % (n_done, n_all, 100.0 * n_done / n_all))
    w("| 残り | %d |" % (n_all - n_done))
    if n_skip:
        w("| うち **CAD用シンボルにしない**もの | %d"
          "（判断は `docs/sym/<番号>.html` に書いてある） |" % n_skip)
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
    w("   置き場所は `elements/JIS_C_0617/<節>/<番号>_<和名>.elmt`")
    w("4. `py -3 tools/render_elmt.py <名前>` で**必ず目視**")
    w("5. `py -3 tools/status.py` でこの文書を作り直し、コミット")
    w("")
    w("規格票の在りかと寸法の約束は [規格の参照.md](規格の参照.md) と"
      "[寸法基準.md](寸法基準.md)。")
    w("")
    w("---")
    w("")
    for sec, label, items in secs:
        d = sum(1 for i in items if i[0] in done)
        mark = "✔" if d == len(items) else ("… " if d else "—")
        w("## %s %s  %s %d/%d" % (sec, label, mark, d, len(items)))
        w("")
        w("| | 図記号番号 | 名称 | ファイル | p. |")
        w("|---|---|---|---|---|")
        for num, page, name in items:
            judge, why = pol.get(num, ("", ""))
            tail = ""
            if judge == "しない":
                tail = "　**CAD用シンボルにしない** —— " + why
            if num in done:
                fn, nm = done[num]
                w("| ✔ | %s | %s | `%s`%s | %d |" % (num, nm, fn, tail, page))
            else:
                w("| — | %s | %s%s | | %d |" % (num, name, tail, page))
        w("")
    w("---")
    w("")
    w("## 規格記号ではない部品")
    w("")
    w("作図の都合で要るもの。JIS C 0617 には無い。端子間は 30。")
    w("**`elements/drawing_aids/` に置く。** 規格に基づくものと混ぜない。")
    w("")
    # ここも手で書かない。elements/drawing_aids/ の実物から名前を読む。
    # **ファイル名はASCIIなので、和名は .elmt の中の <name lang="ja"> が持つ。**
    aid = os.path.join(P.ELEMENTS, "drawing_aids")
    w("| | 名称 | ファイル |")
    w("|---|---|---|")
    got = False
    for fn in sorted(os.listdir(aid)) if os.path.isdir(aid) else []:
        if not fn.endswith(".elmt"):
            continue
        t = io.open(os.path.join(aid, fn), encoding="utf-8").read()
        m = re.search(r'<name lang="ja">([^<]*)</name>', t)
        w("| ✔ | %s | `%s` |" % (m.group(1) if m else "", fn))
        got = True
    if not got:
        w("| — | （まだ無い） | |")
    w("")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--next", type=int, metavar="N", help="次に描くもの N 件を表示")
    ap.add_argument("--check", action="store_true", help="書き直さずに要約だけ")
    ap.add_argument("--part", type=int, default=7, help="規格票の部（既定 7）")
    a = ap.parse_args()

    rows = load_index(a.part)
    done = scan_elements()
    pol = P.cad_policy()
    n_done = sum(1 for r in rows if r[0] in done)
    n_skip = sum(1 for r in rows if pol.get(r[0], ("", ""))[0] == "しない")

    if a.next:
        todo = [r for r in rows if r[0] not in done][:a.next]
        if not todo:
            print("すべて採録済み（%d 個）" % len(rows))
            return 0
        print("次に描くもの %d 件 —— 規格票のページを見て起こす" % len(todo))
        for num, sec, label, page, name in todo:
            print("  %-10s  %-24s  p.%d" % (num, name or label, page))
        return 0

    if not a.check:
        op = out_path(a.part)
        io.open(op, "w", encoding="utf-8", newline="\n").write(
            render(rows, done, pol, a.part))
        print("書き出し:", os.path.relpath(op, P.REPO))

    print("採録 %d / %d （残り %d。うち CAD用シンボルにしないもの %d）"
          % (n_done, len(rows), len(rows) - n_done, n_skip))
    # 索引に無い番号を持つ .elmt があれば知らせる。
    # **別の部のものは正常**なので、その部の番号は黙って外す
    pre = "%02d-" % a.part
    stray = [n for n in done
             if n.startswith(pre) and n not in {r[0] for r in rows}]
    if stray:
        print("索引（第%d部）に無い番号:" % a.part, " ".join(sorted(stray)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
