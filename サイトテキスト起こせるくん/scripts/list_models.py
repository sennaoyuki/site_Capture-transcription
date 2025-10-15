"""利用可能なGeminiモデルを列挙するヘルパースクリプト。"""

from __future__ import annotations

import os

import google.generativeai as genai
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise SystemExit("GOOGLE_API_KEY が未設定です。 .env を確認してください。")

    genai.configure(api_key=api_key)

    print("--- 利用可能なモデル一覧 (generateContent対応) ---")
    for model in genai.list_models():
        methods = getattr(model, "supported_generation_methods", [])
        if "generateContent" not in methods:
            continue
        model_name = getattr(model, "name", "<unknown>")
        is_multimodal = "vision" in model_name.lower() or "pro" in model_name.lower()
        print(model_name)
        print(f"  methods: {methods}")
        if is_multimodal:
            print("  hint: 画像入力に対応している可能性があります")


if __name__ == "__main__":
    main()
