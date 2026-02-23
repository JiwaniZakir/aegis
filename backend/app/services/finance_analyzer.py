"""Finance analyzer — spending analysis, subscription detection, and portfolio briefs."""

from __future__ import annotations

import uuid
from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.account import Account
from app.models.transaction import Transaction
from app.security.audit import audit_log

logger = structlog.get_logger()


async def analyze_spending(
    db: AsyncSession,
    user_id: str,
    period: str = "30d",
) -> dict:
    """Categorized spending breakdown with trends.

    Args:
        db: Async database session.
        user_id: The user's UUID string.
        period: Time period string: "7d", "30d", "90d", "365d".

    Returns:
        dict with categories, totals, and period-over-period trend.
    """
    days = _parse_period(period)
    end_date = date.today()
    start_date = end_date - timedelta(days=days)
    prev_start = start_date - timedelta(days=days)

    uid = uuid.UUID(user_id)

    # Get all accounts for the user
    accounts = await db.execute(select(Account.id).where(Account.user_id == uid))
    account_ids = [row[0] for row in accounts.fetchall()]

    if not account_ids:
        return {"categories": {}, "total": 0, "period": period, "trend_pct": 0}

    # Current period spending by category
    current_rows = await db.execute(
        select(
            Transaction.category,
            func.sum(Transaction.amount).label("total"),
            func.count(Transaction.id).label("count"),
        )
        .where(
            and_(
                Transaction.account_id.in_(account_ids),
                Transaction.transaction_date >= start_date,
                Transaction.transaction_date <= end_date,
                Transaction.amount > 0,
            )
        )
        .group_by(Transaction.category)
    )

    categories: dict[str, dict] = {}
    current_total = Decimal("0")
    for row in current_rows:
        cat = row.category or "Uncategorized"
        amount = row.total or Decimal("0")
        categories[cat] = {
            "amount": float(amount),
            "transaction_count": row.count,
        }
        current_total += amount

    # Previous period total for trend calculation
    prev_result = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.account_id.in_(account_ids),
                Transaction.transaction_date >= prev_start,
                Transaction.transaction_date < start_date,
                Transaction.amount > 0,
            )
        )
    )
    prev_total = prev_result.scalar() or Decimal("0")

    trend_pct = 0.0
    if prev_total > 0:
        trend_pct = round(float((current_total - prev_total) / prev_total * 100), 1)

    result = {
        "categories": dict(sorted(categories.items(), key=lambda x: x[1]["amount"], reverse=True)),
        "total": float(current_total),
        "period": period,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "trend_pct": trend_pct,
    }

    await audit_log(
        db,
        action="spending_analysis",
        resource_type="finance",
        user_id=uid,
        metadata={"period": period, "total": float(current_total)},
    )

    logger.info("spending_analysis_complete", user_id=user_id, period=period)
    return result


async def identify_subscriptions(db: AsyncSession, user_id: str) -> list[dict]:
    """Detect recurring charges and flag potentially unnecessary subscriptions.

    Analyses transaction patterns to identify subscriptions. Uses simple
    heuristics (same merchant, consistent amount, regular interval).

    Returns:
        List of subscription dicts with merchant, amount, frequency, flagged status.
    """
    uid = uuid.UUID(user_id)

    accounts = await db.execute(select(Account.id).where(Account.user_id == uid))
    account_ids = [row[0] for row in accounts.fetchall()]

    if not account_ids:
        return []

    cutoff = date.today() - timedelta(days=90)
    txn_result = await db.execute(
        select(Transaction)
        .where(
            and_(
                Transaction.account_id.in_(account_ids),
                Transaction.transaction_date >= cutoff,
                Transaction.is_recurring.is_(True),
            )
        )
        .order_by(Transaction.merchant, Transaction.transaction_date)
    )
    transactions = txn_result.scalars().all()

    # Group by merchant
    merchant_groups: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        if txn.merchant:
            merchant_groups[txn.merchant].append(txn)

    subscriptions = []
    for merchant, txns in merchant_groups.items():
        if len(txns) < 2:
            continue

        amounts = [float(t.amount) for t in txns]
        avg_amount = sum(amounts) / len(amounts)

        # Estimate monthly cost
        dates = sorted([t.transaction_date for t in txns])
        total_days = (dates[-1] - dates[0]).days if len(dates) > 1 else 30
        monthly_cost = round(avg_amount * (30 / max(total_days / len(txns), 1)), 2)

        subscriptions.append(
            {
                "merchant": merchant,
                "average_amount": round(avg_amount, 2),
                "monthly_cost": monthly_cost,
                "occurrences": len(txns),
                "last_charge": str(dates[-1]),
                "flagged": monthly_cost < 5 or len(txns) > 6,
            }
        )

    subscriptions.sort(key=lambda s: s["monthly_cost"], reverse=True)

    await audit_log(
        db,
        action="subscription_analysis",
        resource_type="finance",
        user_id=uid,
        metadata={"subscription_count": len(subscriptions)},
    )

    logger.info("subscription_analysis_complete", user_id=user_id, count=len(subscriptions))
    return subscriptions


async def affordability_check(
    db: AsyncSession,
    user_id: str,
    amount: float,
    category: str = "general",
) -> dict:
    """Check if a purchase is affordable based on income vs expenses projection.

    Uses the last 30 days of transaction data to estimate income and expenses,
    then determines if the requested amount fits within the budget.

    Returns:
        dict with affordable (bool), monthly_income, monthly_expenses,
        available_budget, and recommendation.
    """
    uid = uuid.UUID(user_id)

    accounts = await db.execute(select(Account.id).where(Account.user_id == uid))
    account_ids = [row[0] for row in accounts.fetchall()]

    if not account_ids:
        return {
            "affordable": False,
            "monthly_income": 0,
            "monthly_expenses": 0,
            "available_budget": 0,
            "amount": amount,
            "category": category,
            "recommendation": "No linked accounts found. Cannot assess affordability.",
        }

    cutoff = date.today() - timedelta(days=30)

    # Get income (negative amounts in Plaid = money in)
    income_result = await db.execute(
        select(func.sum(func.abs(Transaction.amount))).where(
            and_(
                Transaction.account_id.in_(account_ids),
                Transaction.transaction_date >= cutoff,
                Transaction.amount < 0,
            )
        )
    )
    monthly_income = float(income_result.scalar() or 0)

    # Get expenses (positive amounts in Plaid = money out)
    expense_result = await db.execute(
        select(func.sum(Transaction.amount)).where(
            and_(
                Transaction.account_id.in_(account_ids),
                Transaction.transaction_date >= cutoff,
                Transaction.amount > 0,
            )
        )
    )
    monthly_expenses = float(expense_result.scalar() or 0)

    available = monthly_income - monthly_expenses
    affordable = amount <= available

    # Generate recommendation
    if affordable:
        pct_of_available = round(amount / max(available, 0.01) * 100, 1)
        recommendation = (
            f"This ${amount:.2f} {category} purchase is within your budget. "
            f"It represents {pct_of_available}% of your available monthly budget."
        )
    else:
        shortfall = amount - available
        recommendation = (
            f"This ${amount:.2f} {category} purchase exceeds your available budget by "
            f"${shortfall:.2f}. Consider delaying or finding savings."
        )

    result = {
        "affordable": affordable,
        "monthly_income": round(monthly_income, 2),
        "monthly_expenses": round(monthly_expenses, 2),
        "available_budget": round(available, 2),
        "amount": amount,
        "category": category,
        "recommendation": recommendation,
    }

    await audit_log(
        db,
        action="affordability_check",
        resource_type="finance",
        user_id=uid,
        metadata={"amount": amount, "category": category, "affordable": affordable},
    )

    logger.info(
        "affordability_check_complete",
        user_id=user_id,
        affordable=affordable,
    )
    return result


async def portfolio_daily_brief(db: AsyncSession, user_id: str) -> dict:
    """Generate a daily portfolio performance summary using Claude for insights.

    Fetches portfolio data and uses the Anthropic API for LLM-powered analysis.

    Returns:
        dict with portfolio summary and AI-generated insights.
    """
    import anthropic

    settings = get_settings()
    uid = uuid.UUID(user_id)

    # Get account balances
    accounts_result = await db.execute(select(Account).where(Account.user_id == uid))
    accounts = accounts_result.scalars().all()

    total_balance = sum(float(a.balance) for a in accounts)
    account_summaries = [
        {
            "institution": a.institution,
            "type": a.account_type,
            "name": a.account_name,
            "balance": float(a.balance),
        }
        for a in accounts
    ]

    # Get recent transactions for context
    cutoff = date.today() - timedelta(days=7)
    all_account_ids = [a.id for a in accounts]

    recent_txns: list[dict] = []
    if all_account_ids:
        txn_result = await db.execute(
            select(Transaction)
            .where(
                and_(
                    Transaction.account_id.in_(all_account_ids),
                    Transaction.transaction_date >= cutoff,
                )
            )
            .order_by(Transaction.transaction_date.desc())
            .limit(20)
        )
        for txn in txn_result.scalars().all():
            recent_txns.append(
                {
                    "amount": float(txn.amount),
                    "date": str(txn.transaction_date),
                    "category": txn.category,
                    "merchant": txn.merchant,
                }
            )

    # Generate AI insights if API key is available
    ai_insights = ""
    if settings.anthropic_api_key:
        try:
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            prompt = (
                f"Provide a brief daily financial summary based on this data:\n\n"
                f"Total Balance: ${total_balance:,.2f}\n"
                f"Accounts: {len(accounts)}\n"
                f"Recent Transactions (last 7 days): {len(recent_txns)}\n\n"
                f"Account breakdown:\n"
            )
            for acct in account_summaries:
                prompt += f"  - {acct['name']} ({acct['type']}): ${acct['balance']:,.2f}\n"

            if recent_txns:
                prompt += "\nRecent spending:\n"
                for txn in recent_txns[:10]:
                    prompt += (
                        f"  - {txn['date']}: {txn['merchant'] or txn['category'] or 'Unknown'}"
                        f" ${txn['amount']:.2f}\n"
                    )

            prompt += (
                "\nProvide 2-3 sentences of actionable financial insight. Be concise and specific."
            )

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            ai_insights = message.content[0].text

        except Exception as exc:
            logger.warning(
                "portfolio_brief_ai_failed",
                error=str(type(exc).__name__),
            )
            ai_insights = "AI insights unavailable."

    result = {
        "date": str(date.today()),
        "total_balance": total_balance,
        "account_count": len(accounts),
        "accounts": account_summaries,
        "recent_transaction_count": len(recent_txns),
        "ai_insights": ai_insights,
    }

    await audit_log(
        db,
        action="portfolio_daily_brief",
        resource_type="finance",
        user_id=uid,
    )

    logger.info("portfolio_brief_generated", user_id=user_id)
    return result


def _parse_period(period: str) -> int:
    """Parse a period string like '30d' into number of days."""
    period = period.strip().lower()
    if period.endswith("d"):
        try:
            return int(period[:-1])
        except ValueError:
            pass
    defaults = {"week": 7, "month": 30, "quarter": 90, "year": 365}
    return defaults.get(period, 30)
