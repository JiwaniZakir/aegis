"""Unit tests for Celery tasks — verify task configuration, Beat schedule, and
that tasks import cleanly.

Execution-level tests for tasks that call asyncio.run() with database queries
are covered by the live integration tests (test_live_stack.py) which hit the
actual running stack. These unit tests focus on the task configuration layer.
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Task Decorator Configuration
# ---------------------------------------------------------------------------


class TestTaskDecorators:
    """Verify all tasks have correct Celery decorators (max_retries, retry delay,
    acks_late, reject_on_worker_lost)."""

    def test_finance_sync_config(self):
        from app.tasks.finance_sync import sync_finances

        assert sync_finances.max_retries == 3
        assert sync_finances.default_retry_delay == 60
        assert sync_finances.name == "app.tasks.finance_sync.sync_finances"

    def test_email_sync_config(self):
        from app.tasks.email_sync import sync_emails

        assert sync_emails.max_retries == 3
        assert sync_emails.default_retry_delay == 60

    def test_calendar_sync_config(self):
        from app.tasks.calendar_sync import sync_calendars

        assert sync_calendars.max_retries == 3
        assert sync_calendars.default_retry_delay == 60

    def test_social_sync_config(self):
        from app.tasks.social_sync import sync_social

        assert sync_social.max_retries == 3
        assert sync_social.default_retry_delay == 120  # Longer for social APIs

    def test_health_sync_config(self):
        from app.tasks.health_sync import sync_health

        assert sync_health.max_retries == 3
        assert sync_health.default_retry_delay == 60

    def test_content_generation_config(self):
        from app.tasks.content_generation import generate_daily_content

        assert generate_daily_content.max_retries == 2  # Fewer retries for expensive LLM calls
        assert generate_daily_content.default_retry_delay == 300  # 5 min delay

    def test_whatsapp_sync_config(self):
        from app.tasks.whatsapp_sync import sync_whatsapp

        assert sync_whatsapp.max_retries == 3
        assert sync_whatsapp.default_retry_delay == 120
        assert sync_whatsapp.name == "app.tasks.whatsapp_sync.sync_whatsapp"

    def test_garmin_sync_config(self):
        from app.tasks.garmin_sync import sync_garmin

        assert sync_garmin.max_retries == 3
        assert sync_garmin.default_retry_delay == 120
        assert sync_garmin.name == "app.tasks.garmin_sync.sync_garmin"

    def test_meeting_transcription_config(self):
        from app.tasks.meeting_transcription import transcribe_meetings

        assert transcribe_meetings.max_retries == 2
        assert transcribe_meetings.default_retry_delay == 300
        assert transcribe_meetings.name == "app.tasks.meeting_transcription.transcribe_meetings"


# ---------------------------------------------------------------------------
# Beat Schedule Verification
# ---------------------------------------------------------------------------


class TestBeatSchedule:
    """Verify Celery Beat schedule has all expected tasks with correct timing."""

    def test_beat_schedule_has_all_9_tasks(self):
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        task_names = {v["task"] for v in schedule.values()}

        expected_tasks = {
            "app.tasks.finance_sync.sync_finances",
            "app.tasks.email_sync.sync_emails",
            "app.tasks.calendar_sync.sync_calendars",
            "app.tasks.social_sync.sync_social",
            "app.tasks.health_sync.sync_health",
            "app.tasks.content_generation.generate_daily_content",
            "app.tasks.whatsapp_sync.sync_whatsapp",
            "app.tasks.garmin_sync.sync_garmin",
            "app.tasks.meeting_transcription.transcribe_meetings",
        }
        missing = expected_tasks - task_names
        assert not missing, f"Missing tasks in Beat schedule: {missing}"

    def test_beat_schedule_entry_count(self):
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert len(schedule) >= 9

    def test_finance_sync_runs_every_6_hours(self):
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        for entry in schedule.values():
            if entry["task"] == "app.tasks.finance_sync.sync_finances":
                # crontab with */6 hour
                cron = entry["schedule"]
                assert cron._orig_hour == "*/6"  # type: ignore[attr-defined]
                return
        pytest.fail("finance_sync not found in Beat schedule")

    def test_content_generation_runs_at_7am(self):
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        for entry in schedule.values():
            if entry["task"] == "app.tasks.content_generation.generate_daily_content":
                cron = entry["schedule"]
                assert str(cron._orig_hour) == "7"  # type: ignore[attr-defined]
                assert str(cron._orig_minute) == "0"  # type: ignore[attr-defined]
                return
        pytest.fail("generate_daily_content not found in Beat schedule")

    def test_email_sync_runs_every_30_min(self):
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        for entry in schedule.values():
            if entry["task"] == "app.tasks.email_sync.sync_emails":
                cron = entry["schedule"]
                assert cron._orig_minute == "*/30"  # type: ignore[attr-defined]
                return
        pytest.fail("sync_emails not found in Beat schedule")

    def test_calendar_sync_runs_every_15_min(self):
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        for entry in schedule.values():
            if entry["task"] == "app.tasks.calendar_sync.sync_calendars":
                cron = entry["schedule"]
                assert cron._orig_minute == "*/15"  # type: ignore[attr-defined]
                return
        pytest.fail("sync_calendars not found in Beat schedule")


# ---------------------------------------------------------------------------
# Task Module Import Verification
# ---------------------------------------------------------------------------


class TestTaskImports:
    """Verify all task modules import without errors."""

    def test_import_finance_sync(self):
        from app.tasks import finance_sync  # noqa: F401

    def test_import_email_sync(self):
        from app.tasks import email_sync  # noqa: F401

    def test_import_calendar_sync(self):
        from app.tasks import calendar_sync  # noqa: F401

    def test_import_social_sync(self):
        from app.tasks import social_sync  # noqa: F401

    def test_import_health_sync(self):
        from app.tasks import health_sync  # noqa: F401

    def test_import_content_generation(self):
        from app.tasks import content_generation  # noqa: F401

    def test_import_whatsapp_sync(self):
        from app.tasks import whatsapp_sync  # noqa: F401

    def test_import_garmin_sync(self):
        from app.tasks import garmin_sync  # noqa: F401

    def test_import_meeting_transcription(self):
        from app.tasks import meeting_transcription  # noqa: F401


# ---------------------------------------------------------------------------
# Celery App Configuration
# ---------------------------------------------------------------------------


class TestCeleryAppConfig:
    """Verify core Celery app settings."""

    def test_celery_serializer(self):
        from app.celery_app import celery_app

        assert celery_app.conf.task_serializer == "json"
        assert celery_app.conf.result_serializer == "json"

    def test_celery_acks_late(self):
        from app.celery_app import celery_app

        assert celery_app.conf.task_acks_late is True

    def test_celery_reject_on_worker_lost(self):
        from app.celery_app import celery_app

        assert celery_app.conf.task_reject_on_worker_lost is True

    def test_celery_timezone(self):
        from app.celery_app import celery_app

        assert celery_app.conf.timezone == "America/New_York"

    def test_celery_prefetch_multiplier(self):
        from app.celery_app import celery_app

        assert celery_app.conf.worker_prefetch_multiplier == 1
