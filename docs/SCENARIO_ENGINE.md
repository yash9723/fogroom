# Scenario engine & communication degradation

Code: `apps/api/app/scenario/{clock,engine,runner}.py`, `app/services/{degradation,delivery}.py`.

## Simulation clock

```
running:  sim_now = sim_anchor_seconds + (wall_now - anchor_at) × time_scale
paused:   sim_now = sim_anchor_seconds          (anchor_at = NULL)
ended:    sim_now = final_sim_seconds
```

`pause` folds elapsed time into the anchor; `resume` sets a new `anchor_at` and adds to
`total_pause_seconds`. Every schedule (event offsets, decision windows, delayed deliveries) is
stored in **simulation seconds**, so nothing is delivered while paused and time scaling works
without special cases. **Fast-forward** (`POST /rooms/{id}/clock/advance`) steps through every
scheduled moment in order, producing the same history as if the time had elapsed.

## Tick loop

`EngineRunner` keeps one asyncio task per running room (1 s cadence). A Redis lock
(`SET NX PX 5000`) ensures a single worker ticks a room. Each tick, in one transaction with the
room row locked, `ScenarioEngine.process(room, sim)`:

1. updates the phase; ends disruptions whose planned end passed;
2. fires TIME events due (`scheduled_offset_seconds <= sim`, not yet fired);
3. opens TIME decision points; closes those past their deadline (`decision.missed` logged);
4. fires AFTER_DECISION events / decision points whose trigger point closed;
5. releases held deliveries whose path is restored; delivers due deliveries;
6. every 30 sim-seconds records metric snapshots (digital twin metrics per participant + team).

On API start, loops resume for all RUNNING/PAUSED rooms - delayed messages survive restarts.

## Event types

| Template event | Effect |
|----------------|--------|
| BRIEFING / INFORMATION / WEATHER / REQUEST / NOTICE | creates a message for recipients |
| CHANNEL_CHANGE | sets channel status/reliability/latency (+ optional system notice) |
| DISRUPTION | starts a disruption with optional duration (+ optional notice) |

Instructor actions: fire a template event now, custom events, notices, conflict injection,
channel degrade/disable/restore/reliability, disruptions, open decision points, fast-forward,
pause/resume/end, notes. Every action writes an audit event.

## CommunicationDegradationEngine

Pure function evaluated **independently per recipient**, with an RNG seeded from
`(room.seed, message_id, participant_id)` - deterministic and auditable. Order:

1. Scenario override for the recipient's role: `drop`, `delay N`, `variant K`, `deliver`.
2. DROPOUT disruptions (drop-next counters, drop probability).
3. Probabilistic loss (only without an override):
   `p = drop_probability + (1 − path_reliability) × channel_loss_factor`.
4. Conflicting variant: override, CONFLICT_INJECTION disruption, or `conflict_probability`.
5. Channel availability: BLACKOUT → held; channel OFFLINE → reroute via fallback channel if
   available, else held until a path is restored.
6. Delay = channel latency + override delay + DELAY disruptions + random jitter
   (`delay_probability`, `jitter_seconds`).

Result → one `message_deliveries` row: DELIVERED/ALTERED (immediate), DELAYED (scheduled
or held), DROPPED. Reasons are stored in `transformation_metadata.reasons` and shown in the AAR.
Anything still in flight when the exercise ends becomes FAILED (never delivered).

Difficulty defaults (overridable per scenario and per event):

| Difficulty | delay p | drop p | conflict p | jitter s | channel loss |
|------------|---------|--------|------------|----------|--------------|
| BEGINNER | 0.10 | 0.02 | 0.00 | 10 | 0.10 |
| INTERMEDIATE | 0.25 | 0.05 | 0.05 | 20 | 0.25 |
| ADVANCED | 0.40 | 0.10 | 0.10 | 40 | 0.40 |

## Conflicts & contradictions

Designers author controlled `variants` (`fact_value`, content, source, reliability) - no
generative AI in simulation logic. Messages carry `fact_key`/`fact_value`; a participant
"knows a contradiction" when they have received two values for the same `fact_key`.

## Operation Grey Signal (seeded, fictional)

| Time | Event | Information state design |
|------|-------|--------------------------|
| T+00 | Initial briefing | everyone |
| T+01 | Bridge Orion operational (Message A) | Alpha on time, Bravo +100 s, Charlie dropped |
| T+02 | Command Net degrades | latency 12 s, reliability 0.65 |
| T+03 | Bridge Orion unusable (Message B) | Bravo on time (contradiction), Charlie +240 s, Alpha +480 s |
| T+04 | Echo Relay congestion | DELAY +60 s for 300 s |
| T+05 | Medevac request + **decision 1** | medevac method |
| T+06 | Weather warning North Ridge | Charlie +300 s |
| T+07 | Infrastructure roll-up | Alpha receives the conflicting "pier destroyed" variant |
| T+08 | **Decision 2** | primary supply route |
| T+10 | Command Net offline | traffic held / rerouted |
| T+10:30 | **Decision 3** (Charlie) | comms recovery priority |
| T+11 | Relief stock report | held until Backup HF returns |
| T+12 | Backup HF restored | held traffic released |
| T+13-14:30 | Station Echo power, weather clearing, Command restored | |
| T+15 | **Decision 4** | final allocation |

Ground truth: the bridge collapsed at T+02:30; the Harbor Delta pier stayed operational.
