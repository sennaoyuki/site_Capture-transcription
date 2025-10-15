import argparse
import os
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import google.generativeai as genai

import transcribe_website
import summarize_analyses
import extract_seo

SCRIPT_DIR = Path(__file__).resolve().parent


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    lowered = normalized.lower()
    slug = re.sub(r"[^0-9a-zA-Z一-龥ぁ-んァ-ヶー_]+", "_", lowered).strip("_")
    return slug or "default"


def _finalize_transcription(result: dict) -> Path:
    md_path = transcribe_website.save_markdown(result)
    transcribe_website.save_plain_text(result)
    transcribe_website.cleanup_segment_images(result)
    transcribe_website.update_latest_symlink(
        result["run_dir"],
        output_root=result.get("output_root"),
    )
    return md_path


def run_transcription(
    url: str,
    slice_height: int,
    overlap: int,
    keyword_slug: Optional[str] = None,
) -> Path:
    transcribe_website.ensure_ocr_ready()

    result = transcribe_website.transcribe_website(
        url=url,
        slice_height=slice_height,
        overlap=overlap,
        keyword_slug=keyword_slug,
    )

    return _finalize_transcription(result)


def run_local_transcription(
    html_path: Path,
    slice_height: int,
    overlap: int,
    keyword_slug: Optional[str] = None,
) -> Path:
    transcribe_website.ensure_ocr_ready()

    result = transcribe_website.transcribe_local_html(
        html_path=html_path,
        slice_height=slice_height,
        overlap=overlap,
        keyword_slug=keyword_slug,
    )

    return _finalize_transcription(result)


def generate_analysis_request(
    prompt_file: Path,
    transcript_path: Path,
    keyword: str,
    conversion_goal: str,
) -> Path:
    if not prompt_file.exists():
        raise FileNotFoundError(f"prompt file not found: {prompt_file}")
    if not transcript_path.exists():
        raise FileNotFoundError(f"transcript file not found: {transcript_path}")

    template = prompt_file.read_text(encoding="utf-8")
    transcript_text = transcript_path.read_text(encoding="utf-8").strip()

    filled = (
        template.replace("{{KEYWORD}}", keyword)
        .replace("{{CONVERSION_GOAL}}", conversion_goal)
        .replace("{{TRANSCRIPT}}", transcript_text)
    )

    output_path = transcript_path.parent / "analysis_request.md"
    output_path.write_text(filled, encoding="utf-8")
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "URL の文字起こしを実行し、マーケティング分析プロンプトの生成と Gemini による分析を行います。"
        )
    )
    url_group = parser.add_mutually_exclusive_group(required=False)
    url_group.add_argument("--url", help="文字起こし対象の URL")
    url_group.add_argument(
        "--url-list",
        type=Path,
        help="URL の一覧を記載したファイル。各行または `URL:` 行に含まれるリンクを対象にします。",
    )
    parser.add_argument(
        "--local-html",
        type=Path,
        action="append",
        help="ローカルに保存したLP (HTMLファイルまたはディレクトリ) を分析対象として追加します。複数指定するにはオプションを繰り返してください。",
    )
    parser.add_argument("--keyword", required=True, help="検索キーワード")
    parser.add_argument(
        "--conversion-goal",
        required=True,
        help="想定しているコンバージョン（例: 無料相談予約）",
    )
    parser.add_argument(
        "--slice-height",
        type=int,
        default=transcribe_website.SLICE_HEIGHT_DEFAULT,
        help="スクリーンショット分割時の高さ(px)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=transcribe_website.SLICE_OVERLAP_DEFAULT,
        help="分割画像同士の重なり(px)",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=SCRIPT_DIR / "prompts/marketing_analysis_prompt.md",
        help="マーケティング分析用プロンプトのテンプレート",
    )
    parser.add_argument(
        "--gemini-model",
        default="models/gemini-2.5-flash",
        help="分析に使用する Gemini モデル ID",
    )
    parser.add_argument(
        "--skip-gemini",
        action="store_true",
        help="Gemini による分析実行をスキップし、analysis_request.md の生成までで終了します。",
    )
    parser.add_argument(
        "--summary-prompt-file",
        type=Path,
        default=SCRIPT_DIR / "prompts/consolidated_analysis_prompt.md",
        help="URL一覧処理時に使う統合レポート用プロンプトテンプレート",
    )
    parser.add_argument(
        "--summary-output",
        type=Path,
        default=None,
        help="統合レポートの出力先。未指定の場合は runs-dir 配下に timestamp 付きで作成",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="URL一覧処理時に統合レポートを生成しません。",
    )
    parser.add_argument(
        "--use-seo",
        action="store_true",
        help="指定キーワードのSEO上位サイトを自動抽出し、分析対象に追加します。",
    )
    parser.add_argument(
        "--seo-limit",
        type=int,
        default=extract_seo.RESULT_LIMIT,
        help=f"SEO抽出で処理する最大件数 (既定: {extract_seo.RESULT_LIMIT})",
    )

    args = parser.parse_args()

    if args.seo_limit <= 0:
        parser.error("--seo-limit には1以上の値を指定してください。")

    if not args.url and not args.url_list and not args.use_seo and not args.local_html:
        parser.error("--url / --url-list / --use-seo / --local-html のいずれかは指定が必要です。")

    if not args.prompt_file.is_absolute():
        args.prompt_file = (SCRIPT_DIR / args.prompt_file).resolve()
    if not args.summary_prompt_file.is_absolute():
        args.summary_prompt_file = (SCRIPT_DIR / args.summary_prompt_file).resolve()

    return args


def run_gemini_analysis(
    analysis_prompt_path: Path,
    model_name: str,
) -> Path:
    if not analysis_prompt_path.exists():
        raise FileNotFoundError(f"analysis prompt not found: {analysis_prompt_path}")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("環境変数 GOOGLE_API_KEY が設定されていません。")

    genai.configure(api_key=api_key)

    prompt_text = analysis_prompt_path.read_text(encoding="utf-8")

    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt_text,
        generation_config={"temperature": 0.2},
    )

    result_text = (
        transcribe_website.extract_text_from_genai_response(response).strip()
        if hasattr(transcribe_website, "extract_text_from_genai_response")
        else (response.text or "").strip()
    )

    if not result_text:
        raise RuntimeError("Gemini から有効なテキスト応答が得られませんでした。")

    output_path = analysis_prompt_path.parent / "analysis_result_gemini.md"
    output_path.write_text(result_text, encoding="utf-8")
    return output_path


def extract_urls_from_file(url_file: Path) -> list[str]:
    import re

    text = url_file.read_text(encoding="utf-8")
    candidates = re.findall(r'https?://[^\s)>\]]+', text)
    urls: list[str] = []
    seen = set()
    for c in candidates:
        normalized = c.strip().rstrip('.,)')
        if normalized and normalized not in seen:
            seen.add(normalized)
            urls.append(normalized)
    return urls


def main() -> None:
    args = parse_args()

    keyword_slug = slugify(args.keyword)

    urls: list[str] = []
    url_metadata: dict[str, dict[str, str]] = {}
    local_html_entries: list[Path] = []

    if args.use_seo:
        print("🔍 SEOオーガニック結果を抽出中...")
        try:
            seo_results = extract_seo.extract_organic_results(
                keyword=args.keyword,
                limit=args.seo_limit,
                keyword_slug=keyword_slug,
            )
            if seo_results:
                extract_seo.save_to_markdown(
                    seo_results,
                    args.keyword,
                    keyword_slug=keyword_slug,
                )
                for entry in seo_results:
                    normalized_url = (entry.get("url") or "").strip()
                    if not normalized_url:
                        continue
                    if normalized_url in url_metadata:
                        continue
                    urls.append(normalized_url)
                    url_metadata[normalized_url] = {
                        "source": "seo",
                        "title": entry.get("title", ""),
                        "snippet": entry.get("snippet", ""),
                    }
            else:
                print("⚠️ SEO抽出で有効な結果が得られませんでした。")
        except Exception as error:
            print(f"⚠️ SEO抽出に失敗しました: {error}", file=sys.stderr)

    manual_urls: list[str] = []
    if args.url_list:
        if not args.url_list.exists():
            print(f"❌ URL一覧ファイルが見つかりません: {args.url_list}", file=sys.stderr)
            sys.exit(1)
        manual_urls = extract_urls_from_file(args.url_list)
        if not manual_urls:
            print(f"❌ URL一覧ファイルから有効なリンクが見つかりませんでした: {args.url_list}", file=sys.stderr)
            sys.exit(1)
    elif args.url:
        manual_urls = [args.url.strip()]

    for manual_url in manual_urls:
        normalized = manual_url.strip()
        if not normalized:
            continue
        if normalized in url_metadata:
            continue
        urls.append(normalized)
        url_metadata[normalized] = {"source": "manual"}

    if args.local_html:
        for entry in args.local_html:
            try:
                resolved = transcribe_website.resolve_local_html_path(entry)
            except FileNotFoundError as error:
                print(f"⚠️ ローカルLPの読み込みに失敗しました: {error}", file=sys.stderr)
                continue

            if resolved in local_html_entries:
                continue

            local_html_entries.append(resolved)

    if not urls and not local_html_entries:
        print("❌ 処理対象となるURL/ローカルLPが見つかりませんでした。", file=sys.stderr)
        sys.exit(1)

    targets: list[dict[str, object]] = []

    print("処理対象一覧:")
    for idx, target_url in enumerate(urls, start=1):
        meta = url_metadata.get(target_url, {})
        source_label = "SEO抽出" if meta.get("source") == "seo" else "指定URL"
        print(f"  {idx}. {target_url} ({source_label})")
        if meta.get("title"):
            print(f"     タイトル: {meta['title']}")
        targets.append({
            "type": "url",
            "value": target_url,
            "meta": meta,
            "label": source_label,
        })

    base_idx = len(targets)
    for offset, html_path in enumerate(local_html_entries, start=1):
        idx = base_idx + offset
        display_path = str(html_path)
        print(f"  {idx}. {display_path} (ローカルLP)")
        targets.append(
            {
                "type": "local_html",
                "value": html_path,
                "meta": {
                    "source": "local_html",
                    "html_path": str(html_path),
                },
                "label": "ローカルLP",
            }
        )

    overall_results = []

    total_targets = len(targets)

    for idx, target in enumerate(targets, start=1):
        print("=" * 80)

        target_type = target.get("type")
        meta = target.get("meta") or {}
        label = target.get("label") or ("ローカルLP" if target_type == "local_html" else "指定URL")

        if target_type == "local_html":
            html_path = Path(target.get("value"))
            target_identifier = str(html_path)
            target_url = html_path.resolve().as_uri()
            print(f"[{idx}/{total_targets}] {target_identifier} (ローカルLP) の処理を開始します。")
        else:
            target_url = str(target.get("value"))
            target_identifier = target_url
            print(f"[{idx}/{total_targets}] {target_url} の処理を開始します。")

        try:
            if target_type == "local_html":
                transcript_path = run_local_transcription(
                    html_path=Path(target.get("value")),
                    slice_height=args.slice_height,
                    overlap=args.overlap,
                    keyword_slug=keyword_slug,
                )
            else:
                transcript_path = run_transcription(
                    url=target_url,
                    slice_height=args.slice_height,
                    overlap=args.overlap,
                    keyword_slug=keyword_slug,
                )
        except Exception as error:
            msg = f"文字起こし処理でエラーが発生しました ({target_identifier}): {error}"
            print(f"❌ {msg}", file=sys.stderr)
            overall_results.append(
                {
                    "url": target_url,
                    "html_path": target_identifier if target_type == "local_html" else None,
                    "source": meta.get("source") or ("local_html" if target_type == "local_html" else "manual"),
                    "title": meta.get("title"),
                    "snippet": meta.get("snippet"),
                    "label": label,
                    "success": False,
                    "error": msg,
                }
            )
            continue

        try:
            analysis_prompt_path = generate_analysis_request(
                prompt_file=args.prompt_file,
                transcript_path=transcript_path,
                keyword=args.keyword,
                conversion_goal=args.conversion_goal,
            )
        except Exception as error:
            msg = f"マーケティング分析用プロンプトの生成でエラーが発生しました ({target_identifier}): {error}"
            print(f"❌ {msg}", file=sys.stderr)
            overall_results.append(
                {
                    "url": target_url,
                    "html_path": target_identifier if target_type == "local_html" else None,
                    "source": meta.get("source") or ("local_html" if target_type == "local_html" else "manual"),
                    "title": meta.get("title"),
                    "snippet": meta.get("snippet"),
                    "label": label,
                    "success": False,
                    "error": msg,
                }
            )
            continue

        analysis_result_path: Optional[Path] = None

        if not args.skip_gemini:
            try:
                analysis_result_path = run_gemini_analysis(
                    analysis_prompt_path=analysis_prompt_path,
                    model_name=args.gemini_model,
                )
            except Exception as error:
                print(f"⚠️ Gemini による分析に失敗しました ({target_identifier}): {error}", file=sys.stderr)
            else:
                print("✅ Gemini によるマーケティング分析が完了しました。")

        print("✅ 文字起こしとプロンプト生成が完了しました。")
        print(f"  - 文字起こし Markdown: {transcript_path}")
        print(f"  - 分析プロンプト: {analysis_prompt_path}")
        if analysis_result_path and analysis_result_path.exists():
            print(f"  - Gemini 分析結果: {analysis_result_path}")
        else:
            print("  - Gemini 分析結果: 生成されていません。")

        print("次の手順:")
        if analysis_result_path and analysis_result_path.exists():
            print("  1. `analysis_result_gemini.md` を確認し、必要に応じて共有または検証してください。")
            print("  2. さらに Claude での再分析が必要な場合は、analysis_request.md を利用できます。")
        else:
            print("  1. Claude Code から上記プロンプトファイルを開き、その内容を会話に貼り付けるか、")
            print("     MCP のファイル読み込み機能で内容を共有してください。")
            print("  2. 必要であれば同フォルダ内のテキスト版も参照できます。")

        overall_results.append(
            {
                "url": target_url,
                "html_path": target_identifier if target_type == "local_html" else None,
                "source": meta.get("source") or ("local_html" if target_type == "local_html" else "manual"),
                "title": meta.get("title"),
                "snippet": meta.get("snippet"),
                "label": label,
                "success": True,
                "transcript": str(transcript_path),
                "analysis_prompt": str(analysis_prompt_path),
                "analysis_result": str(analysis_result_path) if analysis_result_path else None,
            }
        )

    print("=" * 80)
    print("処理サマリ:")
    for result in overall_results:
        source_label = result.get("label") or (
            "SEO抽出"
            if result.get("source") == "seo"
            else ("ローカルLP" if result.get("source") == "local_html" else "指定URL")
        )
        if result.get("success"):
            print(f"✅ {result['url']} ({source_label})")
            if result.get("title"):
                print(f"   - title: {result['title']}")
            if result.get("html_path"):
                print(f"   - html_path: {result['html_path']}")
            print(f"   - transcript: {result['transcript']}")
            print(f"   - analysis_prompt: {result['analysis_prompt']}")
            if result.get("analysis_result"):
                print(f"   - analysis_result: {result['analysis_result']}")
            else:
                print("   - analysis_result: なし")
        else:
            print(f"❌ {result['url']} ({source_label})")
            if result.get("title"):
                print(f"   - title: {result['title']}")
            if result.get("html_path"):
                print(f"   - html_path: {result['html_path']}")
            print(f"   - error: {result['error']}")

    if not any(r.get("success") for r in overall_results):
        sys.exit(1)

    analysis_ready = [
        r for r in overall_results if r.get("success") and r.get("analysis_result")
    ]

    if args.url_list and not args.skip_summary and analysis_ready:
        try:
            first_result_path = Path(analysis_ready[0]["analysis_result"])
            runs_dir = first_result_path.parent.parent
            latest_count = len(analysis_ready)
            entries = summarize_analyses.collect_analysis_entries(runs_dir, latest_count)
            prompt_text = summarize_analyses.build_prompt(args.summary_prompt_file, entries)
            summary_text = summarize_analyses.run_gemini(prompt_text, args.gemini_model)
        except Exception as error:
            print(f"⚠️ 統合レポート生成に失敗しました: {error}", file=sys.stderr)
        else:
            if args.summary_output:
                summary_path = args.summary_output
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                summary_path = runs_dir / f"consolidated_analysis_{timestamp}.md"
            summary_path.parent.mkdir(parents=True, exist_ok=True)
            summary_path.write_text(summary_text, encoding="utf-8")
            print("✅ 統合レポートを生成しました。")
            print(f"   - 保存先: {summary_path}")


if __name__ == "__main__":
    main()
