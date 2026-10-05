"""Decision submission: validation, persistence and the information snapshot.

Submitting a decision and freezing the participant's information state happen in one
transaction, so every recorded decision has an exact digital twin of what was known.
"""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, conflict, forbidden, not_found
from app.core.text import clean_text
from app.models.decision import Decision, InformationSnapshot
from app.models.enums import ActorType, DecisionPointStatus, EventVisibility, RoomStatus
from app.models.room import Participant, RoomDecisionPoint
from app.scenario.clock import Clock
from app.scenario.engine import ScenarioEngine
from app.services.audit import record_event
from app.services.information_state import InformationStateService


@dataclass
class DecisionInput:
    selected_option: str | None
    decision_text: str | None
    rationale: str | None
    confidence: int


async def submit_decision(
    session: AsyncSession,
    clock: Clock,
    room_id: uuid.UUID,
    participant: Participant,
    decision_point_key: str,
    data: DecisionInput,
) -> tuple[Decision, InformationSnapshot]:
    engine = ScenarioEngine(session, clock)
    room = await engine.lock_room(room_id)
    if room.status == RoomStatus.PAUSED:
        raise conflict("ROOM_PAUSED", "The simulation is paused; decisions resume with the clock.")
    if room.status != RoomStatus.RUNNING:
        raise conflict("ROOM_NOT_RUNNING", "Simulation is not running.")
    sim = engine.now_sim(room)

    dp = await session.scalar(
        select(RoomDecisionPoint)
        .where(RoomDecisionPoint.room_id == room.id, RoomDecisionPoint.key == decision_point_key)
        .with_for_update()
    )
    if dp is None:
        raise not_found("DECISION_POINT_NOT_FOUND", "This decision point is not open.")
    if str(participant.id) not in dp.target_participant_ids:
        raise forbidden("This decision is not assigned to you.", "DECISION_NOT_ASSIGNED")
    if dp.status != DecisionPointStatus.OPEN or (
        dp.deadline_sim_time is not None and sim > dp.deadline_sim_time
    ):
        raise conflict(
            "DECISION_CLOSED",
            "The decision window has closed - late submissions are not accepted.",
            {"deadline_sim_time": dp.deadline_sim_time, "sim_time": sim},
        )

    option_keys = {o["key"] for o in dp.options}
    selected = data.selected_option
    text = clean_text(data.decision_text, 2000)
    rationale = clean_text(data.rationale, 4000)
    if selected:
        if selected not in option_keys:
            raise AppError("INVALID_OPTION", "Unknown decision option.", 422)
        decision_type = "OPTION"
    else:
        if not dp.allow_custom:
            raise AppError("OPTION_REQUIRED", "Select one of the available options.", 422)
        if not text:
            raise AppError("DECISION_TEXT_REQUIRED", "Describe your custom decision.", 422)
        decision_type = "CUSTOM"
    if dp.require_rationale and not rationale:
        raise AppError("RATIONALE_REQUIRED", "A rationale is required for this decision.", 422)

    exists = await session.scalar(
        select(Decision.id).where(
            Decision.decision_point_id == dp.id, Decision.participant_id == participant.id
        )
    )
    if exists is not None:
        raise conflict("ALREADY_SUBMITTED", "You have already submitted this decision.")

    decision = Decision(
        room_id=room.id,
        participant_id=participant.id,
        decision_point_id=dp.id,
        decision_type=decision_type,
        selected_option=selected,
        decision_text=text,
        rationale=rationale,
        confidence=data.confidence,
        submitted_at=clock.now(),
        submitted_sim_time=sim,
        response_time_ms=int(max(0.0, sim - dp.opened_sim_time) * 1000),
    )
    session.add(decision)
    try:
        await session.flush()
    except IntegrityError as exc:
        raise conflict("ALREADY_SUBMITTED", "You have already submitted this decision.") from exc

    state = await InformationStateService(session).reconstruct(room, participant.id, sim)
    snapshot = build_snapshot(room.id, participant.id, decision.id, sim, state)
    session.add(snapshot)

    label = next((o["label"] for o in dp.options if o["key"] == selected), None)
    await record_event(
        session,
        room.id,
        "decision.submitted",
        {
            "decision_id": str(decision.id),
            "participant_id": str(participant.id),
            "callsign": participant.callsign,
            "decision_point_key": dp.key,
            "decision_point_title": dp.title,
            "decision_type": decision_type,
            "selected_option": selected,
            "selected_label": label,
            "decision_text": text,
            "rationale": rationale,
            "confidence": data.confidence,
            "response_time_ms": decision.response_time_ms,
            "uncertainty_index": state["metrics"]["uncertainty_index"],
            "information_completeness": state["metrics"]["information_completeness"],
        },
        actor_id=participant.user_id,
        actor_type=ActorType.USER,
        sim_time=sim,
    )
    await record_event(
        session,
        room.id,
        "decision.acknowledged",
        {"decision_point_key": dp.key, "decision_id": str(decision.id)},
        actor_type=ActorType.SYSTEM,
        sim_time=sim,
        visibility=EventVisibility.PARTICIPANTS,
        targets=[participant.id],
    )
    await engine.close_if_complete(room, dp, sim)
    return decision, snapshot


def build_snapshot(
    room_id: uuid.UUID,
    participant_id: uuid.UUID,
    decision_id: uuid.UUID | None,
    sim: float,
    state: dict[str, Any],
) -> InformationSnapshot:
    mt = state["metrics"]
    return InformationSnapshot(
        room_id=room_id,
        participant_id=participant_id,
        decision_id=decision_id,
        snapshot_time=sim,
        known_message_ids=[i["message_id"] for i in state["received"]],
        pending_message_ids=[i["message_id"] for i in state["pending"]],
        unavailable_channel_ids=list(state["unavailable_channel_ids"]),
        information_completeness=mt["information_completeness"],
        information_reliability=mt["information_reliability"],
        communication_health=mt["communication_health"],
        contradiction_count=mt["known_contradictions"],
        uncertainty_score=mt["uncertainty_index"],
        snapshot_payload=state,
    )
