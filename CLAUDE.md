# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# ClawdBot Personal Intelligence Platform

## Mission

ClawdBot is a self-hosted personal intelligence platform that aggregates data from financial accounts, email, calendars, social media, device usage, health metrics, and the web — then surfaces actionable insights through a secure web console and a voice-based mobile interface. It also runs an autonomous content engine that publishes daily thought-leadership posts to LinkedIn and X.

Everything runs on a single Hetzner VPS behind SSH tunneling with zero public attack surface. Security is the #1 architectural constraint — every design decision must minimize data leakage risk.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                        HETZNER VPS (Docker Compose)              │
│                                                                  │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │ Traefik │  │   API    │  │  Worker  │  │ Content Engine  │  │
│  │(internal│  │(FastAPI) │  │ (Celery) │  │  (RAG + LLM)    │  │
│  │  only)  │  └──────────┘  └──────────┘  └─────────────────┘  │
│  └─────────┘                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────────┐  │
│  │ Postgres │  │  Redis   │  │  Qdrant  │  │     MinIO        │  │
│  │ +pgvector│  │          │  │ (vectors)│  │  (object store)  │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐│
│  │              Cloudflare Tunnel (cloudflared)                 ││
│  └──────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
```

---

## Technology Stack (Pinned Versions)

### Infrastructure
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| VPS | Hetzner Cloud | CPX41+ | Compute (8 vCPU, 16GB RAM minimum) |
| Container Runtime | Docker + Docker Compose | 27.x / 2.29+ | Container orchestration |
| Reverse Proxy | Traefik | 3.x | Internal service routing, TLS termination |
| Tunnel | Cloudflare Tunnel (`cloudflared`) | latest | Zero-trust access without public ports |
| Secrets | Docker Secrets + SOPS + age | — | Encrypted secrets management |

### Backend
| Component | Technology | Version | Purpose |
|-----------|-----------|---------|---------|
| API Framework | FastAPI | 0.115+ | Core REST/WebSocket API |
| Task Queue | Celery | 5.4+ | Async background jobs (scrapers, analysis) |
| Broker | Redis | 7.4+ | Task broker + caching + pub/sub |
| Database | PostgreSQL | 16+ | Primary data store |
| Vector DB | Qdrant | 1.12+ | RAG embeddings for content engine |
| pgvector | pgvector extension | 0.7+ | Financial/contact embeddings |
| Object Storage | MinIO | latest | File/document storage |
| Python | CPython | 3.12+ | Runtime |

### Data Integrations
| Integration | Method | Library/API |
|------------|--------|-------------|
| Banking (Chase, TD, PNC, Discover, Amex) | Plaid API | `plaid-python` — read-only transactions, balances, recurring |
| Investments (Fidelity) | Schwab API (Fidelity migrated to Schwab) | `schwab-py` — portfolio reads + trading |
| Email | Gmail API + IMAP fallback | `google-api-python-client`, `imapclient` |
| Canvas LMS | Canvas REST API | `canvasapi` — assignments, grades, deadlines |
| Blackboard/Learn | Learn REST API | Direct HTTP via `httpx` |
| Pearson Mastering | Web scraper (no public API) | `playwright` |
| LinkedIn | LinkedIn API (limited) + `playwright` scraper | `linkedin-api` (unofficial), `playwright` |
| X / Twitter | X API v2 (Basic tier minimum) | `tweepy` |
| Google Calendar | Google Calendar API v3 | `google-api-python-client` |
| Outlook Calendar | Microsoft Graph API | `msgraph-sdk` |
| Meeting Transcription | Whisper (local) or Deepgram | `faster-whisper`, `deepgram-sdk` |
| WhatsApp | WhatsApp Web via `whatsapp-web.js` bridge | Node.js sidecar container |
| Web Crawling | Playwright + BeautifulSoup | `playwright`, `beautifulsoup4`, `httpx` |
| News | NewsAPI + RSS feeds | `newsapi-python`, `feedparser` |
| Apple Health | HealthKit export via iOS Shortcuts → API | Custom REST endpoint ingestion |
| Garmin | Garmin Connect API | `garminconnect` |
| Mac Productivity | Custom Swift agent (Screen Time + app usage) | macOS LaunchAgent → API reporting |
| iPhone Productivity | iOS Shortcuts + Screen Time → API | Shortcut automation → API reporting |

### Frontend — Web Console
| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | Next.js (App Router) | 15+ |
| UI Library | shadcn/ui + Tailwind CSS | latest |
| Graph Visualization | D3.js + `@vis.js/network` | — |
| Charts | Recharts | 2.x |
| State | Zustand | 5.x |
| Auth | NextAuth.js with credentials provider | 5.x |

### Frontend — Voice Mobile App
| Component | Technology | Version |
|-----------|-----------|---------|
| Framework | React Native (Expo) | SDK 52+ |
| Voice Model | Sesame CSM / Dia (local) OR OpenAI Realtime API (cloud) | — |
| TTS | Kokoro or Sesame CSM | — |
| STT | Whisper (via API) or Deepgram | — |
| Health Data | `react-native-health` (HealthKit bridge) | — |

### Content Engine
| Component | Technology | Purpose |
|-----------|-----------|---------|
| Embeddings | `sentence-transformers` / OpenAI `text-embedding-3-small` | Document vectorization |
| LLM | Claude API (via Anthropic SDK) | Content generation, analysis |
| RAG Store | Qdrant | Retrieve relevant knowledge chunks |
| Scheduler | Celery Beat | Daily posting schedule |
| Platform Posting | LinkedIn API + X API v2 | Automated publishing |

---

## Directory Structure

```
clawdbot/
├── CLAUDE.md
├── docker-compose.yml
├── docker-compose.prod.yml
├── .env.example                    # Template — NEVER commit .env
├── secrets/                        # SOPS-encrypted secrets
│   ├── .sops.yaml
│   ├── plaid.enc.yaml
│   ├── google.enc.yaml
│   ├── schwab.enc.yaml
│   ├── linkedin.enc.yaml
│   ├── x.enc.yaml
│   ├── anthropic.enc.yaml
│   └── db.enc.yaml
├── infrastructure/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── Dockerfile.console
│   ├── Dockerfile.whatsapp-bridge
│   ├── traefik/
│   │   └── traefik.yml
│   ├── postgres/
│   │   └── init.sql
│   ├── cloudflared/
│   │   └── config.yml
│   └── scripts/
│       ├── deploy.sh
│       ├── backup.sh
│       └── rotate-secrets.sh
├── backend/
│   ├── pyproject.toml              # Use uv for dependency management
│   ├── alembic/                    # Database migrations
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app factory
│   │   ├── config.py               # Settings via pydantic-settings
│   │   ├── security/
│   │   │   ├── auth.py             # JWT + session management
│   │   │   ├── audit.py            # Audit logging for all data access
│   │   │   ├── encryption.py       # AES-256-GCM field encryption
│   │   │   └── rate_limit.py
│   │   ├── models/                 # SQLAlchemy models
│   │   │   ├── user.py
│   │   │   ├── transaction.py
│   │   │   ├── email_digest.py
│   │   │   ├── contact.py
│   │   │   ├── meeting.py
│   │   │   ├── health.py
│   │   │   └── content.py
│   │   ├── api/                    # FastAPI routers
│   │   │   ├── v1/
│   │   │   │   ├── finance.py
│   │   │   │   ├── email.py
│   │   │   │   ├── calendar.py
│   │   │   │   ├── contacts.py
│   │   │   │   ├── social.py
│   │   │   │   ├── health.py
│   │   │   │   ├── productivity.py
│   │   │   │   ├── content.py
│   │   │   │   └── insights.py
│   │   │   └── deps.py             # Shared dependencies
│   │   ├── integrations/           # External API clients
│   │   │   ├── base.py             # BaseIntegration ABC
│   │   │   ├── plaid_client.py
│   │   │   ├── schwab_client.py
│   │   │   ├── gmail_client.py
│   │   │   ├── canvas_client.py
│   │   │   ├── blackboard_client.py
│   │   │   ├── pearson_scraper.py
│   │   │   ├── linkedin_client.py
│   │   │   ├── x_client.py
│   │   │   ├── google_calendar_client.py
│   │   │   ├── outlook_client.py
│   │   │   ├── whatsapp_bridge.py
│   │   │   ├── garmin_client.py
│   │   │   ├── web_crawler.py
│   │   │   └── news_aggregator.py
│   │   ├── services/               # Business logic
│   │   │   ├── finance_analyzer.py
│   │   │   ├── email_analyzer.py
│   │   │   ├── assignment_tracker.py
│   │   │   ├── contact_graph.py
│   │   │   ├── meeting_transcriber.py
│   │   │   ├── productivity_analyzer.py
│   │   │   ├── health_optimizer.py
│   │   │   ├── content_engine.py
│   │   │   ├── social_poster.py
│   │   │   └── daily_briefing.py
│   │   └── tasks/                  # Celery tasks
│   │       ├── finance_sync.py
│   │       ├── email_sync.py
│   │       ├── calendar_sync.py
│   │       ├── social_sync.py
│   │       ├── content_generation.py
│   │       └── health_sync.py
│   └── tests/
│       ├── conftest.py
│       ├── test_finance.py
│       ├── test_email.py
│       ├── test_contacts.py
│       └── ...
├── console/                        # Next.js web console
│   ├── package.json
│   ├── next.config.ts
│   ├── tailwind.config.ts
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx            # Dashboard home
│   │   │   ├── finance/
│   │   │   ├── email/
│   │   │   ├── contacts/           # Graph visualization
│   │   │   ├── calendar/
│   │   │   ├── social/
│   │   │   ├── health/
│   │   │   ├── productivity/
│   │   │   ├── content/
│   │   │   └── security/
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn components
│   │   │   ├── charts/
│   │   │   ├── graphs/
│   │   │   └── ...
│   │   └── lib/
│   │       ├── api.ts              # API client
│   │       └── ...
├── mobile/                         # React Native voice app
│   ├── package.json
│   ├── app/                        # Expo Router
│   ├── components/
│   │   ├── VoiceInterface.tsx
│   │   ├── Dashboard.tsx
│   │   └── ...
│   └── ...
└── whatsapp-bridge/                # Node.js sidecar for WhatsApp Web
    ├── package.json
    ├── Dockerfile
    └── src/
        └── index.ts
```

---

## Security Model

### Threat Model
- **External attackers**: Zero public ports. All access via Cloudflare Tunnel with Zero Trust policies.
- **Data exfiltration**: Field-level AES-256-GCM encryption for all PII (financial data, credentials, messages). Decryption keys held in memory only, derived from master key loaded at boot.
- **Supply chain**: Pin all dependency versions. Use `uv.lock` for Python, `package-lock.json` for Node. Scan with `trivy` in CI.
- **Container escape**: Non-root containers. Read-only filesystems. Drop all capabilities. Seccomp profiles.
- **Credential theft**: All API keys/tokens stored as SOPS-encrypted files, decrypted into Docker secrets at deploy time. Never in environment variables directly.

### Encryption Requirements
1. **At rest**: PostgreSQL with `pgcrypto` + application-level AES-256-GCM for sensitive fields (account numbers, tokens, message bodies).
2. **In transit**: TLS 1.3 between all internal services via Traefik. Cloudflare Tunnel for external access.
3. **Secrets**: SOPS + age for secret files. Docker secrets for runtime injection. Rotate every 90 days via `rotate-secrets.sh`.
4. **Backups**: Encrypted with age before upload to MinIO / offsite storage.

### Access Control
- Single-user system. One admin account with strong passphrase + TOTP 2FA.
- All API endpoints require valid JWT. Token lifetime: 15 minutes access, 7 day refresh.
- Every data access logged in audit table with timestamp, action, IP, and resource accessed.
- Console accessible ONLY through Cloudflare Tunnel with email-based Zero Trust policy.

### Network Security
- Docker network isolation: `frontend`, `backend`, `data` networks. Services only join networks they need.
- No container gets `network_mode: host`.
- Redis and PostgreSQL bound to internal Docker network only — no port exposure to host.
- UFW on host: deny all incoming, allow only SSH (key-based, non-standard port) and cloudflared outbound.

---

## Coding Conventions

### Python (Backend)
- **Formatter**: `ruff format` (line length 99)
- **Linter**: `ruff check` with `select = ["E", "F", "I", "N", "W", "UP", "S", "B", "A", "C4", "SIM", "TCH"]`
- **Type hints**: Required on all function signatures. Use `from __future__ import annotations`.
- **Async**: All I/O-bound operations must be async. Use `httpx.AsyncClient` (never `requests`).
- **Models**: SQLAlchemy 2.0 style with `Mapped[]` type annotations. Alembic for migrations.
- **Pydantic**: v2 for all request/response schemas. Use `model_validator` not deprecated v1 patterns.
- **Error handling**: Never catch bare `Exception`. Use specific exceptions. All integration errors must be caught and logged without leaking credentials.
- **Logging**: `structlog` with JSON output. Never log secrets, tokens, or PII. Redact automatically via custom processor.
- **Tests**: `pytest` + `pytest-asyncio`. Minimum 80% coverage on services layer. Use `factory_boy` for test fixtures.

### TypeScript (Console + Mobile)
- **Formatter/Linter**: Biome
- **Framework**: Next.js 15 App Router with Server Components by default. Client components only when needed.
- **Styling**: Tailwind CSS + shadcn/ui. No custom CSS unless absolutely necessary.
- **State**: Zustand for client state. React Query (`@tanstack/react-query`) for server state.
- **Types**: Strict TypeScript. No `any`. Shared API types generated from backend OpenAPI schema via `openapi-typescript`.

### Git Conventions
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`, `security:`, `refactor:`
- Branch per feature: `feat/finance-integration`, `feat/email-analyzer`, etc.
- Never commit secrets, `.env` files, or unencrypted credentials.
- `.gitignore` must include: `.env`, `secrets/*.yaml` (unencrypted), `node_modules/`, `__pycache__/`, `.venv/`

---

## Integration Patterns

### Standard Integration Client Pattern
Every third-party integration MUST follow this pattern:

```python
# backend/app/integrations/base.py
from abc import ABC, abstractmethod
from app.security.audit import audit_log
from app.security.encryption import decrypt_credential

class BaseIntegration(ABC):
    """All integrations inherit from this. Enforces audit logging and secure credential access."""

    def __init__(self, user_id: str):
        self.user_id = user_id

    async def get_credential(self, key: str) -> str:
        """Fetch and decrypt a stored credential. Never cache in plaintext."""
        return await decrypt_credential(self.user_id, key)

    @abstractmethod
    async def sync(self) -> None:
        """Pull latest data from external service."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Verify connection is alive and credentials are valid."""
        ...
```

### Data Flow Pattern
```
External API → Integration Client → Service Layer → Database
                                  ↘ Audit Log
```
- Integration clients handle API communication ONLY. No business logic.
- Service layer handles analysis, transformation, and storage.
- Every external call is wrapped in retry logic (`tenacity`) with exponential backoff.
- Every data write is audit-logged.

### Celery Task Pattern
```python
@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_task(self, user_id: str):
    """All sync tasks follow this pattern for reliability."""
    ...
```

---

## API Feasibility Notes — READ THIS CAREFULLY

These notes exist to prevent hallucination. Do NOT invent APIs that don't exist.

| Integration | Feasibility | Notes |
|------------|-------------|-------|
| Plaid (Banking) | ✅ Fully supported | Use Plaid Link for token exchange. Requires Plaid account ($). Sandbox available for development. |
| Schwab/Fidelity Trading | ⚠️ Partial | Fidelity migrated brokerage to Schwab. Use `schwab-py` library. Requires Schwab developer account. Read access is solid; trading requires OAuth + individual API approval. Build the interface but expect manual approval step. |
| Gmail API | ✅ Fully supported | OAuth 2.0. Use service account or user consent flow. Requires Google Cloud project. |
| Canvas LMS API | ✅ Fully supported | Personal access token from canvas.drexel.edu. Full assignment/grade/deadline access. |
| Blackboard Learn API | ⚠️ Partial | Requires institutional API access. May need to fall back to `playwright` scraping. |
| Pearson Mastering | ❌ No API | Must use `playwright` browser automation. Fragile — build with robust error handling and selectors. |
| LinkedIn API | ⚠️ Very limited | Official API only allows posting (with approved app). Feed reading and connection data require `playwright` scraping. Against ToS — use rate limiting and stealth measures. Accept risk of account restrictions. |
| X API v2 | ✅ Supported (paid) | Basic tier ($100/mo) for read + write. Free tier is write-only with severe limits. |
| Google Calendar | ✅ Fully supported | OAuth 2.0 via Google Cloud project. |
| Microsoft Graph (Outlook) | ✅ Fully supported | Azure AD app registration required. |
| WhatsApp | ⚠️ Unofficial | No official personal API. Use `whatsapp-web.js` (Node.js library that controls WhatsApp Web via Puppeteer). Requires QR scan auth. Can break with WhatsApp updates. |
| Apple Health | ⚠️ Indirect | No direct API from server. Must use iOS Shortcuts to export data and POST to our API, or build minimal Swift iOS widget. |
| Garmin Connect | ⚠️ Unofficial | `garminconnect` Python library works but is unofficial. Can break. |
| Sesame CSM Voice | ⚠️ Experimental | Open-source but resource-heavy. May need to fall back to Whisper STT + Kokoro TTS pipeline if VPS resources are insufficient. |

---

## Scheduled Tasks

| Schedule | Task | Description |
|----------|------|-------------|
| Every 6 hours | `sync_finances` | Pull latest transactions and balances from Plaid |
| Every 30 min | `sync_emails` | Fetch new emails, run analysis |
| Every 15 min | `sync_calendar` | Sync Google Calendar + Outlook events |
| Every 2 hours | `sync_social` | Scrape LinkedIn feed, X feed |
| Every 4 hours | `run_crawlers` | News aggregation, event discovery |
| Daily 6:00 AM | `daily_briefing` | Generate morning briefing with all digests |
| Daily 7:00 AM | `generate_content` | Create and publish LinkedIn + X posts |
| Weekly Sunday 8 PM | `weekly_digest` | Weekly productivity + email + finance report |
| Every 4 days | `grocery_order` | Generate grocery list based on macro goals, prompt for approval |
| Every hour | `health_sync` | Process any new Apple Health / Garmin data |

---

## Environment Variables Schema

```env
# .env.example — Copy to .env and fill in values. NEVER commit .env.

# === Core ===
ADMIN_EMAIL=
ADMIN_PASSWORD_HASH=
JWT_SECRET=                         # Generate with: openssl rand -hex 32
ENCRYPTION_MASTER_KEY=              # Generate with: openssl rand -hex 32

# === Database ===
POSTGRES_USER=clawdbot
POSTGRES_PASSWORD=                  # Generate with: openssl rand -hex 24
POSTGRES_DB=clawdbot
DATABASE_URL=postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
REDIS_URL=redis://redis:6379/0

# === Plaid ===
PLAID_CLIENT_ID=
PLAID_SECRET=
PLAID_ENV=sandbox                   # Change to 'production' when ready

# === Schwab ===
SCHWAB_APP_KEY=
SCHWAB_APP_SECRET=
SCHWAB_CALLBACK_URL=

# === Google (Gmail + Calendar) ===
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REFRESH_TOKEN=

# === Microsoft (Outlook) ===
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_TENANT_ID=

# === Canvas ===
CANVAS_API_URL=https://canvas.drexel.edu/api/v1
CANVAS_ACCESS_TOKEN=

# === Blackboard ===
BLACKBOARD_URL=https://learn.drexel.edu
BLACKBOARD_USERNAME=
BLACKBOARD_PASSWORD=

# === Pearson ===
PEARSON_URL=
PEARSON_USERNAME=
PEARSON_PASSWORD=

# === LinkedIn ===
LINKEDIN_EMAIL=
LINKEDIN_PASSWORD=
LINKEDIN_ACCESS_TOKEN=              # For official API posting

# === X / Twitter ===
X_API_KEY=
X_API_SECRET=
X_ACCESS_TOKEN=
X_ACCESS_TOKEN_SECRET=
X_BEARER_TOKEN=

# === Anthropic (Claude) ===
ANTHROPIC_API_KEY=

# === WhatsApp ===
WHATSAPP_BRIDGE_URL=http://whatsapp-bridge:3001

# === Garmin ===
GARMIN_EMAIL=
GARMIN_PASSWORD=

# === Deepgram (Transcription) ===
DEEPGRAM_API_KEY=

# === News ===
NEWSAPI_KEY=

# === Cloudflare Tunnel ===
CLOUDFLARE_TUNNEL_TOKEN=

# === Health Goals ===
DAILY_PROTEIN_TARGET_G=175
DAILY_CALORIE_LIMIT=1900
```

---

## Critical Rules for Claude Code

1. **NEVER hallucinate an API that doesn't exist.** If unsure whether an API endpoint exists, check the official docs or note it as needing verification. Refer to the feasibility table above.
2. **NEVER hardcode credentials.** All secrets go through SOPS → Docker secrets → environment injection.
3. **NEVER expose ports to 0.0.0.0.** All services bind to internal Docker networks only.
4. **NEVER store plaintext PII.** Financial data, messages, and personal info must be encrypted at rest with AES-256-GCM.
5. **NEVER skip error handling on integrations.** Every external API call must have try/except with specific exceptions, retry logic, and structured logging.
6. **NEVER use `requests` library.** Use `httpx` with async client for all HTTP calls.
7. **NEVER commit `.env`, unencrypted secrets, or API tokens.**
8. **ALWAYS create database migrations via Alembic** — never raw SQL DDL.
9. **ALWAYS write at minimum a smoke test for every integration client and service.**
10. **ALWAYS follow the directory structure defined above.** Do not deviate or create ad-hoc file locations.
11. **ALWAYS use the BaseIntegration pattern for new integrations.**
12. **Build incrementally.** Complete one phase fully (with tests passing) before starting the next. Do not scaffold empty files — implement or don't create.

## File Writing Rules

- Use the Write tool or `python3 -c "..."` instead of `cat << 'EOF'` heredocs. Heredocs bloat `.claude/settings.local.json`.
- For multi-line file creation, prefer the Write tool.

## Permission Hygiene

- Approve wildcard patterns (like `Bash(ssh:*)`) instead of one-off commands.
- Never embed credentials or large content in Bash permission entries.
- Keep `.claude/settings.local.json` clean — short, reusable wildcard patterns only.
