# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

```bash
# Dependencies (use uv, not pip)
uv sync                          # Install core deps
uv sync --extra dev              # Install with dev tools
uv sync --all-extras             # Install everything (integrations + ml + dev)

# Run API server locally
uv run uvicorn app.main:app --reload --port 8000

# Run Celery worker
uv run celery -A app.celery_app worker --loglevel=info

# Run Celery beat scheduler
uv run celery -A app.celery_app beat --loglevel=info

# Linting & formatting
uv run ruff check app/ tests/    # Lint
uv run ruff check --fix app/     # Auto-fix
uv run ruff format app/ tests/   # Format

# Tests
uv run pytest                    # Run all tests
uv run pytest tests/test_auth.py # Run single file
uv run pytest -k "test_name"     # Run by name pattern
uv run pytest -x                 # Stop on first failure

# Database migrations
uv run alembic upgrade head      # Apply all migrations
uv run alembic revision --autogenerate -m "description"  # New migration
uv run alembic downgrade -1      # Rollback one step
```

## Architecture

### Request Flow
```
Client → Traefik → FastAPI (main.py) → Audit Middleware → Router → Depends(auth) → Service → DB
```

Every request is audit-logged via middleware in `main.py` (except `/health`). Auth is enforced via `Depends(get_current_user)` from `api/deps.py`.

### Layer Responsibilities
- **`api/v1/`** — HTTP routing, request validation (Pydantic schemas defined inline), auth enforcement. Calls service layer only.
- **`services/`** — Business logic. Stateless async functions taking `(db: AsyncSession, user_id: str, ...)`. Calls integrations for external data.
- **`integrations/`** — External API clients. All inherit `BaseIntegration` ABC. Handle HTTP calls, credential decryption, retry logic. No business logic.
- **`tasks/`** — Celery tasks. Wrap async service calls via `asyncio.run()`. Follow `bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True` pattern.
- **`models/`** — SQLAlchemy 2.0 `Mapped[]` models. All use `UUIDMixin` + `TimestampMixin` from `models/base.py`.
- **`security/`** — Auth (JWT+bcrypt+TOTP), AES-256-GCM encryption, audit logging, Redis-backed rate limiting, token blocklist.

### Key Files
| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI factory, CORS, audit middleware, router registration |
| `app/config.py` | Pydantic Settings — all env vars defined here |
| `app/database.py` | Async SQLAlchemy engine + session factory |
| `app/celery_app.py` | Celery config + Beat schedule (8 periodic tasks) |
| `app/security/encryption.py` | `encrypt_field()`/`decrypt_field()` — AES-256-GCM with AAD context |
| `app/security/auth.py` | `create_access_token()`, `get_current_user()` dependency |
| `app/integrations/base.py` | `BaseIntegration` ABC — all integrations inherit this |

### Implementation Status
All layers are fully implemented:
- **14 database models** with Alembic migrations
- **7 API routers** (auth, finance, email, calendar, content, social, health/productivity)
- **13 integration clients** (Plaid, Gmail, X, Google Calendar, Outlook, Schwab, Canvas, Blackboard, Pearson, LinkedIn, Garmin, NewsAggregator, WebCrawler)
- **10 services** (finance_analyzer, email_analyzer, assignment_tracker, contact_graph, content_engine, daily_briefing, meeting_transcriber, productivity_analyzer, health_optimizer, social_poster)
- **6 Celery tasks** (finance_sync, email_sync, calendar_sync, social_sync, health_sync, content_generation)
- **SSRF protection** via `security/url_validator.py`

### Sensitive Field Encryption
Fields named `encrypted_*` in models use AES-256-GCM. Always use `encrypt_field()`/`decrypt_field()` from `security/encryption.py` with appropriate AAD context (e.g., `f"user:{user_id}:credential:{service_name}"`).

### Ruff Configuration
Line length 99, target Python 3.12. Alembic versions excluded. Tests allow `assert` (`S101`), hardcoded passwords (`S105`, `S106`). FastAPI `Depends()` in defaults (`B008`) is ignored globally.
