"""URL処理のメインフロー。"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Callable, Iterable
from urllib.parse import urlparse

from .browser import BrowserService
from .config import AppConfig
from .gemini_client import GeminiClient
from .logger import setup_logger
from .utils import TranscriptResult, ensure_dir, slugify

ProgressCallback = Callable[[str], None]


class TranscriptionProcessor:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.run_root = ensure_dir(config.output_root / config.timestamp_prefix)
        log_path = self.run_root / "run.log"
        self.logger = setup_logger(log_path)
        self.browser_service = BrowserService(config)
        self.gemini_client = GeminiClient(config)

    def process(self, urls: Iterable[str], on_progress: ProgressCallback | None = None) -> list[TranscriptResult]:
        url_list = [url for url in urls if url.strip()]
        if not url_list:
            return []

        jobs = []
        for index, url in enumerate(url_list, start=1):
            slug = self._build_slug(url, index)
            url_dir = ensure_dir(self.run_root / slug)
            images_dir = ensure_dir(url_dir / "images")
            text_dir = ensure_dir(url_dir / "texts")
            jobs.append((url, images_dir, text_dir))

        capture_results = asyncio.run(self._capture_all(jobs))

        transcript_results: list[TranscriptResult] = []
        for (url, images_dir, text_dir), capture_result in zip(jobs, capture_results, strict=False):
            if on_progress:
                on_progress(f"{url} のGemini処理を開始")
            segments = self.gemini_client.transcribe(capture_result.image_paths)
            combined_text = self._combine_segments(segments)
            text_path = text_dir / "transcript.md"
            json_path = text_dir / "transcript.json"
            text_dir.mkdir(parents=True, exist_ok=True)
            text_path.write_text(combined_text, encoding="utf-8")
            json_path.write_text(
                json.dumps(
                    {
                        "url": url,
                        "segments": segments,
                        "combined_text": combined_text,
                        "images": [str(path) for path in capture_result.image_paths],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            transcript_results.append(
                TranscriptResult(
                    url=url,
                    output_dir=text_dir.parent,
                    text_output=text_path,
                    image_files=capture_result.image_paths,
                    text_content=combined_text,
                )
            )
            if on_progress:
                on_progress(f"{url} の処理が完了しました")

        return transcript_results

    async def _capture_all(self, jobs: list[tuple[str, Path, Path]]):
        capture_jobs = []
        for url, images_dir, _ in jobs:
            self.logger.info("スクリーンショット取得: %s -> %s", url, images_dir)
            capture_jobs.append((url, images_dir))
        return await self.browser_service.capture(capture_jobs)

    def _combine_segments(self, segments: list[str]) -> str:
        cleaned = [segment.strip() for segment in segments if segment and segment.strip()]
        return "\n\n".join(cleaned)

    def _build_slug(self, url: str, index: int) -> str:
        parsed = urlparse(url)
        base = parsed.netloc + parsed.path
        return f"{index:02d}_{slugify(base)}"
