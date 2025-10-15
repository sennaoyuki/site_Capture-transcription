"""
Webサイトの文字起こしスクリプト（画像内テキストも含む）
PlaywrightとOCRを使用して、Webページのすべてのテキストを抽出します
"""
from playwright.sync_api import sync_playwright
import time
import os
import base64
from pathlib import Path
from datetime import datetime
import json
import re

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ OCRライブラリがインストールされていません。")
    print("画像内テキストを抽出するには以下をインストールしてください：")
    print("  pip install pillow pytesseract")
    print("  Tesseractのインストール（Mac）: brew install tesseract tesseract-lang")


def extract_all_text_from_website(url):
    """
    指定されたURLからすべてのテキストを抽出
    - ページ内の可視テキスト
    - 画像内のテキスト（OCR）
    """
    
    result = {
        'url': url,
        'timestamp': datetime.now().strftime('%Y年%m月%d日 %H:%M:%S'),
        'visible_text': '',
        'images_text': [],
        'meta_info': {},
        'all_text_combined': ''
    }
    
    with sync_playwright() as p:
        # ブラウザを起動
        browser = p.chromium.launch(
            headless=False,
            args=[
                '--disable-blink-features=AutomationControlled',
            ]
        )
        
        context = browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
            locale='ja-JP',
            timezone_id='Asia/Tokyo'
        )
        
        page = context.new_page()
        
        try:
            print(f"📄 ページを読み込み中: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # ページが完全に読み込まれるまで待機
            time.sleep(3)
            
            # ページを少しスクロールして遅延読み込み要素を表示
            page.evaluate("""
                () => {
                    window.scrollTo(0, document.body.scrollHeight / 3);
                }
            """)
            time.sleep(2)
            
            page.evaluate("""
                () => {
                    window.scrollTo(0, document.body.scrollHeight * 2 / 3);
                }
            """)
            time.sleep(2)
            
            page.evaluate("""
                () => {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            """)
            time.sleep(2)
            
            # 最上部に戻る
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(1)
            
            print("✅ ページの読み込みが完了しました")
            
            # メタ情報を取得
            print("\n📋 メタ情報を取得中...")
            result['meta_info']['title'] = page.title()
            
            # メタタグを取得
            meta_description = page.locator('meta[name="description"]').get_attribute('content') if page.locator('meta[name="description"]').count() > 0 else ""
            meta_keywords = page.locator('meta[name="keywords"]').get_attribute('content') if page.locator('meta[name="keywords"]').count() > 0 else ""
            
            result['meta_info']['description'] = meta_description or ""
            result['meta_info']['keywords'] = meta_keywords or ""
            
            # 可視テキストを抽出
            print("\n📝 ページ内の可視テキストを抽出中...")
            
            # body全体のテキストを取得（JavaScriptで整形して取得）
            visible_text = page.evaluate("""
                () => {
                    // 不要な要素を除外
                    const excludeSelectors = ['script', 'style', 'noscript', 'iframe'];
                    excludeSelectors.forEach(selector => {
                        document.querySelectorAll(selector).forEach(el => el.remove());
                    });
                    
                    // bodyのテキストを取得
                    const text = document.body.innerText;
                    
                    // 複数の連続する空白・改行を整理
                    return text.replace(/\\n\\s*\\n/g, '\\n\\n').trim();
                }
            """)
            
            result['visible_text'] = visible_text
            print(f"✅ 可視テキスト抽出完了（{len(visible_text)}文字）")
            
            # 画像を抽出してOCR
            if OCR_AVAILABLE:
                print("\n🖼️  画像内テキストを抽出中（OCR）...")
                
                # すべての画像要素を取得
                images = page.locator('img').all()
                print(f"   見つかった画像数: {len(images)}")
                
                # 作業用ディレクトリを作成
                work_dir = Path("/Users/hattaryoga/Library/CloudStorage/GoogleDrive-naoyuki.uebayashi@senjinholdings.com/マイドライブ/1_ダウンロード/リスティング広告抜き出し/生成AI/temp_images")
                work_dir.mkdir(exist_ok=True)
                
                for idx, img in enumerate(images, 1):
                    try:
                        # 画像が可視かチェック
                        if not img.is_visible():
                            continue
                        
                        # 画像のサイズを取得（小さすぎる画像はスキップ）
                        box = img.bounding_box()
                        if not box or box['width'] < 50 or box['height'] < 50:
                            continue
                        
                        # 画像のalt属性とsrc属性を取得
                        alt_text = img.get_attribute('alt') or ""
                        src = img.get_attribute('src') or ""
                        
                        print(f"   処理中: 画像 {idx}/{len(images)}", end="\r")
                        
                        # 画像をスクリーンショット
                        img_path = work_dir / f"image_{idx}.png"
                        img.screenshot(path=str(img_path))
                        
                        # OCRでテキストを抽出
                        try:
                            image = Image.open(img_path)
                            # 日本語と英語でOCR
                            ocr_text = pytesseract.image_to_string(image, lang='jpn+eng')
                            ocr_text = ocr_text.strip()
                            
                            if ocr_text:
                                result['images_text'].append({
                                    'index': idx,
                                    'alt': alt_text,
                                    'src': src[:100] if src else "",  # URL省略表示
                                    'ocr_text': ocr_text
                                })
                        except Exception as e:
                            print(f"\n   ⚠️ 画像 {idx} のOCR処理エラー: {e}")
                        
                        # 画像ファイルを削除（クリーンアップ）
                        img_path.unlink(missing_ok=True)
                        
                    except Exception as e:
                        print(f"\n   ⚠️ 画像 {idx} の処理エラー: {e}")
                        continue
                
                print(f"\n✅ OCR完了: {len(result['images_text'])}個の画像からテキストを抽出")
                
                # 作業用ディレクトリを削除
                try:
                    work_dir.rmdir()
                except:
                    pass
            else:
                print("\n⚠️ OCRライブラリが利用できないため、画像内テキストの抽出をスキップします")
            
            # スクリーンショットを保存
            screenshot_path = "/Users/hattaryoga/Library/CloudStorage/GoogleDrive-naoyuki.uebayashi@senjinholdings.com/マイドライブ/1_ダウンロード/リスティング広告抜き出し/生成AI/website_screenshot.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print(f"\n📸 スクリーンショットを保存: website_screenshot.png")
            
            # HTMLソースを保存
            html_path = "/Users/hattaryoga/Library/CloudStorage/GoogleDrive-naoyuki.uebayashi@senjinholdings.com/マイドライブ/1_ダウンロード/リスティング広告抜き出し/生成AI/website_source.html"
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(page.content())
            print(f"💾 HTMLソースを保存: website_source.html")
            
            # 確認のため少し待機
            print("\n🔍 結果を確認するため、ブラウザを5秒間開いたままにします...")
            time.sleep(5)
            
        except Exception as e:
            print(f"\n❌ エラーが発生しました: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            browser.close()
    
    # すべてのテキストを結合
    all_text_parts = [result['visible_text']]
    
    if result['images_text']:
        all_text_parts.append("\n\n=== 画像内テキスト ===\n")
        for img_data in result['images_text']:
            if img_data['alt']:
                all_text_parts.append(f"\n[画像 {img_data['index']} - alt: {img_data['alt']}]")
            else:
                all_text_parts.append(f"\n[画像 {img_data['index']}]")
            all_text_parts.append(f"\n{img_data['ocr_text']}\n")
    
    result['all_text_combined'] = "\n".join(all_text_parts)
    
    return result


def save_to_markdown(result):
    """
    抽出結果をMarkdownファイルに保存
    """
    md_path = "/Users/hattaryoga/Library/CloudStorage/GoogleDrive-naoyuki.uebayashi@senjinholdings.com/マイドライブ/1_ダウンロード/リスティング広告抜き出し/生成AI/website_transcription.md"
    
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# Webサイト文字起こし結果\n\n")
        f.write(f"**URL:** {result['url']}\n\n")
        f.write(f"**抽出日時:** {result['timestamp']}\n\n")
        
        # メタ情報
        if result['meta_info']:
            f.write(f"## メタ情報\n\n")
            f.write(f"**タイトル:** {result['meta_info'].get('title', 'N/A')}\n\n")
            if result['meta_info'].get('description'):
                f.write(f"**説明:** {result['meta_info']['description']}\n\n")
            if result['meta_info'].get('keywords'):
                f.write(f"**キーワード:** {result['meta_info']['keywords']}\n\n")
        
        f.write("---\n\n")
        
        # 可視テキスト
        f.write(f"## ページ内テキスト\n\n")
        f.write(f"```\n{result['visible_text']}\n```\n\n")
        
        # 画像内テキスト
        if result['images_text']:
            f.write(f"## 画像内テキスト（OCR抽出）\n\n")
            f.write(f"抽出された画像数: {len(result['images_text'])}\n\n")
            
            for img_data in result['images_text']:
                f.write(f"### 画像 {img_data['index']}\n\n")
                if img_data['alt']:
                    f.write(f"**Alt属性:** {img_data['alt']}\n\n")
                if img_data['src']:
                    f.write(f"**画像URL:** `{img_data['src']}`\n\n")
                f.write(f"**抽出テキスト:**\n\n")
                f.write(f"```\n{img_data['ocr_text']}\n```\n\n")
                f.write("---\n\n")
        
        # 統合テキスト
        f.write(f"## すべてのテキスト（統合版）\n\n")
        f.write(f"```\n{result['all_text_combined']}\n```\n\n")
    
    print(f"\n✅ Markdownファイルを保存: website_transcription.md")
    return md_path


def save_to_text(result):
    """
    抽出結果をプレーンテキストファイルに保存
    """
    txt_path = "/Users/hattaryoga/Library/CloudStorage/GoogleDrive-naoyuki.uebayashi@senjinholdings.com/マイドライブ/1_ダウンロード/リスティング広告抜き出し/生成AI/website_transcription.txt"
    
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(f"Webサイト文字起こし結果\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(f"URL: {result['url']}\n")
        f.write(f"抽出日時: {result['timestamp']}\n\n")
        
        if result['meta_info']:
            f.write(f"タイトル: {result['meta_info'].get('title', 'N/A')}\n\n")
        
        f.write(f"{'=' * 60}\n\n")
        f.write(result['all_text_combined'])
    
    print(f"✅ テキストファイルを保存: website_transcription.txt")
    return txt_path


if __name__ == "__main__":
    print("=" * 70)
    print("🌐 Webサイト文字起こしツール（画像内テキスト対応）")
    print("=" * 70)
    print()
    
    # 対象URL
    url = "https://l.shift-ai.co.jp/lp/lpcam01a/?free4=SY_GSN_lpCAM01A_11111"
    
    if not OCR_AVAILABLE:
        print("⚠️ OCR機能を有効にするには:")
        print("   1. pip install pillow pytesseract")
        print("   2. brew install tesseract tesseract-lang (Macの場合)")
        print()
        response = input("OCRなしで続行しますか？ (y/n): ")
        if response.lower() != 'y':
            print("処理を中止しました")
            exit()
    
    # テキスト抽出を実行
    result = extract_all_text_from_website(url)
    
    # ファイルに保存
    md_file = save_to_markdown(result)
    txt_file = save_to_text(result)
    
    print("\n" + "=" * 70)
    print("🎉 処理完了！")
    print("=" * 70)
    print(f"\n📊 抽出結果:")
    print(f"   - 可視テキスト: {len(result['visible_text'])} 文字")
    print(f"   - 画像からのテキスト抽出: {len(result['images_text'])} 個")
    print(f"   - 合計テキスト: {len(result['all_text_combined'])} 文字")
    print(f"\n📁 出力ファイル:")
    print(f"   - {md_file}")
    print(f"   - {txt_file}")
    print()


