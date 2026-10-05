"""Transparent, configurable training metrics.

These are EXPERIMENTAL TRAINING METRICS designed to be explainable in an After Action
Review. They are not scientifically validated measures of performance.

Information Confidence Score (ICS), 0-100:
    ICS = 0.40 x Completeness + 0.30 x Reliability + 0.30 x Communication Health
          - min(contradiction_cap, contradiction_penalty x known_contradictions)
Uncertainty Index = 100 - ICS

Completeness = sum(weight of intended messages received) / sum(weight of intended messages)
               (an ALTERED/conflicting delivery counts `altered_credit` of its weight)
Reliability  = importance-weighted mean of (source reliability x path reliability) of
               received messages
Comm Health  = weighted mean of channel health; ONLINE/DEGRADED = reliability x 100,
               OFFLINE = 0; a participant under blackout sees every channel as OFFLINE.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetricConfig:
    weight_completeness: float = 0.40
    weight_reliability: float = 0.30
    weight_comm_health: float = 0.30
    contradiction_penalty: float = 10.0
    contradiction_cap: float = 30.0
    altered_credit: float = 0.5
    empty_reliability: float = 50.0
    high_uncertainty_threshold: float = 50.0
    source_reliability_weights: dict[str, float] = field(
        default_factory=lambda: {"HIGH": 0.9, "MEDIUM": 0.6, "LOW": 0.3}
    )


DEFAULT_CONFIG = MetricConfig()


@dataclass(frozen=True)
class IntendedItem:
    weight: float
    received: bool
    altered: bool = False


@dataclass(frozen=True)
class ReceivedItem:
    weight: float
    source_reliability: str
    path_reliability: float


@dataclass(frozen=True)
class ChannelHealthItem:
    weight: float
    status: str
    reliability: float


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def completeness(items: Iterable[IntendedItem], cfg: MetricConfig = DEFAULT_CONFIG) -> float:
    items = list(items)
    total = sum(i.weight for i in items)
    if total <= 0:
        return 100.0
    got = sum(i.weight * (cfg.altered_credit if i.altered else 1.0) for i in items if i.received)
    return round(clamp(100.0 * got / total), 1)


def reliability(items: Iterable[ReceivedItem], cfg: MetricConfig = DEFAULT_CONFIG) -> float:
    items = list(items)
    total = sum(i.weight for i in items)
    if total <= 0:
        return cfg.empty_reliability
    score = sum(
        i.weight
        * cfg.source_reliability_weights.get(i.source_reliability, 0.5)
        * i.path_reliability
        for i in items
    )
    return round(clamp(100.0 * score / total), 1)


def communication_health(items: Iterable[ChannelHealthItem]) -> float:
    items = list(items)
    total = sum(i.weight for i in items)
    if total <= 0:
        return 100.0
    score = sum(i.weight * (0.0 if i.status == "OFFLINE" else i.reliability * 100.0) for i in items)
    return round(clamp(score / total), 1)


def information_confidence(
    completeness_score: float,
    reliability_score: float,
    comm_health_score: float,
    contradictions: int,
    cfg: MetricConfig = DEFAULT_CONFIG,
) -> float:
    base = (
        cfg.weight_completeness * completeness_score
        + cfg.weight_reliability * reliability_score
        + cfg.weight_comm_health * comm_health_score
    )
    penalty = min(cfg.contradiction_cap, cfg.contradiction_penalty * contradictions)
    return round(clamp(base - penalty), 1)


def uncertainty_index(
    completeness_score: float,
    reliability_score: float,
    comm_health_score: float,
    contradictions: int,
    cfg: MetricConfig = DEFAULT_CONFIG,
) -> float:
    return round(
        100.0
        - information_confidence(
            completeness_score, reliability_score, comm_health_score, contradictions, cfg
        ),
        1,
    )


# ---------------------------------------------------------------- decision metrics


def response_score(response_time_s: float, window_s: float) -> float:
    """100 for an instant decision, 50 at the deadline, 0 if missed (handled by caller)."""
    if window_s <= 0:
        return 100.0
    return round(clamp(100.0 * (1.0 - 0.5 * min(1.0, response_time_s / window_s))), 1)


def calibration_score(confidence: float, information_confidence_score: float) -> float:
    """Uncertainty management: how well stated confidence matches information quality."""
    return round(clamp(100.0 - abs(confidence - information_confidence_score)), 1)


def mean(values: Iterable[float], default: float = 0.0) -> float:
    vals = list(values)
    return round(sum(vals) / len(vals), 1) if vals else default
