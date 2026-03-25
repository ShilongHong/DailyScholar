# DailyScholar v3.0 — Agent Knowledge Base

**Generated:** 2026-03-24 | **Commit:** eecc59a | **Branch:** main

## OVERVIEW
"Three-in-One" Python application: FastAPI backend + built-in scheduler + Vue3 SPA frontend. Single process on port `20001`. Fetches arXiv papers, filters via LLM, translates to Chinese, pushes to DingTalk. **DailyScholar** - Your AI research assistant.

## STRUCTURE
```
dailyscholar/
├── app.py           # Entry point (FastAPI + scheduler + all routes) — 1052 lines
├── config.py        # Central configuration (DB, LLM, DingTalk, schedule)
├── services/        # Business logic layer — 8 modules, see services/AGENTS.md
├── tools/           # Maintenance scripts — 6 scripts, see tools/AGENTS.md
├── static/          # Vue3 SPA (single index.html with embedded app)
├── logs/            # Runtime logs (daily rotation)
└── docs/            # Documentation assets
```

## WHERE TO LOOK

| Task | Location | Notes |
|------|----------|-------|
| Add/modify API endpoints | `app.py:498-1036` | All routes in single file, no router modules |
| Modify LLM scoring prompt | `services/prompt_service.py` | DB `prompt_config` or local `DEFAULT_PROMPT_CONFIG` |
| Modify translation prompt | `services/prompt_service.py` | `translation_template` key |
| Add search keywords | API `/api/config/arxiv_config` or DB `system_config` table | Web/API first, `config.py` defaults as fallback |
| Change fetch/push times | API `/api/config/schedule_config` or `config.py:137` | Reload via `/api/scheduler/reload` |
| Thread-safe DB operations | `services/mysql_service.py:43-82` | `get_mysql_connection()` only |
| Fix translation issues | `services/translation_service.py` | Uses prompt_service for prompts |
| Debug scheduler | `app.py:387-461` | `PaperScheduler` class |
| Manual operations | `POST /api/actions/*` | `fetch-now`, `push-now`, `process-now` |

## CODE MAP

| Symbol | Type | Location | Refs | Role |
|--------|------|----------|------|------|
| `PaperScheduler` | Class | app.py:387 | 3 | Manages fetch/push schedule |
| `LLMFilterService` | Class | services/llm_filter_service.py:33 | 5 | Paper relevance scoring |
| `get_mysql_connection` | Func | services/mysql_service.py:43 | 20+ | Thread-safe DB connection |
| `run_fetch_papers` | Func | app.py:162 | 2 | Main fetch pipeline |
| `run_push_papers` | Func | app.py:326 | 2 | DingTalk push pipeline |
| `ArxivService` | Class | services/arxiv_service.py | 2 | arXiv API integration |
| `TranslationService` | Class | services/translation_service.py | 2 | CN/EN translation |
| `PromptService` | Module | services/prompt_service.py | 3 | Prompt management with DB fallback |

## Prompt Management (NEW)

### Architecture
All LLM prompts are now managed through `services/prompt_service.py`:
- **Initialization**: Loads from local `DEFAULT_PROMPT_CONFIG`
- **Runtime**: Priority reads from DB `system_config.prompt_config`, falls back to local defaults

### Available Prompt Keys
| Key | Description | Used By |
|-----|-------------|---------|
| `llm_system_prompt` | System message for paper evaluation | llm_filter_service |
| `llm_few_shot_examples` | Few-shot scoring examples | llm_filter_service |
| `llm_scoring_anchors` | Keyword-based scoring guidelines | llm_filter_service |
| `llm_evaluation_template` | Main evaluation prompt template | llm_filter_service |
| `translation_system_prompt` | System message for translation | translation_service |
| `translation_template` | Translation prompt template | translation_service |

### Modifying Prompts
1. **Via Database** (Hot reload, no restart needed):
   ```sql
   INSERT INTO system_config (config_name, config_value) 
   VALUES ('prompt_config', '{"llm_system_prompt": "..."}');
   ```
2. **Via Code**: Edit `services/prompt_service.py` → `DEFAULT_PROMPT_CONFIG`

### Template Variables
Prompts support `{{variable}}` substitution:
- `{{research_description}}` - User's research area
- `{{paper_title}}`, `{{paper_abstract}}` - Paper content
- `{{scoring_anchors}}`, `{{few_shot_examples}}` - Dynamic prompt sections

## CONVENTIONS

### Language (CRITICAL)
- **Comments/Docstrings/Logs**: MUST be Chinese (Simplified)
- **Variable/Function names**: English `snake_case`
- **Class names**: English `CamelCase`
- **Constants**: `UPPER_SNAKE_CASE`

### Configuration Hierarchy (highest wins)
1. Database `system_config` table ← **check first**
2. `config.py` defaults

### Onboarding and Setup
- Prefer Web initialization wizard and `/api/config/*` for normal setup and configuration updates.
- Keep `config.py` as safe committed defaults/fallback values, not as the primary day-to-day setup path.

### API Response Format
```python
{"success": bool, "data": ..., "message": ...}
```

## ANTI-PATTERNS (FORBIDDEN)

| Forbidden | Correct | Why |
|-----------|---------|-----|
| `pymysql.connect()` directly | `get_mysql_connection()` | Thread-safety |
| Sharing `conn` across threads | New connection per thread | Race conditions |
| Global `_mysql_connection` variable | `_thread_local` storage | Broken pattern |
| Non-Chinese comments/logs | Chinese (Simplified) | Project convention |
| Hardcoded config values | Import from `config.py` | Config hot-reload |

### Dead Code Warning
`mysql_service.py:85-94` — `close_mysql_connection()` references undefined global. Do NOT use.

## COMMANDS

```bash
# Install
pip install -r requirements.txt

# Run (starts API + scheduler + frontend)
python app.py

# Access points
# Frontend:  http://localhost:20001
# API docs:  http://localhost:20001/docs
# Health:    http://localhost:20001/api/health

# Manual triggers
curl -X POST http://localhost:20001/api/actions/fetch-now
curl -X POST http://localhost:20001/api/actions/push-now
curl -X POST http://localhost:20001/api/actions/process-now
```

## NOTES

- **No tests**: Manual verification via API endpoints
- **No auth**: All endpoints publicly accessible
- **No router modules**: All 20+ endpoints in `app.py`
- **Monolithic structure**: Not a monorepo, single app with services layer
- `tools/` = maintenance scripts (non-standard naming, typically `scripts/`)
