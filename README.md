# 🏟️ Sports Bot v2 — Agentic Booking System

An LLM-driven sports facility booking bot that automates slot booking on the MIT-WPU sports portal. Built with **browser-use** (AI browser agent), **FastAPI**, and **APScheduler** for sub-second scheduling precision.

## Why v2?

The [original bot](https://github.com/Samay4405/sports-bot) (Node.js/Playwright) suffered from:

| Problem | v1 (Node.js) | v2 (Python) |
|---------|-------------|-------------|
| **Selectors** | Hardcoded — broke on UI changes | LLM reads live DOM — adapts automatically |
| **Scheduling** | GitHub Actions (30-120 min delays) | APScheduler in-process (sub-second) |
| **Database** | Neon PostgreSQL (cold-start crashes) | Local PostgreSQL (always warm) |
| **Failures** | Silent | Telegram alerts + full reasoning logs |
| **Retries** | Single attempt | Configurable burst around target time |

## Architecture

```
┌──────────────┐     ┌───────────────┐     ┌──────────────┐
│  Admin Panel  │────▶│   FastAPI      │────▶│  PostgreSQL  │
│  (Jinja2+HTMX)│    │   + Scheduler  │    │  (Docker)    │
└──────────────┘     └───────┬───────┘     └──────────────┘
                             │
                    ┌────────▼────────┐
                    │  browser-use    │──── Gemini 2.0 Flash
                    │  (CDP Agent)    │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  Sports Portal  │
                    │  (mitwpu.edu.in)│
                    └─────────────────┘
```

## Quick Start

### 1. Clone & Setup
```bash
git clone https://github.com/Samay4405/sports-bot-2.0.git
cd sports-bot-2.0
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -e ".[dev]"
```

### 2. Configure
```bash
cp .env.example .env
# Edit .env with your real credentials
```

### 3. Start Services
```bash
docker compose -f docker/docker-compose.yml up -d postgres
alembic upgrade head
uvicorn app.main:app --reload
```

### 4. Access
- **Admin Panel**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

## Environment Variables

See [`.env.example`](.env.example) for all required variables.

## Tech Stack

- **Agent**: `browser-use` + Gemini 2.0 Flash (via `langchain-google-genai`)
- **Backend**: FastAPI + SQLModel + asyncpg
- **Scheduler**: APScheduler 3.11 (in-process, sub-second precision)
- **Frontend**: Jinja2 + HTMX (no React/Node.js needed)
- **Security**: AES-256-GCM credential encryption
- **Notifications**: Telegram Bot API
- **Database**: PostgreSQL 16 (Docker)

## License

MIT
