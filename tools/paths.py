# -*- coding: utf-8 -*-
"""図記号(.elmt)の在りかを解決する

ツール3本が共通で使う。**どのフォルダから叩いても、記号が elements/ の
どのサブフォルダにあっても見つかる**ようにするための層。
探索先をここ1か所に集約してあるので、増やすときはこのファイルだけ直せばよい。

探索の順番
  1. 環境変数 W_QET_ELEMENTS（区切りは Windows なら ; 複数指定できる）
  2. <リポジトリ>/elements
  3. QET のユーザーコレクション（%APPDATA%\\qelectrotech\\QElectroTech\\elements）

いずれも再帰的に探す。同じファイル名が複数あれば先の探索先が勝つ。
リポジトリの位置はこのファイルの場所から求めるので、どこに clone してもよい。
"""
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

    raise FileNotFoundError(
        "%s が見つからない。探した場所:\n  %s\n"
        "（環境変数 %s で探索先を足せる）"
        % (name, "\n  ".join(dd) if dd else "(探索先が1つも実在しない)", ENV))


def collection(refresh=False):
    """このリポジトリの elements/ にある .elmt を全部返す（パスのソート順）"""
    return sorted(table([ELEMENTS], refresh).values()) if os.path.isdir(ELEMENTS) else []
