import logging
from typing import List, Sequence

from .config import GeneratorConfig
from .models import AppealAxis, IntentSummary, TDProposal

LOGGER = logging.getLogger(__name__)

MAX_TITLE_LENGTH = 30
MAX_DESCRIPTION_LENGTH = 90


class TDGenerator:
    def __init__(self, config: GeneratorConfig) -> None:
        self._config = config

    def generate(
        self,
        keyword: str,
        target: str,
        intent: IntentSummary,
        appeals: Sequence[AppealAxis],
        site_info: str | None,
    ) -> List[TDProposal]:
        axes = [axis.name for axis in appeals] or ["信頼", "スピード", "価格"]
        proposals: List[TDProposal] = []
        for idx in range(self._config.num_variations):
            axis = axes[idx % len(axes)]
            title = _truncate(f"{keyword}で{axis}重視なら", MAX_TITLE_LENGTH)
            benefit = self._compose_benefit(axis, intent.primary_intent, site_info)
            description = _truncate(f"{target}向けに{benefit}", MAX_DESCRIPTION_LENGTH)
            cta = self._compose_cta(intent.primary_intent)
            rationale = [
                f"検索意図: {intent.primary_intent}",
                f"訴求軸: {axis}",
            ]
            if site_info:
                rationale.append(f"サイト補足: {site_info[:40]}")
            proposals.append(TDProposal(title=title, description=description, cta=cta, rationale=rationale))
        return proposals

    def _compose_benefit(self, axis: str, intent: str, site_info: str | None) -> str:
        base = {
            "価格": "コストを抑えたプランを提示",
            "信頼": "実績豊富なサービス紹介",
            "スピード": "最短対応と迅速サポート",
            "品質": "専門チームが高品質対応",
            "サポート": "導入後の手厚いサポート",
        }.get(axis, "課題を解決するソリューション")
        if intent == "申込・購入":
            base += "ですぐ申し込み"
        elif intent == "比較":
            base += "を他社と比較提示"
        else:
            base += "の情報を詳しく解説"
        if site_info:
            base += f"（{site_info[:15]}）"
        return base

    def _compose_cta(self, intent: str) -> str:
        if intent == "申込・購入":
            return "今すぐ詳細をチェック"
        if intent == "比較":
            return "資料で他社との違いを見る"
        return "まずは無料で情報収集"


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"
