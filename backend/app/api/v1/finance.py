"""Finance API endpoints — banking, investments, and analysis."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security.auth import get_current_user
from app.security.rate_limit import rate_limit

logger = structlog.get_logger()

router = APIRouter(prefix="/finance", tags=["finance"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class LinkTokenResponse(BaseModel):
    link_token: str
    expiration: str


class LinkCallbackRequest(BaseModel):
    public_token: str


class LinkCallbackResponse(BaseModel):
    item_id: str
    status: str = "linked"


class TransactionOut(BaseModel):
    amount: float
    date: str
    category: str | None = None
    merchant: str | None = None


class TransactionsResponse(BaseModel):
    transactions: list[TransactionOut]
    count: int
    start_date: str
    end_date: str


class BalanceOut(BaseModel):
    account_id: str
    name: str
    type: str | None = None
    current: float
    available: float | None = None
    currency: str = "USD"


class BalancesResponse(BaseModel):
    balances: list[BalanceOut]
    total: float


class SubscriptionOut(BaseModel):
    merchant: str
    average_amount: float
    monthly_cost: float
    occurrences: int
    last_charge: str
    flagged: bool = False


class SubscriptionsResponse(BaseModel):
    subscriptions: list[SubscriptionOut]
    total_monthly: float


class AffordabilityRequest(BaseModel):
    amount: float = Field(gt=0)
    category: str = "general"


class AffordabilityResponse(BaseModel):
    affordable: bool
    monthly_income: float
    monthly_expenses: float
    available_budget: float
    amount: float
    category: str
    recommendation: str


class PortfolioPositionOut(BaseModel):
    symbol: str
    quantity: float
    market_value: float
    average_price: float
    current_price: float
    asset_type: str = "EQUITY"


class PortfolioAccountOut(BaseModel):
    account_number_masked: str
    type: str
    value: float
    positions: list[PortfolioPositionOut]


class PortfolioResponse(BaseModel):
    accounts: list[PortfolioAccountOut]
    total_value: float


class PortfolioBriefResponse(BaseModel):
    date: str
    total_balance: float
    account_count: int
    accounts: list[dict]
    recent_transaction_count: int
    ai_insights: str


class TradeRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=10, pattern="^[A-Z0-9.]+$")
    quantity: int = Field(gt=0)
    order_type: str = Field(pattern="^(MARKET|LIMIT)$")
    action: str = Field(pattern="^(BUY|SELL)$")
    limit_price: float | None = Field(default=None, gt=0, le=1_000_000)


class TradePreviewResponse(BaseModel):
    preview: dict
    confirmation_token: str
    expires_in_seconds: int


class TradeConfirmRequest(BaseModel):
    confirmation_token: str


class TradeConfirmResponse(BaseModel):
    order_id: str
    status: str
    details: dict


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/link", response_model=LinkTokenResponse)
async def create_link_token(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LinkTokenResponse:
    """Initiate Plaid Link — returns a link_token for the frontend."""
    try:
        from app.integrations.plaid_client import PlaidClient

        client = PlaidClient(str(user.id), db)
        result = await client.create_link_token()
        return LinkTokenResponse(
            link_token=result["link_token"],
            expiration=str(result["expiration"]),
        )
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Plaid integration is not installed",
        ) from exc
    except Exception as exc:
        logger.error("link_token_failed", error=str(type(exc).__name__))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create Plaid Link token",
        ) from exc


@router.post("/link/callback", response_model=LinkCallbackResponse)
async def link_callback(
    body: LinkCallbackRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> LinkCallbackResponse:
    """Handle Plaid Link callback — exchange public token for access token."""
    try:
        from app.integrations.plaid_client import PlaidClient

        client = PlaidClient(str(user.id), db)
        item_id = await client.exchange_public_token(body.public_token)
        return LinkCallbackResponse(item_id=item_id)
    except ImportError as exc:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Plaid integration is not installed",
        ) from exc
    except Exception as exc:
        logger.error("link_callback_failed", error=str(type(exc).__name__))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to exchange Plaid token",
        ) from exc


@router.get("/transactions", response_model=TransactionsResponse)
async def get_transactions(
    start_date: str | None = None,
    end_date: str | None = None,
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TransactionsResponse:
    """Paginated transactions with optional date/category filters."""
    from datetime import timedelta

    from sqlalchemy import and_, select

    from app.models.account import Account
    from app.models.transaction import Transaction

    accounts = await db.execute(select(Account.id).where(Account.user_id == user.id))
    account_ids = [row[0] for row in accounts.fetchall()]

    if not account_ids:
        return TransactionsResponse(
            transactions=[],
            count=0,
            start_date=start_date or "",
            end_date=end_date or "",
        )

    # Parse dates — return 400 for malformed input instead of 500
    from datetime import date as date_type

    try:
        end = date_type.fromisoformat(end_date) if end_date else date_type.today()
        start = date_type.fromisoformat(start_date) if start_date else end - timedelta(days=30)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date format — use YYYY-MM-DD",
        ) from exc

    conditions = [
        Transaction.account_id.in_(account_ids),
        Transaction.transaction_date >= start,
        Transaction.transaction_date <= end,
    ]
    if category:
        conditions.append(Transaction.category == category)

    offset = (page - 1) * page_size
    query = (
        select(Transaction)
        .where(and_(*conditions))
        .order_by(Transaction.transaction_date.desc())
        .offset(offset)
        .limit(page_size)
    )

    result = await db.execute(query)
    txns = result.scalars().all()

    return TransactionsResponse(
        transactions=[
            TransactionOut(
                amount=float(t.amount),
                date=str(t.transaction_date),
                category=t.category,
                merchant=t.merchant,
            )
            for t in txns
        ],
        count=len(txns),
        start_date=str(start),
        end_date=str(end),
    )


@router.get("/balances", response_model=BalancesResponse)
async def get_balances(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BalancesResponse:
    """Current balances across all linked accounts."""
    from sqlalchemy import select

    from app.models.account import Account

    result = await db.execute(select(Account).where(Account.user_id == user.id))
    accounts = result.scalars().all()

    balances = [
        BalanceOut(
            account_id=str(a.id),
            name=a.account_name,
            type=a.account_type,
            current=float(a.balance),
            currency=a.currency,
        )
        for a in accounts
    ]
    total = sum(b.current for b in balances)

    return BalancesResponse(balances=balances, total=total)


@router.get("/subscriptions", response_model=SubscriptionsResponse)
async def get_subscriptions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubscriptionsResponse:
    """Recurring charges analysis."""
    from app.services.finance_analyzer import identify_subscriptions

    subs = await identify_subscriptions(db, str(user.id))
    total_monthly = sum(s["monthly_cost"] for s in subs)

    return SubscriptionsResponse(
        subscriptions=[SubscriptionOut(**s) for s in subs],
        total_monthly=round(total_monthly, 2),
    )


@router.post("/affordability", response_model=AffordabilityResponse)
async def check_affordability(
    body: AffordabilityRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AffordabilityResponse:
    """Affordability check — income vs expenses projection."""
    from app.services.finance_analyzer import affordability_check

    result = await affordability_check(db, str(user.id), body.amount, body.category)
    return AffordabilityResponse(**result)


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    """Investment portfolio from Schwab."""
    try:
        from app.integrations.schwab_client import SchwabClient

        client = SchwabClient(str(user.id), db)
        portfolio = await client.get_portfolio()

        return PortfolioResponse(
            accounts=[
                PortfolioAccountOut(
                    account_number_masked=a["account_number_masked"],
                    type=a["type"],
                    value=a["value"],
                    positions=[PortfolioPositionOut(**p) for p in a["positions"]],
                )
                for a in portfolio["accounts"]
            ],
            total_value=portfolio["total_value"],
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Schwab credentials configured",
        ) from exc
    except Exception as exc:
        logger.error("portfolio_fetch_failed", error=str(type(exc).__name__))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to fetch portfolio data",
        ) from exc


@router.get("/portfolio/brief", response_model=PortfolioBriefResponse)
async def get_portfolio_brief(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioBriefResponse:
    """Daily portfolio brief with AI insights."""
    from app.services.finance_analyzer import portfolio_daily_brief

    result = await portfolio_daily_brief(db, str(user.id))
    return PortfolioBriefResponse(**result)


@router.post(
    "/trade",
    response_model=TradePreviewResponse,
    dependencies=[Depends(rate_limit(limit=5, window_seconds=60))],
)
async def initiate_trade(
    body: TradeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TradePreviewResponse:
    """Initiate a trade — returns a preview, NOT an execution.

    The caller MUST use POST /finance/trade/confirm with the returned
    confirmation_token to actually execute the trade.
    """
    try:
        from app.integrations.schwab_client import SchwabClient

        client = SchwabClient(str(user.id), db)
        result = await client.place_trade(
            symbol=body.symbol,
            quantity=body.quantity,
            order_type=body.order_type,
            action=body.action,
            limit_price=body.limit_price,
        )
        return TradePreviewResponse(**result)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Schwab credentials configured",
        ) from exc
    except Exception as exc:
        logger.error("trade_initiation_failed", error=str(type(exc).__name__))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create trade preview",
        ) from exc


@router.post(
    "/trade/confirm",
    response_model=TradeConfirmResponse,
    dependencies=[Depends(rate_limit(limit=5, window_seconds=60))],
)
async def confirm_trade(
    body: TradeConfirmRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TradeConfirmResponse:
    """Confirm and execute a previously previewed trade.

    Requires the confirmation_token from POST /finance/trade.
    """
    from app.integrations.schwab_client import SchwabClient, SchwabTradeError

    try:
        client = SchwabClient(str(user.id), db)
        result = await client.confirm_trade(body.confirmation_token)
        return TradeConfirmResponse(**result)
    except SchwabTradeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No Schwab credentials configured",
        ) from exc
    except Exception as exc:
        logger.error("trade_confirm_failed", error=str(type(exc).__name__))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to execute trade",
        ) from exc
