# ELD Trip Planner & Daily Log Generator

A full-stack trucking compliance tool. A dispatcher enters four things — **current location, pickup location, dropoff location, current cycle hours used** — and the app returns:

1. A **route map** (OpenFreeMap tiles) with the driving path and every stop (pickup, dropoff, fuel, rest, break) marked.
2. A set of **FMCSA-compliant Daily Log Sheets** — one per 24-hour period of the trip — rendered as the actual paper-log grid (Off Duty / Sleeper Berth / Driving / On Duty Not Driving), fully filled in.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript + shadcn/ui |
| Backend | Django + Django REST Framework |
| Database | SQLite3 (file-based, mounted on a named volume) |
| Containerization | Docker + docker-compose (two services: `frontend`, `backend`) |
| Map tiles | OpenFreeMap via MapLibre GL JS |
| Routing | OSRM public demo API |
| Geocoding | Nominatim (OSM), proxied through Django |

## Quick Start

```bash
# Clone and run — single command, single URL
docker-compose up --build

# Open the app (migrations run automatically on backend start)
open http://localhost:3000
```

The entire app — pages and API — is served from **one URL, one port** (`http://localhost:3000`). Only the `frontend` service publishes a host port. The Next.js rewrite in `frontend/next.config.js` proxies all `/api/*` requests to the internal Django backend over the Docker network. No CORS configuration needed.

### Local development (without Docker)

```bash
# Terminal 1 — backend (internal / rewrite target)
cd backend && python manage.py migrate && python manage.py runserver 8000

# Terminal 2 — frontend (the only URL you open)
cd frontend && npm run dev
```

Or from the repo root: `npm run dev` (runs both via concurrently). Browse `http://localhost:3000` only.

## Production deploy (one URL, one port)

**Vercel cannot host this stack as a single app.** Vercel runs serverless Next.js only and cannot run the Django + SQLite + Gunicorn process behind the Next rewrite the way Docker does. Deploying the frontend on Vercel and the backend elsewhere becomes two public services and breaks the single-port design in this repo.

Use a Docker host that runs **one container exposing only port 3000** (Next.js). Django stays private on `127.0.0.1:8000` inside that container; Next proxies `/api/*` to it.

### Option A — Railway (recommended)

1. Push this repo to GitHub.
2. Create a new Railway project → **Deploy from GitHub**.
3. Railway picks up `railway.toml` + root `Dockerfile`.
4. Set `DJANGO_SECRET_KEY` in Railway variables.
5. Open the single public URL Railway gives you (HTTPS, one host).

### Option B — Render

1. Push this repo to GitHub.
2. New Blueprint → select this repo (`render.yaml`).
3. Set `DJANGO_SECRET_KEY` if prompted.
4. Use the single web service URL Render assigns.

### Option C — Local production image

```bash
docker compose -f docker-compose.prod.yml up --build
# → http://localhost:3000
```

Local dual-service Docker Compose (`docker-compose.yml`) remains the default for development.

## Running Tests

```bash
# Backend tests (HOS engine + log builder)
docker-compose exec backend python manage.py test trips

# Frontend lint
docker-compose exec frontend npm run lint
```

## Architecture

```
eld-trip-planner/
├── docker-compose.yml           # only `frontend` port is published
├── frontend/                    # Next.js app — the single public entry point
│   ├── Dockerfile
│   ├── next.config.js           # rewrites: /api/:path* -> http://backend:8000/api/:path*
│   ├── app/
│   │   ├── page.tsx              # trip input form
│   │   └── trip/[id]/page.tsx    # results: map + log sheets
│   ├── components/
│   │   ├── trip-form.tsx         # location autocomplete + form
│   │   ├── route-map.tsx         # MapLibre + OpenFreeMap
│   │   ├── log-sheet.tsx         # SVG-drawn FMCSA grid
│   │   └── stat-strip.tsx        # instrument-cluster summary
│   └── lib/
│       └── types.ts              # shared TypeScript types
├── backend/                      # Django project — internal-only
│   ├── Dockerfile
│   ├── config/                   # settings, urls, wsgi
│   └── trips/
│       ├── models.py             # Trip model
│       ├── serializers.py        # DRF serializers
│       ├── views.py              # /api/trips/, /api/geocode/
│       ├── services/
│       │   ├── geocode.py        # Nominatim client
│       │   ├── routing.py        # OSRM client
│       │   ├── hos_engine.py     # core deterministic HOS engine
│       │   └── log_builder.py    # duty segments -> per-day grid data
│       └── tests/
│           ├── test_hos_engine.py
│           └── test_log_builder.py
└── README.md
```

## HOS Rules Implemented

All rules trace to the FMCSA Interstate Truck Driver's Guide to Hours of Service (April 2022):

- **11-hour driving limit** (§395.3(a)(3)): max 11 hours of driving within a duty day
- **14-hour driving window** (§395.3(a)(2)): 14 consecutive hours from first on-duty activity
- **30-minute break** (§395.3(a)(3)(ii)): required after 8 cumulative hours of driving
- **70-hour/8-day limit** (§395.3(b)): rolling 8-day on-duty total may not exceed 70 hours
- **34-hour restart** (§§395.3(c)(1)–(2)): 34+ consecutive hours off duty resets the 70-hour clock
- **10 consecutive hours off duty** required between duty periods before driving may resume
- **Fueling**: 30-minute on-duty stop every 1,000 driven miles
- **Pickup/dropoff**: 1 hour on-duty-not-driving at each location

## Assumptions

- Property-carrying driver
- 70-hour/8-day cycle (not 60-hour/7-day)
- No adverse-driving-conditions exception
- No sleeper-berth splitting (out of scope)
- Fuel stop every 1,000 miles
- 1 hour on-duty-not-driving each at pickup and dropoff

## API Contract

```
POST /api/geocode/           { "q": "Chicago, IL" }
  → [{ "label": "Chicago, IL, USA", "lat": 41.8781, "lng": -87.6298 }, ...]

POST /api/trips/
  Request: { "current_location", "pickup_location", "dropoff_location",
             "current_cycle_used_hours", "trip_start_datetime" (optional) }
  Response: { "trip_id", "summary", "route", "daily_logs" }

GET /api/trips/{id}/   → same response shape
```

## Design

The UI uses a "Dispatch Console" theme:
- **Midnight Asphalt** dark background (#12161C)
- **Signal Amber** primary actions (#F2A93B) — echoes highway/DOT amber
- **Mile Marker Teal** for compliant states (#2FBF9F)
- **Flare Red** for violations (#E5484D)
- **Manifest Paper** log sheets (#F6F1E4) — deliberately breaking from the dark shell to render logs as actual paper documents
- Fonts: Space Grotesk (headings), Inter (body), IBM Plex Mono (data)
