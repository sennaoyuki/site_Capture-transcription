# サイトテキスト起こせるくん

指定したWebサイトを自動でスクリーンショットし、2000pxごとに分割した画像をGemini APIへ送信してテキスト化するデスクトップアプリです。

## セットアップ
1. 依存パッケージをインストールします。
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windowsでは .venv\\Scripts\\activate
   pip install -r requirements.txt
   playwright install
   ```
2. ルートに配置された`.env`にGeminiのAPIキーを設定します。
   ```env
   GOOGLE_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
   ```

## 使い方
1. `main.py`を実行するとGUIが立ち上がります。
   ```bash
   python main.py
   ```
2. URLを入力して「追加」を押す、またはテキスト/CSVファイルからURLリストを読み込みます。
3. 「処理開始」を押すと、URLごとにスクリーンショット撮影→Geminiでの文字起こしが実行されます。
4. 出力は`outputs/<日時>/<連番_スラッグ>/`以下に画像、Markdown、JSONとして保存されます。

## 出力構造
```
outputs/
  20240810_123456/
    run.log
    01_example-com/
      images/
        slice_001.png
        slice_002.png
      texts/
        transcript.md
        transcript.json
```

## 補足設定
- `SITE_TRANSCRIBER_MODEL` 環境変数でGeminiモデルを切り替えられます。既定はマルチモーダル対応の`gemini-pro-vision`です。アクセス権により404が発生する場合は、`genai.list_models()` (Python) 等で利用可能なモデル名を確認し、環境変数で上書きしてください。
- `SITE_TRANSCRIBER_SLICE_HEIGHT` など環境変数でスライス幅やタイムアウトをカスタマイズできます。詳細は`backend/config.py`を参照してください。
- 大きなページでは処理に時間がかかるため、`SITE_TRANSCRIBER_TIMEOUT`を延長することを推奨します。

## トラブルシュート
- **ブラウザ起動に失敗する**: `playwright install` を実行し、Chromiumが正しくセットアップされているか確認してください。
- **GOOGLE_API_KEYが認識されない**: `.env`に記載した後、念のため端末を再起動するか`source .env`で環境変数を読み込んでください。
- **Gemini APIの制限エラー**: `backend/config.py`の`max_retries`や`retry_backoff_base`を調整し、呼び出し間隔を伸ばしてください。
- **利用可能なモデル名がわからない**: `python scripts/list_models.py` を実行すると、`generateContent` に対応しているモデルの一覧が確認できます。表示された名称を `SITE_TRANSCRIBER_MODEL` に設定してください。
