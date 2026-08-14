# -*- coding: utf-8 -*-
"""図記号を QET のユーザーコレクションに登録する

  py -3 tools/install.py             # 登録（更新）
  py -3 tools/install.py --dry-run   # 何が起きるかだけ表示
  py -3 tools/install.py --uninstall # 取り除く

登録先は %APPDATA%\\qelectrotech\\QElectroTech\\elements\\w-qet\\。
**既存の部品と混ぜず、専用のフォルダ1つにまとめる。**

  ・名前がぶつからない（同名の自作部品があっても影響しない）
  ・取り除くときはそのフォルダを消すだけ
  ・QET の部品パネルに1つの木としてまとまって出る

カテゴリ名は各フォルダの `qet_directory` が持つ。QET はこれを読んで
部品パネルに日本語名を出す。無い場合はフォルダ名がそのまま出る。

登録したら **QET を再起動**すること。起動時にコレクションを読むため。
"""
import argparse
import io
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

DIRNAME = "w-qet"
TOP_NAME_JA = "w-qet 電気用図記号（日本）"
TOP_NAME_EN = "w-qet Graphical symbols for diagrams (Japan)"


def qet_directory(ja, en):
    return ('<qet-directory>\n    <names>\n'
            '        <name lang="ja">%s</name>\n'
            '        <name lang="en">%s</name>\n'
            '    </names>\n</qet-directory>\n' % (ja, en))


def target_root():
    uc = P.usercol()
    if not uc:
        raise SystemExit(
            "QET のユーザーコレクションが見つからない。\n"
            "  一度 QET をスタートメニューから起動すると作られる。\n"
            "  %APPDATA%\\qelectrotech\\QElectroTech\\elements\\")
    return os.path.join(uc, DIRNAME)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--uninstall", action="store_true")
    a = ap.parse_args()

    dst = target_root()

    if a.uninstall:
        if not os.path.isdir(dst):
            print("登録されていない:", dst)
            return 0
        n = sum(len([f for f in fs if f.endswith(".elmt")]) for _, _, fs in os.walk(dst))
        print("取り除く: %s（記号 %d 個）" % (dst, n))
        if not a.dry_run:
            shutil.rmtree(dst)
            print("削除した")
        return 0

    src = P.ELEMENTS
    if not os.path.isdir(src) or not P.collection():
        raise SystemExit("elements/ に .elmt が無い: %s" % src)

    print("登録元: %s" % src)
    print("登録先: %s" % dst)
    print()

    n_elmt = n_dir = 0
    plan = []
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        out = dst if rel == "." else os.path.join(dst, rel)
        elmts = sorted(f for f in files if f.endswith(".elmt"))
        if not elmts and not any(
                f.endswith(".elmt") for _, _, fs in os.walk(root) for f in fs):
            continue
        plan.append((out, rel, elmts, os.path.join(root, "qet_directory")))
        n_dir += 1
        n_elmt += len(elmts)

    for out, rel, elmts, qd in plan:
        label = "（最上位）" if rel == "." else rel
        print("  %-28s 記号 %d 個" % (label, len(elmts)))
        if a.dry_run:
            continue
        os.makedirs(out, exist_ok=True)
        # カテゴリ名。元に qet_directory があればそれを、無ければ作る
        dst_qd = os.path.join(out, "qet_directory")
        if os.path.isfile(qd):
            shutil.copy2(qd, dst_qd)
        elif rel == ".":
            io.open(dst_qd, "w", encoding="utf-8", newline="\n").write(
                qet_directory(TOP_NAME_JA, TOP_NAME_EN))
        elif not os.path.isfile(dst_qd):
            nm = os.path.basename(rel)
            io.open(dst_qd, "w", encoding="utf-8", newline="\n").write(
                qet_directory(nm, nm))
        for f in elmts:
            shutil.copy2(os.path.join(P.ELEMENTS, rel, f) if rel != "." else
                         os.path.join(P.ELEMENTS, f), os.path.join(out, f))

    print()
    print("%s: フォルダ %d / 記号 %d" % ("予定" if a.dry_run else "登録した", n_dir, n_elmt))
    if not a.dry_run:
        print()
        print("**QET を再起動すること。** 起動時にコレクションを読む。")
        print("スタートメニューから起動する（exe 直叩きは部品0個になる）。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
