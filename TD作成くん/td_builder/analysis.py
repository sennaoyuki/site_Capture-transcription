import collections
import logging
import math
import re
from typing import Iterable, List, Sequence

from .config import AnalysisConfig
from .models import AppealAxis, IntentSummary, OrganicResult, PageSummary, SeoInsight, SerpAd

LOGGER = logging.getLogger(__name__)

INTENT_RULES = {
    "比較": [r"比較", r"おすすめ", r"ランキング", r"口コミ"],
    "情報収集": [r"とは", r"仕組み", r"メリット", r"デメリット", r"違い"],
    "申込・購入": [r"申込", r"購入", r"料金", r"費用", r"価格"],
}

APPEAL_KEYWORDS = {
    "価格": ["価格", "料金", "費用", "割引", "無料"],
    "信頼": ["実績", "口コミ", "評判", "導入企業", "満足度"],
    "スピード": ["即日", "最短", "スピード", "迅速"],
    "品質": ["専門", "プロ", "品質", "保証"],
    "サポート": ["サポート", "相談", "カスタマー", "サポート体制"],
}


class Analyzer:
    def __init__(self, config: AnalysisConfig) -> None:
        self._config = config

    def analyze_intent(self, keyword: str, ads: Sequence[SerpAd], organic: Sequence[OrganicResult]) -> IntentSummary:
        evidence: List[str] = []
        scores = collections.Counter({k: 0 for k in INTENT_RULES})
        texts = [keyword] + [ad.title + " " + ad.description for ad in ads] + [
            org.title + " " + org.snippet for org in organic
        ]
        for intent, patterns in INTENT_RULES.items():
            for text in texts:
                for pattern in patterns:
                    if re.search(pattern, text):
                        scores[intent] += 1
                        evidence.append(f"{intent}: {pattern} -> '{text[:40]}'")
        primary_intent = scores.most_common(1)[0][0] if scores else "情報収集"
        return IntentSummary(primary_intent=primary_intent, supporting_evidence=evidence[:10])

    def analyze_appeal_axes(self, ads: Sequence[SerpAd], pages: Iterable[PageSummary]) -> List[AppealAxis]:
        counter = collections.Counter()
        evidence_map: dict[str, List[str]] = {axis: [] for axis in APPEAL_KEYWORDS}
        for axis, keywords in APPEAL_KEYWORDS.items():
            for text in _collect_texts(ads, pages):
                for kw in keywords:
                    if kw in text:
                        counter[axis] += 1
                        if len(evidence_map[axis]) < 5:
                            evidence_map[axis].append(f"{kw}: {text[:40]}")
        axes: List[AppealAxis] = []
        for axis, freq in counter.most_common(self._config.top_appeal_axes):
            score = 1.0 - math.exp(-freq)
            axes.append(AppealAxis(name=axis, score=score, evidence=evidence_map.get(axis, [])))
        return axes

    def summarize_seo(self, organic: Sequence[OrganicResult]) -> List[SeoInsight]:
        insights: List[SeoInsight] = []
        for entry in organic:
            topics = _extract_topics(entry.snippet)
            summary = entry.snippet or "要約情報なし"
            insights.append(
                SeoInsight(
                    position=entry.position,
                    title=entry.title,
                    summary=summary,
                    key_topics=topics,
                )
            )
        return insights


def _collect_texts(ads: Sequence[SerpAd], pages: Iterable[PageSummary]) -> Iterable[str]:
    for ad in ads:
        yield ad.title
        yield ad.description
        if ad.site_summary:
            yield " ".join(ad.site_summary.key_points)
    for page in pages:
        if page:
            yield " ".join(page.headings)
            yield " ".join(page.key_points)


def _extract_topics(text: str) -> List[str]:
    tokens = re.findall(r"[ぁ-んァ-ン一-龥A-Za-z0-9]+", text)
    freq = collections.Counter(tokens)
    return [token for token, _ in freq.most_common(5)]
