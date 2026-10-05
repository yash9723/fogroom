# FOGROOM - Project Status

_Last updated: 2026-10-05 - all phases complete; final validation done_

> Resume point for development. If conversation context is lost, read this file first,
> then `docs/ARCHITECTURE.md`.

## Current phase

**COMPLETE.** All phases implemented and verified:

| Check | Result |
|-------|--------|
| Backend pytest | **57 passed** (real Postgres `fogroom_test` + Redis DB 15) |
| Ruff / ruff format / mypy | clean / 80 files formatted / no issues in 70 files |
| Web ESLint / tsc | clean / clean |
| Web Vitest | **17 passed** (5 files) |
| `next build` | success, 17 routes |
| Playwright E2E (dev server) | **1 passed** - full Definition-of-Done flow, 4 browser contexts |
| Playwright E2E (Docker prod build, :3001/:8011) | **1 passed** |
| `docker compose up --build` | postgres, redis, api, web all **healthy**; `/health` db ok + redis ok |
| Manual browser walkthrough | verified (below) |

Known limitations:
- Vitest workers can time out on startup if the machine is heavily loaded (e.g. running at the
  same time as pytest + Docker builds); re-run or run alone. Uses `pool: threads`, 2 workers.
- Port 8000 is used by another local project on this machine; use `API_HOST_PORT`/`API_PORT`.
- Tokens in tab-scoped sessionStorage (demo trade-off; see README security notes).
- AI narrative needs `ANTHROPIC_API_KEY` + `pip install -e '.[ai]'`; template otherwise.

## Browser verification (2026-10-05, API on :8010 because :8000 is taken by another
local project's container `bitflow_20-main-api-1` - do NOT stop it)

Verified with 4 tabs (instructor + Alpha/Bravo/Charlie via `/demo?persona=..&code=..`):
- Landing, demo login, instructor dashboard, Launch Demo Exercise -> lobby with code `GREY-31`.
- 3 trainees joined; lobby updated in real time (CONNECTED presence, auto-assigned roles).
- Start -> live console (clock, LIVE socket, participants with live metrics, timeline, controls).
- Fast-forward T+01:00: Alpha got "Bridge Orion inspection", Bravo/Charlie did not (real-time push).
- T+03:00: Bravo has A (late) + B (conflict); Alpha has A only; Charlie has neither; comm health 72%.
- Decision at T+05:00 submitted through the trainee UI (Bravo) + API (Alpha/Charlie), all different.
- Instructor Degrade on Medical Net -> DEGRADED; End exercise -> "History is now immutable".
- AAR generated (summary, template narrative, metrics, recommendations); Replay at T+03:30:
  Truth matrix (M102 DROPPED for CHARLIE, M104 only BRAVO), Alpha view belief "operational"
  flagged inaccurate, Bravo view shows contradiction M102 vs M104. Decision inspector opens.
- Local dev override: `apps/web/.env.local` points web at :8010; `API_PORT=8010 ./scripts/dev.ps1 dev-api`.

## Completed

| Area | Status | Notes |
|------|--------|-------|
| Repo / infra | ✅ | pnpm workspace, docker-compose (Postgres 16, Redis 7, api, web), `.env.example`, Makefile + `scripts/dev.ps1` |
| Database | ✅ | 24 tables, Alembic migration `0001` (CHECK constraints, partial unique index, FK indexes) |
| Auth | ✅ | argon2 hashing, 15-min JWT access tokens, rotating hashed refresh tokens with reuse detection, RBAC deps, login rate limit (Redis), demo-login (DEMO_MODE only) |
| Scenarios | ✅ | CRUD, duplicate, validation of all cross-references, Operation Grey Signal seeded |
| Rooms / lobby | ✅ | room codes (`GREY-42`), idempotent join, role auto-assign/swap, remove, ready |
| ScenarioEngine | ✅ | anchored sim clock (pause/resume/time-scale/fast-forward), event stream, phases, decision points (TIME / MANUAL / AFTER_DECISION), metric snapshots every 30 sim-s |
| Degradation engine | ✅ | per-recipient deterministic evaluation: drop / delay / variant / reroute / hold; disruptions DELAY, DROPOUT (drop-next), CHANNEL_FAILURE, RELIABILITY_REDUCTION, CONFLICT_INJECTION, BLACKOUT |
| Delayed delivery | ✅ | server-side, persisted in sim-time, released by the tick loop (survives reconnect / restart) |
| Information-State Digital Twin | ✅ | `InformationStateService.reconstruct(room, participant or truth, t)` + instructor-only endpoints |
| Decisions | ✅ | validation, deadlines, unique constraint, information snapshot in the same transaction |
| WebSockets | ✅ | `/ws/rooms/{id}`, first-frame auth, Redis pub/sub fan-out, per-viewer filtering, presence, `/sync?since_seq` |
| AAR | ✅ | report builder, decision inspection, objectives mapping, recommendations, PDF export (reportlab), template narrative + optional Claude narrative |
| Analytics | ✅ | dashboard, cross-exercise overview, room metric series |
| Frontend foundation | ✅ | Next 16 / React 19 / Tailwind 4 tokens, API client w/ refresh, tab-scoped auth store, zod-validated WS client w/ reconnect + `/sync` replay, shadcn-style UI primitives |
| Frontend: auth + landing | ✅ | landing w/ login + demo personas, /login, /register, /demo launcher (new-tab personas) |
| Frontend: instructor | ✅ | dashboard, exercises, lobby, live console, scenarios list + structured editor, AAR (overview, replay w/ Truth/per-trainee views, decision inspector, filtered timeline, comms analysis + charts, PDF export, print view), analytics (Recharts), settings (presentation mode, admin user management) |
| Frontend: trainee | ✅ | join, live dashboard (top bar, map, info feed w/ ack, decisions w/ confidence+rationale, comms, team chat), messages, decision log, team, profile |
| Frontend tests | ✅ | Vitest: login form, room join, decision form, instructor controls, timeline/event feed |
| E2E (Playwright) | ✅ | `apps/web/tests/e2e/demo-flow.spec.ts` |
| Docker | ✅ | configurable host ports, `.dockerignore`s, pinned `requirements.lock`, health checks |
| Docs | ✅ | README + docs/{ARCHITECTURE,DATABASE,SCENARIO_ENGINE,WEBSOCKETS,AAR,DEPLOYMENT,DEMO_SCRIPT} |

## Architecture (short)

See `docs/ARCHITECTURE.md`. Key point: the **global truth** (messages, facts timeline) is
kept strictly separate from each **participant's information state** (`message_deliveries`).
Trainee read models are built only from that participant's deliveries.

## Commands

```bash
docker compose up -d postgres redis          # dependencies
./scripts/dev.ps1 setup                      # Windows (or: make setup)
./scripts/dev.ps1 dev-api                    # API on http://localhost:8000 (docs: /docs)
./scripts/dev.ps1 test-api                   # backend tests
./scripts/dev.ps1 lint                       # ruff + mypy (+ web lint once frontend exists)
```

## Test status

- Backend: **57 passed** (`pytest`): degradation, metrics, clock, auth, RBAC/authorization,
  scenarios, full simulation integration flow, pause semantics, blackout, team comms,
  WebSocket auth and filtered fan-out.
- Ruff: clean. Ruff format: clean. Mypy: no issues (70 files).

## Known issues / decisions to remember

- GateGuard hook (user's ECC plugin) gates first write of every new file; facts are
  stated per batch. The user may set `GATEGUARD_EXEMPT_GLOBS` to speed this up.
- FastAPI 0.142 nests included routers (`app.routes` shows `_IncludedRouter`); OpenAPI has
  all 52 paths.
- Response time is measured in simulation time (`response_time_ms`).

## Next exact tasks

### Render deployment (user: "ditch cloudfare, just deploy to render")
DONE in code: one Docker web service (`Dockerfile.render`: FastAPI + static-exported Next
frontend, same origin) + Render Postgres + Render Key Value, described by `render.yaml`.
Dynamic routes became query routes (`/exercises/room?id=`, `/exercise/room?id=`,
`/aar/report?id=`, `/aar/print?id=`, `/scenarios/edit?id=`) via `lib/routes.ts`.
Verified 2026-10-05: image built and run locally (:8012, `postgres://` URL, PORT=10000) ->
/health ok, Playwright E2E passed against it; pytest 57, vitest 17, ruff/mypy/eslint/tsc clean.
LIVE: https://fogroom.onrender.com (Render service srv-db1tbarncjis73c99ee0, Oregon, free; Postgres
fogroom-db expires 2026-11-04). Live E2E passed 2026-10-05. Redeploy: push to main (autoDeploy).
Blueprint: https://render.com/deploy?repo=https://github.com/yash9723/fogroom
(or via the Render connector). Free web services sleep when idle; free Postgres expires
after 30 days.

Optional future work: AI scenario drafting, map editor for locations,
instructor-tunable metric weights in the UI, httpOnly-cookie auth for production.
