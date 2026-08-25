# starrydata-mcp を Hugging Face Spaces に公開する(オーナー向け・所要目安10分)

準備はワーカー側で完了済み(`Dockerfile`・`/health`・レート制限・READMEの接続手順)。
このページの手順だけでSpaceを起動できる。詳しい背景・トラブルシュートは
[`docs/deploy/huggingface-spaces.md`](deploy/huggingface-spaces.md) を参照。

- [ ] **1. Hugging Faceアカウント作成**(既にあれば飛ばす)
  https://huggingface.co/join からメール登録。無料枠でよい。

- [ ] **2. Space作成**
  https://huggingface.co/new-space を開き、以下を設定して "Create Space":
  - **SDK**: `Docker`(Python/Gradio/Streamlit ではない)
  - **Space name**: 任意(例 `starrydata-mcp`)
  - **Visibility**: `Public`(無料枠でprivateにするには有料プランが必要)
  - Hardware: 既定の `CPU basic`(無料)のままでよい

- [ ] **3. このリポジトリをSpaceへ反映**
  作成直後のSpaceページに表示される git remote URL
  (`https://huggingface.co/spaces/<あなたのユーザー名>/<space名>`)を使い、
  ターミナルで:
  ```sh
  cd (このリポジトリのパス)
  git remote add hf-space https://huggingface.co/spaces/<あなたのユーザー名>/<space名>
  git push hf-space main
  ```
  (初回pushでHFのユーザー名/アクセストークンを聞かれたら、HFの
  [Settings → Access Tokens](https://huggingface.co/settings/tokens) で発行したトークンを
  パスワード欄に入力する)

- [ ] **4. ビルド完了を待つ**
  Spaceの "Building" ログが表示される。`starrydata-mcp ingest` の実行を含むため
  **15〜30分程度**かかる(初回のみ。以降の更新は再ビルド時に同様の時間がかかる)。
  ログが `Uvicorn running on http://0.0.0.0:7860` のような行で終われば起動完了。

- [ ] **5. (必要なら) Secrets / 環境変数の設定**
  基本構成では認証等は不要で、この手順は**通常スキップしてよい**。
  レート制限の既定値(60リクエスト/60秒/IP)を変更したい場合のみ、Spaceの
  "Settings → Variables and secrets" で以下を追加(Secretsではなく通常の変数でよい、
  機密情報ではないため):
  - `STARRYDATA_MCP_RATE_LIMIT_MAX`(既定 `60`)
  - `STARRYDATA_MCP_RATE_LIMIT_WINDOW_SECONDS`(既定 `60`)

- [ ] **6. 公開確認**
  ブラウザまたはターミナルで `/health` を確認:
  ```sh
  curl https://<あなたのユーザー名>-<space名>.hf.space/health
  ```
  `{"status": "ok", "read_only": true, ...}` が返ってくれば公開成功。
  `"status": "unhealthy"` や接続エラーの場合はビルドログを確認(§4)。

- [ ] **7. Claude Codeへの登録**
  ```sh
  claude mcp add --transport http starrydata https://<あなたのユーザー名>-<space名>.hf.space/mcp
  ```
  (末尾の `/mcp` を忘れないこと。`/health` ではなくこちら)

  claude.ai(Web版)で使う場合は Settings → Connectors →
  「カスタムコネクタを追加」から同じURL(`.../mcp`)を登録する。

- [ ] **8. 動作確認**
  Claude Code / claude.ai 側で「starrydataでBi2Te3の熱電特性を調べて」のように聞き、
  `search_materials` 等のツールが呼ばれてデータが返ってくることを確認すれば完了。

## 公開後にやっておくと良いこと(任意、10分の範囲外)

- README.md の「Connecting to a remote server」節にある `<space-url>` プレースホルダを、
  実際のURLに差し替えてコミット(司令塔に依頼すれば対応可能)。
- データを最新に保つには、Spaceの "Settings → Factory rebuild" で**手動で再ビルド**する
  必要がある(このイメージは自動更新されない設計。理由は
  [`docs/deploy/huggingface-spaces.md`](deploy/huggingface-spaces.md) §6「データの更新」参照)。
