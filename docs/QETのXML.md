# QElectroTech の XML —— 実物で確かめたこと

QET の `.elmt`（図記号）と `.qet`（図面）の中身。**公式に詳しい解説が無い**ので、
実機（0.100.0 / Windows）で確かめたことをここにまとめる。

公式 wiki の [XML 仕様](https://qelectrotech.org/wiki_new/doc/xml_struct_elements)は
最新ページでも **「≥0.3」世代**で、0.100.0 とはかなり離れている。
[利用者向け文書](https://qelectrotech.github.io/qelectrotech-doc/)は操作の説明が主で、
XML の構造には踏み込んでいない。**だから読むのではなく、測って書いた。**

確かめ方は3つ。**推測を書かない。**

| 手 | 何が分かる |
|---|---|
| **同梱コレクション 8597 個の属性統計** | 何が必須で何が事実上廃止か。少数派の書き方 |
| **同梱の作例**（`C:\Program Files\QElectroTech\examples\`） | 機能が動いている状態のファイル。ただし**古い版で作られている**ので、そのまま真似ても動くとは限らない |
| **QET に保存させて読む** | いちばん確実。**推測が外れたときはこれで決着した**（下記） |

---

## いちばん大事な一般則

> **QET は派生する値を「編集したとき」に計算して保存する。
> 読み込んだときには計算し直さない。**

相互参照の位置、スレーブのラベル、フォリオ参照の参照先——どれも
`.qet` に**結果が書き込まれている**。リンクの指定だけ書いて値を空にしておくと、
**開いても何も出ない。**

`.qet` をコードから生成するときは、**QET が書くのと同じ形で値も書く**か、
**QET 側で一度編集させる**必要がある。ここを知らずに
「機能が壊れている」と3回読み違えた。

---

## `.elmt` —— 図記号の定義

```xml
<definition width="20" height="60" hotspot_x="10" hotspot_y="30"
            type="element" link_type="slave" version="0.100.0">
    <uuid uuid="{…}"/>
    <names><name lang="ja">a接点</name><name lang="en">Make contact</name></names>
    <informations>…</informations>
    <description>
        <line …/> <terminal …/> <dynamic_text …>…</dynamic_text>
    </description>
</definition>
```

- **座標の原点は hotspot。** `y` は下向き
- `width` / `height` は **10の倍数**（同梱8597個すべて）
- **`<uuid>` を変えない。** 変えると既にある `.qet` の参照が切れる。
  直すときは生成し直さず XML を書き換える

### link_type —— 部品の役割

| 値 | 何に使う |
|---|---|
| `simple` | ふつうの機器。それ自体で完結するもの |
| `master` | コイル・操作器。別の場所に接点を持つ側 |
| `slave` | その接点。ラベルをマスタから受け取る |
| `terminal` | 端子台部品（端子台プラグインが拾う） |
| `next_report` / `previous_report` | フォリオ参照（ページをまたぐ導体の続き） |
| `thumbnail` | 同梱コレクションに少数ある |

**「接点」と名が付いていても機器なら `slave` ではない。**
押しボタン・リミットスイッチ・温度スイッチは接点を内蔵して1つで完結するので `simple`。

### 図形

`line` `rect` `ellipse` `circle` `arc` `polygon` `text` と、`terminal`・`dynamic_text`。

- **`<circle>` は `x,y,diameter` で `x,y` は外接矩形の左上**（中心ではない）。
  同梱の円404個で確認：左上と解釈すると同心円になる組が18、中心と解釈すると0
- **`<arc>` の角度は 0度＝3時方向・正が反時計回り**（Qt の流儀）。
  SVG や Pillow は逆向きなので、描き出すときに反転が要る
- `polygon` は `closed="false"` なら折れ線
- `style` は `line-style` `line-weight` `filling` `color` を `;` で並べる
- `<line>` は端末装飾 `end1` `end2`（`simple` `triangle` `circle` `diamond`）を持てる

### 文字 —— `<text>` と `<dynamic_text>` は座標の意味が違う

| | 用途 | x,y の意味 | 回すと |
|---|---|---|---|
| `<text>` | 記号の一部（`Θ` `I >`） | **ベースラインの左端** | 一緒に倒れる |
| `<dynamic_text>` | ラベル欄・図面で書き換える値 | **外接矩形の左上** | `keep_visual_rotation` 次第 |

置き換えるときは **`y_上端 = y_ベースライン − 0.905 × em`**。
**`1em = ポイント数 × 96/72`**（Qt が pt を画素に直す比）。

```xml
<dynamic_text x="15" y="-30" text_from="ElementInfo" keep_visual_rotation="true"
              font="Liberation Sans,9,-1,5,50,0,0,0,0,0,Regular">
    <text></text>
    <info_name>label</info_name>
</dynamic_text>
```

| `text_from` | 中身 |
|---|---|
| `ElementInfo` | `<info_name>` が指す情報を表示。`label`（機器記号）が代表 |
| `UserText` | `<text>` の固定文字。図面上で書き換えられる |

- **ラベル（`ElementInfo`／`label`）は `keep_visual_rotation="true"`。**
  倒しても正立する。QET は true のとき文字の回転を「基準 − 親の回転」に置く。
  **属性を省いたときの既定も true**で、明示的に `false` と書いたときだけ倒れる
- **記号に文字の欄が無いと、ラベルは何も出ない。** マスタと結んでも同じ。
  図面上で自分で足すまで空のまま

### `<terminal>`

```xml
<terminal x="0" y="-30" orientation="n" name="1" type="Generic" uuid="{…}"/>
```

- **`uuid` `name` `type` は必須**（0.90以降 同梱全件）。`type` は `Generic`
- **並び順を後から変えない。** 出現順に id が振られ、既にある `.qet` の導体がずれる
- **導体は端子と端子の間にしか引けない。** 空中に線は引けない

---

## `.qet` —— 図面

```
<project>
  <properties>          プロジェクトの属性（タイトル・保存日時など）
  <newdiagrams>         **新しいフォリオの既定値。**既存のフォリオには効かない
      <border/> <inset/> <conductors/>
      <report label="%id-%l%c"/>      フォリオ参照の札に出す文字
      <xrefs><xref type="coil" slave_label="(%id-%l%c)" …/></xrefs>
      <conductors_autonums/> <folio_autonums/> <element_autonums/>
  <diagram>             フォリオ1枚
      <defaultconductor/>
      <elements>  置いた部品
      <conductors> 導体
      <inputs>    独立テキスト   <shapes> 矩形など
  <collection>          **部品定義の埋め込み**（図面1つで完結させるため）
```

### 置いた部品

```xml
<element type="embed://import/07-02-01.elmt" x="800" y="400" z="10"
         uuid="{…}" orientation="0" freezeLabel="false" prefix="">
    <terminals><terminal x="0" y="-26" id="0" orientation="0"/></terminals>
    <inputs />
    <links_uuids><link_uuid uuid="{相手の uuid}"/></links_uuids>
    <elementInformations>
        <elementInformation name="label" show="1">R1</elementInformation>
    </elementInformations>
    <dynamic_texts>…</dynamic_texts>
    <texts_groups />
</element>
```

> **空の `<dynamic_texts />` を書かない。**
> 書くと**部品定義側のラベル欄まで打ち消され**、文字の置き場所が無くなる。
> ラベルを省くときも枠だけは置く。**これで「スレーブのラベルが同期されない」と
> 読み違えた。手で描くと動くのに生成すると動かないときは、まず生成側を疑う。**

- `orientation` は 0/1/2/3（90度ずつ）
- 部品どうしの結び付きは `<links_uuids>`。**スレーブ側からマスタを指す**

### 導体

```xml
<conductor num="100" type="multi" element1="{…}" terminal1="{…}"
           element2="{…}" terminal2="{…}" displaytext="1" …/>
```

- **`num` が線番。** 画面では「導体の属性変更」の**「テキスト :」**欄
- 文字が出るのは **`type="multi"`（複線）**
- **分岐はジャンクション部品ではなく、同じ端子に2本目**をつなぐ

### ラベルと相互参照

**スレーブのラベルはマスタから同期される。** コイルを `R1` にすれば、
ラベルを書いていない接点にも `R1` が出る（記号に文字の欄があれば）。

接点に独自の文字を出したいときは `text_from="UserText"` にして
`<info_name>` を書かない。**日本の慣習の小文字**（コイル `R1` → 接点 `r1`）はこちら。
相互参照は `<links_uuids>` 側なので切れない。

位置は `<xref>` の `slave_label` / `master_label` で決まる。

| 変数 | 中身 |
|---|---|
| `%id` | **フォリオの位置（何枚目か）。常に値を持つ** |
| `%f` | フォリオ番号。**番号を振っていないと空**になる |
| `%l` `%c` | 行・列 |

**`%f` ではなく `%id` を使う。**`%f` が空だと括弧の中がほとんど消える。

### フォリオ参照（ページをまたぐ導体）

**動く。ただし順番がある。**

1. **先に** プロジェクトの属性 →「新しいフォリオ」→「フォリオ参照のラベル」を
   **`%id-%l%c`** にする
2. **そのあとで**フォリオを作る。**この設定は既存のフォリオには効かない**
3. 札を置き、相手の札とリンクする（右クリック →**「リンクする要素」**→ 相手をクリック）

**導体の線番は無関係。** 参照先は `<link_uuid>` と
`elementInformation name="label"` に保存される。

---

## 表示が壊れる条件

**どれも `.elmt` を絵にしただけでは分からない。** `tools/check_elmt.py` が全部弾く。

| やってしまうこと | QET でどうなるか |
|---|---|
| **ファイル名に日本語** | 記号名が**ファイル名（拡張子つき）に化ける** |
| **フォルダ名に日本語** | `qet_directory` が読めず、部品パネルで**フォルダ名が空欄** |
| **外形 10×10** | プレビューを作れない。ログに `QPainter::begin … engine == 0` |
| **文字が外形からはみ出す** | 動かしたとき**画面にゴミが残る**（再描画は外形の矩形だけ） |
| **外形が10の倍数でない** | 同梱8597個すべてが10の倍数。実装側の要求と見てよい |
| **破線の刻みを指定する** | できない。Qt のペンそのまま（DashLine 4:2） |

**QET はスタートメニューから起動する。** exe を直に叩くと
シンボル集・言語・図枠の場所を渡せず、**部品が0個**になり UI がフランス語になる。

ログは `%APPDATA%\qelectrotech\QElectroTech\<日付>.log`。
起動ごとに `Custom Elements count` が出るので、登録の結果はここで確かめられる。

---

## 公式仕様書と実物のちがい

同梱コレクション 8597 個の**属性の統計**と突き合わせた結果（図版ではない）。

**仕様書のまま今も正しい**

- `width` / `height` は **10の倍数** — 8597個すべてで成立
- 座標の原点は hotspot、`y` は下向き
- `<circle>` は `x,y,diameter` で `x,y` は外接矩形の左上
- `<arc>` は `x,y,width,height,start,angle`

**仕様書に無い／変わっている**

| 項目 | 仕様書（≥0.3） | 実際の 0.100.0 |
|---|---|---|
| `link_type` | 記載なし | 全件にある（上の表の7種） |
| `<terminal>` | `x y orientation` のみ | **`uuid` `name` `type` が必須**（0.90以降 全件） |
| `<definition>` の `orientation` | 必須のように書かれている | 事実上の廃止。8597個中 **1個** |
| ラベル | 記載なし | `<dynamic_text>`（25954箇所）が現行の仕組み |
| `<text>` の大きさ | `size` | `font="… ,9, …"`。`size` は50154個中35個の旧形式 |
| `color` | black / white | 12種以上（gray, red, blue, …） |
| `filling` | none / white / black | 12種以上 |
| `line-style` | normal / dashed | ＋ `dotted` `dashdotted` |
| `line-weight` | normal / thin / none | ＋ `hight` `eleve` |
| 文字の欄 | 記載なし | 古い記号は `<input>`（0.3世代）。**同梱の作例はこちら** |

> 端子が10グリッド上に乗っているのは同梱コレクションで **58%** しかない。
> guidelines の「10単位グリッド、最初の端子を0に」は**守られていない規則**。
> こちらは守る（[寸法基準.md](寸法基準.md)）。

---

## 関連

| | |
|---|---|
| [寸法基準.md](寸法基準.md) | 記号を描くときの寸法・端子・ラベルの約束 |
| [ツール.md](ツール.md) | `tools/` の使い方。読み書きの実装はここ |
| `.claude/skills/jis-symbol/` | 図記号を描き起こすときの手順 |
| `.claude/skills/qelectrotech/` | 図面を描く・症状から原因を探すとき |
