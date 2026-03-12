from datetime import datetime
import json
from copy import deepcopy
from pathlib import Path


RESEARCH_DESCRIPTION = """
我的研究方向是图表数据提取、多模态信息理解与智能体工作流。
重点关注图表理解、文档智能、视觉语言模型、信息提取和智能体辅助科研。
"""


ARXIV_CONFIG = {
    "keywords": ["cs.CL", "cs.CV", "cs.LG", "cs.AI", "cs.IR"],
    "max_results_per_keyword": None,
    "batch_size": 50,
    "request_delay": 3,
    "consecutive_duplicate_threshold": 5000,
    "recent_days": 1000,
    "api_url": "http://export.arxiv.org/api/query",
    "mysql": {
        "enable": False,
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "paper2data",
        "charset": "utf8mb4",
        "table_raw": "papers_raw",
        "table_relevant": "papers_relevant",
        "table_queue": "paper_queue",
        "table_config": "system_config",
    },
    "sqlite": {
        "enable": True,
        "path": "data/paper2data.db",
        "table_raw": "papers_raw",
        "table_relevant": "papers_relevant",
        "table_queue": "paper_queue",
        "table_config": "system_config",
    },
    "database": {
        "engine": "sqlite",
    },
}


LLM_FILTER_CONFIG = {
    "enable": True,
    "api_key": "",
    "base_url": "https://api.siliconflow.cn/v1/",
    "model": "deepseek-ai/DeepSeek-V3.2",
    "temperature": 0.5,
    "max_tokens": 4096,
    "min_score": 60,
    "min_stars": 60,
    "save_all_papers": True,
    "max_workers": 16,
}


OPENCLAW_CONFIG = {
    "enabled": True,
    "delivery_mode": "cli-session",
    "binary_path": "openclaw",
    "session_key": "main",
    "timeout_seconds": 120,
    "max_papers_per_message": 5,
    "include_full_abstract": False,
}


SCHEDULE_CONFIG = {
    "enable_schedule": True,
    "timezone": "Asia/Shanghai",
    "fetch_papers": {
        "enable": True,
        "time": "02:00",
        "backlog_limit": 50,
    },
    "process_papers": {
        "batch_size": 100,
    },
    "push_papers": {
        "enable": True,
        "times": ["09:00"],
        "max_papers_per_push": 5,
        "min_interval_minutes": 60,
    },
}


LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": f"logs/app_{datetime.now().strftime('%Y%m%d')}.log",
}


OUTPUT_CONFIG = {
    "save_to_file": True,
    "output_dir": "output",
    "filename_format": "arxiv_papers_{date}.csv",
}


MESSAGE_CONFIG = {
    "title_template": "今日论文摘要 - {date}",
    "max_papers_in_message": 20,
}


def _deep_merge(base: dict, override: dict) -> dict:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _load_local_overrides():
    local_path = Path(__file__).resolve().parent.parent / "config.local.json"
    if not local_path.exists():
        return

    local_config = json.loads(local_path.read_text(encoding="utf-8"))

    mapping = {
        "arxiv": ARXIV_CONFIG,
        "llm_filter": LLM_FILTER_CONFIG,
        "openclaw": OPENCLAW_CONFIG,
        "schedule": SCHEDULE_CONFIG,
        "logging": LOGGING_CONFIG,
        "output": OUTPUT_CONFIG,
        "message": MESSAGE_CONFIG,
    }

    for key, target in mapping.items():
        value = local_config.get(key)
        if isinstance(value, dict):
            _deep_merge(target, deepcopy(value))

    database_config = local_config.get("database")
    if isinstance(database_config, dict):
        engine = database_config.get("engine", ARXIV_CONFIG["database"]["engine"])
        ARXIV_CONFIG["database"]["engine"] = engine
        if engine == "mysql":
            ARXIV_CONFIG["mysql"]["enable"] = True
            ARXIV_CONFIG["sqlite"]["enable"] = False
            _deep_merge(ARXIV_CONFIG["mysql"], deepcopy(database_config))
        else:
            ARXIV_CONFIG["mysql"]["enable"] = False
            ARXIV_CONFIG["sqlite"]["enable"] = True
            if "sqlite_path" in database_config:
                ARXIV_CONFIG["sqlite"]["path"] = database_config["sqlite_path"]
            _deep_merge(ARXIV_CONFIG["sqlite"], deepcopy(database_config))


_load_local_overrides()
