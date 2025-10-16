# TD作成くん アプリ概要

## 概要
ターゲット情報と検索キーワードを入力に、Google検索結果（広告・SEO）を収集し、検索意図や競合訴求を整理したうえでGoogle広告用のTD案を自動生成するCLIアプリケーションです。デフォルトでは [ScrapingDog](https://www.scrapingdog.com/google-search-api) の Google Search API を利用しますが、設定を切り替えることで SerpAPI も利用可能です。

## セットアップ
1. 依存パッケージのインストール
   ```bash
   pip install -r requirements.txt
   ```
2. ScrapingDogのAPIキーを環境変数として設定
   ```bash
   export SCRAPINGDOG_API_KEY=あなたのAPIキー
   ```
   SerpAPIを利用したい場合は `td_builder/config.py` の `SerpConfig` で `provider` を `"serpapi"` に変更し、`SERPAPI_KEY` を設定してください。

## 使い方
### 直接引数で実行
```bash
python -m TD作成くん.cli \
  --target "BtoBマーケ担当者" \
  --keyword "マーケティング オートメーション 比較" \
  --site-info "自社ツール：国産でサポート重視" \
  --output result.json \
  --verbose
```
- `--target` と `--keyword` は必須。
- `--site-info` は任意で、自社サイトや提案先サイトの訴求ポイントを渡せます。
- `--output` を省略すると標準出力にJSONが表示されます。
- `--verbose` を指定すると詳細ログを表示します。

### JSONファイルから入力
`input.json`
```json
{
  "target": "中小企業の人事担当者",
  "keyword": "勤怠管理システム おすすめ",
  "site_info": "クラウド型で導入サポートが手厚い"
}
```

```bash
python -m TD作成くん.cli --input input.json --output report.json
```

## 出力内容
- 検索意図の推定結果と根拠
- 競合広告（スポンサード）の一覧と簡易サイト要約
- SEO上位3サイトの要点
- 訴求軸スコア（価格・信頼・スピードなど）
- Google広告向けTD案（タイトル・説明文・CTA）を複数案提示

## 注意事項
- 実際の配信前には広告ポリシー準拠や表現の正確性を運用担当者が確認してください。
- 利用するAPI（ScrapingDog / SerpAPIなど）の規約とGoogleの利用規約に従って運用してください。
- スクレイピング対象サイトのrobots.txtやアクセス制限に配慮し、必要に応じてレート制御を追加してください。
