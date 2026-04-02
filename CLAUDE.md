# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DailyScholar v3.0** - a single-process Python app combining FastAPI backend, built-in scheduler, and Vue 3 SPA frontend. It fetches papers from arXiv, uses LLM to score relevance, translates to Chinese, and pushes notifications via a multi-channel notification system.

**Port**: 20001 | **Main Entry**: [app.py](app.py) | **API Docs**: http://localhost:20001/docs

## Development Commands

```bash
pip install -r requirements.txt
python app.py                      # Starts API + scheduler + frontend
pytest tests                       # Run all tests
pytest tests/test_setup_api.py -k test_db_connection_success  # Single test
```

No formal lint/type-check config exists. Ruff has been used locally before (`.ruff_cache/` exists) but no config file is checked in.

## Architecture

### Data Flow Pipeline
```
arXiv API → papers_raw (DB) → LLM Filter (100pt scoring) → Translation → papers_relevant → paper_queue → Notification Push
```

### Backend Structure
- **All routes live in `app.py`** — there are no separate router modules
- Routes use Pydantic `BaseModel` request bodies
- Standard response shape: `{"success": bool, "data": ..., "message": ...}`

### Service Modules (`services/`)

| Service | Purpose |
|---------|---------|
| [arxiv_service.py](services/arxiv_service.py) | Fetch papers from arXiv API (category codes + keywords) |
| [llm_filter_service.py](services/llm_filter_service.py) | AI relevance scoring via OpenAI-compatible API, 100-point scale |
| [translation_service.py](services/translation_service.py) | Chinese/English translation of titles and abstracts |
| [mysql_service.py](services/mysql_service.py) | Thread-safe DB ops (`threading.local()`), auto-migration, supports **both MySQL and SQLite** |
| [prompt_service.py](services/prompt_service.py) | Centralized prompt template management with DB override |
| [notify_service.py](services/notify_service.py) | **Unified notification dispatch** — single-channel model with DB-configured routing |
| [notify.py](services/notify.py) | Low-level push channel implementations (forked from qinglong) |
| [paper_queue_service.py](services/paper_queue_service.py) | Push queue management, prevents duplicate notifications |

### Multi-Channel Notification Architecture

`NotifyService` is the single notification entry point. It uses a **channel registry pattern**:

1. `NotifyService` reads config from DB (`notify` key), identifies the `active_channel`
2. `dispatch_single_channel()` routes to the correct sender based on channel `send_mode`:
   - **`adapter`** channels (e.g., `dingtalk_app`) instantiate a service class directly
   - **`direct`** channels (e.g., `console`, `bark`, `telegram`) call functions in `notify.py` via `NOTIFY_CHANNEL_FUNCTIONS` mapping
3. Supported channels: `console`, `bark`, `dingtalk_app`, `dingtalk_webhook`, `feishu`, `telegram`, `smtp`, `wxpusher`
4. Channel specs are defined in `CHANNEL_REGISTRY` with `required_keys`, `optional_keys`, `send_mode`, `supports_markdown`

When adding a new notification channel: add entry to `CHANNEL_REGISTRY` in notify_service.py, implement the send function in notify.py, and add mapping in `NOTIFY_CHANNEL_FUNCTIONS`.

### Prompt Management

Prompts are centralized in `prompt_service.py`:
- Default prompts in `DEFAULT_PROMPT_CONFIG` dict
- DB override via `load_config_from_db("prompt_config")` — DB values take precedence
- Templates use `{{variable}}` syntax, rendered via `render_template()` or `get_rendered_prompt()`
- **Never hardcode LLM prompts in other modules** — always use `get_prompt(key)` or `get_rendered_prompt()`

### Key Design Patterns

**1. Configuration Hierarchy** (lowest → highest priority):
- `config.py` defaults → `runtime_config.json` (legacy) → Database `system_config` table (highest)

**2. Thread-Safe Database**: Always use:
```python
conn = get_mysql_connection()
with conn.cursor() as cursor:
    cursor.execute(sql)
conn.commit()
```
Never call `pymysql.connect()` directly or share connections across threads.

**3. Background Processing**: Producer-consumer pattern — main thread fetches to `papers_raw`, background thread processes (`processed=0` records) via LLM filter + translation.

**4. Auto-Migration**: `_ensure_tables_exist()` in mysql_service.py automatically adds missing columns.

## Database

Supports MySQL and SQLite (configurable via `ARXIV_CONFIG['mysql']['db_type']`, SQLite path in `sqlite_path`).

Tables:
- `papers_raw`: Original papers with `processed` flag
- `papers_relevant`: Filtered papers with translations, scores, `is_pushed` flag
- `paper_queue`: Push queue
- `system_config`: Runtime config storage

**The `Stars` column stores 0-100 scores** (not 1-5 stars) for backwards compatibility.

## Frontend

Single-file Vue 3 SPA in [static/index.html](static/index.html) using CDN-loaded Vue, Tailwind, Phosphor icons, and Chart.js. No build pipeline — do not introduce one unless explicitly asked.

## Code Style

- **Comments, docstrings, log messages**: Simplified Chinese (中文)
- **Variable/function names**: English `snake_case`
- **Class names**: English `CamelCase`
- **Internal helpers**: leading underscore (e.g., `_normalize_sql`)
- **Imports**: stdlib → third-party → local modules
- **Type hints**: add on new functions when practical; do not force repo-wide typing migration
- **Logging**: `logger = logging.getLogger(__name__)`; emoji markers (⚠️, ✅, 💾, 🚀) are acceptable

## Development Guidelines

### Adding New Services
1. Create `xxx_service.py` in `services/`
2. `XxxService` class naming
3. Import config from `config.py` — never hardcode
4. Export via `services/__init__.py`

### LLM Service
- Uses `httpx.Client` with proxy disabled
- Retry: 3 attempts, 5-second intervals
- Parallel processing via `max_workers`

### Modifying Paper Scoring
Edit prompt templates in `prompt_service.py`. The evaluation prompt (`llm_evaluation_template`) scores on 4 dimensions (0-25 each): problem_relevance, method_transferability, data_resource, technical_depth. Total ≥ 60 passes.

### Error Handling
- Service layer: catch exceptions, log in Chinese, return safe fallbacks (`[]`, `{}`, etc.)
- API layer: log then `raise HTTPException(status_code=500, detail=str(e))`
- No empty `except` blocks

## Scheduler

Built-in scheduler in app.py runs automatically:
- **Fetch**: Daily at `SCHEDULE_CONFIG['fetch_papers']['time']` (default 02:00)
- **Push**: Daily at `SCHEDULE_CONFIG['push_papers']['times']` (default 09:00, 14:30)
- Reload after config changes: `POST /api/scheduler/reload`

## Manual API Endpoints

- `POST /api/actions/fetch-now`: Fetch papers from arXiv (background)
- `POST /api/actions/push-now`: Push papers via notification channel
- `POST /api/actions/process-now`: Process unprocessed papers
- `POST /api/scheduler/reload`: Reload scheduler config
- `GET /api/papers/stats`: Check unprocessed counts
- `GET /api/queue/status`: Check push queue state

## Verification

No formal test workflow in-repo. Tests exist in `tests/` using pytest + FastAPI TestClient with mocking:
```bash
pytest tests/test_setup_api.py           # Setup API tests (DB/LLM connection, notify)
pytest tests/test_integration_llm_config.py  # LLM config integration tests
```

For manual verification: `python app.py` → hit `/api/health` → exercise relevant endpoints.
