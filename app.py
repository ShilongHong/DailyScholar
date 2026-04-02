"""
DailyScholar v3.0 - AI科研情报助手
后端API + 定时调度 + 静态页面服务
"""

import asyncio
import os
import sys
import json
import logging
import threading
import time
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, cast
from concurrent.futures import ThreadPoolExecutor, as_completed

import schedule
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from openai import OpenAI
import httpx


import uvicorn

try:
    import pymysql
except ImportError:

    class _PyMySQLFallback:
        def connect(self, *args, **kwargs):
            raise ImportError("pymysql未安装")

    pymysql = _PyMySQLFallback()

# 确保服务模块可以导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    ARXIV_CONFIG,
    LLM_FILTER_CONFIG,
    SCHEDULE_CONFIG,
    DINGTALK_CONFIG,
    LOGGING_CONFIG,
    OUTPUT_CONFIG,
)
from services import (
    ArxivService,
    LLMFilterService,
    TranslationService,
    DingTalkHTTPService,
    PaperQueueService,
    get_mysql_connection,
    is_mysql_enabled,
    get_all_relevant_papers,
    get_relevant_papers_by_date,
    get_paper_stats,
    save_raw_papers_to_mysql,
    save_relevant_papers_to_mysql,
    update_paper_mark,
    update_paper_comment,
    delete_paper,
    get_unprocessed_raw_papers,
    mark_papers_as_processed,
    load_config_from_db,
    save_config_to_db,
    get_all_configs_from_db,
    execute_query,
    execute_update,
)
from services.mysql_service import _ensure_tables_exist
from services.notify_service import (
    DEFAULT_NOTIFY_CONFIG,
    dispatch_single_channel,
    NOTIFY_CHANNEL_SCHEMA,
    get_channel_spec,
)
from services.pdf_service import download_and_cache_pdf, serve_pdf, is_pdf_cached, get_pdf_path
from services.annotation_service import get_annotations as db_get_annotations, save_annotations as db_save_annotations
from services.mineru_service import convert_pdf_cloud, convert_pdf_cloud_batch, convert_pdf_local, poll_cloud_status, download_cloud_result, _get_mineru_config, get_image_path
from services.chat_service import ChatService


# ============================================================
# 日志配置
# ============================================================
def setup_logging():
    """配置日志"""
    os.makedirs("logs", exist_ok=True)

    log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=getattr(logging, LOGGING_CONFIG.get("level", "INFO")),
        format=LOGGING_CONFIG.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_filename, encoding="utf-8"),
        ],
    )

    return logging.getLogger(__name__)


logger = setup_logging()


# 全文翻译任务状态（进程内）
FULL_TRANSLATION_TASKS: dict[str, dict[str, Any]] = {}
FULL_TRANSLATION_LOCK = threading.Lock()


def _set_full_translation_task(doi: str, payload: dict[str, Any]) -> None:
    with FULL_TRANSLATION_LOCK:
        current = FULL_TRANSLATION_TASKS.get(doi, {})
        current.update(payload)
        current["updated_at"] = datetime.now().isoformat()
        FULL_TRANSLATION_TASKS[doi] = current


def _get_full_translation_task(doi: str) -> Optional[dict[str, Any]]:
    with FULL_TRANSLATION_LOCK:
        task = FULL_TRANSLATION_TASKS.get(doi)
        return dict(task) if task else None


def _build_bilingual_markdown_from_alignment(
    source_blocks: list[str], translated_blocks: list[str]
) -> str:
    """根据后端对齐分段构建逐段双语 Markdown。"""
    if not source_blocks or not translated_blocks:
        return ""

    lines: list[str] = ["# 双语逐段对照", ""]
    max_len = max(len(source_blocks), len(translated_blocks))

    for idx in range(max_len):
        src = source_blocks[idx] if idx < len(source_blocks) else ""
        dst = translated_blocks[idx] if idx < len(translated_blocks) else ""

        if src:
            lines.extend([f"> 原文 {idx + 1}", "", src, ""])
        if dst:
            lines.extend([f"> 译文 {idx + 1}", "", dst, ""])

        lines.extend(["---", ""])

    return "\n".join(lines)


# ============================================================
# 运行时配置管理
# ============================================================
RUNTIME_CONFIG_FILE = "runtime_config.json"
SETUP_COMPLETE_KEY = "setup_complete"


def load_runtime_config() -> dict[str, Any]:
    """加载运行时配置"""
    # 先尝试从数据库加载
    try:
        configs = get_all_configs_from_db()
        if configs:
            return configs
    except Exception as e:
        logger.warning(f"从数据库加载配置失败: {e}")

    # Fallback: 从文件加载
    if os.path.exists(RUNTIME_CONFIG_FILE):
        try:
            with open(RUNTIME_CONFIG_FILE, "r", encoding="utf-8") as f:
                configs = json.load(f)
                # 迁移到数据库
                for name, value in configs.items():
                    save_config_to_db(name, value)
                return configs
        except Exception as e:
            logger.warning(f"从文件加载配置失败: {e}")

    return {}


def save_runtime_config(config: dict[str, Any]):
    """保存运行时配置（同时保存到数据库和文件）"""
    # 保存到数据库（主要存储）
    success = True
    for name, value in config.items():
        if not save_config_to_db(name, value):
            success = False

    # 同时保存到文件（备份）
    try:
        with open(RUNTIME_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"保存配置文件失败: {e}")

    if not success:
        logger.error("部分配置保存失败")


def is_setup_complete(runtime_config: dict[str, Any]) -> bool:
    return runtime_config.get(SETUP_COMPLETE_KEY) is True


def mask_sensitive_fields(config: object) -> object:
    if isinstance(config, dict):
        safe_config: dict[str, object] = {}
        for key, value in cast(dict[object, object], config).items():
            safe_key = str(key)
            key_name = safe_key.lower()
            if key_name == "keywords":
                safe_config[safe_key] = mask_sensitive_fields(value)
            elif key_name in {"secret", "password", "pwd"} or key_name.endswith(
                ("_key", "_token", "_secret")
            ):
                safe_config[safe_key] = "***"
            else:
                safe_config[safe_key] = mask_sensitive_fields(value)
        return safe_config
    if isinstance(config, list):
        return [mask_sensitive_fields(item) for item in cast(list[object], config)]
    return config


def _is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _get_runtime_section(runtime: dict[str, Any], name: str) -> dict[str, Any]:
    section = runtime.get(name)
    if isinstance(section, dict):
        return cast(dict[str, Any], section)
    return {}


def get_config(name: str) -> dict[str, Any]:
    """获取配置（运行时配置优先）"""
    runtime = load_runtime_config()

    config_map: dict[str, dict[str, Any]] = {
        "arxiv": ARXIV_CONFIG,
        "llm_filter": LLM_FILTER_CONFIG,
        "schedule": SCHEDULE_CONFIG,
        "dingtalk": DINGTALK_CONFIG,
        "notify": DEFAULT_NOTIFY_CONFIG,
    }

    base_config = config_map.get(name, {}).copy()
    if name in runtime:
        base_config.update(runtime[name])

    return base_config


# ============================================================
# 论文工作流
# ============================================================
def run_fetch_papers():
    """执行论文获取任务"""
    logger.info("=" * 60)
    logger.info("开始执行论文获取任务")
    logger.info("=" * 60)

    try:
        # 准备服务
        arxiv_config = get_config("arxiv")
        llm_config = get_config("llm_filter")

        arxiv_service = ArxivService(config=arxiv_config)

        # 初始化LLM服务（如果启用）
        llm_service = None
        translation_service = None
        min_stars = llm_config.get("min_stars", 3)
        if llm_config.get("enable", True):
            llm_service = LLMFilterService(config=llm_config)
            translation_service = TranslationService(config=llm_config)

        queue_service = PaperQueueService()

        # 统计
        processed_count = 0
        processing_lock = threading.Lock()
        stop_processing = threading.Event()

        # 创建线程池用于并行处理
        executor = ThreadPoolExecutor(max_workers=1)

        def _background_processor():
            """后台持续处理数据库中未处理的论文"""
            nonlocal processed_count

            logger.info("🔄 后台处理线程已启动，持续从数据库读取未处理论文...")
            batch_size = 50

            while not stop_processing.is_set():
                # 从数据库读取未处理论文（按时间降序，新论文优先）
                unprocessed = get_unprocessed_raw_papers(limit=batch_size)
                if not unprocessed:
                    if stop_processing.is_set():
                        break
                    logger.info("数据库中暂无未处理论文，等待5秒...")
                    stop_processing.wait(5)  # 可中断的等待
                    continue

                logger.info(f"📝 发现 {len(unprocessed)} 篇未处理论文，开始处理...")

                try:
                    # LLM筛选
                    failed_papers = []
                    if llm_service:
                        filtered, failed_papers = llm_service.filter_papers(unprocessed)
                        qualified = [
                            p for p in filtered if p.get("Stars", 0) >= min_stars
                        ]
                    else:
                        filtered = unprocessed
                        qualified = unprocessed

                    # 翻译并保存
                    if qualified:
                        for idx, paper in enumerate(qualified, 1):
                            if stop_processing.is_set():
                                break
                            try:
                                logger.info(
                                    f"  [后台 {idx}/{len(qualified)}] 翻译: {paper['Title'][:50]}..."
                                )
                                translated = (
                                    translation_service.translate_paper(paper)
                                    if translation_service
                                    else paper
                                )

                                save_relevant_papers_to_mysql([translated])
                                translated["ID"] = translated.get("DOI", "")
                                queue_service.enqueue_papers([translated])

                                with processing_lock:
                                    processed_count += 1
                                logger.info(
                                    f"  [后台 {idx}/{len(qualified)}] 已保存 (总计 {processed_count} 篇)"
                                )
                            except Exception as e:
                                logger.error(f"  [后台处理] 失败: {str(e)}")

                    # 只标记成功评估的论文为已处理，失败的保持未处理状态
                    successfully_processed = [
                        p.get("DOI")
                        for p in (filtered if llm_service else unprocessed)
                        if p.get("DOI")
                    ]
                    if successfully_processed:
                        mark_papers_as_processed(
                            [str(doi) for doi in successfully_processed]
                        )
                        logger.info(
                            f"✅ 已标记 {len(successfully_processed)} 篇为已处理"
                        )

                    if failed_papers:
                        logger.warning(
                            f"⚠️ {len(failed_papers)} 篇评估失败，保持未处理状态，等待重新评估"
                        )

                except Exception as e:
                    logger.error(f"后台处理批次出错: {str(e)}")
                    stop_processing.wait(2)

            logger.info("🛑 后台处理线程已停止")

        # 启动后台处理线程
        processing_future = executor.submit(_background_processor)

        # 主线程：获取新论文并保存到数据库
        logger.info("🚀 开始获取新论文...")
        all_papers = arxiv_service.search_papers()  # 不传 callback，只负责获取和保存raw

        # 主线程：获取新论文并保存到数据库
        logger.info("🚀 开始获取新论文...")
        all_papers = arxiv_service.search_papers()  # 不传 callback，只负责获取和保存raw

        if all_papers:
            logger.info(f"✅ 共获取 {len(all_papers)} 篇新论文，已保存到数据库")
        else:
            logger.info("没有找到新论文")

        # 等待一段时间让后台处理完数据库中的论文
        logger.info("等待后台处理线程处理完所有论文...")
        max_wait = 300  # 最多等待5分钟
        wait_count = 0
        while wait_count < max_wait:
            unprocessed = get_unprocessed_raw_papers(limit=1)
            if not unprocessed:
                logger.info("✅ 所有论文已处理完成")
                break
            time.sleep(1)
            wait_count += 1
            if wait_count % 10 == 0:
                logger.info(f"  仍有未处理论文，已等待 {wait_count} 秒...")

        # 停止后台线程
        stop_processing.set()
        executor.shutdown(wait=True)

        total_processed = processed_count

        return {
            "status": "success",
            "message": f"获取了 {len(all_papers) if all_papers else 0} 篇新论文，共处理了 {total_processed} 篇合格论文",
            "count": total_processed,
        }

    except Exception as e:
        logger.error(f"论文获取任务失败: {str(e)}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "message": str(e), "count": 0}


def run_push_papers():
    """执行论文推送任务"""
    logger.info("=" * 60)
    logger.info("开始执行论文推送任务")
    logger.info("=" * 60)

    try:
        from services import get_unpushed_papers, mark_papers_as_pushed

        push_config = get_config("schedule").get("push_papers", {})
        max_papers = push_config.get("max_papers_per_push", 5)

        # 1. 推送前检查是否有未推送的论文，加入队列
        unpushed = get_unpushed_papers(limit=100)
        if unpushed:
            logger.info(f"发现 {len(unpushed)} 篇未推送的论文，加入推送队列")
            queue_service = PaperQueueService()
            queue_service.enqueue_papers(unpushed)

        # 2. 从队列取出论文
        queue_service = PaperQueueService()
        papers = queue_service.dequeue_papers(max_papers)

        if not papers:
            logger.info("队列中没有待推送的论文")
            return {"status": "success", "message": "队列为空", "count": 0}

        # 3. 通过 NotifyService 单通道推送（通道由数据库 notify 配置决定）
        from services.notify_service import NotifyService

        notify_service = NotifyService()
        push_result = notify_service.send_papers_with_result(papers)
        success = bool(push_result.get("success", False))
        raw_success_count = push_result.get("success_count", 0)
        success_count = raw_success_count if isinstance(raw_success_count, int) else 0
        raw_failure_count = push_result.get("failure_count", 0)
        failure_count = raw_failure_count if isinstance(raw_failure_count, int) else 0
        successful_dois = push_result.get("successful_dois", [])
        if not isinstance(successful_dois, list):
            successful_dois = []

        if successful_dois:
            mark_papers_as_pushed([str(doi) for doi in successful_dois if doi])

        if success:
            logger.info(f"成功推送 {success_count} 篇论文")
            return {
                "status": "success",
                "message": f"推送了 {success_count} 篇论文",
                "count": success_count,
            }
        else:
            if success_count > 0:
                logger.warning(
                    f"部分论文推送失败：成功 {success_count} 篇，失败 {failure_count} 篇"
                )
                return {
                    "status": "partial",
                    "message": f"成功推送 {success_count} 篇，失败 {failure_count} 篇",
                    "count": success_count,
                }

            logger.warning("论文推送全部失败")
            return {
                "status": "partial",
                "message": "论文推送全部失败",
                "count": 0,
            }

    except Exception as e:
        logger.error(f"论文推送任务失败: {str(e)}")
        return {"status": "error", "message": str(e), "count": 0}


# ============================================================
# 调度器
# ============================================================
class PaperScheduler:
    """论文调度器"""

    def __init__(self):
        self.running = False
        self.thread = None
        self._setup_jobs()

    def _setup_jobs(self):
        """设置定时任务"""
        schedule.clear()

        config = get_config("schedule")

        # 论文获取任务
        fetch_config = config.get("fetch_papers", {})
        if fetch_config.get("enable", True):
            fetch_time = fetch_config.get("time", "02:00")
            schedule.every().day.at(fetch_time).do(run_fetch_papers)

        # 论文推送任务
        push_config = config.get("push_papers", {})
        if push_config.get("enable", True):
            push_times = push_config.get("times", ["09:00", "14:30"])
            for push_time in push_times:
                schedule.every().day.at(push_time).do(run_push_papers)

    def _run_loop(self):
        """调度循环"""
        while self.running:
            schedule.run_pending()
            time.sleep(30)

    def start(self):
        """启动调度器"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self):
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)

    def reload(self):
        """重新加载配置"""
        self._setup_jobs()

    def get_status(self) -> dict[str, Any]:
        """获取调度器状态"""
        jobs = []
        for job in schedule.get_jobs():
            jobs.append(
                {
                    "next_run": str(job.next_run) if job.next_run else None,
                    "job": str(job),
                }
            )

        return {"running": self.running, "jobs": jobs, "job_count": len(jobs)}


# 全局调度器实例
scheduler = PaperScheduler()


# ============================================================
# FastAPI 应用
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info("🚀 应用启动中...")
    scheduler.start()
    yield
    # 关闭时
    logger.info("🛑 应用关闭中...")
    scheduler.stop()


app = FastAPI(
    title="DailyScholar - AI科研情报助手",
    description="三合一版本：API + 调度器 + 前端",
    version="3.0.0",
    lifespan=lifespan,
)

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# API 路由
# ============================================================


# --- 健康检查 ---
def is_db_available() -> bool:
    if not is_mysql_enabled():
        return False
    return get_mysql_connection() is not None


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "db": is_db_available(),
        "time": datetime.now().isoformat(),
        "version": "3.0.0",
    }


PAPER_FILTER_CONFIG_NAME = "paper_list_filters"


class PaperFilterConfirmRequest(BaseModel):
    show_pushed: bool = True

    comment_filter: str = "all"
    min_stars: int = 0
    only_marked: bool = False
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    search: Optional[str] = None


class TestDBConnectionRequest(BaseModel):
    host: str
    port: int = 3306
    user: str
    password: str = ""
    database: str
    create_tables: bool = True


class TestNotifyRequest(BaseModel):
    channel: str
    config: Dict[str, Any] = Field(default_factory=dict)


def _validate_test_notify_config(channel: str, config: object) -> dict[str, Any]:
    if not isinstance(config, dict):
        raise ValueError("config 必须是对象")

    channel_spec = get_channel_spec(channel)
    required_keys = cast(list[str], channel_spec.get("required_keys", []))
    optional_keys = cast(list[str], channel_spec.get("optional_keys", []))
    allowed_keys = set(required_keys) | set(optional_keys)

    unknown_keys = [key for key in config if key not in allowed_keys]
    if unknown_keys:
        raise ValueError(f"通道 {channel} 包含未定义字段: {', '.join(unknown_keys)}")

    missing_keys = [key for key in required_keys if key not in config]
    if missing_keys:
        raise ValueError(f"通道 {channel} 缺少必填字段: {', '.join(missing_keys)}")

    for key in required_keys:
        value = config.get(key)
        if key == "CONSOLE":
            if value is not True:
                raise ValueError("通道 console 的 CONSOLE 必须为 true")
            continue
        if isinstance(value, str):
            if not value.strip():
                raise ValueError(f"通道 {channel} 的字段 {key} 不能为空")
        elif value is None:
            raise ValueError(f"通道 {channel} 的字段 {key} 不能为空")

    if channel == "wxpusher":
        topic_ids = config.get("WXPUSHER_TOPIC_IDS")
        uids = config.get("WXPUSHER_UIDS")
        if (topic_ids is None or topic_ids == "") and (uids is None or uids == ""):
            raise ValueError(
                "通道 wxpusher 需要至少配置 WXPUSHER_TOPIC_IDS 或 WXPUSHER_UIDS"
            )

    return config


@app.post("/api/setup/test-db")
async def test_db_connection(request: TestDBConnectionRequest):
    result = await asyncio.to_thread(
        _test_db_sync,
        request.host,
        request.port,
        request.user,
        request.password,
        request.database,
        request.create_tables,
    )
    return result


def _test_db_sync(
    host: str, port: int, user: str, password: str, database: str, create_tables: bool
):
    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset="utf8mb4",
        )

        tables_created = False
        if create_tables:
            mysql_config = cast(dict[str, Any], ARXIV_CONFIG.get("mysql", {}) or {})
            tables_created = _ensure_tables_exist(
                connection,
                {
                    "table_raw": mysql_config.get("table_raw", "papers_raw"),
                    "table_relevant": mysql_config.get(
                        "table_relevant", "papers_relevant"
                    ),
                },
            )
            if not tables_created:
                logger.warning("数据库连接成功，但表结构创建失败")
                return {
                    "success": False,
                    "message": "数据库连接成功，但表结构创建失败",
                    "tables_created": False,
                }

        logger.info(f"数据库连接测试成功: {host}:{port}/{database}")
        return {
            "success": True,
            "message": "数据库连接成功",
            "tables_created": tables_created,
        }
    except Exception as e:
        logger.warning(f"数据库连接测试失败: {e}")
        return {
            "success": False,
            "message": f"数据库连接失败: {str(e)}",
            "tables_created": False,
        }
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


class TestLLMConnectionRequest(BaseModel):
    api_key: str = Field(...)
    base_url: str = Field(...)
    model: str = Field(...)


class GenerateResearchRequest(BaseModel):
    brief: str = Field(..., min_length=5, max_length=500, description="一句话研究方向")


def _test_llm_connection(api_key: str, base_url: str, model: str) -> str:
    timeout = httpx.Timeout(30.0)
    with httpx.Client(
        proxy=None,
        timeout=timeout,
        follow_redirects=True,
        trust_env=False,
    ) as http_client:
        client = OpenAI(api_key=api_key, base_url=base_url, http_client=http_client)
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": "Hello, are you working?"}],
            max_tokens=16,
        )
        content = response.choices[0].message.content if response.choices else ""
        return content or "LLM接口响应成功"


def _extract_json_payload(response_text: str) -> dict[str, Any]:
    text = response_text.strip()
    if text.startswith("```"):
        lines = [
            line for line in text.splitlines() if not line.strip().startswith("```")
        ]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    raise ValueError("模型返回内容不是有效的 JSON")


def _normalize_arxiv_keywords(keywords: object) -> list[str]:
    allowed_keywords = {
        "cs.CV",
        "cs.CL",
        "cs.AI",
        "cs.LG",
        "cs.IR",
        "cs.RO",
        "cs.NE",
        "eess.IV",
        "eess.SP",
        "stat.ML",
    }

    if not isinstance(keywords, list):
        return []

    normalized: list[str] = []
    for item in keywords:
        if not isinstance(item, str):
            continue
        keyword = item.strip()
        if keyword in allowed_keywords and keyword not in normalized:
            normalized.append(keyword)
    return normalized[:6]


def generate_research_description(
    brief: str, llm_config: dict[str, Any]
) -> dict[str, Any]:
    prompt = f"""你是一位学术研究顾问。请根据用户的一句话研究方向描述，生成完整的研究配置。

用户输入：{brief}

请生成以下内容（纯JSON格式，不要markdown代码块）：
{{
  "research_description": "详细的研究方向描述（200-400字，包含核心主题、相关技术、潜在应用）",
  "arxiv_keywords": ["cs.CV", "cs.CL", ...],
  "llm_config": {{
    "scoring_anchors": {{
      "high_score_keywords": ["关键词1", "关键词2", ...],
      "medium_score_keywords": ["关键词1", ...],
      "low_score_keywords": ["关键词1", ...]
    }},
    "few_shot_examples": {{
      "high_score": {{
        "title": "高分论文标题示例",
        "abstract": "摘要示例...",
        "score": 90,
        "reason": "高分原因"
      }},
      "medium_score": {{
        "title": "中等分数论文标题示例",
        "abstract": "摘要示例...",
        "score": 60,
        "reason": "中等原因"
      }},
      "low_score": {{
        "title": "低分论文标题示例",
        "abstract": "摘要示例...",
        "score": 15,
        "reason": "低分原因"
      }}
    }},
    "suggested_min_score": 60
  }}
}}"""

    base_url = str(llm_config.get("base_url", "")).strip()
    api_key = str(llm_config.get("api_key", "")).strip()
    model = str(llm_config.get("model", "")).strip()

    if not base_url or not api_key or not model:
        raise ValueError("LLM 配置不完整，请先完成初始化配置")

    timeout = httpx.Timeout(60.0)
    with httpx.Client(
        proxy=None,
        timeout=timeout,
        follow_redirects=True,
        trust_env=False,
    ) as http_client:
        response = http_client.post(
            f"{base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是学术研究顾问，帮助研究生细化研究方向。",
                    },
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.4,
                "max_tokens": 2500,
            },
        )
        response.raise_for_status()
        payload = response.json()

    choices = payload.get("choices", []) if isinstance(payload, dict) else []
    content = ""
    if choices and isinstance(choices, list):
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message", {})
            if isinstance(message, dict):
                content = str(message.get("content", ""))

    if not content.strip():
        raise ValueError("模型未返回有效内容")

    result = _extract_json_payload(content)
    research_description = str(result.get("research_description", "")).strip()

    arxiv_keywords = _normalize_arxiv_keywords(result.get("arxiv_keywords", []))
    llm_config_raw = result.get("llm_config", {})
    llm_config_result = llm_config_raw if isinstance(llm_config_raw, dict) else {}
    if not research_description:
        raise ValueError("模型返回的研究方向描述为空")

    return {
        "research_description": research_description,
        "arxiv_keywords": arxiv_keywords,
        "llm_config": llm_config_result,
    }


@app.post("/api/setup/test-llm")
async def test_llm_connection(request: TestLLMConnectionRequest):
    api_key = request.api_key.strip()
    base_url = request.base_url.strip()
    model = request.model.strip()

    logger.info(f"开始测试LLM接口: base_url={base_url}, model={model}")

    try:
        await asyncio.to_thread(_test_llm_connection, api_key, base_url, model)
        return {"success": True, "message": "LLM接口连接成功", "model": model}
    except httpx.TimeoutException:
        logger.warning(f"LLM接口测试超时: base_url={base_url}, model={model}")
        return {
            "success": False,
            "message": "LLM接口请求超时，请检查网络或接口地址",
            "model": model,
        }
    except Exception as e:
        error_message = str(e).strip() or "未知错误"
        logger.warning(
            f"LLM接口测试失败: base_url={base_url}, model={model}, 错误: {error_message}"
        )
        return {
            "success": False,
            "message": f"LLM接口连接失败: {error_message}",
            "model": model,
        }


@app.post("/api/setup/generate-research")
async def generate_research(request: GenerateResearchRequest):
    brief = request.brief.strip()
    llm_config = get_config("llm_filter")

    logger.info(f"开始生成研究配置: brief={brief[:80]}")

    try:
        data = await asyncio.to_thread(
            generate_research_description, brief, cast(dict[str, Any], llm_config)
        )
        return {"success": True, "data": data}
    except httpx.TimeoutException:
        logger.warning("生成研究配置超时")
        return {"success": False, "message": "生成研究配置超时，请稍后重试"}
    except Exception as e:
        logger.error(f"生成研究配置失败: {str(e)}")
        return {"success": False, "message": "生成研究配置失败，请稍后重试"}


@app.post("/api/setup/test-notify")
async def test_notify(request: TestNotifyRequest):
    channel = request.channel.strip()
    if not channel:
        return {"success": False, "message": "通知通道不能为空"}

    if channel not in NOTIFY_CHANNEL_SCHEMA:
        return {"success": False, "message": f"不支持的通知通道: {channel}"}

    try:
        if channel == "console":
            logger.info("控制台通知测试成功")
            print("【通知测试】控制台通道测试消息：这是一条测试消息")
            return {"success": True, "message": "控制台通知测试成功"}

        channel_config = _validate_test_notify_config(channel, request.config)
        title = "📨 通知通道测试"
        content = "【通知测试】这是一条测试消息"
        success = dispatch_single_channel(channel, title, content, channel_config)

        if success:
            return {
                "success": True,
                "message": f"{get_channel_spec(channel)['display_name']} 测试发送成功",
            }

        return {
            "success": False,
            "message": f"{get_channel_spec(channel)['display_name']} 测试发送失败",
        }
    except Exception as e:
        logger.warning(f"通知测试失败: {e}")
        return {"success": False, "message": f"通知测试失败: {str(e)}"}


# --- 论文接口 ---
@app.get("/api/papers")
async def get_papers(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    show_pushed: bool = Query(True),
    comment_filter: str = Query("all"),  # all/with/without
    min_stars: int = Query(0),  # 最低分数
    only_marked: bool = Query(False),  # 仅显示已标记
    date_start: Optional[str] = None,  # 开始日期
    date_end: Optional[str] = None,  # 结束日期
    date: Optional[str] = None,
    search: Optional[str] = None,  # 搜索关键词
    use_confirmed_filters: bool = Query(False),
):
    """获取论文列表"""
    try:
        if date:
            papers = get_relevant_papers_by_date(date)
            return {
                "success": True,
                "data": papers,
                "total": len(papers),
                "count": len(papers),
            }

        if use_confirmed_filters:
            confirmed_filters = load_config_from_db(PAPER_FILTER_CONFIG_NAME) or {}
            if confirmed_filters:
                show_pushed = bool(confirmed_filters.get("show_pushed", show_pushed))
                comment_filter = str(
                    confirmed_filters.get("comment_filter", comment_filter)
                )
                min_stars = int(confirmed_filters.get("min_stars", min_stars))
                only_marked = bool(confirmed_filters.get("only_marked", only_marked))
                date_start = confirmed_filters.get("date_start", date_start)
                date_end = confirmed_filters.get("date_end", date_end)
                search = confirmed_filters.get("search", search)
                logger.info("已应用确认的论文筛选条件")
            else:
                logger.info("未找到已确认筛选条件，继续使用请求参数")

        result = get_all_relevant_papers(
            limit=limit,
            offset=offset,
            show_pushed=show_pushed,
            comment_filter=comment_filter,
            min_stars=min_stars,
            only_marked=only_marked,
            date_start=date_start,
            date_end=date_end,
            search=search,
        )
        return {
            "success": True,
            "data": result["papers"],
            "total": result["total"],
            "count": len(result["papers"]),
        }
    except Exception as e:
        logger.error(f"获取论文失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/papers/filters/confirm")
async def confirm_paper_filters(request: PaperFilterConfirmRequest):
    try:
        filter_payload = {
            "show_pushed": request.show_pushed,
            "comment_filter": request.comment_filter,
            "min_stars": request.min_stars,
            "only_marked": request.only_marked,
            "date_start": request.date_start,
            "date_end": request.date_end,
            "search": request.search,
        }
        success = save_config_to_db(PAPER_FILTER_CONFIG_NAME, filter_payload)
        if success:
            logger.info("论文筛选条件已确认并保存")
            return {"success": True, "data": filter_payload}
        logger.error("确认论文筛选条件失败")
        return {"success": False, "message": "保存筛选条件失败"}
    except Exception as e:
        logger.error(f"确认论文筛选条件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/filters/confirmed")
async def get_confirmed_paper_filters():
    try:
        confirmed_filters = load_config_from_db(PAPER_FILTER_CONFIG_NAME) or {}
        return {"success": True, "data": confirmed_filters}
    except Exception as e:
        logger.error(f"获取已确认筛选条件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/stats")
async def get_papers_stats():
    """获取论文统计"""
    try:
        stats = get_paper_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PaperMarkRequest(BaseModel):
    doi: str
    marked: bool


@app.post("/api/papers/mark")
async def mark_paper(request: PaperMarkRequest):
    """标记/取消标记论文"""
    try:
        success = update_paper_mark(request.doi, request.marked)
        return {"success": success, "marked": request.marked}
    except Exception as e:
        logger.error(f"标记论文失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PaperCommentRequest(BaseModel):
    doi: str
    comment: str


@app.post("/api/papers/comment")
async def comment_paper(request: PaperCommentRequest):
    """更新论文评论"""
    try:
        success = update_paper_comment(request.doi, request.comment)
        return {"success": success, "comment": request.comment}
    except Exception as e:
        logger.error(f"更新评论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/papers/{doi}")
async def delete_paper_endpoint(doi: str):
    """删除论文"""
    try:
        success = delete_paper(doi)
        return {"success": success}
    except Exception as e:
        logger.error(f"删除论文失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/papers/{doi}/retranslate")
async def retranslate_paper_endpoint(doi: str):
    """重新翻译论文"""
    try:
        from config import ARXIV_CONFIG

        mysql_config = cast(dict[str, Any], ARXIV_CONFIG.get("mysql", {}) or {})
        table = mysql_config.get("table_relevant", "papers_relevant")

        # 获取论文信息
        sql = f"SELECT * FROM `{table}` WHERE DOI = %s"
        papers = execute_query(sql, (doi,))

        if not papers:
            raise HTTPException(status_code=404, detail="论文不存在")

        paper = papers[0]

        # 重新翻译 - 使用运行时配置
        llm_config = get_config("llm_filter")
        translation_service = TranslationService(config=llm_config)
        translated_paper = translation_service.translate_paper(paper)

        # 更新数据库
        update_sql = (
            f"UPDATE `{table}` SET TitleCN = %s, AbstractCN = %s WHERE DOI = %s"
        )
        execute_update(
            update_sql,
            (translated_paper["TitleCN"], translated_paper["AbstractCN"], doi),
        )

        logger.info(f"重新翻译论文成功: {doi}")
        return {
            "success": True,
            "TitleCN": translated_paper["TitleCN"],
            "AbstractCN": translated_paper["AbstractCN"],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重新翻译论文失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/{doi}/pdf")
async def get_paper_pdf(doi: str):
    """获取论文 PDF（自动下载缓存）"""
    try:
        rows = execute_query(
            "SELECT PDFLink, Link FROM papers_relevant WHERE DOI = %s",
            (doi,)
        )

        if not rows:
            raise HTTPException(status_code=404, detail="论文不存在")

        paper = rows[0]
        pdf_url = paper.get("PDFLink") or paper.get("Link")
        if not pdf_url:
            raise HTTPException(status_code=404, detail="无 PDF 链接")

        # 下载并缓存（如果尚未缓存）
        download_and_cache_pdf(pdf_url, doi)

        # 更新缓存状态
        execute_update(
            "UPDATE papers_relevant SET pdf_cached = TRUE WHERE DOI = %s",
            (doi,)
        )

        return serve_pdf(doi)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 PDF 失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/{doi}/html")
def api_get_paper_html(doi: str):
    """代理 arXiv HTML 页面用于内嵌阅读"""
    try:
        rows = execute_query(
            "SELECT PDFLink, Link FROM papers_relevant WHERE DOI = %s",
            (doi,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="论文不存在")

        link = rows[0].get("PDFLink") or rows[0].get("Link", "")
        if "arxiv.org/pdf/" not in link:
            raise HTTPException(status_code=400, detail="非 arXiv 论文，不支持 HTML 阅读")

        html_url = link.replace("/pdf/", "/html/")

        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            resp = client.get(html_url)
            if resp.status_code == 404:
                raise HTTPException(status_code=404, detail="该论文没有 HTML 版本")
            resp.raise_for_status()

        html_content = resp.content.decode("utf-8", errors="replace")

        # 将所有相对路径重写为 arxiv.org 绝对路径，确保 CSS/JS/图片从 arXiv 加载
        import re
        html_content = re.sub(
            r'(href\s*=\s*["\'])/(?!/|http)',
            r'\g<1>https://arxiv.org/',
            html_content
        )
        html_content = re.sub(
            r'(src\s*=\s*["\'])/(?!/|http)',
            r'\g<1>https://arxiv.org/',
            html_content
        )
        html_content = re.sub(
            r'(action\s*=\s*["\'])/(?!/|http)',
            r'\g<1>https://arxiv.org/',
            html_content
        )

        return HTMLResponse(content=html_content, media_type="text/html; charset=utf-8")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 HTML 页面失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/{doi}/detail")
async def get_paper_detail(doi: str):
    """获取单篇论文详情"""
    try:
        rows = execute_query(
            "SELECT * FROM papers_relevant WHERE DOI = %s",
            (doi,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="论文不存在")
        return {"success": True, "data": rows[0]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取论文详情失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== 标注 API =====

@app.get("/api/papers/{doi}/annotations")
async def api_get_annotations(doi: str):
    """获取论文标注"""
    try:
        annotations = db_get_annotations(doi)
        return {"success": True, "data": annotations}
    except Exception as e:
        logger.error(f"获取标注失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/papers/{doi}/annotations")
async def api_save_annotations(doi: str, request: Request):
    """保存论文标注"""
    try:
        body = await request.json()
        result = db_save_annotations(doi, body.get("annotations", []))
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"保存标注失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== MinerU 转换 API =====

@app.post("/api/papers/{doi}/convert")
async def api_convert_paper(doi: str, request: Request):
    """触发 PDF 转 Markdown"""
    try:
        body = await request.json()
        mode = body.get("mode", "cloud")

        # 获取论文信息
        rows = execute_query(
            "SELECT PDFLink, Link FROM papers_relevant WHERE DOI = %s",
            (doi,)
        )
        if not rows:
            raise HTTPException(status_code=404, detail="论文不存在")

        paper = rows[0]
        pdf_url = paper.get("PDFLink") or paper.get("Link")
        config = _get_mineru_config()

        if mode == "local":
            if not is_pdf_cached(doi):
                raise HTTPException(status_code=400, detail="本地模式需要先下载 PDF，请先打开 PDF 预览")
            pdf_path = get_pdf_path(doi)
            endpoint = config.get("endpoint", "http://localhost:18000")
            result = convert_pdf_local(pdf_path, endpoint)
            if result.get("status") == "completed":
                execute_update(
                    "UPDATE papers_relevant SET markdown_content = %s, markdown_images = %s WHERE DOI = %s",
                    (result["markdown"], json.dumps(result.get("images", [])), doi)
                )
            return {"success": True, "data": result}
        else:
            # 云端模式：优先用论文 PDFLink URL，无 URL 则本地缓存批量上传
            api_key = config.get("api_key", "")
            if not api_key:
                raise HTTPException(status_code=400, detail="未配置 MinerU API Key")

            if pdf_url:
                # 有公网 URL，用单文件 API
                result = convert_pdf_cloud(pdf_url, api_key)
            elif is_pdf_cached(doi):
                # 无公网 URL 但有本地缓存，用批量上传 API
                pdf_path = get_pdf_path(doi)
                result = convert_pdf_cloud_batch(pdf_path, api_key)
            else:
                raise HTTPException(status_code=400, detail="无可用的 PDF 来源（无公网链接且未缓存）")

            # 保存 task_id 以便后续轮询
            if result.get("task_id"):
                execute_update(
                    "UPDATE papers_relevant SET markdown_images = %s WHERE DOI = %s",
                    (json.dumps({"mineru_task_id": result["task_id"]}), doi)
                )
            return {"success": True, "data": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"转换失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/{doi}/convert/status")
async def api_convert_status(doi: str):
    """查询转换状态（云端模式会自动轮询并存储结果）"""
    rows = execute_query(
        "SELECT markdown_content, markdown_images FROM papers_relevant WHERE DOI = %s",
        (doi,)
    )

    if not rows:
        return {"success": True, "data": {"status": "pending"}}

    row = rows[0]
    if row.get("markdown_content"):
        return {"success": True, "data": {"status": "completed"}}

    # 检查是否有进行中的云端任务
    images_data = row.get("markdown_images")
    task_id = None
    if images_data:
        if isinstance(images_data, str):
            try:
                images_data = json.loads(images_data)
            except (json.JSONDecodeError, TypeError):
                images_data = {}
        if isinstance(images_data, dict) and images_data.get("mineru_task_id"):
            task_id = images_data["mineru_task_id"]

    if task_id:
        try:
            config = _get_mineru_config()
            api_key = config.get("api_key", "")
            if api_key:
                status_data = poll_cloud_status(task_id, api_key)
                task_state = status_data.get("state", "")

                if task_state == "done":
                    # 下载并存储结果
                    result = download_cloud_result(task_id, api_key, doi)
                    if result.get("status") == "completed" and result.get("markdown"):
                        execute_update(
                            "UPDATE papers_relevant SET markdown_content = %s, markdown_images = %s WHERE DOI = %s",
                            (result["markdown"], json.dumps(result.get("images", [])), doi)
                        )
                        return {"success": True, "data": {"status": "completed"}}
                    else:
                        return {"success": True, "data": {"status": "failed", "error": result.get("error", "下载结果失败")}}
                elif task_state == "failed":
                    return {"success": True, "data": {"status": "failed", "error": status_data.get("error", "转换失败")}}
                elif task_state in ("pending", "running"):
                    return {"success": True, "data": {"status": "processing"}}

                return {"success": True, "data": {"status": "processing"}}
        except Exception as e:
            logger.warning(f"轮询云端转换状态失败: {e}")

    return {"success": True, "data": {"status": "pending"}}


@app.get("/api/papers/{doi}/markdown")
async def api_get_markdown(doi: str):
    """获取转换后的 Markdown"""
    rows = execute_query(
        "SELECT markdown_content, markdown_images FROM papers_relevant WHERE DOI = %s",
        (doi,)
    )

    if not rows or not rows[0].get("markdown_content"):
        raise HTTPException(status_code=404, detail="尚未转换为 Markdown")

    row = rows[0]
    images = row.get("markdown_images")
    if isinstance(images, str):
        try:
            images = json.loads(images)
        except (json.JSONDecodeError, TypeError):
            images = []
    # 过滤掉内部 task_id 元数据
    if isinstance(images, dict):
        images = images.get("images", [])

    return {"success": True, "data": {"markdown": row["markdown_content"], "images": images or []}}


@app.get("/api/papers/{doi}/markdown/images/{image_name}")
async def api_get_markdown_image(doi: str, image_name: str):
    """获取 MinerU 转换后的 Markdown 引用图片"""
    img_path = get_image_path(doi, image_name)
    if not os.path.exists(img_path):
        raise HTTPException(status_code=404, detail="图片不存在")
    return FileResponse(img_path)


# ===== 全文翻译 API =====

async def _run_full_translation_task(doi: str, text: str) -> None:
    """后台执行全文翻译并持续更新任务状态。"""
    try:
        from services.translation_service import TranslationService

        llm_config = get_config("llm_filter")
        translation_svc = TranslationService(config=llm_config)

        def _on_progress(progress: dict[str, Any]) -> None:
            _set_full_translation_task(
                doi,
                {
                    "status": progress.get("status", "processing"),
                    "progress": progress.get("progress", 0),
                    "current": progress.get("current", 0),
                    "total": progress.get("total", 0),
                    "message": progress.get("message", "正在翻译..."),
                },
            )

        full_translation = await asyncio.to_thread(
            translation_svc.translate_text,
            text,
            "en",
            "zh",
            doi,
            _on_progress,
        )

        alignment = translation_svc.get_last_alignment()
        bilingual_markdown = _build_bilingual_markdown_from_alignment(
            alignment.get("source_blocks", []),
            alignment.get("translated_blocks", []),
        )

        execute_update(
            "UPDATE papers_relevant SET full_translation = %s WHERE DOI = %s",
            (full_translation, doi),
        )

        _set_full_translation_task(
            doi,
            {
                "status": "completed",
                "progress": 100,
                "current": _get_full_translation_task(doi).get("total", 0) if _get_full_translation_task(doi) else 0,
                "total": _get_full_translation_task(doi).get("total", 0) if _get_full_translation_task(doi) else 0,
                "message": "翻译完成",
                "translation": full_translation,
                "bilingual_markdown": bilingual_markdown,
            },
        )
    except Exception as e:
        logger.error(f"全文翻译后台任务失败: {e}")
        _set_full_translation_task(
            doi,
            {
                "status": "failed",
                "progress": 0,
                "message": "翻译失败",
                "error": str(e),
            },
        )

@app.post("/api/papers/{doi}/translate-full")
async def api_translate_full(doi: str, request: Request):
    """触发全文翻译（后台任务）"""
    try:
        body = await request.json()
        source = body.get("source", "markdown")
        force = bool(body.get("force", False))

        existing_task = _get_full_translation_task(doi)
        if existing_task and existing_task.get("status") == "processing":
            return {"success": True, "data": existing_task}

        rows = execute_query(
            "SELECT markdown_content, Abstract, full_translation FROM papers_relevant WHERE DOI = %s",
            (doi,)
        )

        if not rows:
            raise HTTPException(status_code=404, detail="论文不存在")

        row = rows[0]

        # 已有全文翻译则直接复用，避免重复翻译
        if not force and row.get("full_translation"):
            reused_translation = row.get("full_translation")
            _set_full_translation_task(
                doi,
                {
                    "status": "completed",
                    "progress": 100,
                    "current": 1,
                    "total": 1,
                    "message": "复用已有全文翻译",
                    "translation": reused_translation,
                    "source": source,
                    "error": "",
                },
            )
            return {
                "success": True,
                "data": {
                    "status": "completed",
                    "progress": 100,
                    "message": "复用已有全文翻译",
                    "translation": reused_translation,
                },
            }

        text = ""
        if source == "markdown" and row.get("markdown_content"):
            text = row["markdown_content"]
        elif row.get("Abstract"):
            text = row["Abstract"]
        else:
            raise HTTPException(status_code=400, detail="无可翻译的内容")

        _set_full_translation_task(
            doi,
            {
                "status": "processing",
                "progress": 0,
                "current": 0,
                "total": 0,
                "message": "翻译任务已启动",
                "source": source,
                "error": "",
            },
        )

        asyncio.create_task(_run_full_translation_task(doi, text))

        return {
            "success": True,
            "data": {
                "status": "processing",
                "progress": 0,
                "message": "翻译任务已启动",
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"全文翻译失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/{doi}/translate-full/status")
async def api_translate_full_status(doi: str):
    """查询全文翻译任务状态"""
    task = _get_full_translation_task(doi)
    if task:
        return {"success": True, "data": task}

    rows = execute_query(
        "SELECT full_translation FROM papers_relevant WHERE DOI = %s",
        (doi,),
    )
    if rows and rows[0].get("full_translation"):
        return {
            "success": True,
            "data": {
                "status": "completed",
                "progress": 100,
                "message": "翻译完成",
                "translation": rows[0]["full_translation"],
            },
        }

    return {
        "success": True,
        "data": {
            "status": "pending",
            "progress": 0,
            "message": "暂无翻译任务",
        },
    }


@app.delete("/api/papers/{doi}/translate-full/cache")
async def api_clear_translate_full_cache(doi: str):
    """清除某论文的全文翻译缓存（分块缓存 + 全文缓存）。"""
    try:
        from services.translation_service import TranslationService

        chunk_deleted = TranslationService.clear_chunk_cache_for_doi(doi)
        full_deleted = execute_update(
            "UPDATE papers_relevant SET full_translation = NULL WHERE DOI = %s",
            (doi,),
        )

        _set_full_translation_task(
            doi,
            {
                "status": "pending",
                "progress": 0,
                "current": 0,
                "total": 0,
                "message": "缓存已清除",
                "error": "",
                "translation": "",
            },
        )

        return {
            "success": True,
            "data": {
                "doi": doi,
                "chunk_cache_deleted": chunk_deleted,
                "full_translation_cleared": full_deleted > 0,
            },
        }
    except Exception as e:
        logger.error(f"清除翻译缓存失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/{doi}/translate-full/stream")
async def api_translate_full_stream(doi: str):
    """SSE 流式返回全文翻译进度。"""

    async def event_generator():
        last_payload = ""
        idle_rounds = 0
        max_idle_rounds = 30 * 60  # 最多保持 30 分钟

        while idle_rounds < max_idle_rounds:
            task = _get_full_translation_task(doi)

            if task:
                payload = {
                    "status": task.get("status", "processing"),
                    "progress": task.get("progress", 0),
                    "current": task.get("current", 0),
                    "total": task.get("total", 0),
                    "message": task.get("message", "正在翻译..."),
                    "error": task.get("error", ""),
                }
                if task.get("status") == "completed":
                    payload["translation"] = task.get("translation", "")
                    payload["bilingual_markdown"] = task.get("bilingual_markdown", "")
            else:
                rows = execute_query(
                    "SELECT full_translation FROM papers_relevant WHERE DOI = %s",
                    (doi,),
                )
                if rows and rows[0].get("full_translation"):
                    payload = {
                        "status": "completed",
                        "progress": 100,
                        "current": 1,
                        "total": 1,
                        "message": "翻译完成",
                        "translation": rows[0]["full_translation"],
                        "error": "",
                    }
                else:
                    payload = {
                        "status": "pending",
                        "progress": 0,
                        "current": 0,
                        "total": 0,
                        "message": "等待翻译任务启动",
                        "error": "",
                    }

            payload_text = json.dumps(payload, ensure_ascii=False)
            if payload_text != last_payload:
                yield f"data: {payload_text}\n\n"
                last_payload = payload_text

            if payload.get("status") in {"completed", "failed", "error"}:
                break

            idle_rounds += 1
            await asyncio.sleep(1)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ===== 论文精读对话 API =====

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


@app.post("/api/papers/{doi}/chat")
def api_chat_with_paper(doi: str, body: ChatMessageRequest):
    """发送消息，SSE 流式返回"""
    message = body.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="消息不能为空")

    rows = execute_query(
        "SELECT DOI, Title, TitleCN, Abstract, AbstractCN, Stars, RelevanceReason, markdown_content "
        "FROM papers_relevant WHERE DOI = %s",
        (doi,)
    )
    if not rows:
        raise HTTPException(status_code=404, detail="论文不存在")

    paper_context = rows[0]
    chat_svc = ChatService(config=get_config("llm_filter"))
    return StreamingResponse(
        chat_svc.send_message_stream(doi, message, paper_context),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
    )


@app.get("/api/papers/{doi}/chat/history")
async def api_get_chat_history(doi: str):
    """获取对话历史"""
    try:
        chat_svc = ChatService(config=get_config("llm_filter"))
        messages = chat_svc.get_chat_history(doi)
        return {"success": True, "data": messages}
    except Exception as e:
        logger.error(f"获取对话历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/papers/{doi}/chat")
async def api_clear_chat_history(doi: str):
    """清空对话历史"""
    try:
        chat_svc = ChatService(config=get_config("llm_filter"))
        chat_svc.clear_chat_history(doi)
        return {"success": True, "message": "对话已清空"}
    except Exception as e:
        logger.error(f"清空对话失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/{doi}/chat/suggestions")
async def api_get_chat_suggestions(doi: str):
    """获取推荐问题"""
    try:
        rows = execute_query(
            "SELECT Title, TitleCN, Abstract, AbstractCN, Stars, RelevanceReason FROM papers_relevant WHERE DOI = %s",
            (doi,)
        )
        paper_data = rows[0] if rows else {}
        suggestions = ChatService.get_suggestions(paper_data)
        return {"success": True, "data": suggestions}
    except Exception as e:
        logger.error(f"获取推荐问题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 队列接口 ---
@app.get("/api/queue/status")
async def get_queue_status():
    """获取队列状态"""
    try:
        queue_service = PaperQueueService()
        size = queue_service.get_queue_size()
        preview = queue_service.get_queue_preview(5)

        return {"success": True, "data": {"size": size, "preview": preview}}
    except Exception as e:
        logger.error(f"获取队列状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 配置接口 ---
@app.get("/api/setup/status")
async def get_setup_status():
    """获取初始化状态"""
    runtime = load_runtime_config()
    setup_complete = is_setup_complete(runtime)

    return {
        "success": True,
        "data": {"needs_setup": not setup_complete, "missing": []},
    }


@app.get("/api/setup/existing-config")
async def get_existing_config():
    runtime = cast(dict[str, Any], load_runtime_config() or {})

    arxiv_config = _get_runtime_section(runtime, "arxiv")
    llm_config = _get_runtime_section(runtime, "llm_filter")
    notify_config = _get_runtime_section(runtime, "notify")
    mysql_config = _get_runtime_section(arxiv_config, "mysql")

    mysql_safe = mask_sensitive_fields(mysql_config)
    llm_safe = mask_sensitive_fields(llm_config)
    notify_safe = mask_sensitive_fields(notify_config)
    arxiv_safe = mask_sensitive_fields(arxiv_config)

    has_mysql = bool(
        mysql_config
        and mysql_config.get("enable", True) is True
        and _is_non_empty_string(mysql_config.get("host"))
        and _is_non_empty_string(mysql_config.get("database"))
        and _is_non_empty_string(mysql_config.get("user"))
        and _is_non_empty_string(mysql_config.get("password"))
    )

    has_llm = bool(
        llm_config
        and llm_config.get("enable", True) is True
        and _is_non_empty_string(llm_config.get("base_url"))
        and _is_non_empty_string(llm_config.get("model"))
        and _is_non_empty_string(llm_config.get("api_key"))
    )

    research_description = runtime.get("research_description", "")
    has_research = _is_non_empty_string(research_description)
    research_preview = str(research_description).strip()[:100] if has_research else ""

    has_notify = bool(
        notify_config
        and _is_non_empty_string(notify_config.get("active_channel"))
        and isinstance(notify_config.get("channels"), dict)
        and bool(cast(dict[str, Any], notify_config.get("channels")))
    )

    arxiv_keywords = arxiv_config.get("keywords")
    has_arxiv = bool(
        arxiv_config
        and isinstance(arxiv_keywords, list)
        and any(
            _is_non_empty_string(item) for item in cast(list[object], arxiv_keywords)
        )
    )

    return {
        "success": True,
        "data": {
            "has_mysql": has_mysql,
            "has_llm": has_llm,
            "has_research": has_research,
            "has_notify": has_notify,
            "has_arxiv": has_arxiv,
            "mysql": {
                "host": mysql_safe.get("host", "")
                if isinstance(mysql_safe, dict)
                else "",
                "port": mysql_safe.get("port", 3306)
                if isinstance(mysql_safe, dict)
                else 3306,
                "database": mysql_safe.get("database", "")
                if isinstance(mysql_safe, dict)
                else "",
                "user": mysql_safe.get("user", "")
                if isinstance(mysql_safe, dict)
                else "",
            },
            "llm": {
                "base_url": llm_safe.get("base_url", "")
                if isinstance(llm_safe, dict)
                else "",
                "model": llm_safe.get("model", "")
                if isinstance(llm_safe, dict)
                else "",
            },
            "research_description": research_preview,
            "notify": {
                "active_channel": notify_safe.get("active_channel", "")
                if isinstance(notify_safe, dict)
                else "",
            },
            "arxiv": {
                "keywords": arxiv_safe.get("keywords", [])
                if isinstance(arxiv_safe, dict)
                else [],
            },
        },
    }


@app.post("/api/setup/complete")
async def complete_setup():
    """标记初始化完成"""
    try:
        save_runtime_config({SETUP_COMPLETE_KEY: True})
        return {"success": True, "message": "初始化已完成"}
    except Exception as e:
        logger.error(f"标记初始化完成失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/setup/reset")
async def reset_setup():
    try:
        save_runtime_config({SETUP_COMPLETE_KEY: False})
        return {"success": True, "message": "初始化状态已重置"}
    except Exception as e:
        logger.error(f"重置初始化状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config/all")
async def get_all_config():
    """获取所有配置"""
    from config import RESEARCH_DESCRIPTION
    from services.prompt_service import DEFAULT_PROMPT_CONFIG

    # 从数据库加载研究方向（如果有）
    runtime = cast(dict[str, object], load_runtime_config() or {})
    research_description = str(
        runtime.get("research_description", RESEARCH_DESCRIPTION)
    )

    llm_raw = cast(dict[str, object], get_config("llm_filter") or {})
    notify_raw = cast(dict[str, object], get_config("notify") or {})
    llm_config = mask_sensitive_fields(llm_raw)
    notify_config = mask_sensitive_fields(notify_raw)

    # 加载 prompt_config
    try:
        from services.mysql_service import load_config_from_db

        prompt_config = load_config_from_db("prompt_config") or {}
        # 合并默认值和数据库值
        full_prompt_config = {**DEFAULT_PROMPT_CONFIG, **prompt_config}
    except Exception:
        full_prompt_config = DEFAULT_PROMPT_CONFIG

    return {
        "success": True,
        "data": {
            "arxiv": get_config("arxiv"),
            "llm_filter": llm_config,
            "schedule": get_config("schedule"),
            "notify": notify_config,
            "research_description": research_description,
            "prompt_config": full_prompt_config,
            "dingtalk": {
                "app_key": DINGTALK_CONFIG.get("app_key", ""),
                "robot_code": DINGTALK_CONFIG.get("robot_code", ""),
                # 不返回敏感信息
            },
        },
    }


class ConfigUpdate(BaseModel):
    config: Dict[str, Any]


@app.put("/api/config/{name}")
async def update_config(name: str, update: ConfigUpdate):
    """更新配置"""
    try:
        runtime = load_runtime_config()

        # 特殊处理研究方向（字符串而非字典）
        if name == "research_description":
            runtime["research_description"] = update.config.get("content", "")
        else:
            runtime[name] = update.config

        save_runtime_config(runtime)

        if name == "notify":
            saved_notify = load_config_from_db("notify")
            if saved_notify != runtime.get("notify"):
                raise HTTPException(
                    status_code=500, detail="notify 配置保存到数据库失败"
                )

        # 重新加载调度器
        if name == "schedule":
            scheduler.reload()

        return {"success": True, "message": f"配置 {name} 已更新"}
    except Exception as e:
        logger.error(f"更新配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 调度器接口 ---
@app.get("/api/scheduler/status")
async def get_scheduler_status():
    """获取调度器状态"""
    return {"success": True, "data": scheduler.get_status()}


@app.post("/api/scheduler/reload")
async def reload_scheduler():
    """重新加载调度器"""
    try:
        scheduler.reload()
        return {"success": True, "message": "调度器已重新加载"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- 手动操作接口 ---
@app.post("/api/actions/fetch-now")
async def fetch_now(background_tasks: BackgroundTasks):
    """立即执行论文获取"""
    try:
        # 在后台任务中执行
        background_tasks.add_task(run_fetch_papers)
        return {"success": True, "message": "论文获取任务已在后台启动，请稍后查看结果"}
    except Exception as e:
        logger.error(f"启动论文获取任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/actions/push-now")
async def push_now(background_tasks: BackgroundTasks):
    """立即执行论文推送"""
    try:
        # 在后台任务中执行
        background_tasks.add_task(run_push_papers)
        return {"success": True, "message": "论文推送任务已在后台启动"}
    except Exception as e:
        logger.error(f"启动论文推送任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/actions/process-now")
async def process_now(background_tasks: BackgroundTasks):
    """立即处理未解析的论文"""
    try:

        def process_unprocessed():
            """处理未解析论文的后台任务"""
            logger.info("=" * 60)
            logger.info("开始处理未解析的论文")
            logger.info("=" * 60)

            try:
                # 从配置读取处理数量
                process_config = get_config("schedule").get("process_papers", {})
                batch_size = process_config.get("batch_size", 100)

                # 获取未处理的论文
                unprocessed = get_unprocessed_raw_papers(limit=batch_size)
                total = len(unprocessed)

                if total == 0:
                    logger.info("没有未处理的论文")
                    return

                logger.info(f"找到 {total} 篇未处理的论文（配置限制：{batch_size}篇）")

                # 初始化服务
                llm_config = get_config("llm_filter")
                min_stars = llm_config.get("min_stars", 3)
                llm_service = (
                    LLMFilterService(config=llm_config)
                    if llm_config.get("enable", True)
                    else None
                )
                translation_service = TranslationService(config=llm_config)
                queue_service = PaperQueueService()

                processed_count = 0
                relevant_count = 0

                # LLM筛选
                failed_papers = []
                if llm_service:
                    logger.info(f"开始LLM筛选 {total} 篇论文...")
                    filtered, failed_papers = llm_service.filter_papers(unprocessed)
                    qualified = [p for p in filtered if p.get("Stars", 0) >= min_stars]
                else:
                    filtered = unprocessed
                    qualified = unprocessed

                logger.info(
                    f"筛选完成: {len(qualified)}/{total} 篇论文达到 {min_stars}星及以上"
                )

                # 翻译并保存
                if qualified:
                    for idx, paper in enumerate(qualified, 1):
                        try:
                            logger.info(
                                f"  [{idx}/{len(qualified)}] 翻译: {paper['Title'][:50]}..."
                            )
                            translated = translation_service.translate_paper(paper)

                            save_relevant_papers_to_mysql([translated])
                            translated["ID"] = translated.get("DOI", "")
                            queue_service.enqueue_papers([translated])

                            relevant_count += 1
                            logger.info(
                                f"  [{idx}/{len(qualified)}] 已保存 (总计 {relevant_count} 篇)"
                            )
                        except Exception as e:
                            logger.error(
                                f"  [{idx}/{len(qualified)}] 处理失败: {str(e)}"
                            )

                # 只标记成功评估的论文为已处理
                successfully_processed = [
                    p.get("DOI")
                    for p in (filtered if llm_service else unprocessed)
                    if p.get("DOI")
                ]
                if successfully_processed:
                    mark_papers_as_processed(
                        [str(doi) for doi in successfully_processed]
                    )
                    processed_count = len(successfully_processed)

                if failed_papers:
                    logger.warning(
                        f"⚠️ {len(failed_papers)} 篇评估失败，保持未处理状态，等待重新评估"
                    )

                logger.info("=" * 60)
                logger.info(
                    f"处理完成: 共处理 {processed_count} 篇，相关 {relevant_count} 篇"
                )
                logger.info("=" * 60)

            except Exception as e:
                logger.error(f"处理未解析论文失败: {e}")
                import traceback

                logger.error(traceback.format_exc())

        # 在后台任务中执行
        background_tasks.add_task(process_unprocessed)
        return {"success": True, "message": "论文处理任务已在后台启动，请稍后查看结果"}
    except Exception as e:
        logger.error(f"启动论文处理任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 日志接口 ---
@app.get("/api/logs/list")
async def list_logs():
    """获取日志文件列表"""
    try:
        log_dir = "logs"
        if not os.path.exists(log_dir):
            return {"success": True, "data": []}

        files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
        files.sort(reverse=True)  # 最新的在前面
        return {"success": True, "data": files}
    except Exception as e:
        logger.error(f"获取日志列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/content")
async def get_log_content(filename: Optional[str] = None, lines: int = 100):
    """获取日志内容"""
    try:
        log_dir = "logs"
        if not filename:
            # 默认获取最新的日志
            files = [f for f in os.listdir(log_dir) if f.endswith(".log")]
            if not files:
                return {"success": True, "data": ""}
            files.sort(reverse=True)
            filename = files[0]

        if ".." in filename or "/" in filename or "\\" in filename:
            raise HTTPException(status_code=400, detail="无效的文件名")

        file_path = os.path.realpath(os.path.join(log_dir, filename))
        log_dir_resolved = os.path.realpath(log_dir)
        if not file_path.startswith(log_dir_resolved + os.sep):
            raise HTTPException(status_code=403, detail="禁止访问")

        if not os.path.isfile(file_path):
            raise HTTPException(status_code=404, detail="日志文件不存在")

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.readlines()

        # 返回最后N行
        return {
            "success": True,
            "data": "".join(content[-lines:]),
            "filename": filename,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取日志内容失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# --- 提示词管理接口 ---
@app.get("/api/prompts")
async def get_prompts():
    """获取所有提示词配置"""
    try:
        from services.prompt_service import DEFAULT_PROMPT_CONFIG, get_prompt

        prompts = {
            "llm_system_prompt": get_prompt("llm_system_prompt"),
            "llm_few_shot_examples": get_prompt("llm_few_shot_examples"),
            "llm_scoring_anchors": get_prompt("llm_scoring_anchors"),
            "llm_evaluation_template": get_prompt("llm_evaluation_template"),
            "translation_system_prompt": get_prompt("translation_system_prompt"),
            "translation_template": get_prompt("translation_template"),
        }
        return {"success": True, "data": prompts}
    except Exception as e:
        logger.error(f"获取提示词配置失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class PromptUpdateRequest(BaseModel):
    content: str


@app.put("/api/prompts/{prompt_key}")
async def update_prompt(prompt_key: str, request: PromptUpdateRequest):
    """更新提示词（热更新）"""
    try:
        from services.prompt_service import DEFAULT_PROMPT_CONFIG
        from services.mysql_service import load_config_from_db, save_config_to_db

        if prompt_key not in DEFAULT_PROMPT_CONFIG:
            raise HTTPException(
                status_code=400, detail=f"未知的提示词key: {prompt_key}"
            )

        # 加载现有配置
        prompt_config = load_config_from_db("prompt_config") or {}
        if not isinstance(prompt_config, dict):
            prompt_config = {}

        # 更新指定key
        prompt_config[prompt_key] = request.content

        # 保存到数据库
        if save_config_to_db("prompt_config", prompt_config):
            return {"success": True, "message": f"提示词 {prompt_key} 已更新"}
        else:
            raise HTTPException(status_code=500, detail="保存到数据库失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/prompts/{prompt_key}/reset")
async def reset_prompt(prompt_key: str):
    """重置提示词为默认值"""
    try:
        from services.prompt_service import DEFAULT_PROMPT_CONFIG
        from services.mysql_service import load_config_from_db, save_config_to_db

        if prompt_key not in DEFAULT_PROMPT_CONFIG:
            raise HTTPException(
                status_code=400, detail=f"未知的提示词key: {prompt_key}"
            )

        # 加载现有配置
        prompt_config = load_config_from_db("prompt_config") or {}
        if not isinstance(prompt_config, dict):
            prompt_config = {}

        # 重置为默认值
        prompt_config[prompt_key] = DEFAULT_PROMPT_CONFIG[prompt_key]

        # 保存到数据库
        if save_config_to_db("prompt_config", prompt_config):
            return {"success": True, "message": f"提示词 {prompt_key} 已重置为默认值"}
        else:
            raise HTTPException(status_code=500, detail="保存到数据库失败")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"重置提示词失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# 静态文件服务
# ============================================================
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

# 挂载静态资源目录
if os.path.exists(os.path.join(STATIC_DIR, "assets")):
    app.mount(
        "/assets",
        StaticFiles(directory=os.path.join(STATIC_DIR, "assets")),
        name="assets",
    )


# 前端路由
@app.get("/")
async def serve_index():
    """服务前端首页"""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    else:
        return JSONResponse(
            {
                "message": "欢迎使用DailyScholar v3.0!\n\n系统已准备就绪，请在系统配置中设置您的研究方向描述，以获取最精准的论文推送。",
                "docs": "/docs",
                "api": "/api/health",
                "note": "请将前端构建文件放到 static/ 目录",
            }
        )


@app.get("/{path:path}")
async def serve_static(path: str):
    """服务其他静态文件（Vite构建输出 + SPA路由兜底）"""
    # 先尝试直接找文件
    file_path = os.path.join(STATIC_DIR, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)

    # 已知的静态资源扩展名才视为文件请求，找不到则404
    static_extensions = {'.js', '.css', '.map', '.png', '.jpg', '.jpeg', '.gif',
                         '.svg', '.ico', '.woff', '.woff2', '.ttf', '.eot', '.webp'}
    ext = os.path.splitext(path)[1].lower()
    if ext in static_extensions:
        raise HTTPException(status_code=404, detail="Not found")

    # 其余路径（SPA路由、DOI 含点的路径）都返回 index.html
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="Not found")


# ============================================================
# 主入口
# ============================================================
if __name__ == "__main__":
    print("""
╔══════════════════════════════════════════════════════════╗
        ║         DailyScholar v3.0 - 您的AI科研情报助手           ║
║                                                          ║
║  功能：后端API + 定时调度 + 前端页面服务                 ║
║  端口：20001                                             ║
║  文档：http://localhost:20001/docs                       ║
╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run("app:app", host="0.0.0.0", port=20001, reload=False, log_level="info")
