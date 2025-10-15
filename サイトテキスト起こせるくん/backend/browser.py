"""Playwrightを用いたスクリーンショット取得モジュール。"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from playwright.async_api import Browser, Page, async_playwright

from .config import AppConfig
from .utils import ensure_dir


@dataclass
class ScreenshotResult:
    url: str
    image_paths: list[Path]


class BrowserService:
    """Playwrightブラウザを管理し、スクリーンショットを生成する。"""

    def __init__(self, config: AppConfig) -> None:
        self._config = config

    async def _new_page(self, browser: Browser) -> Page:
        context = await browser.new_context(device_scale_factor=1)
        page = await context.new_page()
        await page.set_viewport_size({"width": 1280, "height": 720})
        return page

    async def capture(self, jobs: Iterable[tuple[str, Path]]) -> list[ScreenshotResult]:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            results: list[ScreenshotResult] = []
            try:
                for url, output_dir in jobs:
                    page = await self._new_page(browser)
                    try:
                        screenshot_paths = await self.capture_url(page, url, output_dir)
                        results.append(ScreenshotResult(url=url, image_paths=screenshot_paths))
                    finally:
                        await page.context.close()
            finally:
                await browser.close()
        return results

    async def capture_url(self, page: Page, url: str, output_root: Path) -> list[Path]:
        await page.goto(url, wait_until="networkidle", timeout=self._config.request_timeout * 1000)
        await asyncio.sleep(1.0)
        total_height = await page.evaluate("document.body.scrollHeight")
        viewport = await page.evaluate("({ width: window.innerWidth, height: window.innerHeight })")
        width = int(viewport.get("width", 1280))
        slice_height = self._config.slice_height
        output_root = ensure_dir(output_root)

        image_paths: list[Path] = []
        y = 0
        index = 1
        while y < total_height:
            clip_height = min(slice_height, total_height - y)
            clip_height = max(int(clip_height), 1)
            path = output_root / f"slice_{index:03d}.png"
            await page.screenshot(
                path=str(path),
                full_page=False,
                clip={"x": 0, "y": int(y), "width": width, "height": clip_height},
            )
            image_paths.append(path)
            y += clip_height
            index += 1
        return image_paths
