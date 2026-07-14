"""HOS Engine — deterministic FMCSA Hours-of-Service compliance logic.

Every rule implemented here traces back to a specific citation in
ELD_TRIP_PLANNER_PROMPT.md §3 (source: FMCSA Interstate Truck Driver's
Guide to Hours of Service, April 2022).

This module is deliberately free of Django imports so it can be tested
as plain Python given primitive inputs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple


# ---------------------------------------------------------------------------
# Regulation constants — each named for its citation
# ---------------------------------------------------------------------------

# §395.3(a)(3) — max 11 hours of driving within a duty day
DRIVING_LIMIT_HOURS: float = 11.0

# §395.3(a)(2) — 14 consecutive hours from first on-duty activity
DRIVING_WINDOW_HOURS: float = 14.0

# §395.3(a)(3)(ii) — 30-minute break after 8 cumulative hours of driving
BREAK_REQUIRED_AFTER_HOURS: float = 8.0
BREAK_DURATION_HOURS: float = 0.5  # 30 minutes

# 10 consecutive hours off duty required before driving may resume
OFF_DUTY_RESET_HOURS: float = 10.0

# §395.3(b) — 70-hour/8-day cycle limit
CYCLE_LIMIT_HOURS: float = 70.0
CYCLE_WINDOW_DAYS: int = 8

# §§395.3(c)(1)–(2) — 34-hour restart
RESTART_DURATION_HOURS: float = 34.0

# Fueling — 30-min on-duty stop every 1,000 driven miles
FUEL_STOP_INTERVAL_MILES: float = 1000.0
FUEL_STOP_DURATION_HOURS: float = 0.5

# Pickup / dropoff — 1 hour on-duty-not-driving at each
PICKUP_DROPOFF_DURATION_HOURS: float = 1.0

# Tolerance for floating-point comparisons (1 minute in hours)
_EPSILON: float = 1.0 / 60.0


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class DutyStatus(str, Enum):
    """FMCSA duty status categories."""

    OFF_DUTY = "OFF_DUTY"
    SLEEPER_BERTH = "SLEEPER_BERTH"
    DRIVING = "DRIVING"
    ON_DUTY_NOT_DRIVING = "ON_DUTY_NOT_DRIVING"


@dataclass
class LatLng:
    """Geographic coordinate."""

    lat: float
    lng: float


@dataclass
class DutySegment:
    """A single contiguous period of one duty status.

    Attributes:
        status: FMCSA duty status.
        start_datetime: When this segment begins.
        end_datetime: When this segment ends.
        start_latlng: Location at segment start (optional).
        end_latlng: Location at segment end (optional).
        distance_miles: Miles driven (DRIVING segments only).
        label: Human-readable remark for this segment.
    """

    status: DutyStatus
    start_datetime: datetime
    end_datetime: datetime
    start_latlng: Optional[LatLng] = None
    end_latlng: Optional[LatLng] = None
    distance_miles: float = 0.0
    label: str = ""

    @property
    def duration_hours(self) -> float:
        return (self.end_datetime - self.start_datetime).total_seconds() / 3600.0


@dataclass
class RouteLeg:
    """A single routing leg from OSRM.

    Attributes:
        distance_miles: Total distance in miles.
        duration_hours: Total driving time in hours.
        geometry: GeoJSON LineString coordinates — list of [lng, lat].
        start_coords: Starting coordinate.
        end_coords: Ending coordinate.
    """

    distance_miles: float
    duration_hours: float
    geometry: List[Tuple[float, float]]
    start_coords: LatLng
    end_coords: LatLng


@dataclass
class Activity:
    """A single activity in the flat queue before HOS rules are applied."""

    status: DutyStatus
    duration_hours: float
    distance_miles: float = 0.0
    start_coords: Optional[LatLng] = None
    end_coords: Optional[LatLng] = None
    label: str = ""


@dataclass
class TripSummary:
    """Summary statistics for a completed trip."""

    total_distance_miles: float = 0.0
    total_drive_hours: float = 0.0
    total_duty_hours: float = 0.0
    num_days: int = 1
    cycle_hours_remaining_at_finish: float = 0.0
    restarts_required: int = 0


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _haversine_miles(
    coord1: Tuple[float, float], coord2: Tuple[float, float]
) -> float:
    """Distance in miles between two (lng, lat) points."""
    r = 3959.0
    lat1, lng1 = math.radians(coord1[1]), math.radians(coord1[0])
    lat2, lng2 = math.radians(coord2[1]), math.radians(coord2[0])
    dlat = lat2 - lat1
    dlng = lng2 - lng1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))
    return r * c


def _interpolate_geometry(
    geometry: List[Tuple[float, float]], fraction: float
) -> Tuple[float, float]:
    """Interpolate a point at *fraction* along the geometry by distance."""
    if not geometry:
        return (0.0, 0.0)
    if fraction <= 0.0:
        return geometry[0]
    if fraction >= 1.0:
        return geometry[-1]

    cumul: List[float] = [0.0]
    for i in range(1, len(geometry)):
        cumul.append(cumul[-1] + _haversine_miles(geometry[i - 1], geometry[i]))
    total = cumul[-1]
    if total == 0:
        return geometry[0]

    target = fraction * total
    for i in range(1, len(cumul)):
        if cumul[i] >= target:
            seg_len = cumul[i] - cumul[i - 1]
            if seg_len == 0:
                return geometry[i]
            t = (target - cumul[i - 1]) / seg_len
            lng = geometry[i - 1][0] + t * (
                geometry[i][0] - geometry[i - 1][0]
            )
            lat = geometry[i - 1][1] + t * (
                geometry[i][1] - geometry[i - 1][1]
            )
            return (lng, lat)
    return geometry[-1]


def _interpolate_coords(
    start: Optional[LatLng], end: Optional[LatLng], fraction: float
) -> Optional[LatLng]:
    """Linear interpolation between two LatLng points."""
    if start is None or end is None:
        return end if fraction >= 1.0 else start
    return LatLng(
        lat=start.lat + fraction * (end.lat - start.lat),
        lng=start.lng + fraction * (end.lng - start.lng),
    )


def _split_leg_by_distance(
    leg: RouteLeg, interval_miles: float
) -> List[Tuple[float, float, LatLng, LatLng]]:
    """Split a RouteLeg into segments at every *interval_miles*.

    Returns list of (distance_miles, duration_hours, start_coords, end_coords).
    """
    if leg.distance_miles <= interval_miles + 0.01:
        return [
            (
                leg.distance_miles,
                leg.duration_hours,
                leg.start_coords,
                leg.end_coords,
            )
        ]

    segments: List[Tuple[float, float, LatLng, LatLng]] = []
    num_full = int(leg.distance_miles // interval_miles)

    for i in range(num_full):
        start_frac = i * interval_miles / leg.distance_miles
        end_frac = (i + 1) * interval_miles / leg.distance_miles
        seg_dist = interval_miles
        seg_dur = leg.duration_hours * (end_frac - start_frac)
        start_pt = LatLng(*reversed(_interpolate_geometry(leg.geometry, start_frac)))
        end_pt = LatLng(*reversed(_interpolate_geometry(leg.geometry, end_frac)))
        segments.append((seg_dist, seg_dur, start_pt, end_pt))

    remaining_dist = leg.distance_miles - num_full * interval_miles
    if remaining_dist > 0.01:
        start_frac = num_full * interval_miles / leg.distance_miles
        seg_dist = remaining_dist
        seg_dur = leg.duration_hours * (1.0 - start_frac)
        start_pt = LatLng(*reversed(_interpolate_geometry(leg.geometry, start_frac)))
        segments.append((seg_dist, seg_dur, start_pt, leg.end_coords))

    return segments


# ---------------------------------------------------------------------------
# Rolling 8-day total (§395.3(b)) — used by test_hos_engine.py
# ---------------------------------------------------------------------------


def rolling_8_day_total(
    day_hours: List[float], window_size: int = CYCLE_WINDOW_DAYS
) -> List[float]:
    """Calculate rolling window totals.

    Given a list of daily on-duty hours, returns a list where element *i*
    is the sum of ``day_hours[i : i + window_size]``.

    Example (from FMCSA guide §3.2):
        >>> day_hours = [0, 10, 8.5, 12.5, 9, 10, 12, 5, 6, 0]
        >>> rolling_8_day_total(day_hours)
        [67.0, 73.0, 63.0]
    """
    totals: List[float] = []
    for i in range(len(day_hours) - window_size + 1):
        totals.append(sum(day_hours[i : i + window_size]))
    return totals


# ---------------------------------------------------------------------------
# Activity queue builder
# ---------------------------------------------------------------------------


def build_activity_queue(legs: List[RouteLeg]) -> List[Activity]:
    """Build the flat activity queue from route legs.

    Queue order (per §3.1 step 3):
        ``DRIVE(current→pickup) → ON_DUTY(pickup, 1hr) →
        DRIVE(pickup→dropoff, split every 1000mi with FUEL(30min)) →
        ON_DUTY(dropoff, 1hr)``
    """
    activities: List[Activity] = []

    # Leg 1: current → pickup (driving, no fuel stops per spec)
    if legs and legs[0].distance_miles > 0.01:
        activities.append(
            Activity(
                status=DutyStatus.DRIVING,
                duration_hours=legs[0].duration_hours,
                distance_miles=legs[0].distance_miles,
                start_coords=legs[0].start_coords,
                end_coords=legs[0].end_coords,
                label="Drive to pickup",
            )
        )

    # Pickup: 1 hour on-duty-not-driving
    pickup_coords = legs[0].end_coords if legs else None
    activities.append(
        Activity(
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            duration_hours=PICKUP_DROPOFF_DURATION_HOURS,
            start_coords=pickup_coords,
            end_coords=pickup_coords,
            label="Pickup",
        )
    )

    # Leg 2: pickup → dropoff (driving, split every 1000mi with fuel stops)
    if len(legs) > 1 and legs[1].distance_miles > 0.01:
        drive_segments = _split_leg_by_distance(
            legs[1], FUEL_STOP_INTERVAL_MILES
        )
        for i, (dist, dur, start, end) in enumerate(drive_segments):
            activities.append(
                Activity(
                    status=DutyStatus.DRIVING,
                    duration_hours=dur,
                    distance_miles=dist,
                    start_coords=start,
                    end_coords=end,
                    label=f"Drive to dropoff (segment {i + 1})",
                )
            )
            # Fuel stop after each segment except the last
            if i < len(drive_segments) - 1:
                activities.append(
                    Activity(
                        status=DutyStatus.ON_DUTY_NOT_DRIVING,
                        duration_hours=FUEL_STOP_DURATION_HOURS,
                        start_coords=end,
                        end_coords=end,
                        label="Fuel stop",
                    )
                )

    # Dropoff: 1 hour on-duty-not-driving
    dropoff_coords = legs[-1].end_coords if legs else None
    activities.append(
        Activity(
            status=DutyStatus.ON_DUTY_NOT_DRIVING,
            duration_hours=PICKUP_DROPOFF_DURATION_HOURS,
            start_coords=dropoff_coords,
            end_coords=dropoff_coords,
            label="Dropoff",
        )
    )

    return activities


# ---------------------------------------------------------------------------
# Core engine — build_duty_timeline
# ---------------------------------------------------------------------------


def build_duty_timeline(
    legs: List[RouteLeg],
    start_datetime: datetime,
    current_cycle_used_hours: float,
) -> Tuple[List[DutySegment], TripSummary]:
    """Build a HOS-compliant duty timeline from route legs.

    This is the core deterministic engine. It walks the activity queue
    and inserts rest periods (30-min breaks, 10-hour off-duty resets,
    34-hour restarts) as required by FMCSA regulations.

    Args:
        legs: List of RouteLeg (typically 2: current→pickup, pickup→dropoff).
        start_datetime: When the trip begins.
        current_cycle_used_hours: Hours already used in the 70-hour/8-day
            cycle at trip start.

    Returns:
        Tuple of (list of DutySegment, TripSummary).
    """
    activities = build_activity_queue(legs)

    segments: List[DutySegment] = []
    current_time = start_datetime

    # Counters
    drive_since_break = 0.0  # §395.3(a)(3)(ii) — resets on 30-min+ non-driving
    drive_in_window = 0.0  # §395.3(a)(3) — actual driving in current window
    window_elapsed = 0.0  # §395.3(a)(2) — wall clock in current 14h window
    cycle_used = current_cycle_used_hours  # §395.3(b) — rolling 8-day total
    window_active = False  # Whether a 14h window is currently open
    restarts_required = 0

    def _emit(
        status: DutyStatus,
        duration_h: float,
        start_coords: Optional[LatLng] = None,
        end_coords: Optional[LatLng] = None,
        label: str = "",
        distance: float = 0.0,
    ) -> None:
        nonlocal current_time
        end_time = current_time + timedelta(hours=duration_h)
        segments.append(
            DutySegment(
                status=status,
                start_datetime=current_time,
                end_datetime=end_time,
                start_latlng=start_coords,
                end_latlng=end_coords,
                distance_miles=distance,
                label=label,
            )
        )
        current_time = end_time

    def _insert_30min_break() -> None:
        """Insert a 30-minute off-duty break (§395.3(a)(3)(ii))."""
        nonlocal drive_since_break, window_elapsed
        _emit(DutyStatus.OFF_DUTY, BREAK_DURATION_HOURS, label="30-min break")
        drive_since_break = 0.0
        if window_active:
            window_elapsed += BREAK_DURATION_HOURS

    def _insert_10h_off_duty() -> None:
        """Insert 10 consecutive hours off duty to reset the driving window."""
        nonlocal drive_since_break, drive_in_window, window_elapsed, window_active
        _emit(DutyStatus.OFF_DUTY, OFF_DUTY_RESET_HOURS, label="10-hour reset")
        drive_since_break = 0.0
        drive_in_window = 0.0
        window_elapsed = 0.0
        window_active = False

    def _insert_34h_restart() -> None:
        """Insert a 34-hour restart (§§395.3(c)(1)–(2))."""
        nonlocal drive_since_break, drive_in_window, window_elapsed
        nonlocal window_active, cycle_used, restarts_required
        _emit(DutyStatus.OFF_DUTY, RESTART_DURATION_HOURS, label="34-hour restart")
        drive_since_break = 0.0
        drive_in_window = 0.0
        window_elapsed = 0.0
        window_active = False
        cycle_used = 0.0
        restarts_required += 1

    for activity in activities:
        # ---- Pre-activity cycle check (§395.3(b)) ----
        if activity.status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING):
            if cycle_used >= CYCLE_LIMIT_HOURS - _EPSILON:
                _insert_34h_restart()

        # ---- Start a new window if needed ----
        if activity.status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING):
            if not window_active:
                window_active = True
                window_elapsed = 0.0
                drive_in_window = 0.0

        # ---- Process by status ----
        if activity.status == DutyStatus.DRIVING:
            total_dur = activity.duration_hours
            total_dist = activity.distance_miles
            driven = 0.0  # hours driven so far within this activity

            while total_dur - driven > _EPSILON:
                remaining = total_dur - driven

                # Check if we need rest before driving more
                need_restart = cycle_used >= CYCLE_LIMIT_HOURS - _EPSILON
                need_off_duty = (
                    drive_in_window >= DRIVING_LIMIT_HOURS - _EPSILON
                    or window_elapsed >= DRIVING_WINDOW_HOURS - _EPSILON
                )
                need_break = drive_since_break >= BREAK_REQUIRED_AFTER_HOURS - _EPSILON

                if need_restart:
                    _insert_34h_restart()
                    # Re-open window for continued driving
                    window_active = True
                    window_elapsed = 0.0
                    drive_in_window = 0.0
                    continue

                if need_off_duty:
                    _insert_10h_off_duty()
                    # Re-open window for continued driving
                    window_active = True
                    window_elapsed = 0.0
                    drive_in_window = 0.0
                    continue

                if need_break:
                    _insert_30min_break()
                    continue

                # No rest needed — calculate how far we can drive
                max_by_break = BREAK_REQUIRED_AFTER_HOURS - drive_since_break
                max_by_11h = DRIVING_LIMIT_HOURS - drive_in_window
                max_by_14h = DRIVING_WINDOW_HOURS - window_elapsed
                max_by_cycle = CYCLE_LIMIT_HOURS - cycle_used

                max_drive = min(
                    max_by_break, max_by_11h, max_by_14h, max_by_cycle, remaining
                )

                if max_drive <= _EPSILON:
                    # Safety net — shouldn't happen after checks above
                    break

                # Drive for max_drive hours
                frac_start = driven / total_dur if total_dur > 0 else 0.0
                frac_end = (driven + max_drive) / total_dur if total_dur > 0 else 1.0
                seg_start = _interpolate_coords(
                    activity.start_coords, activity.end_coords, frac_start
                )
                seg_end = _interpolate_coords(
                    activity.start_coords, activity.end_coords, frac_end
                )
                seg_dist = total_dist * (max_drive / total_dur) if total_dur > 0 else 0.0

                _emit(
                    DutyStatus.DRIVING,
                    max_drive,
                    start_coords=seg_start,
                    end_coords=seg_end,
                    label=activity.label,
                    distance=seg_dist,
                )

                driven += max_drive
                drive_since_break += max_drive
                drive_in_window += max_drive
                window_elapsed += max_drive
                cycle_used += max_drive

        elif activity.status == DutyStatus.ON_DUTY_NOT_DRIVING:
            dur = activity.duration_hours

            # Check if this on-duty time would exceed cycle
            if cycle_used + dur > CYCLE_LIMIT_HOURS - _EPSILON:
                # Drive up to cycle limit, then restart, then continue
                # But on-duty-not-driving can't be "split" easily —
                # insert restart before the activity
                _insert_34h_restart()
                # Re-open window
                window_active = True
                window_elapsed = 0.0
                drive_in_window = 0.0

            _emit(
                DutyStatus.ON_DUTY_NOT_DRIVING,
                dur,
                start_coords=activity.start_coords,
                end_coords=activity.end_coords,
                label=activity.label,
            )

            window_elapsed += dur
            cycle_used += dur

            # 30-min break satisfaction (§395.3(a)(3)(ii)):
            # any consecutive 30 min off duty, on-duty-not-driving, or sleeper
            if dur >= BREAK_DURATION_HOURS - _EPSILON:
                drive_since_break = 0.0

        elif activity.status == DutyStatus.OFF_DUTY:
            dur = activity.duration_hours
            _emit(DutyStatus.OFF_DUTY, dur, label=activity.label)

            if dur >= OFF_DUTY_RESET_HOURS - _EPSILON:
                # 10+ hours off duty resets the window
                drive_since_break = 0.0
                drive_in_window = 0.0
                window_elapsed = 0.0
                window_active = False
            else:
                if window_active:
                    window_elapsed += dur
                if dur >= BREAK_DURATION_HOURS - _EPSILON:
                    drive_since_break = 0.0

    # ---- Build summary ----
    total_distance = sum(
        s.distance_miles for s in segments if s.status == DutyStatus.DRIVING
    )
    total_drive = sum(
        s.duration_hours for s in segments if s.status == DutyStatus.DRIVING
    )
    total_duty = sum(
        s.duration_hours
        for s in segments
        if s.status in (DutyStatus.DRIVING, DutyStatus.ON_DUTY_NOT_DRIVING)
    )

    # Number of calendar days spanned
    if segments:
        first_day = segments[0].start_datetime.date()
        last_day = segments[-1].end_datetime.date()
        num_days = (last_day - first_day).days + 1
    else:
        num_days = 1

    summary = TripSummary(
        total_distance_miles=round(total_distance, 2),
        total_drive_hours=round(total_drive, 2),
        total_duty_hours=round(total_duty, 2),
        num_days=num_days,
        cycle_hours_remaining_at_finish=round(
            max(0.0, CYCLE_LIMIT_HOURS - cycle_used), 2
        ),
        restarts_required=restarts_required,
    )

    return segments, summary
