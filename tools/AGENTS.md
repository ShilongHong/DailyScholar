# Maintenance Tools — Agent Knowledge Base

**Generated:** 2026-03-24 | **Parent:** ../AGENTS.md

## OVERVIEW
6 maintenance scripts for data operations. Run directly with `python tools/<script>.py`.

## SCRIPTS

| Script | Purpose | Key Options |
|--------|---------|-------------|
| `rebuild_queue.py` | Clear & refill push queue from `papers_relevant` | `--limit N` |
| `rescore_papers.py` | Batch re-evaluate with new LLM prompt | `--dry-run`, `--workers N`, `--limit N`, `--convert-only` |
| `re_evaluate_failed.py` | Retry papers with failed LLM scoring | `--limit N` |
| `fix_created_at.py` | Fix timestamp consistency | — |
| `reset_processed_2026.py` | Reset `processed` flag for reprocessing | — |
| `prompt_demo.py` | Test LLM prompt changes (418 lines) | — |

## WHERE TO LOOK

| Task | Script |
|------|--------|
| Test new scoring prompt | `prompt_demo.py` |
| Rebuild after DB issues | `rebuild_queue.py` |
| Re-evaluate with new criteria | `rescore_papers.py --dry-run` |
| Fix failed evaluations | `re_evaluate_failed.py` |

## PATTERNS

### Path Setup (Legacy)
```python
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ...
from services import ...
```

### Common Options
- `--dry-run`: Preview without DB changes
- `--limit N`: Process only N papers
- `--workers N`: Parallel workers (default: 8)

## NOTES

- All scripts use `sys.path.insert` to find parent modules
- `prompt_demo.py` is largest (418 lines) — contains demo/test logic
- No `__init__.py` — standalone scripts
- Run from project root: `python tools/<script>.py`