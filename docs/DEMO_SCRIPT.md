# SIH demo script (5-7 minutes)

**Setup (before judges arrive):** stack running, browser at the landing page, projector on.
Optional: append `?presentation=true` for larger text. Four tabs will be used: instructor +
Alpha + Bravo + Charlie.

| Time | Action | Talking point |
|------|--------|---------------|
| 0:00 | Landing page | "Teams rarely fail for lack of a decision - they fail because information arrives late, incomplete or contradictory. FOGROOM trains exactly that." |
| 0:30 | **Instructor** demo sign-in → **Launch Demo Exercise** | Operation Grey Signal - a fictional cyclone-response cell across Orion and Delta islands. |
| 0:50 | Lobby: room code `GREY-xx` → **Open Alpha / Bravo / Charlie Demo** | Three trainees join; roles assigned automatically; presence updates live. |
| 1:15 | **Start exercise** | Server-side simulation clock; everyone receives the briefing. |
| 1:30 | **Next: Bridge Orion inspection** (fast-forward) | Show the three trainee tabs: **Alpha has the bridge report, Bravo doesn't yet, Charlie never will.** Same server truth, three different information states. |
| 2:15 | **Next** ×2 (Command degrades, T+03:00) | Bravo now holds two contradictory reports (operational vs unusable, MEDIUM vs HIGH source). Alpha still believes the bridge is fine. Comm health drops to 72 %. |
| 2:45 | Controls: **Degrade** Medical Net; **Disrupt → Drop next message** for Charlie; **Inject conflict** to Alpha | Every degradation is per recipient, deterministic and audited. |
| 3:15 | **Next** to T+05:00 - decision point | Each trainee decides with confidence and rationale (Alpha: ground convoy 85 %, Bravo: boat 55 %, Charlie: hold 35 %). |
| 3:45 | **Restore** channels → **End exercise** | History is now immutable. |
| 4:00 | **Generate AAR** | Summary, team metrics, participant comparison - experimental, fully explained formulas. |
| 4:30 | **Replay** tab: slider to ~T+03:30, toggle **Global Truth → ALPHA → BRAVO** | Truth: who received what (M102 dropped for Charlie). Alpha's belief flagged wrong; Bravo shows the contradiction. |
| 5:15 | **Decisions → Inspect** Alpha | Available / missing / delayed / conflicting information, confidence, rationale, response time, uncertainty score. "Alpha wasn't careless - the decisive report was still in flight." |
| 6:00 | **Export PDF** | Downloadable report for the debrief. |
| 6:20 | Close | "**FOGROOM evaluates not just what decision was made, but what information was available when that decision was made.**" |

## Backup plan

- If Wi-Fi is down: everything runs locally (map is a bundled SVG, no external tiles).
- If a tab disconnects: it reconnects automatically and replays missed events.
- The full flow is also covered by the Playwright test `apps/web/tests/e2e/demo-flow.spec.ts`.
