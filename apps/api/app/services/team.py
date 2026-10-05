"""Team communication between participants - subject to channel availability."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError, conflict, not_found
from app.core.text import require_text
from app.models.enums import ActorType, ChannelStatus, DeliveryStatus, EventVisibility, RoomStatus
from app.models.messaging import TeamMessage
from app.models.room import CommunicationChannel, Participant, SimulationRoom
from app.scenario.clock import Clock, sim_now
from app.services.audit import record_event
from app.services.delivery import DeliveryService


async def send_team_message(
    session: AsyncSession,
    clock: Clock,
    room: SimulationRoom,
    sender: Participant,
    *,
    channel_key: str,
    message: str,
    recipient_id: uuid.UUID | None,
) -> dict[str, Any]:
    if room.status not in (RoomStatus.RUNNING, RoomStatus.PAUSED):
        raise conflict(
            "ROOM_NOT_RUNNING", "Team communication is only available during the exercise."
        )
    text = require_text(message, 1000)
    if not text:
        raise AppError("EMPTY_MESSAGE", "Message cannot be empty.", 422)
    sim = sim_now(room, clock.now())

    channel = await session.scalar(
        select(CommunicationChannel).where(
            CommunicationChannel.room_id == room.id, CommunicationChannel.key == channel_key
        )
    )
    if channel is None:
        raise not_found("CHANNEL_NOT_FOUND", "Channel not found.")
    participants = list(
        (await session.scalars(select(Participant).where(Participant.room_id == room.id))).all()
    )
    if recipient_id is not None and recipient_id not in {p.id for p in participants}:
        raise not_found("PARTICIPANT_NOT_FOUND", "Recipient not found in this room.")

    disruptions = await DeliveryService(session, clock).active_disruptions(room.id)
    everyone_out, out_ids = DeliveryService.blacked_out(disruptions)

    failure: str | None = None
    if everyone_out or str(sender.id) in out_ids:
        failure = "Your communications are blacked out"
    elif channel.status == ChannelStatus.OFFLINE:
        failure = f"{channel.name} is offline"

    candidates = [
        p
        for p in participants
        if p.id != sender.id and (recipient_id is None or p.id == recipient_id)
    ]
    delivered_to = (
        []
        if failure
        else [str(p.id) for p in candidates if not (everyone_out or str(p.id) in out_ids)]
    )
    if not failure and recipient_id is not None and not delivered_to:
        failure = "Recipient is unreachable"

    row = TeamMessage(
        room_id=room.id,
        sender_participant_id=sender.id,
        recipient_participant_id=recipient_id,
        channel_id=channel.id,
        message=text,
        sim_time=sim,
        delivered_to=delivered_to,
        delivery_status=DeliveryStatus.FAILED.value if failure else DeliveryStatus.DELIVERED.value,
        failure_reason=failure,
    )
    session.add(row)
    await session.flush()
    payload = {
        "id": str(row.id),
        "sender_participant_id": str(sender.id),
        "sender_callsign": sender.callsign,
        "recipient_participant_id": str(recipient_id) if recipient_id else None,
        "channel_key": channel.key,
        "message": text,
        "sim_time": sim,
        "delivery_status": row.delivery_status,
        "failure_reason": failure,
    }
    if failure:
        await record_event(
            session,
            room.id,
            "team.message_failed",
            {**payload, "delivered_to": []},
            actor_id=sender.user_id,
            actor_type=ActorType.USER,
            sim_time=sim,
        )
    else:
        await record_event(
            session,
            room.id,
            "team.message",
            payload,
            actor_id=sender.user_id,
            actor_type=ActorType.USER,
            sim_time=sim,
            visibility=EventVisibility.PARTICIPANTS,
            targets=[str(sender.id), *delivered_to],
        )
    return payload
