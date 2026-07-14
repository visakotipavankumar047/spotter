# Scope: ELD Trip Planner & Daily Log Generator

A full stack trucking compliance tool. A dispatcher enters a trip's current location, pickup, dropoff, and current cycle hours used, and the app returns a route map and a set of FMCSA compliant daily log sheets for the trip.

**Build approach:** Tracer Bullet (prove the whole pipe, form through HOS engine through log sheet through map, works end to end on a simple trip first, then thicken each segment).
**Weight profile:** the HOS engine slices are full weight (compliance correctness is the actual grading focus); most other rows are lean or medium.

## At a glance

| # | Feature | Phase | Status |
|---|---------|-------|--------|
| 1 | Stack & architecture (Django backend scaffold) | Foundation | in-progress |
| 2 | Docker single port topology | Foundation | planned |
| 3 | Coding standards & tooling | Foundation | planned |
| 4 | Data model (Trip, DailyLog, DutySegment) | Foundation | planned |
| 5 | Design system: Dispatch Console tokens | Foundation | planned |
| 6 | Core trip loop (short trip, end to end) | Slice 1 | planned |
| 7 | Multi day trips (daily log splitting) | Slice 2 | planned |
| 8 | Long trip compliance (34 hour restart, fuel stops, breaks) | Slice 3 | planned |
| 9 | Dispatch Console visual polish & motion | Slice 4 | planned |
| 10 | Trip reload by id | Slice 5 | planned |
| 11 | Submission deliverables (README, assumptions) | Slice 6 | planned |
| 12 | Live deployment (Railway/Render) | Deferred | planned |

## Foundations

### 1. Stack & architecture (Django backend scaffold) · in-progress
The stack is fixed by `ELD_TRIP_PLANNER_PROMPT.md` §1 (Next.js frontend already scaffolded, Django + DRF backend, SQLite3). This feature scaffolds the Django project and `trips` app per the repo layout in §2 so later slices build on real structure.
**Done when:** `backend/` boots locally (`manage.py runserver`), has the `config/` and `trips/` layout from §2, and `manage.py migrate` runs clean.
- [x] Design it (spec): `/architect stack & architecture`
- [ ] Scaffold from the decision: `/develop stack & architecture`
- [ ] Smoke check it runs: `/test`
Spec [0001](../specs/0001-stack-architecture.md) · code (filled by /develop)

### 2. Docker single port topology
`docker-compose.yml` with exactly two services (`frontend` publishing the only host port, `backend` internal only via `expose`), the Next.js `/api/*` rewrite, and a named volume for `db.sqlite3`, per §7. Fully dictated by the prompt doc, no decision to make.
**Done when:** `docker-compose up --build` serves the whole app at `http://localhost:3000`; the backend has no published port; `/api/*` calls resolve through the rewrite with no CORS config.
- [ ] Build it: `/develop docker single port topology`

### 3. Coding standards & tooling
Capture conventions and tooling choices from the real scaffolded project (Python/Django side, since the frontend side is already captured in root `AGENTS.md`), then install lint/format/pre-commit.
**Done when:** root `AGENTS.md` reflects the real backend stack, and lint/format run clean on both `frontend/` and `backend/`.
- [ ] Capture conventions + tooling choices: `/audit`
- [ ] Install the tooling: `/develop tooling`

### 4. Data model (Trip, DailyLog, DutySegment)
Core entities every slice builds on: `Trip`, `DailyLog`, `DutySegment`, their relationships, and the DRF serializers matching the API contract in §4.
**Done when:** migrations apply clean; a `Trip` can be created with nested `DailyLog`/`DutySegment` records and serialized to the exact response shape in §4.
- [ ] Design it (spec): `/architect data model`

### 5. Design system: Dispatch Console tokens
The palette, type, and layout direction in §6 ("Dispatch Console") are fully specified already. This feature wires them into the Tailwind/shadcn theme (CSS variables, fonts, the paper log color break, base component restyle) so every later screen inherits it instead of shadcn zinc defaults.
**Done when:** the CSS variables in §6 are the live theme (not defaults), Space Grotesk/Inter/IBM Plex Mono are loaded and applied by role, and base shadcn components (`Card`, `Input`, `Button`) reflect the Steel Panel/Signal Amber styling.
- [ ] Design it (spec): `/architect design system: dispatch console tokens`

## Slice 1: Core trip loop

### 6. Core trip loop (short trip, end to end)
The walking skeleton: trip input form (with geocode autocomplete) submits a short (<1 day) trip through `POST /api/trips/`, the backend geocodes locations, calls OSRM for the two legs, runs `hos_engine.build_duty_timeline` and `log_builder` for the simple case (no restart, no fuel split needed), and the results page renders the stat strip, the map with route + pickup/dropoff stops, and one FMCSA log sheet card. Real DB, real API, real UI; only breadth (multi day, restarts, fuel stops, polish) is deferred to later slices.
**Done when:** submitting a short trip (e.g. Indianapolis, IN -> Louisville, KY) returns a saved `Trip` and renders a working map plus one accurate daily log sheet whose four totals sum to 24 hours.
- [ ] Design it (spec): `/architect core trip loop`

## Slice 2: Multi day trips

### 7. Multi day trips (daily log splitting)
Extend `log_builder.py` to slice the duty segment list at each local midnight into one `DailyLog` per calendar day (padding leading/trailing edges with `OFF_DUTY`), and the results page to stack multiple log sheet cards, most recent day last.
**Done when:** a 2 to 3 day trip renders one correctly totaled log sheet card per day, in order.
- [ ] Build it: `/develop multi day trips`

## Slice 3: Long trip compliance

### 8. Long trip compliance (34 hour restart, fuel stops, breaks) · full
The full correctness of the rules engine: 30 minute break after 8 cumulative driving hours, 10 hour off duty resets, mandatory 34 hour restart insertion when continuing would exceed the 70 hour/8 day cycle, and a fuel stop every 1,000 driven miles. Includes the ground truth fixtures from §3.2 (rolling 8 day total; Richmond -> Newark worked example).
**Done when:** `test_hos_engine.py` passes both §3.2 fixtures; a 5+ day trip forces a visible 34 hour restart segment; fuel stops appear at least once per 1,000 driven miles; every daily log's four totals still sum to exactly 24 hours.
- [ ] Build it: `/develop long trip compliance`

## Slice 4: Dispatch Console visual polish & motion

### 9. Dispatch Console visual polish & motion
Apply the remaining §6 direction beyond static tokens: the split view input screen with the idle oscilloscope style trace preview, the SVG step line draw in animation on the log sheet (`stroke-dashoffset`), the same subtler treatment on the route polyline, `prefers-reduced-motion` handling, and visible keyboard focus throughout.
**Done when:** the input screen shows the animated idle trace, log sheets draw in on load, motion respects `prefers-reduced-motion`, and keyboard focus is visible on every interactive element.
- [ ] Build it: `/develop dispatch console visual polish`

## Slice 5: Trip reload

### 10. Trip reload by id
`GET /api/trips/{id}/` returns the same response shape as creation, and `/trip/[id]` renders it directly on load (not just right after submission), so a saved trip's URL is shareable/reloadable.
**Done when:** navigating directly to `/trip/[id]` for a previously created trip renders the same map and log sheets as the original submission, with no re-submission.
- [ ] Build it: `/develop trip reload by id`

## Slice 6: Submission deliverables

### 11. Submission deliverables (README, assumptions)
README with local `docker-compose up` instructions and a short assumptions section matching §3 (property carrying driver, 70 hour/8 day cycle, no adverse driving conditions exception, no sleeper berth splitting). The Loom walkthrough and the public GitHub repo/live URL steps in §8 are manual and stay with you.
**Done when:** README covers setup, assumptions, and matches the acceptance checklist in §8 for everything except the video and the deployed URL.
- [ ] Build it: `/document readme`

## Deferred
Out of scope for the current build pass, kept so the plan stays honest.
- **Live deployment (Railway/Render)**: publishing the docker-compose stack to a host and wiring the one public URL · needs a decision when picked back up

## Legend

**The decision box.** Every feature carries exactly one, the sub-task whose label ends with `(spec)`. Every other box is an execution box and `/architect` never ticks one.

**Feature lifecycle**: the scope updates as a feature moves; each row is what it shows and who sets it:

| State | Set by | The feature shows |
|---|---|---|
| `planned` · needs a decision | `/scope` | one box: `Design it (spec): /architect <feature>` |
| `in-progress` (designed) | **`/architect` at spec capture** | `Design it` ticked; spec linked; `Build it: /develop <feature>` + **2 to 5 milestones rolled up from the spec**; `Verify it` + `Test it` boxes; any surfaced follow-up enrolled |
| `in-progress` (building) | `/develop` | milestone sub-boxes tick one by one; code pointer filled |
| `in-progress` (verified) | `/check verify` | `Build it` + milestones ticked; `Verify it` ticked |
| `done` | `/test`, then `/sync` | all boxes ticked; `/sync` captures the slice's conventions into `AGENTS.md` |

- **Next step** = the first unticked box (always a command or a tracked milestone).
- **needs a decision** = run `/architect` first; otherwise straight to `/develop` (or `/audit` for standards & tooling). The tag drops once the spec is captured.
- **Atomic build tasks live in the spec's `## Build plan`, not here**: the scope carries only the milestone rollup.
- **Status** `planned` → `in-progress` → `done`, plus `existing` (pre-workflow) and `dropped` (de-scoped, kept for history).
- **Approach tag** beside a heading (e.g. `· Facade`) overrides the project default for that feature; no tag = inherits it.
- **Weight tag** `· full` = a fresh-model `/check review` warranted; `lean`/`medium` get no tag.
- **Pointer line** (`spec <n> · code in <path>`): the spec link added by `/architect`, the code path by `/develop`.
