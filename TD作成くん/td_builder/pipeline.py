import json
import logging
from typing import Any, Dict, Optional

from .analysis import Analyzer
from .config import AppConfig
from .generator import TDGenerator
from .models import InputSpec, OrganicResult, Report, SerpAd
from .scraper import PageScraper
from .serp import SerpClient, SerpProviderError, parse_ads, parse_organic_results

LOGGER = logging.getLogger(__name__)


def build_td_report(spec: InputSpec, config: Optional[AppConfig] = None) -> Report:
    config = config or AppConfig()
    serp_client = SerpClient(config.serp)
    scraper = PageScraper(config.scraper)
    analyzer = Analyzer(config.analysis)
    generator = TDGenerator(config.generator)

    raw_serp = serp_client.search(spec.keyword)
    ads = parse_ads(raw_serp)
    organic = parse_organic_results(raw_serp, limit=config.serp.num_organic_results)

    ads_with_summaries = _attach_summaries(ads, scraper)
    organic_with_summaries = _attach_organic_summaries(organic, scraper)

    intent = analyzer.analyze_intent(spec.keyword, ads_with_summaries, organic_with_summaries)
    pages = [
        summary
        for summary in (
            [ad.site_summary for ad in ads_with_summaries]
            + [entry.site_summary for entry in organic_with_summaries]
        )
        if summary is not None
    ]
    appeal_axes = analyzer.analyze_appeal_axes(ads_with_summaries, pages)
    seo_insights = analyzer.summarize_seo(organic_with_summaries)

    proposals = generator.generate(
        keyword=spec.keyword,
        target=spec.target,
        intent=intent,
        appeals=appeal_axes,
        site_info=spec.site_info,
    )

    return Report(
        keyword=spec.keyword,
        target=spec.target,
        intent=intent,
        ads=ads_with_summaries,
        seo_insights=seo_insights,
        appeal_axes=appeal_axes,
        proposals=proposals,
    )


def load_spec_from_json(raw: str | Dict[str, Any]) -> InputSpec:
    payload: Dict[str, Any]
    if isinstance(raw, str):
        payload = json.loads(raw)
    else:
        payload = raw
    return InputSpec(
        target=payload["target"],
        keyword=payload["keyword"],
        site_info=payload.get("site_info"),
    )


def _attach_summaries(ads: list[SerpAd], scraper: PageScraper) -> list[SerpAd]:
    for ad in ads:
        if ad.link:
            ad.site_summary = scraper.fetch(ad.link)
    return ads


def _attach_organic_summaries(
    organic: list[OrganicResult], scraper: PageScraper
) -> list[OrganicResult]:
    for entry in organic:
        if entry.link:
            entry.site_summary = scraper.fetch(entry.link)
    return organic
