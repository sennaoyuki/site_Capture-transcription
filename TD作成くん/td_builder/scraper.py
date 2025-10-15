import logging
from typing import List

import bs4
import requests

from .config import ScraperConfig
from .models import PageSummary

LOGGER = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class PageScraper:
    def __init__(self, config: ScraperConfig) -> None:
        self._config = config

    def fetch(self, url: str) -> PageSummary | None:
        try:
            LOGGER.debug("ページ取得開始: %s", url)
            resp = requests.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=self._config.request_timeout,
            )
            if not resp.ok:
                LOGGER.warning("ページ取得失敗 (%s): %s", resp.status_code, url)
                return None
        except requests.RequestException as exc:
            LOGGER.warning("ページ取得エラー: %s (%s)", url, exc)
            return None

        soup = bs4.BeautifulSoup(resp.text, "html.parser")
        title = soup.title.string.strip() if soup.title and soup.title.string else None
        description = None
        desc_tag = soup.find("meta", attrs={"name": "description"})
        if desc_tag and desc_tag.get("content"):
            description = desc_tag["content"].strip()

        headings = _extract_headings(soup, self._config.max_headings)
        key_points = _extract_key_points(soup, self._config.max_content_length)

        return PageSummary(
            url=url,
            title=title,
            meta_description=description,
            headings=headings,
            key_points=key_points,
        )


def _extract_headings(soup: bs4.BeautifulSoup, limit: int) -> List[str]:
    headings: List[str] = []
    for level in range(1, 4):
        for tag in soup.find_all(f"h{level}"):
            text = tag.get_text(strip=True)
            if text:
                headings.append(text)
            if len(headings) >= limit:
                return headings
    return headings


def _extract_key_points(soup: bs4.BeautifulSoup, max_length: int) -> List[str]:
    paragraphs: List[str] = []
    total_length = 0
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if not text:
            continue
        total_length += len(text)
        paragraphs.append(text)
        if total_length >= max_length:
            break
    return paragraphs[:10]
