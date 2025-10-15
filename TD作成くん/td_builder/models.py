from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class InputSpec:
    target: str
    keyword: str
    site_info: Optional[str] = None


@dataclass
class SerpAd:
    position: int
    title: str
    description: str
    link: str
    display_link: Optional[str] = None
    site_summary: Optional["PageSummary"] = None


@dataclass
class OrganicResult:
    position: int
    title: str
    snippet: str
    link: str
    site_summary: Optional["PageSummary"] = None


@dataclass
class PageSummary:
    url: str
    title: Optional[str]
    meta_description: Optional[str]
    headings: List[str]
    key_points: List[str]


@dataclass
class IntentSummary:
    primary_intent: str
    supporting_evidence: List[str]


@dataclass
class AppealAxis:
    name: str
    score: float
    evidence: List[str] = field(default_factory=list)


@dataclass
class SeoInsight:
    position: int
    title: str
    summary: str
    key_topics: List[str]


@dataclass
class TDProposal:
    title: str
    description: str
    cta: str
    rationale: List[str]


@dataclass
class Report:
    keyword: str
    target: str
    intent: IntentSummary
    ads: List[SerpAd]
    seo_insights: List[SeoInsight]
    appeal_axes: List[AppealAxis]
    proposals: List[TDProposal]
