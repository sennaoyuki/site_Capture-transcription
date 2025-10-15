"""
WebサイトのOCR文字起こしツール
Playwrightでページを取得し、スマートフォン表示のフルスクリーンショットをそのままOCRにかけて文字起こしを行います。
"""

import argparse
import sys
import time
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import os
import subprocess
import shutil

import math

from PIL import Image

# Playwrightのクラッシュレポーターを無効化して権限エラーを避ける
os.environ.setdefault("PLAYWRIGHT_SKIP_CRASH_REPORTER", "1")

# Gemini関連ライブラリをインポート
try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency
    requests = None

from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
    Error as PlaywrightError,
)

# .envファイルから環境変数を読み込む
ENV_PATH = Path(__file__).resolve().parent / ".env"
if load_dotenv is not None:
    load_dotenv(dotenv_path=ENV_PATH)

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_OUTPUT_DIR = SCRIPT_DIR / "output"
BASE_OUTPUT_DIR.mkdir(exist_ok=True)


def get_output_root(keyword_slug: Optional[str] = None) -> Path:
    if keyword_slug:
        root = BASE_OUTPUT_DIR / keyword_slug
    else:
        root = BASE_OUTPUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    return root

ORIGINAL_HOME = Path.home()
PLAYWRIGHT_SANDBOX_HOME = SCRIPT_DIR / ".playwright_home"
PLAYWRIGHT_SANDBOX_HOME.mkdir(parents=True, exist_ok=True)

CRASH_DUMPS_DIR = PLAYWRIGHT_SANDBOX_HOME / "crashpad"
CRASH_DUMPS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_PLAYWRIGHT_BROWSERS = ORIGINAL_HOME / "Library" / "Caches" / "ms-playwright"
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(DEFAULT_PLAYWRIGHT_BROWSERS))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
GENAI_LIB_AVAILABLE = genai is not None
GEMINI_AVAILABLE = False

# APIキーを設定
if GENAI_LIB_AVAILABLE and GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    GEMINI_AVAILABLE = True

SLICE_HEIGHT_DEFAULT = 1400
SLICE_OVERLAP_DEFAULT = 120
DESKTOP_VIEWPORT = {"width": 1400, "height": 900}
DESKTOP_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_0) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def clear_playwright_quarantine() -> None:
    if sys.platform != "darwin":
        return

    candidate_paths = {
        DEFAULT_PLAYWRIGHT_BROWSERS,
        PLAYWRIGHT_SANDBOX_HOME / "Library" / "Caches" / "ms-playwright",
    }

    browsers_path_env = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if browsers_path_env:
        candidate_paths.add(Path(browsers_path_env))

    for path in candidate_paths:
        if not path or not Path(path).exists():
            continue
        try:
            subprocess.run(
                ["xattr", "-dr", "com.apple.quarantine", str(path)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            continue


def prepare_chromium_environment() -> None:
    if sys.platform != "darwin":
        return

    crashpad_dir = PLAYWRIGHT_SANDBOX_HOME / "Library" / "Application Support" / "Chromium" / "Crashpad"
    try:
        crashpad_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["xattr", "-dr", "com.apple.quarantine", str(crashpad_dir)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _resolve_headless_shell():
    browsers_path = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", DEFAULT_PLAYWRIGHT_BROWSERS))
    if not browsers_path.exists():
        return None

    for entry in sorted(browsers_path.glob("chromium_headless_shell-*"), reverse=True):
        potential = entry / "chrome-mac" / "headless_shell"
        if potential.exists():
            return str(potential)
    return None


def build_browser_env() -> dict:
    env = os.environ.copy()
    env["HOME"] = str(PLAYWRIGHT_SANDBOX_HOME)
    env.setdefault("USER", os.environ.get("USER", "playwright"))
    return env


def launch_browser(playwright):
    launch_env = build_browser_env()

    def attempt(label, launcher):
        try:
            print(f"ℹ️ {label} でブラウザ起動を試行します。")
            return launcher()
        except Exception as error:
            print(f"⚠️ {label} の起動に失敗しました: {error}")
            return None

    chromium_args = [
        "--headless=new",
        "--disable-crash-reporter",
        "--disable-crashpad",
        "--disable-features=CrashReporting",
        f"--crash-dumps-dir={CRASH_DUMPS_DIR}",
    ]

    launchers = [
        ("Chromium (新Headless)", lambda: playwright.chromium.launch(headless=True, args=chromium_args, env=launch_env)),
        ("Chromium (Chromeチャンネル)", lambda: playwright.chromium.launch(channel="chrome", headless=True, args=chromium_args, env=launch_env)),
    ]

    headless_shell_path = _resolve_headless_shell()
    if headless_shell_path:
        launchers.append(
            ("Chromium Headless Shell", lambda: playwright.chromium.launch(executable_path=headless_shell_path, headless=True, env=launch_env))
        )

    launchers.extend(
        [
            ("Firefox", lambda: playwright.firefox.launch(headless=True, env=launch_env)),
            ("WebKit", lambda: playwright.webkit.launch(headless=True, env=launch_env)),
        ]
    )

    for label, launcher in launchers:
        browser = attempt(label, launcher)
        if browser is not None:
            return browser

    raise RuntimeError("Playwrightのブラウザを起動できませんでした。`playwright install` やブラウザへの権限設定を確認してください。")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="WebサイトのOCR文字起こしツール")
    parser.add_argument("--url", dest="url", help="文字起こし対象のURL")
    parser.add_argument(
        "--html-path",
        dest="html_path",
        type=Path,
        help="ローカルのHTMLファイルまたはディレクトリを文字起こし対象に指定します",
    )
    parser.add_argument(
        "--slice-height",
        dest="slice_height",
        type=int,
        default=SLICE_HEIGHT_DEFAULT,
        help="スクリーンショット分割時の高さ(px)。大きすぎるとOCR精度が下がります",
    )
    parser.add_argument(
        "--overlap",
        dest="overlap",
        type=int,
        default=SLICE_OVERLAP_DEFAULT,
        help="分割画像同士の重なり(px)。小さすぎると行が欠けやすくなります",
    )
    args = parser.parse_args()

    if args.url and args.html_path:
        parser.error("--url と --html-path は同時に指定できません。")

    return args


def ensure_ocr_ready() -> None:
    if not GENAI_LIB_AVAILABLE:
        print("⚠️ ライブラリ `google-generativeai` が見つからないため、Gemini OCRは利用できません。")
        print("   `pip install google-generativeai` でインストール可能です。")

    if not GOOGLE_API_KEY:
        print("⚠️ 環境変数 `GOOGLE_API_KEY` が設定されていません。Gemini OCRは利用できません。")
        print("   .envファイルを作成するか、環境変数を設定してください。")

    if GEMINI_AVAILABLE:
        print("✅ Gemini OCR (API) を利用します。")
    else:
        print("⚠️ Gemini OCRを使用できないため、Playwrightから取得したテキストのみ保存します。")


def resolve_local_html_path(html_path: Path) -> Path:
    """ローカルLPのエントリポイントとなるHTMLファイルを解決する。"""

    candidate = html_path.expanduser().resolve()

    if candidate.is_dir():
        for default_name in ("index.html", "index.htm"):  # よくあるエントリポイントを探索
            default_path = candidate / default_name
            if default_path.exists():
                return default_path
        raise FileNotFoundError(
            f"ディレクトリ {candidate} に index.html / index.htm が見つかりません。"
        )

    if not candidate.exists():
        raise FileNotFoundError(f"HTMLファイルが見つかりません: {candidate}")

    if candidate.is_file():
        return candidate

    raise FileNotFoundError(f"指定されたパスはファイルまたはディレクトリではありません: {candidate}")


def load_page(page, url: str) -> None:
    print(f"📄 ページを読み込み中: {url}")
    try:
        # networkidleだけで十分（ネットワーク通信が500ms以内に落ち着くまで待つ）
        page.goto(url, wait_until="networkidle", timeout=60000, referer="https://www.google.com/")
        print("✅ ページ読み込み完了")
    except PlaywrightTimeoutError:
        print("⚠️ タイムアウト、取得可能な範囲で続行")

    # スクロールで遅延読み込みをトリガー
    scroll_page(page)
    time.sleep(1.0)


def scroll_page(page) -> None:
    body_height = page.evaluate("() => document.body.scrollHeight")
    checkpoints = [0.25, 0.5, 0.75, 1.0]

    for ratio in checkpoints:
        target = int(body_height * ratio)
        page.evaluate("(y) => window.scrollTo({top: y, behavior: 'smooth'})", target)
        time.sleep(1.5)

    page.evaluate("() => window.scrollTo(0, 0)")
    time.sleep(1.0)


def collect_meta(page) -> Dict[str, str]:
    meta: Dict[str, str] = {"title": page.title()}

    description_locator = page.locator('meta[name="description"]')
    meta["description"] = (
        description_locator.first.get_attribute("content")
        if description_locator.count() > 0
        else ""
    ) or ""

    keywords_locator = page.locator('meta[name="keywords"]')
    meta["keywords"] = (
        keywords_locator.first.get_attribute("content")
        if keywords_locator.count() > 0
        else ""
    ) or ""

    return meta


def fetch_visible_text(page) -> str:
    return page.evaluate(
        r"""
        () => {
            const excludeSelectors = ['script', 'style', 'noscript', 'iframe'];
            excludeSelectors.forEach(selector => {
                document.querySelectorAll(selector).forEach(el => el.remove());
            });

            const text = document.body.innerText;
            return text.replace(/\n\s*\n/g, '\n\n').trim();
        }
        """
    )


def capture_page_screenshots(page, run_dir: Path, slice_height: int = 1400, overlap: int = 120) -> tuple[Path, List[Dict[str, Any]]]:
    """Playwrightで直接スライススクリーンショットを取得（最適化版）"""
    segments_dir = run_dir / "segments"
    segments_dir.mkdir(exist_ok=True)

    try:
        # ページ全体の高さとビューポート幅を取得
        total_height = page.evaluate("() => document.body.scrollHeight")
        viewport = page.viewport_size or {"width": 1400, "height": 900}
        viewport_width = viewport["width"]

        print(f"📏 ページ全体の高さ: {total_height}px")

        # ビューポートの高さをslice_heightに設定
        page.set_viewport_size({"width": viewport_width, "height": slice_height})

        segments_meta = []
        segment_paths = []
        current_top = 0
        index = 1

        while current_top < total_height:
            # スクロール位置を設定
            page.evaluate(f"() => window.scrollTo(0, {current_top})")
            time.sleep(0.3)  # 画像読み込み待機

            # 現在のビューポートをスクリーンショット
            segment_path = segments_dir / f"segment_{index:04d}.png"
            page.screenshot(path=str(segment_path), full_page=False)

            # 実際の高さを計算
            actual_height = min(slice_height, total_height - current_top)

            segments_meta.append({
                "index": index,
                "path": str(segment_path),
                "top": current_top,
                "bottom": current_top + actual_height,
            })
            segment_paths.append(segment_path)

            print(f"  📸 スライス #{index} ({current_top}px ~ {current_top + actual_height}px)")

            # 次のスライス位置（オーバーラップを考慮）
            current_top += slice_height - overlap
            index += 1

            # 最後のスライスを超えた場合は終了
            if current_top >= total_height:
                break

        # ビューポートを元に戻す
        page.set_viewport_size(viewport)
        page.evaluate("() => window.scrollTo(0, 0)")

        print(f"✅ {len(segments_meta)} 個のスライススクリーンショットを取得しました")

        # フルページ画像を結合
        screenshot_path = run_dir / "full_page.png"
        merge_segment_images(segment_paths, screenshot_path)
        print(f"✅ フルページ画像を結合しました")

        return screenshot_path, segments_meta

    except Exception as error:
        print(f"⚠️ フルページのスクリーンショット取得に失敗したため、分割キャプチャに切り替えます: {error}")
        segment_paths = capture_fallback_segments(page, run_dir, parts=2)

        segments_meta = []
        offset = 0
        for idx, segment_path in enumerate(segment_paths, start=1):
            with Image.open(segment_path) as img:
                height = img.height
            segments_meta.append(
                {
                    "index": idx,
                    "path": str(segment_path),
                    "top": offset,
                    "bottom": offset + height,
                }
            )
            offset += height

        try:
            merge_segment_images(segment_paths, screenshot_path)
        except Exception as merge_error:
            print(f"⚠️ 分割画像の結合に失敗しました: {merge_error}")

        return screenshot_path, segments_meta


def capture_full_page_screenshot(page, path: Path) -> None:
    page.screenshot(
        path=str(path),
        full_page=True,
        animations="disabled",
        timeout=120_000,
    )


def capture_fallback_segments(
    page,
    run_dir: Path,
    parts: Optional[int] = None,
) -> List[Path]:
    segments_dir = run_dir / "segments"
    segments_dir.mkdir(exist_ok=True)

    viewport = page.viewport_size or DESKTOP_VIEWPORT
    width = viewport["width"]
    viewport_height = viewport["height"] or 1

    total_height = page.evaluate("() => document.body.scrollHeight")
    if parts is None:
        required_parts = math.ceil(total_height / viewport_height)
    else:
        required_parts = max(parts, math.ceil(total_height / viewport_height))

    required_parts = max(1, required_parts)
    step = max(total_height // required_parts, viewport_height)

    paths: List[Path] = []
    for index in range(required_parts):
        scroll_top = min(index * step, max(0, total_height - viewport_height))
        page.evaluate("(y) => window.scrollTo(0, y)", scroll_top)
        time.sleep(1.5)

        clip_height = min(viewport_height, total_height - scroll_top)
        if clip_height <= 0:
            break

        segment_path = segments_dir / f"segment_{index + 1:02d}.png"
        page.screenshot(
            path=str(segment_path),
            full_page=False,
            animations="disabled",
            timeout=120_000,
            clip={
                "x": 0,
                "y": 0,
                "width": width,
                "height": clip_height,
            },
        )
        paths.append(segment_path)

    page.evaluate("() => window.scrollTo(0, 0)")

    if not paths:
        raise RuntimeError("フォールバック用のスクリーンショット取得に失敗しました。")

    return paths


def load_and_capture(
    context,
    url: str,
    run_dir: Path,
    slice_height: int = 1400,
    overlap: int = 120,
) -> tuple:
    page = context.new_page()
    load_page(page, url)
    meta = collect_meta(page)
    visible_text = ""  # Playwright HTML抽出を無効化
    screenshot_path, segments_meta = capture_page_screenshots(page, run_dir, slice_height, overlap)
    return page, meta, visible_text, screenshot_path, segments_meta


def sanitize_html_for_static_render(html: str, base_url: str) -> str:
    cleaned = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", "", html, flags=re.IGNORECASE | re.DOTALL)
    if "<base" not in cleaned.lower():
        head_insertion = "<head>"
        base_tag = f"<base href=\"{base_url}\">"
        if head_insertion in cleaned:
            cleaned = cleaned.replace(head_insertion, head_insertion + base_tag, 1)
        else:
            cleaned = base_tag + cleaned
    return cleaned


def capture_static_render(
    playwright,
    url: str,
    run_dir: Path,
    context_options: dict,
    slice_height: int = 1400,
    overlap: int = 120,
) -> tuple[Dict[str, str], str, Path, List[Dict[str, Any]]]:
    if requests is None:
        raise RuntimeError("requests ライブラリが見つからないため、HTMLダウンロード方式のキャプチャに失敗しました。")

    headers = {
        "User-Agent": DESKTOP_USER_AGENT,
        "Referer": "https://www.google.com/",
    }
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
    except Exception as error:
        raise RuntimeError(f"HTMLのダウンロードに失敗しました: {error}") from error

    sanitized_html = sanitize_html_for_static_render(response.text, base_url=url)

    browser = launch_browser(playwright)
    context = browser.new_context(**context_options)
    page = None
    try:
        page = context.new_page()
        page.set_content(sanitized_html, wait_until="load", timeout=120000)
        meta = collect_meta(page)
        visible_text = ""  # Playwright HTML抽出を無効化
        screenshot_path, segments_meta = capture_page_screenshots(page, run_dir, slice_height, overlap)
    finally:
        if page and not page.is_closed():
            try:
                page.close()
            except PlaywrightError:
                pass
        try:
            context.close()
        except PlaywrightError:
            pass
        try:
            browser.close()
        except PlaywrightError:
            pass

    return meta, visible_text, screenshot_path, segments_meta


def merge_segment_images(segment_paths: List[Path], output_path: Path) -> None:
    images = [Image.open(p).convert("RGB") for p in segment_paths]
    try:
        width = max(img.width for img in images)
        total_height = sum(img.height for img in images)
        merged = Image.new("RGB", (width, total_height), color=(255, 255, 255))

        current_y = 0
        for img in images:
            merged.paste(img, (0, current_y))
            current_y += img.height

        merged.save(output_path)
    finally:
        for img in images:
            img.close()


def extract_text_from_genai_response(response) -> str:
    if response is None:
        return ""

    text = getattr(response, "text", None)
    if text:
        return text

    texts: List[str] = []
    for candidate in getattr(response, "candidates", []) or []:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", []) if content else []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                texts.append(part_text)
    return "\n".join(texts)


def run_gemini_ocr(image_path: str) -> str:
    """
    Gemini APIを呼び出して画像からテキストを抽出する
    """
    if not GEMINI_AVAILABLE:
        return ""

    try:
        print(f"    - Gemini APIでOCR処理中: {Path(image_path).name}")
        model = genai.GenerativeModel("gemini-2.0-flash-exp")
        
        # 画像を直接読み込んで送信（upload_fileを使わない方法）
        from PIL import Image
        img = Image.open(image_path)
        image_file = img
        try:
            response = model.generate_content(
                [
                    """# 命令
あなたは、WebコンテンツとUXの構造を分析する専門家です。これから送付される複数の画像（ランディングページを上から順にスライスしたもの）を分析し、その構成と文脈を完全に再現した上で、内容をMarkdown形式のテキストとして高品質な文字起こししてください。

---

# 背景とコンテキスト
- **対象:** あるサービスのランディングページ（LP）
- **入力データ:** LPを上から順に分割した一連の画像ファイル。
- **最終目標:** 画像に含まれる情報を、元のLPの論理的な流れや階層構造（見出し、本文、箇条書き、CTAなど）を保持したまま、単一のMarkdownドキュメントに再構成すること。単なる文字の抜き出しではなく、マーケティング上の文脈を理解した上での再構成を求めます。

---

# 実行ステップ
1.  提供された画像を、ファイル名や送信された順番通りに、上から下への流れとして認識してください。
2.  各画像の内容を分析し、それがLPのどの構成要素（例: ファーストビュー、問題提起、解決策の提示、お客様の声、CTA）に該当するかを頭の中で把握します。
3.  画像に含まれる全てのテキストを、一言一句正確に文字起こしします。
4.  テキストの役割（大見出し、小見出し、本文、箇条書き、ボタンの文言など）を判断します。
5.  判断した役割に基づき、以下の出力形式のルールに従って、全てのテキストを単一のMarkdownドキュメントとして整形し、出力してください。

---

# 出力形式
- **大見出し (H1):** `# 見出し`
- **セクション見出し (H2):** `## セクション見出し`
- **小見出し (H3):** `### 小見出し`
- **本文:** 通常のテキスト
- **強調:** 太字で表現されている箇所は `**強調テキスト**` を使用してください。
- **箇条書き:** `- リスト項目` の形式を使用してください。
- **お客様の声や引用:** `> 引用文` の形式を使用してください。
- **コールトゥアクション (CTA) / ボタン:** `[CTA] ボタンのテキスト` という形式で明確に示してください。

---

# 制約事項
- 画像に含まれるテキストは、装飾的なものであっても原則としてすべて文字起こししてください。
- 画像の順番をLPのストーリーテリングの順番とみなし、厳守してください。
- あなた自身の意見や追加情報は含めず、画像の内容のみを忠実に再現してください。
""",
                    image_file,
                ],
                generation_config={"temperature": 0.0},
            )
        finally:
            # 画像を直接渡しているので削除不要
            pass

        text = extract_text_from_genai_response(response).strip()
        return text

    except Exception as e:
        print(f"❌ Gemini APIの呼び出し中にエラーが発生しました: {e}")
        return ""


def run_ocr_on_segments(segments: List[Dict[str, any]]) -> List[Dict[str, any]]:
    """セグメントのOCRを並列処理（最適化版）"""
    if not GEMINI_AVAILABLE:
        print("⚠️ Gemini OCRが利用できないため、OCRセグメント処理をスキップします。")
        results = []
        for segment in segments:
            results.append(
                {
                    "index": segment["index"],
                    "path": Path(segment["path"]),
                    "top": segment["top"],
                    "bottom": segment["bottom"],
                    "raw_text": "",
                    "clean_text": "",
                }
            )
        return results

    print(f"🔍 {len(segments)} 個のセグメントをGeminiで並列OCR処理中...")

    def process_single_segment(segment):
        """単一セグメントのOCR処理"""
        try:
            print(f"  🔍 セグメント {segment['index']} 処理中...")
            ocr_raw = run_gemini_ocr(segment["path"])
            raw_text = ocr_raw.strip()
            clean_text = clean_ocr_text(raw_text)

            return {
                "index": segment["index"],
                "path": Path(segment["path"]),
                "top": segment["top"],
                "bottom": segment["bottom"],
                "raw_text": raw_text,
                "clean_text": clean_text,
            }
        except Exception as e:
            print(f"  ❌ セグメント {segment['index']} のOCRエラー: {e}")
            return {
                "index": segment["index"],
                "path": Path(segment["path"]),
                "top": segment["top"],
                "bottom": segment["bottom"],
                "raw_text": "",
                "clean_text": "",
            }

    # ThreadPoolExecutorで並列処理（最大3スレッド）
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_segment = {executor.submit(process_single_segment, seg): seg for seg in segments}

        for future in as_completed(future_to_segment):
            result = future.result()
            results.append(result)

    # インデックスでソート
    results.sort(key=lambda x: x["index"])

    print(f"✅ {len(results)} 個のセグメントのOCR処理が完了しました")
    return results


def clean_ocr_text(raw_text: str) -> str:
    if not raw_text:
        return ""

    lines = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if re.fullmatch(r"[\W_]+", stripped):
            continue
        lines.append(stripped)

    if not lines:
        return ""

    paragraphs: List[str] = []
    buffer: List[str] = []

    for line in lines:
        buffer.append(line)
        if line.endswith(("。", "！", "？", "!", "?")) or len(line) > 40:
            paragraphs.append("".join(buffer))
            buffer = []

    if buffer:
        paragraphs.append("".join(buffer))

    deduped: List[str] = []
    seen = set()

    for paragraph in paragraphs:
        key = paragraph.replace(" ", "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(paragraph)

    return "\n".join(deduped)


def combine_clean_segments(segments: List[Dict[str, str]]) -> str:
    combined: List[str] = []
    seen = set()

    for segment in segments:
        text = segment.get("clean_text", "").strip()
        if not text:
            continue

        for paragraph in [p.strip() for p in text.split("\n") if p.strip()]:
            if paragraph in seen:
                continue
            seen.add(paragraph)
            combined.append(paragraph)

    return "\n\n".join(combined)


def save_markdown(result: Dict) -> Path:
    md_path = result["run_dir"] / "website_transcription.md"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# WebサイトOCR文字起こし結果\n\n")
        f.write(f"**URL:** {result['url']}\n\n")
        f.write(f"**抽出日時:** {result['timestamp']}\n\n")
        f.write(f"**スクリーンショット:** {result['screenshot'].name}\n\n")

        if result.get("source_type") == "local_html" and result.get("source_path"):
            f.write(f"**ローカルHTML:** {result['source_path']}\n\n")
        f.write(f"**分割数:** {len(result['segments'])} 枚\n\n")

        if result.get("meta"):
            f.write("## メタ情報\n\n")
            f.write(f"- タイトル: {result['meta'].get('title', '')}\n")
            if result['meta'].get('description'):
                f.write(
                    f"- 説明: {result['meta'].get('description', '').strip()}\n"
                )
            if result['meta'].get('keywords'):
                f.write(f"- キーワード: {result['meta'].get('keywords', '').strip()}\n")
            f.write("\n")

        if result.get("combined_text"):
            f.write("## 整理済みテキスト\n\n")
            f.write(result["combined_text"] + "\n\n")

        # Playwright抽出テキストセクションを削除（OCRのみ使用）

        f.write("## OCRセグメント詳細\n\n")
        for segment in result["segments"]:
            f.write(f"### セグメント {segment['index']:02d}\n\n")
            f.write(f"- ファイル: {segment['path'].name}\n")
            f.write(
                f"- 位置: {segment['top']}px 〜 {segment['bottom']}px\n\n"
            )

            if segment.get("clean_text"):
                f.write("**整形テキスト**\n\n")
                f.write("```\n")
                f.write(segment["clean_text"])
                f.write("\n```\n\n")

            if segment.get("raw_text") and segment.get("raw_text") != segment.get("clean_text"):
                f.write("**OCR生テキスト**\n\n")
                f.write("```\n")
                f.write(segment["raw_text"])
                f.write("\n```\n\n")

    return md_path


def save_plain_text(result: Dict) -> Path:
    txt_path = result["run_dir"] / "website_transcription.txt"

    with open(txt_path, "w", encoding="utf-8") as f:
        if result.get("combined_text"):
            f.write(result["combined_text"])
        # visible_textのフォールバックを削除（OCRのみ使用）

    return txt_path


def cleanup_segment_images(result: Dict) -> None:
    segments_dir = result["run_dir"] / "segments"
    if segments_dir.exists():
        try:
            shutil.rmtree(segments_dir)
            print("🧹 分割キャプチャ画像を削除しました。")
        except Exception as cleanup_error:
            print(f"⚠️ 分割画像の削除中にエラーが発生しました: {cleanup_error}")


def update_latest_symlink(run_dir: Path, output_root: Optional[Path] = None) -> None:
    base_root = output_root or run_dir.parent
    latest_link = base_root / "latest"

    try:
        if latest_link.is_symlink() or latest_link.exists():
            if latest_link.is_dir() and not latest_link.is_symlink():
                shutil.rmtree(latest_link)
            else:
                latest_link.unlink()

        latest_link.symlink_to(run_dir, target_is_directory=True)
        print(f"🔁 最新出力へのリンクを更新しました: {latest_link} -> {run_dir}")
    except Exception as link_error:
        print(f"⚠️ 最新出力リンクの更新に失敗しました: {link_error}")


def transcribe_website(
    url: str,
    slice_height: int,
    overlap: int,
    keyword_slug: Optional[str] = None,
    *,
    source_type: str = "url",
    source_path: Optional[Path] = None,
) -> Dict:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_root = get_output_root(keyword_slug)
    run_dir = output_root / f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=True)

    screenshot_path: Optional[Path] = None

    with sync_playwright() as playwright:
        clear_playwright_quarantine()
        prepare_chromium_environment()
        context_options = {
            "locale": "ja-JP",
            "timezone_id": "Asia/Tokyo",
            "viewport": DESKTOP_VIEWPORT,
            "user_agent": DESKTOP_USER_AGENT,
            "is_mobile": False,
            "has_touch": False,
            "device_scale_factor": 1,
            "bypass_csp": True,
            "extra_http_headers": {
                "Referer": "https://www.google.com/",
            },
        }

        meta: Dict[str, str] = {}
        visible_text = ""
        segments_meta: List[Dict[str, int]] = []
        screenshot_path: Optional[Path] = None

        capture_success = False
        capture_error: Optional[Exception] = None

        for attempt in range(2):
            local_context_options = dict(context_options)
            if attempt == 1:
                print("⚠️ JavaScriptを無効化して再試行します。")
                local_context_options["java_script_enabled"] = False
            browser = launch_browser(playwright)
            context = browser.new_context(**local_context_options)
            try:
                context.add_init_script("""
                    (function() {
                        const noop = function noop() {};
                        try {
                            Object.defineProperty(window, 'close', { value: noop, configurable: true });
                        } catch (_) {
                            window.close = noop;
                        }
                        try {
                            window.open = function() { return window; };
                        } catch (_) {}
                        try {
                            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                        } catch (_) {}
                        try {
                            delete window.__nightmare;
                            delete window.__selenium_unwrapped;
                            delete window._Selenium_IDE_Recorder;
                        } catch (_) {}
                    })();
                """)
            except PlaywrightError:
                pass
            page = None
            try:
                if attempt > 0:
                    print("🔁 ページを再読み込みしてキャプチャを再試行します。")
                page, meta, visible_text, screenshot_path, segments_meta = load_and_capture(
                    context=context,
                    url=url,
                    run_dir=run_dir,
                    slice_height=slice_height,
                    overlap=overlap,
                )
            except Exception as error:
                capture_error = error
                attempt_no = attempt + 1
                print(f"⚠️ ページキャプチャに失敗しました (試行{attempt_no}): {error}")
            else:
                capture_success = True
                break
            finally:
                if page and not page.is_closed():
                    try:
                        page.close()
                    except PlaywrightError:
                        pass
                try:
                    context.close()
                except PlaywrightError:
                    pass
                try:
                    browser.close()
                except PlaywrightError:
                    pass

        if not capture_success or not screenshot_path:
            print("⚠️ 通常のブラウザ操作でページを保持できなかったため、HTMLダウンロード方式で再試行します。")
            try:
                meta, visible_text, screenshot_path, segments_meta = capture_static_render(
                    playwright=playwright,
                    url=url,
                    run_dir=run_dir,
                    context_options=dict(context_options),
                    slice_height=slice_height,
                    overlap=overlap,
                )
                capture_success = True
            except Exception as fallback_error:
                raise RuntimeError(
                    "スクリーンショットの取得に失敗しました。"
                    + (f" 原因: {capture_error}" if capture_error else "")
                    + f" / HTMLダウンロード方式も失敗しました: {fallback_error}"
                ) from fallback_error

    if not segments_meta:
        segments_meta = [
            {
                "index": 1,
                "path": str(screenshot_path) if screenshot_path else "",
                "top": 0,
                "bottom": 0,
            }
        ]

    if not screenshot_path:
        raise RuntimeError("スクリーンショットの取得に失敗しました。")

    ocr_segments = run_ocr_on_segments(segments_meta)
    combined_text = combine_clean_segments(ocr_segments)

    if not combined_text:
        combined_text = visible_text

    result = {
        "url": url,
        "timestamp": timestamp,
        "run_dir": run_dir,
        "screenshot": screenshot_path,
        "segments": ocr_segments,
        "combined_text": combined_text,
        "visible_text": visible_text,
        "meta": meta,
        "slice_height": slice_height,
        "overlap": overlap,
        "keyword_slug": keyword_slug,
        "output_root": output_root,
        "source_type": source_type,
    }

    if source_path is not None:
        result["source_path"] = str(source_path)

    return result


def transcribe_local_html(
    html_path: Path,
    slice_height: int,
    overlap: int,
    keyword_slug: Optional[str] = None,
) -> Dict:
    """ローカルに保存されたLPをスクリーンショット＆文字起こしする。"""

    resolved_html = resolve_local_html_path(html_path)
    file_url = resolved_html.as_uri()

    return transcribe_website(
        url=file_url,
        slice_height=slice_height,
        overlap=overlap,
        keyword_slug=keyword_slug,
        source_type="local_html",
        source_path=resolved_html,
    )


def main() -> None:
    args = parse_args()
    ensure_ocr_ready()

    target_mode = "url"
    target_url: Optional[str] = None
    target_html: Optional[Path] = None

    if args.html_path is not None:
        target_mode = "local_html"
        target_html = args.html_path
    else:
        candidate = args.url or input("文字起こし対象のURLまたはローカルHTMLパスを入力してください: ").strip()
        if not candidate:
            print("❌ URL / HTMLパスが指定されていません。")
            sys.exit(1)

        potential_path = Path(candidate).expanduser()
        if potential_path.exists():
            target_mode = "local_html"
            target_html = potential_path
        else:
            target_url = candidate

    print("=" * 70)
    print("🌐 WebサイトOCR文字起こしツール (Gemini版)")
    print("=" * 70)

    if target_mode == "local_html":
        assert target_html is not None
        result = transcribe_local_html(
            html_path=target_html,
            slice_height=args.slice_height,
            overlap=args.overlap,
        )
    else:
        assert target_url is not None
        result = transcribe_website(
            url=target_url,
            slice_height=args.slice_height,
            overlap=args.overlap,
        )

    md_path = save_markdown(result)
    txt_path = save_plain_text(result)
    cleanup_segment_images(result)
    update_latest_symlink(result["run_dir"], output_root=result.get("output_root"))

    print("\n" + "=" * 70)
    print("🎉 処理完了！")
    print("=" * 70)
    print(f"📁 出力フォルダ: {result['run_dir']}")
    print(f"- Markdown: {md_path.name}")
    print(f"- テキスト : {txt_path.name}")
    print(f"- スクリーンショット: {result['screenshot'].name}")
    print(f"- セグメント数: {len(result['segments'])}")


if __name__ == "__main__":
    main()
