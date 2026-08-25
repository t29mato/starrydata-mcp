# CLAUDE.md — starrydata-mcp 開発ガイド

このファイルは、starrydata-mcp に対してコードを書く人間・AIエージェント(Claude Code含む)
向けのガイドです。プロジェクトの目的・設計方針・開発規約をまとめています。

## プロジェクトの目的

材料科学データベース **Starrydata** の公開データをAIエージェントから使えるようにする
**MCPサーバー** を作る。

### アーキテクチャ上の絶対制約

- **Starrydata本番DB・本番APIには一切接続しない**。本プロジェクトは公式に公開配布されている
  データセットのみを利用する方針とする。
- データ源は**公開配布されているデータセットZIP(約130MB、日次更新)のみ**。1日1回取得→
  ローカルDB(DuckDB)に自動変換→MCPサーバーはそのDBだけを参照する。実際の取得元・スキーマ・
  パイプライン設計は `docs/design/architecture.md` を参照。
- リアルタイム性は不要。日次更新で十分。
- データ登録者向けの本番DB直結機能はスコープ外(将来の別案)。

## 設計・品質方針(必須)

- **設計ファースト**: アーキテクチャに関わる変更・技術選定の変更は、実装着手前に
  `docs/design/` に設計(取得パイプライン・DBスキーマ・MCPツール定義一覧・依存方向、
  Mermaid図)を書き、レビューを経てから実装する。
- **クリーンアーキテクチャ**: ドメイン層(データモデル・検索ロジック)はMCP SDK・DB実装に
  依存しない。依存は常に内側へ(`interface`/`infrastructure` → `application` → `domain`)。
  `import-linter` をCIに組み込み、レイヤー違反でCIを落とす。設定を緩める場合は理由を
  `docs/design/` に書き、レビューを経ること。層構成の詳細は
  `docs/TECHNICAL_OVERVIEW.md` §4を参照。
- **TDD**: テスト先行。カバレッジ目標はドメイン/アプリケーション層でほぼ100%、リポジトリ
  全体でCIゲート85%(`pyproject.toml`の`--cov-fail-under`参照)。詳細は
  `docs/TECHNICAL_OVERVIEW.md` §7.1。
- **LLMO**: READMEに機械可読な1文説明。MCPツールのdescriptionはエージェントが読んで
  使い方を誤らない品質にする(これ自体が製品価値)。ツール設計の思想は
  `docs/TECHNICAL_OVERVIEW.md` §5を参照。
- **ライセンス**: Starrydataのデータは独自調査によりCC BY 4.0であることを確認済み
  (`docs/design/architecture.md` §1.3、NIMS Materials Data Repository公式ページで確認)。
  ただし変換済みDBそのものの再配布はせず、「利用者(または本サーバーの運用者)がデータセットを
  取得して自分でDuckDBに変換する」設計を維持している。

## AIエージェントへの補足

- lintの機械的な修正・テストログの要約・README/リリースノートの下書きのような単純作業は、
  対応できる環境であれば軽量なサブエージェント/モデルに委譲してよい。設計判断は委譲しない。
- 判断に迷う設計変更(技術選定・レイヤー構成の変更など)は、実装を進める前に
  `docs/design/` に検討内容を書き、レビューを経ること。
- 実データ(公開データセット)を使った検証は、fixtureだけでは見つからない不具合を洗い出せる
  ことが実際にあった(`docs/design/architecture.md` §5、`docs/TECHNICAL_OVERVIEW.md` §6参照)。
  設計・実装の節目では可能な範囲で実データでの検証を行うことを推奨する。

## ブランチ・PR運用

- mainへの直接pushは避け、featureブランチ→PRを基本とする。マージにはメンテナのレビューを
  経ること。
- push・PR作成前に、ローカルで `uv run pytest`・`uv run ruff check .`・`uv run mypy`・
  `uv run lint-imports` がgreenであることを確認する。コマンド一覧は `AGENTS.md` を参照。
- タグ・GitHub Release・PyPI公開・破壊的なCI設定緩和にはメンテナの承認が必要。

## 開発コマンド・アーキテクチャ規約の詳細

ビルド・テスト・lint・型チェックの具体的なコマンドは `AGENTS.md` を参照。技術的な背景
(なぜDuckDBか、なぜこの8ツール構成か、実データ検証で見つかった不具合とその対処など)は
`docs/TECHNICAL_OVERVIEW.md` を参照。
