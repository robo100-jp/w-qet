# -*- coding: utf-8 -*-
"""点検メモをブラウザで書く —— 保存すると `docs/点検メモ.md` が直接書き換わる

  py -3 tools/memo_server.py

局所（127.0.0.1）に立ててブラウザを開く。記号の姿を見ながら「済」と
「気づいたこと」を書き、保存すると **`docs/点検メモ.md` がその場で書き換わる**。
Excel のような書き出し・取り込みが要らず、**git の差分もそのまま出る**。

**外に開かない。** `127.0.0.1` にだけ束ねる。書き込みは `docs/点検メモ.md` の
1ファイルだけで、それ以外には触らない。

止めるのは Ctrl+C。標準ライブラリだけで動く（追加のインストールは要らない）。
"""
import http.server
import json
import os
import re
import sys
import threading
import webbrowser
from urllib.parse import unquote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checklist as K                                       # noqa: E402
import paths as P                                           # noqa: E402
import svg_elmt as S                                        # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")

HOST, PORT = "127.0.0.1", 8731

PAGE = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<title>点検メモ — w-qet</title>
<style>
:root { color-scheme: light; }
* { box-sizing: border-box; }
body { margin:0; font:14px/1.6 "Meiryo","Yu Gothic",sans-serif; color:#1a1a1a;
       background:#fafafa; }
header { position:sticky; top:0; z-index:5; background:#fff; padding:10px 16px;
         border-bottom:1px solid #ddd; display:flex; gap:12px; align-items:center;
         flex-wrap:wrap; }
h1 { font-size:16px; margin:0 8px 0 0; }
input[type=search] { padding:6px 10px; border:1px solid #bbb; border-radius:4px;
                     width:220px; font:inherit; }
button { padding:6px 14px; border:1px solid #888; border-radius:4px; background:#fff;
         font:inherit; cursor:pointer; }
button.primary { background:#1a5fb4; color:#fff; border-color:#1a5fb4; }
button:disabled { opacity:.45; cursor:default; }
#status { color:#555; }
#status.dirty { color:#b03000; font-weight:bold; }
main { padding:0 16px 60px; }
h2 { font-size:15px; margin:26px 0 6px; padding-bottom:4px;
     border-bottom:2px solid #333; }
table { border-collapse:collapse; width:100%; background:#fff; }
td { border-bottom:1px solid #e6e6e6; padding:6px 8px; vertical-align:middle; }
td.fig { width:120px; text-align:center; }
td.fig svg { max-width:110px; max-height:64px; height:auto; }
td.num { width:110px; font-family:Consolas,monospace; white-space:nowrap; }
td.name { width:300px; }
td.done { width:52px; text-align:center; }
td.memo { }
td.memo textarea { width:100%; min-height:32px; padding:5px 7px; font:inherit;
                   border:1px solid #ccc; border-radius:3px; resize:vertical;
                   background:#fffdf2; }
tr.has textarea, tr.has td.num { background:#fff8e0; }
input[type=checkbox] { width:18px; height:18px; }
.hide { display:none; }
</style></head><body>
<header>
  <h1>点検メモ</h1>
  <input type="search" id="q" placeholder="番号・名称で絞る">
  <label><input type="checkbox" id="only"> 書いた行だけ</label>
  <button class="primary" id="save" disabled>保存（Ctrl+S）</button>
  <span id="status">docs/点検メモ.md に書きます</span>
</header>
<main id="main"></main>
<script>
const DATA = __DATA__;
const main = document.getElementById('main');
const stat = document.getElementById('status');
const save = document.getElementById('save');
let dirty = false;

function mark() {
  dirty = true; save.disabled = false;
  stat.textContent = '未保存'; stat.className = 'dirty';
}

let sec = null, tbl = null;
for (const it of DATA) {
  if (it.sec !== sec) {
    sec = it.sec;
    const h = document.createElement('h2'); h.textContent = sec; main.appendChild(h);
    tbl = document.createElement('table'); main.appendChild(tbl);
  }
  const tr = document.createElement('tr');
  tr.dataset.key = (it.num + ' ' + it.name).toLowerCase();
  tr.innerHTML =
    '<td class="fig">' + it.svg + '</td>' +
    '<td class="num"></td><td class="name"></td>' +
    '<td class="done"><input type="checkbox"></td>' +
    '<td class="memo"><textarea rows="1"></textarea></td>';
  tr.querySelector('.num').textContent = it.num;
  tr.querySelector('.name').textContent = it.name;
  const cb = tr.querySelector('input'), ta = tr.querySelector('textarea');
  cb.checked = !!it.done; ta.value = it.memo;
  const touch = () => {
    tr.classList.toggle('has', cb.checked || ta.value.trim() !== '');
    mark();
  };
  cb.addEventListener('change', touch);
  ta.addEventListener('input', touch);
  tr.classList.toggle('has', cb.checked || ta.value.trim() !== '');
  tr.dataset.num = it.num;
  tbl.appendChild(tr);
}

function collect() {
  const out = {};
  for (const tr of document.querySelectorAll('tr[data-num]')) {
    out[tr.dataset.num] = [tr.querySelector('input').checked ? '\\u2714' : '',
                           tr.querySelector('textarea').value];
  }
  return out;
}

async function doSave() {
  stat.textContent = '保存中…'; stat.className = '';
  try {
    const r = await fetch('/save', {method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(collect())});
    const j = await r.json();
    if (!r.ok || !j.ok) throw new Error(j.error || r.statusText);
    dirty = false; save.disabled = true;
    stat.textContent = '保存しました（書き込み ' + j.written + ' 行）';
  } catch (e) {
    stat.textContent = '保存できませんでした: ' + e.message;
    stat.className = 'dirty';
  }
}
save.addEventListener('click', doSave);
addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 's') { e.preventDefault(); doSave(); }
});
addEventListener('beforeunload', e => { if (dirty) e.preventDefault(); });

function filt() {
  const q = document.getElementById('q').value.trim().toLowerCase();
  const only = document.getElementById('only').checked;
  for (const tr of document.querySelectorAll('tr[data-num]')) {
    const ok = (!q || tr.dataset.key.includes(q))
            && (!only || tr.classList.contains('has'));
    tr.classList.toggle('hide', !ok);
  }
  for (const t of document.querySelectorAll('table')) {
    const any = [...t.rows].some(r => !r.classList.contains('hide'));
    t.classList.toggle('hide', !any);
    t.previousElementSibling.classList.toggle('hide', !any);
  }
}
document.getElementById('q').addEventListener('input', filt);
document.getElementById('only').addEventListener('change', filt);
</script></body></html>
"""


def build_page():
    """記号の姿を埋め込んだ1枚を組み立てる

    **SVG は貼り込む。** 別ファイルとして取りに来させると、
    このサーバが `docs/` を配る役も持つことになる。**書くのは1ファイルだけ**
    という約束を保ちたいので、読み取りもここで済ませる。
    """
    items = K.rows()
    keep, src = K.read_notes()
    out, cur = [], ""
    for ja, path in items:
        if ja:
            cur = ja
        base = os.path.basename(path)[:-5]
        _, _, name, _ = S.body(path, False)
        done, memo = keep.get(base, ("", ""))
        svg = S.one(path, scale=2)
        svg = re.sub(r"<\?xml[^>]*\?>\s*", "", svg)     # HTML に貼るので宣言は外す
        out.append({"sec": cur, "num": base, "name": name,
                    "done": bool(done), "memo": memo, "svg": svg})
    return PAGE.replace("__DATA__", json.dumps(out, ensure_ascii=False)), src


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass                                    # 1行ごとのアクセス記録は要らない

    def _send(self, code, body, ctype="text/html; charset=utf-8"):
        b = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        if unquote(self.path.split("?")[0]) != "/":
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        page, src = build_page()
        print("  開いた（%s から読んだ）" % src)
        self._send(200, page)

    def do_POST(self):
        if self.path != "/save":
            self._send(404, '{"ok":false}', "application/json")
            return
        try:
            n = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(n).decode("utf-8"))
            keep = {k: (str(v[0]), str(v[1])) for k, v in data.items()}
            items = K.rows()
            open(K.MEMO, "w", encoding="utf-8").write(K.build_md(items, keep))
            written = sum(1 for v in keep.values() if v[0] or v[1].strip())
            print("  保存した（書き込み %d行）→ %s"
                  % (written, os.path.relpath(K.MEMO, P.REPO)))
            self._send(200, json.dumps({"ok": True, "written": written}),
                       "application/json")
        except Exception as ex:                 # noqa: BLE001
            print("  保存に失敗:", ex)
            self._send(500, json.dumps({"ok": False, "error": str(ex)}),
                       "application/json")


def main():
    os.makedirs(K.SYM, exist_ok=True)
    url = "http://%s:%d/" % (HOST, PORT)
    srv = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    print("点検メモを開きます:", url)
    print("書き込み先:", os.path.relpath(K.MEMO, P.REPO))
    print("止めるのは Ctrl+C")
    threading.Timer(.5, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n止めました")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
