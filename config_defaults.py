"""DailyScholar 默认配置。

本文件只包含可提交的非敏感默认值。生产环境如需覆盖配置，可复制
config.example.py 为本地 config.py，或通过 Web 配置向导写入运行时配置。
"""

ARXIV_CONFIG = {
    "api_url": "https://export.arxiv.org/api/query",
    "keywords": ["cs.CL", "cs.CV", "cs.LG", "cs.AI"],
    "batch_size": 100,
    "max_results_per_keyword": 100,
    "request_delay": 3,
    "recent_days": 3,
    "consecutive_duplicate_threshold": 100,
    "mysql": {
        "enable": True,
        "db_type": "sqlite",
        "sqlite_path": "data/papers.db",
        "host": "localhost",
        "port": 3306,
        "user": "root",
        "password": "",
        "database": "arxiv_papers",
        "charset": "utf8mb4",
        "table_raw": "papers_raw",
        "table_relevant": "papers_relevant",
    },
}

LLM_FILTER_CONFIG = {
    "enable": True,
    "api_key": "",
    "base_url": "",
    "model": "gpt-3.5-turbo",
    "min_stars": 60,
    "min_score": 60,
    "temperature": 0.1,
    "max_tokens": 1200,
    "max_workers": 8,
    "translation_temperature": 0.3,
    "translation_max_tokens": 4096,
}

SCHEDULE_CONFIG = {
    "fetch_papers": {
        "enable": True,
        "time": "02:00",
        "backlog_limit": 100,
    },
    "process_papers": {
        "batch_size": 100,
    },
    "push_papers": {
        "enable": True,
        "times": ["09:00", "14:30"],
        "max_papers_per_push": 5,
    },
}

DINGTALK_CONFIG = {
    "app_key": "",
    "app_secret": "",
    "robot_code": "",
    "open_conversation_id": "",
    "token_url": "https://oapi.dingtalk.com/gettoken",
    "access_token": "",
    "token_expire_time": 0,
}

MINERU_CONFIG = {
    "mode": "cloud",
    "api_key": "",
    "endpoint": "http://localhost:18000",
}

MESSAGE_CONFIG = {
    "title_template": "DailyScholar 论文推送 - {date}",
    "no_papers_message": "今天暂无符合筛选条件的论文。",
    "paper_template": """# {TitleCN}

**评分**: {Stars}/100

**作者**: {Author}

**机构**: {Affiliation}

**年份**: {PublicationYear}

**推荐理由**: {RelevanceReason}

**潜在帮助**: {PotentialHelp}

**摘要**: {AbstractCN}

[论文链接]({Link}) | [PDF]({PDFLink})

DOI: {DOI}""",
}

OUTPUT_CONFIG = {
    "dir": "output",
    "raw_filename": "papers_raw.csv",
    "relevant_filename": "papers_relevant.csv",
}

LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
}

RESEARCH_DESCRIPTION = "请在 Web 配置向导或系统配置页面中填写你的研究方向。"