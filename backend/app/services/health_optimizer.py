"""Health optimizer — analysis, macro tracking, and grocery list generation."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.health import HealthMetric
from app.security.audit import audit_log

logger = structlog.get_logger()

# Metric types that the Apple Health export may contain.
_APPLE_HEALTH_METRIC_MAP: dict[str, tuple[str, str]] = {
    "HKQuantityTypeIdentifierStepCount": ("steps", "count"),
    "HKQuantityTypeIdentifierActiveEnergyBurned": ("calories_burned", "kcal"),
    "HKQuantityTypeIdentifierBasalEnergyBurned": ("calories_resting", "kcal"),
    "HKQuantityTypeIdentifierHeartRate": ("heart_rate", "bpm"),
    "HKQuantityTypeIdentifierRestingHeartRate": ("resting_heart_rate", "bpm"),
    "HKQuantityTypeIdentifierDistanceWalkingRunning": ("distance", "meters"),
    "HKQuantityTypeIdentifierFlightsClimbed": ("flights_climbed", "count"),
    "HKQuantityTypeIdentifierBodyMass": ("weight", "kg"),
    "HKQuantityTypeIdentifierDietaryProtein": ("protein", "g"),
    "HKQuantityTypeIdentifierDietaryEnergyConsumed": ("calories_consumed", "kcal"),
    "HKQuantityTypeIdentifierDietaryCarbohydrates": ("carbohydrates", "g"),
    "HKQuantityTypeIdentifierDietaryFatTotal": ("fat", "g"),
    "HKQuantityTypeIdentifierDietaryFiber": ("fiber", "g"),
    "HKCategoryTypeIdentifierSleepAnalysis": ("sleep_duration", "hours"),
}


async def ingest_apple_health(
    db: AsyncSession,
    user_id: str,
    data: list[dict],
) -> dict:
    """Parse an Apple Health JSON export and store as HealthMetric records.

    The ``data`` parameter should be a list of dicts, each containing at
    minimum: ``type`` (HealthKit identifier), ``value`` (numeric), and
    ``startDate`` (ISO-8601 string).

    Args:
        db: Async database session.
        user_id: UUID string of the user.
        data: List of Apple Health sample dicts.

    Returns:
        Dict with ingestion statistics.
    """
    uid = uuid.UUID(user_id)
    stored = 0
    skipped = 0

    for sample in data:
        hk_type = sample.get("type", "")
        mapping = _APPLE_HEALTH_METRIC_MAP.get(hk_type)
        if mapping is None:
            skipped += 1
            continue

        metric_type, unit = mapping

        try:
            value = float(sample["value"])
        except (KeyError, ValueError, TypeError):
            skipped += 1
            continue

        ts_raw = sample.get("startDate") or sample.get("date")
        if isinstance(ts_raw, str):
            try:
                ts = datetime.fromisoformat(ts_raw)
            except ValueError:
                skipped += 1
                continue
        elif isinstance(ts_raw, datetime):
            ts = ts_raw
        else:
            skipped += 1
            continue

        record = HealthMetric(
            user_id=uid,
            metric_type=metric_type,
            value=value,
            unit=unit,
            timestamp=ts,
            source="apple_health",
        )
        db.add(record)
        stored += 1

    if stored:
        await db.flush()

    await audit_log(
        db,
        action="apple_health_ingest",
        resource_type="health",
        user_id=uid,
        metadata={"stored": stored, "skipped": skipped},
    )

    logger.info(
        "apple_health_ingested",
        user_id=user_id,
        stored=stored,
        skipped=skipped,
    )

    return {"stored": stored, "skipped": skipped, "total": len(data)}


async def get_daily_health_summary(
    db: AsyncSession,
    user_id: str,
    target_date: date | None = None,
) -> dict:
    """Aggregate all health metrics for a single day.

    Collects the latest value for each metric type recorded on the target
    date and returns a unified summary dict.

    Args:
        db: Async database session.
        user_id: UUID string of the user.
        target_date: The date to summarise. Defaults to today.

    Returns:
        Dict with metric values keyed by metric_type.
    """
    if target_date is None:
        target_date = date.today()

    uid = uuid.UUID(user_id)
    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(HealthMetric)
        .where(
            and_(
                HealthMetric.user_id == uid,
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
        )
        .order_by(HealthMetric.timestamp.desc())
    )
    metrics = result.scalars().all()

    # Aggregate: sum for cumulative metrics, latest for point-in-time
    summable_types = {
        "steps",
        "calories_burned",
        "calories_resting",
        "calories_consumed",
        "distance",
        "flights_climbed",
        "protein",
        "carbohydrates",
        "fat",
        "fiber",
    }

    summary: dict[str, float] = {}
    units: dict[str, str] = {}

    for metric in metrics:
        mt = metric.metric_type
        if mt in summable_types:
            summary[mt] = summary.get(mt, 0.0) + metric.value
        elif mt not in summary:
            # Take the latest reading (query is ordered desc)
            summary[mt] = metric.value
        units.setdefault(mt, metric.unit)

    await audit_log(
        db,
        action="daily_health_summary",
        resource_type="health",
        user_id=uid,
        metadata={"date": target_date.isoformat(), "metric_count": len(summary)},
    )

    logger.info(
        "daily_health_summary",
        user_id=user_id,
        date=target_date.isoformat(),
        metrics=len(summary),
    )

    return {
        "date": target_date.isoformat(),
        "metrics": summary,
        "units": units,
        "source_count": len(metrics),
    }


async def get_macro_tracking(
    db: AsyncSession,
    user_id: str,
    target_date: date | None = None,
) -> dict:
    """Track nutrition / macro intake against configured targets.

    Compares the day's consumed calories and protein against the targets
    defined in application settings (``daily_protein_target_g`` and
    ``daily_calorie_limit``).

    Args:
        db: Async database session.
        user_id: UUID string of the user.
        target_date: The date to track. Defaults to today.

    Returns:
        Dict with actual values, targets, and remaining amounts.
    """
    if target_date is None:
        target_date = date.today()

    settings = get_settings()
    uid = uuid.UUID(user_id)

    day_start = datetime(target_date.year, target_date.month, target_date.day, tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    # Sum nutritional metrics for the day
    macro_types = ("protein", "calories_consumed", "carbohydrates", "fat", "fiber")
    rows = await db.execute(
        select(
            HealthMetric.metric_type,
            func.sum(HealthMetric.value).label("total"),
        )
        .where(
            and_(
                HealthMetric.user_id == uid,
                HealthMetric.metric_type.in_(macro_types),
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
        )
        .group_by(HealthMetric.metric_type)
    )

    actuals: dict[str, float] = {}
    for row in rows:
        actuals[row.metric_type] = round(float(row.total), 1)

    protein_actual = actuals.get("protein", 0.0)
    calories_actual = actuals.get("calories_consumed", 0.0)

    protein_target = float(settings.daily_protein_target_g)
    calorie_target = float(settings.daily_calorie_limit)

    tracking = {
        "date": target_date.isoformat(),
        "protein": {
            "actual_g": protein_actual,
            "target_g": protein_target,
            "remaining_g": round(max(protein_target - protein_actual, 0.0), 1),
            "pct": round(protein_actual / max(protein_target, 1) * 100, 1),
        },
        "calories": {
            "actual_kcal": calories_actual,
            "target_kcal": calorie_target,
            "remaining_kcal": round(max(calorie_target - calories_actual, 0.0), 1),
            "pct": round(calories_actual / max(calorie_target, 1) * 100, 1),
        },
        "carbohydrates_g": actuals.get("carbohydrates", 0.0),
        "fat_g": actuals.get("fat", 0.0),
        "fiber_g": actuals.get("fiber", 0.0),
    }

    await audit_log(
        db,
        action="macro_tracking",
        resource_type="health",
        user_id=uid,
        metadata={"date": target_date.isoformat()},
    )

    logger.info("macro_tracking", user_id=user_id, date=target_date.isoformat())
    return tracking


async def generate_grocery_list(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Generate a grocery list based on macro goals using Claude API.

    Analyses recent macro tracking data and generates a grocery
    recommendation that helps the user meet their protein and calorie
    targets for the upcoming week.

    Falls back to a static template if the LLM is unavailable.

    Args:
        db: Async database session.
        user_id: UUID string of the user.

    Returns:
        Dict with grocery items grouped by category.
    """
    settings = get_settings()
    uid = uuid.UUID(user_id)

    # Gather the last 7 days of macro data for context
    today = date.today()
    weekly_macros: list[dict] = []
    for i in range(7):
        day = today - timedelta(days=i)
        day_data = await get_macro_tracking(db, user_id, day)
        weekly_macros.append(day_data)

    avg_protein = _safe_avg([d["protein"]["actual_g"] for d in weekly_macros])
    avg_calories = _safe_avg([d["calories"]["actual_kcal"] for d in weekly_macros])

    protein_target = settings.daily_protein_target_g
    calorie_limit = settings.daily_calorie_limit

    prompt = (
        "Generate a weekly grocery list optimised for the following goals:\n\n"
        f"Daily protein target: {protein_target}g\n"
        f"Daily calorie limit: {calorie_limit} kcal\n\n"
        f"Over the past week the user averaged {avg_protein:.0f}g protein "
        f"and {avg_calories:.0f} kcal per day.\n\n"
        "Provide a JSON object with grocery items grouped by category "
        "(produce, protein, dairy, grains, snacks, other). Each item should "
        "have 'name', 'quantity', and 'unit'. Focus on high-protein, "
        "moderate-calorie whole foods. Return ONLY valid JSON."
    )

    grocery_list: dict = {}

    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            import json

            raw = message.content[0].text.strip()
            # Strip markdown code fences if present
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            grocery_list = json.loads(raw)
        except Exception as exc:
            logger.warning(
                "grocery_list_llm_failed",
                error=str(type(exc).__name__),
            )
            grocery_list = _fallback_grocery_list(protein_target)
    else:
        grocery_list = _fallback_grocery_list(protein_target)

    await audit_log(
        db,
        action="grocery_list_generate",
        resource_type="health",
        user_id=uid,
        metadata={
            "protein_target": protein_target,
            "calorie_limit": calorie_limit,
            "item_count": sum(len(v) for v in grocery_list.values() if isinstance(v, list)),
        },
    )

    logger.info("grocery_list_generated", user_id=user_id)

    return {
        "grocery_list": grocery_list,
        "generated_at": datetime.now(UTC).isoformat(),
        "targets": {
            "daily_protein_g": protein_target,
            "daily_calorie_limit": calorie_limit,
        },
        "weekly_avg": {
            "protein_g": round(avg_protein, 1),
            "calories_kcal": round(avg_calories, 1),
        },
    }


async def get_health_trends(
    db: AsyncSession,
    user_id: str,
    days: int = 30,
) -> dict:
    """Analyse health metric trends over a given time period.

    For each metric type recorded in the period, computes the daily
    average, min, max, and the trend direction (improving / declining /
    stable).

    Args:
        db: Async database session.
        user_id: UUID string of the user.
        days: Number of days to analyse. Defaults to 30.

    Returns:
        Dict with per-metric trend data.
    """
    uid = uuid.UUID(user_id)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    rows = await db.execute(
        select(
            HealthMetric.metric_type,
            func.avg(HealthMetric.value).label("avg_value"),
            func.min(HealthMetric.value).label("min_value"),
            func.max(HealthMetric.value).label("max_value"),
            func.count(HealthMetric.id).label("data_points"),
        )
        .where(
            and_(
                HealthMetric.user_id == uid,
                HealthMetric.timestamp >= cutoff,
            )
        )
        .group_by(HealthMetric.metric_type)
    )

    trends: dict[str, dict] = {}
    for row in rows:
        trends[row.metric_type] = {
            "avg": round(float(row.avg_value), 2),
            "min": round(float(row.min_value), 2),
            "max": round(float(row.max_value), 2),
            "data_points": row.data_points,
        }

    # Compute first-half vs second-half trend direction
    midpoint = datetime.now(UTC) - timedelta(days=days // 2)

    for metric_type in trends:
        first_half = await db.execute(
            select(func.avg(HealthMetric.value)).where(
                and_(
                    HealthMetric.user_id == uid,
                    HealthMetric.metric_type == metric_type,
                    HealthMetric.timestamp >= cutoff,
                    HealthMetric.timestamp < midpoint,
                )
            )
        )
        second_half = await db.execute(
            select(func.avg(HealthMetric.value)).where(
                and_(
                    HealthMetric.user_id == uid,
                    HealthMetric.metric_type == metric_type,
                    HealthMetric.timestamp >= midpoint,
                )
            )
        )

        avg_first = first_half.scalar() or 0
        avg_second = second_half.scalar() or 0

        if avg_first == 0:
            direction = "stable"
        else:
            pct_change = (float(avg_second) - float(avg_first)) / float(avg_first) * 100
            if pct_change > 5:
                direction = "increasing"
            elif pct_change < -5:
                direction = "decreasing"
            else:
                direction = "stable"

        trends[metric_type]["trend"] = direction

    await audit_log(
        db,
        action="health_trends",
        resource_type="health",
        user_id=uid,
        metadata={"days": days, "metric_count": len(trends)},
    )

    logger.info(
        "health_trends_computed",
        user_id=user_id,
        days=days,
        metrics=len(trends),
    )

    return {
        "period_days": days,
        "trends": trends,
        "computed_at": datetime.now(UTC).isoformat(),
    }


async def get_weekly_trends(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Compute daily health summaries for the past 7 days.

    Returns a list of per-day summaries so the caller can visualise trends
    across the week (steps, sleep, heart rate, etc.).

    Args:
        db: Async database session.
        user_id: UUID string of the user.

    Returns:
        Dict with a list of daily summaries and computed weekly averages.
    """
    uid = uuid.UUID(user_id)
    today = date.today()
    daily_summaries: list[dict] = []

    for i in range(7):
        day = today - timedelta(days=i)
        summary = await get_daily_health_summary(db, user_id, day)
        daily_summaries.append(summary)

    daily_summaries.reverse()  # oldest first

    # Compute weekly averages per metric type
    metric_totals: dict[str, list[float]] = {}
    for day_summary in daily_summaries:
        for metric_type, value in day_summary.get("metrics", {}).items():
            metric_totals.setdefault(metric_type, []).append(float(value))

    weekly_averages: dict[str, float] = {}
    for metric_type, values in metric_totals.items():
        weekly_averages[metric_type] = round(sum(values) / len(values), 2) if values else 0.0

    await audit_log(
        db,
        action="weekly_health_trends",
        resource_type="health",
        user_id=uid,
        metadata={"metric_types": list(weekly_averages.keys())},
    )

    logger.info("weekly_trends_computed", user_id=user_id, days=7)

    return {
        "period": f"{(today - timedelta(days=6)).isoformat()} to {today.isoformat()}",
        "daily_summaries": daily_summaries,
        "weekly_averages": weekly_averages,
    }


async def check_health_goals(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Compare today's metrics against configured health goals.

    Checks daily protein intake vs ``settings.daily_protein_target_g`` and
    daily calorie consumption vs ``settings.daily_calorie_limit``. Also
    evaluates step count against a default 10 000-step goal and sleep
    against a 7-hour target.

    Args:
        db: Async database session.
        user_id: UUID string of the user.

    Returns:
        Dict with goal statuses (met / not_met) and progress percentages.
    """
    settings = get_settings()
    uid = uuid.UUID(user_id)
    today = date.today()

    macro_data = await get_macro_tracking(db, user_id, today)
    summary = await get_daily_health_summary(db, user_id, today)
    metrics = summary.get("metrics", {})

    # Step goal (default 10 000)
    step_goal = 10_000
    steps_actual = metrics.get("steps", 0.0)

    # Sleep goal (default 7 hours)
    sleep_goal_hours = 7.0
    sleep_actual = metrics.get("sleep_duration", metrics.get("sleep_hours", 0.0))

    goals: dict[str, dict] = {
        "protein": {
            "target": f"{settings.daily_protein_target_g}g",
            "actual": f"{macro_data['protein']['actual_g']}g",
            "pct": macro_data["protein"]["pct"],
            "status": "met" if macro_data["protein"]["pct"] >= 100 else "not_met",
        },
        "calories": {
            "target": f"{settings.daily_calorie_limit} kcal",
            "actual": f"{macro_data['calories']['actual_kcal']} kcal",
            "pct": macro_data["calories"]["pct"],
            "status": (
                "met"
                if macro_data["calories"]["actual_kcal"] <= settings.daily_calorie_limit
                else "exceeded"
            ),
        },
        "steps": {
            "target": step_goal,
            "actual": steps_actual,
            "pct": round(steps_actual / max(step_goal, 1) * 100, 1),
            "status": "met" if steps_actual >= step_goal else "not_met",
        },
        "sleep": {
            "target": f"{sleep_goal_hours}h",
            "actual": f"{round(sleep_actual, 1)}h",
            "pct": round(sleep_actual / max(sleep_goal_hours, 0.01) * 100, 1),
            "status": "met" if sleep_actual >= sleep_goal_hours else "not_met",
        },
    }

    await audit_log(
        db,
        action="check_health_goals",
        resource_type="health",
        user_id=uid,
        metadata={
            "date": today.isoformat(),
            "goals_met": sum(1 for g in goals.values() if g["status"] == "met"),
        },
    )

    logger.info(
        "health_goals_checked",
        user_id=user_id,
        goals_met=sum(1 for g in goals.values() if g["status"] == "met"),
    )

    return {
        "date": today.isoformat(),
        "goals": goals,
        "overall_met": sum(1 for g in goals.values() if g["status"] == "met"),
        "total_goals": len(goals),
    }


async def generate_recommendations(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Generate personalised health recommendations using Claude API.

    Gathers the past week of health data plus goal progress and asks the
    LLM for actionable advice. Falls back to static recommendations when
    the API key is not configured.

    Args:
        db: Async database session.
        user_id: UUID string of the user.

    Returns:
        Dict with a list of recommendation strings.
    """
    settings = get_settings()
    uid = uuid.UUID(user_id)

    # Gather context
    goals = await check_health_goals(db, user_id)
    trends = await get_health_trends(db, user_id, days=7)

    goals_summary = "\n".join(
        f"- {name}: {g['actual']} / {g['target']} ({g['status']})"
        for name, g in goals.get("goals", {}).items()
    )
    trends_summary = "\n".join(
        f"- {mt}: avg={info['avg']}, trend={info.get('trend', 'unknown')}"
        for mt, info in trends.get("trends", {}).items()
    )

    prompt = (
        "Based on the following health data, provide 3-5 short, actionable "
        "recommendations to improve overall health. Be specific and practical.\n\n"
        f"Today's goal progress:\n{goals_summary}\n\n"
        f"7-day trends:\n{trends_summary}\n\n"
        f"Targets: {settings.daily_protein_target_g}g protein, "
        f"{settings.daily_calorie_limit} kcal/day\n\n"
        "Return ONLY a JSON array of recommendation strings."
    )

    recommendations: list[str] = []

    if settings.anthropic_api_key:
        try:
            import json

            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = message.content[0].text.strip()
            if raw.startswith("```"):
                lines = raw.split("\n")
                raw = "\n".join(lines[1:-1])
            recommendations = json.loads(raw)
        except Exception as exc:
            logger.warning(
                "recommendations_llm_failed",
                error=str(type(exc).__name__),
            )
            recommendations = _fallback_recommendations()
    else:
        recommendations = _fallback_recommendations()

    await audit_log(
        db,
        action="health_recommendations_generate",
        resource_type="health",
        user_id=uid,
        metadata={"count": len(recommendations)},
    )

    logger.info("health_recommendations_generated", user_id=user_id)

    return {
        "recommendations": recommendations,
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------


def _fallback_recommendations() -> list[str]:
    """Static recommendations when LLM is unavailable."""
    return [
        "Aim for at least 10,000 steps daily to support cardiovascular health.",
        "Prioritize 7-9 hours of sleep each night for optimal recovery.",
        "Distribute protein intake evenly across meals (30-40g per meal).",
        "Stay hydrated -- aim for at least 8 glasses of water per day.",
        "Include 2-3 strength training sessions per week to support muscle mass.",
    ]


def _safe_avg(values: list[float]) -> float:
    """Return the average of a list, defaulting to 0 for empty lists."""
    filtered = [v for v in values if v > 0]
    if not filtered:
        return 0.0
    return sum(filtered) / len(filtered)


def _fallback_grocery_list(protein_target: int) -> dict:
    """Static grocery template when LLM is unavailable."""
    return {
        "produce": [
            {"name": "Broccoli", "quantity": 2, "unit": "lbs"},
            {"name": "Spinach", "quantity": 1, "unit": "bag"},
            {"name": "Sweet Potatoes", "quantity": 4, "unit": "count"},
            {"name": "Bananas", "quantity": 6, "unit": "count"},
            {"name": "Blueberries", "quantity": 2, "unit": "pints"},
        ],
        "protein": [
            {"name": "Chicken Breast", "quantity": 3, "unit": "lbs"},
            {"name": "Ground Turkey (93% lean)", "quantity": 2, "unit": "lbs"},
            {"name": "Salmon Fillets", "quantity": 1, "unit": "lb"},
            {"name": "Eggs", "quantity": 18, "unit": "count"},
        ],
        "dairy": [
            {"name": "Greek Yogurt (plain, nonfat)", "quantity": 2, "unit": "32oz"},
            {"name": "Cottage Cheese", "quantity": 1, "unit": "16oz"},
        ],
        "grains": [
            {"name": "Brown Rice", "quantity": 2, "unit": "lbs"},
            {"name": "Oats", "quantity": 1, "unit": "42oz"},
            {"name": "Whole Wheat Bread", "quantity": 1, "unit": "loaf"},
        ],
        "snacks": [
            {"name": "Protein Bars", "quantity": 1, "unit": "box"},
            {"name": "Almonds", "quantity": 1, "unit": "lb"},
        ],
        "other": [
            {"name": "Olive Oil", "quantity": 1, "unit": "bottle"},
            {"name": "Whey Protein Powder", "quantity": 1, "unit": "container"},
        ],
    }
