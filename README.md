# LP文字起こしツール - Screenshot OCR Transcription Web App

URLまたはローカルHTMLファイルからスクリーンショットを撮影し、OCRで文字起こしを行うWebアプリケーション。

## 機能

- URLからのWebページ文字起こし
- ローカルHTMLファイルアップロード
- スクリーンショットプレビュー
- 個別スライスごとの文字起こし結果表示
- クリップボードコピー機能
- MD/TXT形式でのダウンロード
- 検索広告・SEO分析に基づくGoogle広告TD案自動生成（TD作成くん）

## 技術スタック

### Frontend
- Nuxt.js 3
- Vue 3
- Tailwind CSS

### Backend
- FastAPI
- Playwright (ブラウザ自動化)
- Google Gemini API (OCR)
- ScrapingDog / SerpAPI (検索結果取得: TD作成くん)

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

### TD作成くん Webアプリの利用

1. バックエンドの環境変数を設定（ScrapingDogの場合）
   ```bash
   export SCRAPINGDOG_API_KEY=your_scrapingdog_api_key
   ```
   SerpAPIを利用する場合は `TD作成くん/td_builder/config.py` の `SerpConfig.provider` を `"serpapi"` に変更し、`SERPAPI_KEY` を設定してください。
2. 上記手順でバックエンドを起動した状態でブラウザから `http://localhost:3000/td` にアクセス
3. 「ターゲット」「検索キーワード」「サイト特徴（任意）」を入力してTD案を生成

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

## バックエンドのデプロイ（Google Cloud Run）（推奨）

Google Cloud Runを使用したデプロイが最も確実です：

### 前提条件
- Google Cloud アカウント
- Google Cloud CLI (`gcloud`) インストール済み

### デプロイ手順

1. Google Cloud Console でプロジェクトを作成または選択

2. Cloud Run API と Artifact Registry API を有効化
```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com
```

3. プロジェクトをクローンして api ディレクトリに移動
```bash
git clone https://github.com/sennaoyuki/site_Capture-transcription.git
cd site_Capture-transcription/api
```

4. Cloud Run にデプロイ
```bash
gcloud run deploy lp-transcriber-api \
  --source . \
  --platform managed \
  --region asia-northeast1 \
  --allow-unauthenticated \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --set-env-vars GOOGLE_API_KEY=your_gemini_api_key_here
```

5. デプロイ完了後、表示されるURLをコピー（例: `https://lp-transcriber-api-xxxxx-an.a.run.app`）

6. Vercel Dashboardで`API_BASE_URL`環境変数を設定:
   - `https://lp-transcriber-api-xxxxx-an.a.run.app`

7. Vercelで再デプロイ

### 注意事項
- メモリ: 2Gi（Playwrightのため）
- CPU: 2コア（並列処理のため）
- タイムアウト: 300秒（大きなページの処理のため）

## バックエンドのデプロイ（Railway）

**注意**: Railwayはモノレポ構成で設定が複雑なため、Google Cloud Runを推奨します。

### 自動デプロイ

リポジトリに`railway.json`が含まれていますが、設定が必要です：

1. [Railway](https://railway.app)にログイン
2. 「New Project」→「Deploy from GitHub repo」
3. リポジトリ選択: `sennaoyuki/site_Capture-transcription`
4. 環境変数を設定:
   - `GOOGLE_API_KEY`: Google Gemini API Key
5. デプロイ完了後、URLをコピー
6. Vercel Dashboardで`API_BASE_URL`環境変数を設定
7. Vercelで再デプロイ

## パフォーマンス最適化

- Playwright直接スライシング（1400px高さ、120pxオーバーラップ）
- 並列OCR処理（ThreadPoolExecutor、3ワーカー）
- networkidleベースのシンプルなページロード戦略

## ライセンス

MIT
