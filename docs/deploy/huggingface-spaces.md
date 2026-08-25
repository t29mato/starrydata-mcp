# Hugging Face Spaces へのデプロイ手順(オーナー向け)

司令塔からの依頼(2026-08-25)に基づき準備した、`starrydata-mcp` をHugging Face Spacesの
無料枠でリモートMCPサーバーとして公開するための手順。**このリポジトリのワーカーはデプロイの
実行(Spaceの作成等)は行っていない** — Space作成・GitHubリポジトリのpublic化・HFアカウントの
操作はオーナー自身が行う必要がある操作のため。以下はそのための準備が完了した状態の手順書。

前提: `docs/design/architecture.md`(初期設計)、`docs/TECHNICAL_OVERVIEW.md`(全体解説)、
`docs/OPERATIONAL_CONCERNS.md`(運用上の懸念)を先に一読推奨。

## 1. 準備済みのもの

- `Dockerfile`(リポジトリルート): HF Spaces の **Docker SDK** 用。ビルド時に`starrydata-mcp
  ingest`を実行し、DuckDBファイルをイメージに焼き込む(起動時にingestを待たず即座に応答できる)。
  非rootユーザー(`user`, uid 1000)・ポート7860というHF Spacesの標準的な作法に従っている。
- `.dockerignore`: ビルドコンテキストを最小化(`.venv`・テスト・キャッシュ等を除外)。
- `starrydata-mcp serve --http :7860`: streamable-HTTPトランスポートでの起動モード
  (`src/starrydata_mcp/cli.py`)。既定はstdio(ローカル利用向け)のまま変更なし。
- `/health` エンドポイント: DuckDBが実際にクエリ可能かを確認するliveness/readinessチェック
  (`src/starrydata_mcp/interface/mcp_server.py`)。
- 簡易レート制限(`src/starrydata_mcp/interface/rate_limit.py`、既定 60リクエスト/60秒/IP、
  環境変数`STARRYDATA_MCP_RATE_LIMIT_MAX`・`STARRYDATA_MCP_RATE_LIMIT_WINDOW_SECONDS`で調整可)。

## 2. 前提条件(オーナー側で必要なもの)

- Hugging Faceアカウント(無料枠でよい)
- このリポジトリへのpush権限(現状private)。**Spaceを作る際にこのGitHubリポジトリをpublic化
  するかどうかは別問題**(HF Spaces自体は、リポジトリがprivateのままでも、Spaceのgitリモートに
  直接pushする形であれば動く。GitHub側のpublic化はIssue #15の判断と混同しないこと)

## 3. Space作成手順

1. https://huggingface.co/new-space でSpaceを新規作成
   - SDK: **Docker** を選択(Python/Gradio/Streamlit等ではない)
   - Space visibility: 公開したい範囲に応じて選択(無料枠はpublicのみ、privateは有料プランが必要な
     点に注意)
   - Hardware: 既定のCPU basic(無料)で問題ない想定(DuckDBの読み取りクエリのみでGPU不要)
2. 作成されたSpaceのgitリモートURLを控える
   (`https://huggingface.co/spaces/<owner>/<space-name>`)
3. このリポジトリの内容をSpaceのgitリモートにpush:
   ```sh
   git remote add hf-space https://huggingface.co/spaces/<owner>/<space-name>
   git push hf-space main
   ```
   (Docker SDKのSpaceは、リポジトリルートの`Dockerfile`を自動検出してビルドする)
4. ビルドログを確認: `RUN uv run starrydata-mcp ingest` の完了まで見届ける
   (公開データセットのダウンロード+約40万行の読み込みで**15〜30分程度**かかる見込み。
   `docs/TECHNICAL_OVERVIEW.md` §2.4参照)。ビルドが失敗する場合は§5参照。
5. ビルド完了後、Spaceが起動したら `https://<space-url>/health` にアクセスして
   `{"status": "ok", ...}` が返ることを確認する。

## 4. Space の README.md(HF側メタデータ)

HF SpacesはSpace側の`README.md`先頭のYAML frontmatterでSDK種別等を認識する。
Space作成UIで自動生成されるが、念のため想定される内容を記す(値はSpace作成時に埋める):

```yaml
---
title: Starrydata MCP
emoji: 🌟
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
license: mit
---
```

このリポジトリの`README.md`(プロジェクト本体の説明)とは別物であることに注意
(HF Spacesにpushする際、このリポジトリの`README.md`がそのままSpaceのREADMEとしても
使われるため、上記frontmatterを**このリポジトリのREADME.md先頭に追記するかどうかは
オーナー判断**。追記する場合はGitHub側の表示にも影響する点を考慮すること — 本タスクでは
リポジトリのREADME.mdにこのfrontmatterを追加していない)。

## 5. よくある失敗と対処

| 症状 | 想定原因 | 対処 |
|---|---|---|
| ビルド中に`ingest`がタイムアウト/失敗する | GitHub Releasesへのアクセスに問題、または一時的なネットワーク不調 | ビルドを再実行(`starrydata-mcp ingest`は冪等なので再実行は安全)。継続的に失敗する場合はHF Spacesのビルド環境からgithub.comへのアクセスに制限が無いか確認 |
| `/health`が503を返す | `dataset_meta`が空 = ingestがビルド時に完走していない | ビルドログでingestが成功しているか確認。イメージを作り直す |
| 起動はするがツール呼び出しがすぐ429になる | レート制限に複数クライアントが同時にかかっている、または既定値が厳しすぎる | `STARRYDATA_MCP_RATE_LIMIT_MAX`・`STARRYDATA_MCP_RATE_LIMIT_WINDOW_SECONDS`をSpaceの環境変数で調整 |

## 6. データの更新(重要な運用上の注意)

このDockerイメージは**ビルド時に1回だけ**ingestを実行する設計であり、コンテナ起動後に
自動で日次更新されるわけではない(§`docs/OPERATIONAL_CONCERNS.md`も参照)。
Starrydataの最新スナップショットを反映するには**Spaceの再ビルドが必要**
(HF SpacesのUIから "Restart this Space" ではなく "Factory rebuild" を選ぶか、
空コミットをpushして再ビルドをトリガーする)。この運用(手動/定期リビルド)を続けるか、
将来的にコンテナ内で定期ingestを行う仕組みに変更するかは別途司令塔判断とする
(本タスクのスコープ外)。

## 7. 公開後にやること

- README.md の「リモートMCPサーバーへの接続方法」セクション(本タスクで追加済み、
  プレースホルダURL)を、実際のSpace URLに差し替える。
- 実際のURLでClaude Code / claude.ai Integrations からの接続を再検証する
  (ローカルhttpモードでの検証はワーカー側で完了済み。実URLでの検証はデプロイ後に別途)。
