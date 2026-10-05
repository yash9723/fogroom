"""AIAnalysisService - optional narrative layer on top of the AAR.

The platform never depends on AI. Without ANTHROPIC_API_KEY a deterministic template
narrative is produced. AI output is stored only as `aar_reports.ai_narrative` and never
modifies recorded simulation history.
"""

import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger("fogroom.ai")


def template_narrative(report: dict[str, Any]) -> str:
    ex = report["exercise"]
    team = report["team"]
    parts = [
        f"During {ex['title']} ({ex['duration_label']}), the cell made {len(report['decisions'])} decisions "
        f"under degraded communications. {team['delivery_status_counts'].get('DROPPED', 0)} report deliveries "
        f"were dropped and {team['delivery_status_counts'].get('ALTERED', 0)} arrived in a conflicting form."
    ]
    ranked = sorted(report["participants"], key=lambda p: p["overall_score"], reverse=True)
    if ranked:
        best = ranked[0]
        parts.append(
            f"{best['callsign']} achieved the highest overall training score ({best['overall_score']:.0f}), "
            f"with decision quality {best['decision_quality']:.0f} and calibration {best['uncertainty_management']:.0f}."
        )
    contested = [d for d in report["decisions"] if d["known_contradictions"]]
    if contested:
        d = contested[0]
        parts.append(
            f"At {d['submitted_label']} {d['callsign']} decided '{d['decision_point_title']}' while holding "
            f"contradictory reports, choosing '{d['selected_label'] or d['decision_text']}' at {d['confidence']}% "
            f"confidence."
        )
    parts.append(
        f"Team agreement on shared decisions was {team['decision_agreement']:.0f}% and the average "
        f"uncertainty index at decision time was {team['average_uncertainty_at_decision']:.0f}."
    )
    if report["recommendations"]:
        parts.append("Key recommendation: " + report["recommendations"][0])
    return " ".join(parts)


class AIAnalysisService:
    """Narrative summaries; falls back to deterministic templates."""

    def __init__(self) -> None:
        self.enabled = bool(settings.anthropic_api_key)

    async def narrative(self, report: dict[str, Any]) -> tuple[str, str]:
        """Return (text, source) where source is 'AI' or 'TEMPLATE'."""
        if not self.enabled:
            return template_narrative(report), "TEMPLATE"
        try:
            text = await self._claude_narrative(report)
            if text:
                return text, "AI"
        except Exception:
            logger.exception("AI narrative failed; using template")
        return template_narrative(report), "TEMPLATE"

    async def _claude_narrative(self, report: dict[str, Any]) -> str | None:
        try:
            from anthropic import AsyncAnthropic
        except ImportError:
            logger.warning("anthropic package not installed; pip install -e '.[ai]'")
            return None
        compact = {
            "exercise": report["exercise"],
            "team": report["team"],
            "participants": report["participants"],
            "decisions": [
                {
                    k: d[k]
                    for k in (
                        "callsign",
                        "decision_point_title",
                        "selected_label",
                        "confidence",
                        "uncertainty_index",
                        "known_contradictions",
                        "decision_quality",
                        "rationale",
                    )
                }
                for d in report["decisions"]
            ],
            "recommendations": report["recommendations"],
        }
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        response = await client.messages.create(
            model=settings.anthropic_model,
            max_tokens=700,
            system=(
                "You write concise After Action Review narratives for a fictional disaster-response "
                "training exercise. Use only the data provided. Do not invent events. Describe metrics "
                "as experimental training metrics. Four short paragraphs maximum."
            ),
            messages=[{"role": "user", "content": f"AAR data (JSON):\n{compact}"}],
        )
        texts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return "\n\n".join(texts).strip() or None
