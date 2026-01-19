"""
服务模块初始化
"""
# 导入所有服务类
from .arxiv_service import ArxivService
from .llm_filter_service import LLMFilterService
from .translation_service import TranslationService
from .dingtalk_service import DingTalkService
from .dingtalk_http_service import DingTalkHTTPService  # HTTP版本（推荐）
from .paper_queue_service import PaperQueueService
from .mysql_service import (
    get_mysql_connection,
    close_mysql_connection,
    save_raw_papers_to_mysql,
    save_relevant_papers_to_mysql,
    execute_query,
    execute_update,
    get_all_relevant_papers,
    get_relevant_papers_by_date,
    get_paper_stats,
    is_paper_processed,
    is_mysql_enabled,
    update_paper_mark,
    update_paper_comment,
    delete_paper,
    get_unprocessed_raw_papers,
    mark_papers_as_processed,
    load_config_from_db,
    save_config_to_db,
    get_all_configs_from_db,
    enqueue_papers_to_db,
    dequeue_papers_from_db,
    get_queue_size_from_db,
    get_queue_preview_from_db,
    clear_queue_in_db,
    get_unpushed_papers,
    mark_papers_as_pushed
)

__all__ = [
    'ArxivService',
    'LLMFilterService', 
    'TranslationService',
    'DingTalkService',
    'DingTalkHTTPService',  # HTTP版本（推荐）
    'PaperQueueService',
    'get_mysql_connection',
    'close_mysql_connection',
    'save_raw_papers_to_mysql',
    'save_relevant_papers_to_mysql',
    'execute_query',
    'execute_update',
    'get_all_relevant_papers',
    'get_relevant_papers_by_date',
    'get_paper_stats',
    'is_paper_processed',
    'is_mysql_enabled',
    'update_paper_mark',
    'update_paper_comment',
    'delete_paper',
    'get_unprocessed_raw_papers',
    'mark_papers_as_processed',
    'load_config_from_db',
    'save_config_to_db',
    'get_all_configs_from_db',
    'enqueue_papers_to_db',
    'dequeue_papers_from_db',
    'get_queue_size_from_db',
    'get_queue_preview_from_db',
    'clear_queue_in_db',
    'get_unpushed_papers',
    'mark_papers_as_pushed',
]
