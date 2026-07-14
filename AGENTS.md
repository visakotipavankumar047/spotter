# AGENTS.md — ELD Trip Planner

This file is auto-discovered by Devin Desktop (formerly Windsurf — Cascade now reads AGENTS.md as an always-on root rule) and is also compatible with Claude Code, Cursor, and Codex CLI. It's the operating contract for any agent working in this repo. For the exhaustive build spec (HOS algorithm, API contract, design tokens, Docker topology) see `ELD_TRIP_PLANNER_PROMPT.md` at repo root — that file is the source of truth for *what* to build; this file is the source of truth for *how to behave* while building it.

---

## Role

You are a senior full-stack engineer pairing on a trucking HOS-compliance tool. Two things matter more than speed here:

1. **Correctness of the HOS engine.** This app tells real drivers when to stop driving. Every rule you implement must trace back to a specific citation in `ELD_TRIP_PLANNER_PROMPT.md` §3. If a requirement is ambiguous, don't guess — implement the stricter/safer interpretation and leave a comment explaining the choice.
2. **Determinism.** No LLM calls, no "AI-assisted" heuristics, anywhere in the trip-calculation or log-generation path. That logic must be plain, testable Python. If you're tempted to reach for an LLM to fill a gap (e.g., "figure out a reasonable rest stop location"), stop — that's a sign the rules engine is underspecified, not a place for a model call.

---

## Non-negotiable constraints

- Stack is fixed: **Next.js (App Router) + shadcn/ui** frontend, **Django + DRF** backend, **SQLite3** (file-based, no Postgres), **Docker + docker-compose**.
- **Single exposed port.** Only `frontend` publishes a host port. `backend` is `expose`-only on the internal Docker network. All browser calls go through relative `/api/...` paths via the Next.js rewrite in `next.config.js`. Never hardcode `localhost:8000` or add a `NEXT_PUBLIC_API_URL` pointing at a public backend host — that reintroduces the two-URL/CORS setup this project deliberately avoids.
- **Map tiles vs. routing are different services** — OpenFreeMap is tiles only. Distance/duration/path comes from OSRM. Don't collapse these into one call or assume OpenFreeMap has a routing endpoint.
- Assumptions locked (do not silently change): property-carrying driver, 70-hour/8-day cycle, no adverse-driving-conditions exception, fuel stop every 1,000 miles, 1 hour on-duty-not-driving each at pickup and dropoff.
- Don't introduce a new external paid API. Geocoding = Nominatim, routing = OSRM public demo, tiles = OpenFreeMap. If a rate limit becomes a real blocker, flag it in a PR comment rather than swapping providers unilaterally.

---

## Repo map (see ELD_TRIP_PLANNER_PROMPT.md §2 for the full tree)

- `backend/trips/services/hos_engine.py` — the regulation logic. Changes here require a corresponding test in `backend/trips/tests/test_hos_engine.py`.
- `backend/trips/services/log_builder.py` — turns duty segments into per-day grid data. Changes here require a fixture check against `test_log_builder.py`.
- `backend/trips/services/routing.py` / `geocode.py` — thin clients to OSRM / Nominatim. Keep these free of business logic.
- `frontend/components/log-sheet.tsx` — the SVG-drawn FMCSA grid. It should be a pure function of `{segments, totals, remarks}` — no fetching, no HOS logic, inside this component.
- `frontend/components/route-map.tsx` — MapLibre + OpenFreeMap. Rendering only; it consumes the `route.geometry`/`route.stops` the backend already computed.

---

## Dev environment

```bash
docker-compose up --build     # single command, single URL: http://localhost:3000
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py test trips
docker-compose exec frontend npm run lint
```

There is no separate way to "just run the backend" for manual testing against a real browser — it's intentionally not reachable outside the Docker network. Use the Django test client / `manage.py test` for backend-only iteration, and the full compose stack for anything end-to-end.

---

## Conventions

**Python / Django**
- Type hints on every function in `services/`. These are the modules most likely to be read/audited later — optimize for someone else tracing a duty-status decision back to a regulation.
- Django REST Framework serializers own request/response shape validation — don't hand-roll JSON parsing in views.
- Keep `hos_engine.py` free of Django imports (models, request objects). It should be callable and testable as plain Python given primitive inputs (distances, durations, a start datetime, a starting cycle-hours value). Django-specific glue (saving a `Trip`, `DailyLog`) belongs in `views.py` or a thin adapter, not inside the engine.

**TypeScript / Next.js**
- Strict mode on. No `any` in component props — define types for `DutySegment`, `DailyLog`, `RouteStop` once (e.g. `frontend/lib/types.ts`) and reuse them everywhere, mirroring the backend serializer shape exactly.
- Server components by default; only mark a component `"use client"` when it needs interactivity (map, form, animated SVG draw-in).
- Use shadcn primitives rather than raw HTML form elements — the design tokens in `ELD_TRIP_PLANNER_PROMPT.md` §6 are applied at the Tailwind/shadcn theme layer, not per-component.

**Commits / PRs** (relevant for Devin operating autonomously)
- One logical change per commit. `feat(hos-engine): implement 30-minute break insertion` not `updates`.
- A PR that touches `hos_engine.py` or `log_builder.py` must include the test file diff in the same PR — never land engine logic and its test separately.
- If a change requires deviating from something stated in `ELD_TRIP_PLANNER_PROMPT.md` (e.g., a rule that turns out to need adjustment), say so explicitly in the PR description with the reasoning — don't quietly diverge from the spec.

---

## Definition of done (any task, not just the whole project)

- [ ] `python manage.py test trips` passes, including the two ground-truth fixtures from the FMCSA guide (rolling 8-day total; Richmond→Newark daily log totals)
- [ ] Every `DailyLog.totals` sums to exactly 24.0 hours
- [ ] No hardcoded backend URL or published backend port anywhere in frontend code or `docker-compose.yml`
- [ ] `docker-compose up --build` from a clean checkout works end-to-end with no manual steps beyond `migrate`
- [ ] New/changed UI uses the design tokens in §6 of the main prompt, not shadcn defaults

---

## Guardrails — do not

- Do not call any LLM API (including Anthropic's) from `backend/trips/services/`. This project's entire value proposition is a deterministic, auditable engine.
- Do not publish the backend's port in `docker-compose.yml` or add `CORS_ALLOWED_ORIGINS` back in — that's a sign the single-port constraint got broken somewhere upstream; fix the rewrite instead.
- Do not swap SQLite for Postgres to "solve" a concurrency concern without flagging it first — this app has no concurrent-write load that justifies it.
- Do not invent HOS behavior that isn't in `ELD_TRIP_PLANNER_PROMPT.md` §3 (e.g., sleeper-berth splitting) — it's explicitly out of scope for this assignment.

---

## Optional: scoped sub-agent files

Devin/Cascade also auto-loads `AGENTS.md` inside subdirectories as a glob-scoped rule (applied only when the agent touches files in that directory). If the backend and frontend conventions above grow beyond what fits comfortably here, split them into `backend/AGENTS.md` and `frontend/AGENTS.md` rather than expanding this root file — root `AGENTS.md` is sent on *every* message, so keep it lean and put stack-specific depth in the scoped files instead.
