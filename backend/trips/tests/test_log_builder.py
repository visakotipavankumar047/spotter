"""Tests for log_builder — daily log generation from duty segments."""
from datetime import datetime, timedelta
from django.test import TestCase

from trips.services.hos_engine import DutySegment, DutyStatus, LatLng
from trips.services.log_builder import build_daily_logs, daily_log_to_dict


class LogBuilderTest(TestCase):
    """Test the log builder's segment slicing and total computation."""

    def test_single_day_log(self):
        """A trip within one day should produce one daily log."""
        start = datetime(2026, 7, 14, 6, 0, 0)
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=5),
                distance_miles=300.0,
                label="Driving",
            ),
            DutySegment(
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
                start_datetime=start + timedelta(hours=5),
                end_datetime=start + timedelta(hours=6),
                label="Dropoff",
            ),
        ]

        logs = build_daily_logs(segments=segments)

        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0].date, "2026-07-14")
        self.assertAlmostEqual(logs[0].total_miles_today, 300.0, places=1)

    def test_multi_day_log(self):
        """A trip spanning two days should produce two daily logs."""
        start = datetime(2026, 7, 14, 20, 0, 0)  # 8 PM start
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=8),
                distance_miles=480.0,
                label="Driving",
            ),
        ]

        logs = build_daily_logs(segments=segments)

        # Should span 2 days (July 14 and July 15)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0].date, "2026-07-14")
        self.assertEqual(logs[1].date, "2026-07-15")

    def test_totals_always_sum_to_24(self):
        """Every daily log must total exactly 24 hours."""
        start = datetime(2026, 7, 14, 3, 0, 0)  # 3 AM start
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=22),
                distance_miles=1320.0,
                label="Long drive",
            ),
            DutySegment(
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
                start_datetime=start + timedelta(hours=22),
                end_datetime=start + timedelta(hours=23),
                label="Dropoff",
            ),
        ]

        logs = build_daily_logs(segments=segments)

        for log in logs:
            total = sum(log.totals.values())
            self.assertAlmostEqual(total, 24.0, places=2)

    def test_off_duty_padding_before_trip(self):
        """Time before the trip starts should be padded with OFF_DUTY."""
        start = datetime(2026, 7, 14, 10, 0, 0)  # 10 AM start
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=4),
                distance_miles=240.0,
                label="Driving",
            ),
        ]

        logs = build_daily_logs(segments=segments)

        # First segment of the day should be OFF_DUTY from 00:00 to 10:00
        first_seg = logs[0].segments[0]
        self.assertEqual(first_seg.status, "OFF_DUTY")
        self.assertEqual(first_seg.start, "00:00")
        self.assertEqual(first_seg.end, "10:00")

    def test_off_duty_padding_after_trip(self):
        """Time after the trip ends should be padded with OFF_DUTY."""
        start = datetime(2026, 7, 14, 6, 0, 0)
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=4),
                distance_miles=240.0,
                label="Driving",
            ),
        ]

        logs = build_daily_logs(segments=segments)

        # Last segment of the day should be OFF_DUTY from 10:00 to 24:00
        last_seg = logs[0].segments[-1]
        self.assertEqual(last_seg.status, "OFF_DUTY")
        self.assertEqual(last_seg.start, "10:00")
        self.assertEqual(last_seg.end, "24:00")

    def test_remarks_at_status_changes(self):
        """Remarks should be generated at each status change."""
        start = datetime(2026, 7, 14, 6, 0, 0)
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=3),
                distance_miles=180.0,
                start_latlng=LatLng(41.8, -87.6),
                label="Drive to pickup",
            ),
            DutySegment(
                status=DutyStatus.ON_DUTY_NOT_DRIVING,
                start_datetime=start + timedelta(hours=3),
                end_datetime=start + timedelta(hours=4),
                start_latlng=LatLng(39.7, -86.1),
                label="Pickup",
            ),
        ]

        logs = build_daily_logs(segments=segments)

        # Should have remarks for each segment
        self.assertGreaterEqual(len(logs[0].remarks), 2)

    def test_daily_log_to_dict(self):
        """daily_log_to_dict should produce the correct API shape."""
        start = datetime(2026, 7, 14, 6, 0, 0)
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=5),
                distance_miles=300.0,
                label="Driving",
            ),
        ]

        logs = build_daily_logs(segments=segments)
        d = daily_log_to_dict(logs[0])

        self.assertIn("date", d)
        self.assertIn("total_miles_today", d)
        self.assertIn("segments", d)
        self.assertIn("totals", d)
        self.assertIn("remarks", d)

        # Segments should have status, start, end
        for seg in d["segments"]:
            self.assertIn("status", seg)
            self.assertIn("start", seg)
            self.assertIn("end", seg)

    def test_miles_split_across_days(self):
        """Miles should be correctly split when a drive spans midnight."""
        start = datetime(2026, 7, 14, 22, 0, 0)  # 10 PM start
        segments = [
            DutySegment(
                status=DutyStatus.DRIVING,
                start_datetime=start,
                end_datetime=start + timedelta(hours=4),
                distance_miles=240.0,
                label="Driving",
            ),
        ]

        logs = build_daily_logs(segments=segments)

        # Day 1: 2 hours of driving (22:00-24:00) = 120 miles
        # Day 2: 2 hours of driving (00:00-02:00) = 120 miles
        self.assertAlmostEqual(logs[0].total_miles_today, 120.0, places=1)
        self.assertAlmostEqual(logs[1].total_miles_today, 120.0, places=1)
