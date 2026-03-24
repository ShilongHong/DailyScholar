"""
ArXiv论文推送系统 v3.0 - 三合一版
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
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
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
            logger.info(f"从数据库加载了 {len(configs)} 个配置")
            return configs
    except Exception as e:
        logger.warning(f"从数据库加载配置失败: {e}")

    # Fallback: 从文件加载
    if os.path.exists(RUNTIME_CONFIG_FILE):
        try:
            with open(RUNTIME_CONFIG_FILE, "r", encoding="utf-8") as f:
                configs = json.load(f)
                logger.info(f"从文件加载了 {len(configs)} 个配置")
                # 迁移到数据库
                for name, value in configs.items():
                    save_config_to_db(name, value)
                logger.info("已将文件配置迁移到数据库")
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
            logger.info(f"📅 论文获取任务已设置: 每天 {fetch_time}")

        # 论文推送任务
        push_config = config.get("push_papers", {})
        if push_config.get("enable", True):
            push_times = push_config.get("times", ["09:00", "14:30"])
            for push_time in push_times:
                schedule.every().day.at(push_time).do(run_push_papers)
            logger.info(f"📅 论文推送任务已设置: 每天 {', '.join(push_times)}")

    def _run_loop(self):
        """调度循环"""
        logger.info("⏰ 调度器已启动")
        while self.running:
            schedule.run_pending()
            time.sleep(30)
        logger.info("⏰ 调度器已停止")

    def start(self):
        """启动调度器"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        logger.info("✅ 后台调度器已启动")

    def stop(self):
        """停止调度器"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹️ 后台调度器已停止")

    def reload(self):
        """重新加载配置"""
        self._setup_jobs()
        logger.info("🔄 调度器配置已重新加载")

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
    title="ArXiv论文推送系统",
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

    # 从数据库加载研究方向（如果有）
    runtime = cast(dict[str, object], load_runtime_config() or {})
    research_description = str(
        runtime.get("research_description", RESEARCH_DESCRIPTION)
    )

    llm_raw = cast(dict[str, object], get_config("llm_filter") or {})
    notify_raw = cast(dict[str, object], get_config("notify") or {})
    llm_config = mask_sensitive_fields(llm_raw)
    notify_config = mask_sensitive_fields(notify_raw)

    return {
        "success": True,
        "data": {
            "arxiv": get_config("arxiv"),
            "llm_filter": llm_config,
            "schedule": get_config("schedule"),
            "notify": notify_config,
            "research_description": research_description,
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
                "message": "欢迎使用ArXiv论文推送系统 v3.0",
                "docs": "/docs",
                "api": "/api/health",
                "note": "请将前端构建文件放到 static/ 目录",
            }
        )


@app.get("/{path:path}")
async def serve_static(path: str):
    """服务其他静态文件"""
    # 先尝试直接找文件
    file_path = os.path.join(STATIC_DIR, path)
    if os.path.exists(file_path) and os.path.isfile(file_path):
        return FileResponse(file_path)

    # 对于SPA路由，返回index.html
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
║         ArXiv论文推送系统 v3.0 - 三合一版                ║
║                                                          ║
║  功能：后端API + 定时调度 + 前端页面服务                 ║
║  端口：20001                                             ║
║  文档：http://localhost:20001/docs                       ║
╚══════════════════════════════════════════════════════════╝
    """)

    uvicorn.run("app:app", host="0.0.0.0", port=20001, reload=False, log_level="info")
