# LP文字起こしツール - Screenshot OCR Transcription Web App

URLまたはローカルHTMLファイルからスクリーンショットを撮影し、OCRで文字起こしを行うWebアプリケーション。

## 機能

- URLからのWebページ文字起こし
- ローカルHTMLファイルアップロード
- スクリーンショットプレビュー
- 個別スライスごとの文字起こし結果表示
- クリップボードコピー機能
- MD/TXT形式でのダウンロード

## 技術スタック

### Frontend
- Nuxt.js 3
- Vue 3
- Tailwind CSS

### Backend
- FastAPI
- Playwright (ブラウザ自動化)
- Google Gemini API (OCR)

## ローカル開発

### 必要な環境
- Node.js 18+
- Python 3.8+
- Google Gemini API Key

### セットアップ

1. リポジトリをクローン
```bash
git clone https://github.com/sennaoyuki/site_Capture-transcription.git
cd site_Capture-transcription
```

2. 環境変数を設定
```bash
cp .env.example .env
# .envファイルを編集してGoogle Gemini API Keyを設定
```

3. Backend起動
```bash
cd api
pip install -r requirements.txt
playwright install chromium
python app.py
```

4. Frontend起動（別ターミナル）
```bash
npm install
npm run dev
```

5. ブラウザで http://localhost:3000 にアクセス

## Vercelへのデプロイ

### 方法1: Vercel CLI（推奨）

1. Vercel CLIをインストール
```bash
npm install -g vercel
```

2. プロジェクトをデプロイ
```bash
vercel
```

3. 環境変数を設定
```bash
vercel env add GOOGLE_API_KEY
vercel env add API_BASE_URL
```

4. 本番デプロイ
```bash
vercel --prod
```

### 方法2: Vercel Dashboard

1. [Vercel](https://vercel.com)にログイン
2. 「Import Project」をクリック
3. GitHubリポジトリを選択: `sennaoyuki/site_Capture-transcription`
4. 環境変数を設定:
   - `GOOGLE_API_KEY`: Google Gemini API Key
   - `API_BASE_URL`: バックエンドのURL（デプロイ後に更新）
5. 「Deploy」をクリック

### 注意事項

**重要**: このアプリケーションのバックエンドはPlaywrightを使用しており、Vercelのサーバーレス関数では実行できません。以下のいずれかの方法でバックエンドをホスティングする必要があります:

1. **別のプラットフォームでバックエンドをホスト**（推奨）:
   - Railway
   - Render
   - Google Cloud Run
   - AWS EC2/ECS
   - Heroku

2. **Vercelでフロントエンドのみデプロイ**し、`API_BASE_URL`環境変数でバックエンドURLを指定

## バックエンドのデプロイ（Railway）

### 自動デプロイ（推奨）

リポジトリに`railway.json`が含まれているため、自動的に設定されます：

1. [Railway](https://railway.app)にログイン
2. 「New Project」→「Deploy from GitHub repo」
3. リポジトリ選択: `sennaoyuki/site_Capture-transcription`
4. Railwayが自動で`railway.json`を検出してデプロイ
5. 環境変数を設定:
   - `GOOGLE_API_KEY`: Google Gemini API Key
   - `PORT`: 8000（自動設定される場合あり）
6. デプロイ完了後、URLをコピー（例: `https://your-app.railway.app`）
7. Vercel Dashboardで`API_BASE_URL`環境変数を設定:
   - `https://your-app.railway.app`
8. Vercelで再デプロイ

### 手動設定が必要な場合

`railway.json`が認識されない場合：

1. Settings → Build:
   - Build Command: `pip install -r api/requirements.txt && playwright install chromium && playwright install-deps`
2. Settings → Deploy:
   - Start Command: `cd api && uvicorn app:app --host 0.0.0.0 --port $PORT`
3. 環境変数を設定（上記と同じ）

## パフォーマンス最適化

- Playwright直接スライシング（1400px高さ、120pxオーバーラップ）
- 並列OCR処理（ThreadPoolExecutor、3ワーカー）
- networkidleベースのシンプルなページロード戦略

## ライセンス

MIT
