from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SerpApiConfig:
    api_key: Optional[str] = None
    engine: str = "google"
    locale: str = "jp"
    gl: str = "jp"
    hl: str = "ja"
    num_organic_results: int = 3
    timeout: int = 30


@dataclass(frozen=True)
class ScraperConfig:
    request_timeout: int = 20
    max_content_length: int = 8000
    max_headings: int = 5


@dataclass(frozen=True)
class AnalysisConfig:
    top_appeal_axes: int = 3


@dataclass(frozen=True)
class GeneratorConfig:
    num_variations: int = 3


@dataclass(frozen=True)
class AppConfig:
    serp: SerpApiConfig = SerpApiConfig()
    scraper: ScraperConfig = ScraperConfig()
    analysis: AnalysisConfig = AnalysisConfig()
    generator: GeneratorConfig = GeneratorConfig()
