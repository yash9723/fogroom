import uuid

from fastapi import APIRouter, status

from app.auth.deps import CurrentUser, InstructorUser, SessionDep
from app.core.errors import forbidden
from app.models.enums import ActorType, UserRole
from app.models.scenario import ScenarioTemplate
from app.scenario.loader import (
    apply_scenario,
    get_scenario,
    list_scenarios,
    replace_scenario,
    scenario_summary,
    scenario_to_out,
)
from app.schemas.scenario import ScenarioCreate, ScenarioOut, ScenarioSummary
from app.services.audit import record_event

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


def _can_edit(user_role: str) -> None:
    if user_role not in (UserRole.INSTRUCTOR, UserRole.ADMIN):
        raise forbidden("Only instructors can manage scenarios.", "FORBIDDEN_ROLE")


@router.get("", response_model=list[ScenarioSummary], summary="List scenario templates")
async def get_scenarios(user: CurrentUser, session: SessionDep) -> list[ScenarioSummary]:
    _can_edit(user.role)
    return [scenario_summary(s) for s in await list_scenarios(session)]


@router.post(
    "", response_model=ScenarioOut, status_code=status.HTTP_201_CREATED, summary="Create a scenario"
)
async def create_scenario(
    body: ScenarioCreate, user: InstructorUser, session: SessionDep
) -> ScenarioOut:
    scenario = apply_scenario(ScenarioTemplate(created_by=user.id), body)
    session.add(scenario)
    await session.flush()
    await record_event(
        session,
        None,
        "scenario.created",
        {"scenario_id": str(scenario.id), "name": scenario.name},
        actor_id=user.id,
        actor_type=ActorType.USER,
    )
    await session.commit()
    return scenario_to_out(await get_scenario(session, scenario.id))


@router.get(
    "/{scenario_id}",
    response_model=ScenarioOut,
    summary="Get a scenario with all phases, events and decision points",
)
async def read_scenario(
    scenario_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> ScenarioOut:
    _can_edit(user.role)
    return scenario_to_out(await get_scenario(session, scenario_id))


@router.put("/{scenario_id}", response_model=ScenarioOut, summary="Replace a scenario definition")
async def update_scenario(
    scenario_id: uuid.UUID, body: ScenarioCreate, user: InstructorUser, session: SessionDep
) -> ScenarioOut:
    """Rooms keep a frozen snapshot of the scenario they were created from, so edits never
    change exercises that have already run."""
    scenario = await get_scenario(session, scenario_id)
    await replace_scenario(session, scenario, body)
    await record_event(
        session,
        None,
        "scenario.updated",
        {"scenario_id": str(scenario.id), "name": scenario.name},
        actor_id=user.id,
        actor_type=ActorType.USER,
    )
    await session.commit()
    session.expire_all()
    return scenario_to_out(await get_scenario(session, scenario_id))


@router.post(
    "/{scenario_id}/duplicate",
    response_model=ScenarioOut,
    status_code=status.HTTP_201_CREATED,
    summary="Duplicate a scenario",
)
async def duplicate_scenario(
    scenario_id: uuid.UUID, user: InstructorUser, session: SessionDep
) -> ScenarioOut:
    source = scenario_to_out(await get_scenario(session, scenario_id))
    data = ScenarioCreate.model_validate(
        {
            **source.model_dump(
                mode="json",
                exclude={"id", "created_at", "updated_at", "created_by", "is_published"},
            ),
            "name": f"{source.name} (copy)",
        }
    )
    copy = apply_scenario(ScenarioTemplate(created_by=user.id), data)
    session.add(copy)
    await session.commit()
    return scenario_to_out(await get_scenario(session, copy.id))


@router.delete(
    "/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a scenario template"
)
async def delete_scenario(
    scenario_id: uuid.UUID, user: InstructorUser, session: SessionDep
) -> None:
    scenario = await get_scenario(session, scenario_id)
    await record_event(
        session,
        None,
        "scenario.deleted",
        {"scenario_id": str(scenario.id), "name": scenario.name},
        actor_id=user.id,
        actor_type=ActorType.USER,
    )
    await session.delete(scenario)
    await session.commit()
