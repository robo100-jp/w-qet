# -*- coding: utf-8 -*-
"""図記号1個につき1枚の HTML を作り、目次と注釈のページでまとめる（`docs/sym/`）

**カタログを置き換えるもの。** 姿を並べるだけでなく、**他の形式に写すのに要る
数値を全部出す**（外形・挿入基点・端子・図形の座標・文字の大きさ）。
`.elmt` だけでなく DXF なり何なりに変換する人が、このページだけ見れば済むように。

  py -3 tools/sympage.py

出力は `docs/sym/`。**外部の CSS・JS・画像を使わない**ので、
GitHub Pages でも、ローカルの file:// でも、1枚だけ人に渡してもそのまま開ける。

規格票の PDF は**要らない。**規格から採った情報は
`docs/規格データ/` の注釈 tsv（要点と適用先）に
落としてあり、ここはそれを読む。**会社PCでも作り直せる。**

> **規格票の本文を写さない。**注釈のページに載せるのは、番号・こちらの言葉での
> 要点・適用される図記号へのリンクだけ（CLAUDE.md の 1・2・5）。
"""
import io
import json
import os
import re
import sys
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paths as P                                           # noqa: E402
import render_elmt as R                                     # noqa: E402
import svg_elmt as S                                        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

MODULE_MM = 5.0            # 規格の作図モジュール M（規格票の「概要」）
UNIT_MM = MODULE_MM / 10   # グリッド1単位 = 0.1M

DASH = {"normal": "実線", "dashed": "破線", "dotted": "点線",
        "dashdotted": "一点鎖線"}
DASH_KEY = {"normal": "solid", "dashed": "dashed", "dotted": "dotted",
            "dashdotted": "dashdot"}
WEIGHT = {"thin": "細", "normal": "標準", "hight": "太", "eleve": "太",
          "none": "描かない"}
WEIGHT_KEY = {"thin": "thin", "normal": "normal", "hight": "thick",
              "eleve": "thick", "none": "none"}
END = {"simple": "開いた矢", "triangle": "塗り三角", "circle": "丸", "diamond": "菱形"}
END_KEY = {"simple": "open_arrow", "triangle": "filled_triangle",
           "circle": "circle", "diamond": "diamond"}
LINK = {"simple": "単独の機器", "master": "マスタ（別の場所に接点を持つ側）",
        "slave": "スレーブ（マスタから名前を受け取る側）", "terminal": "端子台部品",
        "next_report": "フォリオ参照（続き）",
        "previous_report": "フォリオ参照（元）"}
ORI = {"n": "上", "e": "右", "s": "下", "w": "左"}
PARTS = {"07": "第7部 開閉装置，制御装置及び保護装置",
         "08": "第8部 計器，ランプ及び信号装置"}

CSS = """
:root{--bg:#fff;--fg:#1a1a1a;--dim:#666;--line:#dcdcdc;--accent:#1c4f9c;
      --card:#fafafa;--code:#f2f3f5;--warn:#8a5a00}
@media (prefers-color-scheme:dark){:root{
  --bg:#16181c;--fg:#e6e6e6;--dim:#9aa0a6;--line:#33363c;--accent:#8ab4f8;
  --card:#1e2126;--code:#202329;--warn:#d9a441}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:"Yu Gothic UI",Meiryo,system-ui,sans-serif;line-height:1.75;
  font-size:15px}
.wrap{max-width:1000px;margin:0 auto;padding:22px 18px 64px}
a{color:var(--accent)}
h1{font-size:1.45rem;margin:.2em 0 .1em}
h1 .num{font-family:ui-monospace,Consolas,monospace;color:var(--dim);
  margin-right:.6em}
h2{font-size:1.05rem;margin:2.2em 0 .5em;padding-bottom:.25em;
  border-bottom:1px solid var(--line)}
h3{font-size:.95rem;margin:1.6em 0 .3em}
.en{color:var(--dim);font-size:.9rem}
.src{font-family:ui-monospace,Consolas,monospace;font-size:.82rem;
  color:var(--dim);margin:.4em 0 0}
.top{display:flex;gap:24px;flex-wrap:wrap;align-items:flex-start}
.fig{background:var(--card);border:1px solid var(--line);border-radius:8px;
  padding:12px;flex:0 0 auto;max-width:100%}
.fig svg{display:block;max-width:100%;height:auto;color:var(--fg)}
.legend{font-size:.78rem;color:var(--dim);margin-top:6px;text-align:center}
.spec{flex:1 1 320px;min-width:280px}
table{border-collapse:collapse;width:100%;font-size:.86rem}
.scroll{overflow-x:auto}
th,td{border:1px solid var(--line);padding:5px 8px;text-align:left;
  vertical-align:top}
th{background:var(--card);font-weight:600;white-space:nowrap}
td.n,th.n{text-align:right;font-family:ui-monospace,Consolas,monospace;
  white-space:nowrap}
.spec table th{width:8.5em}
.units{margin:1.4em 0 .4em;font-size:.85rem}
.units button{font:inherit;padding:3px 12px;margin-right:-1px;cursor:pointer;
  border:1px solid var(--line);background:var(--bg);color:var(--fg)}
.units button.on{background:var(--accent);color:#fff;border-color:var(--accent)}
.note{white-space:pre-wrap;background:var(--card);border-left:3px solid var(--line);
  padding:10px 14px;font-size:.88rem;border-radius:0 6px 6px 0}
.rule{font-size:.85rem;color:var(--dim)}
.rule li{margin:.25em 0}
pre{background:var(--code);padding:12px;border-radius:6px;overflow-x:auto;
  font-size:.78rem;line-height:1.5}
code{font-family:ui-monospace,Consolas,monospace;font-size:.92em}
details summary{cursor:pointer;color:var(--accent);font-size:.9rem}
nav.crumb{font-size:.85rem;color:var(--dim);margin-bottom:1em}
footer{margin-top:3.5em;padding-top:1em;border-top:1px solid var(--line);
  font-size:.8rem;color:var(--dim)}
.grid{display:grid;gap:10px;
  grid-template-columns:repeat(auto-fill,minmax(118px,1fr))}
.cell{border:1px solid var(--line);border-radius:6px;padding:8px 4px 6px;
  text-align:center;text-decoration:none;color:inherit;background:var(--card)}
.cell:hover{border-color:var(--accent)}
.cell .box{height:66px;display:flex;align-items:center;justify-content:center}
.cell svg{max-width:100%;max-height:64px;height:auto;color:var(--fg)}
.cell .id{font-family:ui-monospace,Consolas,monospace;font-size:.72rem;
  color:var(--dim);margin-top:4px}
.cell .ja{font-size:.74rem;line-height:1.35;margin-top:1px;overflow:hidden;
  display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical}
#q{width:100%;max-width:360px;font:inherit;padding:6px 10px;
  border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg)}
.hit{font-size:.82rem;color:var(--dim);margin-left:.6em}
.an{border:1px solid var(--line);border-radius:8px;padding:12px 16px;
  margin:.8em 0;background:var(--card)}
.an h3{margin:0 0 .2em}
.an .id{font-family:ui-monospace,Consolas,monospace;color:var(--dim);
  margin-right:.5em}
.an .apply{font-size:.8rem;margin-top:.5em}
.an .apply a{font-family:ui-monospace,Consolas,monospace;margin-right:.35em}
.hand{border:1px dashed var(--line);border-radius:6px;padding:2px 14px;
  background:var(--card)}
.hand .ph{color:var(--dim);font-size:.85rem;font-style:italic}
.hand h4{margin:.8em 0 .2em;font-size:.9rem}
h3 + .rule{margin-top:.1em}
.pencil{font-size:.72rem;color:var(--dim);font-weight:400;margin-left:.6em;
  border:1px solid var(--line);border-radius:3px;padding:0 5px}
.caution{border-left:3px solid var(--warn);background:var(--card);
  padding:10px 14px;font-size:.85rem;border-radius:0 6px 6px 0;margin:1em 0}
"""

JS_UNITS = """
(function(){var m='u',b=document.querySelectorAll('.units button');
 function f(v,k){v=parseFloat(v);
  if(k==='M')v=v/10;else if(k==='mm')v=v*%(mm)g;
  return (Math.round(v*1000)/1000).toString();}
 function go(){document.querySelectorAll('.v').forEach(function(e){
   e.textContent=f(e.dataset.u,m);});
  b.forEach(function(x){x.classList.toggle('on',x.dataset.m===m);});}
 b.forEach(function(x){x.onclick=function(){m=x.dataset.m;go();};});go();})();
""" % {"mm": UNIT_MM}

JS_FILTER = """
(function(){var q=document.getElementById('q'),h=document.getElementById('hit'),
 c=[].slice.call(document.querySelectorAll('.cell'));
 q.oninput=function(){var s=q.value.trim().toLowerCase(),n=0;
  c.forEach(function(e){var ok=!s||e.dataset.k.indexOf(s)>=0;
   e.style.display=ok?'':'none';if(ok)n++;});
  document.querySelectorAll('section').forEach(function(x){
   x.style.display=x.querySelector('.cell:not([style*="none"])')?'':'none';});
  h.textContent=s?n+' 件':'';};})();
"""

FOOT = ('w-qet — JIS C 0617（＝IEC 60617）を参考に、座標から描き起こしたもの。'
        '<b>規格票の図版や本文を複製したものではなく、「JIS準拠」を名乗るもの'
        'でもありません。</b>正しさは保証しません。<br>'
        'この頁は <code>tools/sympage.py</code> が <code>elements/</code> から'
        '作り直します。<b>「手で書く欄」だけは作り直しても消えません</b>'
        '（<code>&lt;!--hand:…--&gt;</code> の印で挟んであります。'
        '<b>印を消さないでください</b>）。それ以外を書き換えても'
        '次の作り直しで消えます。　ライセンス CC0 1.0')


# ---- 規格から採った情報（PDF は要らない。tsv を読む）--------------------
def load_notes():
    """{注釈番号: (表題, 要点, [適用される図記号])}"""
    out = {}
    for part in (7, 8):
        f = os.path.join(P.STDDATA, "第%d部注釈.tsv" % part)
        if not os.path.isfile(f):
            continue
        for line in io.open(f, encoding="utf-8"):
            if line.startswith("#") or not line.strip():
                continue
            a, title, gist = line.rstrip("\n").split("\t")
            out[a] = [title, gist, []]
        g = os.path.join(P.STDDATA, "第%d部注釈_適用.tsv" % part)
        for line in io.open(g, encoding="utf-8"):
            if not line.strip():
                continue
            a, syms = line.rstrip("\n").split("\t")
            if a in out:
                out[a][2] = syms.split()
    return out


# ---- 手で書き込む欄 ------------------------------------------------------
#
# **この頁は人も直接書き換える。**作り直しで消してはいけないので、
# 印で挟んだところだけは既存のファイルから読み戻す。
#
#   <!--hand:memo-->  … 人が書く …  <!--/hand:memo-->
#
# **印を消さないこと。**消えていると読み戻せないので、
# その頁だけ作り直しを見送って知らせる（黙って消さない）。
HAND_RE = re.compile(r"<!--hand:(\w+)-->(.*?)<!--/hand:\1-->", re.S)
_KEEP = {}


def read_hand(path):
    """既にある頁から手書きの中身を読む → {key: html}"""
    if not os.path.isfile(path):
        return {}
    return {m.group(1): m.group(2)
            for m in HAND_RE.finditer(io.open(path, encoding="utf-8").read())}


PH_RE = re.compile(r'<p class="ph">.*?</p>', re.S)


def hand(key, placeholder, default=None):
    """手で書く欄。`default` を渡すと、空のときそれを焼く

    **規格票から判断が付くものは `default` に載せて初回に焼き、以後は
    頁に書いてあるほうを優先する。**人が直接書き換えたらそれが残る。
    """
    # **前回の「（例：…）」は捨てる。**残すと書き足すたびに例文が溜まる
    got = PH_RE.sub("", _KEEP.get(key, "")).strip()
    # **書いてあるものが最優先。**ここを else に落とすと書いたものが消える
    # （一度やった。既定を持つ欄で「書いてある＋既定あり」がどの枝にも
    # 入らず、最後の else で例文に上書きされていた）
    if got:
        if default is None:
            # 既定を焼く欄は数えない。**人が書いた欄だけ**数える
            _KEEP["_written"] = "1"
    elif default:
        got = default
    else:
        got = '<p class="ph">（%s）</p>' % escape(placeholder)
    return ('<div class="hand"><!--hand:%s-->%s<!--/hand:%s--></div>'
            % (key, got, key))


def rich(s):
    """`**強調**` だけ太字にする。tsv に書いた要点をそのまま出すため"""
    return re.sub("[*][*](.+?)[*][*]", lambda m: "<b>%s</b>" % m.group(1), escape(s))


def num(v):
    return '<span class="v" data-u="%g">%g</span>' % (float(v), float(v))


def pt(x, y):
    return "(%s, %s)" % (num(x), num(y))


def style_of(a):
    st = dict(kv.split(":", 1) for kv in a.get("style", "").split(";") if ":" in kv)
    return (st.get("line-style", "normal"), st.get("line-weight", "normal"),
            st.get("filling", "none"))


def shapes(prims):
    """図形を**形式に依らない形**に直す（表と JSON の両方がこれを使う）

    `.elmt` の生の属性をそのまま出さない。円は中心と直径、弧は中心と角度、
    という**どの CAD でも同じ意味になる形**にしてから渡す。
    """
    out = []
    for tag, a in prims:
        f = lambda k, d=0.: float(a.get(k, d))              # noqa: E731
        ls, lw, fill = style_of(a)
        s = {"stroke": {"style": DASH_KEY.get(ls, ls),
                        "weight": WEIGHT_KEY.get(lw, lw)},
             "fill": None if fill in ("none", "") else fill}
        if tag == "line":
            s.update(type="line", frm=[f("x1"), f("y1")], to=[f("x2"), f("y2")])
            for k, e, ln in (("start", a.get("end1"), a.get("length1")),
                             ("end", a.get("end2"), a.get("length2"))):
                if e and e != "none":
                    s.setdefault("ends", {})[k] = {
                        "kind": END_KEY.get(e, e), "length": float(ln or 1.5)}
        elif tag == "rect":
            s.update(type="rect", at=[f("x"), f("y")],
                     size=[f("width"), f("height")])
        elif tag == "ellipse":
            w, h = f("width"), f("height")
            c = [f("x") + w / 2, f("y") + h / 2]
            if abs(w - h) < 1e-9:
                s.update(type="circle", center=c, diameter=w)
            else:
                s.update(type="ellipse", center=c, size=[w, h])
        elif tag == "arc":
            w, h = f("width"), f("height")
            s.update(type="arc", center=[f("x") + w / 2, f("y") + h / 2],
                     size=[w, h], start_deg=f("start"), sweep_deg=f("angle"))
        elif tag == "polygon":
            n = len([k for k in a if re.fullmatch(r"x\d+", k)])
            s.update(type="polyline" if a.get("closed") == "false" else "polygon",
                     points=[[f("x%d" % i), f("y%d" % i)] for i in range(1, n + 1)])
        elif tag == "text":
            m = re.search(r"[^,]+,([\d.]+)", a.get("font", ""))
            s = {"type": "text", "text": a.get("text", ""),
                 "baseline_left": [f("x"), f("y")],
                 "pt": float(m.group(1)) if m else None,
                 "italic": "Italic" in a.get("font", "")}
        out.append(s)
    return out


def shape_rows(sh):
    """図形を人が読む1行にする"""
    t = sh["type"]
    if t == "line":
        d = "%s → %s" % (pt(*sh["frm"]), pt(*sh["to"]))
        for k, jp in (("start", "始"), ("end", "終")):
            e = sh.get("ends", {}).get(k)
            if e:
                d += "　%s端 %s" % (jp, {v: k2 for k2, v in END_KEY.items()}
                                   .get(e["kind"], e["kind"]))
                d = d.replace("simple", "開いた矢").replace("triangle", "塗り三角")
        return "線", d
    if t == "rect":
        return "長方形", "左上 %s　%s × %s" % (pt(*sh["at"]), num(sh["size"][0]),
                                          num(sh["size"][1]))
    if t == "circle":
        return "円", "中心 %s　直径 %s" % (pt(*sh["center"]), num(sh["diameter"]))
    if t == "ellipse":
        return "楕円", "中心 %s　径 %s × %s" % (pt(*sh["center"]), num(sh["size"][0]),
                                           num(sh["size"][1]))
    if t == "arc":
        return "弧", ("中心 %s　径 %s × %s　開始 %g°　角度 %g°"
                     % (pt(*sh["center"]), num(sh["size"][0]), num(sh["size"][1]),
                        sh["start_deg"], sh["sweep_deg"]))
    if t in ("polygon", "polyline"):
        return ("多角形" if t == "polygon" else "折れ線",
                "　".join(pt(*p) for p in sh["points"]))
    if t == "text":
        return "文字", ("「%s」　ベースライン左端 %s　%s pt%s"
                      % (escape(sh["text"]), pt(*sh["baseline_left"]),
                         sh["pt"], "　斜体" if sh["italic"] else ""))
    return t, ""


def figure(path):
    """1M の格子・外形・端子の印つきの大きな SVG。**格子は原点に位相を合わせる**"""
    svg, (x0, y0, x1, y1), _, _ = S.body(path, True)
    _, _, _, g, _, _ = R.parse(path)
    hx, hy = float(g["hotspot_x"]), float(g["hotspot_y"])
    pad = 6
    vx, vy = x0 - pad, y0 - pad
    vw, vh = (x1 - x0) + pad * 2, (y1 - y0) + pad * 2
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g"'
            ' width="%g" height="%g" role="img">'
            '<defs><pattern id="g1" width="10" height="10"'
            ' patternUnits="userSpaceOnUse" x="%g" y="%g">'
            '<path d="M10 0H0V10" fill="none" stroke="currentColor"'
            ' stroke-width=".25" opacity=".22"/></pattern></defs>'
            '<rect x="%g" y="%g" width="%g" height="%g" fill="url(#g1)"/>'
            '<g stroke-linecap="round" stroke-linejoin="round"'
            ' stroke="currentColor" fill="none">%s</g></svg>'
            % (vx, vy, vw, vh, vw * 3.2, vh * 3.2, -hx, -hy,
               vx, vy, vw, vh, svg))


def thumb(path):
    g, (x0, y0, x1, y1), _, _ = S.body(path, False)
    p = 2
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g">'
            '<g stroke-linecap="round" stroke-linejoin="round"'
            ' stroke="currentColor" fill="none">%s</g></svg>'
            % (x0 - p, y0 - p, (x1 - x0) + p * 2, (y1 - y0) + p * 2, g))


def page(path, notes):
    prims, terms, dtexts, g, ja, info = R.parse(path)
    raw = io.open(path, encoding="utf-8").read()
    base = os.path.basename(path)[:-5]
    en = re.search(r'<name lang="en">([^<]*)</name>', raw)
    en = en.group(1) if en else ""
    W, H = int(g["width"]), int(g["height"])
    hx, hy = float(g["hotspot_x"]), float(g["hotspot_y"])
    src = re.search(r"JIS C 0617 / IEC 60617 ([0-9A-Za-z\-]+)", info)
    combo = re.search(r"JIS C 0617 の組合せ (.+)", info)
    sh = shapes(prims)
    mine = sorted(a for a, v in notes.items() if base in v[2])

    o = []
    w = o.append
    w('<nav class="crumb"><a href="index.html">図記号の一覧</a>'
      ' ／ <a href="notes.html">規格の注釈</a> ／ %s</nav>' % escape(base))
    w('<h1><span class="num">%s</span>%s</h1>' % (escape(base), escape(ja)))
    if en:
        w('<div class="en">%s</div>' % escape(en))
    if src:
        w('<p class="src">JIS C 0617 / IEC 60617 %s'
          '　—— 規格を参考に座標から描き起こしたもの</p>' % escape(src.group(1)))
    elif combo:
        w('<p class="src">JIS C 0617 の組合せ %s'
          '　—— 規格に番号の無い組合せ</p>' % escape(combo.group(1)))
    else:
        w('<p class="src">規格に基づかない、作図の都合の部品</p>')

    w('<div class="top"><div class="fig">%s<div class="legend">'
      '格子 1目 = 1M。灰の枠が外形、赤丸が端子、青が名前の欄</div></div>'
      % figure(path))
    w('<div class="spec"><table><tbody>')
    w("<tr><th>外形</th><td>%s × %s</td></tr>" % (num(W), num(H)))
    w("<tr><th>挿入基点</th><td>外形の左上から %s"
      "<br><span class=\"rule\">図形の座標はここが (0, 0)。y は下向き</span>"
      "</td></tr>" % pt(hx, hy))
    w("<tr><th>役割</th><td>%s<br><span class=\"rule\">QET の <code>link_type"
      "</code> = <code>%s</code></span></td></tr>"
      % (LINK.get(g.get("link_type", ""), "?"), escape(g.get("link_type", ""))))
    w("<tr><th>端子</th><td>%d</td></tr>" % len(terms))
    w("<tr><th>図形</th><td>%d</td></tr>" % len(sh))
    w("</tbody></table></div></div>")

    if mine:
        w("<h2>規格の注釈</h2>")
        w('<p class="rule">この図記号に付いている注釈。'
          "<b>要点はこちらの言葉でまとめたもの</b>で、原文ではない。"
          '<a href="notes.html">注釈の一覧</a>。</p>')
        for a in mine:
            title, gist, _ = notes[a]
            w('<div class="an"><h3><span class="id">'
              '<a href="notes.html#%s">%s</a></span>%s</h3>%s</div>'
              % (a, a, escape(title), rich(gist)))

    body_note = "\n".join(l for l in info.split("\n")
                          if not l.startswith("JIS C 0617")).strip()
    if body_note:
        w("<h2>図記号ファイルの覚え書き</h2>")
        w('<p class="rule"><code>.elmt</code> の <code>&lt;informations&gt;</code>'
          " から。<b>ここは書き換えても次に作り直すと消える。</b>"
          "書くなら下の「手で書く欄」か <code>.elmt</code> 側に。</p>")
        w('<div class="note">%s</div>' % escape(body_note))

    w('<h2>覚え書き<span class="pencil">手で書く欄</span></h2>')
    w(hand("memo", "使ってみて分かったこと、選ぶときの目安、注意など。"))

    # **「何を作るか」の2つは隣に置く。**単独でシンボルにするか、
    # 他と組み合わせて別の記号にするか —— 同じ種類の判断なので離さない。
    w('<h2>この図記号から何を作るか<span class="pencil">手で書く欄</span></h2>')
    w('<h3>CAD用シンボルにする／しない</h3>')
    w('<p class="rule">CAD 用のシンボル（QET の <code>.elmt</code>、'
      "DXF のブロックなど）を作るかどうか。<b>「しない」と書いてあれば作らなくてよい。"
      "</b>図（SVG）とこの頁は、作らないものにも用意する。<br>"
      "<b>「する。」か「しない。」で書き始めること。</b>道具がそこだけ見て数える。"
      "規格票から判断が付くときも、人が決めるときも、<b>書く場所はここ</b>。</p>")
    # **旧図記号（附属書A）は既定で「しない」。**新しい図面には使わないものなので、
    # CAD 用のシンボルにはしないと決めてある。頁に書いてあれば頁のほうが勝つ。
    old = re.match(r"\d\d-A", base) is not None
    w(hand("cad", "する／しない と、その理由",
           "<p><b>しない。</b>旧図記号。規格票の附属書Aに参考として載っている"
           "もので、新しい図面には使わない。</p>" if old
           else "<p><b>する。</b></p>"))
    w("<h3>組合せ・変種</h3>")
    w('<p class="rule">この図記号から派生させて作ったもの、これから作るもの。'
      "<b>組合せ</b>（他の番号と組んだもの）と<b>変種</b>"
      "（規格に無い色・段数・向きなどを足したもの）の両方をここに書く。"
      "作った先のファイル名も書いておくと、頁から頁へたどれる。</p>")
    w(hand("combine",
           "組合せの例：07-07-02（押しボタンの操作子）＋ 07-07-07（ブレーク接点）"
           " → 07-07-02_07-07-07　／　変種の例：色ちがい → 08-10-01__green"))

    w("<h2>他の形式に写すときの約束</h2>")
    w('<ul class="rule">')
    w("<li><b>1単位 = 0.1M = %gmm。</b>規格の作図モジュールは "
      "<b>M = %gmm</b></li>" % (UNIT_MM, MODULE_MM))
    w("<li><b>原点は挿入基点、y は下向き。</b>JSON の座標はすべて原点基準。"
      "y が上向きの CAD（DXF など）に写すときは <b>y を反転</b>する</li>")
    w("<li><b>弧の角度は 3時方向が0度、反時計回りが正。</b>"
      "SVG は逆向き。DXF の <code>ARC</code> は反時計回り正で同じ向きだが、"
      "終了角で指定するので <code>開始 + 角度</code> を渡す</li>")
    w("<li><b>円・楕円・長方形は軸平行のみ。</b>傾いたものは表せない</li>")
    w("<li>線の太さは <code>細 / 標準 / 太</code> の3段階。"
      "規格票の線は実測 0.10M ≒ %gmm</li>" % (0.10 * MODULE_MM))
    w("<li>破線の刻みは指定できない（Qt のペンそのまま 4:2）。"
      "規格票の刻みは 1.0M で、こちらは 0.6M</li>")
    w("<li>文字は <b>1em = pt × 96/72 単位</b>。書体は Liberation Sans"
      "（≒ Arial）。<b>規格票はセリフ斜体だが、書体は合わせないと決めてある</b></li>")
    w("</ul>")

    data = {"id": base, "name": {"ja": ja, "en": en},
            "standard": src.group(1) if src else None,
            "combination": combo.group(1).split(" ＋ ") if combo else None,
            "application_notes": mine,
            "units": {"unit_mm": UNIT_MM, "module_mm": MODULE_MM,
                      "y_axis": "down", "origin": "insertion_point",
                      "arc_angle": "ccw_from_east"},
            "outline": {"width": W, "height": H, "insertion": [hx, hy]},
            "qet_link_type": g.get("link_type"),
            "terminals": [{"x": x, "y": y, "orientation": o} for x, y, o in terms],
            # 図面で差し替わる文字。**座標は外接矩形の左上**（shapes の text は
            # ベースラインの左端。意味が違うので分けてある）
            "labels": [{"text": s2, "top_left": [x, y],
                        "source": a.get("text_from"),
                        "keep_upright": a.get("keep_visual_rotation") == "true"}
                       for x, y, s2, a in dtexts],
            "shapes": sh}
    w("<h2>機械可読（JSON）</h2>")
    w('<p class="rule">変換スクリプトはこの <code>&lt;pre id="data"&gt;</code> '
      "を読めばよい。<b>形式に依らない形に直してある</b>"
      "（円は中心と直径、弧は中心と角度）。</p>")
    w('<details><summary>開く</summary><pre id="data">%s</pre></details>'
      % escape(json.dumps(data, ensure_ascii=False, indent=1)))
    return "\n".join(o)


def notes_page(notes, have):
    o = []
    w = o.append
    w('<nav class="crumb"><a href="index.html">図記号の一覧</a> ／ 規格の注釈</nav>')
    w("<h1>規格の注釈</h1>")
    w('<p class="en">JIS C 0617 の各図記号には「注釈」（application note）の番号が'
      "付いていて、図記号の使い方の決めごとはそちらに書いてある。"
      "図だけ見ていると落とす。</p>")
    w('<div class="caution"><b>ここにあるのは原文ではありません。</b>'
      "規格票の本文を写すことはできないので、"
      "<b>図記号を描く・使うときに効いてくる点だけを、こちらの言葉で</b>"
      "まとめてあります。正確なところは番号で規格票を引いてください。</div>")
    for a in sorted(notes):
        title, gist, syms = notes[a]
        w('<div class="an" id="%s"><h3><span class="id">%s</span>%s</h3>%s'
          % (a, a, escape(title), rich(gist)))
        if syms:
            w('<div class="apply">付いている図記号（%d）—— ' % len(syms))
            w("".join('<a href="%s.html">%s</a>' % (s, s)
                      if s in have else '<span class="rule">%s </span>' % s
                      for s in syms))
            w("</div>")
        w("</div>")
    return "\n".join(o)


def index_names():
    """図記号番号 → 名称（規格票から採った索引が持っている）"""
    out = {}
    for part in (7, 8):
        f = os.path.join(P.STDDATA, "第%d部索引.tsv" % part)
        if not os.path.isfile(f):
            continue
        for line in io.open(f, encoding="utf-8"):
            c = line.rstrip("\n").split("\t")
            if len(c) >= 5 and c[0][0].isdigit():
                out[c[0]] = c[4]
    return out


def missing_rows(have):
    """規格には載っているが、まだ図の無いもの → [(番号, 名称)]

    **黙って落とさない。**一覧に無いと、描き忘れたのか決めて外したのかが
    分からなくなる。
    """
    return [(n, name) for n, name in sorted(index_names().items())
            if n not in have]


def stub_page(num, name, notes):
    """**まだ図の無い図記号の頁。**規格には載っているので頁だけ先に作る

    図が無くても、番号・名称・規格票のページ・付いている注釈は書けるし、
    **「CAD用シンボルにするか」を先に決めて書いておける。**
    描いたら図と諸元が入って、手で書いた欄はそのまま残る。
    """
    part = int(num[:2])
    pg = P.index(part).get(num)
    mine = sorted(a for a, v in notes.items() if num in v[2])
    o = []
    w = o.append
    w('<nav class="crumb"><a href="index.html">図記号の一覧</a>'
      ' ／ <a href="notes.html">規格の注釈</a> ／ %s</nav>' % escape(num))
    w('<h1><span class="num">%s</span>%s</h1>' % (escape(num), escape(name)))
    w('<p class="src">JIS C 0617 / IEC 60617 %s%s</p>'
      % (escape(num), "　—— 規格票 p.%d" % pg if pg else ""))
    w('<div class="caution"><b>まだ図がありません。</b>'
      "規格には載っているが、こちらでまだ描き起こしていないもの。"
      "描けば姿と諸元がこの頁に入る。<b>下の手で書く欄はそのまま残る。</b></div>")
    if mine:
        w("<h2>規格の注釈</h2>")
        w('<p class="rule">この図記号に付いている注釈。'
          "<b>要点はこちらの言葉でまとめたもの</b>で、原文ではない。"
          '<a href="notes.html">注釈の一覧</a>。</p>')
        for a2 in mine:
            title, gist, _ = notes[a2]
            w('<div class="an"><h3><span class="id">'
              '<a href="notes.html#%s">%s</a></span>%s</h3>%s</div>'
              % (a2, a2, escape(title), rich(gist)))
    w('<h2>覚え書き<span class="pencil">手で書く欄</span></h2>')
    w(hand("memo", "使ってみて分かったこと、選ぶときの目安、注意など。"))
    old = re.match(r"\d\d-A", num) is not None
    w('<h2>この図記号から何を作るか<span class="pencil">手で書く欄</span></h2>')
    w("<h3>CAD用シンボルにする／しない</h3>")
    w('<p class="rule">CAD 用のシンボル（QET の <code>.elmt</code>、'
      "DXF のブロックなど）を作るかどうか。<b>「しない」と書いてあれば作らなくてよい。"
      "</b><b>「する。」か「しない。」で書き始めること。</b></p>")
    w(hand("cad", "する／しない と、その理由",
           "<p><b>しない。</b>旧図記号。規格票の附属書Aに参考として載っている"
           "もので、新しい図面には使わない。</p>" if old
           else "<p><b>する。</b></p>"))
    w("<h3>組合せ・変種</h3>")
    w(hand("combine", "組合せ・変種を書く欄"))
    return "\n".join(o)


def index_page(items, skipped):
    o = []
    w = o.append
    w("<h1>JIS C 0617 図記号の一覧</h1>")
    w('<p class="en">1個ずつの諸元（外形・挿入基点・端子・図形の座標・文字の'
      "大きさ）へ飛べます。他の形式に写すのに要る数値はそちらにあります。"
      '　<a href="notes.html">規格の注釈</a></p>')
    w('<p><input id="q" placeholder="番号・名称でしぼり込む（例 接点／07-13／lamp）">'
      '<span class="hit" id="hit"></span></p>')
    cur = None
    for part, sec, secname, base, ja, th in items:
        key = (part, sec)
        if key != cur:
            if cur is not None:
                w("</div></section>")
            if cur is None or cur[0] != part:
                w('<h2 style="margin-top:2.4em">%s</h2>' % escape(part))
            w('<section><h3 id="%s">%s %s</h3><div class="grid">'
              % (escape(sec), escape(sec), escape(secname)))
            cur = key
        w('<a class="cell" href="%s.html" data-k="%s"><div class="box">%s</div>'
          '<div class="id">%s</div><div class="ja">%s</div></a>'
          % (base, escape((base + " " + ja).lower()),
             th, escape(base), escape(ja)))
    w("</div></section>")
    if skipped:
        w('<h2 style="margin-top:2.6em">まだ図の無いもの</h2>')
        w('<p class="en">規格には載っているが、まだ描いていないもの。'
          "<b>図と頁は、CAD用シンボルにしないものにも作ります。</b></p>")
        w('<div class="scroll"><table><thead><tr><th>図記号番号</th>'
          "<th>名称</th></tr></thead><tbody>")
        for n, name in skipped:
            w('<tr><td><a href="%s.html"><code>%s</code></a></td>'
              "<td>%s</td></tr>" % (escape(n), escape(n), escape(name)))
        w("</tbody></table></div>")
    return "\n".join(o)


def html(title, body, script=""):
    return ('<!doctype html>\n<html lang="ja"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            "<title>%s</title><style>%s</style></head><body>"
            '<div class="wrap">%s<footer>%s</footer></div>'
            "%s</body></html>\n"
            % (escape(title), CSS, body, FOOT,
               "<script>%s</script>" % script if script else ""))


def main():
    dst = os.path.join(P.REPO, "docs", "sym")
    os.makedirs(dst, exist_ok=True)
    # **手書きを先に全部読む。**消える頁のぶんも、消す前に読む
    keep = {f[:-5]: read_hand(os.path.join(dst, f))
            for f in os.listdir(dst) if f.endswith(".html")}
    for f in os.listdir(dst):                      # 消した記号の頁を残さない
        if f.endswith(".html"):
            os.remove(os.path.join(dst, f))
    svgdir = os.path.join(dst, "svg")
    os.makedirs(svgdir, exist_ok=True)
    notes = load_notes()
    kept = 0
    files = sorted(P.collection())
    have = {os.path.basename(p)[:-5] for p in files}
    items = []
    for p in files:
        base = os.path.basename(p)[:-5]
        sec = os.path.basename(os.path.dirname(p))
        secname = P.dirname_ja(os.path.dirname(p))
        _, _, _, _, ja, _ = R.parse(p)
        part = PARTS.get(base[:2], "規格に基づかない部品")
        # **姿だけの SVG も出す。**README や外の文書から `<img>` で貼るため
        io.open(os.path.join(svgdir, base + ".svg"), "w", encoding="utf-8",
                newline="\n").write(S.one(p))
        global _KEEP
        _KEEP = keep.get(base, {})
        io.open(os.path.join(dst, base + ".html"), "w", encoding="utf-8",
                newline="\n").write(
            html("%s %s — w-qet" % (base, ja), page(p, notes)))
        if _KEEP.get("_written"):
            kept += 1
        items.append((part, sec, secname, base, ja, thumb(p)))
    # **図の無いものにも頁を作る。**規格に載っているのに頁が無いと、
    # 描き忘れたのか決めて外したのかが分からず、判断の書き場所も無い
    stub = 0
    for n, name in missing_rows(have):
        _KEEP = keep.get(n, {})
        globals()["_KEEP"] = _KEEP
        io.open(os.path.join(dst, n + ".html"), "w", encoding="utf-8",
                newline="\n").write(
            html("%s %s — w-qet" % (n, name), stub_page(n, name, notes)))
        stub += 1
    io.open(os.path.join(dst, "index.html"), "w", encoding="utf-8",
            newline="\n").write(
        html("JIS C 0617 図記号の一覧 — w-qet",
             index_page(items, missing_rows(have)), JS_FILTER))
    io.open(os.path.join(dst, "notes.html"), "w", encoding="utf-8",
            newline="\n").write(
        html("規格の注釈 — w-qet", notes_page(notes, have)))
    print("書き出し: docs/sym/  記号 %d 枚 ＋ 目次 ＋ 注釈 %d 件（SVG も %d 枚）"
          % (len(items), len(notes), len(items)))
    print("  まだ図の無い頁 %d" % stub)
    print("  手書きを引き継いだ頁 %d" % kept)
    # **図の無い頁も「作った頁」に数える。**でないと消えたと誤って知らせる
    made = {i[3] for i in items} | {n for n, _ in missing_rows(have)}
    lost = sorted(set(keep) - made - {"index", "notes"})
    if lost:
        print("  **頁が消えるが手書きが入っていた:**", " ".join(lost))
    return 0


if __name__ == "__main__":
    sys.exit(main())
