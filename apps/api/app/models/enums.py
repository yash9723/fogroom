"""Domain enumerations (stored as VARCHAR with CHECK constraints)."""

from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    INSTRUCTOR = "INSTRUCTOR"
    TRAINEE = "TRAINEE"


class Difficulty(StrEnum):
    BEGINNER = "BEGINNER"
    INTERMEDIATE = "INTERMEDIATE"
    ADVANCED = "ADVANCED"


class RoomStatus(StrEnum):
    LOBBY = "LOBBY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    ARCHIVED = "ARCHIVED"


class ConnectionStatus(StrEnum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"


class ChannelStatus(StrEnum):
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"


class DeliveryStatus(StrEnum):
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    DELAYED = "DELAYED"
    DROPPED = "DROPPED"
    ALTERED = "ALTERED"
    FAILED = "FAILED"


RECEIVED_STATUSES = (DeliveryStatus.DELIVERED, DeliveryStatus.ALTERED)
IN_FLIGHT_STATUSES = (DeliveryStatus.PENDING, DeliveryStatus.DELAYED)


class TransformationType(StrEnum):
    NONE = "NONE"
    DELAY = "DELAY"
    DROP = "DROP"
    VARIANT = "VARIANT"
    CHANNEL_UNAVAILABLE = "CHANNEL_UNAVAILABLE"
    REROUTED = "REROUTED"


class DisruptionType(StrEnum):
    DELAY = "DELAY"
    DROPOUT = "DROPOUT"
    CHANNEL_FAILURE = "CHANNEL_FAILURE"
    RELIABILITY_REDUCTION = "RELIABILITY_REDUCTION"
    CONFLICT_INJECTION = "CONFLICT_INJECTION"
    BLACKOUT = "BLACKOUT"


class Priority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class SourceReliability(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SenderType(StrEnum):
    SYSTEM = "SYSTEM"
    INSTRUCTOR = "INSTRUCTOR"
    PARTICIPANT = "PARTICIPANT"


class EventVisibility(StrEnum):
    ALL = "ALL"  # every member of the room
    INSTRUCTOR = "INSTRUCTOR"  # room owner / admins only
    PARTICIPANTS = "PARTICIPANTS"  # only target_participant_ids (+ instructor)


class DecisionPointStatus(StrEnum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class ActorType(StrEnum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    ENGINE = "ENGINE"


class TriggerType(StrEnum):
    TIME = "TIME"
    MANUAL = "MANUAL"
    AFTER_DECISION = "AFTER_DECISION"


class ScenarioEventType(StrEnum):
    BRIEFING = "BRIEFING"
    INFORMATION = "INFORMATION"
    WEATHER = "WEATHER"
    REQUEST = "REQUEST"
    NOTICE = "NOTICE"
    CHANNEL_CHANGE = "CHANNEL_CHANGE"
    DISRUPTION = "DISRUPTION"


MESSAGE_EVENT_TYPES = {
    ScenarioEventType.BRIEFING,
    ScenarioEventType.INFORMATION,
    ScenarioEventType.WEATHER,
    ScenarioEventType.REQUEST,
    ScenarioEventType.NOTICE,
}
