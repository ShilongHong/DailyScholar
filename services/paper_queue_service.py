"""
论文队列管理服务
"""

import logging
from typing import List, Dict, Any

# 导入数据库队列函数
from .mysql_service import (
    enqueue_papers_to_db,
    dequeue_papers_from_db,
    get_queue_size_from_db,
    get_queue_preview_from_db,
    clear_queue_in_db,
)

logger = logging.getLogger(__name__)


class PaperQueueService:
    """论文队列管理服务类（使用数据库存储）"""

    def __init__(self, queue_file: str = "output/paper_queue.json"):
        # 保留参数以保持兼容性，但实际使用数据库
        pass

    def enqueue_papers(self, papers: List[Dict[str, Any]]) -> int:
        """将新论文加入队列"""
        return enqueue_papers_to_db(papers)

    def dequeue_papers(self, max_count: int) -> List[Dict[str, Any]]:
        """从队列中取出论文（策略：>80分全推，否则凑齐max_count，优先当天）"""
        return dequeue_papers_from_db(max_count)

    def get_queue_size(self) -> int:
        """获取队列中的论文数量"""
        return get_queue_size_from_db()

    def clear_queue(self):
        """清空队列"""
        clear_queue_in_db()
        logger.info("✅ 论文队列已清空")

    def get_queue_preview(self, max_count: int = 10) -> List[Dict[str, Any]]:
        """获取队列中的论文预览"""
        return get_queue_preview_from_db(max_count)
