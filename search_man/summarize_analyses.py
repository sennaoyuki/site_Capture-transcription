import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

import google.generativeai as genai


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="複数サイトの Gemini 分析結果をまとめて統合レポートを生成します。"
    )
    parser.add_argument(
        "--runs-dir",
        type=Path,
        default=Path("output"),
        help="analysis_result_gemini.md が格納された run_* ディレクトリを含む親ディレクトリ",
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=Path("prompts/consolidated_analysis_prompt.md"),
        help="統合レポート生成用のプロンプトテンプレート",
    )
    parser.add_argument(
        "--gemini-model",
        default="models/gemini-2.5-flash",
        help="統合レポート生成に使用する Gemini モデル ID",
    )
    parser.add_argument(
        "--latest",
        type=int,
        default=None,
        help="最新の run_* ディレクトリから指定数のみを対象にする（未指定ならすべて）",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="生成される統合レポートの保存先（未指定の場合は runs_dir 配下に timestamp 付きファイルを作成）",
    )
    return parser.parse_args()


def extract_url_from_analysis_request(request_path: Path) -> str:
    if not request_path.exists():
        return "N/A"

    for line in request_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("**URL:**"):
            return line.split("**URL:**", 1)[-1].strip()
    return "N/A"


def collect_analysis_entries(runs_dir: Path, latest: int | None) -> List[dict]:
    run_dirs = sorted(
        [p for p in runs_dir.iterdir() if p.is_dir() and p.name.startswith("run_")],
        key=lambda p: p.name,
    )

    if latest is not None:
        run_dirs = run_dirs[-latest:]

    entries = []
    for run_dir in run_dirs:
        analysis_path = run_dir / "analysis_result_gemini.md"
        if not analysis_path.exists():
            continue

        request_path = run_dir / "analysis_request.md"
        url = extract_url_from_analysis_request(request_path)
        analysis_text = analysis_path.read_text(encoding="utf-8").strip()

        entries.append(
            {
                "run_dir": run_dir,
                "url": url,
                "analysis_path": analysis_path,
                "analysis_text": analysis_text,
            }
        )

    return entries


def build_prompt(template_path: Path, entries: List[dict]) -> str:
    if not template_path.exists():
        raise FileNotFoundError(f"prompt template not found: {template_path}")

    template = template_path.read_text(encoding="utf-8")

    analyses_block_parts = []
    for idx, entry in enumerate(entries, start=1):
        block = [
            f"### サイト {idx}",
            f"- URL: {entry['url']}",
            f"- 分析ファイル: {entry['analysis_path']}",
            "",
            entry["analysis_text"],
        ]
        analyses_block_parts.append("\n".join(block))

    analyses_block = "\n\n".join(analyses_block_parts)
    return template.replace("{{ANALYSES}}", analyses_block)


def run_gemini(prompt: str, model_name: str) -> str:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("環境変数 GOOGLE_API_KEY が設定されていません。")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    response = model.generate_content(
        prompt,
        generation_config={"temperature": 0.2},
    )

    text = ""
    if hasattr(response, "text") and response.text:
        text = response.text.strip()
    else:
        candidates = getattr(response, "candidates", None)
        if candidates:
            for candidate in candidates:
                parts = getattr(candidate, "content", None)
                if parts:
                    for part in getattr(parts, "parts", []):
                        part_text = getattr(part, "text", "")
                        if part_text:
                            text += part_text
            text = text.strip()

    if not text:
        raise RuntimeError("Gemini から有効なテキスト応答が得られませんでした。")

    return text


def main() -> None:
    args = parse_args()

    entries = collect_analysis_entries(args.runs_dir, args.latest)
    if not entries:
        print("❌ 統合対象となる analysis_result_gemini.md が見つかりませんでした。", file=sys.stderr)
        sys.exit(1)

    print(f"対象サイト数: {len(entries)} 件")
    for entry in entries:
        print(f"- {entry['url']} ({entry['analysis_path']})")

    prompt = build_prompt(args.prompt_file, entries)

    try:
        summary_text = run_gemini(prompt, args.gemini_model)
    except Exception as error:
        print(f"❌ Gemini による統合レポート生成でエラーが発生しました: {error}", file=sys.stderr)
        sys.exit(1)

    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = args.runs_dir / f"consolidated_analysis_{timestamp}.md"

    output_path.write_text(summary_text, encoding="utf-8")

    print("✅ 統合レポートを生成しました。")
    print(f"  - 保存先: {output_path}")


if __name__ == "__main__":
    main()
