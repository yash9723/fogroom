"""Information-State Digital Twin.

Reconstructs, for any participant and any simulation time t, exactly what that
participant knew: received / in-flight / dropped / never-addressed messages, effective
channel availability, active disruptions, known contradictions, beliefs vs ground truth,
decisions taken - plus the experimental uncertainty metrics.

The reconstruction is computed purely from recorded history (messages, deliveries,
channel state changes, disruptions, decisions). It never re-runs probabilistic logic,
so the AAR replay matches the original session exactly.
"""

import uuid
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.decision import Decision
from app.models.enums import ChannelStatus, DeliveryStatus, DisruptionType
from app.models.messaging import CommunicationDisruption, Message, MessageDelivery
from app.models.room import (
    ChannelStateChange,
    CommunicationChannel,
    Participant,
    RoomDecisionPoint,
    SimulationRoom,
)
from app.services import metrics as m

RECEIVED = {DeliveryStatus.DELIVERED.value, DeliveryStatus.ALTERED.value}


@dataclass
class _History:
    messages: list[Message]
    deliveries: list[MessageDelivery]
    channels: list[CommunicationChannel]
    changes: list[ChannelStateChange]
    disruptions: list[CommunicationDisruption]
    participants: list[Participant]
    decisions: list[Decision]
    decision_points: list[RoomDecisionPoint]


def truth_value_at(facts: list[dict[str, Any]], key: str | None, t: float) -> str | None:
    if not key:
        return None
    for fact in facts:
        if fact.get("key") == key:
            value = None
            for entry in sorted(fact.get("timeline", []), key=lambda e: e["from_seconds"]):
                if entry["from_seconds"] <= t:
                    value = entry["value"]
            return value
    return None


def fact_label(facts: list[dict[str, Any]], key: str) -> str:
    for fact in facts:
        if fact.get("key") == key:
            return str(fact.get("label", key))
    return key


class InformationStateService:
    def __init__(self, session: AsyncSession, cfg: m.MetricConfig = m.DEFAULT_CONFIG) -> None:
        self.session = session
        self.cfg = cfg

    async def _load(self, room: SimulationRoom, t: float) -> _History:
        s = self.session
        messages = list(
            (
                await s.scalars(
                    select(Message)
                    .where(Message.room_id == room.id, Message.created_sim_time <= t)
                    .order_by(Message.created_sim_time, Message.label)
                )
            ).all()
        )
        message_ids = [msg.id for msg in messages]
        deliveries = (
            list(
                (
                    await s.scalars(
                        select(MessageDelivery).where(MessageDelivery.message_id.in_(message_ids))
                    )
                ).all()
            )
            if message_ids
            else []
        )
        return _History(
            messages=messages,
            deliveries=deliveries,
            channels=list(
                (
                    await s.scalars(
                        select(CommunicationChannel)
                        .where(CommunicationChannel.room_id == room.id)
                        .order_by(CommunicationChannel.sort_order)
                    )
                ).all()
            ),
            changes=list(
                (
                    await s.scalars(
                        select(ChannelStateChange)
                        .where(
                            ChannelStateChange.room_id == room.id, ChannelStateChange.sim_time <= t
                        )
                        .order_by(ChannelStateChange.sim_time, ChannelStateChange.created_at)
                    )
                ).all()
            ),
            disruptions=list(
                (
                    await s.scalars(
                        select(CommunicationDisruption).where(
                            CommunicationDisruption.room_id == room.id,
                            CommunicationDisruption.start_sim_time <= t,
                        )
                    )
                ).all()
            ),
            participants=list(
                (
                    await s.scalars(
                        select(Participant)
                        .where(Participant.room_id == room.id)
                        .order_by(Participant.joined_at)
                    )
                ).all()
            ),
            decisions=list(
                (
                    await s.scalars(
                        select(Decision)
                        .where(Decision.room_id == room.id, Decision.submitted_sim_time <= t)
                        .order_by(Decision.submitted_sim_time)
                    )
                ).all()
            ),
            decision_points=list(
                (
                    await s.scalars(
                        select(RoomDecisionPoint)
                        .where(
                            RoomDecisionPoint.room_id == room.id,
                            RoomDecisionPoint.opened_sim_time <= t,
                        )
                        .order_by(RoomDecisionPoint.opened_sim_time)
                    )
                ).all()
            ),
        )

    # ------------------------------------------------------------------ helpers

    @staticmethod
    def _channels_at(h: _History, t: float) -> dict[uuid.UUID, dict[str, Any]]:
        state: dict[uuid.UUID, dict[str, Any]] = {}
        for c in h.channels:
            state[c.id] = {
                "id": str(c.id),
                "key": c.key,
                "name": c.name,
                "channel_type": c.channel_type,
                "weight": c.weight,
                # Before any recorded change (lobby), fall back to the live row.
                "status": c.status,
                "reliability": c.reliability,
                "latency_ms": c.latency_ms,
            }
        seen: set[uuid.UUID] = set()
        for change in h.changes:  # ordered by sim_time
            if change.sim_time <= t and change.channel_id in state:
                st = state[change.channel_id]
                st["status"] = change.status
                st["reliability"] = change.reliability
                st["latency_ms"] = change.latency_ms
                seen.add(change.channel_id)
        return state

    @staticmethod
    def _active_disruptions(h: _History, t: float) -> list[CommunicationDisruption]:
        return [
            d
            for d in h.disruptions
            if d.start_sim_time <= t and (d.end_sim_time is None or d.end_sim_time > t)
        ]

    @staticmethod
    def _message_summary(msg: Message, channels: dict[uuid.UUID, dict[str, Any]]) -> dict[str, Any]:
        ch = channels.get(msg.channel_id) if msg.channel_id else None
        return {
            "message_id": str(msg.id),
            "label": msg.label,
            "title": msg.title,
            "canonical_content": msg.canonical_content,
            "source": msg.source,
            "source_reliability": msg.source_reliability,
            "priority": msg.priority,
            "importance_weight": msg.importance_weight,
            "channel_key": ch["key"] if ch else None,
            "channel_name": ch["name"] if ch else "System",
            "fact_key": msg.fact_key,
            "fact_value": msg.fact_value,
            "location_key": msg.location_key,
            "created_sim_time": msg.created_sim_time,
            "sender_type": msg.sender_type,
        }

    # ------------------------------------------------------------- reconstruct

    async def reconstruct(
        self, room: SimulationRoom, participant_id: uuid.UUID | None, t: float
    ) -> dict[str, Any]:
        """Information state at simulation time `t` (participant view, or global truth when
        participant_id is None)."""
        h = await self._load(room, t)
        facts: list[dict[str, Any]] = (
            (room.scenario_snapshot or {}).get("initial_conditions", {}).get("facts", [])
        )
        channels = self._channels_at(h, t)
        active = self._active_disruptions(h, t)
        truth_facts = [
            {
                "key": f["key"],
                "label": f.get("label", f["key"]),
                "value": truth_value_at(facts, f["key"], t),
            }
            for f in facts
        ]
        base: dict[str, Any] = {
            "room_id": str(room.id),
            "sim_time": t,
            "truth": {"facts": truth_facts},
            "active_disruptions": [
                {
                    "id": str(d.id),
                    "disruption_type": d.disruption_type,
                    "target_participant_ids": d.target_participant_ids,
                    "target_channel_ids": d.target_channel_ids,
                    "configuration": d.configuration,
                    "start_sim_time": d.start_sim_time,
                    "end_sim_time": d.end_sim_time,
                }
                for d in active
            ],
        }
        if participant_id is None:
            return {**base, **(await self._truth_view(room, h, t, channels, facts))}

        participant = next((p for p in h.participants if p.id == participant_id), None)
        if participant is None:
            raise ValueError("participant not in room")
        return {**base, **self._participant_view(h, participant, t, channels, active, facts)}

    def _participant_view(
        self,
        h: _History,
        participant: Participant,
        t: float,
        channels: dict[uuid.UUID, dict[str, Any]],
        active: list[CommunicationDisruption],
        facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        pid = str(participant.id)
        mine = {d.message_id: d for d in h.deliveries if d.participant_id == participant.id}

        received: list[dict[str, Any]] = []
        pending: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []
        not_addressed: list[dict[str, Any]] = []
        intended: list[m.IntendedItem] = []
        received_items: list[m.ReceivedItem] = []

        for msg in h.messages:
            summary = self._message_summary(msg, channels)
            summary["truth_value_at_t"] = truth_value_at(facts, msg.fact_key, t)
            d = mine.get(msg.id)
            if d is None:
                not_addressed.append(summary)
                continue
            delivery_info = {
                "delivery_id": str(d.id),
                "status": d.delivery_status,
                "transformation_type": d.transformation_type,
                "reasons": (d.transformation_metadata or {}).get("reasons", []),
                "delivered_title": d.delivered_title,
                "delivered_content": d.delivered_content,
                "delivered_fact_value": d.delivered_fact_value,
                "delivered_source": d.delivered_source,
                "delivered_source_reliability": d.delivered_source_reliability,
                "reliability_score": d.reliability_score,
                "received_sim_time": d.actual_delivery_sim_time,
                "scheduled_sim_time": d.scheduled_sim_time,
                "delay_seconds": d.delay_seconds,
                "acknowledged": d.acknowledged_sim_time is not None
                and d.acknowledged_sim_time <= t,
                "altered": d.transformation_type == "VARIANT",
            }
            item = {**summary, **delivery_info}
            got = (
                d.delivery_status in RECEIVED
                and d.actual_delivery_sim_time is not None
                and d.actual_delivery_sim_time <= t
            )
            intended.append(
                m.IntendedItem(
                    weight=msg.importance_weight, received=got, altered=bool(item["altered"])
                )
            )
            if got:
                received.append(item)
                received_items.append(
                    m.ReceivedItem(
                        weight=msg.importance_weight,
                        source_reliability=d.delivered_source_reliability or msg.source_reliability,
                        path_reliability=d.reliability_score,
                    )
                )
            elif d.delivery_status == DeliveryStatus.DROPPED:
                dropped.append(item)
            else:
                # In flight at t. The eventual outcome is known to the instructor.
                if d.actual_delivery_sim_time is not None:
                    item["eventual_outcome"] = "DELIVERED_LATER"
                    item["arrives_sim_time"] = d.actual_delivery_sim_time
                elif d.delivery_status == DeliveryStatus.FAILED:
                    item["eventual_outcome"] = "NEVER_DELIVERED"
                    item["arrives_sim_time"] = None
                else:
                    item["eventual_outcome"] = "IN_FLIGHT"
                    item["arrives_sim_time"] = d.scheduled_sim_time
                pending.append(item)

        # Effective channel view (blackout => everything offline for this participant).
        blackout = any(
            d.disruption_type == DisruptionType.BLACKOUT
            and (not d.target_participant_ids or pid in d.target_participant_ids)
            for d in active
        )
        channel_list = []
        for st in channels.values():
            effective = ChannelStatus.OFFLINE.value if blackout else st["status"]
            channel_list.append({**st, "base_status": st["status"], "status": effective})
        unavailable = [c["id"] for c in channel_list if c["status"] == ChannelStatus.OFFLINE]

        contradictions = self._contradictions(received, facts)
        beliefs = self._beliefs(received, facts, t)

        completeness = m.completeness(intended, self.cfg)
        reliability = m.reliability(received_items, self.cfg)
        comm_health = m.communication_health(
            m.ChannelHealthItem(c["weight"], c["status"], c["reliability"]) for c in channel_list
        )
        confidence = m.information_confidence(
            completeness, reliability, comm_health, len(contradictions), self.cfg
        )

        my_decisions = [d for d in h.decisions if d.participant_id == participant.id]
        dp_by_id = {dp.id: dp for dp in h.decision_points}
        open_points = [
            dp
            for dp in h.decision_points
            if (not dp.target_participant_ids or pid in dp.target_participant_ids)
            and (dp.closed_sim_time is None or dp.closed_sim_time > t)
            and dp.id not in {d.decision_point_id for d in my_decisions}
        ]
        return {
            "view": "PARTICIPANT",
            "participant": {
                "id": pid,
                "callsign": participant.callsign,
                "role": participant.assigned_role,
            },
            "received": received,
            "pending": pending,
            "dropped": dropped,
            "not_addressed": not_addressed,
            "channels": channel_list,
            "unavailable_channel_ids": unavailable,
            "blackout": blackout,
            "contradictions": contradictions,
            "beliefs": beliefs,
            "decisions": [
                {
                    "id": str(d.id),
                    "decision_point_key": dp_by_id[d.decision_point_id].key
                    if d.decision_point_id in dp_by_id
                    else None,
                    "selected_option": d.selected_option,
                    "decision_text": d.decision_text,
                    "confidence": d.confidence,
                    "submitted_sim_time": d.submitted_sim_time,
                }
                for d in my_decisions
            ],
            "open_decision_points": [{"key": dp.key, "title": dp.title} for dp in open_points],
            "metrics": {
                "information_completeness": completeness,
                "information_reliability": reliability,
                "communication_health": comm_health,
                "known_contradictions": len(contradictions),
                "information_confidence": confidence,
                "uncertainty_index": round(100.0 - confidence, 1),
                "counts": {
                    "received": len(received),
                    "pending": len(pending),
                    "dropped": len(dropped),
                    "not_addressed": len(not_addressed),
                },
            },
        }

    @staticmethod
    def _contradictions(
        received: list[dict[str, Any]], facts: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        by_fact: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in received:
            value = item.get("delivered_fact_value") or item.get("fact_value")
            if item.get("fact_key") and value:
                by_fact[item["fact_key"]].append(item)
        result = []
        for key, items in by_fact.items():
            values = {(i.get("delivered_fact_value") or i.get("fact_value")) for i in items}
            if len(values) > 1:
                result.append(
                    {
                        "fact_key": key,
                        "label": fact_label(facts, key),
                        "reports": [
                            {
                                "value": i.get("delivered_fact_value") or i.get("fact_value"),
                                "label": i["label"],
                                "title": i.get("delivered_title") or i["title"],
                                "source": i.get("delivered_source") or i["source"],
                                "source_reliability": i.get("delivered_source_reliability")
                                or i["source_reliability"],
                                "received_sim_time": i.get("received_sim_time"),
                            }
                            for i in sorted(items, key=lambda x: x.get("received_sim_time") or 0)
                        ],
                    }
                )
        return result

    @staticmethod
    def _beliefs(
        received: list[dict[str, Any]], facts: list[dict[str, Any]], t: float
    ) -> list[dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for item in sorted(received, key=lambda x: x.get("received_sim_time") or 0):
            value = item.get("delivered_fact_value") or item.get("fact_value")
            if item.get("fact_key") and value:
                latest[item["fact_key"]] = {"value": value, "label": item["label"]}
        beliefs = []
        for key, info in latest.items():
            truth = truth_value_at(facts, key, t)
            beliefs.append(
                {
                    "fact_key": key,
                    "label": fact_label(facts, key),
                    "believed_value": info["value"],
                    "based_on": info["label"],
                    "truth_value": truth,
                    "accurate": truth is None or truth == info["value"],
                }
            )
        return beliefs

    async def _truth_view(
        self,
        room: SimulationRoom,
        h: _History,
        t: float,
        channels: dict[uuid.UUID, dict[str, Any]],
        facts: list[dict[str, Any]],
    ) -> dict[str, Any]:
        deliveries_by_msg: dict[uuid.UUID, list[MessageDelivery]] = defaultdict(list)
        for d in h.deliveries:
            deliveries_by_msg[d.message_id].append(d)
        callsign = {p.id: p.callsign for p in h.participants}
        messages = []
        for msg in h.messages:
            summary = self._message_summary(msg, channels)
            summary["truth_value_at_t"] = truth_value_at(facts, msg.fact_key, t)
            outcome = []
            for d in deliveries_by_msg.get(msg.id, []):
                received_by_t = (
                    d.delivery_status in RECEIVED
                    and d.actual_delivery_sim_time is not None
                    and d.actual_delivery_sim_time <= t
                )
                if received_by_t:
                    state = "ALTERED" if d.delivery_status == DeliveryStatus.ALTERED else "RECEIVED"
                elif d.delivery_status == DeliveryStatus.DROPPED:
                    state = "DROPPED"
                else:
                    state = "IN_FLIGHT"
                outcome.append(
                    {
                        "participant_id": str(d.participant_id),
                        "callsign": callsign.get(d.participant_id),
                        "state": state,
                        "received_sim_time": d.actual_delivery_sim_time if received_by_t else None,
                        "delivered_fact_value": d.delivered_fact_value,
                    }
                )
            summary["deliveries"] = sorted(outcome, key=lambda o: o["callsign"] or "")
            messages.append(summary)

        summaries = []
        for p in h.participants:
            view = self._participant_view(h, p, t, channels, self._active_disruptions(h, t), facts)
            summaries.append(
                {
                    "participant_id": str(p.id),
                    "callsign": p.callsign,
                    "role": p.assigned_role,
                    "metrics": view["metrics"],
                    "contradictions": len(view["contradictions"]),
                    "inaccurate_beliefs": [b for b in view["beliefs"] if not b["accurate"]],
                }
            )
        channel_list = [{**st, "base_status": st["status"]} for st in channels.values()]
        comm_health = m.communication_health(
            m.ChannelHealthItem(c["weight"], c["status"], c["reliability"]) for c in channel_list
        )
        return {
            "view": "TRUTH",
            "participant": None,
            "messages": messages,
            "channels": channel_list,
            "participants": summaries,
            "decisions": [
                {
                    "id": str(d.id),
                    "participant_id": str(d.participant_id),
                    "callsign": callsign.get(d.participant_id),
                    "selected_option": d.selected_option,
                    "confidence": d.confidence,
                    "submitted_sim_time": d.submitted_sim_time,
                }
                for d in h.decisions
            ],
            "metrics": {
                "communication_health": comm_health,
                "message_count": len(h.messages),
                "mean_uncertainty_index": m.mean(
                    s["metrics"]["uncertainty_index"] for s in summaries
                ),
            },
        }
