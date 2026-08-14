# -*- coding: utf-8 -*-
"""QElectroTech プロジェクト(.qet) 生成ライブラリ

QET の .qet は XML。手描きした 無題.qet を解析して判明した仕様に基づき、
部品配置・導体・線番・ラベルをプログラムから組み立てる。

要点
  ・部品定義は <collection><category name="import"> に丸ごと埋め込む
    （プロジェクト単体で完結し、他PCでも部品が失われない）
  ・部品インスタンスは type="embed://import/<ファイル名>" で定義を参照
  ・導体は (element_uuid, terminal_uuid) の組で両端を指定する
  ・端子の向きは n=0 / e=1 / s=2 / w=3

部品名は elements/ のどのサブフォルダにあっても名前だけで解決できる（paths.py）。
パスで直に指定してもよい。埋め込むときはファイル名だけを使うので、
どのフォルダの記号から作った .qet でも他PCでそのまま開ける。
"""
import os
import re
import sys
import uuid as U
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                          # noqa: E402

USERCOL = P.usercol()          # 後方互換のため残す。探索は P.find() が行う
ORI = {"n": 0, "e": 1, "s": 2, "w": 3}

# --- 文字の大きさ ---
LBL_PT = 14        # 部品ラベル（機器記号）のポイント数
LBL_X, LBL_Y = 10, -16
NUM_PT = 11        # 導体の線番のポイント数

# --- A3 横（420×297 = 1.414）に合う図枠 ---
A3 = dict(cols=32, rows=16, colsize=60, rowsize=80)   # 1920 x 1280 (+表題欄70)

# 日本の制御盤の慣習。印刷するとコイルと接点の対応が追えなくなるため、
# 接点は親コイルの記号を小文字にして表示する（T1 のタイマの接点 → t1）。
LEGEND = "凡例  大文字 T1・M1・R1 = コイル本体 ／ 小文字 t1・m1・r1 = その接点"
W, TOPY, BOTY = 1920, 120, 1220


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


class Part:
    """部品定義（.elmt）を読み込んで保持する"""
    _cache = {}

    def __init__(self, fname):
        self.path = P.find(fname)
        # 埋め込み時の参照名はファイル名だけ。フォルダ構成を .qet に持ち込まない
        self.fname = os.path.basename(self.path)
        self.raw = open(self.path, encoding="utf-8").read()
        root = ET.fromstring(self.raw)
        self.link_type = root.get("link_type") or "simple"
        self.w = int(root.get("width") or 0)
        self.h = int(root.get("height") or 0)
        self.hx = int(root.get("hotspot_x") or 0)
        self.hy = int(root.get("hotspot_y") or 0)
        n = root.find(".//name[@lang='ja']")
        self.name = (n.text if n is not None else self.fname)
        # 端子（定義ファイルの出現順に id 0,1,2...）
        self.terms = []
        for i, t in enumerate(root.findall(".//terminal")):
            self.terms.append({
                "uuid": t.get("uuid"), "id": i,
                "x": float(t.get("x")), "y": float(t.get("y")),
                "ori": ORI.get(t.get("orientation"), 0),
                "name": t.get("name") or "",
            })

    @classmethod
    def get(cls, fname):
        if fname not in cls._cache:
            cls._cache[fname] = cls(fname)
        return cls._cache[fname]

    def term(self, which):
        """which: 'n','s','e','w' もしくは index

        向きで指定したとき、同じ向きの端子が複数あれば黙って先頭を返さずに
        エラーにする。配線先を取り違えると図面が静かに間違うため。
        """
        if isinstance(which, int):
            return self.terms[which]
        hits = [t for t in self.terms if t["ori"] == ORI[which]]
        if not hits:
            raise KeyError(f"{self.fname} に向き {which} の端子がない")
        if len(hits) > 1:
            raise KeyError(
                f"{self.fname} には向き {which} の端子が {len(hits)} 個ある"
                f"（index {[t['id'] for t in hits]}）。index で指定すること")
        return hits[0]


class Inst:
    """図面上に配置した部品インスタンス"""
    def __init__(self, part, x, y, label="", ori=0):
        self.part, self.x, self.y = part, x, y
        self.label, self.ori = label, ori
        self.uuid = "{%s}" % U.uuid4()
        self.links = []        # slave(接点) → master(コイル) の相互参照

    def link_to(self, master):
        """この接点を親コイルに紐づける（QET の相互参照が自動表示になる）"""
        self.links.append(master)
        return self

    def xml(self):
        terms = "".join(
            f'\n                    <terminal x="{t["x"]:g}" y="{t["y"]:g}" '
            f'id="{t["id"]}" orientation="{t["ori"]}" />'
            for t in self.part.terms)
        # **空の <dynamic_texts /> を書かない。**書くと部品定義側のラベル欄まで
        # 打ち消され、**文字の置き場所そのものが無くなる**（実機で確認。
        # ラベルを省いた接点に何も出ず、同期していないと読み違えた）。
        # ラベルを省いたときも枠だけは置き、中身は QET に埋めさせる。
        slave = self.part.link_type == "slave"
        label = self.label

        info = ""
        if label:
            info = (f'\n                    <elementInformation name="label" '
                    f'show="1">{esc(label)}</elementInformation>')
        # スレーブに**明示ラベルを付けたときだけ**固定文字（UserText）にする。
        # ElementInfo のままだとリンク先のコイルのラベルで表示が上書きされ、
        # 「t1」と書いてもコイルの「T1」が出る。相互参照は links_uuids 側なので
        # UserText にしても切れない。
        # **省いたときは ElementInfo。**スレーブならマスタのラベルがここに出る。
        fixed = slave and bool(label)
        src = "UserText" if fixed else "ElementInfo"
        iname = ("" if fixed else
                 '\n                        <info_name>label</info_name>')
        dtxt = (
            '\n                    <dynamic_elmt_text frame="false" '
            f'Halignment="AlignLeft" x="{LBL_X}" y="{LBL_Y}" rotation="0" '
            f'font="Liberation Sans,{LBL_PT},-1,5,50,0,0,0,0,0,Regular" '
            f'text_width="-1" uuid="{{{U.uuid4()}}}" '
            # 部品を倒しても機器記号は正立のままにする。QET は true のとき
            # 文字の回転を「基準 − 親の回転」に置いて親の回転を打ち消す
            # （dynamicelementtextitem.cpp の parentElementRotationChanged）。
            # false だと文字まで倒れる。属性を省いたときの既定も true。
            f'keep_visual_rotation="true" text_from="{src}" '
            'Valignment="AlignTop">'
            f'\n                        <text>{esc(label)}</text>'
            f'{iname}'
            '\n                    </dynamic_elmt_text>')
        links = ""
        if self.links:
            links = ('\n                <links_uuids>' + "".join(
                f'\n                    <link_uuid uuid="{m.uuid}" />'
                for m in self.links) + '\n                </links_uuids>')
        return (
            f'\n            <element type="embed://import/{esc(self.part.fname)}" '
            f'x="{self.x:g}" y="{self.y:g}" z="10" freezeLabel="false" '
            f'prefix="" uuid="{self.uuid}" orientation="{self.ori}">'
            f'\n                <terminals>{terms}\n                </terminals>'
            f'\n                <inputs />{links}'
            f'\n                <elementInformations>{info}\n                </elementInformations>'
            f'\n                <dynamic_texts>{dtxt}\n                </dynamic_texts>'
            f'\n                <texts_groups />'
            f'\n            </element>')


class Cond:
    """導体（部品の端子どうしを結ぶ）"""
    def __init__(self, a, at, b, bt, num=""):
        self.a, self.at, self.b, self.bt, self.num = a, at, b, bt, num

    def xml(self):
        ta = self.a.part.term(self.at)
        tb = self.b.part.term(self.bt)
        return (
            f'\n            <conductor num="{esc(self.num)}" conductor_color="" '
            f'type="multi" element1_name="{esc(self.a.part.name)}" '
            f'element2_name="{esc(self.b.part.name)}" x="0" y="0" displaytext="1" '
            'vertirotatetext="270" onetextperfolio="0" color2="#000000" '
            'horizrotatetext="0" bicolor="false" '
            f'element1="{self.a.uuid}" element2="{self.b.uuid}" '
            f'condsize="1" numsize="{NUM_PT}" tension_protocol="" dash-size="1" bus="" '
            'freezeLabel="false" conductor_section="" vertical-alignment="AlignRight" '
            f'terminal1="{ta["uuid"]}" terminalname1="{esc(ta["name"])}" '
            f'terminal2="{tb["uuid"]}" terminalname2="{esc(tb["name"])}" '
            f'element1_label="{esc(self.a.label)}" element2_label="{esc(self.b.label)}" '
            'function="" horizontal-alignment="AlignBottom" text_color="#000000" '
            'formula="" cable="">\n            </conductor>')


class Folio:
    def __init__(self, title="", cols=17, rows=8, colsize=60, rowsize=80,
                 author="", date="", filename=""):
        self.title, self.cols, self.rows = title, cols, rows
        self.colsize, self.rowsize = colsize, rowsize
        self.author, self.date, self.filename = author, date, filename
        self.insts, self.conds = [], []
        self.shapes, self.texts = [], []

    def add(self, part_file, x, y, label="", ori=0):
        i = Inst(Part.get(part_file), x, y, label, ori)
        self.insts.append(i)
        return i

    def wire(self, a, at, b, bt, num=""):
        c = Cond(a, at, b, bt, num)
        self.conds.append(c)
        return c

    def rect(self, x1, y1, x2, y2, dashed=True, color="#000000", width=0.6):
        """盤の境界などを示す矩形。既定は破線（盤外郭の慣用）"""
        style = "DashLine" if dashed else "SolidLine"
        self.shapes.append(
            f'\n            <shape z="0" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'rx="0" ry="0" closed="0" type="Rectangle" is_movable="1">'
            f'\n                <pen color="{color}" widthF="{width}" style="{style}"/>'
            '\n                <brush color="#000000" style="NoBrush"/>'
            '\n            </shape>')

    def text(self, x, y, s, pt=12, bold=False):
        """図面上の独立テキスト（盤名・注記など）

        text 属性の中身は Qt のリッチテキスト。タグは実体参照で書くので
        属性値を壊さないよう esc() を通してから &lt; に戻す。
        """
        font = f"Sans Serif,{pt},-1,5,{'75' if bold else '50'},0,0,0,0,0"
        body = esc(s)
        if bold:
            body = f"&lt;b&gt;{body}&lt;/b&gt;"
        self.texts.append(
            f'\n            <input x="{x}" y="{y}" rotation="0" '
            f'font="{font}" text="{body}"/>')

    def xml(self, order):
        h = self.rows * self.rowsize + 20
        return (
            f'\n    <diagram colsize="{self.colsize}" indexrev="" displaycols="true" '
            f'plant="" locmach="" title="{esc(self.title)}" rows="{self.rows}" '
            f'rowsize="{self.rowsize}" height="{h}" filename="{esc(self.filename)}" '
            f'order="{order}" date="{esc(self.date) or "null"}" '
            f'author="{esc(self.author)}" version="0.100.0" freezeNewConductor="false" '
            f'cols="{self.cols}" displayAt="bottom" auto_page_num="" '
            'folio="%id/%total" displayrows="true" freezeNewElement="false">'
            '\n        <defaultconductor num="_" conductor_color="" type="multi" '
            'displaytext="1" vertirotatetext="270" onetextperfolio="0" color2="#000000" '
            f'horizrotatetext="0" bicolor="false" condsize="1" numsize="{NUM_PT}" '
            'tension_protocol="" bus="" dash-size="1" conductor_section="" '
            'vertical-alignment="AlignRight" function="" '
            'horizontal-alignment="AlignBottom" text_color="#000000" cable="" formula="" />'
            '\n        <elements>' + "".join(i.xml() for i in self.insts) +
            '\n        </elements>'
            '\n        <conductors>' + "".join(c.xml() for c in self.conds) +
            '\n        </conductors>'
            + ('\n        <inputs>' + "".join(self.texts) +
               '\n        </inputs>' if self.texts else '')
            + ('\n        <shapes>' + "".join(self.shapes) +
               '\n        </shapes>' if self.shapes else '')
            + '\n    </diagram>')


HEAD = '''<project title="{title}" version="0.100.0">
    <properties>
        <property name="title" show="1">{title}</property>
    </properties>
    <newdiagrams>
        <border cols="32" colsize="60" rows="16" displaycols="true" displayrows="true" rowsize="80" />
        <inset date="null" title="" auto_page_num="" displayAt="bottom" filename="" folio="%id/%total" author="" />
        <conductors num="_" conductor_color="" type="multi" displaytext="1" onetextperfolio="0" vertirotatetext="270" color2="#000000" horizrotatetext="0" bicolor="false" condsize="1" numsize="{npt}" tension_protocol="" bus="" dash-size="1" conductor_section="" vertical-alignment="AlignRight" function="" horizontal-alignment="AlignBottom" text_color="#000000" cable="" formula="" />
        <!-- フォリオ参照の札に出す文字。**既定は %id-%l%c。**%f（フォリオ番号）は
             番号を振っていないと空になり、札に何も出ない。%id は何枚目かなので必ず値を持つ。
             **これは「新しいフォリオ」の設定で、既存のフォリオには効かない。** -->
        <report label="%id-%l%c" />
        <xrefs>
            <xref type="coil" displayhas="cross" offset="0" slave_label="(%id-%l%c)" showpowerctc="true" master_label="%id-%l%c" snapto="bottom" />
            <xref type="protection" displayhas="cross" offset="0" slave_label="(%id-%l%c)" showpowerctc="true" master_label="%id-%l%c" snapto="bottom" />
        </xrefs>
        <conductors_autonums freeze_new_conductors="false" current_autonum="" />
        <folio_autonums />
        <element_autonums freeze_new_elements="false" current_autonum="" />
    </newdiagrams>'''


def save(path, folios, title="制御盤"):
    used = []
    for f in folios:
        for i in f.insts:
            if i.part.fname not in [u.fname for u in used]:
                used.append(i.part)
    cat = ""
    for p in used:
        body = re.sub(r"^\s*<\?xml[^>]*\?>\s*", "", p.raw).strip()
        body = "\n".join("                " + l for l in body.splitlines())
        cat += (f'\n            <element name="{esc(p.fname)}">\n{body}'
                f'\n            </element>')
    xml = (HEAD.format(title=esc(title), npt=NUM_PT)
           + "".join(f.xml(n) for n, f in enumerate(folios, 1))
           + '\n    <collection>\n        <category name="import">'
             '\n            <names>\n                <name lang="ja">インポートした要素</name>'
             '\n                <name lang="en">Imported elements</name>\n            </names>'
           + cat
           + '\n        </category>\n    </collection>\n</project>\n')
    open(path, "w", encoding="utf-8").write(xml)
    return len(used)
