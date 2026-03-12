from collections.abc import Sequence
from typing import cast

from config import ARXIV_CONFIG
from core.config_loader import load_settings
from storage.base import PaperQueryResult, PaperRecord, PaperStore
from storage.factory import create_store
from services import mysql_service as mysql_backend


SqlParams = Sequence[object] | None


def _get_database_engine() -> str:
    database_config = cast(dict[str, object], ARXIV_CONFIG.get("database", {}))
    return str(database_config.get("engine", "sqlite"))


def _get_store() -> PaperStore:
    settings = load_settings()
    return create_store(cast(dict, settings))


def get_mysql_connection():
    return mysql_backend.get_mysql_connection()


def close_mysql_connection():
    return mysql_backend.close_mysql_connection()


def execute_query(sql: str, params: SqlParams = None):
    if params is None:
        return mysql_backend.execute_query(sql)
    return mysql_backend.execute_query(sql, tuple(params))


def execute_update(sql: str, params: SqlParams = None) -> int:
    if params is None:
        return mysql_backend.execute_update(sql)
    return mysql_backend.execute_update(sql, tuple(params))


def save_raw_papers_to_mysql(papers: list[PaperRecord]) -> int:
    return _get_store().save_raw_papers(papers)


def save_relevant_papers_to_mysql(papers: list[PaperRecord]) -> int:
    return _get_store().save_relevant_papers(papers)


def get_all_relevant_papers(
    *, limit: int = 50, offset: int = 0, **kwargs
) -> PaperQueryResult:
    store = _get_store()
    if _get_database_engine() == "mysql":
        return mysql_backend.get_all_relevant_papers(
            limit=limit, offset=offset, **kwargs
        )
    return store.get_all_relevant_papers(limit, offset)


def get_relevant_papers_by_date(publication_date: str) -> list[PaperRecord]:
    return _get_store().get_relevant_papers_by_date(publication_date)


def get_paper_stats() -> dict[str, int]:
    return _get_store().get_paper_stats()


def is_mysql_enabled() -> bool:
    return _get_database_engine() == "mysql"


def is_paper_processed(doi: str, table: str = "papers_raw") -> bool:
    if _get_database_engine() == "mysql":
        return mysql_backend.is_paper_processed(doi, table=table)
    return _get_store().is_paper_processed(doi)


def update_paper_mark(doi: str, is_marked: bool) -> bool:
    return _get_store().update_paper_mark(doi, is_marked)


def update_paper_comment(doi: str, comment: str) -> bool:
    return _get_store().update_paper_comment(doi, comment)


def delete_paper(doi: str) -> bool:
    return _get_store().delete_paper(doi)


def get_unprocessed_raw_papers(limit: int = 50) -> list[PaperRecord]:
    return _get_store().get_unprocessed_raw_papers(limit)


def mark_papers_as_processed(dois: list[str]) -> int:
    return _get_store().mark_papers_as_processed(dois)


def load_config_from_db(config_name: str) -> object | None:
    return _get_store().load_config(config_name)


def save_config_to_db(config_name: str, config_value: object) -> bool:
    return _get_store().save_config(config_name, config_value)


def get_all_configs_from_db() -> dict[str, object]:
    return _get_store().get_all_configs()


def enqueue_papers_to_db(papers: list[PaperRecord]) -> int:
    return _get_store().enqueue_papers(papers)


def dequeue_papers_from_db(max_count: int) -> list[PaperRecord]:
    return _get_store().dequeue_papers(max_count)


def get_queue_size_from_db() -> int:
    return _get_store().get_queue_size()


def get_queue_preview_from_db(max_count: int = 10) -> list[PaperRecord]:
    return _get_store().get_queue_preview(max_count)


def clear_queue_in_db() -> None:
    _get_store().clear_queue()


def get_unpushed_papers(limit: int = 20) -> list[PaperRecord]:
    return _get_store().get_unpushed_papers(limit)


def mark_papers_as_pushed(dois: list[str]) -> int:
    return _get_store().mark_papers_as_pushed(dois)
