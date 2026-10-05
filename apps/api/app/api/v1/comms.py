"""Trainee actions: decisions, message acknowledgement, team communication."""

import uuid
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import select

from app.auth.deps import RoomAccessDep, RoomParticipant, SessionDep
from app.core.errors import conflict, not_found
from app.models.decision import Decision
from app.models.enums import ActorType, DeliveryStatus, RoomStatus
from app.models.messaging import MessageDelivery
from app.models.room import RoomDecisionPoint
from app.scenario.clock import SystemClock, sim_now
from app.schemas.room import DecisionSubmitIn, TeamMessageIn
from app.services.audit import commit_and_publish, record_event
from app.services.decision import DecisionInput, submit_decision
from app.services.live_state import trainee_state
from app.services.team import send_team_message

router = APIRouter(tags=["trainee"])
clock = SystemClock()


@router.post(
    "/rooms/{room_id}/decisions/{decision_point}/submit",
    status_code=status.HTTP_201_CREATED,
    summary="Submit a decision (captures an information snapshot)",
)
async def submit(
    decision_point: str, body: DecisionSubmitIn, access: RoomParticipant, session: SessionDep
) -> dict[str, Any]:
    assert access.participant is not None
    decision, snapshot = await submit_decision(
        session,
        clock,
        access.room.id,
        access.participant,
        decision_point,
        DecisionInput(body.selected_option, body.decision_text, body.rationale, body.confidence),
    )
    await commit_and_publish(session)
    return {
        "id": str(decision.id),
        "decision_point_key": decision_point,
        "selected_option": decision.selected_option,
        "confidence": decision.confidence,
        "submitted_sim_time": decision.submitted_sim_time,
        "response_time_ms": decision.response_time_ms,
        "snapshot_id": str(snapshot.id),
    }


@router.get("/rooms/{room_id}/decisions", summary="Decisions (instructor: all, trainee: own)")
async def list_decisions(access: RoomAccessDep, session: SessionDep) -> list[dict[str, Any]]:
    query = (
        select(Decision, RoomDecisionPoint)
        .join(RoomDecisionPoint, RoomDecisionPoint.id == Decision.decision_point_id)
        .where(Decision.room_id == access.room.id)
    )
    if not access.is_instructor:
        assert access.participant is not None
        query = query.where(Decision.participant_id == access.participant.id)
    rows = (await session.execute(query.order_by(Decision.submitted_sim_time))).all()
    return [
        {
            "id": str(d.id),
            "participant_id": str(d.participant_id),
            "decision_point_key": dp.key,
            "decision_point_title": dp.title,
            "selected_option": d.selected_option,
            "selected_label": next(
                (o["label"] for o in dp.options if o["key"] == d.selected_option), None
            ),
            "decision_text": d.decision_text,
            "rationale": d.rationale,
            "confidence": d.confidence,
            "response_time_ms": d.response_time_ms,
            "submitted_sim_time": d.submitted_sim_time,
        }
        for d, dp in rows
    ]


@router.get("/rooms/{room_id}/messages", summary="Messages delivered to the calling trainee")
async def my_messages(access: RoomParticipant, session: SessionDep) -> list[dict[str, Any]]:
    assert access.participant is not None
    state = await trainee_state(session, access.room, access.participant, clock)
    messages: list[dict[str, Any]] = state["messages"]
    return messages


@router.post(
    "/rooms/{room_id}/messages/{delivery_id}/ack", summary="Acknowledge a received message"
)
async def acknowledge(
    delivery_id: uuid.UUID, access: RoomParticipant, session: SessionDep
) -> dict[str, Any]:
    assert access.participant is not None
    delivery = await session.get(MessageDelivery, delivery_id)
    # Only deliveries this participant actually received can be acknowledged.
    if (
        delivery is None
        or delivery.participant_id != access.participant.id
        or delivery.delivery_status not in (DeliveryStatus.DELIVERED, DeliveryStatus.ALTERED)
    ):
        raise not_found("MESSAGE_NOT_FOUND", "Message not found.")
    if access.room.status not in (RoomStatus.RUNNING, RoomStatus.PAUSED):
        raise conflict("ROOM_NOT_RUNNING", "The exercise is not running.")
    if delivery.acknowledged_sim_time is None:
        sim = sim_now(access.room, clock.now())
        delivery.acknowledged_sim_time = sim
        await record_event(
            session,
            access.room.id,
            "message.acknowledged",
            {
                "delivery_id": str(delivery.id),
                "message_id": str(delivery.message_id),
                "participant_id": str(access.participant.id),
                "callsign": access.participant.callsign,
            },
            actor_id=access.user.id,
            actor_type=ActorType.USER,
            sim_time=sim,
        )
        await commit_and_publish(session)
    return {"id": str(delivery.id), "acknowledged_sim_time": delivery.acknowledged_sim_time}


@router.get("/rooms/{room_id}/team-messages", summary="Team messages visible to the caller")
async def team_messages(access: RoomParticipant, session: SessionDep) -> list[dict[str, Any]]:
    assert access.participant is not None
    state = await trainee_state(session, access.room, access.participant, clock)
    rows: list[dict[str, Any]] = state["team_messages"]
    return rows


@router.post(
    "/rooms/{room_id}/team-messages",
    status_code=status.HTTP_201_CREATED,
    summary="Send a team message over a channel",
)
async def post_team_message(
    body: TeamMessageIn, access: RoomParticipant, session: SessionDep
) -> dict[str, Any]:
    assert access.participant is not None
    result = await send_team_message(
        session,
        clock,
        access.room,
        access.participant,
        channel_key=body.channel_key,
        message=body.message,
        recipient_id=body.recipient_participant_id,
    )
    await commit_and_publish(session)
    return result
