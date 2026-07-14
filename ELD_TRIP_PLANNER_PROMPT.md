# Build Prompt: ELD Trip Planner & Daily Log Generator

Paste this whole document into Claude Code (or your agent of choice) as the opening task brief. It is self-contained: tech stack, domain rules, API contract, data flow, and visual direction are all specified so the build can proceed without back-and-forth.

---

## 0. What we're building

A full-stack trucking compliance tool. A dispatcher enters four things — **current location, pickup location, dropoff location, current cycle hours used** — and the app returns:

1. A **route map** (OpenFreeMap tiles) with the driving path and every stop (pickup, dropoff, fuel, rest, break) marked.
2. A set of **FMCSA-compliant Daily Log Sheets** — one per 24-hour period of the trip — rendered as the actual paper-log grid (Off Duty / Sleeper Berth / Driving / On Duty Not Driving), fully filled in, not just a table of numbers.

This is a **rules-engine problem, not an ML problem**. The HOS calculation must be deterministic, auditable, and traceable to the exact regulation it implements. No LLM calls anywhere in the calculation path — only backend code.

---

## 1. Tech stack (fixed — do not substitute)

| Layer | Choice |
|---|---|
| Frontend | Next.js (App Router) + TypeScript |
| UI kit | shadcn/ui (already scaffolded — restyle tokens, don't leave defaults) |
| Backend | Django + Django REST Framework |
| Containerization | Docker + docker-compose (two services only: `frontend`, `backend` — no separate db container) |
| Database | SQLite3, file-based, mounted on a named volume so trip history survives container restarts |
| Deployment topology | Single exposed port. `backend` is **not** published externally; Next.js proxies `/api/*` to it internally over the Docker network so the whole app is reachable from one URL / one port |
| Map rendering | OpenFreeMap tiles via MapLibre GL JS |
| Routing engine | OSRM public demo API (`router.project-osrm.org`) — OpenFreeMap only supplies tiles, it does **not** do routing, so a separate routing call is required |
| Geocoding | Nominatim (OSM) — proxy it through the Django backend so we control the required User-Agent header and rate limiting, and to avoid CORS issues on the frontend |

---

## 2. Repo structure

```
eld-trip-planner/
├── docker-compose.yml           # only `frontend` port is published
├── frontend/                    # Next.js app — the single public entry point
│   ├── Dockerfile
│   ├── next.config.js           # rewrites: /api/:path* -> http://backend:8000/api/:path*
│   ├── app/
│   │   ├── page.tsx              # trip input form
│   │   └── trip/[id]/page.tsx    # results: map + log sheets
│   └── components/
│       ├── trip-form.tsx
│       ├── route-map.tsx         # MapLibre + OpenFreeMap
│       ├── log-sheet.tsx         # SVG-drawn FMCSA grid
│       └── stat-strip.tsx
├── backend/                      # Django project — internal-only, never published
│   ├── Dockerfile
│   ├── db.sqlite3                # created on first run, mounted via named volume
│   ├── config/                   # settings, urls
│   └── trips/
│       ├── models.py             # Trip, DailyLog, DutySegment
│       ├── serializers.py
│       ├── views.py              # /api/trips/, /api/geocode/
│       ├── services/
│       │   ├── geocode.py
│       │   ├── routing.py        # OSRM client
│       │   ├── hos_engine.py     # <- the core deterministic engine
│       │   └── log_builder.py    # duty segments -> per-day grid data
│       └── tests/
│           ├── test_hos_engine.py
│           └── test_log_builder.py
└── README.md
```

---

## 3. Domain rules — the HOS engine (source: FMCSA Interstate Truck Driver's Guide to Hours of Service, April 2022)

Hard-code these as named constants and implement each as its own function so the logic is inspectable and testable. Assumptions locked for this assignment: **property-carrying driver, 70-hour/8-day cycle, no adverse driving conditions exception applied.**

- **11-hour driving limit** (§395.3(a)(3)): max 11 hours of driving within a duty day, after 10 consecutive hours off duty.
- **14-hour driving window** (§395.3(a)(2)): 14 consecutive hours from the start of the first on-duty activity, during which driving is allowed. Once elapsed, no more driving is permitted regardless of remaining drive-hour budget, until another 10 consecutive hours off duty.
- **30-minute break** (§395.3(a)(3)(ii)): required after 8 cumulative (not consecutive) hours of driving. Satisfied by any consecutive 30 minutes off duty, on duty not driving, or in sleeper berth.
- **70-hour/8-day limit** (§395.3(b)): total on-duty time (driving + on-duty-not-driving) over a rolling 8-day window may not exceed 70 hours. Treat the `current_cycle_used_hours` input as the hours already burned in that rolling window at trip start; add every subsequent on-duty minute to that running total.
- **34-hour restart** (§§395.3(c)(1)–(2)): 34+ consecutive hours off duty resets the 70-hour clock to zero. In this engine, trigger a mandatory 34-hour restart automatically whenever continuing the trip would exceed 70 hours, insert it as an explicit segment, reset the cycle counter, and flag it in the trip summary so the UI can call it out.
- **10 consecutive hours off duty** required between duty periods before driving may resume (sleeper-berth splitting is out of scope for this assignment — always use a plain consecutive off-duty reset).
- **Fueling**: insert a 30-minute on-duty-not-driving stop at least once every 1,000 driven miles.
- **Pickup / dropoff**: 1 hour on-duty-not-driving at each location.

### 3.1 Algorithm (implement as `hos_engine.build_duty_timeline(...)`)

1. Geocode `current_location`, `pickup_location`, `dropoff_location`.
2. Call OSRM for two legs: current→pickup and pickup→dropoff. Take distance (miles) and duration (hours) directly from OSRM — don't assume a flat average speed.
3. Build a flat activity queue in order:
   `DRIVE(current→pickup) → ON_DUTY(pickup, 1hr) → DRIVE(pickup→dropoff, split every 1000mi with FUEL(30min)) → ON_DUTY(dropoff, 1hr)`
4. Walk the queue minute-by-minute (or in discrete chunks — minute-granularity is simplest to reason about and test), maintaining four counters:
   - `drive_hours_since_break` → reset on any 30-min+ non-driving break; forces a break insertion at 8.0
   - `drive_hours_in_window` and `duty_hours_in_window` → reset after a 10-hour off-duty period; force a 10-hr off-duty insertion at 11.0 drive hours or 14.0 window hours, whichever comes first
   - `cycle_hours_used` → starts at `current_cycle_used_hours`; forces a 34-hour restart insertion at 70.0
5. Emit a list of `DutySegment { status, start_datetime, end_datetime, start_latlng, end_latlng }` covering the whole trip, status ∈ `{OFF_DUTY, SLEEPER_BERTH, DRIVING, ON_DUTY_NOT_DRIVING}`.
6. `log_builder.py` slices that segment list at each local midnight into one `DailyLog` per calendar day. For each day: per-status totals (must sum to 24h — pad the leading/trailing edges with OFF_DUTY if the trip hasn't started/already ended that day), miles driven that day, and a remarks list (reverse-geocode the lat/lng at each status change to city/state, matching the paper log convention shown in the guide).

### 3.2 Test cases to implement (pulled directly from the source guide — use as ground truth)

- **Rolling 8-day total**: Day hours `[0,10,8.5,12.5,9,10,12,5,6,0]` (Sun→Tue) → assert 8-day total for Days 1–8 = **67**, Days 2–9 = **73**, Days 3–10 = **63**. This validates the rolling-window summation before wiring it into the live engine.
- **Daily log totals**: the guide's own worked example (Richmond, VA → Newark, NJ) produces Off Duty 10, Sleeper Berth 1.75, Driving 7.75, On Duty (Not Driving) 4.5, summing to 24. Use this as a fixture for `log_builder` output shape and the SVG renderer.

---

## 4. API contract

```
POST /api/geocode/           { "q": "Chicago, IL" }
  → [{ "label": "Chicago, IL, USA", "lat": 41.8781, "lng": -87.6298 }, ...]

POST /api/trips/
Request:
{
  "current_location": "Chicago, IL",
  "pickup_location": "Indianapolis, IN",
  "dropoff_location": "Louisville, KY",
  "current_cycle_used_hours": 12.5,
  "trip_start_datetime": "2026-07-14T06:00:00"   // optional, defaults to now
}

Response:
{
  "trip_id": "uuid",
  "summary": {
    "total_distance_miles": 412.3,
    "total_drive_hours": 7.8,
    "total_duty_hours": 10.3,
    "num_days": 2,
    "cycle_hours_remaining_at_finish": 57.7,
    "restarts_required": 0
  },
  "route": {
    "geometry": { "type": "LineString", "coordinates": [...] },  // GeoJSON, both legs concatenated
    "stops": [
      { "type": "pickup", "label": "Indianapolis, IN", "lat": ..., "lng": ..., "arrival": "...", "duration_min": 60 },
      { "type": "fuel", "label": "...", "lat": ..., "lng": ..., "arrival": "...", "duration_min": 30 },
      { "type": "dropoff", "label": "Louisville, KY", "lat": ..., "lng": ..., "arrival": "...", "duration_min": 60 }
    ]
  },
  "daily_logs": [
    {
      "date": "2026-07-14",
      "total_miles_today": 340.1,
      "segments": [
        { "status": "OFF_DUTY", "start": "00:00", "end": "06:00" },
        { "status": "ON_DUTY_NOT_DRIVING", "start": "06:00", "end": "06:30" },
        { "status": "DRIVING", "start": "06:30", "end": "10:15" }
      ],
      "totals": { "off_duty": 10.0, "sleeper_berth": 0, "driving": 9.5, "on_duty_not_driving": 4.5 },
      "remarks": [
        { "time": "06:30", "location": "Chicago, IL", "note": "Start driving" },
        { "time": "10:15", "location": "Rensselaer, IN", "note": "Fuel stop" }
      ]
    }
  ]
}

GET /api/trips/{id}/   → same shape, for reloading a saved trip
```

---

## 5. Frontend requirements

- **`/` — Trip Input**: a form (shadcn `Card`, `Input`, `Button`) for the four inputs. Location fields use an autocomplete (shadcn `Command`/`Popover` combobox) backed by `POST /api/geocode/`, debounced. Submits to `POST /api/trips/`, then routes to `/trip/[id]`. All calls use relative paths (`/api/...`) — same-origin, since the Next.js rewrite in §7 handles the proxy to Django. Never hardcode a `:8000` backend URL in client code.
- **`/trip/[id]` — Results**:
  - A stat strip across the top: total miles, total drive hours, number of days, cycle hours remaining, restart flag if any.
  - A full-width map (MapLibre GL + OpenFreeMap tile style) drawing the route `LineString` and every stop as a marker, color-coded by stop type, with a popup on click.
  - One card per `daily_logs[]` entry, each rendering the **actual FMCSA grid**: a 24-hour axis (midnight→midnight, tick every hour, sub-tick every 15 min), four horizontal rows (Off Duty, Sleeper Berth, Driving, On Duty Not Driving), a step-line connecting status changes, a totals column on the right that sums to 24, and a remarks rail below with location labels at each status change — mirroring the "Completed Grid" / "Completed Log" pages of the source guide. Build this as an SVG component driven purely by the `segments`/`totals`/`remarks` data — no manual drawing.
  - Multi-day trips scroll through log sheets as separate cards, most recent day last.

---

## 6. Visual direction — "Dispatch Console"

Don't reach for a generic SaaS dashboard or a default shadcn zinc theme. The subject here is professional trucking compliance — night-shift dispatch, digital ELD hardware, highway signage, and the physical paper log the driver still has to reference. Build the design plan below, then critique it against the brief before coding — revise anything that reads like a stock template.

**Palette** (override shadcn/Tailwind CSS variables — don't leave defaults):
- `--bg` Midnight Asphalt `#12161C` — app shell background, desaturated navy-charcoal, not pure black
- `--surface` Steel Panel `#1B212B` — cards, nav
- `--border` Route Line `#2A323D` — hairlines
- `--accent` Signal Amber `#F2A93B` — primary actions, active states (echoes highway/DOT amber and ELD screen amber — thematically justified, not decorative)
- `--positive` Mile Marker Teal `#2FBF9F` — compliant/available-hours states
- `--danger` Flare Red `#E5484D` — violations, forced restarts
- `--paper` Manifest Paper `#F6F1E4` with ink `#232323` — **used only inside the log-sheet component**, deliberately breaking from the dark shell to render the log as an actual paper document, because that's literally what it is in real life

**Type**:
- Display/headings: **Space Grotesk** — geometric, instrument-panel character
- Body/UI: **Inter**
- Data (hours, timestamps, coordinates, log totals): **IBM Plex Mono** — reads like a digital ELD readout

**Layout**:
- Input screen: split view — left is the compact console-style form, right is a preview panel where an idle duty-status trace line animates faintly (an oscilloscope-style teaser of what the output looks like).
- Results screen: instrument-cluster stat strip → full-bleed map → stacked paper log cards.

**Signature element**: the log-sheet grid itself. On load, animate the status step-line drawing itself left to right (SVG `stroke-dashoffset`), like a plotter tracing the driver's day. Same treatment, more subtly, for the route polyline on the map. Respect `prefers-reduced-motion`; keep visible keyboard focus throughout.

---

## 7. Docker & deployment — single port, SQLite, no separate db container

**Database**: SQLite3. Django's default `db.sqlite3` file, written to a named volume (e.g. `backend_data:/app/data`) so it survives `docker-compose down`/`up`. No Postgres, no separate db service — one less moving part, and fine for this use case since there's no concurrent-write load.

**Single-port topology**: `docker-compose.yml` defines exactly two services on a shared internal Docker network:

```yaml
services:
  backend:
    build: ./backend
    expose:
      - "8000"        # internal only — no `ports:` mapping, not reachable from the host
    volumes:
      - backend_data:/app/data
    environment:
      - DJANGO_SECRET_KEY=${DJANGO_SECRET_KEY}
      - ALLOWED_HOSTS=backend,localhost
      - DATABASE_PATH=/app/data/db.sqlite3

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"   # the only port published to the host
    environment:
      - BACKEND_INTERNAL_URL=http://backend:8000
    depends_on:
      - backend

volumes:
  backend_data:
```

In `frontend/next.config.js`, add a rewrite so every request to `/api/*` on port 3000 is transparently forwarded to the internal `backend` container — the browser never talks to Django directly, and Django's port is never exposed:

```js
async rewrites() {
  return [
    { source: "/api/:path*", destination: `${process.env.BACKEND_INTERNAL_URL}/api/:path*` },
  ];
}
```

Result: the whole app — pages and API — is served from **one URL, one port** (`http://localhost:3000` locally). No CORS configuration is needed either, since from the browser's point of view every request is same-origin.

**Production deployment**: use a host that runs `docker-compose`-style multi-service stacks with a single public entry point — Railway or Render (Docker deploy) both support this: publish only the `frontend` service's port, keep `backend` on a private/internal network. This replaces the earlier "Vercel + separate backend host" split — Vercel's serverless model can't run the Django container behind Next.js, so it doesn't fit this single-port requirement. If a Vercel deploy is wanted anyway later, that would mean going back to two public URLs and re-adding CORS, which defeats the point here.

README must include: local `docker-compose up` instructions, the one deployed URL, and a short "assumptions" section matching §3.

---

## 8. Acceptance checklist (mirrors the assignment's grading criteria)

- [ ] Trip form → route map → correctly segmented daily log sheets, for a short (<1 day), medium (2–3 day), and long (5+ day, forces a 34-hour restart) trip
- [ ] `test_hos_engine.py` passes against the rolling-8-day and worked-log fixtures in §3.2
- [ ] Every daily log's four totals sum to exactly 24 hours
- [ ] Fuel stops appear at least once per 1,000 driven miles; pickup/dropoff each show 1 hour on-duty-not-driving
- [ ] Restart/violation states are visibly flagged in the UI, not just in a tooltip
- [ ] Design tokens above are actually applied — no default shadcn zinc palette left in place
- [ ] One live URL (single port) serves the whole app end-to-end from a cold load — no separate backend URL, no CORS config needed
- [ ] GitHub repo is public, README complete
- [ ] 3–5 min Loom: (1) live demo of a multi-day trip end-to-end, (2) walk through `hos_engine.py` explaining how each regulation maps to code, (3) walk through the log-sheet renderer, (4) quick look at `docker-compose.yml`, the Next.js rewrite proxy, and how the whole stack ends up behind one port
