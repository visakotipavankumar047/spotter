"""Log Builder — converts duty segments into per-day FMCSA grid data.

Slices the segment list at each local midnight into one DailyLog per
calendar day. For each day: per-status totals (must sum to 24h), miles
driven that day, and a remarks list.

This module is free of Django imports — it operates on plain dataclasses
from hos_engine and returns plain dicts/lists.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .hos_engine import DutySegment, DutyStatus, LatLng


@dataclass
class DailyRemark:
    """A single remark entry on a daily log."""

    time: str  # "HH:MM"
    location: str
    note: str


@dataclass
class DailyLogSegment:
    """A segment within a single day's log, in HH:MM format."""

    status: str
    start: str  # "HH:MM"
    end: str    # "HH:MM"


@dataclass
class DailyLog:
    """One day's log sheet data."""

    date: str  # "YYYY-MM-DD"
    total_miles_today: float
    segments: List[DailyLogSegment]
    totals: Dict[str, float]
    remarks: List[DailyRemark]


def _seconds_to_hhmm(seconds: float) -> str:
    """Convert seconds since midnight to HH:MM string."""
    total_seconds = int(round(seconds))
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


def _segment_to_day_segments(
    segment: DutySegment, day_start: datetime, day_end: datetime
) -> List[tuple]:
    """Clip a DutySegment to a single day and return (status, start_s, end_s) tuples.

    Times are in seconds since day_start (midnight).
    """
    results: List[tuple] = []
    seg_start = max(segment.start_datetime, day_start)
    seg_end = min(segment.end_datetime, day_end)

    if seg_start >= seg_end:
        return results

    start_s = (seg_start - day_start).total_seconds()
    end_s = (seg_end - day_start).total_seconds()

    results.append((segment.status, start_s, end_s))
    return results


def _merge_adjacent_same_status(
    segs: List[tuple],
) -> List[tuple]:
    """Merge adjacent segments with the same status."""
    if not segs:
        return []
    merged: List[tuple] = [segs[0]]
    for status, start_s, end_s in segs[1:]:
        last_status, last_start, last_end = merged[-1]
        if status == last_status and abs(start_s - last_end) < 1.0:
            merged[-1] = (last_status, last_start, end_s)
        else:
            merged.append((status, start_s, end_s))
    return merged


def _pad_with_off_duty(
    segs: List[tuple],
) -> List[tuple]:
    """Fill gaps in a 24-hour timeline with OFF_DUTY segments."""
    if not segs:
        return [(DutyStatus.OFF_DUTY, 0.0, 86400.0)]

    padded: List[tuple] = []
    # Leading gap
    if segs[0][1] > 1.0:
        padded.append((DutyStatus.OFF_DUTY, 0.0, segs[0][1]))
    padded.append(segs[0])

    for i in range(1, len(segs)):
        gap_start = segs[i - 1][2]
        gap_end = segs[i][1]
        if gap_end - gap_start > 1.0:
            padded.append((DutyStatus.OFF_DUTY, gap_start, gap_end))
        padded.append(segs[i])

    # Trailing gap
    if segs[-1][2] < 86400.0 - 1.0:
        padded.append((DutyStatus.OFF_DUTY, segs[-1][2], 86400.0))

    return padded


def _coords_label(latlng: Optional[LatLng], fallback: str = "") -> str:
    """Return a human-readable label for coordinates.

    In a production system this would reverse-geocode via Nominatim.
    For now we return the fallback label or a coordinate string.
    """
    if latlng is None:
        return fallback
    return fallback or f"{latlng.lat:.4f}, {latlng.lng:.4f}"


def build_daily_logs(
    segments: List[DutySegment],
    reverse_geocode_fn=None,
) -> List[DailyLog]:
    """Build per-day log sheets from a list of duty segments.

    Args:
        segments: Flat list of DutySegment covering the whole trip.
        reverse_geocode_fn: Optional callable (lat, lng) -> str for remarks.
            If None, uses coordinate string fallback.

    Returns:
        List of DailyLog, one per calendar day spanned by the segments.
    """
    if not segments:
        return []

    # Determine the range of days
    first_day = segments[0].start_datetime.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    last_segment_end = segments[-1].end_datetime
    last_day = last_segment_end.replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    daily_logs: List[DailyLog] = []
    current_day = first_day

    while current_day <= last_day:
        day_end = current_day + timedelta(days=1)

        # Collect all segments that overlap this day
        day_segs_raw: List[tuple] = []
        day_miles = 0.0
        remarks: List[DailyRemark] = []

        for seg in segments:
            # Check if segment overlaps this day
            if seg.end_datetime <= current_day or seg.start_datetime >= day_end:
                continue

            # Clip segment to this day
            clipped = _segment_to_day_segments(seg, current_day, day_end)
            day_segs_raw.extend(clipped)

            # Accumulate miles for driving segments
            if seg.status == DutyStatus.DRIVING:
                overlap_start = max(seg.start_datetime, current_day)
                overlap_end = min(seg.end_datetime, day_end)
                if overlap_end > overlap_start and seg.duration_hours > 0:
                    frac = (
                        (overlap_end - overlap_start).total_seconds()
                        / (seg.end_datetime - seg.start_datetime).total_seconds()
                    )
                    day_miles += seg.distance_miles * frac

            # Add remark at status change (start of segment within this day)
            seg_day_start = max(seg.start_datetime, current_day)
            if seg_day_start < day_end:
                time_str = _seconds_to_hhmm(
                    (seg_day_start - current_day).total_seconds()
                )
                if reverse_geocode_fn and seg.start_latlng:
                    location = reverse_geocode_fn(
                        seg.start_latlng.lat, seg.start_latlng.lng
                    )
                else:
                    location = _coords_label(seg.start_latlng, seg.label)
                remarks.append(
                    DailyRemark(
                        time=time_str,
                        location=location,
                        note=seg.label,
                    )
                )

        # Sort by start time, merge adjacent same-status, pad to 24h
        day_segs_raw.sort(key=lambda s: s[1])
        merged = _merge_adjacent_same_status(day_segs_raw)
        padded = _pad_with_off_duty(merged)

        # Build segment list and totals
        log_segments: List[DailyLogSegment] = []
        totals: Dict[str, float] = {
            "off_duty": 0.0,
            "sleeper_berth": 0.0,
            "driving": 0.0,
            "on_duty_not_driving": 0.0,
        }

        status_key_map = {
            DutyStatus.OFF_DUTY: "off_duty",
            DutyStatus.SLEEPER_BERTH: "sleeper_berth",
            DutyStatus.DRIVING: "driving",
            DutyStatus.ON_DUTY_NOT_DRIVING: "on_duty_not_driving",
        }

        for status, start_s, end_s in padded:
            start_hhmm = _seconds_to_hhmm(start_s)
            end_hhmm = _seconds_to_hhmm(end_s)
            log_segments.append(
                DailyLogSegment(
                    status=status.value,
                    start=start_hhmm,
                    end=end_hhmm,
                )
            )
            duration_h = (end_s - start_s) / 3600.0
            key = status_key_map.get(status, "off_duty")
            totals[key] += duration_h

        # Round totals to avoid floating point drift
        for k in totals:
            totals[k] = round(totals[k], 2)

        daily_logs.append(
            DailyLog(
                date=current_day.strftime("%Y-%m-%d"),
                total_miles_today=round(day_miles, 2),
                segments=log_segments,
                totals=totals,
                remarks=remarks,
            )
        )

        current_day += timedelta(days=1)

    return daily_logs


def daily_log_to_dict(log: DailyLog) -> dict:
    """Convert a DailyLog to a JSON-serializable dict matching the API contract."""
    return {
        "date": log.date,
        "total_miles_today": log.total_miles_today,
        "segments": [
            {"status": s.status, "start": s.start, "end": s.end}
            for s in log.segments
        ],
        "totals": log.totals,
        "remarks": [
            {"time": r.time, "location": r.location, "note": r.note}
            for r in log.remarks
        ],
    }
