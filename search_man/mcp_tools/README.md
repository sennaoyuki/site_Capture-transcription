# Claude Code MCP 連携手順

## 1. 実行スクリプトの登録
Claude Code の `config.json`（例: `~/Library/Application Support/Claude/code/config.json`）で `toolConfigurations` に以下の設定を追加してください。

```jsonc
{
  "id": "run_full_pipeline",
  "label": "LP文字起こし + 分析プロンプト生成",
  "description": "run_full_pipeline.py を呼び出して文字起こしと analysis_request.md を自動生成します。",
  "type": "command",
  "properties": {
    "command": "/bin/bash",
    "args": [
      "/Users/hattaryoga/Desktop/リスティング広告抜き出し/マウスピース矯正/mcp_tools/run_full_pipeline.sh",
      "{{url}}",
      "{{keyword}}",
      "{{conversion_goal}}"
    ]
  },
  "inputs": [
    { "name": "url", "label": "URL" },
    { "name": "keyword", "label": "検索キーワード" },
    { "name": "conversion_goal", "label": "コンバージョン目標" }
  ]
}
```

## 2. プロンプト送信用ツール
合わせて、生成済みの `analysis_request.md` を会話に貼り付けるツールを追加します。

```jsonc
{
  "id": "post_analysis_request",
  "label": "最新分析プロンプトを送信",
  "description": "output/latest/analysis_request.md の内容を会話に投稿します。",
  "type": "command",
  "properties": {
    "command": "/bin/bash",
    "args": [
      "/Users/hattaryoga/Desktop/リスティング広告抜き出し/マウスピース矯正/mcp_tools/post_analysis_request.sh"
    ]
  },
  "outputs": [
    { "type": "message", "role": "user" }
  ]
}
```

## 3. 使い方
1. Claude Code で `LP文字起こし + 分析プロンプト生成` ツールを実行し、URL・キーワード・コンバージョン目標を入力します。（URL の代わりに URL 一覧ファイルを指定したい場合は、コマンド引数を `--url-list <ファイル>` 形式に変更してツール登録を調整してください。）Gemini による分析結果が `analysis_result_gemini.md` として出力され、URL一覧を使った場合は統合レポート `consolidated_analysis_*.md` も自動生成されます（不要なら `--skip-summary` を指定）。
2. 追加で Claude へ依頼したい場合は `最新分析プロンプトを送信` ツールを実行すると、Claude へのメッセージとして `analysis_request.md` が投稿され、そのまま二段構えの分析を依頼できます。

> **補足**: スクリプトに実行権限がない場合は、一度 `chmod +x mcp_tools/*.sh` を実行してください。

## 統合レポートの生成
複数サイトの Gemini 分析結果をまとめて俯瞰したい場合は、以下のスクリプトを利用できます。

```bash
python3 summarize_analyses.py \
  --runs-dir /Users/hattaryoga/Desktop/リスティング広告抜き出し/マウスピース矯正/output \
  --latest 5
```

`output/run_*` にある `analysis_result_gemini.md` をまとめ、`consolidated_analysis_*.md` を生成します。`--latest` を指定すると直近 n 件のみを対象にできます。
