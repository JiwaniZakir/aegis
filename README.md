<div align="center">

# Aegis

**Self-hosted personal intelligence platform.**

Aggregate 15+ data sources. Surface actionable insights with RAG. Publish autonomously.

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com/)
[![License](https://img.shields.io/badge/License-MIT-58A6FF?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/JiwaniZakir/aegis?style=for-the-badge&color=58A6FF)](https://github.com/JiwaniZakir/aegis/stargazers)
[![Forks](https://img.shields.io/github/forks/JiwaniZakir/aegis?style=for-the-badge&color=58A6FF)](https://github.com/JiwaniZakir/aegis/network/members)

</div>

---

## Overview

Aegis connects to your financial accounts, email, calendars, social media, health devices, and more — then uses a RAG pipeline powered by Claude to deliver intelligent briefings, trend analysis, and autonomous content publishing. Everything runs on a single VPS behind Cloudflare Tunnel with zero public ports and AES-256-GCM encryption at rest.

---

## :sparkles: Features

**Personal Intelligence**
- :bank: **Financial analysis** — Spending trends, recurring charges, and portfolio tracking via Plaid + Schwab
- :envelope: **Email intelligence** — Automated categorization, priority scoring, and relationship extraction
- :mortar_board: **Academic tracking** — Assignment deadlines and grade monitoring across Canvas, Blackboard, and Pearson
- :people_holding_hands: **Contact graph** — Relationship mapping across email, social, calendar, and messaging
- :heart: **Health optimization** — Activity trends and sleep analysis from Apple Health + Garmin

**Content Engine**
- :robot: **RAG pipeline** — Qdrant vector store with sentence-transformer embeddings over all ingested data
- :newspaper: **Autonomous publishing** — Daily thought-leadership posts to LinkedIn and X from your knowledge base
- :brain: **Claude-powered analysis** — Anthropic Claude API for content generation and insight synthesis

**Security-First Architecture**
- :lock: **Zero attack surface** — No public ports; all access through Cloudflare Tunnel
- :shield: **AES-256-GCM encryption** — All sensitive data encrypted at rest with authenticated encryption
- :key: **SOPS + age** — Secrets managed with Mozilla SOPS, encrypted with age keys
- :memo: **Audit logging** — Every data access operation logged with tamper-evident trails

---

## :building_construction: Architecture

```
                         Cloudflare Tunnel (zero public ports)
                                      |
                    +-----------------+-----------------+
                    |                 |                 |
               Web Console      Mobile App       Automated
              (Next.js 15)    (React Native)     Publishing
                    |                 |           (LinkedIn/X)
                    +--------+--------+--------+
                             |
                    +--------v--------+
                    |     Traefik     |         Single VPS
                    |  (internal RP)  |      Docker Compose
                    +--------+--------+
                             |
          +------------------+------------------+
          |                  |                  |
   +------v------+   +------v------+   +-------v--------+
   |   FastAPI    |   |   Celery    |   | Content Engine |
   |   (REST +    |   |  (Workers   |   |  (RAG + Claude |
   |  WebSocket)  |   |   + Beat)   |   |   pipeline)    |
   +------+-------+   +------+------+   +-------+--------+
          |                  |                  |
          +------------------+------------------+
          |            |            |            |
   +------v--+  +-----v---+  +----v----+  +----v----+
   | Postgres |  |  Redis  |  | Qdrant  |  |  MinIO  |
   |+pgvector |  | (broker |  |(vectors)|  |(objects)|
   |          |  |+ cache) |  |         |  |         |
   +----------+  +---------+  +---------+  +---------+
```

---

## :electric_plug: Data Integrations

| Category | Sources | Method |
|:---------|:--------|:-------|
| **Banking** | Chase, TD, PNC, Discover, Amex | Plaid API |
| **Investments** | Fidelity / Schwab | Schwab API (`schwab-py`) |
| **Email** | Gmail | Gmail API + IMAP fallback |
| **Education** | Canvas LMS, Blackboard, Pearson | REST APIs + Playwright |
| **Social** | LinkedIn, X / Twitter | Platform APIs + scraper fallback |
| **Calendar** | Google Calendar, Outlook | Google Calendar API, Microsoft Graph |
| **Messaging** | WhatsApp | `whatsapp-web.js` Node.js bridge |
| **Health** | Apple Health, Garmin | HealthKit export, Garmin Connect API |
| **Productivity** | Mac Screen Time, iPhone | Swift agent + iOS Shortcuts |
| **News** | NewsAPI, RSS feeds | `newsapi-python`, `feedparser` |
| **Web** | General web | Playwright + BeautifulSoup |

---

## :hammer_and_wrench: Tech Stack

<table>
<tr>
<td>

[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Celery](https://img.shields.io/badge/Celery-5.4+-37814A?style=for-the-badge&logo=celery&logoColor=white)](https://docs.celeryq.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-7.4+-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.13+-DC244C?style=for-the-badge&logo=qdrant&logoColor=white)](https://qdrant.tech/)

</td>
<td>

[![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![React Native](https://img.shields.io/badge/React_Native-Expo_52+-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://expo.dev/)
[![Tailwind](https://img.shields.io/badge/Tailwind_CSS-3.x-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white)](https://docker.com/)
[![Traefik](https://img.shields.io/badge/Traefik-3.x-24A1C1?style=for-the-badge&logo=traefikproxy&logoColor=white)](https://traefik.io/)
[![Anthropic](https://img.shields.io/badge/Claude-API-D4A574?style=for-the-badge&logo=anthropic&logoColor=white)](https://anthropic.com/)

</td>
</tr>
</table>

---

## :rocket: Quick Start

### Prerequisites

- Docker + Docker Compose 2.29+
- Python 3.12+
- Node.js 20+

### 1. Clone and configure

```bash
git clone https://github.com/JiwaniZakir/aegis.git
cd aegis
cp .env.example .env
# Edit .env with your API credentials (Plaid, Google, Anthropic, etc.)
```

### 2. Start all services

```bash
docker compose up -d
```

### 3. Run database migrations

```bash
docker compose exec api alembic upgrade head
```

### 4. Open the console

```bash
open http://localhost:3000
```

### Development

```bash
# Backend only (with hot reload)
cd backend && uv sync --extra dev && uv run uvicorn app.main:app --reload

# Install all optional extras (integrations + ml + dev)
cd backend && uv sync --all-extras

# Console only
cd console && npm install && npm run dev

# Run tests (338 tests)
cd backend && uv sync --extra dev && uv run pytest

# Lint + format
make lint
make format
```

See the [`Makefile`](Makefile) for all available commands.

---

## :card_index_dividers: Project Structure

```
aegis/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application factory
│   │   ├── config.py               # Pydantic settings
│   │   ├── celery_app.py           # Task queue + Beat schedule
│   │   ├── database.py             # Async SQLAlchemy engine
│   │   ├── api/v1/                 # 12 REST routers
│   │   ├── integrations/           # 15 data source clients
│   │   ├── services/               # 10 business logic modules
│   │   ├── models/                 # 14 SQLAlchemy models
│   │   ├── security/               # Auth, encryption, audit
│   │   └── tasks/                  # 9 Celery task definitions
│   ├── tests/                      # 338 tests
│   ├── alembic/                    # Database migrations
│   └── pyproject.toml
├── console/                        # Next.js 15 web dashboard
│   └── src/
│       ├── app/                    # 10 dashboard pages
│       ├── components/             # shadcn/ui components
│       └── lib/                    # API client, Zustand stores
├── mobile/                         # React Native voice app (Expo)
├── whatsapp-bridge/                # Node.js WhatsApp sidecar
├── infrastructure/
│   ├── Dockerfile.*                # Multi-stage container builds
│   ├── cloudflared/                # Tunnel configuration
│   ├── traefik/                    # Reverse proxy config
│   ├── postgres/                   # DB initialization
│   └── scripts/                    # deploy.sh, backup.sh, rotate-secrets.sh
├── secrets/                        # SOPS-encrypted credentials
├── docker-compose.yml              # Development stack
├── docker-compose.prod.yml         # Production overrides
├── Makefile                        # Dev workflow commands
└── .env.example                    # Environment template
```

---

## :calendar: Scheduled Tasks

| Task | Frequency | Description |
|:-----|:----------|:------------|
| Financial sync | Every 6 hours | Pull transactions and balances via Plaid |
| Email analysis | Every 30 minutes | Categorize and extract insights from new emails |
| Calendar sync | Every 15 minutes | Sync events from Google Calendar + Outlook |
| Social monitoring | Every 2 hours | Track LinkedIn and X activity |
| Health sync | Hourly | Process Apple Health + Garmin data |
| Content publishing | Daily 7:00 AM | Generate and publish thought-leadership content |
| WhatsApp sync | Every 30 minutes | Sync messages via WhatsApp bridge |
| Meeting transcription | Every 2 hours | Transcribe and analyze recordings |
| Garmin sync | Every 4 hours | Pull fitness and sleep metrics |

---

## :handshake: Contributing

Contributions are welcome. Please read the [contributing guidelines](.github/CONTRIBUTING.md) before opening a pull request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feat/my-feature`)
3. Commit your changes (`git commit -m 'feat: add my feature'`)
4. Push to the branch (`git push origin feat/my-feature`)
5. Open a Pull Request

This project follows [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `chore:`, `docs:`, `security:`).

---

## :page_facing_up: License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built by [Zakir Jiwani](https://github.com/JiwaniZakir)

</div>
