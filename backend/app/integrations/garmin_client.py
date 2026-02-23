"""Garmin Connect integration — health metrics, activities, and sleep data.

Uses the unofficial ``garminconnect`` library. This library can break
with Garmin server-side changes; all calls are wrapped in retry logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.integrations.base import BaseIntegration
from app.models.health import HealthMetric

logger = structlog.get_logger()

# Conditional import — garminconnect is unofficial and in the optional group.
try:
    from garminconnect import Garmin

    GARMIN_AVAILABLE = True
except ImportError:
    Garmin = None  # type: ignore[assignment, misc]
    GARMIN_AVAILABLE = False


class GarminClientError(RuntimeError):
    """Raised when a Garmin Connect API call fails."""


class GarminClient(BaseIntegration):
    """Integration client for Garmin Connect (unofficial API).

    Pulls daily stats, heart rate, steps, sleep, and activities from Garmin
    Connect using the ``garminconnect`` Python library. This library is
    unofficial and may break with upstream changes — all calls are wrapped
    in robust error handling.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        if not GARMIN_AVAILABLE:
            msg = "garminconnect is not installed. Install with: uv pip install garminconnect"
            raise GarminClientError(msg)
        self._client: Garmin | None = None

    async def login(self) -> None:
        """Authenticate with Garmin Connect using stored credentials.

        Raises:
            GarminClientError: If login fails or garminconnect is unavailable.
        """
        await self._ensure_client()

    async def _ensure_client(self) -> Garmin:
        """Lazily initialise and authenticate the Garmin client."""
        if self._client is not None:
            return self._client

        email = await self.get_credential("garmin_email")
        password = await self.get_credential("garmin_password")

        try:
            client = Garmin(email, password)
            client.login()
            self._client = client
            self._log.info("garmin_authenticated")
            return client
        except Exception as exc:
            self._log.error("garmin_auth_failed", error=str(type(exc).__name__))
            msg = "Failed to authenticate with Garmin Connect"
            raise GarminClientError(msg) from exc

    # ------------------------------------------------------------------
    # Data retrieval methods
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def get_stats(self, target_date: date | None = None) -> dict:
        """Fetch daily summary stats (steps, calories, distance, etc.).

        Args:
            target_date: Date to retrieve stats for. Defaults to today.

        Returns:
            Dict with daily summary fields from Garmin Connect.
        """
        if target_date is None:
            target_date = date.today()

        client = await self._ensure_client()
        date_str = target_date.isoformat()

        try:
            stats = client.get_stats(date_str)
            self._log.info("garmin_stats_fetched", date=date_str)
            await self._audit(
                action="garmin_stats_read",
                resource_type="health",
                metadata={"date": date_str},
            )
            return stats if isinstance(stats, dict) else {}
        except Exception as exc:
            self._log.error(
                "garmin_stats_failed",
                date=date_str,
                error=str(type(exc).__name__),
            )
            msg = f"Failed to fetch Garmin stats for {date_str}"
            raise GarminClientError(msg) from exc

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def get_heart_rate(self, days: int = 7) -> list[dict]:
        """Fetch heart rate data for the specified number of days.

        Args:
            days: Number of days to retrieve (default 7).

        Returns:
            List of dicts with date, resting HR, max HR, and avg HR.
        """
        client = await self._ensure_client()
        results: list[dict] = []
        today = date.today()

        for i in range(days):
            target = today - timedelta(days=i)
            date_str = target.isoformat()
            try:
                hr_data = client.get_heart_rates(date_str)
                if isinstance(hr_data, dict):
                    results.append(
                        {
                            "date": date_str,
                            "resting_hr": hr_data.get("restingHeartRate", 0),
                            "max_hr": hr_data.get("maxHeartRate", 0),
                            "avg_hr": hr_data.get("averageHeartRate", 0),
                            "source": "garmin",
                        }
                    )
            except Exception as exc:
                self._log.warning(
                    "garmin_heart_rate_failed",
                    date=date_str,
                    error=str(type(exc).__name__),
                )

        self._log.info("garmin_heart_rate_fetched", days=days, records=len(results))
        await self._audit(
            action="garmin_heart_rate_read",
            resource_type="health",
            metadata={"days": days, "records": len(results)},
        )
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def get_steps(self, days: int = 7) -> list[dict]:
        """Fetch daily step counts for the specified number of days.

        Args:
            days: Number of days to retrieve (default 7).

        Returns:
            List of dicts with date and total steps.
        """
        client = await self._ensure_client()
        results: list[dict] = []
        today = date.today()

        for i in range(days):
            target = today - timedelta(days=i)
            date_str = target.isoformat()
            try:
                steps_data = client.get_steps_data(date_str)
                total_steps = 0
                if isinstance(steps_data, list):
                    total_steps = sum(
                        entry.get("steps", 0) for entry in steps_data if isinstance(entry, dict)
                    )
                elif isinstance(steps_data, dict):
                    total_steps = steps_data.get("totalSteps", 0)

                results.append(
                    {
                        "date": date_str,
                        "steps": total_steps,
                        "source": "garmin",
                    }
                )
            except Exception as exc:
                self._log.warning(
                    "garmin_steps_failed",
                    date=date_str,
                    error=str(type(exc).__name__),
                )

        self._log.info("garmin_steps_fetched", days=days, records=len(results))
        await self._audit(
            action="garmin_steps_read",
            resource_type="health",
            metadata={"days": days, "records": len(results)},
        )
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def get_sleep(self, days: int = 7) -> list[dict]:
        """Fetch sleep data for the specified number of days.

        Args:
            days: Number of days to retrieve (default 7).

        Returns:
            List of dicts with date, sleep hours, and stage breakdowns.
        """
        client = await self._ensure_client()
        results: list[dict] = []
        today = date.today()

        for i in range(days):
            target = today - timedelta(days=i)
            date_str = target.isoformat()
            try:
                sleep_data = client.get_sleep_data(date_str)
                if isinstance(sleep_data, dict):
                    daily_sleep = sleep_data.get("dailySleepDTO", {})
                    duration_secs = daily_sleep.get("sleepTimeSeconds", 0) or 0
                    sleep_hours = round(duration_secs / 3600, 2)

                    results.append(
                        {
                            "date": date_str,
                            "sleep_hours": sleep_hours,
                            "deep_sleep_seconds": daily_sleep.get("deepSleepSeconds", 0),
                            "light_sleep_seconds": daily_sleep.get("lightSleepSeconds", 0),
                            "rem_sleep_seconds": daily_sleep.get("remSleepSeconds", 0),
                            "awake_seconds": daily_sleep.get("awakeSleepSeconds", 0),
                            "source": "garmin",
                        }
                    )
            except Exception as exc:
                self._log.warning(
                    "garmin_sleep_failed",
                    date=date_str,
                    error=str(type(exc).__name__),
                )

        self._log.info("garmin_sleep_fetched", days=days, records=len(results))
        await self._audit(
            action="garmin_sleep_read",
            resource_type="health",
            metadata={"days": days, "records": len(results)},
        )
        return results

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(ConnectionError),
        reraise=True,
    )
    async def get_activities(self, days: int = 7) -> list[dict]:
        """Fetch recent activities (runs, walks, cycling, etc.).

        Args:
            days: Number of days to look back (default 7).

        Returns:
            List of activity summary dicts within the time window.
        """
        client = await self._ensure_client()
        results: list[dict] = []
        cutoff = datetime.now(UTC) - timedelta(days=days)

        try:
            activities = client.get_activities(0, 50)
            if not isinstance(activities, list):
                return results

            for activity in activities:
                if not isinstance(activity, dict):
                    continue

                started = activity.get("startTimeLocal", "")
                if started:
                    try:
                        activity_dt = datetime.fromisoformat(started)
                        if activity_dt.tzinfo is None:
                            activity_dt = activity_dt.replace(tzinfo=UTC)
                        if activity_dt < cutoff:
                            continue
                    except (ValueError, TypeError):
                        pass

                results.append(
                    {
                        "activity_id": str(activity.get("activityId", "")),
                        "name": activity.get("activityName", ""),
                        "type": activity.get("activityType", {}).get("typeKey", "unknown"),
                        "start_time": started,
                        "duration_seconds": activity.get("duration", 0),
                        "calories": activity.get("calories", 0),
                        "distance_meters": activity.get("distance", 0),
                        "avg_hr": activity.get("averageHR", 0),
                        "max_hr": activity.get("maxHR", 0),
                        "source": "garmin",
                    }
                )
        except Exception as exc:
            self._log.warning(
                "garmin_activities_failed",
                error=str(type(exc).__name__),
            )

        self._log.info("garmin_activities_fetched", days=days, records=len(results))
        await self._audit(
            action="garmin_activities_read",
            resource_type="health",
            metadata={"days": days, "count": len(results)},
        )
        return results

    # ------------------------------------------------------------------
    # Metric storage
    # ------------------------------------------------------------------

    async def store_metrics(
        self,
        metrics: list[dict],
    ) -> int:
        """Persist a list of health metrics to the database.

        Each metric dict must contain ``metric_type``, ``value``, ``unit``,
        and ``timestamp`` (ISO-format string or datetime).

        Args:
            metrics: List of metric dicts to store.

        Returns:
            Number of metrics stored.
        """
        uid = uuid.UUID(self.user_id)
        stored = 0

        for metric in metrics:
            try:
                ts = metric.get("timestamp")
                if isinstance(ts, str):
                    ts = datetime.fromisoformat(ts)
                elif not isinstance(ts, datetime):
                    ts = datetime.now(UTC)

                record = HealthMetric(
                    user_id=uid,
                    metric_type=metric["metric_type"],
                    value=float(metric["value"]),
                    unit=metric.get("unit", "count"),
                    timestamp=ts,
                    source="garmin",
                )
                self.db.add(record)
                stored += 1
            except (KeyError, ValueError, TypeError) as exc:
                self._log.warning(
                    "garmin_metric_store_skipped",
                    error=str(type(exc).__name__),
                    metric_type=metric.get("metric_type"),
                )

        if stored:
            await self.db.flush()
            self._log.info("garmin_metrics_stored", count=stored)
            await self._audit(
                action="garmin_metrics_store",
                resource_type="health",
                metadata={"count": stored},
            )

        return stored

    # ------------------------------------------------------------------
    # Abstract implementations
    # ------------------------------------------------------------------

    async def sync(self) -> None:
        """Pull latest health data from Garmin Connect and store it.

        Fetches steps, heart rate, sleep, and activity data for the past day,
        converts to HealthMetric rows, and persists to the database.
        """
        await self.login()

        metrics: list[dict] = []
        ts_now = datetime.now(UTC).isoformat()
        today = date.today()

        # Steps (1 day)
        steps_data = await self.get_steps(days=1)
        for entry in steps_data:
            metrics.append(
                {
                    "metric_type": "steps",
                    "value": entry.get("steps", 0),
                    "unit": "count",
                    "timestamp": f"{entry['date']}T23:59:00+00:00",
                }
            )

        # Heart rate (1 day)
        hr_data = await self.get_heart_rate(days=1)
        for entry in hr_data:
            if entry.get("resting_hr"):
                metrics.append(
                    {
                        "metric_type": "heart_rate",
                        "value": entry["resting_hr"],
                        "unit": "bpm",
                        "timestamp": f"{entry['date']}T23:59:00+00:00",
                    }
                )

        # Sleep (1 day)
        sleep_data = await self.get_sleep(days=1)
        for entry in sleep_data:
            metrics.append(
                {
                    "metric_type": "sleep_hours",
                    "value": entry.get("sleep_hours", 0),
                    "unit": "hours",
                    "timestamp": f"{entry['date']}T08:00:00+00:00",
                }
            )

        # Activities — calories burned
        activities = await self.get_activities(days=1)
        for activity in activities:
            calories = activity.get("calories", 0)
            if calories:
                metrics.append(
                    {
                        "metric_type": "calories_burned",
                        "value": calories,
                        "unit": "kcal",
                        "timestamp": activity.get(
                            "start_time", f"{today.isoformat()}T12:00:00+00:00"
                        ),
                    }
                )

        # Also pull daily stats for aggregate calories / distance
        try:
            stats = await self.get_stats(today)
            if total_cal := stats.get("totalKilocalories"):
                metrics.append(
                    {
                        "metric_type": "calories_burned",
                        "value": total_cal,
                        "unit": "kcal",
                        "timestamp": ts_now,
                    }
                )
            if distance_m := stats.get("totalDistanceMeters"):
                metrics.append(
                    {
                        "metric_type": "distance",
                        "value": distance_m,
                        "unit": "meters",
                        "timestamp": ts_now,
                    }
                )
        except GarminClientError:
            self._log.warning("garmin_sync_stats_skipped")

        if metrics:
            await self.store_metrics(metrics)

        await self._audit(
            action="garmin_sync",
            resource_type="health",
            metadata={
                "steps_records": len(steps_data),
                "hr_records": len(hr_data),
                "sleep_records": len(sleep_data),
                "activity_records": len(activities),
                "total_metrics": len(metrics),
            },
        )

        self._log.info("garmin_sync_complete", total_metrics=len(metrics))

    async def health_check(self) -> bool:
        """Verify Garmin Connect credentials are valid."""
        try:
            await self._ensure_client()
            return True
        except GarminClientError:
            self._log.warning("garmin_health_check_failed")
            return False
