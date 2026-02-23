"""Tests for health, fitness, and productivity services."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Productivity analyzer tests
# ---------------------------------------------------------------------------


def test_productivity_analyzer_imports():
    """Productivity analyzer functions are importable."""
    from app.services.productivity_analyzer import (
        get_daily_productivity,
        get_productivity_trends,
        get_weekly_report,
        ingest_screen_time,
    )

    assert callable(ingest_screen_time)
    assert callable(get_daily_productivity)
    assert callable(get_productivity_trends)
    assert callable(get_weekly_report)


# ---------------------------------------------------------------------------
# Health optimizer helper tests
# ---------------------------------------------------------------------------


def test_safe_avg_normal():
    """_safe_avg computes the average of positive values."""
    from app.services.health_optimizer import _safe_avg

    assert _safe_avg([10.0, 20.0, 30.0]) == 20.0
    assert _safe_avg([100.0]) == 100.0


def test_safe_avg_filters_zeros():
    """_safe_avg filters out zero values before averaging."""
    from app.services.health_optimizer import _safe_avg

    assert _safe_avg([10.0, 0.0, 20.0]) == 15.0


def test_safe_avg_empty():
    """_safe_avg returns 0.0 for empty lists."""
    from app.services.health_optimizer import _safe_avg

    assert _safe_avg([]) == 0.0
    assert _safe_avg([0.0, 0.0]) == 0.0


def test_fallback_recommendations_structure():
    """Fallback recommendations return a list of actionable strings."""
    from app.services.health_optimizer import _fallback_recommendations

    recs = _fallback_recommendations()
    assert isinstance(recs, list)
    assert len(recs) >= 3
    assert all(isinstance(r, str) for r in recs)
    assert all(len(r) > 10 for r in recs)


def test_fallback_grocery_list_structure():
    """Fallback grocery list returns categorized items."""
    from app.services.health_optimizer import _fallback_grocery_list

    grocery = _fallback_grocery_list(175)
    assert isinstance(grocery, dict)
    assert "produce" in grocery
    assert "protein" in grocery
    assert "dairy" in grocery
    assert "grains" in grocery

    # Each category has items with name, quantity, unit
    for _category, items in grocery.items():
        assert isinstance(items, list)
        for item in items:
            assert "name" in item
            assert "quantity" in item
            assert "unit" in item


# ---------------------------------------------------------------------------
# Health trends tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_health_trends_returns_structure():
    """get_health_trends returns the expected dict structure."""
    from app.services.health_optimizer import get_health_trends

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    # Mock the db query to return no data
    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    mock_db.execute.return_value = mock_result

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock):
        result = await get_health_trends(mock_db, user_id, days=30)

    assert "period_days" in result
    assert "trends" in result
    assert "computed_at" in result
    assert result["period_days"] == 30
    assert isinstance(result["trends"], dict)


@pytest.mark.asyncio
async def test_get_health_trends_calls_audit_log():
    """get_health_trends writes an audit log entry."""
    from app.services.health_optimizer import get_health_trends

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    mock_result = MagicMock()
    mock_result.__iter__ = MagicMock(return_value=iter([]))
    mock_db.execute.return_value = mock_result

    with patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock) as mock_audit:
        await get_health_trends(mock_db, user_id, days=7)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["action"] == "health_trends"
        assert call_kwargs["resource_type"] == "health"


# ---------------------------------------------------------------------------
# Weekly trends tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_weekly_trends_returns_structure():
    """get_weekly_trends returns daily summaries and weekly averages."""
    from app.services.health_optimizer import get_weekly_trends

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    mock_summary = {
        "date": "2026-02-23",
        "metrics": {"steps": 8000, "calories_burned": 300},
        "units": {"steps": "count", "calories_burned": "kcal"},
        "source_count": 2,
    }

    with (
        patch(
            "app.services.health_optimizer.get_daily_health_summary",
            new_callable=AsyncMock,
            return_value=mock_summary,
        ),
        patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock),
    ):
        result = await get_weekly_trends(mock_db, user_id)

    assert "period" in result
    assert "daily_summaries" in result
    assert "weekly_averages" in result
    assert len(result["daily_summaries"]) == 7
    # Weekly averages should contain the metric types
    assert "steps" in result["weekly_averages"]
    assert result["weekly_averages"]["steps"] == 8000.0


# ---------------------------------------------------------------------------
# Recommendations tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_recommendations_without_api_key():
    """generate_recommendations returns fallback recs when no API key."""
    from app.services.health_optimizer import generate_recommendations

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    mock_goals = {
        "date": "2026-02-23",
        "goals": {
            "protein": {
                "target": "175g",
                "actual": "100g",
                "pct": 57.1,
                "status": "not_met",
            },
            "calories": {
                "target": "1900 kcal",
                "actual": "1500 kcal",
                "pct": 78.9,
                "status": "met",
            },
        },
        "overall_met": 1,
        "total_goals": 2,
    }
    mock_trends = {
        "period_days": 7,
        "trends": {"steps": {"avg": 8000, "trend": "stable"}},
        "computed_at": "2026-02-23T00:00:00+00:00",
    }

    with (
        patch(
            "app.services.health_optimizer.check_health_goals",
            new_callable=AsyncMock,
            return_value=mock_goals,
        ),
        patch(
            "app.services.health_optimizer.get_health_trends",
            new_callable=AsyncMock,
            return_value=mock_trends,
        ),
        patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock),
    ):
        result = await generate_recommendations(mock_db, user_id)

    assert "recommendations" in result
    assert "generated_at" in result
    assert isinstance(result["recommendations"], list)
    assert len(result["recommendations"]) >= 3


# ---------------------------------------------------------------------------
# Grocery list tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_grocery_list_without_api_key():
    """generate_grocery_list returns fallback list when no API key."""
    from app.services.health_optimizer import generate_grocery_list

    mock_db = AsyncMock()
    user_id = str(uuid.uuid4())

    mock_macro = {
        "date": "2026-02-23",
        "protein": {"actual_g": 150.0, "target_g": 175, "remaining_g": 25.0, "pct": 85.7},
        "calories": {
            "actual_kcal": 1800.0,
            "target_kcal": 1900,
            "remaining_kcal": 100.0,
            "pct": 94.7,
        },
        "carbohydrates_g": 200.0,
        "fat_g": 60.0,
        "fiber_g": 25.0,
    }

    with (
        patch(
            "app.services.health_optimizer.get_macro_tracking",
            new_callable=AsyncMock,
            return_value=mock_macro,
        ),
        patch("app.services.health_optimizer.audit_log", new_callable=AsyncMock),
    ):
        result = await generate_grocery_list(mock_db, user_id)

    assert "grocery_list" in result
    assert "generated_at" in result
    assert "targets" in result
    assert "weekly_avg" in result
    assert result["targets"]["daily_protein_g"] == 175
    assert result["targets"]["daily_calorie_limit"] == 1900
    # Fallback list should have produce and protein categories
    assert "produce" in result["grocery_list"]
    assert "protein" in result["grocery_list"]


# ---------------------------------------------------------------------------
# API router registration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_summary_endpoint_registered(client):
    """Health summary endpoint is registered."""
    response = await client.get("/api/v1/health-data/summary")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_macros_endpoint_registered(client):
    """Health macros endpoint is registered."""
    response = await client.get("/api/v1/health-data/macros")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_health_trends_endpoint_registered(client):
    """Health trends endpoint is registered."""
    response = await client.get("/api/v1/health-data/trends")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_apple_health_ingest_endpoint_registered(client):
    """Apple Health ingest endpoint is registered."""
    response = await client.post(
        "/api/v1/health-data/apple",
        json={"data": [{"type": "steps", "value": 10000}]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_grocery_list_endpoint_registered(client):
    """Grocery list endpoint is registered."""
    response = await client.post(
        "/api/v1/health-data/grocery-list",
        json={"days": 7},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_screen_time_ingest_endpoint_registered(client):
    """Screen time ingest endpoint is registered."""
    response = await client.post(
        "/api/v1/productivity/screen-time",
        json={"data": [{"app": "Safari", "duration_min": 30}]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_productivity_daily_endpoint_registered(client):
    """Productivity daily endpoint is registered."""
    response = await client.get("/api/v1/productivity/daily")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_productivity_trends_endpoint_registered(client):
    """Productivity trends endpoint is registered."""
    response = await client.get("/api/v1/productivity/trends")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_productivity_weekly_endpoint_registered(client):
    """Productivity weekly endpoint is registered."""
    response = await client.get("/api/v1/productivity/weekly")
    assert response.status_code == 401
