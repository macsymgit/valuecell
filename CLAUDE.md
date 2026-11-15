# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Python coding rules (imports, async-first, loguru logging, error handling, size limits) live in AGENTS.md and apply to all Python changes:

@AGENTS.md

## Repository layout

- `python/` — backend package `valuecell` (Python ≥3.12, managed with `uv`; venv at `python/.venv`). FastAPI server, orchestration core, agents, data adapters.
- `frontend/` — React 19 + React Router 7 (SPA) + Vite + Tailwind 4, packaged as a desktop app with Tauri 2 (`src-tauri/`). Managed with `bun`.
- `docs/` — `CORE_ARCHITECTURE.md`, `CONFIGURATION_GUIDE.md`, `CONTRIBUTE_AN_AGENT.md`. Read these before changing core flow, config, or agents.
- `start.sh` / `start.ps1` — full local dev launch (installs deps, inits DB, starts frontend on :1420 and backend on :8000 with `AGENT_DEBUG_MODE=true`).

## Commands

Backend (run from `python/` unless noted):

```bash
uv sync --group dev                         # install incl. ruff, isort, pytest
uv run python -m valuecell.server.main      # API server (http://localhost:8000/api/v1)
uv run valuecell/server/db/init_db.py       # initialize SQLite DB
uv run pytest valuecell/core/               # what CI runs (plus diff-cover >= 90% on core)
uv run pytest valuecell/core/plan/tests/test_planner.py::test_name   # single test
```

From repo root: `make format` (ruff format + isort), `make lint` (ruff check), `make test`.
CI also checks `ruff format --check` and `isort --check` — run `make format` before committing Python.

Frontend (run from `frontend/`):

```bash
bun install
bun run dev          # dev server on :1420
bun run typecheck    # react-router typegen && tsc
bun run check:fix    # biome lint+format autofix (CI runs `biome ci --diagnostic-level=error ./src`)
bun run build
bun run tauri dev    # desktop shell
```

No frontend test suite exists.

## Backend architecture

Request flow (details in `docs/CORE_ARCHITECTURE.md`):

`server/api/routers/*` → `core/coordinate/orchestrator.py::AgentOrchestrator.process_user_input` → **Super Agent** (`core/super_agent/`) triages: answer directly, or hand off an enriched query → **Planner** (`core/plan/`) builds an `ExecutionPlan`, pausing for human-in-the-loop via `UserInputRequest` when info is missing → **TaskExecutor** (`core/task/`) runs each task by calling an agent over **A2A** (`a2a-sdk`) → agent status events go through `core/event/` (`ResponseRouter` maps events to typed responses, `ResponseBuffer` assigns stable item IDs and aggregates partial chunks) → persisted via `core/conversation/` stores and streamed to the UI.

Planning/execution runs in a background producer, so work continues if the client disconnects; the streaming generator just drains a queue. Keep that decoupling when touching the orchestrator.

### Agents

- Each agent is discovered from a JSON **agent card** in `python/configs/agent_cards/`. `name` must equal the agent class name; `url` sets the host/port the agent's A2A server binds to; `enabled: false` disables it; `metadata.local_agent_class` (`"module.path:ClassName"`) lets the backend import and launch the agent in-process (`core/agent/connect.py::RemoteConnections`). Metadata flags `planner_passthrough` and `hidden` change routing/visibility.
- Agent classes subclass `BaseAgent` (`valuecell.core.types`) and implement async `stream(query, conversation_id, task_id, dependencies)`, yielding events built with `valuecell.core.agent.responses.streaming` helpers (`message_chunk`, `tool_call_started`, `tool_call_completed`, `done`, …). `create_wrapped_agent(cls)` (`core/agent/decorator.py`) wraps them into an A2A server; agents with a `__main__.py` can also run standalone with `python -m valuecell.agents.<name>`.
- Agent implementations mostly wrap `agno` agents. Models come from `valuecell.utils.model.get_model("<ENV_KEY>")`.
- `agents/common/trading/` is a reusable trading-strategy framework (`BaseStrategyAgent`: data → features → decision composer → execution gateway (paper or CCXT live) → portfolio/history); see its `README.md`. `prompt_strategy_agent` and `grid_agent` build on it.

### Configuration

Priority: environment variables > `.env` > YAML in `python/configs/` (`config.yaml`, `providers/*.yaml`, `agents/*.yaml`). Logic in `valuecell/config/` (`loader.py` resolves `${VAR}`, `manager.py` is the API). Agent YAMLs declare `env_overrides` that map env vars (e.g. `RESEARCH_AGENT_MODEL_ID`) to config paths.

The `.env`, SQLite DB (`valuecell.db`), LanceDB and `.knowledge` dirs live in the **system app directory**, not the repo (`valuecell/utils/env.py`): `%APPDATA%\ValueCell` on Windows, `~/Library/Application Support/ValueCell` on macOS, `~/.config/valuecell` on Linux. `.env` is created from `.env.example` on first run.

### Other backend pieces

- `server/` — FastAPI app (`api/app.py`), routers, schemas, SQLAlchemy models/repositories in `server/db/`, services in `server/services/`. `server/main.py` shuts down when it reads `__EXIT__` on stdin (used by the Tauri shell); set `ENV=local_dev` to skip that stdin thread under IDE debuggers.
- `adapters/assets/` — market data adapters (yfinance, akshare, baostock) behind a common base/manager.
- `adapters/models/` — LLM provider factory.
- Tests are colocated in `tests/` subdirectories next to the code they cover.

## Frontend architecture

- Routes declared in `src/routes.ts`; pages under `src/app/`.
- HTTP via `src/lib/api-client.ts` (base URL `VITE_API_BASE_URL`, default `http://localhost:8000/api/v1`); per-domain query hooks in `src/api/` (TanStack Query); client state in `src/store/` (zustand).
- UI primitives are shadcn/Radix components in `src/components/`; i18n via i18next (`src/i18n/`); backend locale files live in `python/configs/locales/`.
- Tauri (`src-tauri/src/backend.rs`) runs the Python backend as a `uv` sidecar (`uv sync`, then `uv run -m valuecell.server.main`) and stops it via the stdin `__EXIT__` command.

## Conventions

- Conventional commits: `type(scope): subject` (`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`).
- Ruff line length is 88.
