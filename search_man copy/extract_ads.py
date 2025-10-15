"""
指定KWのスポンサード広告を抽出するスクリプト
"""
from pathlib import Path
from playwright.sync_api import sync_playwright
import time

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "SearchAds"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
DEFAULT_KEYWORD = "マウスピース矯正"

def extract_sponsored_ads(keyword: str = DEFAULT_KEYWORD):
    """
    指定されたキーワードでGoogle検索を行い、
    スポンサード広告の見出しを抽出する
    """
    ads_data = []
    
    with sync_playwright() as p:
        # ブラウザを起動（通常モード、より人間らしい設定）
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
        )
        iphone_device = p.devices.get("iPhone 12")
        context = browser.new_context(
            **iphone_device,
            locale='ja-JP',
            timezone_id='Asia/Tokyo'
        )
        
        # webdriver プロパティを削除して自動化検知を回避
        page = context.new_page()
        
        try:
            # Google検索ページへ移動
            print(f"検索中: {keyword}")
            print("ページが読み込まれるまでお待ちください...")
            page.goto(f"https://www.google.com/search?q={keyword}", wait_until="domcontentloaded")
            
            # ページの読み込みを待つ（人間のような動作をシミュレート）
            time.sleep(5)
            
            # スクロールして広告が表示されるのを確認
            page.evaluate("window.scrollBy(0, 300)")
            time.sleep(2)
            
            # デバッグ: ページのHTMLを確認
            html_content = page.content()
            print(f"ページHTMLの長さ: {len(html_content)} 文字")
            
            # CAPTCHAが表示されているか確認
            if "recaptcha" in html_content.lower() or "unusual traffic" in html_content.lower():
                print("\n⚠️ 警告: GoogleがCAPTCHAを表示しています")
                print("ブラウザウィンドウでCAPTCHAを手動で解決してください...")
                print("解決後、30秒間待機します...\n")
                time.sleep(30)
                html_content = page.content()
            
            # 広告要素を探す
            print("広告要素を検索中...")
            
            # より包括的なセレクタで広告を検索
            # Googleの広告表示パターンは複数あるため、様々な方法で試す
            
            # 方法1: 「スポンサー」または「広告」テキストを含む要素から親要素を取得
            sponsor_labels = page.locator('span:has-text("スポンサー"), span:has-text("広告"), span:has-text("Sponsored"), span:has-text("Ad")').all()
            print(f"見つかったスポンサーラベル数: {len(sponsor_labels)}")
            
            # 方法2: 既知の広告コンテナセレクタ
            ad_blocks = page.locator('div.uEierd, div.Cu4Edb, div.v5yQqb, div[data-text-ad], li.ads-ad').all()
            print(f"見つかった広告ブロック数（セレクタ）: {len(ad_blocks)}")
            
            # 方法3: aria-labelで広告を探す
            aria_ad_blocks = page.locator('[aria-label*="広告"], [aria-label*="Ad"], [aria-label*="スポンサー"]').all()
            print(f"見つかった広告ブロック数（aria-label）: {len(aria_ad_blocks)}")
            
            # スポンサーラベルから親要素を取得して広告ブロックを特定
            ad_blocks_from_labels = []
            for label in sponsor_labels:
                try:
                    # 親要素を複数レベル上がって広告ブロックを探す
                    parent = label.locator('xpath=ancestor::div[contains(@class, "uEierd") or contains(@class, "Cu4Edb")]').first
                    ad_blocks_from_labels.append(parent)
                except:
                    pass
            
            print(f"スポンサーラベルから取得した広告ブロック数: {len(ad_blocks_from_labels)}")
            
            # すべての広告ブロックを統合
            raw_ad_blocks = ad_blocks + ad_blocks_from_labels + aria_ad_blocks
            print(f"合計広告ブロック数: {len(raw_ad_blocks)}")

            unique_ad_blocks = []
            seen_block_html = set()
            for block in raw_ad_blocks:
                try:
                    signature = block.evaluate("el => el.outerHTML")
                    if not signature:
                        continue
                    signature = signature.strip()
                except Exception:
                    continue
                if signature in seen_block_html:
                    continue
                seen_block_html.add(signature)
                unique_ad_blocks.append(block)
            print(f"ユニーク広告ブロック数: {len(unique_ad_blocks)}")
            
            for idx, ad_block in enumerate(unique_ad_blocks):
                try:
                    # 広告の見出しを抽出（複数のセレクタを試す）
                    headline_selectors = [
                        'div[role="heading"]',
                        'div.v5yQqb',
                        'div.CCgQ5',
                        'span',
                        'a > div > div > span',
                    ]
                    
                    headline = ""
                    for selector in headline_selectors:
                        try:
                            headline_elem = ad_block.locator(selector).first
                            if headline_elem.is_visible():
                                headline = headline_elem.inner_text()
                                if headline and len(headline) > 5:  # 有効な見出しかチェック
                                    break
                        except:
                            continue
                    
                    # URLを抽出
                    url = ""
                    try:
                        url_elem = ad_block.locator('a').first
                        url = url_elem.get_attribute('href') or ""
                    except:
                        pass
                    
                    # 説明文を抽出
                    description = ""
                    try:
                        desc_elem = ad_block.locator('div.MUxGbd').first
                        if desc_elem.is_visible():
                            description = desc_elem.inner_text()
                    except:
                        pass
                    
                    if headline:
                        ads_data.append({
                            'headline': headline.strip(),
                            'url': (url or "").strip(),
                            'description': (description or "").strip()
                        })
                
                except Exception as e:
                    print(f"広告ブロック {idx + 1} の処理中にエラー: {e}")
                    continue
            
            # スクリーンショットを保存
            screenshot_path = OUTPUT_DIR / "search_result.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"スクリーンショットを保存: {screenshot_path}")
            
            # デバッグ用: HTMLを保存
            html_path = OUTPUT_DIR / "page_source.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page.content())
            print(f"ページHTMLを保存: {html_path}")
            
            # ブラウザを開いたまま待機（手動確認用）
            print("\n結果を確認するため、ブラウザを10秒間開いたままにします...")
            time.sleep(10)
            
        except Exception as e:
            print(f"エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            browser.close()
    
    print(f"候補広告総数: {len(ads_data)}")

    unique_ads = []
    seen_ads = set()
    for ad in ads_data:
        key = (ad['headline'], ad['url'], ad['description'])
        if key in seen_ads:
            print(f"重複広告をスキップ: {ad['headline']}")
            continue
        seen_ads.add(key)
        ad_with_index = ad.copy()
        ad_with_index['index'] = len(unique_ads) + 1
        unique_ads.append(ad_with_index)
        print(f"広告 {ad_with_index['index']}: {ad_with_index['headline']}")

    if not unique_ads and ads_data:
        print("ユニーク抽出で全件除外されたため、見出し単位で整理し直します")
        unique_ads = []
        seen_headlines = set()
        for ad in ads_data:
            headline = ad['headline']
            if headline in seen_headlines:
                continue
            seen_headlines.add(headline)
            ad_with_index = ad.copy()
            ad_with_index['index'] = len(unique_ads) + 1
            unique_ads.append(ad_with_index)
            print(f"広告 {ad_with_index['index']}: {headline}")

    return unique_ads

def save_to_markdown(ads_data, keyword: str = DEFAULT_KEYWORD):
    """
    抽出した広告データをMarkdownファイルに保存
    """
    md_path = OUTPUT_DIR / "sponsored_ads.md"
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# {keyword} - スポンサード広告見出し一覧\n\n")
        f.write(f"抽出日時: {time.strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
        f.write(f"検索キーワード: **{keyword}**\n\n")
        f.write("---\n\n")
        
        if not ads_data:
            f.write("**スポンサード広告が見つかりませんでした。**\n\n")
            f.write("注意: 広告表示は地域、時間帯、検索履歴などによって変動します。\n")
        else:
            f.write(f"## 抽出された広告数: {len(ads_data)}\n\n")
            
            for ad in ads_data:
                f.write(f"### 広告 {ad['index']}\n\n")
                f.write(f"**見出し:** {ad['headline']}\n\n")
                if ad['url']:
                    f.write(f"**URL:** {ad['url']}\n\n")
                if ad['description']:
                    f.write(f"**説明文:**\n{ad['description']}\n\n")
                f.write("---\n\n")
    
    print(f"Markdownファイルを保存: {md_path}")
    return md_path

if __name__ == "__main__":
    print("=== Google スポンサード広告抽出ツール ===\n")
    
    # 広告を抽出
    keyword = DEFAULT_KEYWORD
    ads = extract_sponsored_ads(keyword)
    
    print(f"\n抽出完了: {len(ads)}件の広告が見つかりました")
    
    # Markdownファイルに保存
    md_file = save_to_markdown(ads, keyword)
    
    print(f"\n完了: {md_file}")
