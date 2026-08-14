# -*- coding: utf-8 -*-
"""図記号カタログ（`docs/カタログ.md` と `docs/images/*.svg`）を作り直す

**この文書は手で書かない。** 記号を足したり直したりしたら叩き直す。
`status.py` が採録の**数**を数え直すのと同じ役割を、**姿**について持つ。

  py -3 tools/catalog.py

節の表示名は各フォルダの `qet_directory` から取る（QET の部品パネルに出る名前と
同じものを使う。カタログとパネルで名前が食い違うと引けなくなる）。
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                           # noqa: E402
import svg_elmt as S                                        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

DOCS = os.path.join(P.REPO, "docs")
IMG = os.path.join(DOCS, "images")

HEAD = """# 図記号カタログ

`elements/` にある図記号 %(n)d 個の姿。**番号を知らなくても形から引ける**ように
節ごとに並べたもの。番号と名称の一覧は [採録状況.md](採録状況.md)。

> **この文書は手で書かない。** `py -3 tools/catalog.py` が `elements/` から作り直す。
> 記号を足したり直したりしたら叩き直す。

> **JIS C 0617（＝IEC 60617）を参考に、座標から描き起こしたもの**です。
> 規格票の図版を複製したものではありません。「JIS準拠」を名乗るものでもありません。

図は SVG です。**GitHub 上でそのまま見え、拡大しても崩れません。**
1目盛 = 作図モジュール **1M = 10単位**（[寸法基準.md](寸法基準.md)）。

"""


def slug(s):
    """GitHub が見出しから作るアンカー名

    **句読点は「消す」。ハイフンに置き換えるのではない。**
    `07-A 旧図記号（参考・使わない）` → `07-a-旧図記号参考使わない`。
    置き換えにすると目次のリンクが全部外れる（見た目では気づけない）。
    """
    s = re.sub(r"[^\w\s-]", "", s.lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "-", s.strip())


def dirname_ja(d):
    """フォルダの `qet_directory` が持つ日本語の表示名。無ければフォルダ名"""
    f = os.path.join(d, "qet_directory")
    if os.path.isfile(f):
        m = re.search(r'<name lang="ja">([^<]*)</name>',
                      open(f, encoding="utf-8").read())
        if m:
            return m.group(1)
    return os.path.basename(d)


def main():
    os.makedirs(IMG, exist_ok=True)
    secs = S.sections()
    total = sum(len(v) for v in secs.values())

    # 出所ごとにまとめる。**規格に基づくものと、そうでないものを混ぜない**
    groups = {}
    for key in sorted(secs):
        top = key.split("/")[0]
        groups.setdefault(top, []).append(key)

    body, toc = [], []
    for top in sorted(groups):
        top_ja = dirname_ja(os.path.join(P.ELEMENTS, top))
        body.append("## %s\n" % top_ja)
        for key in groups[top]:
            files = sorted(secs[key])
            leaf = key.rsplit("/", 1)[-1]
            ja = dirname_ja(os.path.join(P.ELEMENTS, *key.split("/")))
            name = os.path.join(IMG, leaf + ".svg")
            open(name, "w", encoding="utf-8").write(S.sheet(files, cols=6))
            body.append("### %s  <sub>%d個</sub>\n" % (ja, len(files)))
            body.append("![%s](images/%s.svg)\n" % (ja, leaf))
            toc.append("- [%s](#%s) %d個" % (ja, slug(ja), len(files)))
            print("  %-14s %2d個" % (leaf, len(files)))

    out = os.path.join(DOCS, "カタログ.md")
    open(out, "w", encoding="utf-8").write(
        HEAD % {"n": total} + "\n".join(toc) + "\n\n" + "\n".join(body))
    print("書き出し:", os.path.relpath(out, P.REPO), "／ 図 %d枚" % len(secs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
