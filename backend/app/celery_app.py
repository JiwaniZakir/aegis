"""Celery application configuration."""

from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "aegis",
    broker=settings.redis_connection_url,
    backend=settings.redis_connection_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/New_York",
    enable_utc=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_reject_on_worker_lost=True,
)

# Explicit imports to register all task modules with Celery
import app.tasks.calendar_sync  # noqa: E402, F401
import app.tasks.content_generation  # noqa: E402, F401
import app.tasks.email_sync  # noqa: E402, F401
import app.tasks.finance_sync  # noqa: E402, F401
import app.tasks.garmin_sync  # noqa: E402, F401
import app.tasks.health_sync  # noqa: E402, F401
import app.tasks.meeting_transcription  # noqa: E402, F401
import app.tasks.social_sync  # noqa: E402, F401
import app.tasks.whatsapp_sync  # noqa: E402, F401

# Periodic task schedule (Celery Beat)
celery_app.conf.beat_schedule = {
    "sync-finances-every-6h": {
        "task": "app.tasks.finance_sync.sync_finances",
        "schedule": crontab(minute=0, hour="*/6"),
    },
    "sync-emails-every-30m": {
        "task": "app.tasks.email_sync.sync_emails",
        "schedule": crontab(minute="*/30"),
    },
    "sync-calendar-every-15m": {
        "task": "app.tasks.calendar_sync.sync_calendars",
        "schedule": crontab(minute="*/15"),
    },
    "sync-social-every-2h": {
        "task": "app.tasks.social_sync.sync_social",
        "schedule": crontab(minute=0, hour="*/2"),
    },
    "generate-content-7am": {
        "task": "app.tasks.content_generation.generate_daily_content",
        "schedule": crontab(minute=0, hour=7),
    },
    "health-sync-hourly": {
        "task": "app.tasks.health_sync.sync_health",
        "schedule": crontab(minute=0),
    },
    "sync-whatsapp-every-30m": {
        "task": "app.tasks.whatsapp_sync.sync_whatsapp",
        "schedule": crontab(minute="*/30"),
    },
    "sync-garmin-every-4h": {
        "task": "app.tasks.garmin_sync.sync_garmin",
        "schedule": crontab(minute=0, hour="*/4"),
    },
    "transcribe-meetings-every-2h": {
        "task": "app.tasks.meeting_transcription.transcribe_meetings",
        "schedule": crontab(minute=30, hour="*/2"),
    },
}
