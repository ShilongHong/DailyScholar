# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is **DailyScholar v3.0** (formerly ArXiv Paper Push System) - a three-in-one academic paper recommendation system that combines FastAPI backend, built-in scheduler, and static frontend server. It automatically fetches papers from arXiv, uses LLM to filter relevant papers, translates them to Chinese, and pushes notifications to DingTalk.

**Port**: 20001
**Main Entry**: [app.py](app.py)
**API Docs**: http://localhost:20001/docs (Swagger UI)

## Development Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application (starts API + scheduler + frontend)
python app.py

# Access points
# - Frontend: http://localhost:20001
# - API docs: http://localhost:20001/docs
# - Health check: http://localhost:20001/api/health
```

### Testing
No automated tests currently exist. For manual verification, use API endpoints:
```bash
# Test fetching papers
curl -X POST http://localhost:20001/api/actions/fetch-now

# Test pushing papers
curl -X POST http://localhost:20001/api/actions/push-now
```

If adding tests, install pytest and create tests in `test/`:
```bash
pip install pytest
pytest test/
```

## Architecture

### Data Flow Pipeline
```
arXiv API → papers_raw (MySQL) → LLM Filter → Translation → papers_relevant → paper_queue → DingTalk Push
```

### Service Modules (`services/`)

| Service | Purpose | Key Notes |
|---------|---------|-----------|
| [arxiv_service.py](services/arxiv_service.py) | Fetch papers from arXiv API | Supports category codes (cs.CL, cs.CV) and keywords |
| [llm_filter_service.py](services/llm_filter_service.py) | AI-powered relevance scoring | Uses DeepSeek-V3.2, 100-point scale (60+ passes) |
| [translation_service.py](services/translation_service.py) | Chinese/English translation | Translates titles and abstracts |
| [mysql_service.py](services/mysql_service.py) | Database operations | Thread-safe connections via `threading.local()`, auto-migration |
| [dingtalk_http_service.py](services/dingtalk_http_service.py) | DingTalk notifications | **Preferred over SDK version** |
| [dingtalk_service.py](services/dingtalk_service.py) | DingTalk SDK version | Legacy, prefer HTTP version |
| [paper_queue_service.py](services/paper_queue_service.py) | Push queue management | Prevents duplicate notifications |

### Key Design Patterns

**1. Configuration Hierarchy** (lowest to highest priority):
- [config.py](config.py) - Default values
- `runtime_config.json` - Runtime overrides (legacy, deprecated)
- Database `system_config` table - Highest priority, takes precedence over all

To update config at runtime, use API endpoints `/api/config/{name}` - these persist to the database.

**2. Thread-Safe Database**: MySQL uses `threading.local()` for per-thread connection pooling. Always use:
```python
from services import get_mysql_connection
conn = get_mysql_connection()
with conn.cursor() as cursor:
    cursor.execute(sql)
conn.commit()
```

**3. Background Processing**: The fetch pipeline uses producer-consumer pattern:
- Main thread fetches and saves to `papers_raw`
- Background thread continuously reads `processed=0` records, filters, translates, and saves to `papers_relevant`

**4. Auto-Migration**: `_ensure_tables_exist()` in mysql_service.py automatically adds missing columns

## Configuration

**Core Settings** ([config.py](config.py)):

- `RESEARCH_DESCRIPTION`: Research area context for LLM filtering
- `ARXIV_CONFIG['keywords']`: arXiv categories to search (cs.CL, cs.CV, cs.LG, cs.AI, cs.IR)
- `LLM_FILTER_CONFIG['min_score']`: Relevance threshold (default: 60/100)
- `SCHEDULE_CONFIG`: Fetch time (02:00) and push times (09:00, 14:30)

## API Conventions

- All API routes prefixed with `/api/`
- Response format: `{"success": bool, "data": ..., "message": ...}`
- Use Pydantic BaseModel for request bodies
- View full API documentation at `/docs` when server is running

## Database Schema

- `papers_raw`: Original fetched papers with `processed` flag
- `papers_relevant`: Filtered papers with translations, scores, and `is_pushed` flag
- `paper_queue`: Push queue (papers awaiting notification)
- `system_config`: Runtime configuration storage

**Important**: The `Stars` column stores 0-100 scores (not 1-5 stars) for backwards compatibility.

## Code Style

- **Comments & Docstrings**: Must be in **Chinese (Simplified)**
- **Log Messages**: Must be in **Chinese (Simplified)**
- **Variable/Function Names**: English `snake_case` (e.g., `get_paper_list`)
- **Class Names**: English `CamelCase` (e.g., `ArxivService`)
- **Indentation**: 4 spaces (PEP 8)

## Development Guidelines

### Adding New Services
1. Create `xxx_service.py` in `services/`
2. Use `XxxService` class naming convention
3. Import config from `config.py`, never hardcode
4. Export via `services/__init__.py`

### LLM Service Notes
- Uses `httpx.Client` with proxy disabled
- Built-in retry: 3 attempts, 5-second intervals
- Parallel processing configurable via `max_workers` in config

### Modifying Paper Scoring
Edit `_build_evaluation_prompt()` in [llm_filter_service.py](services/llm_filter_service.py:70). The system uses 100-point scoring where 60+ indicates relevance.

### Rescoring Papers
The project includes a rescore utility in [tools/rescore_papers.py](tools/rescore_papers.py) with options:
- `--dry-run`: Preview changes without database updates
- `--convert-only`: Convert legacy 5-star ratings to 100-point scale
- `--workers N`: Set parallel worker count
- `--limit N`: Limit number of papers to process

### Other Maintenance Scripts

Located in [tools/](tools/) directory:
- [rebuild_queue.py](tools/rebuild_queue.py): Clears and rebuilds paper_queue from papers_relevant with Stars >= 60
- [re_evaluate_failed.py](tools/re_evaluate_failed.py): Re-evaluates papers where LLM scoring failed (papers with "评估失败" in RelevanceReason)
- [reset_processed_2026.py](tools/reset_processed_2026.py): Reset processing status for reprocessing
- [fix_created_at.py](tools/fix_created_at.py): Data consistency fixes for created_at timestamps

## Manual Operations

The API provides several endpoints for triggering tasks manually:
- `POST /api/actions/fetch-now`: Immediately fetch papers from arXiv (runs in background)
- `POST /api/actions/push-now`: Immediately push papers to DingTalk
- `POST /api/actions/process-now`: Process unprocessed papers from `papers_raw`
- `GET /api/logs/list`: List available log files
- `GET /api/logs/content`: View log content (last N lines)

## Troubleshooting

**Frontend shows 404**: Ensure `static/index.html` exists. The frontend is served from the `static/` directory. If missing, you can still use the Swagger UI at `/docs`.

**Papers not being processed**: Check `/api/papers/stats` for unprocessed counts. Use `/api/actions/process-now` to manually trigger processing.

**Queue issues**: Use `/api/queue/status` to check queue state. Run `rebuild_queue.py` to rebuild from `papers_relevant`.

**LLM evaluation failures**: Papers with failed evaluations retain `processed=0` in `papers_raw`. Run `re_evaluate_failed.py` to retry them.

## Scheduler

The built-in scheduler ([app.py:333-405](app.py#L333-L405)) runs automatically:
- **Fetch Task**: Daily at `SCHEDULE_CONFIG['fetch_papers']['time']` (default 02:00)
- **Push Task**: Daily at `SCHEDULE_CONFIG['push_papers']['times']` (default 09:00, 14:30)

Reload scheduler after config changes: `POST /api/scheduler/reload`

## Important File References

- Main application: [app.py](app.py)
- Central configuration: [config.py](config.py)
- ArXiv integration: [services/arxiv_service.py](services/arxiv_service.py)
- LLM filtering: [services/llm_filter_service.py](services/llm_filter_service.py)
- Database operations: [services/mysql_service.py](services/mysql_service.py)
- Frontend (Vue3 SPA): [static/index.html](static/index.html)
