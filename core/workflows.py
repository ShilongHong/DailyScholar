import logging
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import cast

from delivery.openclaw_notifier import OpenClawNotifier
from services import (
    ArxivService,
    LLMFilterService,
    PaperQueueService,
    TranslationService,
    get_unprocessed_raw_papers,
    get_unpushed_papers,
    mark_papers_as_processed,
    mark_papers_as_pushed,
    save_relevant_papers_to_mysql,
)

from core.runtime_config import get_config


PaperRecord = dict[str, object]
WorkflowResult = dict[str, object]
ConfigMap = dict[str, object]
SearchPapersCallable = Callable[[], list[PaperRecord]]


def _get_logger(logger: logging.Logger | None = None) -> logging.Logger:
    return logger or logging.getLogger("app")


def _to_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def _to_str(value: object, default: str) -> str:
    if isinstance(value, str):
        return value
    return default


def run_fetch_papers(logger: logging.Logger | None = None) -> WorkflowResult:
    active_logger = _get_logger(logger)

    active_logger.info("=" * 60)
    active_logger.info("开始执行论文获取任务")
    active_logger.info("=" * 60)

    try:
        arxiv_config = get_config("arxiv", logger=active_logger)
        llm_config = get_config("llm_filter", logger=active_logger)

        arxiv_service = ArxivService(config=arxiv_config)
        llm_service = None
        translation_service = None
        min_stars = _to_int(llm_config.get("min_stars", 3), 3)

        if llm_config.get("enable", True):
            llm_service = LLMFilterService(config=llm_config)
            translation_service = TranslationService(config=llm_config)

        queue_service = PaperQueueService()
        processed_count = 0
        processing_lock = threading.Lock()
        stop_processing = threading.Event()
        executor = ThreadPoolExecutor(max_workers=1)

        def _background_processor() -> None:
            nonlocal processed_count

            active_logger.info("🔄 后台处理线程已启动，持续从数据库读取未处理论文...")
            batch_size = 50

            while not stop_processing.is_set():
                unprocessed = get_unprocessed_raw_papers(limit=batch_size)
                if not unprocessed:
                    if stop_processing.is_set():
                        break
                    active_logger.info("数据库中暂无未处理论文，等待5秒...")
                    _ = stop_processing.wait(5)
                    continue

                active_logger.info(
                    f"📝 发现 {len(unprocessed)} 篇未处理论文，开始处理..."
                )

                try:
                    failed_papers = []
                    if llm_service:
                        filtered, failed_papers = llm_service.filter_papers(unprocessed)
                        qualified = [
                            paper
                            for paper in filtered
                            if paper.get("Stars", 0) >= min_stars
                        ]
                    else:
                        filtered = unprocessed
                        qualified = unprocessed

                    if qualified:
                        for index, paper in enumerate(qualified, start=1):
                            if stop_processing.is_set():
                                break
                            try:
                                active_logger.info(
                                    f"  [后台 {index}/{len(qualified)}] 翻译: {str(paper.get('Title', ''))[:50]}..."
                                )
                                translated = (
                                    cast(
                                        PaperRecord,
                                        translation_service.translate_paper(paper),
                                    )
                                    if translation_service
                                    else paper
                                )
                                _ = save_relevant_papers_to_mysql([translated])
                                translated["ID"] = translated.get("DOI", "")
                                _ = queue_service.enqueue_papers([translated])

                                with processing_lock:
                                    processed_count += 1

                                active_logger.info(
                                    f"  [后台 {index}/{len(qualified)}] 已保存 (总计 {processed_count} 篇)"
                                )
                            except Exception as exc:
                                active_logger.error(f"  [后台处理] 失败: {exc}")

                    successfully_processed = [
                        paper.get("DOI")
                        for paper in (filtered if llm_service else unprocessed)
                        if paper.get("DOI")
                    ]
                    if successfully_processed:
                        _ = mark_papers_as_processed(
                            [str(doi) for doi in successfully_processed]
                        )
                        active_logger.info(
                            f"✅ 已标记 {len(successfully_processed)} 篇为已处理"
                        )

                    if failed_papers:
                        active_logger.warning(
                            f"⚠️ {len(failed_papers)} 篇评估失败，保持未处理状态，等待重新评估"
                        )
                except Exception as exc:
                    active_logger.error(f"后台处理批次出错: {exc}")
                    _ = stop_processing.wait(2)

            active_logger.info("🛑 后台处理线程已停止")

        _ = executor.submit(_background_processor)

        active_logger.info("🚀 开始获取新论文...")
        search_papers = cast(SearchPapersCallable, arxiv_service.search_papers)
        all_papers = search_papers()

        if all_papers:
            active_logger.info(f"✅ 共获取 {len(all_papers)} 篇新论文，已保存到数据库")
        else:
            active_logger.info("没有找到新论文")

        active_logger.info("等待后台处理线程处理完所有论文...")
        max_wait = 300
        wait_count = 0
        while wait_count < max_wait:
            unprocessed = get_unprocessed_raw_papers(limit=1)
            if not unprocessed:
                active_logger.info("✅ 所有论文已处理完成")
                break
            time.sleep(1)
            wait_count += 1
            if wait_count % 10 == 0:
                active_logger.info(f"  仍有未处理论文，已等待 {wait_count} 秒...")

        stop_processing.set()
        executor.shutdown(wait=True)

        return {
            "status": "success",
            "message": f"获取了 {len(all_papers) if all_papers else 0} 篇新论文，共处理了 {processed_count} 篇合格论文",
            "count": processed_count,
        }
    except Exception as exc:
        active_logger.error(f"论文获取任务失败: {exc}")
        import traceback

        traceback.print_exc()
        return {"status": "error", "message": str(exc), "count": 0}


def run_delivery(logger: logging.Logger | None = None) -> WorkflowResult:
    active_logger = _get_logger(logger)

    active_logger.info("=" * 60)
    active_logger.info("开始执行论文投递任务")
    active_logger.info("=" * 60)

    try:
        push_config = cast(
            ConfigMap,
            get_config("schedule", logger=active_logger).get("push_papers", {}),
        )
        max_papers = _to_int(push_config.get("max_papers_per_push", 5), 5)

        unpushed = get_unpushed_papers(limit=100)
        if unpushed:
            active_logger.info(f"发现 {len(unpushed)} 篇未投递的论文，加入投递队列")
            _ = PaperQueueService().enqueue_papers(unpushed)

        queue_service = PaperQueueService()
        papers = queue_service.dequeue_papers(max_papers)
        if not papers:
            active_logger.info("队列中没有待投递的论文")
            return {"status": "success", "message": "队列为空", "count": 0}

        delivery_config = get_config("openclaw", logger=active_logger)
        notifier = OpenClawNotifier(
            binary_path=_to_str(
                delivery_config.get("binary_path", "openclaw"), "openclaw"
            ),
            session_key=_to_str(delivery_config.get("session_key", "main"), "main"),
            timeout_seconds=_to_int(delivery_config.get("timeout_seconds", 120), 120),
        )
        success = notifier.send_papers(papers)

        if success:
            dois = [paper.get("DOI") for paper in papers if paper.get("DOI")]
            if dois:
                _ = mark_papers_as_pushed([str(doi) for doi in dois])

            active_logger.info(f"成功投递 {len(papers)} 篇论文")
            return {
                "status": "success",
                "message": f"投递了 {len(papers)} 篇论文",
                "count": len(papers),
            }

        active_logger.warning("部分论文投递失败")
        return {
            "status": "partial",
            "message": "部分论文投递失败",
            "count": len(papers),
        }
    except Exception as exc:
        active_logger.error(f"论文投递任务失败: {exc}")
        return {"status": "error", "message": str(exc), "count": 0}


def process_unprocessed_papers(logger: logging.Logger | None = None) -> None:
    active_logger = _get_logger(logger)

    active_logger.info("=" * 60)
    active_logger.info("开始处理未解析的论文")
    active_logger.info("=" * 60)

    try:
        process_config = cast(
            ConfigMap,
            get_config("schedule", logger=active_logger).get("process_papers", {}),
        )
        batch_size = _to_int(process_config.get("batch_size", 100), 100)

        unprocessed = get_unprocessed_raw_papers(limit=batch_size)
        total = len(unprocessed)
        if total == 0:
            active_logger.info("没有未处理的论文")
            return

        active_logger.info(f"找到 {total} 篇未处理的论文（配置限制：{batch_size}篇）")

        llm_config = get_config("llm_filter", logger=active_logger)
        min_stars = _to_int(llm_config.get("min_stars", 3), 3)
        llm_service = (
            LLMFilterService(config=llm_config)
            if llm_config.get("enable", True)
            else None
        )
        translation_service = TranslationService(config=llm_config)
        queue_service = PaperQueueService()

        processed_count = 0
        relevant_count = 0
        failed_papers = []

        if llm_service:
            active_logger.info(f"开始LLM筛选 {total} 篇论文...")
            filtered, failed_papers = llm_service.filter_papers(unprocessed)
            qualified = [
                paper for paper in filtered if paper.get("Stars", 0) >= min_stars
            ]
        else:
            filtered = unprocessed
            qualified = unprocessed

        active_logger.info(
            f"筛选完成: {len(qualified)}/{total} 篇论文达到 {min_stars}星及以上"
        )

        if qualified:
            for index, paper in enumerate(qualified, start=1):
                try:
                    active_logger.info(
                        f"  [{index}/{len(qualified)}] 翻译: {str(paper.get('Title', ''))[:50]}..."
                    )
                    translated = cast(
                        PaperRecord, translation_service.translate_paper(paper)
                    )
                    _ = save_relevant_papers_to_mysql([translated])
                    translated["ID"] = translated.get("DOI", "")
                    _ = queue_service.enqueue_papers([translated])
                    relevant_count += 1
                    active_logger.info(
                        f"  [{index}/{len(qualified)}] 已保存 (总计 {relevant_count} 篇)"
                    )
                except Exception as exc:
                    active_logger.error(f"  [{index}/{len(qualified)}] 处理失败: {exc}")

        successfully_processed = [
            paper.get("DOI")
            for paper in (filtered if llm_service else unprocessed)
            if paper.get("DOI")
        ]
        if successfully_processed:
            _ = mark_papers_as_processed([str(doi) for doi in successfully_processed])
            processed_count = len(successfully_processed)

        if failed_papers:
            active_logger.warning(
                f"⚠️ {len(failed_papers)} 篇评估失败，保持未处理状态，等待重新评估"
            )

        active_logger.info("=" * 60)
        active_logger.info(
            f"处理完成: 共处理 {processed_count} 篇，相关 {relevant_count} 篇"
        )
        active_logger.info("=" * 60)
    except Exception as exc:
        active_logger.error(f"处理未解析论文失败: {exc}")
        import traceback

        active_logger.error(traceback.format_exc())
