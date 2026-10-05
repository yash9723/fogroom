# FOGROOM Architecture

FOGROOM is a multiplayer decision-training simulation. Its core idea is the
**Information-State Digital Twin**: the server keeps the *global truth* and, separately, an
exact record of what *each participant* received, when, through which channel, and in
which form, so that any participant's knowledge at any moment can be reconstructed for
After Action Review (AAR).

## System overview

```mermaid
flowchart LR
  subgraph Browser
    I[Instructor UI<br/>Next.js]
    T1[Trainee UI]
  end
  subgraph API[FastAPI process(es)]
    R[REST /api/v1]
    W[WebSocket /ws/rooms/:id]
    E[ScenarioEngine tick loop]
    D[CommunicationDegradationEngine]
    S[InformationStateService]
    A[AAR builder / PDF]
  end
  PG[(PostgreSQL<br/>source of truth)]
  RD[(Redis<br/>pub/sub, presence,<br/>engine locks, rate limits)]
  I -- HTTPS JSON --> R
  T1 -- HTTPS JSON --> R
  I <-- WS events --> W
  T1 <-- filtered WS events --> W
  R --> E
  E --> D
  E --> PG
  R --> S --> PG
  R --> A --> PG
  E -- publish after commit --> RD
  RD -- room:* --> W
```

## Truth vs participant information state

| Concept | Storage | Who can read |
|---------|---------|--------------|
| Ground truth facts over time | `simulation_rooms.scenario_snapshot.initial_conditions.facts` (timeline) | instructor |
| Canonical message (what was actually reported) | `messages` | instructor |
| What one participant experienced | `message_deliveries` (one row per message x recipient) | instructor; the participant sees only rows with status DELIVERED/ALTERED and `actual_delivery_sim_time` set |
| Channel state over time | `communication_channels` + append-only `channel_state_changes` | everyone sees current status; history is instructor-only |
| Decision + frozen knowledge | `decisions` + `information_snapshots` | instructor; trainee sees own decision |
| Event stream | append-only `audit_events` with per-room `seq` and `visibility` | filtered per viewer |

The trainee read model (`services/live_state.trainee_state`) is built **only** from that
participant's deliveries. Message labels (`M101`), fact keys and truth values are never sent
to trainees, so gaps in numbering cannot reveal dropped information.

## Key decisions (ADRs)

1. **Monorepo**: pnpm workspace (`apps/web`, `packages/shared`) + Python venv for `apps/api`
   (`pip install -e .[dev]`). No uv dependency.
2. **Task runner**: Makefile + equivalent `scripts/dev.ps1` for Windows.
3. **Simulation clock in simulation seconds, anchored**:
   `sim_now = sim_anchor + (wall - anchor_at) * time_scale` while running; frozen while
   paused. All schedules are stored as simulation seconds, so pause/resume, time scaling and
   fast-forward are correct by construction (`app/scenario/clock.py`).
4. **One tick loop per running room** (`app/scenario/runner.py`), 1 s cadence, guarded by a
   Redis lock (`SET NX PX`) so multiple API workers never double-tick a room. Running rooms
   resume on startup. Tests drive `ScenarioEngine.process()` directly with a `ManualClock`.
5. **Redis is fan-out only** (pub/sub, presence, locks, rate limits). PostgreSQL is the
   source of truth; events are published only after commit (`commit_and_publish`), and
   clients recover missed events from `/sync?since_seq=`.
6. **Deterministic degradation**: RNG seeded from `(room.seed, message_id, participant_id)`;
   explicit scenario rules take precedence over probabilities. **Replay never re-runs the
   RNG**; it reads recorded deliveries.
7. **Controlled conflicts**: variants are authored per event (no AI in simulation logic).
   Contradictions are detected deterministically by shared `fact_key` with different values.
8. **Append-only event stream** with per-room `seq` (row-locked counter on the room) and
   visibility (`ALL`, `INSTRUCTOR`, `PARTICIPANTS` + targets).
9. **Auth**: argon2 password hashes; 15-min JWT access tokens; opaque refresh tokens stored as
   SHA-256 hashes, rotated on use, family revoked on reuse. Tokens are kept in tab-scoped
   `sessionStorage` (not cookies) so instructor + three trainees can run in four tabs of one
   browser for the demo. WebSocket auth is a first-frame message, never a URL token.
10. **Scenario snapshot per room**: the template is frozen into the room at creation, so
    editing a template never changes an exercise that has run.
11. **Immutability**: once COMPLETED, engine mutators reject changes (`ROOM_NOT_RUNNING` /
    `INVALID_ROOM_STATE`); AAR regeneration and notes are audited.
12. **PDF** via reportlab (pure Python) plus a print-optimised web page.
13. **AI optional**: `AIAnalysisService` writes only `aar_reports.ai_narrative`; deterministic
    template narrative when no `ANTHROPIC_API_KEY`.

## Backend modules (`apps/api/app`)

| Module | Responsibility |
|--------|----------------|
| `core/` | settings, errors (envelope), security (JWT/argon2), Redis, rate limit, headers, text sanitising |
| `models/` | SQLAlchemy 2 models (see `docs/DATABASE.md`) |
| `schemas/` | Pydantic request/response schemas; `scenario.py` validates all scenario cross-references |
| `auth/` | auth service + FastAPI dependencies (`RoomAccess`, `RoomInstructor`, `RoomParticipant`) |
| `scenario/` | clock, engine, runner, loader, scenario library (Grey Signal) |
| `services/degradation.py` | pure `CommunicationDegradationEngine` |
| `services/delivery.py` | message creation, per-recipient deliveries, due/held release |
| `services/information_state.py` | the Digital Twin reconstruction |
| `services/metrics.py` | transparent, configurable metrics |
| `services/decision.py` | decision submission + snapshot (one transaction) |
| `services/live_state.py` | instructor / trainee read models |
| `realtime/` | WebSocket endpoint, connection manager, Redis bus, visibility rules |
| `aar/` | AAR builder, decision inspection, PDF, AI narrative |
| `analytics/` | dashboard and cross-exercise analytics |

## Request flow examples

**Scheduled message**: tick → `ScenarioEngine.process(sim)` → `fire_event` →
`DeliveryService.create_message` → degradation per recipient → `message_deliveries` rows →
audit events (`message.created`, `message.delayed`/`message.dropped`/`message.delivered`) →
commit → Redis publish → each WebSocket connection receives only events visible to it.

**Decision**: `POST /rooms/{id}/decisions/{key}/submit` → room row lock → validations →
insert decision (unique constraint) → reconstruct info state at `sim_now` → insert
`information_snapshots` → audit → close decision point if everyone answered → commit.
