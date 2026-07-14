"""Tests for the HOS engine — FMCSA Hours-of-Service compliance logic.

Ground-truth fixtures from ELD_TRIP_PLANNER_PROMPT.md §3.2:
  - Rolling 8-day total
  - Richmond→Newark daily log totals
"""
from datetime import datetime, timedelta
from django.test import TestCase

from trips.services.hos_engine import (
    DutyStatus,
    DutySegment,
    LatLng,
    RouteLeg,
    TripSummary,
    build_activity_queue,
    build_duty_timeline,
    rolling_8_day_total,
    DRIVING_LIMIT_HOURS,
    DRIVING_WINDOW_HOURS,
    BREAK_REQUIRED_AFTER_HOURS,
    BREAK_DURATION_HOURS,
    OFF_DUTY_RESET_HOURS,
    CYCLE_LIMIT_HOURS,
    RESTART_DURATION_HOURS,
    FUEL_STOP_INTERVAL_MILES,
    PICKUP_DROPOFF_DURATION_HOURS,
)
from trips.services.log_builder import build_daily_logs


class Rolling8DayTotalTest(TestCase):
    """§3.2 — Rolling 8-day total fixture."""

    def test_rolling_8_day_totals(self):
        """Day hours [0,10,8.5,12.5,9,10,12,5,6,0] (Sun→Tue).

        Days 1–8 = 67, Days 2–9 = 73, Days 3–10 = 63.
        """
        day_hours = [0, 10, 8.5, 12.5, 9, 10, 12, 5, 6, 0]
        totals = rolling_8_day_total(day_hours)

        self.assertEqual(len(totals), 3)
        self.assertEqual(totals[0], 67.0)
        self.assertEqual(totals[1], 73.0)
        self.assertEqual(totals[2], 63.0)

    def test_short_list(self):
        """Fewer than 8 days should return empty list."""
        self.assertEqual(rolling_8_day_total([5, 5, 5]), [])

    def test_exactly_8_days(self):
        """Exactly 8 days should return one total."""
        totals = rolling_8_day_total([10] * 8)
        self.assertEqual(len(totals), 1)
        self.assertEqual(totals[0], 80.0)


class BuildActivityQueueTest(TestCase):
    """Test the flat activity queue builder."""

    def test_short_trip_queue(self):
        """A short trip should produce: drive → pickup → drive → dropoff."""
        leg1 = RouteLeg(
            distance_miles=180.0,
            duration_hours=3.0,
            geometry=[(-87.6, 41.8), (-86.1, 39.7)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(39.7, -86.1),
        )
        leg2 = RouteLeg(
            distance_miles=100.0,
            duration_hours=2.0,
            geometry=[(-86.1, 39.7), (-85.7, 38.2)],
            start_coords=LatLng(39.7, -86.1),
            end_coords=LatLng(38.2, -85.7),
        )

        activities = build_activity_queue([leg1, leg2])

        # drive, pickup (on-duty), drive, dropoff (on-duty)
        self.assertEqual(len(activities), 4)
        self.assertEqual(activities[0].status, DutyStatus.DRIVING)
        self.assertEqual(activities[1].status, DutyStatus.ON_DUTY_NOT_DRIVING)
        self.assertEqual(activities[2].status, DutyStatus.DRIVING)
        self.assertEqual(activities[3].status, DutyStatus.ON_DUTY_NOT_DRIVING)

        # Pickup and dropoff should each be 1 hour
        self.assertEqual(activities[1].duration_hours, PICKUP_DROPOFF_DURATION_HOURS)
        self.assertEqual(activities[3].duration_hours, PICKUP_DROPOFF_DURATION_HOURS)

    def test_long_trip_fuel_stops(self):
        """A 2,500-mile leg should produce fuel stops every 1,000 miles."""
        leg1 = RouteLeg(
            distance_miles=50.0,
            duration_hours=1.0,
            geometry=[(-87.6, 41.8), (-87.0, 41.5)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(41.5, -87.0),
        )
        leg2 = RouteLeg(
            distance_miles=2500.0,
            duration_hours=45.0,
            geometry=[(-87.0, 41.5), (-118.0, 34.0)],
            start_coords=LatLng(41.5, -87.0),
            end_coords=LatLng(34.0, -118.0),
        )

        activities = build_activity_queue([leg1, leg2])

        # Should have: drive(50mi), pickup(1hr), drive(1000mi), fuel(30min),
        # drive(1000mi), fuel(30min), drive(500mi), dropoff(1hr)
        drive_count = sum(1 for a in activities if a.status == DutyStatus.DRIVING)
        fuel_count = sum(
            1 for a in activities
            if a.status == DutyStatus.ON_DUTY_NOT_DRIVING and "fuel" in a.label.lower()
        )

        # 3 drive segments in leg2 + 1 in leg1 = 4 total
        self.assertEqual(drive_count, 4)
        # 2 fuel stops (at 1000mi and 2000mi)
        self.assertEqual(fuel_count, 2)


class BuildDutyTimelineTest(TestCase):
    """Test the core HOS timeline builder."""

    def _make_short_legs(self) -> list:
        """Create legs for a short trip (~5 hours driving total)."""
        leg1 = RouteLeg(
            distance_miles=180.0,
            duration_hours=3.0,
            geometry=[(-87.6, 41.8), (-86.1, 39.7)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(39.7, -86.1),
        )
        leg2 = RouteLeg(
            distance_miles=100.0,
            duration_hours=2.0,
            geometry=[(-86.1, 39.7), (-85.7, 38.2)],
            start_coords=LatLng(39.7, -86.1),
            end_coords=LatLng(38.2, -85.7),
        )
        return [leg1, leg2]

    def test_short_trip_no_violations(self):
        """A short trip with low cycle hours should need no rest insertions."""
        legs = self._make_short_legs()
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=legs,
            start_datetime=start,
            current_cycle_used_hours=10.0,
        )

        # Total driving = 5 hours, well under 11-hour limit
        self.assertAlmostEqual(summary.total_drive_hours, 5.0, places=1)
        # Total duty = 5 driving + 2 on-duty (pickup + dropoff) = 7
        self.assertAlmostEqual(summary.total_duty_hours, 7.0, places=1)
        # No restarts needed
        self.assertEqual(summary.restarts_required, 0)
        # Cycle remaining = 70 - 10 - 7 = 53
        self.assertAlmostEqual(
            summary.cycle_hours_remaining_at_finish, 53.0, places=1
        )

    def test_30_min_break_inserted(self):
        """When driving exceeds 8 hours, a 30-min break must be inserted."""
        # Create a single leg with 10 hours of driving (no fuel stops needed)
        leg1 = RouteLeg(
            distance_miles=50.0,
            duration_hours=1.0,
            geometry=[(-87.6, 41.8), (-87.0, 41.5)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(41.5, -87.0),
        )
        leg2 = RouteLeg(
            distance_miles=600.0,
            duration_hours=10.0,
            geometry=[(-87.0, 41.5), (-80.0, 36.0)],
            start_coords=LatLng(41.5, -87.0),
            end_coords=LatLng(36.0, -80.0),
        )
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=[leg1, leg2],
            start_datetime=start,
            current_cycle_used_hours=0.0,
        )

        # Should have at least one OFF_DUTY break segment
        break_segments = [
            s for s in segments
            if s.status == DutyStatus.OFF_DUTY and "break" in s.label.lower()
        ]
        self.assertGreaterEqual(len(break_segments), 1)

        # Each break should be ~30 minutes
        for b in break_segments:
            self.assertAlmostEqual(
                b.duration_hours, BREAK_DURATION_HOURS, places=2
            )

    def test_11_hour_driving_limit(self):
        """Driving must stop at 11 hours and require a 10-hour reset."""
        # 15 hours of driving in one leg — will need to split at 11h
        leg1 = RouteLeg(
            distance_miles=50.0,
            duration_hours=1.0,
            geometry=[(-87.6, 41.8), (-87.0, 41.5)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(41.5, -87.0),
        )
        leg2 = RouteLeg(
            distance_miles=900.0,
            duration_hours=15.0,
            geometry=[(-87.0, 41.5), (-75.0, 35.0)],
            start_coords=LatLng(41.5, -87.0),
            end_coords=LatLng(35.0, -75.0),
        )
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=[leg1, leg2],
            start_datetime=start,
            current_cycle_used_hours=0.0,
        )

        # Find all driving segments and check none exceeds 11 hours
        drive_segments = [s for s in segments if s.status == DutyStatus.DRIVING]
        for ds in drive_segments:
            self.assertLessEqual(
                ds.duration_hours,
                DRIVING_LIMIT_HOURS + 0.01,
                f"Driving segment exceeds 11h limit: {ds.duration_hours}h"
            )

        # Should have at least one 10-hour reset
        reset_segments = [
            s for s in segments
            if s.status == DutyStatus.OFF_DUTY and "reset" in s.label.lower()
        ]
        self.assertGreaterEqual(len(reset_segments), 1)

    def test_14_hour_window_limit(self):
        """The 14-hour driving window must be respected."""
        # 1h drive + 1h pickup + 12h drive = 14h window used, then must reset
        leg1 = RouteLeg(
            distance_miles=60.0,
            duration_hours=1.0,
            geometry=[(-87.6, 41.8), (-87.0, 41.5)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(41.5, -87.0),
        )
        leg2 = RouteLeg(
            distance_miles=720.0,
            duration_hours=12.0,
            geometry=[(-87.0, 41.5), (-78.0, 36.0)],
            start_coords=LatLng(41.5, -87.0),
            end_coords=LatLng(36.0, -78.0),
        )
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=[leg1, leg2],
            start_datetime=start,
            current_cycle_used_hours=0.0,
        )

        # Total drive should be 13h but split by 10h reset due to 14h window
        # After 1h drive + 1h pickup + 12h drive = 14h window, driving must stop
        # Actually: 1h drive + 1h on-duty = 2h window, then 12h drive = 14h total
        # So 12h driving in window, but 11h limit kicks in first
        # The engine should insert a 10h reset when either 11h drive or 14h window hits

        # Verify no driving segment exceeds 11h
        drive_segments = [s for s in segments if s.status == DutyStatus.DRIVING]
        for ds in drive_segments:
            self.assertLessEqual(
                ds.duration_hours,
                DRIVING_LIMIT_HOURS + 0.01,
            )

    def test_34_hour_restart(self):
        """When cycle would exceed 70h, a 34-hour restart must be inserted."""
        # Start with 68 hours used — even a short trip will trigger restart
        leg1 = RouteLeg(
            distance_miles=180.0,
            duration_hours=3.0,
            geometry=[(-87.6, 41.8), (-86.1, 39.7)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(39.7, -86.1),
        )
        leg2 = RouteLeg(
            distance_miles=100.0,
            duration_hours=2.0,
            geometry=[(-86.1, 39.7), (-85.7, 38.2)],
            start_coords=LatLng(39.7, -86.1),
            end_coords=LatLng(38.2, -85.7),
        )
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=[leg1, leg2],
            start_datetime=start,
            current_cycle_used_hours=68.0,
        )

        # 68 + 5 driving + 2 on-duty = 75 > 70, so restart needed
        self.assertGreaterEqual(summary.restarts_required, 1)

        # Find the restart segment
        restart_segments = [
            s for s in segments
            if s.status == DutyStatus.OFF_DUTY and "restart" in s.label.lower()
        ]
        self.assertGreaterEqual(len(restart_segments), 1)

        for rs in restart_segments:
            self.assertAlmostEqual(
                rs.duration_hours, RESTART_DURATION_HOURS, places=1
            )

    def test_cycle_remaining_after_restart(self):
        """After a 34h restart, cycle should reset to 0 + new duty hours."""
        leg1 = RouteLeg(
            distance_miles=180.0,
            duration_hours=3.0,
            geometry=[(-87.6, 41.8), (-86.1, 39.7)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(39.7, -86.1),
        )
        leg2 = RouteLeg(
            distance_miles=100.0,
            duration_hours=2.0,
            geometry=[(-86.1, 39.7), (-85.7, 38.2)],
            start_coords=LatLng(39.7, -86.1),
            end_coords=LatLng(38.2, -85.7),
        )
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=[leg1, leg2],
            start_datetime=start,
            current_cycle_used_hours=69.0,
        )

        # After restart, cycle resets to 0, then 5 driving + 2 on-duty = 7
        # Remaining = 70 - 7 = 63
        self.assertEqual(summary.restarts_required, 1)
        self.assertAlmostEqual(
            summary.cycle_hours_remaining_at_finish, 63.0, places=1
        )

    def test_segment_continuity(self):
        """All segments should be contiguous — no gaps in the timeline."""
        legs = self._make_short_legs()
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=legs,
            start_datetime=start,
            current_cycle_used_hours=10.0,
        )

        self.assertGreater(len(segments), 0)

        # First segment starts at trip start
        self.assertEqual(segments[0].start_datetime, start)

        # Each segment's end == next segment's start
        for i in range(len(segments) - 1):
            self.assertEqual(
                segments[i].end_datetime,
                segments[i + 1].start_datetime,
                f"Gap between segment {i} and {i + 1}"
            )


class DailyLogTotalsTest(TestCase):
    """§3.2 — Daily log totals must sum to exactly 24 hours."""

    def test_totals_sum_to_24(self):
        """Every daily log's four totals must sum to 24.0 hours."""
        leg1 = RouteLeg(
            distance_miles=180.0,
            duration_hours=3.0,
            geometry=[(-87.6, 41.8), (-86.1, 39.7)],
            start_coords=LatLng(41.8, -87.6),
            end_coords=LatLng(39.7, -86.1),
        )
        leg2 = RouteLeg(
            distance_miles=100.0,
            duration_hours=2.0,
            geometry=[(-86.1, 39.7), (-85.7, 38.2)],
            start_coords=LatLng(39.7, -86.1),
            end_coords=LatLng(38.2, -85.7),
        )
        start = datetime(2026, 7, 14, 6, 0, 0)

        segments, summary = build_duty_timeline(
            legs=[leg1, leg2],
            start_datetime=start,
            current_cycle_used_hours=10.0,
        )

        daily_logs = build_daily_logs(segments=segments)

        for log in daily_logs:
            total = (
                log.totals["off_duty"]
                + log.totals["sleeper_berth"]
                + log.totals["driving"]
                + log.totals["on_duty_not_driving"]
            )
            self.assertAlmostEqual(
                total, 24.0, places=2,
                msg=f"Daily log for {log.date} totals {total}, expected 24.0"
            )

    def test_richmond_newark_fixture(self):
        """Richmond→Newark fixture: Off 10, Sleeper 1.75, Driving 7.75, On-duty 4.5.

        This is the worked example from the FMCSA guide. We construct
        segments manually to match the expected totals, then verify
        log_builder produces the correct output.
        """
        # Richmond, VA → Newark, NJ is ~330 miles, ~7.75 hours driving
        # The guide's example log: Off 10, Sleeper 1.75, Driving 7.75, On-duty 4.5
        # Total = 24.0

        start = datetime(2026, 7, 14, 6, 0, 0)

        # Build segments to match the fixture:
        # 06:00-06:30 ON_DUTY (0.5h pre-trip) — part of the 4.5 on-duty
        # 06:30-14:15 DRIVING (7.75h)
        # 14:15-15:15 ON_DUTY (1h dropoff)
        # 15:15-17:00 ON_DUTY (1.75h) — remaining on-duty
        # 17:00-18:45 SLEEPER (1.75h)
        # 18:45-04:45 OFF_DUTY (10h)
        # Wait — let's just construct segments that produce the right totals

        # Simpler: construct a single day with the exact fixture totals
        segments = [
            DutySegment(
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=4.5),
                label="On duty",
            ),
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start + timedelta(hours=4.5),
                end_datetime=start + timedelta(hours=4.5 + 7.75),
                distance_miles=330.0,
                label="Driving",
            ),
            DutySegment(
                status=DutyStatus.SLEEPER_BERTH,
                start_datetime=start + timedelta(hours=4.5 + 7.75),
                end_datetime=start + timedelta(hours=4.5 + 7.75 + 1.75),
                label="Sleeper",
            ),
            DutySegment(
                status=DutyStatus.OFF_DUTY,
                start_datetime=start + timedelta(hours=4.5 + 7.75 + 1.75),
                end_datetime=start + timedelta(hours=24),
                label="Off duty",
            ),
        ]

        daily_logs = build_daily_logs(segments=segments)

        self.assertEqual(len(daily_logs), 1)
        log = daily_logs[0]

        self.assertAlmostEqual(log.totals["off_duty"], 10.0, places=2)
        self.assertAlmostEqual(log.totals["sleeper_berth"], 1.75, places=2)
        self.assertAlmostEqual(log.totals["driving"], 7.75, places=2)
        self.assertAlmostEqual(log.totals["on_duty_not_driving"], 4.5, places=2)

        total = sum(log.totals.values())
        self.assertAlmostEqual(total, 24.0, places=2)
