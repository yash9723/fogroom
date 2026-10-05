"""Information-State Digital Twin queries, decision inspection and AAR reports."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Query, Response
from sqlalchemy import select

from app.aar.ai import AIAnalysisService
from app.aar.builder import build_report, inspect_decision
from app.aar.pdf import render_pdf
from app.analytics.service import room_metric_series
from app.auth.deps import RoomInstructor, SessionDep
from app.core.errors import AppError, not_found
from app.models.aar import AARReport
from app.models.enums import ActorType, RoomStatus
from app.models.room import Participant
from app.scenario.clock import SystemClock, sim_now
from app.services.audit import commit_and_publish, record_event
from app.services.information_state import InformationStateService

router = APIRouter(tags=["aar"])
clock = SystemClock()


def _timestamp(room_sim: float, timestamp: float | None) -> float:
    if timestamp is None:
        return room_sim
    return max(0.0, min(float(timestamp), room_sim if room_sim > 0 else float(timestamp)))


@router.get(
    "/rooms/{room_id}/participants/{participant_id}/information-state",
    summary="Reconstruct what a participant knew at a simulation time (instructor only)",
)
async def participant_information_state(
    participant_id: uuid.UUID,
    access: RoomInstructor,
    session: SessionDep,
    timestamp: Annotated[
        float | None, Query(ge=0, description="Simulation seconds; default = now")
    ] = None,
) -> dict[str, Any]:
    participant = await session.get(Participant, participant_id)
    if participant is None or participant.room_id != access.room.id:
        raise not_found("PARTICIPANT_NOT_FOUND", "Participant not found in this room.")
    t = _timestamp(sim_now(access.room, clock.now()), timestamp)
    return await InformationStateService(session).reconstruct(access.room, participant_id, t)


@router.get(
    "/rooms/{room_id}/information-state/truth", summary="Global truth state at a simulation time"
)
async def truth_state(
    access: RoomInstructor,
    session: SessionDep,
    timestamp: Annotated[float | None, Query(ge=0)] = None,
) -> dict[str, Any]:
    t = _timestamp(sim_now(access.room, clock.now()), timestamp)
    return await InformationStateService(session).reconstruct(access.room, None, t)


@router.get(
    "/rooms/{room_id}/decisions/{decision_id}/inspection",
    summary="Available / missing / delayed / conflicting information behind one decision",
)
async def decision_inspection(
    decision_id: uuid.UUID, access: RoomInstructor, session: SessionDep
) -> dict[str, Any]:
    return await inspect_decision(session, access.room, decision_id)


async def _report_out(report: AARReport) -> dict[str, Any]:
    return {
        "id": str(report.id),
        "room_id": str(report.room_id),
        "generated_at": report.generated_at.isoformat(),
        "version": report.version,
        "summary": report.summary,
        "team_score": report.team_score,
        "narrative": report.ai_narrative,
        "narrative_source": report.narrative_source,
        "report": report.report_payload,
    }


@router.post(
    "/rooms/{room_id}/aar/generate",
    summary="Generate (or regenerate) the AAR for a completed exercise",
)
async def generate_aar(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    room = access.room
    if room.status not in (RoomStatus.COMPLETED, RoomStatus.ARCHIVED):
        raise AppError(
            "ROOM_NOT_COMPLETED", "The AAR is generated after the exercise has ended.", 409
        )
    payload = await build_report(session, room)
    narrative, source = await AIAnalysisService().narrative(payload)
    report = await session.scalar(select(AARReport).where(AARReport.room_id == room.id))
    if report is None:
        report = AARReport(room_id=room.id, version=1, summary="", team_score=0.0)
        session.add(report)
    else:
        report.version += 1
        report.generated_at = clock.now()
    report.generated_by = access.user.id
    report.summary = payload["summary"]
    report.team_score = payload["team"]["team_score"]
    report.report_payload = payload
    report.ai_narrative = narrative
    report.narrative_source = source
    await session.flush()
    await record_event(
        session,
        room.id,
        "aar.generated",
        {"report_id": str(report.id), "version": report.version},
        actor_id=access.user.id,
        actor_type=ActorType.USER,
        sim_time=room.final_sim_seconds,
    )
    await commit_and_publish(session)
    return await _report_out(report)


@router.get("/rooms/{room_id}/aar", summary="Get the generated AAR")
async def get_aar(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    report = await session.scalar(select(AARReport).where(AARReport.room_id == access.room.id))
    if report is None:
        raise not_found("AAR_NOT_FOUND", "No AAR has been generated for this exercise yet.")
    return await _report_out(report)


@router.get(
    "/rooms/{room_id}/aar/export.pdf",
    summary="Download the AAR as PDF",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def export_pdf(access: RoomInstructor, session: SessionDep) -> Response:
    report = await session.scalar(select(AARReport).where(AARReport.room_id == access.room.id))
    if report is None:
        raise not_found("AAR_NOT_FOUND", "Generate the AAR before exporting it.")
    pdf = render_pdf(report.report_payload, report.ai_narrative)
    filename = f"FOGROOM-AAR-{access.room.room_code}.pdf"
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/rooms/{room_id}/analytics", summary="Metric time series for an exercise")
async def room_analytics(access: RoomInstructor, session: SessionDep) -> dict[str, Any]:
    return await room_metric_series(session, access.room)
