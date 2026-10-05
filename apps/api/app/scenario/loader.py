"""Mapping between ScenarioTemplate ORM graphs and the ScenarioCreate/Out schemas."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.errors import not_found
from app.models.scenario import (
    ScenarioChannel,
    ScenarioDecisionPoint,
    ScenarioEventTemplate,
    ScenarioPhase,
    ScenarioRole,
    ScenarioTemplate,
)
from app.schemas.scenario import ScenarioCreate, ScenarioOut, ScenarioSummary

_LOAD = (
    selectinload(ScenarioTemplate.roles),
    selectinload(ScenarioTemplate.channels),
    selectinload(ScenarioTemplate.phases),
    selectinload(ScenarioTemplate.events),
    selectinload(ScenarioTemplate.decision_points),
)


async def get_scenario(session: AsyncSession, scenario_id: uuid.UUID) -> ScenarioTemplate:
    scenario = await session.scalar(
        select(ScenarioTemplate).where(ScenarioTemplate.id == scenario_id).options(*_LOAD)
    )
    if scenario is None:
        raise not_found("SCENARIO_NOT_FOUND", "Scenario not found.")
    return scenario


async def list_scenarios(session: AsyncSession) -> list[ScenarioTemplate]:
    result = await session.scalars(
        select(ScenarioTemplate).options(*_LOAD).order_by(ScenarioTemplate.created_at)
    )
    return list(result.all())


def apply_scenario(model: ScenarioTemplate, data: ScenarioCreate) -> ScenarioTemplate:
    """Replace the template's fields and child collections with `data`."""
    model.name = data.name
    model.description = data.description
    model.difficulty = data.difficulty.value
    model.estimated_duration_minutes = data.estimated_duration_minutes
    model.category = data.category
    model.briefing = data.briefing
    model.objectives = [o.model_dump(mode="json") for o in data.objectives]
    model.initial_conditions = data.initial_conditions.model_dump(mode="json")
    model.degradation_rules = data.degradation_rules.model_dump(mode="json", exclude_none=True)

    model.roles = [
        ScenarioRole(sort_order=i, **r.model_dump(mode="json")) for i, r in enumerate(data.roles)
    ]
    model.channels = [
        ScenarioChannel(sort_order=i, **c.model_dump(mode="json"))
        for i, c in enumerate(data.channels)
    ]
    model.phases = [ScenarioPhase(**p.model_dump(mode="json")) for p in data.phases]
    events = []
    for e in data.events:
        payload = e.model_dump(mode="json")
        payload["meta"] = payload.pop("metadata")
        payload["effects"] = payload["effects"] or {}
        events.append(ScenarioEventTemplate(**payload))
    model.events = events
    model.decision_points = [
        ScenarioDecisionPoint(**d.model_dump(mode="json")) for d in data.decision_points
    ]
    return model


async def replace_scenario(
    session: AsyncSession, model: ScenarioTemplate, data: ScenarioCreate
) -> ScenarioTemplate:
    """Update an existing template. Child rows are deleted (and flushed) first, because the
    unit of work would otherwise insert replacements before deleting orphans and violate the
    (scenario_id, key) unique constraints."""
    model.roles.clear()
    model.channels.clear()
    model.phases.clear()
    model.events.clear()
    model.decision_points.clear()
    await session.flush()
    return apply_scenario(model, data)


def scenario_to_out(model: ScenarioTemplate) -> ScenarioOut:
    def event_dict(e: ScenarioEventTemplate) -> dict[str, Any]:
        return {
            "key": e.key,
            "event_type": e.event_type,
            "title": e.title,
            "content": e.content,
            "trigger_type": e.trigger_type,
            "scheduled_offset_seconds": e.scheduled_offset_seconds,
            "trigger_decision_key": e.trigger_decision_key,
            "phase_key": e.phase_key,
            "channel_key": e.channel_key,
            "priority": e.priority,
            "source": e.source,
            "source_reliability": e.source_reliability,
            "reliability": e.reliability,
            "importance_weight": e.importance_weight,
            "fact_key": e.fact_key,
            "fact_value": e.fact_value,
            "location_key": e.location_key,
            "targeting_rules": e.targeting_rules or {},
            "variants": e.variants or [],
            "effects": e.effects or None,
            "metadata": e.meta or {},
        }

    return ScenarioOut.model_validate(
        {
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "difficulty": model.difficulty,
            "estimated_duration_minutes": model.estimated_duration_minutes,
            "category": model.category,
            "briefing": model.briefing,
            "objectives": model.objectives or [],
            "initial_conditions": model.initial_conditions or {},
            "degradation_rules": model.degradation_rules or {},
            "is_published": model.is_published,
            "created_by": model.created_by,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
            "roles": [
                {
                    "key": r.key,
                    "name": r.name,
                    "callsign": r.callsign,
                    "team": r.team,
                    "description": r.description,
                    "objectives": r.objectives or [],
                }
                for r in model.roles
            ],
            "channels": [
                {
                    "key": c.key,
                    "name": c.name,
                    "channel_type": c.channel_type,
                    "initial_status": c.initial_status,
                    "reliability": c.reliability,
                    "latency_ms": c.latency_ms,
                    "weight": c.weight,
                    "fallback_channel_key": c.fallback_channel_key,
                }
                for c in model.channels
            ],
            "phases": [
                {
                    "key": p.key,
                    "name": p.name,
                    "description": p.description,
                    "starts_at_seconds": p.starts_at_seconds,
                }
                for p in model.phases
            ],
            "events": [event_dict(e) for e in model.events],
            "decision_points": [
                {
                    "key": d.key,
                    "title": d.title,
                    "prompt": d.prompt,
                    "options": d.options or [],
                    "trigger_type": d.trigger_type,
                    "opens_at_seconds": d.opens_at_seconds,
                    "trigger_decision_key": d.trigger_decision_key,
                    "deadline_seconds": d.deadline_seconds,
                    "allow_custom": d.allow_custom,
                    "require_rationale": d.require_rationale,
                    "target_roles": d.target_roles or [],
                    "phase_key": d.phase_key,
                    "critical": d.critical,
                    "relevant_fact_keys": d.relevant_fact_keys or [],
                }
                for d in model.decision_points
            ],
        }
    )


def scenario_summary(model: ScenarioTemplate) -> ScenarioSummary:
    return ScenarioSummary(
        id=model.id,
        name=model.name,
        description=model.description,
        difficulty=model.difficulty,
        estimated_duration_minutes=model.estimated_duration_minutes,
        category=model.category,
        role_count=len(model.roles),
        channel_count=len(model.channels),
        event_count=len(model.events),
        decision_count=len(model.decision_points),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def scenario_snapshot(model: ScenarioTemplate) -> dict[str, Any]:
    """Frozen JSON copy stored on a room so later template edits never alter history."""
    return scenario_to_out(model).model_dump(mode="json")
