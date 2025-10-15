"""
指定KWのオーガニック検索結果（SEO）を抽出するスクリプト
"""
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode
from playwright.sync_api import sync_playwright, TimeoutError
import time

BASE_DIR = Path(__file__).resolve().parent
BASE_OUTPUT_DIR = BASE_DIR / "SearchSEO"
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_KEYWORD = "マウスピース矯正"
RESULT_LIMIT = 4


def _ensure_output_dir(keyword_slug: Optional[str] = None) -> Path:
    if keyword_slug:
        target_dir = BASE_OUTPUT_DIR / keyword_slug
    else:
        target_dir = BASE_OUTPUT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def extract_organic_results(
    keyword: str = DEFAULT_KEYWORD,
    limit: int = RESULT_LIMIT,
    keyword_slug: Optional[str] = None,
):
    """
    指定されたキーワードでGoogle検索を行い、
    オーガニック検索結果の上位 `limit` 件を抽出する
    """
    output_dir = _ensure_output_dir(keyword_slug)

    results = []
    seen_urls = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
            ],
        )

        iphone_device = p.devices.get("iPhone 12")
        context = browser.new_context(
            **iphone_device,
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )

        page = context.new_page()

        try:
            print(f"検索中: {keyword}")
            print("ページが読み込まれるまでお待ちください...")
            query_params = {
                "q": keyword,
                "hl": "ja",
                "gl": "JP",
                "udm": "14",
            }
            search_url = "https://www.google.com/search?" + urlencode(query_params)
            page.goto(search_url, wait_until="domcontentloaded")

            time.sleep(5)
            page.evaluate("window.scrollBy(0, 800)")
            time.sleep(2.5)

            try:
                page.wait_for_selector("div.g, div.tF2Cxc, div.MjjYud", timeout=10000)
            except TimeoutError:
                print("検索結果のコンテナを取得できませんでしたが処理を続行します")

            extracted = page.evaluate(
                """
            (limit) => {
                const containerSelectors = [
                    'div.tF2Cxc',
                    'div.MjjYud',
                    'div.g',
                    'div.dv3tp',
                    'div.N54PNb'
                ];
                const snippetSelectors = [
                    "div[data-content-feature='1']",
                    "div[data-sncf='1']",
                    "div.VwiC3b",
                    "div[data-attrid='wa:/description']",
                    "span[jsname='bN97Pc']",
                    "div.yXK7lf",
                    "div.P7xzyd",
                    "div.fc9yUc"
                ];

                const containers = [];
                const seenNodes = new Set();
                for (const selector of containerSelectors) {
                    document.querySelectorAll(selector).forEach((el) => {
                        if (!seenNodes.has(el)) {
                            seenNodes.add(el);
                            containers.push(el);
                        }
                    });
                }

                const results = [];
                const seenUrls = new Set();
                const adPattern = /(スポンサー|広告|Ad\b)/i;

                for (const el of containers) {
                    if (results.length >= limit) break;
                    const link = el.querySelector('a[href]');
                    if (!link) continue;

                    let href = link.getAttribute('href') || '';
                    if (!href) continue;
                    if (href.startsWith('/aclk') || href.includes('googleadservices')) continue;
                    if (href.startsWith('/')) {
                        href = new URL(href, window.location.origin).href;
                    }
                    if (href.startsWith('https://www.google.com/url?')) {
                        const urlObj = new URL(href);
                        const target = urlObj.searchParams.get('q');
                        if (target) {
                            href = target;
                        }
                    }
                    if (!href || seenUrls.has(href)) continue;

                    const titleEl = el.querySelector('h3, div[role="heading"]');
                    if (!titleEl) continue;
                    const title = titleEl.textContent ? titleEl.textContent.trim() : '';
                    if (!title || title.length < 3) continue;

                    const textContent = el.textContent || '';
                    if (adPattern.test(textContent)) continue;

                    let snippet = '';
                    for (const selector of snippetSelectors) {
                        const candidate = el.querySelector(selector);
                        if (candidate && candidate.textContent) {
                            const text = candidate.textContent.trim();
                            if (text) {
                                snippet = text;
                                break;
                            }
                        }
                    }

                    if (!snippet) {
                        const span = el.querySelector('span');
                        if (span && span.textContent) {
                            snippet = span.textContent.trim();
                        }
                    }

                    results.push({ title, url: href, snippet });
                    seenUrls.add(href);
                }

                return results;
            }
                """,
                limit,
            )

            print(f"抽出候補数 (JS): {len(extracted)}")

            for entry in extracted:
                if len(results) >= limit:
                    break
                url = entry.get("url", "").strip()
                title = entry.get("title", "").strip()
                snippet = entry.get("snippet", "").strip()

                if not title or not url:
                    continue
                if url in seen_urls:
                    continue

                result = {
                    "index": len(results) + 1,
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }

                results.append(result)
                seen_urls.add(url)
                print(f"結果 {result['index']}: {title}")

            screenshot_path = output_dir / "search_result_seo.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"スクリーンショットを保存: {screenshot_path}")

            html_path = output_dir / "page_source_seo.html"
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            print(f"ページHTMLを保存: {html_path}")

            print("結果を確認するため、ブラウザを5秒間開いたままにします...")
            time.sleep(5)

        except Exception as e:
            print(f"エラーが発生しました: {e}")
            import traceback

            traceback.print_exc()

        finally:
            browser.close()

    return results


def save_to_markdown(
    results,
    keyword: str = DEFAULT_KEYWORD,
    keyword_slug: Optional[str] = None,
):
    """
    抽出したオーガニック検索結果をMarkdownファイルに保存
    """
    output_dir = _ensure_output_dir(keyword_slug)
    md_path = output_dir / "organic_results.md"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(f"# {keyword} - オーガニック検索結果 上位{RESULT_LIMIT}件\n\n")
        f.write(f"抽出日時: {time.strftime('%Y年%m月%d日 %H:%M:%S')}\n\n")
        f.write(f"検索キーワード: **{keyword}**\n\n")
        f.write("---\n\n")

        if not results:
            f.write("**該当するオーガニック検索結果が見つかりませんでした。**\n\n")
            f.write("注意: 検索結果は地域、時間帯、検索履歴などによって変動します。\n")
        else:
            f.write(f"## 抽出された記事数: {len(results)}\n\n")

            for result in results:
                f.write(f"### 結果 {result['index']}\n\n")
                f.write(f"**タイトル:** {result['title']}\n\n")
                f.write(f"**URL:** {result['url']}\n\n")
                if result['snippet']:
                    f.write(f"**スニペット:**\n{result['snippet']}\n\n")
                f.write("---\n\n")

    print(f"Markdownファイルを保存: {md_path}")
    return md_path


if __name__ == "__main__":
    print("=== Google オーガニック検索結果抽出ツール ===\n")

    keyword = DEFAULT_KEYWORD
    results = extract_organic_results(keyword)

    print(f"\n抽出完了: {len(results)}件の結果が見つかりました")

    md_file = save_to_markdown(results, keyword)

    print(f"\n完了: {md_file}")
