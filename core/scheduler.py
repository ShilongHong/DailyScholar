import logging
import threading
import time
from schedule import Job
from typing import Callable, Protocol, cast

import schedule

from core.runtime_config import get_config


ConfigMap = dict[str, object]
JobCallable = Callable[[], object]
GetConfigCallable = Callable[[str], ConfigMap]


class DailyJobBuilder(Protocol):
    def at(self, time_str: str) -> "DailyJobRunner": ...


class DailyJobRunner(Protocol):
    def do(self, job_func: JobCallable) -> Job: ...


def _schedule_job(
    job_builder: DailyJobBuilder, run_at: str, callback: JobCallable
) -> None:
    _ = job_builder.at(run_at).do(callback)


class PaperScheduler:
    fetch_job: JobCallable
    delivery_job: JobCallable
    get_config_func: GetConfigCallable
    logger: logging.Logger
    running: bool

    def __init__(
        self,
        fetch_job: JobCallable,
        delivery_job: JobCallable,
        get_config_func: GetConfigCallable = get_config,
        logger: logging.Logger | None = None,
    ):
        self.fetch_job = fetch_job
        self.delivery_job = delivery_job
        self.get_config_func = get_config_func
        self.logger = logger or logging.getLogger("app")
        self.running = False
        self.thread: threading.Thread | None = None
        self._setup_jobs()

    def _setup_jobs(self) -> None:
        schedule.clear()
        config = self.get_config_func("schedule")

        fetch_config = cast(ConfigMap, config.get("fetch_papers", {}))
        if fetch_config.get("enable", True):
            fetch_time = str(fetch_config.get("time", "02:00"))
            _schedule_job(schedule.every().day, fetch_time, self.fetch_job)
            self.logger.info(f"📅 论文获取任务已设置: 每天 {fetch_time}")

        push_config = cast(ConfigMap, config.get("push_papers", {}))
        if push_config.get("enable", True):
            push_times = cast(list[str], push_config.get("times", ["09:00", "14:30"]))
            for push_time in push_times:
                _schedule_job(schedule.every().day, push_time, self.delivery_job)
            self.logger.info(f"📅 论文投递任务已设置: 每天 {', '.join(push_times)}")

    def _run_loop(self) -> None:
        self.logger.info("⏰ 调度器已启动")
        while self.running:
            schedule.run_pending()
            time.sleep(30)
        self.logger.info("⏰ 调度器已停止")

    def start(self) -> None:
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.logger.info("✅ 后台调度器已启动")

    def stop(self) -> None:
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        self.logger.info("⏹️ 后台调度器已停止")

    def reload(self) -> None:
        self._setup_jobs()
        self.logger.info("🔄 调度器配置已重新加载")

    def get_status(self) -> ConfigMap:
        jobs = [
            {
                "next_run": str(job.next_run) if job.next_run else None,
                "job": str(job),
            }
            for job in schedule.get_jobs()
        ]
        return {"running": self.running, "jobs": jobs, "job_count": len(jobs)}
