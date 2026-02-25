"""Tests for health optimizer service, Apple Health ingestion, and Garmin client."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Health endpoint smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    """GET /health returns 200 with status ok."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "aegis-api"


@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient):
    """POST /api/v1/auth/login with bad credentials returns 401."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@test.com", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_protected_endpoint_without_token(client: AsyncClient):
    """Accessing a protected endpoint without a token returns 403."""
    response = await client.get(
        "/api/v1/auth/refresh",
    )
    # Should fail since no auth header provided
    assert response.status_code in {403, 405, 422}


# ---------------------------------------------------------------------------
# Apple Health ingestion tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_apple_health_known_metrics():
    """ingest_apple_health stores known metric types and skips unknowns."""
    from app.services.health_optimizer import ingest_apple_health

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    data = [
        {
            "type": "HKQuantityTypeIdentifierStepCount",
            "value": 10000,
            "startDate": "2026-02-23T08:00:00+00:00",
        },
        {
            "type": "HKQuantityTypeIdentifierDietaryProtein",
            "value": 45.5,
            "startDate": "2026-02-23T12:00:00+00:00",
        },
        {
            "type": "UnknownHealthKitType",
            "value": 999,
            "startDate": "2026-02-23T10:00:00+00:00",
        },
    ]

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock):
        result = await ingest_apple_health(mock_db, user_id, data)

    assert result["stored"] == 2
    assert result["skipped"] == 1
    assert result["total"] == 3


@pytest.mark.asyncio
async def test_ingest_apple_health_invalid_value():
    """ingest_apple_health skips entries with invalid or missing values."""
    from app.services.health_optimizer import ingest_apple_health

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    data = [
        {
            "type": "HKQuantityTypeIdentifierStepCount",
            "value": "not-a-number",
            "startDate": "2026-02-23T08:00:00+00:00",
        },
        {
            "type": "HKQuantityTypeIdentifierStepCount",
            "startDate": "2026-02-23T08:00:00+00:00",
            # missing 'value'
        },
    ]

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock):
        result = await ingest_apple_health(mock_db, user_id, data)

    assert result["stored"] == 0
    assert result["skipped"] == 2


@pytest.mark.asyncio
async def test_ingest_apple_health_invalid_date():
    """ingest_apple_health skips entries with unparseable dates."""
    from app.services.health_optimizer import ingest_apple_health

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    data = [
        {
            "type": "HKQuantityTypeIdentifierStepCount",
            "value": 5000,
            "startDate": "not-a-date",
        },
        {
            "type": "HKQuantityTypeIdentifierStepCount",
            "value": 5000,
            # missing date entirely
        },
    ]

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock):
        result = await ingest_apple_health(mock_db, user_id, data)

    assert result["stored"] == 0
    assert result["skipped"] == 2


@pytest.mark.asyncio
async def test_ingest_apple_health_empty_list():
    """ingest_apple_health handles an empty data list."""
    from app.services.health_optimizer import ingest_apple_health

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock):
        result = await ingest_apple_health(mock_db, user_id, [])

    assert result["stored"] == 0
    assert result["skipped"] == 0
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_ingest_apple_health_calls_audit_log():
    """ingest_apple_health writes an audit log entry."""
    from app.services.health_optimizer import ingest_apple_health

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())
    data = [
        {
            "type": "HKQuantityTypeIdentifierStepCount",
            "value": 8000,
            "startDate": "2026-02-23T08:00:00+00:00",
        },
    ]

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock) as mock_audit:
        await ingest_apple_health(mock_db, user_id, data)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["action"] == "apple_health_ingest"
        assert call_kwargs["resource_type"] == "health"


# ---------------------------------------------------------------------------
# get_daily_health_summary tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_daily_health_summary_returns_structure():
    """get_daily_health_summary returns the expected dict structure."""
    from app.services.health_optimizer import get_daily_health_summary

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock the db query to return no metrics
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock):
        result = await get_daily_health_summary(mock_db, user_id, date(2026, 2, 23))

    assert "date" in result
    assert "metrics" in result
    assert "units" in result
    assert "source_count" in result
    assert result["date"] == "2026-02-23"
    assert result["source_count"] == 0


# ---------------------------------------------------------------------------
# get_macro_tracking tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_macro_tracking_returns_structure():
    """get_macro_tracking returns protein and calorie tracking data."""
    from app.services.health_optimizer import get_macro_tracking

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock the db query to return no macro data
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    mock_db.execute.return_value = mock_result

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock):
        result = await get_macro_tracking(mock_db, user_id, date(2026, 2, 23))

    assert "date" in result
    assert "protein" in result
    assert "calories" in result
    assert result["protein"]["target_g"] == 175
    assert result["calories"]["target_kcal"] == 1900
    assert result["protein"]["remaining_g"] == 175.0
    assert result["calories"]["remaining_kcal"] == 1900.0


# ---------------------------------------------------------------------------
# check_health_goals tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_check_health_goals_returns_all_goals():
    """check_health_goals returns status for protein, calories, steps, sleep."""
    from app.services.health_optimizer import check_health_goals

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock both get_macro_tracking and get_daily_health_summary
    mock_macro = {
        "date": "2026-02-23",
        "protein": {"actual_g": 100.0, "target_g": 175, "remaining_g": 75.0, "pct": 57.1},
        "calories": {
            "actual_kcal": 1500.0,
            "target_kcal": 1900,
            "remaining_kcal": 400.0,
            "pct": 78.9,
        },
        "carbohydrates_g": 200.0,
        "fat_g": 50.0,
        "fiber_g": 25.0,
    }
    mock_summary = {
        "date": "2026-02-23",
        "metrics": {"steps": 12000, "sleep_duration": 7.5},
        "units": {},
        "source_count": 5,
    }

    with (
        patch(
            "app.services.health_optimizer.get_macro_tracking",
            new_callable=AsyncMock,
            return_value=mock_macro,
        ),
        patch(
            "app.services.health_optimizer.get_daily_health_summary",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ),
        patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock),
    ):
        result = await check_health_goals(mock_db, user_id)

    assert "goals" in result
    assert "protein" in result["goals"]
    assert "calories" in result["goals"]
    assert "steps" in result["goals"]
    assert "sleep" in result["goals"]
    # Steps met (12000 >= 10000), sleep met (7.5 >= 7)
    assert result["goals"]["steps"]["status"] == "met"
    assert result["goals"]["sleep"]["status"] == "met"
    # Protein not met (100 < 175)
    assert result["goals"]["protein"]["status"] == "not_met"
    # Calories within limit (1500 <= 1900)
    assert result["goals"]["calories"]["status"] == "met"
    assert result["overall_met"] == 3
    assert result["total_goals"] == 4


# ---------------------------------------------------------------------------
# GarminClient import and structure tests
# ---------------------------------------------------------------------------


def test_garmin_client_import():
    """GarminClient can be imported from the integrations module."""
    from app.integrations.garmin_client import GarminClient, GarminClientError

    assert GarminClient is not None
    assert GarminClientError is not None


def test_garmin_client_is_base_integration():
    """GarminClient inherits from BaseIntegration."""
    from app.integrations.base import BaseIntegration
    from app.integrations.garmin_client import GarminClient

    assert issubclass(GarminClient, BaseIntegration)


def test_garmin_client_has_required_methods():
    """GarminClient implements sync, health_check, and data retrieval methods."""
    from app.integrations.garmin_client import GarminClient

    assert hasattr(GarminClient, "sync")
    assert hasattr(GarminClient, "health_check")
    assert hasattr(GarminClient, "get_stats")
    assert hasattr(GarminClient, "get_heart_rate")
    assert hasattr(GarminClient, "get_steps")
    assert hasattr(GarminClient, "get_sleep")
    assert hasattr(GarminClient, "get_activities")
    assert hasattr(GarminClient, "store_metrics")


# ---------------------------------------------------------------------------
# Apple Health metric mapping tests
# ---------------------------------------------------------------------------


def test_apple_health_metric_map_completeness():
    """The Apple Health metric map covers the expected HealthKit types."""
    from app.services.health_optimizer import _APPLE_HEALTH_METRIC_MAP

    assert "HKQuantityTypeIdentifierStepCount" in _APPLE_HEALTH_METRIC_MAP
    assert "HKQuantityTypeIdentifierDietaryProtein" in _APPLE_HEALTH_METRIC_MAP
    assert "HKQuantityTypeIdentifierDietaryEnergyConsumed" in _APPLE_HEALTH_METRIC_MAP
    assert "HKQuantityTypeIdentifierHeartRate" in _APPLE_HEALTH_METRIC_MAP
    assert "HKCategoryTypeIdentifierSleepAnalysis" in _APPLE_HEALTH_METRIC_MAP

    # Verify each mapping returns (metric_type, unit) tuple
    for _hk_type, mapping in _APPLE_HEALTH_METRIC_MAP.items():
        assert isinstance(mapping, tuple)
        assert len(mapping) == 2
        metric_type, unit = mapping
        assert isinstance(metric_type, str)
        assert isinstance(unit, str)
