# After Action Review & metrics

Code: `apps/api/app/aar/{builder,pdf,ai}.py`, `app/services/{information_state,metrics}.py`;
UI: `apps/web/app/(instructor)/aar/[roomId]`, `components/aar/*`.

## Replay never re-simulates

Replay reads recorded history only (messages, deliveries with actual delivery times, channel
state changes, disruptions, decisions). Probabilistic logic is never re-run, so the AAR matches
the live session exactly.

`GET /rooms/{id}/participants/{pid}/information-state?timestamp=t` (instructor only) returns:
received (with delivered/altered content), in flight (with eventual outcome: delivered later /
never delivered), dropped, never addressed, effective channels (blackout aware), active
disruptions, known contradictions, beliefs vs ground truth, decisions, open decision points and
metrics. `GET /rooms/{id}/information-state/truth?timestamp=t` returns every canonical message
with each participant's delivery state, ground-truth facts at `t` and per-participant summaries.

## Decision inspection

`GET /rooms/{id}/decisions/{decision_id}/inspection`: participant, decision, timestamp,
response time, confidence, rationale, **available** information, **missing** information
(dropped / never addressed / in flight), **delayed** information (arrived late / arrived after
the decision), **conflicting** information, beliefs vs truth, uncertainty score. Every decision
also has a frozen `information_snapshots` row written in the same transaction.

## Experimental training metrics (transparent formulas)

All weights live in `MetricConfig` (`services/metrics.py`).

| Metric | Formula |
|--------|---------|
| Information Completeness | Σ weight(received) / Σ weight(addressed to participant); ALTERED counts 0.5 |
| Information Reliability | importance-weighted mean of source reliability (HIGH 0.9 / MEDIUM 0.6 / LOW 0.3) × path reliability |
| Communication Health | weighted mean of channel health (reliability × 100; OFFLINE = 0; blackout → all offline) |
| Information Confidence (ICS) | 0.40 × Completeness + 0.30 × Reliability + 0.30 × Comm Health − min(30, 10 × known contradictions) |
| **Uncertainty Index** | 100 − ICS |
| Decision Response Score | mean of 100 × (1 − 0.5 × response_time / window); missed decision = 0 |
| Information Awareness | 0.7 × mean completeness at decision time + 0.3 × acknowledgement rate |
| Decision Quality | mean scenario-designer rubric score (`truth_alignment`) of chosen options; custom = 50 |
| Uncertainty Management (calibration) | mean of 100 − abs(confidence − ICS at decision) |
| Training Coordination Metric | 0.4 × agreement with team's modal choice + 0.3 × communication participation + 0.3 × acknowledgement rate |
| Team score | mean of each participant's mean of the five scores above |

Decisions under high uncertainty: uncertainty index ≥ 50. These are explainable training
metrics intended to structure debrief discussion - **not scientifically validated**.

## Report contents

Exercise summary, narrative (template or AI), team metrics, participant comparison, decisions,
critical decision analysis (relevant beliefs, missing relevant information), disruptions,
channel history, information outcomes ("M102 was dropped for CHARLIE"), objectives mapped to
observations, recommendations, instructor notes, formulas and disclaimer.

Export: `GET /rooms/{id}/aar/export.pdf` (reportlab) or the print page `/aar/{id}/print`.

## AI narrative (optional)

`AIAnalysisService` uses Claude (`ANTHROPIC_MODEL`, default `claude-sonnet-5-5`) when
`ANTHROPIC_API_KEY` is set and the `ai` extra is installed (`pip install -e '.[ai]'`);
otherwise a deterministic template. Output is stored only in `aar_reports.ai_narrative` and
never modifies historical simulation records.
