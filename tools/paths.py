# -*- coding: utf-8 -*-
"""図記号(.elmt)と規格票 PDF の在りかを解決する

各ツールが共通で使う。**どのフォルダから叩いても、記号が elements/ の
どのサブフォルダにあっても見つかる**ようにするための層。
探索先をここ1か所に集約してあるので、増やすときはこのファイルだけ直せばよい。

探索の順番
  1. 環境変数 W_QET_ELEMENTS（区切りは Windows なら ; 複数指定できる）
  2. <リポジトリ>/elements
  3. QET のユーザーコレクション（%APPDATA%\\qelectrotech\\QElectroTech\\elements）

いずれも再帰的に探す。同じファイル名が複数あれば先の探索先が勝つ。
リポジトリの位置はこのファイルの場所から求めるので、どこに clone してもよい。

規格票 PDF は `standard()` が探す。**リポジトリの外にしか置かない**ので、
パスをソースに書かずここで解決する（→ docs/規格の参照.md）。
"""
import glob as _glob
import os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

ELEMENTS = os.path.join(REPO, "elements")     # このリポジトリの図記号
RENDER = os.path.join(REPO, "render")         # 描き出した PNG の置き場

ENV = "W_QET_ELEMENTS"

_cache = {}


def usercol():
    """QET のユーザーコレクション。Windows 以外・未作成なら None"""
    ap = os.environ.get("APPDATA")
    if not ap:
        return None
    p = os.path.join(ap, "qelectrotech", "QElectroTech", "elements")
    return p if os.path.isdir(p) else None


def search_dirs(extra=()):
    """実在する探索先を優先順に並べて返す"""
    cand = list(extra) + os.environ.get(ENV, "").split(os.pathsep) \
        + [ELEMENTS, usercol()]
    dirs = []
    for d in cand:
        if not d:
            continue
        d = os.path.abspath(d)
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)
    return dirs


def table(dirs=None, refresh=False):
    """{ファイル名: フルパス} を返す。探索先を再帰的に走査した結果

    同名は先勝ち（探索先の順番がそのまま優先順位）。
    """
    dirs = search_dirs() if dirs is None else [os.path.abspath(d) for d in dirs]
    key = tuple(dirs)
    if refresh or key not in _cache:
        found = {}
        for d in dirs:
            for root, _, files in os.walk(d):
                for fn in sorted(files):
                    if fn.endswith(".elmt") and fn not in found:
                        found[fn] = os.path.join(root, fn)
        _cache[key] = found
    return _cache[key]


def find(name, dirs=None):
    """名前でもパスでも .elmt の実体を探し当てる

    受け付ける形
      elements/接点/30_a接点.elmt   パス（実在すればそのまま使う）
      30_a接点.elmt                 ファイル名
      30_a接点                      拡張子なし
      接点/30_a接点                 サブフォルダ付き（区切りは / \\ どちらでも）

    見つからなければ FileNotFoundError。探した場所を全部メッセージに入れる。
    """
    for cand in (name, name if name.endswith(".elmt") else name + ".elmt"):
        if os.path.isfile(cand):
            return os.path.abspath(cand)

    rel = (name if name.endswith(".elmt") else name + ".elmt").replace("\\", "/")
    base = os.path.basename(rel)
    dd = search_dirs() if dirs is None else [os.path.abspath(d) for d in dirs]

    # 探索先を1つずつ、その中で「パス指定 → 名前で再帰」の順に当てる。
    # 全探索先の直下を先に見てしまうと、elements/ の入れ子に置いた記号が
    # ユーザーコレクション直下の同名に負ける。優先順位は探索先の順で決める。
    for d in dd:
        p = os.path.join(d, *rel.split("/"))
        if os.path.isfile(p):
            return p
        hit = table([d]).get(base)
        if hit:
            return hit

    # 図記号番号だけで呼べるようにする（`render_elmt.py 07-02-06`）。
    # ファイル名は「番号_和名.elmt」なので前方一致で足りる。**一意のときだけ**通す。
    stem = base[:-5]
    for d in dd:
        hit = [p for fn, p in sorted(table([d]).items()) if fn.startswith(stem)]
        if len(hit) == 1:
            return hit[0]
        if len(hit) > 1:
            raise FileNotFoundError(
                "%s に当てはまるものが複数ある:\n  %s"
                % (name, "\n  ".join(os.path.basename(p) for p in hit)))

    raise FileNotFoundError(
        "%s が見つからない。探した場所:\n  %s\n"
        "（環境変数 %s で探索先を足せる）"
        % (name, "\n  ".join(dd) if dd else "(探索先が1つも実在しない)", ENV))


def collection(refresh=False):
    """このリポジトリの elements/ にある .elmt を全部返す（パスのソート順）"""
    return sorted(table([ELEMENTS], refresh).values()) if os.path.isdir(ELEMENTS) else []


# --- 規格票 PDF -------------------------------------------------------------
#
# **買った規格票はリポジトリに入れない。**公開リポジトリなので再配布になる。
# 置き場所も人によって違うので、パスをソースに書かずここで解決する。

STD_ENV = "W_QET_STD"


def std_dirs():
    """規格票 PDF を探す場所を優先順に"""
    out = []
    for d in (os.environ.get(STD_ENV),
              os.path.join(os.path.expanduser("~"), "規格"),
              os.path.join(os.path.expanduser("~"), "Documents", "規格")):
        if d and os.path.isdir(d) and d not in out:
            out.append(d)
    return out


def standard(part=7):
    """JIS C 0617 第<part>部の PDF を探して返す。無ければ FileNotFoundError

    環境変数 W_QET_STD にファイルそのものを指してもよい（1部だけ使うとき）。
    JSA の PDF はファイル名が `jis_c_00617_007_000_2024_j_ed10_ch.pdf` の形。
    """
    env = os.environ.get(STD_ENV)
    if env and os.path.isfile(env):
        return env
    pat = "jis_c_00617_%03d_*.pdf" % part
    for d in std_dirs():
        hit = sorted(_glob.glob(os.path.join(d, pat)))
        if hit:
            return hit[0]
    raise FileNotFoundError(
        "JIS C 0617 第%d部の PDF が見つからない（%s）。探した場所:\n  %s\n"
        "（環境変数 %s にフォルダかファイルを指定できる）"
        % (part, pat, "\n  ".join(std_dirs()) or "(どれも実在しない)", STD_ENV))


def index(part=7):
    """図記号番号 → 規格票のページ。docs/第<part>部索引.tsv から読む"""
    import io
    p = os.path.join(REPO, "docs", "第%d部索引.tsv" % part)
    out = {}
    if not os.path.isfile(p):
        return out
    for line in io.open(p, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if len(f) == 4 and f[0].startswith("%02d-" % part) and f[3].isdigit():
            out[f[0]] = int(f[3])
    return out


def dirname_ja(d):
    """節のフォルダの日本語の表示名。`qet_directory` が持っている

    **フォルダ名は ASCII にしてある**（日本語だと QET が `qet_directory` を
    読めず、部品パネルで名前が空欄になる）。和名はここから引く。
    """
    import io
    import re
    f = os.path.join(d, "qet_directory")
    if os.path.isfile(f):
        m = re.search(r'<name lang="ja">([^<]*)</name>',
                      io.open(f, encoding="utf-8").read())
        if m:
            return m.group(1)
    return os.path.basename(d)
