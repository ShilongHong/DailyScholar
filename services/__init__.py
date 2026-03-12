"""
服务模块初始化
"""

from importlib import import_module


_EXPORTS = {
    "ArxivService": "arxiv_service",
    "LLMFilterService": "llm_filter_service",
    "TranslationService": "translation_service",
    "PaperQueueService": "paper_queue_service",
    "mysql_service": "mysql_service",
    "get_mysql_connection": "storage_service",
    "close_mysql_connection": "storage_service",
    "save_raw_papers_to_mysql": "storage_service",
    "save_relevant_papers_to_mysql": "storage_service",
    "execute_query": "storage_service",
    "execute_update": "storage_service",
    "get_all_relevant_papers": "storage_service",
    "get_relevant_papers_by_date": "storage_service",
    "get_paper_stats": "storage_service",
    "is_paper_processed": "storage_service",
    "is_mysql_enabled": "storage_service",
    "update_paper_mark": "storage_service",
    "update_paper_comment": "storage_service",
    "delete_paper": "storage_service",
    "get_unprocessed_raw_papers": "storage_service",
    "mark_papers_as_processed": "storage_service",
    "load_config_from_db": "storage_service",
    "save_config_to_db": "storage_service",
    "get_all_configs_from_db": "storage_service",
    "enqueue_papers_to_db": "storage_service",
    "dequeue_papers_from_db": "storage_service",
    "get_queue_size_from_db": "storage_service",
    "get_queue_preview_from_db": "storage_service",
    "clear_queue_in_db": "storage_service",
    "get_unpushed_papers": "storage_service",
    "mark_papers_as_pushed": "storage_service",
}


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if not module_name:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(f".{module_name}", __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(list(globals().keys()) + list(_EXPORTS.keys()))


__all__ = [
    "ArxivService",
    "LLMFilterService",
    "TranslationService",
    "PaperQueueService",
    "mysql_service",
    "get_mysql_connection",
    "close_mysql_connection",
    "save_raw_papers_to_mysql",
    "save_relevant_papers_to_mysql",
    "execute_query",
    "execute_update",
    "get_all_relevant_papers",
    "get_relevant_papers_by_date",
    "get_paper_stats",
    "is_paper_processed",
    "is_mysql_enabled",
    "update_paper_mark",
    "update_paper_comment",
    "delete_paper",
    "get_unprocessed_raw_papers",
    "mark_papers_as_processed",
    "load_config_from_db",
    "save_config_to_db",
    "get_all_configs_from_db",
    "enqueue_papers_to_db",
    "dequeue_papers_from_db",
    "get_queue_size_from_db",
    "get_queue_preview_from_db",
    "clear_queue_in_db",
    "get_unpushed_papers",
    "mark_papers_as_pushed",
]
