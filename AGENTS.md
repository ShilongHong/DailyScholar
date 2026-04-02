# DailyScholar v3.0 — Agent Guide

## Overview

DailyScholar is a single-process Python application that combines:
- FastAPI backend
- built-in scheduler
- Vue 3 SPA served from `static/index.html`

Primary flow:
`arXiv API -> raw papers -> LLM filtering -> translation -> queue -> notification`

Main entrypoint: `app.py`
Main port: `20001`

## Repository Layout

```text
daliy_paper_v3/
├── app.py                    # FastAPI app, scheduler, and all routes
├── config.py                 # Default configuration constants
├── requirements.txt          # Runtime Python dependencies
├── services/                 # Business logic layer
├── static/index.html         # Single-file Vue 3 frontend
├── tests/                    # Pytest-style tests exist here
├── test/                     # Ad hoc test script(s)
├── docs/                     # Docs and screenshots
└── .github/copilot-instructions.md
```

## Authoritative Repo Rules

There is a Copilot instruction file at `.github/copilot-instructions.md`. Its guidance is consistent with the codebase and should be followed.

No `.cursorrules` file was found.
No `.cursor/rules/` directory was found.

## Build / Run / Test / Lint Commands

### Install dependencies

```bash
pip install -r requirements.txt
```

Source of truth:
- `requirements.txt`
- `README.md`
- `.github/copilot-instructions.md`

### Run the app

```bash
python app.py
```

Then access:
- UI: `http://localhost:20001`
- API docs: `http://localhost:20001/docs`
- Health: `http://localhost:20001/api/health`

### Tests

This repo contains pytest-style tests in `tests/`, but pytest is **not** declared in `requirements.txt`, and there is no `pytest.ini`, `pyproject.toml`, or other authoritative test config.

That means:
- tests exist
- `.pytest_cache/` exists
- but automated test tooling is **not formally configured** in-repo

If your environment already has `pytest` installed, these are the likely commands:

```bash
pytest tests
pytest tests/test_setup_api.py
pytest tests/test_setup_api.py -k <pattern>
pytest tests/test_integration_llm_config.py::test_name
```

Use those as ad hoc commands, not as guaranteed project-supported workflows.

### Single test execution

Preferred when pytest is available:

```bash
pytest tests/test_setup_api.py::test_name
```

or pattern-based:

```bash
pytest tests/test_setup_api.py -k keyword
```

### Lint / format / type-check

No authoritative lint/type config files were found:
- no `pyproject.toml`
- no `ruff.toml` / `.ruff.toml`
- no `mypy.ini`
- no `.flake8`
- no `pylintrc`

Observations:
- `.ruff_cache/` exists, so Ruff has been run locally before
- LSP diagnostics report many Python warnings, but no current `.py` errors

Implication for agents:
- do **not** invent a required lint command
- prefer targeted verification over claiming a nonexistent repo-wide lint workflow

## Verification Guidance

Because tooling is light, verification should usually be:
1. `python app.py` for startup sanity
2. hit `/api/health`
3. manually exercise relevant `/api/*` endpoints
4. for frontend changes, verify behavior through the served SPA

Manual action endpoints:
- `POST /api/actions/fetch-now`
- `POST /api/actions/process-now`
- `POST /api/actions/push-now`

Scheduler endpoint:
- `POST /api/scheduler/reload`

## Architecture Notes

### Backend
- All routes live in `app.py`; there are no router modules.
- Request bodies use Pydantic `BaseModel` classes.
- Most route responses follow `{"success": bool, "data": ..., "message": ...}`.
- Some infra endpoints like `/api/health` return custom payloads.

### Services
- Business logic lives under `services/`.
- Shared service exports are re-exported through `services/__init__.py`.
- Prompt management is centralized in `services/prompt_service.py`.
- Notification dispatch now centers on `services/notify_service.py`.

### Frontend
- Frontend is a single-file Vue 3 app in `static/index.html`.
- It uses CDN-loaded Vue, Tailwind, Phosphor icons, and Chart.js.
- Avoid introducing a bundler/toolchain unless the user explicitly asks.

## Code Style Conventions

### Language
- Comments: Simplified Chinese
- Docstrings: Simplified Chinese
- Log messages: Simplified Chinese
- User-facing UI copy: Simplified Chinese

### Naming
- variables/functions: `snake_case`
- classes: `CamelCase`
- constants: `UPPER_SNAKE_CASE`
- internal helpers: leading underscore, e.g. `_normalize_sql`

### Imports
- Order imports as: standard library -> third-party -> local modules
- Common local import patterns:

```python
from config import ARXIV_CONFIG, LLM_FILTER_CONFIG
from services import get_mysql_connection
from services.prompt_service import get_prompt, get_rendered_prompt
```

### Formatting
- Match existing Python style; there is no formal formatter config
- Keep line length moderate and use wrapped calls like the existing code
- Prefer small helper functions over deeply nested route logic where practical

### Types
- Add type hints on new functions when practical
- Follow the repo's existing mixed style:
  - modern builtins like `dict[str, Any]` appear in `app.py`
  - older `Dict[str, Any]` / `List[...]` style still appears in services
- Do not force a repo-wide typing migration during a small change

### API Models
- Use Pydantic `BaseModel` for request bodies
- Keep field names aligned with current API payloads
- Preserve existing response shapes unless explicitly changing the API contract

## Error Handling Conventions

- Service layer usually catches exceptions, logs in Chinese, and returns safe fallbacks
- API layer often logs then raises `HTTPException(status_code=500, detail=str(e))`
- Retry external LLM/API calls when matching existing patterns
- Avoid empty `except` blocks unless the existing local pattern truly requires silent cleanup

Typical patterns:
- return `[]` / `{}` / fallback values from service helpers
- log warnings for recoverable failures
- log errors for final failure paths

## Configuration Rules

Configuration precedence is important:
1. database `system_config`
2. `runtime_config.json`
3. `config.py` defaults

Follow these rules:
- prefer DB-backed runtime config for active behavior
- use `config.py` as defaults/fallbacks
- do not hardcode values that already exist in config
- prefer Web setup or `/api/config/*` flows for operational changes

Prompt-specific rule:
- prompts should come from `services/prompt_service.py`
- do not hardcode LLM prompts in unrelated modules

## Database Rules

Thread safety is critical.

Always use the repo helpers:

```python
conn = get_mysql_connection()
with conn.cursor() as cursor:
    cursor.execute(sql)
conn.commit()
```

Never:
- call `pymysql.connect()` directly in feature code
- share a connection across threads
- reintroduce a global DB connection pattern

SQLite is also supported; `mysql_service.py` abstracts both SQLite and MySQL.

## Logging Rules

- Use `logger = logging.getLogger(__name__)`
- Keep logs in Chinese
- Existing code often uses emoji markers like `⚠️`, `✅`, `💾`, `🚀`; matching them is acceptable
- Log enough context to debug external calls and background tasks

## Known Project Constraints

- This is a monolithic app; do not assume modular FastAPI routers
- There is no formal frontend build pipeline
- There is no formally configured lint/type/test workflow in-repo
- Existing Python code has many type-related warnings; do not expand them casually
- `close_mysql_connection()` has been flagged historically as risky/dead-code territory; avoid introducing dependencies on it without re-validating the implementation

## Agent Do / Do Not

Do:
- make minimal, pattern-matching changes
- keep Chinese comments/logs consistent with surrounding code
- preserve API response shapes
- verify changes with actual endpoint/manual checks when tests are absent
- check both backend and `static/index.html` when a feature crosses UI/API boundaries

Do not:
- add new frameworks or build systems without being asked
- invent unsupported repo commands
- bypass `mysql_service` connection helpers
- hardcode runtime config or prompt text that already has a managed source
- refactor unrelated modules during a bug fix
