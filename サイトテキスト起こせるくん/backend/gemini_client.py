"""Gemini APIとの連携を担当するモジュール。"""

from __future__ import annotations

import os
import time
from typing import Iterable

import google.generativeai as genai

from .config import AppConfig
from .utils import encode_image


PROMPT_TEMPLATE = (
    "以下のスクリーンショット画像({index}/{total})に写っているWebページの本文テキストを、"
    "レイアウト構造を保ちながらMarkdownで書き出してください。"
    "箇条書きや表はMarkdown記法を用い、余計な要約や変換は行わずに原文を忠実に写してください。"
)


class GeminiClient:
    def __init__(self, config: AppConfig) -> None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise EnvironmentError("GOOGLE_API_KEY が環境変数に設定されていません。")
        genai.configure(api_key=api_key)
        self._config = config
        self._model = genai.GenerativeModel(model_name=config.model_name)

    def transcribe(self, image_paths: Iterable[str | os.PathLike[str]]) -> list[str]:
        images = list(image_paths)
        if not images:
            return []

        results: list[str] = []
        total = len(images)
        for index, path in enumerate(images, start=1):
            prompt = PROMPT_TEMPLATE.format(index=index, total=total)
            results.append(self._transcribe_single(path, prompt))
        return results

    def _transcribe_single(self, image_path, prompt: str) -> str:
        attempt = 0
        backoff = 1.0
        while True:
            try:
                parts = [{"text": prompt}, {"inline_data": encode_image(image_path)}]
                response = self._model.generate_content(
                    parts,
                    request_options={"timeout": self._config.request_timeout},
                )
                text = getattr(response, "text", None)
                if text:
                    return text.strip()
                # fallback
                if response.candidates:
                    candidate = response.candidates[0]
                    if candidate.content.parts:
                        collected = "\n".join(part.text for part in candidate.content.parts if hasattr(part, "text"))
                        if collected:
                            return collected.strip()
                return ""
            except Exception as exc:  # noqa: BLE001
                attempt += 1
                if attempt > self._config.max_retries:
                    raise exc
                time.sleep(backoff)
                backoff *= self._config.retry_backoff_base

