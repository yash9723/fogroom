# FOGROOM

**Decision Training Under Information Uncertainty** - Smart India Hackathon problem statement **SIH26248**.

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/yash9723/fogroom) (see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md#render-one-click))

FOGROOM is a multiplayer, web-based decision-training simulation. An instructor runs a live
exercise for a team of trainees while deliberately degrading communications - delaying,
dropping, rerouting and contradicting information per recipient. Afterwards the After Action
Review (AAR) replays **exactly what each trainee knew at every moment** next to the global truth.

> *FOGROOM evaluates not just what decision was made, but what information was available when
> that decision was made.*

All scenarios, places and organisations are **fictional** (the seeded scenario is a disaster-
response exercise). Scores are **experimental training metrics**, not validated measures.

---

## Key idea: the Information-State Digital Twin

The server keeps the **global truth** (canonical messages, ground-truth facts over time) and,
separately, one `message_deliveries` row per message × recipient recording what *that*
participant experienced (delivered / delayed / dropped / altered / held / failed, when, through
which channel). `InformationStateService.reconstruct(room, participant, t)` rebuilds any
participant's knowledge at any simulation time - received, in flight, dropped, never addressed,
channel availability, known contradictions, beliefs vs ground truth and an uncertainty index.
Trainee views are built only from their own deliveries, so the server never leaks what it knows.

## Features

- Real auth (argon2, 15-min JWT + rotating refresh tokens with reuse detection, RBAC: ADMIN /
  INSTRUCTOR / TRAINEE, login rate limiting) and one-click demo personas (DEMO_MODE only)
- Scenario templates with a structured editor (roles, channels + fallbacks, phases, timed /
  manual / after-decision events, controlled conflicting variants, decision points, difficulty
  defaults with overrides); seeded **Operation Grey Signal**
- Lobby with room codes (`GREY-42`), role assignment, presence, single-laptop demo tabs
- `ScenarioEngine`: anchored simulation clock (pause / resume / time-scale / fast-forward),
  append-only event stream, phases, decision points, metric snapshots
- `CommunicationDegradationEngine`: deterministic per-recipient delay / drop / variant / reroute
  / hold; disruptions DELAY, DROPOUT (drop next), CHANNEL_FAILURE, RELIABILITY_REDUCTION,
  CONFLICT_INJECTION, BLACKOUT; server-side delayed delivery persisted in PostgreSQL
- Live instructor console: clock, participants with live uncertainty metrics, 2D communication
  graph, scenario timeline (fire now / fast-forward), filtered event feed, channel controls,
  disruptions, conflict injection, custom events, notices, timestamped notes, recent decisions
- Trainee dashboard: fictional map (Leaflet, offline SVG), information feed (source, priority,
  reported reliability, channel, report age), acknowledgements, decisions with confidence slider
  and rationale, communication status, team chat that fails over offline channels
- WebSockets with first-frame auth, Redis pub/sub fan-out, per-viewer filtering, reconnect +
  `/sync` replay of missed events
- AAR: summary + narrative (template, or Claude if `ANTHROPIC_API_KEY` is set), team metrics,
  participant comparison, **replay slider with Global Truth / per-trainee views**, decision
  inspection (available / missing / delayed / conflicting information), filtered timeline,
  disruption timeline, comm graph, objectives, recommendations, instructor notes, **PDF export**
  and print view; analytics across exercises; presentation mode (`?presentation=true`)

## Tech stack

| Layer | Stack |
|-------|-------|
| Web | Next.js 16 (App Router), React 19, TypeScript, Tailwind CSS 4, shadcn-style Radix components, Lucide, TanStack Query, Zustand, Recharts, react-leaflet, Zod, sonner |
| API | Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 (async, asyncpg), Alembic, Redis, reportlab |
| Data | PostgreSQL 16 (source of truth), Redis 7 (pub/sub, presence, engine locks, rate limits) |
| Tests | Pytest (+ httpx, Starlette TestClient), Vitest + React Testing Library, Playwright |
| Tooling | pnpm workspace, Ruff, mypy, ESLint, Prettier, Docker Compose |

## Quick start (local development)

Prerequisites: Docker Desktop, Python 3.12, Node 20+, pnpm 9 (`npm i -g pnpm`).

```bash
cp .env.example .env                     # review values; never commit .env
docker compose up -d postgres redis      # PostgreSQL :5432, Redis :6379
make setup                               # venv + deps + pnpm install + migrate + seed
make dev                                 # API :8000 and web :3000
```

Windows PowerShell equivalents (no make needed):

```powershell
Copy-Item .env.example .env
./scripts/dev.ps1 setup      # venv, pip install, pnpm install, docker deps, migrate, seed
./scripts/dev.ps1 dev-api    # terminal 1 - API on :8000 (set $env:API_PORT to change)
./scripts/dev.ps1 dev-web    # terminal 2 - web on :3000
```

| Service | URL |
|---------|-----|
| Web | http://localhost:3000 |
| API | http://localhost:8000 |
| API docs (OpenAPI) | http://localhost:8000/docs |
| Health | http://localhost:8000/health |

If port 8000 is taken, run the API on another port and point the web app at it with
`apps/web/.env.local` (`NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`).

### Developer commands

| Make | PowerShell | Purpose |
|------|------------|---------|
| `make setup` | `./scripts/dev.ps1 setup` | install everything, migrate, seed |
| `make dev` | `dev-api` + `dev-web` | run API + web |
| `make migrate` | `./scripts/dev.ps1 migrate` | `alembic upgrade head` |
| `make seed` | `./scripts/dev.ps1 seed` | demo users + Operation Grey Signal |
| `make reset-db` | `./scripts/dev.ps1 reset-db` | downgrade, upgrade, seed |
| `make test` | `./scripts/dev.ps1 test` | pytest + vitest |
| `make e2e` | `./scripts/dev.ps1 e2e` | Playwright (needs API running) |
| `make lint` | `./scripts/dev.ps1 lint` | ruff, ruff format --check, mypy, eslint, tsc |
| `make docker-up` / `docker-down` | same | full stack in Docker |

## Environment variables

See `.env.example`. Key ones: `DATABASE_URL`, `REDIS_URL`, `JWT_SECRET`,
`JWT_ACCESS_EXPIRATION_MINUTES`, `JWT_REFRESH_EXPIRATION_DAYS`, `CORS_ORIGINS`, `APP_ENV`,
`DEMO_MODE`, `DEMO_PASSWORD`, `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_WS_URL`,
`ANTHROPIC_API_KEY` (optional). In `APP_ENV=production` the API refuses to start with the default
JWT secret or with demo mode enabled.

## Database & seed

```bash
cd apps/api && .venv/bin/python -m alembic upgrade head   # migrations (never create_all)
.venv/bin/python -m app.seed                              # idempotent seed
```

## Demo accounts

Seeded by `make seed`; password = `DEMO_PASSWORD` from `.env` (default `FogRoom!2026`):

| Role | Email |
|------|-------|
| Instructor | instructor@fogroom.demo |
| Trainee | alpha@fogroom.demo, bravo@fogroom.demo, charlie@fogroom.demo |
| Admin | admin@fogroom.demo |

With `DEMO_MODE=true` the landing page also offers one-click demo sign-in buttons.

## Demo walkthrough (one laptop)

1. Sign in as **Instructor** → **Launch Demo Exercise** → note the room code.
2. Click **Open Alpha / Bravo / Charlie Demo** (each opens a separate session tab).
3. **Start exercise**; use **Next: …** (fast-forward) to step through the timeline.
4. Watch Alpha receive the bridge report, Bravo receive it late plus a contradiction, Charlie
   never receive it. Degrade/disable channels, inject conflicts, start a blackout.
5. Trainees decide with confidence + rationale → **End exercise** → **Generate AAR**.
6. **Replay**: scrub the slider, switch Global Truth ↔ ALPHA ↔ BRAVO; **Decisions → Inspect**.
7. **Export PDF**. Full script: [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md).

## Testing

```bash
make test-api     # 57 pytest tests: degradation, metrics, clock, auth, RBAC, scenarios,
                  # full simulation flow, pause semantics, blackout, team comms, WebSockets
make test-web     # 17 Vitest tests: login form, room join, decision form, instructor
                  # controls, timeline rendering
make e2e          # Playwright: instructor + 3 trainees, full Definition-of-Done flow
```

Backend tests run against a real PostgreSQL database `fogroom_test` (created by
`infra/docker/postgres/init.sql`) and Redis DB 15.

## Docker

```bash
docker compose up -d --build     # postgres, redis, api (migrates + seeds), web
```

Host ports are configurable: `API_HOST_PORT`, `WEB_HOST_PORT`, `POSTGRES_HOST_PORT`,
`REDIS_HOST_PORT` (set `NEXT_PUBLIC_API_URL`/`NEXT_PUBLIC_WS_URL`/`CORS_ORIGINS` to match).
See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Folder structure

```
fogroom/
  apps/
    api/               FastAPI app (app/{core,db,models,schemas,auth,api/v1,scenario,
                       services,realtime,aar,analytics}), migrations/, tests/
    web/               Next.js app (app/, components/, features/, hooks/, lib/, tests/)
  packages/shared/     WebSocket frame types + zod schemas shared with the web app
  infra/docker/        Postgres init script
  scripts/dev.ps1      Windows task runner (mirrors the Makefile)
  docs/                ARCHITECTURE, DATABASE, SCENARIO_ENGINE, WEBSOCKETS, AAR,
                       DEPLOYMENT, DEMO_SCRIPT
  docker-compose.yml   .env.example   Makefile   PROJECT_STATUS.md
```

## Documentation

[Architecture](docs/ARCHITECTURE.md) · [Database](docs/DATABASE.md) ·
[Scenario engine](docs/SCENARIO_ENGINE.md) · [WebSockets](docs/WEBSOCKETS.md) ·
[AAR & metrics](docs/AAR.md) · [Deployment](docs/DEPLOYMENT.md) · [Demo script](docs/DEMO_SCRIPT.md)

## Security notes

- Passwords hashed with argon2; refresh tokens stored only as SHA-256 hashes, rotated on use,
  token family revoked on reuse; login rate limiting (Redis fixed window).
- Every permission is enforced server-side (`RoomAccess` dependencies); trainees can only read
  their own deliveries and never global truth, other participants' states or the event stream
  beyond events addressed to them. Covered by `tests/test_authorization.py`.
- ORM-only queries (no string SQL), Pydantic validation with `extra="forbid"`, control
  characters stripped from user text, React escapes output, PDF output escapes markup.
- Security headers on API and web; CORS restricted to configured origins; WebSocket tokens are
  sent in the first frame, never in URLs; tokens and passwords are never logged.
- Tokens live in tab-scoped `sessionStorage` (deliberate trade-off enabling four sessions on
  one laptop for demos; for production consider httpOnly cookies + CSRF protection).

## Future work

- AI-assisted scenario drafting (behind the existing `AIAnalysisService` abstraction)
- Multi-room analytics cohorts, instructor-defined metric weights in the UI
- Map editor for scenario locations; richer channel topologies (relays, bandwidth)
- Horizontal scaling hardening (already supported: Redis-locked engine loops, pub/sub fan-out)
