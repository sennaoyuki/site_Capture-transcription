# LP文字起こしツール - ウェブアプリ版

URLやローカルHTMLファイルから文字起こしを行うウェブアプリケーション

## 技術スタック

- **フロントエンド**: Nuxt.js 3 + Tailwind CSS
- **バックエンド**: FastAPI + Python
- **OCR**: Google Gemini API

## プロジェクト構成

```
.
├── backend/                # FastAPI バックエンド
│   ├── app.py             # メインアプリケーション
│   ├── requirements.txt   # Python依存関係
│   └── temp/              # 一時ファイル保存先
├── frontend/              # Nuxt.js フロントエンド
│   ├── pages/             # ページコンポーネント
│   ├── assets/            # CSS等のアセット
│   ├── nuxt.config.ts     # Nuxt設定
│   └── package.json       # Node.js依存関係
└── search_man copy/       # 既存の文字起こしモジュール
```

## セットアップ手順

### 1. 環境変数の設定

```bash
# Google Gemini API Keyを設定
export GOOGLE_API_KEY="your_api_key_here"
```

### 2. バックエンドのセットアップ

```bash
cd backend

# 仮想環境を作成（推奨）
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 依存関係をインストール
pip install -r requirements.txt

# 既存の文字起こしモジュールの依存関係もインストール
cd "../search_man copy"
pip install -r requirements.txt
cd ../backend

# サーバーを起動
python app.py
```

バックエンドは `http://localhost:8000` で起動します。

### 3. フロントエンドのセットアップ

新しいターミナルウィンドウで:

```bash
cd frontend

# 依存関係をインストール
npm install

# 開発サーバーを起動
npm run dev
```

フロントエンドは `http://localhost:3000` で起動します。

## 使い方

1. ブラウザで `http://localhost:3000` を開く
2. 入力タイプを選択（URL または ローカルHTML）
3. URL入力 または HTMLファイルをアップロード/ドラッグ&ドロップ
4. 「🚀 文字起こし実行」ボタンをクリック
5. 処理完了後、結果を確認・ダウンロード

## API エンドポイント

### `GET /health`
ヘルスチェック

### `POST /api/transcribe/url`
URLから文字起こし

**リクエスト:**
```json
{
  "url": "https://example.com"
}
```

### `POST /api/transcribe/upload`
HTMLファイルアップロードから文字起こし

**リクエスト:** `multipart/form-data` でファイルをアップロード

### `GET /api/status/{job_id}`
処理ステータスを確認

### `GET /api/download/{job_id}/{file_type}`
結果ファイルをダウンロード
- `file_type`: `markdown`, `text`, `screenshot`

## 本番環境へのデプロイ

### バックエンド

```bash
cd backend

# Gunicornを使用（本番推奨）
pip install gunicorn
gunicorn app:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### フロントエンド

```bash
cd frontend

# 本番ビルド
npm run build

# プレビュー
npm run preview
```

または静的サイト生成:

```bash
npm run generate
# .output/public/ 配下を静的ホスティングサービスにデプロイ
```

## 環境変数

### バックエンド
- `GOOGLE_API_KEY`: Google Gemini API Key（必須）

### フロントエンド
- `API_BASE_URL`: バックエンドAPIのURL（デフォルト: `http://localhost:8000`）

`.env` ファイルを作成して設定できます:

```bash
# frontend/.env
API_BASE_URL=http://your-backend-url.com
```

## トラブルシューティング

### CORS エラーが発生する
- バックエンドの `app.py` でフロントエンドのURLを `allow_origins` に追加してください

### ファイルアップロードが失敗する
- ファイルサイズが大きすぎる可能性があります
- HTMLファイル形式（.html, .htm）であることを確認してください

### OCR が動作しない
- `GOOGLE_API_KEY` が正しく設定されているか確認
- `google-generativeai` ライブラリがインストールされているか確認

## ライセンス

既存のプロジェクトライセンスに従います。
