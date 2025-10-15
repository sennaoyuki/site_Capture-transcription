import argparse
import json
import logging
from pathlib import Path

from .td_builder.config import AppConfig
from .td_builder.models import InputSpec
from .td_builder.pipeline import build_td_report, load_spec_from_json
from .td_builder.serp import SerpApiError


def main() -> None:
    parser = argparse.ArgumentParser(description="TD作成くん - TD自動生成パイプライン")
    parser.add_argument("--target", help="ターゲット情報（直接指定）")
    parser.add_argument("--keyword", help="検索キーワード（直接指定）")
    parser.add_argument("--site-info", help="配信サイト情報（任意）")
    parser.add_argument("--input", help="JSONファイルから入力を読み込む")
    parser.add_argument("--output", help="結果を書き出すファイルパス")
    parser.add_argument("--verbose", action="store_true", help="詳細ログを表示する")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    spec = _resolve_spec(args)
    config = AppConfig()

    try:
        report = build_td_report(spec, config)
    except SerpApiError as exc:
        logging.error(str(exc))
        raise SystemExit(1) from exc

    result = {
        "keyword": report.keyword,
        "target": report.target,
        "intent": {
            "primary": report.intent.primary_intent,
            "evidence": report.intent.supporting_evidence,
        },
        "ads": [
            {
                "position": ad.position,
                "title": ad.title,
                "description": ad.description,
                "link": ad.link,
                "summary": _serialize_summary(ad.site_summary),
            }
            for ad in report.ads
        ],
        "seo_insights": [
            {
                "position": insight.position,
                "title": insight.title,
                "summary": insight.summary,
                "key_topics": insight.key_topics,
            }
            for insight in report.seo_insights
        ],
        "appeal_axes": [
            {"name": axis.name, "score": axis.score, "evidence": axis.evidence}
            for axis in report.appeal_axes
        ],
        "proposals": [
            {
                "title": proposal.title,
                "description": proposal.description,
                "cta": proposal.cta,
                "rationale": proposal.rationale,
            }
            for proposal in report.proposals
        ],
    }

    if args.output:
        Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


def _resolve_spec(args: argparse.Namespace) -> InputSpec:
    if args.input:
        content = Path(args.input).read_text(encoding="utf-8")
        return load_spec_from_json(content)
    if not args.target or not args.keyword:
        raise SystemExit("ターゲットとキーワードは必須です (--target / --keyword)")
    return InputSpec(target=args.target, keyword=args.keyword, site_info=args.site_info)


def _serialize_summary(summary):
    if summary is None:
        return None
    return {
        "title": summary.title,
        "meta_description": summary.meta_description,
        "headings": summary.headings,
        "key_points": summary.key_points,
    }


if __name__ == "__main__":
    main()
