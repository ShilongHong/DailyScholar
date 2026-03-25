# Services Layer — Agent Knowledge Base

**Generated:** 2026-03-24 | **Parent:** ../AGENTS.md

## OVERVIEW
Business logic layer with 8 service modules. All services follow singleton-ish pattern with class-based interfaces.

**NEW:** `prompt_service.py` — Centralized prompt management with DB fallback

## WHERE TO LOOK

| Task | File | Key Function/Class |
|------|------|-------------------|
| Paper fetching | `arxiv_service.py` | `ArxivService.fetch_papers()` |
| LLM scoring | `llm_filter_service.py:164` | `LLMFilterService.evaluate_paper()` |
| Translation | `translation_service.py` | `TranslationService.translate_paper()` |
| DB operations | `mysql_service.py` | 20+ functions, see `__init__.py` |
| **统一通知推送** | `notify_service.py` | `NotifyService.send_papers()` — 论文推送主出口，单通道，数据库 notify 配置驱动 |
| DingTalk（保留备用）| `dingtalk_http_service.py` | `DingTalkHTTPService`（不再是主推送入口，由 NotifyService 内部按通道调用）|
| Queue management | `paper_queue_service.py` | `PaperQueueService` |
| **Prompt management** | `prompt_service.py` | `get_prompt()`, `render_template()` |

## CODE MAP

| Symbol | Type | Lines | Role |
|--------|------|-------|------|
| `LLMFilterService` | Class | 555 | Scoring with few-shot examples, retry logic |
| `get_mysql_connection` | Func | 43-82 | Thread-safe connection via `threading.local()` |
| `save_relevant_papers_to_mysql` | Func | 296-339 | Persist filtered papers |
| `_build_evaluation_prompt` | Method | 260-316 | LLM prompt construction |
| `_ensure_tables_exist` | Func | 97-246 | Auto-migration for DB schema |
| `get_prompt` | Func | 169-201 | Load prompts from DB, fallback to defaults |
| `render_template` | Func | 204-218 | Replace {{variables}} in templates |

## PATTERNS

### Import Convention
```python
from config import ARXIV_CONFIG, LLM_FILTER_CONFIG  # Direct from config
from services import get_mysql_connection  # Via __init__.py
from services.prompt_service import get_prompt  # Prompt management
```

### Prompt Service Usage
```python
# Get prompt from DB (fallback to DEFAULT_PROMPT_CONFIG)
system_prompt = get_prompt("llm_system_prompt")

# Render template with variables
template = get_prompt("llm_evaluation_template")
prompt = render_template(template, {
    "research_description": desc,
    "paper_title": title,
    "paper_abstract": abstract,
    "scoring_anchors": anchors,
    "few_shot_examples": examples
})
```

### Error Handling
- Try/except with Chinese log messages
- Return `None` or empty list on failure
- Never raise to caller

### Retry Pattern (LLM)
```python
for attempt in range(max_retries):
    try:
        response = self.client.chat.completions.create(...)
    except Exception as e:
        logger.warning(f"重试 {attempt+1}/{max_retries}: {e}")
        time.sleep(retry_delay)
```

## ANTI-PATTERNS

| Forbidden | Location | Issue |
|-----------|----------|-------|
| `close_mysql_connection()` | mysql_service.py:85-94 | References undefined global, dead code |
| `pymysql.connect()` | Anywhere | Bypasses thread-safety |
| Direct `config.py` mutation | Any service | DB `system_config` takes precedence |
| Hardcoded prompts | Any service | Use `prompt_service.get_prompt()` instead |

## NOTES

- `mysql_service.py` is 986 lines — largest service, contains all DB logic
- `dingtalk_http_service.py` 保留但不再是主推送入口；`NotifyService` 统一管理所有推送通道
- No base class — services are independent
- Auto-migration: `_ensure_tables_exist()` runs on every connection
- **Prompt Configuration**: Stored in `system_config` table as `prompt_config` JSON
- **Hot Reload**: Prompts can be updated via `/api/prompts/{key}` without restart
- **Notify Configuration**: 推送通道配置存于 `system_config` 表 `notify_config` 键，运行时仅激活一个通道