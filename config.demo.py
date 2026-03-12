from datetime import datetime

RESEARCH_DESCRIPTION = """
我的研究方向是**图表数据提取与多模态信息理解**，核心目标是构建通用的、基于智能体的图表数据提取框架，并探索其在各类下游任务中的应用潜力。

### 核心研究主题（高相关性）
1. **图表数据提取方法**：Chart-to-Table、Plot Digitization、图表OCR、各类图表（折线图/柱状图/散点图/饼图等）的自动数据提取
2. **视觉语言模型在图表任务上的应用**：Chart Question Answering (ChartQA)、Chart Captioning、Chart Reasoning、Chart Summarization
3. **多模态大模型与指令微调**：Vision-Language Models for Charts、Instruction-Tuning for Document AI
4. **智能体框架**：LLM-based Agents、Tool-augmented LLMs、Agentic Workflows for Information Extraction
5. **文档智能**：Document Understanding、Figure/Table Extraction、PDF解析

### 相关支撑技术（中等相关性）
- 实例分割、关键点检测（用于图表元素识别）
- OCR与文本检测
- 表格识别与结构化（Table Recognition/Extraction）
- 多模态检索与推理

### 潜在应用场景（根据具体内容判断相关性）
- 事实核验（Fact Verification）
- 商业智能与数据分析自动化
- 教育与自动化测评
- 无障碍访问（Accessibility）
- 数据库与数据管理

### 排除方向（低相关性）
- 纯图表生成/可视化（不涉及提取）
- 与图表无关的通用视觉问答
- 纯NLP任务（不涉及视觉模态）
- 硬件优化、模型压缩（除非直接应用于图表任务）
"""

ARXIV_CONFIG = {
    "keywords": [
        "cs.CL",
        "cs.CV",
        "cs.LG",
        "cs.AI",
        "cs.IR",
    ],
    "max_results_per_keyword": None,
    "batch_size": 50,
    "request_delay": 3,
    "consecutive_duplicate_threshold": 5000,
    "recent_days": 1000,
    "api_url": "http://export.arxiv.org/api/query",
    "mysql": {
        "enable": True,
        "host": "your-host",
        "port": 3306,
        "user": "your-user",
        "password": "your-password",
        "database": "your-database",
        "charset": "utf8mb4",
        "table_raw": "papers_raw",
        "table_relevant": "papers_relevant",
    },
}


LLM_FILTER_CONFIG = {
    "enable": True,
    "api_key": "your-api-key",
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
        "times": ["09:00", "14:30"],
        "max_papers_per_push": 5,
        "min_interval_minutes": 60,
    },
}


LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "log_file": "logs/daily_paper.log",
}


OUTPUT_CONFIG = {
    "save_to_file": True,
    "output_dir": "output",
    "filename_format": "arxiv_papers_{date}.csv",
}


MESSAGE_CONFIG = {
    "msg_type": "markdown",
    "title_template": "📚 今日arXiv论文推送 - {date}",
    "paper_template": """
## {TitleCN}

**📊 相关度评分**: {Stars}分/100

**💡 推荐理由**: {RelevanceReason}

**🎯 对我的帮助**: {PotentialHelp}

---

**👥 作者**: {Author}

**🏛️ 单位**: {Affiliation}

**📅 发布日期**: {PublicationYear}

---

**📝 摘要**:
{AbstractCN}

---

**🔗 链接**:
- [查看原文]({Link})
- [下载PDF]({PDFLink})

**🆔 DOI/arXiv ID**: {DOI}
""",
    "no_papers_message": "今天没有发现相关度达标的论文 😊",
    "max_papers_in_message": 20,
}
