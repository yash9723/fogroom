"""Import every model so Base.metadata is complete (Alembic, tests, services)."""

from app.models.aar import AARReport, MetricSnapshot
from app.models.audit import AuditEvent
from app.models.decision import Decision, InformationSnapshot
from app.models.messaging import (
    CommunicationDisruption,
    Message,
    MessageDelivery,
    ScenarioEvent,
    TeamMessage,
)
from app.models.room import (
    ChannelStateChange,
    CommunicationChannel,
    InstructorNote,
    Participant,
    RoomDecisionPoint,
    SimulationRoom,
)
from app.models.scenario import (
    ScenarioChannel,
    ScenarioDecisionPoint,
    ScenarioEventTemplate,
    ScenarioPhase,
    ScenarioRole,
    ScenarioTemplate,
)
from app.models.user import RefreshToken, User

__all__ = [
    "AARReport",
    "AuditEvent",
    "ChannelStateChange",
    "CommunicationChannel",
    "CommunicationDisruption",
    "Decision",
    "InformationSnapshot",
    "InstructorNote",
    "Message",
    "MessageDelivery",
    "MetricSnapshot",
    "Participant",
    "RefreshToken",
    "RoomDecisionPoint",
    "ScenarioChannel",
    "ScenarioDecisionPoint",
    "ScenarioEvent",
    "ScenarioEventTemplate",
    "ScenarioPhase",
    "ScenarioRole",
    "ScenarioTemplate",
    "SimulationRoom",
    "TeamMessage",
    "User",
]
