# Agent Guide for ArXiv Paper Push System v3.0

This document provides essential context and guidelines for AI agents working on this codebase.

## 1. Project Overview
**Type**: "Three-in-One" System (FastAPI Backend + Scheduler + Static Frontend)  
**Port**: `20001`  
**Entry Point**: `app.py`

### Key Features
- **Data Flow**: `arXiv API` -> `MySQL (papers_raw)` -> `LLM Filter` -> `Translation` -> `MySQL (papers_relevant)` -> `DingTalk Push`
- **Scheduler**: Integrated `schedule` library running in main process.
- **Frontend**: Static files served from `static/`.

## 2. Build and Run Commands

### Installation
```bash
pip install -r requirements.txt
```

### Running (Development & Production)
```bash
# Starts API server, scheduler, and serves static files
python app.py
```
- **Frontend**: http://localhost:20001
- **API Docs**: http://localhost:20001/docs
- **Health Check**: http://localhost:20001/api/health

### Testing
*Current State*: No automated test suite exists in `requirements.txt`.
**Instructions**:
1. **Manual Verification**: Use API endpoints (e.g., `/api/actions/fetch-now`) to verify changes.
2. **Adding Tests**: If requested, install `pytest` and create tests in `tests/`.
   ```bash
   pip install pytest
   pytest
   ```

### Linting
*Current State*: No strict linter config.
**Instructions**:
- Follow **PEP 8**.
- Use 4 spaces for indentation.
- Maintain existing style (see Section 3).

## 3. Code Style and Conventions

### Language Rules (CRITICAL)
- **Comments & Docstrings**: MUST be in **Chinese (Simplified)**.
- **Log Messages**: MUST be in **Chinese (Simplified)**.
- **Variable/Function Names**: English `snake_case` (e.g., `get_paper_list`).
- **Class Names**: English `CamelCase` (e.g., `ArxivService`).

### Database Patterns (CRITICAL)
**Library**: `pymysql` (Thread-safe wrapper)
**Rule**: NEVER share connections between threads. ALWAYS use the service helper.

```python
from services.mysql_service import get_mysql_connection

def my_db_task():
    # Correct way to get a thread-local connection
    conn = get_mysql_connection()
    if not conn:
        return
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT * FROM papers_raw LIMIT 1")
        conn.commit()
    finally:
        # Connection closing is handled by the service/context if needed, 
        # but explicit close is safe if new connection obtained each time.
        conn.close() 
```

### File Structure & Imports
- **Absolute Imports**: Prefer `from services.arxiv_service import ...`
- **Path Handling**: Some legacy scripts use `sys.path.insert(0, ...)` to find `config.py`. Maintain this if editing existing scripts in `tools/`.
- **Configuration**:
  - `config.py`: Default settings.
  - `system_config` (DB table): Overrides defaults. Always prefer fetching config from DB.

## 4. Architecture & Services

### Service Modules (`services/`)
| Module | Responsibility |
|--------|----------------|
| `arxiv_service.py` | Fetch from arXiv API. Handles keywords & categories (e.g. `cs.CL`). |
| `llm_filter_service.py` | Evaluate relevance (0-100 score) using OpenAI-compatible API. |
| `translation_service.py` | Translate Title/Abstract (CN/EN). |
| `mysql_service.py` | Central DB access. Handles connection pooling/thread-safety. |
| `dingtalk_service.py` | Send notifications via DingTalk webhook. |
| `paper_queue_service.py` | Manage push queue. |

### Utility Tools (`tools/`)
Maintenance scripts have been moved to `tools/`:
- `rebuild_queue.py`: Clear/refill push queue.
- `rescore_papers.py`: Batch re-evaluate papers with new LLM prompts.
- `fix_created_at.py`: Data consistency fixes.
- `reset_processed_2026.py`: Reset processing status for reprocessing.

## 5. Common Tasks

### Modifying LLM Prompt
Edit `_build_evaluation_prompt` in `services/llm_filter_service.py`.
- **Score Range**: 0-100 (Threshold usually 60).
- **Format**: JSON output required.

### Adding New Search Keywords
Update `ARXIV_CONFIG['keywords']` in `config.py` OR update the `system_config` table in the database (Database config takes precedence).

### Manual Trigger
Use these API endpoints for testing flows:
- `POST /api/actions/fetch-now`: Trigger immediate paper fetch.
- `POST /api/actions/push-now`: Trigger immediate push to DingTalk.
