# Real-time protocol

Endpoint: `ws://<api>/ws/rooms/{room_id}` (`apps/api/app/realtime/ws.py`).
Client: `apps/web/lib/ws.ts` + `hooks/use-room-socket.ts`. Frames validated with zod
(`packages/shared/src/index.ts`).

## Handshake

```
client → {"type": "auth", "token": "<access JWT>"}          first frame, within 10 s
server → {"type": "hello", "room_id", "last_seq", "room_status", "viewer", "participant_id"}
server → {"type": "event", "event": {seq, event_type, sim_time, timestamp, visibility, payload}}
client → {"type": "ping"}      server → {"type": "pong", "server_time"}
```

Tokens never appear in URLs (so never in access logs). Close codes: `4401` unauthenticated,
`4403` not a member of the room.

## Fan-out and filtering

1. A service writes `audit_events` rows (per-room `seq`, `visibility`, targets) in its DB
   transaction.
2. After commit, `commit_and_publish` publishes the events to Redis channel `room:{id}`.
3. Every API worker subscribes to `room:*` and dispatches to its local connections, applying
   `realtime/visibility.py`:
   - instructor (room owner or admin): everything;
   - trainee: `ALL` events and `PARTICIPANTS` events that name them; `targets` and actor
     metadata are stripped. Message creation, drops, delays and truth payloads are
     instructor-only - a trainee only ever sees `message.delivered` for their own deliveries.

## Event types

`participant.joined/left/updated/ready`, `presence.updated`, `simulation.started/paused/resumed/
completed`, `clock.advanced`, `phase.changed`, `scenario.event`, `message.created`,
`message.delivered` (trainee-safe view), `delivery.completed`, `message.delayed`,
`message.dropped`, `message.held`, `message.released`, `message.failed`, `message.acknowledged`,
`channel.updated`, `comms.changed`, `disruption.started/ended`, `conflict.injected`,
`decision.requested/submitted/acknowledged/closed/missed`, `team.message`,
`team.message_failed`, `note.created`, `metrics.updated`, `aar.generated`.

## Presence & reconnect

- Presence: Redis hash `fogroom:presence:{room}` counts connections per participant; the
  participant row flips CONNECTED/DISCONNECTED (shielded cleanup survives task cancellation).
- Reconnect: exponential backoff (0.5 s → 15 s). After every `hello`, the client calls
  `GET /api/v1/rooms/{id}/sync?since_seq=<last seen>` (same visibility rules) and refetches its
  read model. PostgreSQL is the source of truth; WebSocket events only trigger refetches.
