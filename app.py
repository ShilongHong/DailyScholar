"""
ArXiv论文推送系统 v3.0 - 三合一版
后端API + 定时调度 + 静态页面服务
"""

import os
import sys
import logging
from collections.abc import Callable
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Annotated, cast

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


import uvicorn

# 确保服务模块可以导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    OPENCLAW_CONFIG,
    LOGGING_CONFIG,
    RESEARCH_DESCRIPTION,
)
from core.runtime_config import get_config, load_runtime_config, save_runtime_config
from core.scheduler import PaperScheduler
from services.paper_queue_service import PaperQueueService
from services import storage_service
from services.translation_service import TranslationService


# ============================================================
# 日志配置
# ============================================================
def setup_logging():
    """配置日志"""
    os.makedirs("logs", exist_ok=True)

    log_level_name = str(LOGGING_CONFIG.get("level", "INFO"))
    log_format = str(
        LOGGING_CONFIG.get(
            "format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
    )

    log_filename = f"logs/app_{datetime.now().strftime('%Y%m%d')}.log"

    log_level = cast(int | str, getattr(logging, log_level_name))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_filename, encoding="utf-8"),
        ],
    )

    return logging.getLogger(__name__)


logger = setup_logging()


PaperRecord = dict[str, object]
PaperQueryResult = dict[str, object]
ConfigMap = dict[str, object]
PaperFetcher = Callable[..., PaperQueryResult]


def run_fetch_job():
    from core.workflows import run_fetch_papers

    return run_fetch_papers(logger=logger)


def run_delivery_job():
    from core.workflows import run_delivery

    return run_delivery(logger=logger)


def run_process_job():
    from core.workflows import process_unprocessed_papers

    return process_unprocessed_papers(logger=logger)


scheduler = PaperScheduler(
    fetch_job=run_fetch_job,
    delivery_job=run_delivery_job,
    get_config_func=get_config,
    logger=logger,
)


# ============================================================
# FastAPI 应用
# ============================================================
@asynccontextmanager
async def lifespan(_app: FastAPI):
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
@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "time": datetime.now().isoformat(), "version": "3.0.0"}


PAPER_FILTER_CONFIG_NAME = "paper_list_filters"


class PaperFilterConfirmRequest(BaseModel):
    show_pushed: bool = True

    comment_filter: str = "all"
    min_stars: int = 0
    only_marked: bool = False
    date_start: str | None = None
    date_end: str | None = None
    search: str | None = None


# --- 论文接口 ---
@app.get("/api/papers")
async def get_papers(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    show_pushed: Annotated[bool, Query()] = True,
    comment_filter: Annotated[str, Query()] = "all",
    min_stars: Annotated[int, Query()] = 0,
    only_marked: Annotated[bool, Query()] = False,
    date_start: str | None = None,
    date_end: str | None = None,
    date: str | None = None,
    search: str | None = None,
    use_confirmed_filters: Annotated[bool, Query()] = False,
):
    """获取论文列表"""
    try:
        if date:
            papers = storage_service.get_relevant_papers_by_date(date)
            return {
                "success": True,
                "data": papers,
                "total": len(papers),
                "count": len(papers),
            }

        if use_confirmed_filters:
            confirmed_filters = cast(
                ConfigMap,
                storage_service.load_config_from_db(PAPER_FILTER_CONFIG_NAME) or {},
            )
            if confirmed_filters:
                show_pushed = bool(confirmed_filters.get("show_pushed", show_pushed))
                comment_filter = str(
                    confirmed_filters.get("comment_filter", comment_filter)
                )
                min_stars = int(
                    cast(int, confirmed_filters.get("min_stars", min_stars))
                )
                only_marked = bool(confirmed_filters.get("only_marked", only_marked))
                date_start = cast(
                    str | None, confirmed_filters.get("date_start", date_start)
                )
                date_end = cast(str | None, confirmed_filters.get("date_end", date_end))
                search = cast(str | None, confirmed_filters.get("search", search))
                logger.info("已应用确认的论文筛选条件")
            else:
                logger.info("未找到已确认筛选条件，继续使用请求参数")

        fetch_papers = cast(PaperFetcher, storage_service.get_all_relevant_papers)
        result = fetch_papers(
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
        papers = cast(list[PaperRecord], result["papers"])
        total = int(cast(int | str, result["total"]))
        return {
            "success": True,
            "data": papers,
            "total": total,
            "count": len(papers),
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
        success = storage_service.save_config_to_db(
            PAPER_FILTER_CONFIG_NAME, filter_payload
        )
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
        confirmed_filters = cast(
            ConfigMap,
            storage_service.load_config_from_db(PAPER_FILTER_CONFIG_NAME) or {},
        )
        return {"success": True, "data": confirmed_filters}
    except Exception as e:
        logger.error(f"获取已确认筛选条件失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/papers/stats")
async def get_papers_stats():
    """获取论文统计"""
    try:
        stats = storage_service.get_paper_stats()
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
        success = storage_service.update_paper_mark(request.doi, request.marked)
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
        success = storage_service.update_paper_comment(request.doi, request.comment)
        return {"success": success, "comment": request.comment}
    except Exception as e:
        logger.error(f"更新评论失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/papers/{doi}")
async def delete_paper_endpoint(doi: str):
    """删除论文"""
    try:
        success = storage_service.delete_paper(doi)
        return {"success": success}
    except Exception as e:
        logger.error(f"删除论文失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/papers/{doi}/retranslate")
async def retranslate_paper_endpoint(doi: str):
    """重新翻译论文"""
    try:
        from config import ARXIV_CONFIG

        mysql_config = cast(ConfigMap, ARXIV_CONFIG.get("mysql", {}))
        table = str(mysql_config.get("table_relevant", "papers_relevant"))

        # 获取论文信息
        sql = f"SELECT * FROM `{table}` WHERE DOI = %s"
        papers = cast(list[PaperRecord], storage_service.execute_query(sql, (doi,)))

        if not papers:
            raise HTTPException(status_code=404, detail="论文不存在")

        paper = papers[0]

        # 重新翻译 - 使用运行时配置
        llm_config = get_config("llm_filter", logger=logger)
        translation_service = TranslationService(config=llm_config)
        translated_paper = translation_service.translate_paper(paper)

        # 更新数据库
        update_sql = (
            f"UPDATE `{table}` SET TitleCN = %s, AbstractCN = %s WHERE DOI = %s"
        )
        _ = storage_service.execute_update(
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
@app.get("/api/config/all")
async def get_all_config():
    """获取所有配置"""
    # 从数据库加载研究方向（如果有）
    runtime = load_runtime_config(logger=logger)
    research_value = runtime.get("research_description", RESEARCH_DESCRIPTION)
    research_description = str(research_value)

    return {
        "success": True,
        "data": {
            "arxiv": get_config("arxiv", logger=logger),
            "llm_filter": get_config("llm_filter", logger=logger),
            "schedule": get_config("schedule", logger=logger),
            "research_description": research_description,
            "openclaw": {
                "enabled": OPENCLAW_CONFIG.get("enabled", True),
                "delivery_mode": OPENCLAW_CONFIG.get("delivery_mode", "cli-session"),
                "session_key": OPENCLAW_CONFIG.get("session_key", "main"),
                "binary_path": OPENCLAW_CONFIG.get("binary_path", "openclaw"),
            },
        },
    }


class ConfigUpdate(BaseModel):
    config: dict[str, object]


@app.put("/api/config/{name}")
async def update_config(name: str, update: ConfigUpdate):
    """更新配置"""
    try:
        runtime = load_runtime_config(logger=logger)

        # 特殊处理研究方向（字符串而非字典）
        if name == "research_description":
            runtime["research_description"] = update.config.get("content", "")
        else:
            runtime[name] = update.config

        save_runtime_config(runtime, logger=logger)

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
        background_tasks.add_task(run_fetch_job)
        return {"success": True, "message": "论文获取任务已在后台启动，请稍后查看结果"}
    except Exception as e:
        logger.error(f"启动论文获取任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/actions/deliver-now")
async def deliver_now(background_tasks: BackgroundTasks):
    try:
        background_tasks.add_task(run_delivery_job)
        return {"success": True, "message": "论文投递任务已在后台启动"}
    except Exception as e:
        logger.error(f"启动论文投递任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/actions/push-now")
async def push_now(background_tasks: BackgroundTasks):
    return await deliver_now(background_tasks)


@app.post("/api/actions/process-now")
async def process_now(background_tasks: BackgroundTasks):
    """立即处理未解析的论文"""
    try:
        background_tasks.add_task(run_process_job)
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
            empty_files: list[str] = []
            return {"success": True, "data": empty_files}

        files: list[str] = [f for f in os.listdir(log_dir) if f.endswith(".log")]
        files.sort(reverse=True)  # 最新的在前面
        return {"success": True, "data": files}
    except Exception as e:
        logger.error(f"获取日志列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/logs/content")
async def get_log_content(filename: str | None = None, lines: int = 100):
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

        file_path = os.path.join(log_dir, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Log file not found")

        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.readlines()

        # 返回最后N行
        return {
            "success": True,
            "data": "".join(content[-lines:]),
            "filename": filename,
        }
    except Exception as e:
        logger.error(f"获取日志内容失败: {e}")
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
