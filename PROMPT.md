# Aegis — Phased Build Prompt for Claude Code

> **Instructions**: Run each phase sequentially. Complete and verify each phase before moving on. Each phase lists exact acceptance criteria — all must pass before proceeding. Read CLAUDE.md first for full architecture, technology decisions, and security constraints.

---

## PHASE 0: Project Scaffolding + Infrastructure Foundation

### What to build:
1. Initialize the monorepo with the exact directory structure defined in CLAUDE.md.
2. Create `docker-compose.yml` with the following services, ALL bound to internal Docker networks only (zero host port bindings except SSH):
   - `postgres` (PostgreSQL 16 with pgvector extension, persistent volume, internal network only)
   - `redis` (Redis 7.4, internal network only, requirepass enabled)
   - `qdrant` (Qdrant latest, internal network only, persistent volume)
   - `minio` (MinIO latest, internal network only, persistent volume)
   - `traefik` (v3, internal routing between services, TLS via self-signedts for inter-service)
   - `cloudflared` (Cloudflare Tunnel container pointing to traefik)
3. Create `docker-compose.prod.yml` override with production-specific settings (resource limits, restart policies, logging drivers).
4. Create three isolated Docker networks: `frontend`, `backend`, `data`. Assign services to minimum-required networks.
5. Write `.env.example` with every variable from CLAUDE.md (no real values).
6. Create `infrastructure/scripts/deploy.sh` — a script that: decrypts SOPS secrets, validates `.env`, runs `docker compose up -d --build`, runs health checks on all services.
7. Create `infrastructure/scripts/backup.sh` — dumps PostgreSQL, encrypts with age, stores in MinIO.
8. Create a `Makefile` with targets: `dev`, `prod`, `backup`, `logs`, `health`, `migrate`, `test`.
9. Set up the Python backend project in `backend/` using `pyproject.toml` with `uv` as the package manager. Pin all dependencies. Include: `fastapi`, `uvicorn`, `celery[redis]`, `sqlalchemy[asyncio]`, `asyncpg`, `alembic`,tpx`, `pydantic-settings`, `structlog`, `cryptography`, `tenacity`, `plaid-python`, `tweepy`, `canvasapi`, `playwright`, `beautifulsoup4`, `qdrant-client`, `sentence-transformers`, `anthropic`, `faster-whisper`, `deepgram-sdk`, `python-jose[cryptography]`, `passlib[bcrypt]`, `factory-boy`, `pytest`, `pytest-asyncio`, `ruff`.
10. Set up the Next.js console in `console/` with: Next.js 15, TypeScript strict mode, Tailwind CSS, shadcn/ui initialized, Biome linter, `@tanstack/react-query`, `zustand`, `d3`, `@vis.js/network`, `recharts`.

### Acceptance criteria:
- `docker compose config` validates without errors
- `docker compose up -d` starts all infrastructure services (postgres, redis, qdrant, minio, traefik)
- `docker compose exec postgres pg_isready` returns success
- `docker compose exec postgres psql -c "CREATE EXTENSION IF NOT EXISTS vector;"` succeeds
- `docker compose exec redis redis-cli ping` returns PONG
- Backend: `cd backend && uv sync` installs without errors
- Console: `cd console && npm install && npm run build` succeeds
- `ruff check backend/` reports zero errors
- Directory structure matches CLAUDE.md exactly

---

## PHASE 1: Core Backend — Security + Auth + Database Models

### What to build:
1. `backend/app/config.py` — Pydantic Settings class loading all env vars with validation. Fail fast on missing required vars.
2. `backend/app/security/encryption.py`:
   - `encrypt_field(plaintext: str, master_key: bytes) -> str` — AES-256-GCM, returns base64 encoded nonce+ciphertext+tag.
   - `decrypt_field(ciphertext: str, master_key: bytes) -> str` — reverse.
   - `encrypt_credential(user_id: str, key: str, value: str)` — store encrypted credential in DB.
   - `decrypt_credential(user_id: str, key: str) -> str` — retrieve and decrypt.
3. `backend/app/security/auth.py`:
   - JWT creation/validation with 15-min access token, 7-day refresh token.
   - Password hashing with bcrypt (12 rounds).
   - TOTP 2FA verification.
   - `get_current_user` FastAPI dependency.
4. `backend/app/security/aud Audit logger that records: timestamp, user_id, action, resource_type, resource_id, ip_address, metadata.
   - Stored in `audit_log` table. Append-only (no UPDATE/DELETE permissions on this table).
5. `backend/app/security/rate_limit.py` — Redis-backed rate limiting middleware.
6. SQLAlchemy models (all in `backend/app/models/`):
   - `User` — single admin user with hashed password, TOTP secret, created_at
   - `Credential` — encrypted API credentials storage (user_id, service_name, encrypted_value)
   - `Transaction` — financial transactions (account, amount, date, category, merchant, encrypted_memo)
   - `Account` — bank/investment accounts (institution, type, balance, last_synced)
   - `EmailDigest` — email summaries (subject, sender, priority, category, encrypted_body_summary, date)
   - `Assignment` — LMS assignments (platform, course, title, due_date, status, type, url)
   - `Contact` — contacts (name, email, phone, source, relationship_strength, last_interaction, notes, encrypted_detactEdge` — graph edges between contacts (contact_a_id, contact_b_id, relationship_type, weight)
   - `Meeting` — meetings (title, start_time, end_time, attendees, encrypted_transcript, summary, action_items)
   - `HealthMetric` — health data (metric_type, value, unit, timestamp, source)
   - `ProductivityLog` — device usage (device, app_name, duration_minutes, category, date)
   - `ContentPost` — generated content (platform, content, posted_at, engagement_metrics, status)
   - `DailyBriefing` — daily digests (date, finance_summary, email_summary, calendar_summary, health_summary, recommendations)
   - `AuditLog` — audit trail (as described above)
7. Alembic setup with initial migration generating all tables.
8. `backend/app/main.py` — FastAPI app factory with:
   - CORS middleware (restrict origins to console URL only)
   - Rate limiting middleware
   - Audit logging middleware
   - Health check endpoint at `/health`
   - OpenAPI schema generation
9. Dockerfiles: `infrastructure/Dockerfile.ap non-root, read-only fs) and `infrastructure/Dockerfile.worker` (same base, runs Celery).

### Acceptance criteria:
- All models generate valid migration with `alembic revision --autogenerate`
- `alembic upgrade head` applies cleanly to fresh PostgreSQL
- Encryption round-trips correctly: encrypt then decrypt returns original value
- JWT creation → validation round-trip works with correct claims
- Audit log writes to database on every API call
- `POST /auth/login` returns JWT pair with correct expiry
- `GET /health` returns 200 with service status
- All Docker images build successfully under 500MB each
- `ruff check backend/` and `pytest backend/tests/` pass
- No secrets appear in any log output (test with structlog redaction)

---

## PHASE 2: Financial Integration (Plaid + Schwab)

### What to build:
1. `backend/app/integrations/plaid_client.py`:
   - Inherits `BaseIntegration`
   - `create_link_token()` — for Plaid Link initialization
   - `exchange_public_token(public_token)` — exchange for access, store encrypted
   - `sync_transactions(start_date, end_date)` — fetch transactions, store in DB
   - `get_balances()` — current balances across all linked accounts
   - `get_recurring()` — identify recurring transactions via Plaid's recurring endpoint
   - All responses audit-logged. Access tokens encrypted at rest.
2. `backend/app/integrations/schwab_client.py`:
   - Inherits `BaseIntegration`
   - `authenticate()` — OAuth flow for Schwab API
   - `get_portfolio()` — current positions, balances, performance
   - `get_transactions()` — trade history
   - `place_trade(symbol, quantity, order_type, action)` — submit trade order (requires explicit confirmation flow)
   - Trade execution MUST require a two-step confirmation: first call returns order preview, second call with confirmation token executes. Never auto-execute trades.
3. `backend/app/services/finance_analyzer.py`:
   - `analyze_spending(period)` — categorized spending breakdown with trends
   - `identify_subscriptions()` — detecs, flag potentially unnecessary ones
   - `affordability_check(amount, category)` — given projected income vs expenses, determine if purchase is affordable
   - `portfolio_daily_brief()` — portfolio performance summary with key movers
   - `investment_insights()` — LLM-powered analysis of portfolio allocation and market context
4. `backend/app/tasks/sync_finances.py` — Celery task running every 6 hours.
5. `backend/app/api/v1/finance.py` — FastAPI router with endpoints:
   - `POST /finance/link` — initiate Plaid Link
   - `POST /finance/link/callback` — handle Plaid Link callback
   - `GET /finance/transactions` — paginated transactions with filters
   - `GET /finance/balances` — current balances
   - `GET /finance/subscriptions` — recurring charges analysis
   - `POST /finance/affordability` — affordability check
   - `GET /finance/portfolio` — investment portfolio
   - `GET /finance/portfolio/brief` — daily portfolio brief
   - `POST /finance/trade` — initiate trade (returns prrade/confirm` — confirm trade execution
6. Tests: Plaid sandbox integration test, Schwab mock tests, finance analyzer unit tests.

### Acceptance criteria:
- Plaid Link token generation works in sandbox mode
- Transaction sync correctly stores encrypted data in PostgreSQL
- Recurring transaction detection identifies test subscriptions
- Affordability check returns accurate projections
- Trade confirmation flow requires two explicit API calls
- All financial data is encrypted at rest (verify by querying DB directly — values unreadable)
- Tests pass with Plaid sandbox credentials

---

## PHASE 3: Email Integration + LMS Assignment Tracking

### What to build:
1. `backend/app/integrations/gmail_client.py`:
   - OAuth 2.0 flow for Gmail API
   - `fetch_new_emails(since)` — retrieve emails since last sync
   - `get_email_body(message_id)` — full email content (encrypted before storage)
   - `list_labels()` — email labels/folders
   - Read-only — never send, delete, or modify emails.
2. `backend/app//canvas_client.py`:
   - Uses `canvasapi` library with personal access token
   - `get_courses()` — list active courses
   - `get_assignments(course_id)` — all assignments with due dates and descriptions
   - `get_grades(course_id)` — current grades
   - `get_announcements(course_id)` — course announcements
3. `backend/app/integrations/blackboard_client.py`:
   - Authenticate via Learn REST API or fall back to Playwright scraping
   - `get_courses()`, `get_assignments()`, `get_grades()` — same interface as Canvas
4. `backend/app/integrations/pearson_scraper.py`:
   - Playwright-based scraper for Mastering Pearson
   - `login()` — automated login with stored credentials
   - `get_assignments()` — scrape assignment list with due dates
   - Robust error handling — selectors may change. Log detailed errors with page screenshots on failure.
5. `backend/app/services/email_analyzer.py`:
   - `categorize_email(email)` — classify into: priority, informational, promotional, junk, academic
   - `dail summarized digest of today's emails by priority
   - `weekly_email_digest()` — weekly productivity report analyzing email patterns, response suggestions
   - `spam_audit()` — identify subscriptions/spam to unsubscribe from, provide direct unsubscribe links where available
   - `extract_academic_items(email)` — detect assignment mentions from Blackboard/Canvas notification emails
   - Uses Claude API for intelligent categorization and summarization
6. `backend/app/services/assignment_tracker.py`:
   - Aggregate assignments from Canvas + Blackboard + Pearson + email extraction
   - `get_upcoming_assignments()` — sorted by due date with difficulty estimate
   - `get_overdue_assignments()` — past-due items
   - `auto_completion_assessment(assignment)` — analyze assignment type and determine if automatable (simple quizzes, etc.) vs needs manual work
   - `generate_reminders()` — create reminder schedule based on due dates and estimated effort
7. Celery tasks: `sync_emails` (every 30 min), `sync_asery 2 hours)
8. API endpoints: `/email/digest`, `/email/weekly`, `/email/spam-audit`, `/assignments/upcoming`, `/assignments/overdue`
9. Tests for each component.

### Acceptance criteria:
- Gmail OAuth flow works and fetches emails (test with real credentials in staging)
- Canvas API returns courses and assignments for canvas.drexel.edu
- Email categorization correctly classifies sample emails into 5 categories
- Assignment aggregation merges results from all three LMS platforms
- All email bodies stored encrypted
- Daily brief generates readable, actionable summary
- Playwright scrapers include retry logic and screenshot-on-failure

---

## PHASE 4: Calendar, Meeting Transcription, and Contact Graph

### What to build:
1. `backend/app/integrations/google_calendar_client.py`:
   - OAuth 2.0 flow
   - `get_events(start, end)` — events within range
   - `get_today_events()` — today's schedule
2. `backend/app/integrations/outlook_client.py`:
   - Microsoft Graph API
   - Same interface as Google Calendar nt
3. `backend/app/services/meeting_transcriber.py`:
   - Accept audio file upload or URL → transcribe via Deepgram or local Whisper
   - `transcribe(audio_path) -> str` — full transcript
   - `summarize_meeting(transcript) -> MeetingSummary` — LLM-generated summary with: key points, action items, follow-ups, decisions made
   - Store transcript encrypted, summary in plaintext
4. `backend/app/services/contact_graph.py`:
   - **This is the core relationship intelligence engine.**
   - `add_contact(name, source, metadata)` — add or merge contact from any source
   - `add_edge(contact_a, contact_b, relationship_type, weight)` — create connection edge
   - `merge_contacts(contact_ids)` — deduplicate contacts from different sources
   - `get_network_graph(center_contact_id, depth)` — return subgraph N degrees from center
   - `shortest_path(from_contact, to_contact)` — compute shortest path for warm intro chains
   - `degree_of_separation(from_contact, to_contact)` — number of hops
   - `classiategorize by: company, industry, relationship strength, last interaction recency
   - `suggest_outreach()` — identify contacts to reconnect with based on time since last interaction and relationship value
   - `enrich_from_meeting(meeting)` — extract attendees from meeting and create/update contacts + edges
   - `enrich_from_messages(messages)` — extract contacts from email/WhatsApp messages
   - Use NetworkX for graph algorithms internally. Store graph in PostgreSQL (`Contact` + `ContactEdge` tables).
5. `backend/app/services/daily_briefing.py`:
   - `generate_morning_brief()` — combines: today's calendar, top priority emails, assignment deadlines, portfolio summary, health stats, contact follow-up reminders, news highlights
   - Output as structured JSON that the console can render
6. API endpoints: `/calendar/today`, `/calendar/events`, `/meetings/upload`, `/meetings/{id}/summary`, `/contacts/graph`, `/contacts/shortest-path`, `/contacts/suggest-outreach`, `/briefing/today`
7. Tests with mock meeio, sample contact networks.

### Acceptance criteria:
- Google Calendar and Outlook sync events correctly
- Meeting transcription produces accurate text from sample audio
- Meeting summaries extract actionable items
- Contact graph correctly computes shortest paths (test with known graph)
- Contact deduplication merges same person from different sources
- Morning briefing aggregates all data sources into coherent summary
- Graph query performance acceptable for 5000+ contacts (benchmark test)

---

## PHASE 5: Social Media Integration + Web Crawling

### What to build:
1. `backend/app/integrations/linkedin_client.py`:
   - Playwright-based scraper (LinkedIn has no feed-reading API for non-partners)
   - `login()` — session-based auth with cookies persistence to minimize logins
   - `scrape_feed(scroll_depth)` — scrape feed posts with anti-detection: randomized delays, realistic scroll patterns, human-like mouse movements
   - `get_connections()` — list all connections with profiles
   - `get_messagesread recent messages
   - `post_content(text, image_url=None)` — publish post via official API (requires approved app)
   - `search_people(query)` — search LinkedIn profiles
   - Rate limit: max 100 page loads per session. Cool down 4+ hours between sessions.
   - Store session cookies encrypted. Rotate user-agent strings.
2. `backend/app/integrations/x_client.py`:
   - X API v2 via `tweepy`
   - `get_home_timeline(count)` — recent feed posts
   - `get_mentions()` — mentions and replies
   - `post_tweet(text)` — publish tweet
   - `search(query)` — search tweets
   - Respect rate limits strictly. Use `tweepy`'s built-in rate limit handling.
3. `backend/app/integrations/whatsapp_bridge.py`:
   - HTTP client to the `whatsapp-bridge` Node.js sidecar container
   - `get_chats()` — list recent chats
   - `get_messages(chat_id, limit)` — read messages (encrypted in transit and at rest)
   - Read-only. Never send messages.
4. `whatsapp-bridge/` — Node.js container:
   - Uses `whatsapp-web.js` lib endpoints: `GET /chats`, `GET /chats/:id/messages`, `GET /status`
   - QR code auth flow (render QR to console for initial scan)
   - Session persistence to avoid re-scanning
   - Health check endpoint
5. `backend/app/integrations/web_crawler.py`:
   - `crawl_url(url) -> str` — extract clean text from any URL
   - `crawl_news(topics, sources)` — aggregate news from predefined sources
   - `discover_events(location, interests)` — find tech/VC/startup events in specified cities
   - Use Playwright for JS-heavy pages, `httpx` + BeautifulSoup for static pages
   - Respect `robots.txt`. Implement polite crawling with delays.
6. `backend/app/integrations/news_aggregator.py`:
   - NewsAPI + RSS feeds for: TechCrunch, The Verge, Hacker News, ArXiv (AI/Robotics), a16z blog, Sequoia blog, Y Combinator blog
   - `get_latest_news(topics)` — aggregated and deduplicated news feed
7. `backend/app/services/social_analyzer.py`:
   - `analyze_linkedin_feed()` — extract: key posts, trending topics, events, notable s posting, VC/founder activity
   - `analyze_x_feed()` — extract: tech news, AI developments, VC insights, event announcements
   - `suggest_connections()` — recommend new connections based on interest alignment and mutual connections
   - `message_priorities()` — rank pending messages by importance and suggest responses
   - `events_digest(cities)` — aggregate events from web crawling + social media for Philadelphia, NYC, and East Coast
8. Celery tasks: `sync_social` (every 2 hours), `run_crawlers` (every 4 hours)
9. API endpoints for all the above.

### Acceptance criteria:
- LinkedIn scraper fetches feed posts with anti-detection measures
- X API integration reads timeline and posts tweets
- WhatsApp bridge starts, shows QR code, reads messages after auth
- Web crawler extracts clean text from 10 sample URLs
- News aggregator returns deduplicated feed from all sources
- Social analyzer produces actionable LinkedIn digest
- Event discovery finds real events in Philadelphia area
- All message conted encrypted
- Rate limits strictly enforced on all scrapers

---

## PHASE 6: Content Engine (RAG + Auto-Posting)

### What to build:
1. `backend/app/services/content_engine.py`:
   - **Knowledge Base Construction:**
     - Ingest top essays and substacks: Paul Graham essays, a16z blog, Sequoia blog, Sam Altman's blog, Elad Gil, Y Combinator blog. Chunk with 512-token windows, 100-token overlap.
     - Embed with `sentence-transformers` (`all-MiniLM-L6-v2`) or OpenAI `text-embedding-3-small`
     - Store in Qdrant collection `knowledge_base`
   - **News Layer:**
     - Daily ingest of latest AI/tech/robotics news and research (from Phase 5 crawlers)
     - Embed and store in Qdrant collection `daily_news` (TTL: 30 days)
   - **Research Layer:**
     - ArXiv papers in AI, robotics, world models. Ingest abstracts + key findings.
     - Qdrant collection `research`
   - **Viral Content Analysis:**
     - Collect top-performing posts from LinkedIn and X (from Phase 5 scrapers)
     - Analyze patterns: format, length, hooks, engagement triggers
     - Store as reference in Qdrant collection `viral_patterns`
2. `backend/app/services/social_poster.py`:
   - `generate_linkedin_post()`:
     - RAG query across all collections for today's most relevant topic
     - Use Claude API with detailed system prompt: "Write a LinkedIn post that is informative, direct, has zero fluff, delivers maximum value to tech founders and builders. Style: authoritative but approachable. Length: 150-300 words. Include a compelling hook in the first line. Reference specific data, research, or insights. Match formatting patterns of top-performing LinkedIn posts (line breaks for readability, no hashtag spam, max 3 relevant hashtags at end). Sound completely human — no AI tells."
     - Return draft for optional review before posting
   - `generate_x_post()`:
     - Same RAG pipeline, but optimized for X format
     - System prompt adjusted for X: "Write a tweet or short thread (max 3 tweets). Punchy, insight-dense, no fluff. Hook must stop t scroll. Include specific numbers, names, or predictions when possible. Match what goes viral in tech/AI X — provocative but substantive takes, contrarian insights, pattern recognition. Zero corporate speak."
   - `auto_publish(platform, content)` — post via LinkedIn API / X API
   - `track_engagement(post_id, platform)` — monitor likes, reposts, comments over 48 hours for feedback loop
3. Celery task: `generate_content` — runs daily at 7 AM. Generates posts, publishes, tracks engagement.
4. API endpoints: `/content/generate`, `/content/preview`, `/content/publish`, `/content/history`, `/content/engagement`

### Acceptance criteria:
- Knowledge base ingested with 1000+ chunks from curated sources
- RAG retrieval returns relevant chunks for given topics
- Generated LinkedIn posts read as human-written, are substantive, and match platform style
- Generated X posts are concise and engaging
- Auto-publishing posts to both platforms via their APIs
- Content preview endpoint returns draft without publishiagement tracking records metrics over time

---

## PHASE 7: Health, Fitness, and Grocery Automation

### What to build:
1. `backend/app/integrations/garmin_client.py`:
   - `garminconnect` library
   - `get_daily_summary()` — steps, calories, heart rate, sleep score
   - `get_workouts()` — exercise sessions with details
   - `get_sleep(date)` — sleep stages, duration, quality
   - `get_body_composition()` — weight, body fat %, muscle mass
2. `backend/app/api/v1/health.py`:
   - `POST /health/apple` — ingest Apple Health export data (JSON from iOS Shortcuts)
   - `GET /health/dashboard` — unified health view
   - `GET /health/sleep` — sleep analysis
   - `GET /health/macros` — macro tracking
   - `GET /health/workouts` — workout history and analysis
   - `POST /health/log-meal` — manual meal logging with macro calculation
   - `GET /health/grocery-list` — auto-generated grocery list
   - `POST /health/grocery-approve` — approve and trigger grocery order
3. `backend/app/services/healtaily_health_summary()` — aggregate Garmin + Apple Health data
   - `sleep_analysis()` — sleep patterns, recommendations based on sleep science
   - `macro_tracker(date)` — track protein (target: 175g), calories (limit: 1900), fats, carbs
   - `workout_analyzer()` — analyze workout patterns, progressive overload tracking, recovery recommendations
   - `generate_grocery_list()`:
     - Based on macro targets (175g protein, <1900 cal)
     - Generate 4-day meal plan optimized for lean muscle gain + fat loss
     - Convert meal plan to grocery list with quantities
     - Use LLM with system prompt grounded in sports nutrition research
   - `body_composition_insights()` — track trends, project timeline to goals
   - `science_tips()` — LLM-generated tips backed by actual research (cite DOIs when possible): workout optimization, recovery, hydration, supplementation
4. Grocery ordering:
   - Generate the list + get approval via console/voice app
   - For actual ordering: create structured output compatitacart or preferred grocery service (full auto-ordering requires manual API setup as no public Instacart API exists — generate a shareable shopping list as the realistic deliverable)
5. Celery tasks: `health_sync` (hourly), `grocery_order` (every 4 days — generates list, sends for approval)

### Acceptance criteria:
- Garmin data syncs correctly (test with real account)
- Apple Health data ingests from Shortcuts-formatted JSON
- Macro tracking correctly calculates daily totals against 175g protein / 1900 cal targets
- Grocery list generated for 4 days aligns with macro targets
- Sleep analysis provides actionable recommendations
- Workout analysis tracks progressive overload
- Health dashboard aggregates all sources

---

## PHASE 8: Web Console (Next.js Dashboard)

### What to build:
A clean, minimal, dark-mode-first dashboard. Design language: think Linear meets Raycast — information dense but not cluttered. Use shadcn/ui components exclusively. No unnecessary animations. Every pixel must serve a pu

1. **Layout**: Sidebar navigation (collapsible) + main content area. Pages:
   - **Dashboard Home** (`/`) — morning briefing view: today's calendar, top 5 email priorities, portfolio snapshot, health stats, assignment deadlines, follow-up reminders. One-glance life overview.
   - **Finance** (`/finance`) — accounts overview, transaction table with filters/search, spending by category (Recharts pie/bar), subscription list with cost analysis, portfolio performance chart, affordability calculator.
   - **Email** (`/email`) — daily digest view, email by category (tabs: Priority, Informational, Academic, Promotional, Junk), weekly productivity analysis, spam audit with one-click unsubscribe list.
   - **Assignments** (`/assignments`) — Kanban-style board (To Do, In Progress, Done, Overdue). Each card shows: course, platform, due date, difficulty estimate, automation potential.
   - **Calendar** (`/calendar`) — week view + agenda view. Shows Google + Outlook merged. Upcoming meetings with transcriptio   - **Contacts** (`/contacts`) — **THE GRAPH VIEW**:
     - Full-screen force-directed graph (vis.js Network) showing all contacts as nodes
     - Node size = relationship strength. Color = category (VC, founder, academic, friend, etc.)
     - Click node → sidebar with full contact profile, interaction history, conversation notes
     - Search bar to find any contact → highlight shortest path from you to them
     - Filters: by company, industry, relationship strength, last interaction
     - "Suggest Outreach" panel showing who to reconnect with
   - **Social** (`/social`) — LinkedIn digest, X digest, trending topics, event recommendations, message priorities.
   - **Content** (`/content`) — today's generated posts (preview), post history with engagement metrics, knowledge base stats, content calendar.
   - **Health** (`/health`) — sleep chart (7-day), workout log, macro tracking with progress bars (protein bar prominently showing /175g), body composition trends, grocery list with approve buttbased tips.
   - **Productivity** (`/productivity`) — device usage breakdown (Mac vs iPhone), app usage time, productive vs unproductive time, dopamine spike analysis, weekly productivity score, science-based improvement tips.
   - **Security** (`/security`) — audit log viewer (filterable), system health status for all integrations (green/yellow/red), last sync times, encryption status, security recommendations from AI analysis.
   - **Settings** (`/settings`) — manage integrations, credentials, notification preferences, health targets.

2. **Auth**: Login page with password + TOTP. Session management via httpOnly secure cookies. Redirect to login if unauthenticated.
3. **API Client**: Generated TypeScript types from backend OpenAPI schema. Use `@tanstack/react-query` for all data fetching with appropriate cache/stale times.
4. **Real-time**: WebSocket connection for live notification badges (new emails, assignment reminders, meeting starting).
5. **Responsive**: Must work on tablet. Mobile is secondaice app covers mobile use case).

### Acceptance criteria:
- All pages render with real data from backend API
- Contact graph renders 100+ nodes smoothly with force-directed layout
- Shortest path search returns and highlights path visually
- Finance charts show real transaction data
- Assignment Kanban is drag-and-drop functional
- Auth flow works with JWT + TOTP
- Dark mode is default, light mode toggle available
- Lighthouse score: Performance >80, Accessibility >90
- Build completes without TypeScript errors

---

## PHASE 9: Voice Mobile App (React Native)

### What to build:
1. React Native app (Expo) with:
   - **Voice Interface**: Hold-to-talk button. Records audio → sends to backend → Whisper transcription → Claude processes query → response streamed back → TTS playback.
   - **Dashboard**: Simplified mobile version of console dashboard (morning briefing, top priorities, quick stats).
   - **Contacts**: Searchable contact list with quick-add. Tap to see profile + interaction history.
   -**: Voice or text journal entries. Stored encrypted. LLM analyzes for patterns and life insights.
   - **Quick Actions**: "Add contact", "Log meal", "Check assignment", "What's my schedule today"
2. Voice pipeline:
   - STT: Deepgram streaming API (lowest latency) or on-device Whisper
   - Processing: Claude API on backend — conversational system prompt that has context of all user's data
   - TTS: Kokoro (open source, runs on backend) or Sesame CSM if VPS has GPU. Fall back to cloud TTS (ElevenLabs / OpenAI TTS) if needed.
3. Apple HealthKit integration via `react-native-health`:
   - Read: steps, workouts, sleep, heart rate, active calories
   - Auto-sync to backend every hour via background task
4. Push notifications for: morning briefing ready, assignment due soon, follow-up reminder, meeting starting.
5. Secure storage: all tokens in Expo SecureStore. Certificate pinning for API communication.

### Acceptance criteria:
- Voice capture → transcription → response → TTS playback completes in <3 seith cloud APIs)
- HealthKit data syncs in background
- Journal entries stored encrypted
- Push notifications deliver reliably
- App builds for iOS via Expo EAS
- Secure storage properly protects tokens

---

## PHASE 10: Integration Testing + Hardening + Deployment

### What to build:
1. End-to-end integration tests:
   - Full data flow: Plaid sync → transaction stored → finance analysis → appears in console
   - Email sync → categorization → daily brief → appears in console
   - Meeting audio → transcription → summary → contacts extracted → graph updated
   - Content generation → preview → publish → engagement tracked
2. Load testing with `locust`:
   - Console API under 200 concurrent requests
   - WebSocket connections (10 simultaneous)
   - Background task queue under full sync load
3. Security hardening:
   - Run `trivy` scan on all Docker images — fix all HIGH/CRITICAL
   - Run `bandit` on Python code — fix all issues
   - Verify no secrets in git history (`trufflehog`)
 n database (spot check queries)
   - Penetration test checklist: SQLi, XSS, CSRF, IDOR, auth bypass
4. Monitoring:
   - Prometheus metrics endpoint on backend
   - Grafana dashboard (optional container) for system monitoring
   - Error alerting: send critical errors to admin email
5. Documentation:
   - README.md with setup instructions
   - API documentation (auto-generated from OpenAPI)
   - Runbook for common operations (restart services, rotate secrets, restore backup)
6. Deployment:
   - Push to Hetzner VPS via SSH
   - `deploy.sh` handles: pull latest, decrypt secrets, rebuild images, apply migrations, restart services, verify health
   - Automated daily backup via cron

### Acceptance criteria:
- All integration tests pass
- No HIGH/CRITICAL vulnerabilities in Docker images
- No `bandit` issues in Python code
- No secrets in git history
- Encrypted PII verified in database
- Backup + restore tested successfully
- Deploy script runs cleanly on fresh VPS
- All services healthy after deployment
- Console accessible only through Cloudflare Tunnel
- Zero public ports on VPS (verified with `nmap`)
