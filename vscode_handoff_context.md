# Project Handoff Context: Sports-Bot v2

**Goal:** Rebuild the fragile Node.js/Playwright sports facility booking bot into a resilient, agentic Python system using `browser-use`, FastAPI, and APScheduler.

**Stack:**
- **Language:** Python 3.11+
- **Web Framework:** FastAPI with Jinja2 templates (Admin UI)
- **Database:** SQLite (local dev fallback) / PostgreSQL (production via asyncpg), managed via SQLModel & Alembic.
- **Agent:** `browser-use` (CDP-based) powered by Google Gemini 2.0 Flash.
- **Scheduling:** APScheduler 3.11.
- **Security:** AES-256-GCM encrypted credentials stored in the DB.
- **Notifications:** Telegram Bot API (error-isolated).

---

## 🟢 What Has Been Completed (Phases 1-5)

The entire core application has been built (34 files, ~3350 lines of code) and pushed to GitHub (`main` branch).

1. **Foundation & Security:**
   - `.env` setup and `.gitignore`.
   - Async SQLAlchemy/SQLModel database engine (`app/database.py`).
   - `BookingTask` and `BookingRun` models.
   - AES-256-GCM encryption for user credentials (`app/security/crypto.py`). **(All 6 tests passing).**
   - *Recent Fix:* Switched `app/database.py` to auto-detect and use SQLite (`aiosqlite`) for local development since Docker Desktop was not running on the host machine.

2. **Booking Agent (`app/agent/`):**
   - `llm_provider.py`: LangChain wrapper for Gemini.
   - `booking_agent.py`: The orchestrator handling retries, exponential backoff (for 429s), screenshot capture, and structured logging.
   - `prompts.py`: Natural language prompts for the LLM based on the actual portal UI.

3. **Scheduler & Notifications:**
   - `app/scheduler/manager.py`: APScheduler configured for IST. Jobs trigger 2 minutes *before* the target time to allow for login overhead.
   - `app/notifications/telegram.py`: Sends async, error-swallowed alerts for success/failure/errors.

4. **API & Admin Panel:**
   - `app/api/`: CRUD endpoints for tasks, run history, and system health. Includes a manual trigger endpoint.
   - `app/main.py`: FastAPI application with lifespan hooks for DB init and scheduler start/stop.
   - *Recent Fix:* Updated the `TemplateResponse` call in `app/main.py` to use keyword arguments (`request=...`, `name=...`, `context=...`) to fix a Starlette 500 Error.
   - `app/templates/dashboard.html` & `static/style.css`: A premium dark-themed, glassmorphic UI.

5. **Docker:**
   - Multi-stage `Dockerfile` including Chromium dependencies for `browser-use`.
   - `docker-compose.yml` for the app and PostgreSQL.

---

## 🔍 Recent UI Discoveries (Portal Mapping)

Before pausing, an AI browser subagent successfully logged into `https://sports.mitwpu.edu.in/login` and mapped the actual flow outside of booking hours. The prompts in `app/agent/prompts.py` were **updated** to reflect this exact flow:

1. **Login:** Email/Password -> "Login" button.
2. **Dashboard:** Click the dark **"Book now"** button.
3. **Sports Grid:** 15 available sports (e.g., "Table_Tennis - 5", "Swimming Pool"). Click **"View Slots"**.
4. **Slots Page:** Cards showing time ranges (e.g., `10:00 AM – 10:50 AM`) and spots (`3/4 spots available`).
   - *Note:* If outside hours, a red **"Ended"** badge appears.
   - Click **"View Spots"**.
5. **Spot Selection:** Pick a specific spot/seat and confirm.

---

## 🔴 What is Remaining (To Do in VS Code)

You are currently at **Phase 6: Local E2E Testing**.

### 1. Start the Server
Since the virtual environment is set up and dependencies are installed (including `aiosqlite`), open a VS Code terminal and run:
```powershell
# Activate venv
.venv\Scripts\Activate.ps1

# Run Alembic migrations (creates SQLite tables in sportsbot.db)
alembic upgrade head

# Start the FastAPI server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### 2. Verify the Dashboard
Open `http://127.0.0.1:8000` in your browser. The 500 error should be fixed, and you should see the dark-themed dashboard.

### 3. Test a Booking Flow
- Open the API docs at `http://127.0.0.1:8000/docs`.
- Use the `POST /api/tasks` endpoint to create a task using your credentials (`samay.gandhi@mitwpu.edu.in` / `Test@@0000`).
  - *Example payload sport:* `"Table_Tennis - 5"`
  - *Example payload time:* `"10:00 AM - 10:50 AM"`
- Either wait for the scheduled time OR hit the `POST /api/tasks/{task_id}/trigger` endpoint to run it immediately.
- Watch the terminal logs. `browser-use` will spin up a headless (or headed, depending on config) Chromium instance and attempt the steps defined in `prompts.py`.
- Check Telegram for the notification.

### 4. Deployment (Phase 7)
Once local testing proves the agent can successfully navigate and book a slot, you can proceed with deploying the Dockerized version (which uses PostgreSQL) to your Oracle Cloud VM.
