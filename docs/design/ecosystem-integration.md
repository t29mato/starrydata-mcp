# エコシステム連携調査: deep-digitizer の学習データ取得経路として starrydata-mcp は使えるか

司令塔依頼(2026-08-21)への回答。**実装はしていない、調査と設計記録のみ**。
`starrydata-mcp(データ) → deep-digitizer(モデル) → real-chart-bench(評価)` という
エコシステム構想に対し、実際に deep-digitizer が今どうStarrydataデータを取得しているかを
コードベースから確認し、MCPツール経由への置き換え可否を評価した。

結論を先に書く: **現状の8ツールでは置き換えられない**。理由は「機能が足りない」というより
**「用途がそもそも違う」**ため(§3)。ただし、置き換えではなく**別の形での連携価値**は明確にある(§4)。
副次的に、3プロジェクトが同じ上流データを独立に再ダウンロードしている重複も見つかった(§5)。

---

## 1. 調査対象

- `~/herd/deep-digitizer/`(ワークツリー、読み取りのみ)
- `~/herd/real-chart-bench/`(ワークツリー、読み取りのみ)— deep-digitizerが実際に依存している
  データの実体はこちら側にあることが調査の過程で判明したため、合わせて確認した。

## 2. deep-digitizer の現状のデータ取得経路

### 2.1 探索段階(`scripts/data_exploration/`)

`download_starrydata.py` が **starrydata-mcpと全く同じ配布元**(GitHub Releases,
`starrydata/starrydata_datasets`, tag `latest`)から `all_papers.csv.gz` /
`all_samples.csv.gz` / `all_curves.csv.gz` / `manifest.json` を直接ダウンロードし、
`data/starrydata/`(gitignore対象)に保存している。スクリプト冒頭のコメントに「Figshareは
bot拒否と見られる403を返すため、実体であるGitHub Releasesから取得する」という、
starrydata-mcpの設計調査(`docs/design/architecture.md` §1.4)と**全く同じ結論**が
独立に書かれている。ダウンロード自体はSHA256検証・冪等性チェック・ロック等を持たない
素朴な実装(`urllib.request`で直接書き込むだけ)。

`explore_starrydata.py` はこのCSVに対して pandas で**全件のgroupby・null率・重複キー検出・
クロスリンク整合性チェック**を行う探索スクリプト(例: `curves.groupby("figure_id").size()`,
`curves["project_names"].str.contains(...)`)。

### 2.2 学習データ構築段階(`scripts/v0_training/prepare_data.py`) — 実際の本番経路

探索スクリプトとは別に、実際にモデルへ渡す学習データを組み立てる`prepare_data.py`は
**deep-digitizer自身がダウンロードしたCSVを使っていない**。代わりに:

1. `real-chart-bench/data/manifest/v0/figures.json`(`split: "public"` / `"held_out"`の
   ラベル付き、real-chart-bench独自のベンチマーク管理データ)を読む
2. `real-chart-bench/data/cache/ThermoelectricMaterials_curves.csv.gz`
   (real-chart-bench自身がGitHub Releasesから**プロジェクト分割版**をダウンロードして
   キャッシュしたもの)を読む
3. 両者を `(SID=paper_id, figure_id)` で内部結合(pandas merge)し、`held_out`が
   混入していないかを機械的にチェックしてから学習レコードを組み立てる

つまり実際の依存関係は
`GitHub Releases → real-chart-bench(collect_v0_dataset.py, §2.3) → data/cache/*.csv.gz
→ deep-digitizer(prepare_data.py)` であり、**deep-digitizer独自のダウンロード経路
(2.1)は探索用途にしか使われていない**。

### 2.3 real-chart-bench側の取得経路(deep-digitizerが実際に依存する実体)

`scripts/collect/collect_v0_dataset.py` が同じくGitHub Releasesから
`ThermoelectricMaterials_{papers,curves}.csv.gz` を直接ダウンロードし
(`RELEASE_BASE = "https://github.com/starrydata/starrydata_datasets/releases/download/latest"`)、
`src/real_chart_bench/adapter/starrydata_csv.py` でCSV行をパースする。ただし、これは
収集パイプラインの**一部品にすぎない**: 同じスクリプト内でOpenAlex経由のライセンス分類、
PDF取得、PDFからの図画像抽出まで一括して行っており、Starrydataの数値データ(x/y曲線)は
そのうちの1入力でしかない。`scripts/pilot/phase3_collect_cc_by_batch.py` も同じ
`starrydata_csv`アダプタと同じダウンロードURLを独立に使っている。

## 3. MCPツール経由への置き換え評価: なぜ現状の8ツールでは無理か

### 3.1 用途のミスマッチ

starrydata-mcpの8ツールは design doc §5 の通り「AIエージェントが対話的に検索→絞り込み→
取得する」ことを前提に設計されている(`limit`既定20、`get_curve_data`は「目安20件以内」を
description内で明示)。一方、deep-digitizer/real-chart-benchが必要としているのは
**プロジェクト単位の全件バルク取得**(ThermoelectricMaterials全体で curves 155,758件、
papers・samplesも同程度の規模)。これは設計思想が根本的に異なる。

### 3.2 具体的な障害

| 障害 | 詳細 |
|---|---|
| ページ数が非現実的 | `search_curves`の既定`limit=20`のまま155,758件を取得すると**7,788回**のツール呼び出しが必要。これはAIエージェントの1セッションでは非現実的 |
| `limit`に上限が無い(別の問題として) | 現行実装は`search_curves`/`search_papers`等の`limit`引数を検証・上限クランプしていない。理論上は`limit=200000`のような値を渡せば1回で返るが、これはツールの設計意図(軽量なサマリを少数返す)に反する誤用であり、想定した使い方ではない |
| `search_curves`はx/y配列を返さない | 曲線本体は`get_curve_data`で別途取得する設計(§5.1のsearch→narrow→fetch思想通り)。バルク取得ではこの2段階が全件分必要になり、往復回数がさらに倍増する |
| MCP(JSON-RPC/stdio)はバルク転送に非効率 | 234,390件・x/y配列込みのデータをJSON構造でシリアライズしてやり取りするのは、gzip圧縮CSV(該当プロジェクトのみで数MB)を1回ダウンロードするのに比べて明らかに遅く、メモリ効率も悪い |
| プロジェクト全件エクスポート用のツールが無い | 「`<Project>_curves.csv.gz`相当を1回でエクスポートする」ツールはそもそも存在しない(§4.2で設計候補として記録) |
| 曲線データ以外の依存がスコープ外 | real-chart-benchの収集パイプラインはOpenAlexライセンス分類・PDF取得・図画像抽出も内包しており、これらはstarrydata-mcpのミッション(Starrydataの数値データをエージェントから使えるようにする)の範囲外。曲線データ部分を置き換えられたとしても、パイプライン全体の代替にはならない |

### 3.3 結論

**現状の8ツールをそのまま使ってdeep-digitizerの学習データ取得経路を置き換えることは
実用上不可能**。ツールが「壊れている」のではなく、「対話的エージェント向けツール」と
「学習データの一括ETL」は要求される性能特性(スループット・転送単位)が違いすぎる。

---

## 4. それでも見出せる連携価値

### 4.1 対話的な検証・エラー分析での価値(置き換えではなく補完)

deep-digitizerの`docs/experiments/*.md`や real-chart-benchの評価作業では、
「この特定の図・特定の曲線について正解データを確認したい」という**単発・対話的な参照**が
発生しうる(例: モデルの誤予測を1件ずつ確認する際に「このcurve_idの正解x/yは?」
「この論文の他の曲線は?」を聞く)。これはまさにstarrydata-mcpの`get_sample_detail`・
`get_curve_data`・`search_papers`が想定する使い方そのものであり、**AIエージェントを介した
エラー分析ワークフローで実際に使える**(現状これを行う手段が両プロジェクトに無い)。

### 4.2 「ツールの追加」ではなく「ingestパイプラインの共有」による重複排除(§5参照)

3プロジェクトが独立に同じGitHub Releasesファイルを再ダウンロード・再パースしている
(§5)。この重複を解消する最も筋の良い統合点は、新しいMCPツールを増やすことではなく、
**starrydata-mcpのDuckDB成果物(`~/.cache/starrydata-mcp/starrydata.duckdb`)や
`ingest`の頑健な取得ロジック(SHA256検証・冪等性・ロック・atomic rename、
`docs/TECHNICAL_OVERVIEW.md` §2参照)を、deep-digitizer/real-chart-bench側が
(MCPプロトコルを介さず)ライブラリ的に直接再利用すること**である。これらは
AIエージェントではなく決定的なPythonバッチ処理なので、MCP経由である必然性が無い。

## 5. 副次的な発見: 3プロジェクトの重複ダウンロード

| プロジェクト | ファイル | 取得内容 |
|---|---|---|
| starrydata-mcp | `infrastructure/ingestion/downloader.py` | `all_{papers,samples,curves}.csv.gz` + `manifest.json`(全ドメイン統合版) |
| deep-digitizer | `scripts/data_exploration/download_starrydata.py` | 同上(探索用途のみ、本番経路では未使用) |
| real-chart-bench | `scripts/collect/collect_v0_dataset.py`, `scripts/pilot/phase3_collect_cc_by_batch.py` | `ThermoelectricMaterials_{papers,curves}.csv.gz`(プロジェクト分割版) |

いずれも**同一のGitHub Releasesエンドポイント**(`starrydata/starrydata_datasets`)へ
独立にアクセスしており、SHA256検証・冪等性・エラーハンドリングの完成度もバラバラ
(starrydata-mcpが今回のバグ修正で最も頑健)。実害は今のところ無い(アクセス頻度も低く
GitHub側への負荷は問題にならない規模)が、**同じ取得ロジックを3箇所で保守している**のは
非効率であり、将来アップストリームのスキーマが変わった際(`docs/OPERATIONAL_CONCERNS.md` §2)
に3箇所それぞれで対応が必要になるリスクがある。

## 6. 設計として記録する不足機能(実装はしない)

将来、本当に「MCPサーバーを学習データ取得の正式経路にする」ことを目指す場合の設計候補。
優先度・要否は司令塔判断。

### 候補A: バルクエクスポートはMCP「ツール」ではなくCLI/ライブラリとして提供する(推奨)

新しいMCP toolとしてではなく、`starrydata-mcp`のCLIに
`starrydata-mcp export --project ThermoelectricMaterials --out ./curves.parquet`
のようなサブコマンドを足す案。あるいはさらにシンプルに「ローカルDuckDBファイルのパスを
ドキュメントで案内し、deep-digitizer/real-chart-bench側が`duckdb`パッケージで直接SQLを
発行する」だけでも十分(DuckDBファイルは単一ファイルで読み取り専用アクセスなら競合しない)。
§3.2の性能上のミスマッチ(MCP/JSON-RPCはバルク転送に不向き)を根本的に回避できる。

### 候補B: MCPツールとして提供するならリソース(Resource)を使う

どうしてもMCPプロトコル経由にこだわるなら、`tool`ではなくMCPの`resource`
(URIで参照するバイナリ/大容量データ向けのプリミティブ)として
`starrydata://export/ThermoelectricMaterials/curves.csv.gz`のようなリソースを公開し、
クライアントがストリームで取得する設計が考えられる。ただし現行のMCP SDK(`mcp` 2.0)での
resource実装コスト・エージェント側の対応状況は未調査であり、候補Aより優先度は低い。

### 候補C(参考、非推奨): `search_curves`/`search_papers`の`limit`に明示的な上限を設ける

バルク用途に転用されることを防ぐ意味では、`limit`に妥当な上限(例: 500)を設ける方が
ツールの設計意図に忠実だが、これは「バルク取得を可能にする」候補ではなく逆に
「対話的ツールとしての誤用を防ぐ」ための改善であり、本調査とは別に品質改善として
検討する価値がある(§3.2で触れた既存の未対応ギャップ)。

## 7. 推奨

- deep-digitizer/real-chart-benchの学習データ取得経路をMCPツール呼び出しに**置き換えることは
  推奨しない**(§3)。
- 3プロジェクトの重複ダウンロードは、starrydata-mcpの`ingest`ロジック(または成果物の
  DuckDBファイル)を**ライブラリ/共有データとして**再利用する形での統合を検討する価値がある
  (§4.2、§6候補A)。ただしこれはstarrydata-mcp側のスコープ変更(CLIへのexportサブコマンド追加等)
  を伴うため、司令塔判断・別タスクとして起票することを推奨する。
- MCPサーバーとしての価値は「バルク学習データ供給」ではなく、**AIエージェントを介した
  対話的なデータ探索・正解データ検証**(モデル開発時のエラー分析、評価結果のスポットチェック等)
  にある、という位置づけが実態に即している。
