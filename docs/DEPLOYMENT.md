# Deployment

## Docker Compose (single host)

```bash
cp .env.example .env            # set JWT_SECRET; review DEMO_MODE
docker compose up -d --build    # postgres, redis, api, web (with health checks)
docker compose ps
docker compose logs -f api
```

The `api` container runs `alembic upgrade head` and (with `RUN_SEED=true`) the idempotent seed
before starting uvicorn. Service dependencies use health checks: api waits for healthy
postgres + redis; web waits for a healthy api.

Port overrides (useful when 8000/3000 are taken):

```bash
API_HOST_PORT=8011 WEB_HOST_PORT=3001 \
NEXT_PUBLIC_API_URL=http://localhost:8011 NEXT_PUBLIC_WS_URL=ws://localhost:8011 \
CORS_ORIGINS=http://localhost:3001 docker compose up -d --build
```

`NEXT_PUBLIC_*` values are baked into the web bundle at build time - rebuild `web` after
changing them. The API image installs exact versions from `apps/api/requirements.lock`.

## Production checklist

- `APP_ENV=production` (the API refuses the default JWT secret and `DEMO_MODE=true`)
- Strong `JWT_SECRET` (`python -c "import secrets; print(secrets.token_urlsafe(48))"`)
- `DEMO_MODE=false`, `NEXT_PUBLIC_DEMO_MODE=false`, `RUN_SEED=false` (seed users manually)
- Managed PostgreSQL + Redis; set `DATABASE_URL`, `REDIS_URL`
- TLS-terminating reverse proxy; `NEXT_PUBLIC_API_URL=https://…`, `NEXT_PUBLIC_WS_URL=wss://…`
  (proxy must forward WebSocket upgrades for `/ws/`)
- `CORS_ORIGINS` = the web origin only
- Multiple API workers are supported: engine loops are coordinated by Redis locks and events
  fan out over Redis pub/sub
- Back up PostgreSQL - it is the single source of truth for every replay

## Migrations

```bash
cd apps/api
python -m alembic upgrade head          # apply
python -m alembic downgrade -1          # roll back one revision
python -m alembic revision --autogenerate -m "describe change"   # new migration (review it!)
```
