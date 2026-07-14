# 0001. Stack & architecture: Next.js + Django + SQLite, single Docker port

**Date**: 2026-07-14
**Status**: Proposed

## Summary

This spec records the foundational tech stack for the ELD Trip Planner, a trucking hours of service compliance tool. The stack is fully locked by the build prompt (`ELD_TRIP_PLANNER_PROMPT.md` sections 1 and 7) and the non negotiable constraints in `AGENTS.md`: a Next.js App Router frontend with shadcn/ui, a Django REST Framework backend, SQLite3 for storage, and Docker Compose with a single published port. The only open setup decisions settled here are the Python and Django versions, settings management, and the test runner. This is a documentation spec, not an evaluation, because the decision was made before this workflow started.

## Context

The product is a full stack trucking compliance tool. A dispatcher enters a trip (current location, pickup, dropoff, current cycle hours used) and the app returns a route map plus FMCSA compliant daily log sheets. The core value is a deterministic, auditable hours of service engine (the rules that tell real drivers when they must stop driving), so the stack choices prioritize boring, proven tools that keep the rules engine simple to test and trace.

The build prompt fixes the stack and the deployment topology. The frontend is Next.js with the App Router and TypeScript, using shadcn/ui for components (already scaffolded in this repo). The backend is Django with Django REST Framework. The database is SQLite3, file based, mounted on a named Docker volume so trip history survives container restarts. The whole app runs behind a single published port (the frontend's port 3000), with the backend reachable only on the internal Docker network. The Next.js rewrite in `next.config.js` proxies `/api/*` calls to the internal backend, so the browser never talks to Django directly and no CORS configuration is needed.

External services are also fixed. Map tiles come from OpenFreeMap, rendered with MapLibre GL JS. Routing (distance, duration, path geometry) comes from the OSRM public demo API. Geocoding (turning place names into coordinates) comes from Nominatim, proxied through the Django backend so the required User Agent header and rate limiting stay server side. These are three separate services: OpenFreeMap supplies tiles only, it does not do routing.

The consequence of not recording this decision in a spec is that later features (the data model, the core trip loop, the HOS engine) would each have to restate the stack, or worse, silently diverge from it. This spec is the one place the foundational choices live, so every later spec and build task can reference it.

## Options considered

The build prompt documents the alternatives that were ruled out. They are recorded here for history, not re evaluated.

### Option 1: Postgres instead of SQLite3

A separate Postgres database container alongside the backend and frontend.

**Pros**:
- Handles concurrent writes, which a real multi user production app would need.

**Cons**:
- Adds a third Docker service and a database to operate.
- This app has no concurrent write load (a single dispatcher enters trips one at a time), so the extra moving part buys nothing.

### Option 2: Vercel for the frontend, a separate host for the backend

Deploy the Next.js frontend on Vercel and the Django backend on a separate host, with two public URLs.

**Pros**:
- Vercel's serverless model is the default path for Next.js apps.

**Cons**:
- Vercel's serverless model cannot run the Django container behind Next.js, so the single port topology breaks.
- Two public URLs mean CORS configuration is needed again, which the single port design deliberately avoids.

### Option 3: Two public ports (frontend and backend both published)

Publish both the frontend (port 3000) and backend (port 8000) to the host, with the frontend calling the backend directly.

**Pros**:
- Simpler Docker Compose file, no rewrite proxy.

**Cons**:
- The browser talks to Django directly, requiring CORS configuration.
- Two URLs to manage, defeating the single entry point goal.

## Decision

**Chosen option**: The locked stack from the build prompt (Next.js + shadcn/ui, Django + DRF, SQLite3, Docker single port, OpenFreeMap, OSRM, Nominatim), with the open setup decisions settled as: Python 3.12, Django 5.2, django-environ for settings, Django's built in test runner, and DRF at the latest version compatible with Django 5.2.

**Implementation skills**: none (no community skills installed for this stack).

## Rationale

The stack is locked because this is a graded assignment with a fixed specification. The build prompt chose proven, boring tools that keep the rules engine (the actual grading focus) simple to test and trace. Django and DRF give a mature REST API layer with serializers that own request and response validation, so the HOS engine stays free of Django imports and callable as plain Python. SQLite3 removes a database service from the Docker topology (one less moving part) and is fine for an app with no concurrent write load. The single port topology (Next.js proxies `/api/*` to the internal backend) means the browser sees one origin, so no CORS configuration is needed and the backend is never reachable from the host.

The setup decisions follow the same boring and proven principle. Python 3.12 is mature, well supported by Django 5.x, and available in the `python:3.12-slim` Docker image. Django 5.2 is the current stable release line, supported by DRF, and works with Python 3.11 through 3.13. django-environ reads environment variables from a `.env` file with typed access, which matches the Docker Compose pattern of passing secrets through environment variables and keeps secrets out of the code. Django's built in test runner is what `AGENTS.md` already documents (`python manage.py test trips`), so no extra test dependency is needed. DRF is pinned to the latest version compatible with Django 5.2 (3.16.x as of this writing).

## Proposed stack

| Layer | Choice | Reason |
|---|---|---|
| Backend language | Python 3.12 | Mature, well supported by Django 5.x, available as `python:3.12-slim` Docker image. |
| Backend framework | Django 5.2 + Django REST Framework (latest compatible) | DRF serializers own request and response validation, keeping the HOS engine free of Django imports. |
| Frontend framework | Next.js (App Router) + TypeScript | Already scaffolded. Server components by default, client components only for interactivity (map, form, animated SVG). |
| UI kit | shadcn/ui | Already scaffolded. Design tokens applied at the Tailwind theme layer, not per component. |
| Primary database | SQLite3 (file based, named Docker volume) | No concurrent write load, so no need for a separate database service. The volume (`backend_data:/app/data`) survives container restarts. |
| Map rendering | MapLibre GL JS + OpenFreeMap tiles | OpenFreeMap supplies tiles only. MapLibre draws the route LineString and stop markers from backend computed geometry. |
| Routing | OSRM public demo API (`router.project-osrm.org`) | Supplies distance, duration, and path geometry. A separate call from map tiles. |
| Geocoding | Nominatim, proxied through Django | Keeps the required User Agent header and rate limiting server side, avoids frontend CORS issues. |
| Containerization | Docker + docker-compose (two services) | Only `frontend` publishes a host port. `backend` is `expose` only on the internal Docker network. |
| Deployment topology | Single published port (3000) | Next.js rewrite proxies `/api/*` to the internal backend. One URL, one port, no CORS. |
| Settings management | django-environ | Reads `.env` and environment variables with typed access. Matches the Docker Compose env var pattern. |
| Test runner | Django built in (`manage.py test`) | Already documented in `AGENTS.md`. No extra test dependency. |
| Auth | None | Not in scope for this assignment. No user accounts, no login. |
| Background jobs | None | Trip calculation is synchronous within the request. No queue needed. |
| File storage | None | No file uploads in scope. |
| Observability | Django structured logging | Log geocode and OSRM call failures for debugging. No external monitoring service for a local assignment. |
| Hosting | Local `docker-compose up` | Live deployment (Railway or Render) is deferred, out of scope for this build pass. |

## Consequences

**Positive**:
- One command (`docker-compose up --build`) starts the whole app. One URL (`http://localhost:3000`) serves pages and API.
- No CORS configuration anywhere, because every browser request is same origin through the Next.js proxy.
- The HOS engine is plain Python, callable and testable with primitive inputs, no Django imports needed.
- SQLite removes a database service from the topology, keeping it to exactly two Docker services.
- DRF serializers own validation, so views stay thin.

**Negative / tradeoffs**:
- SQLite is single writer. If the app ever needs concurrent writes (multi dispatcher), a migration to Postgres would be required. Acceptable now because there is no concurrent write load.
- The backend is not reachable from the host for manual testing. Backend only iteration uses `manage.py test` or the Django test client, not a browser hitting port 8000.
- The OSRM public demo API and Nominatim are rate limited free services. If rate limits become a real blocker, the fix is to flag it in a PR comment, not to swap providers unilaterally (per `AGENTS.md`).
- No auth means anyone who can reach the app can create and view trips. Fine for a local assignment, not for a real multi user product.

**Neutral**:
- The Next.js rewrite in `next.config.js` is the single point that makes the proxy work. Any change to the backend URL pattern must update the rewrite, not add a hardcoded `localhost:8000` or a `NEXT_PUBLIC_API_URL`.
- `db.sqlite3` lives at `/app/data/db.sqlite3` inside the container (the `DATABASE_PATH` env var), mounted on the `backend_data` volume.

## Follow-up

- [ ] After the backend scaffold is built, run `/audit` to capture the Python and Django conventions into root `AGENTS.md` (scope feature 3, coding standards and tooling).
- [ ] Pin exact dependency versions in `backend/requirements.txt` once the scaffold is built, so the Docker build is reproducible.
