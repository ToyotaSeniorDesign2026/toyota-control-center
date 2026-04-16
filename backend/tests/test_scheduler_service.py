from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app.services.scheduler_service import next_daily_occurrence


class SchedulerServiceTests(unittest.TestCase):
    def test_daily_pm_schedule_fires_today_after_due_time(self) -> None:
        now = datetime(2026, 4, 15, 21, 0, tzinfo=timezone.utc)
        occurrence = next_daily_occurrence("daily at 7:30 PM", now=now, timezone_name="UTC")

        self.assertIsNotNone(occurrence)
        assert occurrence is not None
        self.assertEqual(occurrence.fire_key, "2026-04-15T19:30")
        self.assertEqual(occurrence.due_at, datetime(2026, 4, 15, 19, 30, tzinfo=timezone.utc))

    def test_daily_pm_schedule_waits_for_today_before_due_time(self) -> None:
        now = datetime(2026, 4, 15, 18, 0, tzinfo=timezone.utc)
        occurrence = next_daily_occurrence("daily at 7:30 PM", now=now, timezone_name="UTC")

        self.assertIsNotNone(occurrence)
        assert occurrence is not None
        self.assertEqual(occurrence.fire_key, "2026-04-14T19:30")

    def test_simple_daily_cron_is_supported(self) -> None:
        now = datetime(2026, 4, 15, 21, 0, tzinfo=timezone.utc)
        occurrence = next_daily_occurrence("30 19 * * *", now=now, timezone_name="UTC")

        self.assertIsNotNone(occurrence)
        assert occurrence is not None
        self.assertEqual(occurrence.fire_key, "2026-04-15T19:30")
