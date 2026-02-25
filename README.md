# Aegis

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.4+-DC382D?logo=redis&logoColor=white)](https://redis.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Self-hosted personal intelligence platform aggregating 15+ data sources with RAG-powered insights and autonomous content generation.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     Single VPS (Docker Compose)                       │
│                                                                       │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────────┐   │
│  │ Traefik  │  │    API    │  │  Worker   │  │  Content Engine  │   │
│  │(internal)│  │ (FastAPI) │  │ (Celery)  │  │  (RAG + Claude)  │   │
│  └──────────┘  └───────────┘  └───────────┘  └──────────────────┘   │
│                                                                       │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────────────────┐  │
│  │ Postgres  │  │   Redis   │  │  Qdrant   │  │      MinIO       │  │
│  │ +pgvector │  │           │  │ (vectors) │  │  (object store)  │  │
│  └───────────┘  └───────────┘  └───────────┘  └──────────────────┘  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐   │
│  │               Cloudflare Tunnel (zero public ports)            │   │
│  └───────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────┘
        │                          │                        │
   ┌────┴────┐              ┌──────┴──────┐          ┌──────┴──────┐
   │   Web   │              │   Mobile    │          │  Automated  │
   │ Console │              │  (Voice UI) │          │  Publishing │
   │(Next.js)│              │(React Native│          │ (LinkedIn/X)│
   └─────────┘              └─────────────┘          └─────────────┘
```

## Data Integrations

| Category | Sources | Method |
|----------|---------|--------|
| **Banking** | Chase, TD, PNC, Discover, Amex | Plaid API (read-only transactions, balances, recurring) |
| **Investments** | Fidelity/Schwab | Schwab API (portfolio reads + trading) |
| **Email** | Gmail | Gmail API + IMAP fallback |
| **Education** | Canvas LMS, Blackboard, Pearson | REST APIs + Playwright scraper |
| **Social** | LinkedIn, X/Twitter | Platform APIs + scraper fallback |
| **Calendar** | Google Calendar, Outlook | Google Calendar API, Microsoft Graph |
| **Messaging** | WhatsApp | whatsapp-web.js Node.js bridge |
| **Health** | Apple Health, Garmin | HealthKit export, Garmin Connect API |
| **Productivity** | Mac Screen Time, iPhone | Custom Swift agent + iOS Shortcuts |
| **News** | NewsAPI, RSS feeds | newsapi-python, feedparser |
| **Web** | General web | Playwright + BeautifulSoup crawler |

## Features

### Personal Intelligence
- **Financial analysis** — Spending trends, recurring charges, investment portfolio tracking via Plaid + Schwab
- **Email intelligence** — Automated categorization, priority scoring, relationship extraction from Gmail
- **Academic tracking** — Assignment deadlines, grade monitoring across Canvas, Blackboard, Pearson
- **Contact graph** — Relationship mapping across email, social, calendar, and messaging
- **Health optimization** — Activity trends and sleep analysis from Apple Health + Garmin

### Content Engine
- **RAG pipeline** — Qdrant vector store with sentence-transformer embeddings over all ingested data
- **Autonomous publishing** — Daily thought-leadership posts to LinkedIn and X, generated from personal knowledge base
- **Claude-powered analysis** — Anthropic Claude API for content generation and insight synthesis

### Security Architecture
- **Zero attack surface** — No public ports; all access through Cloudflare Tunnel
- **AES-256-GCM encryption** — All sensitive data encrypted at rest with authenticated encryption
- **SOPS + age** — Secrets managed with Mozilla SOPS, encrypted with age keys
- **Internal-only routing** — Traefik reverse proxy restricted to Docker network
- **Audit logging** — All data access operations logged with tamper-evident trails

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI 0.115+, Python 3.12+ |
| Task Queue | Celery 5.4+ with Redis broker |
| Database | PostgreSQL 16+ with pgvector |
| Vector Store | Qdrant 1.12+ |
| Object Storage | MinIO |
| LLM | Claude API (Anthropic SDK) |
| Embeddings | sentence-transformers / OpenAI text-embedding-3-small |
| Web Console | Next.js 15, shadcn/ui, Tailwind CSS, Zustand, D3.js |
| Mobile | React Native (Expo SDK 52+), voice UI |
| Infrastructure | Docker Compose, Traefik 3.x, Cloudflare Tunnel |
| Secrets | SOPS + age, Docker Secrets |

## Project Structure

```
aegis/
├── backend/
│   ├── app/
│   │   ├── main.py                    # FastAPI application
│   │   ├── config.py                  # Environment configuration
│   │   ├── celery_app.py              # Task queue setup
│   │   ├── database.py                # Async SQLAlchemy engine
│   │   ├── api/v1/                    # REST endpoints
│   │   │   ├── auth.py                # Authentication
│   │   │   ├── finance.py             # Banking & investments
│   │   │   ├── email.py               # Email intelligence
│   │   │   ├── calendar.py            # Calendar sync
│   │   │   ├── social.py              # Social media
│   │   │   ├── health.py              # Health metrics
│   │   │   └── security.py            # Audit & encryption
│   │   ├── integrations/              # 13 data source clients
│   │   │   ├── plaid_client.py
│   │   │   ├── schwab_client.py
│   │   │   ├── gmail_client.py
│   │   │   ├── canvas_client.py
│   │   │   ├── linkedin_client.py
│   │   │   ├── x_client.py
│   │   │   ├── google_calendar.py
│   │   │   ├── outlook_client.py
│   │   │   ├── whatsapp_bridge.py
│   │   │   ├── garmin_client.py
│   │   │   └── ...
│   │   ├── services/                  # Business logic
│   │   │   ├── finance_analyzer.py
│   │   │   ├── email_analyzer.py
│   │   │   ├── contact_graph.py
│   │   │   ├── content_engine.py
│   │   │   ├── health_optimizer.py
│   │   │   └── daily_briefing.py
│   │   ├── models/                    # SQLAlchemy models
│   │   ├── security/                  # Auth, encryption, audit
│   │   └── tasks/                     # Celery task definitions
│   ├── tests/                         # 207 tests
│   ├── alembic/                       # Database migrations
│   └── pyproject.toml
├── console/                           # Next.js web dashboard
│   └── src/
│       ├── app/                       # 10 dashboard pages
│       ├── components/                # UI components
│       └── lib/                       # API client, state
├── mobile/                            # React Native voice app
│   └── app/                           # Expo Router screens
├── whatsapp-bridge/                   # Node.js WhatsApp sidecar
├── infrastructure/
│   ├── cloudflared/                   # Tunnel configuration
│   ├── traefik/                       # Reverse proxy config
│   ├── postgres/                      # DB initialization
│   └── scripts/                       # deploy.sh, backup.sh, rotate-secrets.sh
├── secrets/                           # SOPS-encrypted credentials
├── docker-compose.yml                 # Development
├── docker-compose.prod.yml            # Production overrides
└── .env.example                       # Environment template
```

## Quick Start

### Prerequisites

- Docker + Docker Compose 2.29+
- Python 3.12+
- Node.js 20+

### Setup

```bash
git clone https://github.com/JiwaniZakir/aegis.git
cd aegis

# Copy environment template
cp .env.example .env
# Edit .env with your API credentials (Plaid, Google, etc.)

# Start all services
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# Access web console
open http://localhost:3000
```

### Development

```bash
# Backend only
cd backend && uv sync && uv run uvicorn app.main:app --reload

# Console only
cd console && npm install && npm run dev

# Run tests
cd backend && uv run pytest
```

## Scheduled Tasks

| Task | Frequency | Description |
|------|-----------|-------------|
| Financial sync | Every 6 hours | Pull transactions and balances via Plaid |
| Email analysis | Every 4 hours | Categorize and extract insights from new emails |
| Calendar sync | Every 2 hours | Sync events from Google Calendar + Outlook |
| Social monitoring | Every 8 hours | Track LinkedIn and X activity |
| Content publishing | Daily 8:00 AM | Generate and publish thought-leadership content |
| Health sync | Daily 6:00 AM | Pull Garmin metrics and Apple Health exports |
| Weekly briefing | Weekly (Monday) | Comprehensive intelligence digest |

## Contributing

See [CONTRIBUTING.md](.github/CONTRIBUTING.md) for guidelines.

## License

MIT License. See [LICENSE](LICENSE) for details.
