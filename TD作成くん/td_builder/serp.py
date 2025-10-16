import logging
import os
from typing import Any, Dict, List, Optional, Sequence

import requests

from .config import SerpConfig
from .models import OrganicResult, SerpAd

LOGGER = logging.getLogger(__name__)


class SerpProviderError(Exception):
    """SERP取得に関する共通例外。"""


class SerpClient:
    """利用設定に応じてSERPプロバイダを切り替えるクライアント。"""

    def __init__(self, config: SerpConfig) -> None:
        provider = (config.provider or "scrapingdog").lower()
        if provider == "scrapingdog":
            self._impl = ScrapingDogClient(config)
        elif provider == "serpapi":
            self._impl = SerpApiClient(config)
        else:
            raise SerpProviderError(f"未対応のSERPプロバイダです: {provider}")

    def search(self, keyword: str) -> Dict[str, Any]:
        return self._impl.search(keyword)


class ScrapingDogClient:
    """ScrapingDog Google Search API ラッパー。"""

    BASE_URL = "https://api.scrapingdog.com/google/"

    def __init__(self, config: SerpConfig) -> None:
        api_key = config.api_key or os.getenv("SCRAPINGDOG_API_KEY")
        if not api_key:
            raise SerpProviderError(
                "ScrapingDogのAPIキーが設定されていません。環境変数 SCRAPINGDOG_API_KEY を設定してください。"
            )
        self._config = config
        self._api_key = api_key

    def search(self, keyword: str) -> Dict[str, Any]:
        params = {
            "api_key": self._api_key,
            "query": keyword,
            "results": max(self._config.num_organic_results, 3),
            "country": self._config.gl,
            "domain": getattr(self._config, "domain", "google.com"),
            "advance_search": "true" if self._config.advance_search else "false",
            "language": self._config.hl,
        }
        if self._config.include_ads:
            params["ads"] = "true"
        LOGGER.debug("ScrapingDog へリクエスト: %s", params)
        response = requests.get(self.BASE_URL, params=params, timeout=self._config.timeout)
        if not response.ok:
            raise SerpProviderError(
                f"ScrapingDog リクエストに失敗しました: {response.status_code} {response.text}"
            )
        try:
            payload: Dict[str, Any] = response.json()
        except ValueError:
            snippet = response.text[:200] if response.text else "レスポンス本文なし"
            raise SerpProviderError(
                f"ScrapingDog のレスポンスをJSONとして解析できませんでした: {snippet}"
            ) from None
        if payload.get("error"):
            raise SerpProviderError(f"ScrapingDog エラー: {payload['error']}")
        return payload


class SerpApiClient:
    """SerpAPI ラッパー（互換性維持用）。"""

    def __init__(self, config: SerpConfig) -> None:
        api_key = config.api_key or os.getenv("SERPAPI_KEY")
        if not api_key:
            raise SerpProviderError(
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
            raise SerpProviderError(
                f"SerpAPI リクエストに失敗しました: {response.status_code} {response.text}"
            )
        payload: Dict[str, Any] = response.json()
        if "error" in payload:
            raise SerpProviderError(f"SerpAPI エラー: {payload['error']}")
        return payload


def parse_ads(raw_serp: Dict[str, Any]) -> List[SerpAd]:
    """SERPレスポンスから広告情報を整理する。"""
    ads: List[SerpAd] = []
    ad_entries: Sequence[Dict[str, Any]] = (
        raw_serp.get("ads")
        or raw_serp.get("paid_results")
        or raw_serp.get("ad_results")
        or raw_serp.get("sponsored_results")
        or []
    )
    for ad in ad_entries:
        position = ad.get("position", len(ads) + 1)
        title = ad.get("title") or ad.get("headline") or ad.get("heading") or ""
        description = ad.get("description") or ad.get("snippet") or ""
        link = ad.get("link") or ad.get("url") or ad.get("displayed_link") or ""
        ads.append(
            SerpAd(
                position=position,
                title=title.strip(),
                description=description.strip(),
                link=link,
                display_link=ad.get("displayed_link") or ad.get("domain"),
            )
        )
    return ads


def parse_organic_results(raw_serp: Dict[str, Any], limit: Optional[int] = None) -> List[OrganicResult]:
    """SERPレスポンスからオーガニック検索結果を整理する。"""
    organic: List[OrganicResult] = []
    organic_entries = (
        raw_serp.get("organic_results")
        or raw_serp.get("results")
        or raw_serp.get("organic")
        or []
    )
    if limit is not None:
        organic_entries = organic_entries[:limit]
    for entry in organic_entries:
        organic.append(
            OrganicResult(
                position=entry.get("position", len(organic) + 1),
                title=(entry.get("title") or "").strip(),
                snippet=(entry.get("snippet") or entry.get("description") or "").strip(),
                link=entry.get("link") or entry.get("url") or "",
            )
        )
    return organic
