import logging
import os
from typing import Any, Dict, List, Optional

import requests

from .config import SerpApiConfig
from .models import OrganicResult, SerpAd

LOGGER = logging.getLogger(__name__)


class SerpApiError(Exception):
    pass


class SerpApiClient:
    def __init__(self, config: SerpApiConfig) -> None:
        api_key = config.api_key or os.getenv("SERPAPI_KEY")
        if not api_key:
            raise SerpApiError(
                "SERPAPI_KEY が設定されていません。環境変数 SERPAPI_KEY を設定してください。"
            )
        self._config = config
        self._api_key = api_key

    def search(self, keyword: str) -> Dict[str, Any]:
        params = {
            "api_key": self._api_key,
            "engine": self._config.engine,
            "q": keyword,
            "hl": self._config.hl,
            "gl": self._config.gl,
            "num": max(self._config.num_organic_results, 3),
        }
        LOGGER.debug("SerpAPI へリクエスト: %s", params)
        response = requests.get(
            "https://serpapi.com/search.json", params=params, timeout=self._config.timeout
        )
        if not response.ok:
            raise SerpApiError(f"SerpAPI リクエストに失敗しました: {response.status_code} {response.text}")
        payload: Dict[str, Any] = response.json()
        if "error" in payload:
            raise SerpApiError(f"SerpAPI エラー: {payload['error']}")
        return payload


def parse_ads(raw_serp: Dict[str, Any]) -> List[SerpAd]:
    ads: List[SerpAd] = []
    for ad in raw_serp.get("ads", []):
        position = ad.get("position", len(ads) + 1)
        title = ad.get("title") or ad.get("headline") or ""
        description = ad.get("description", "")
        link = ad.get("link") or ad.get("displayed_link") or ""
        ads.append(
            SerpAd(
                position=position,
                title=title.strip(),
                description=description.strip(),
                link=link,
                display_link=ad.get("displayed_link"),
            )
        )
    return ads


def parse_organic_results(raw_serp: Dict[str, Any], limit: Optional[int] = None) -> List[OrganicResult]:
    organic: List[OrganicResult] = []
    organic_entries = raw_serp.get("organic_results", [])
    if limit is not None:
        organic_entries = organic_entries[:limit]
    for entry in organic_entries:
        organic.append(
            OrganicResult(
                position=entry.get("position", len(organic) + 1),
                title=(entry.get("title") or "").strip(),
                snippet=(entry.get("snippet") or "").strip(),
                link=entry.get("link") or "",
            )
        )
    return organic
