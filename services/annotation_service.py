"""论文标注服务"""

import json
import logging
from services.mysql_service import execute_query, execute_update

logger = logging.getLogger(__name__)


def get_annotations(doi: str) -> list:
    """获取论文的所有标注"""
    rows = execute_query(
        "SELECT id, page, type, position, content, color, created_at, updated_at "
        "FROM paper_annotations WHERE doi = %s ORDER BY page, created_at",
        (doi,)
    )

    for row in rows:
        if isinstance(row.get("position"), str):
            row["position"] = json.loads(row["position"])

    return rows


def save_annotations(doi: str, annotations: list) -> dict:
    """保存标注（全量替换）"""
    try:
        # 删除旧标注
        execute_update("DELETE FROM paper_annotations WHERE doi = %s", (doi,))

        # 插入新标注
        for ann in annotations:
            position = ann.get("position", {})
            if isinstance(position, dict):
                position = json.dumps(position)

            execute_update(
                "INSERT INTO paper_annotations (doi, page, type, position, content, color) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (doi, ann.get("page"), ann.get("type"), position,
                 ann.get("content"), ann.get("color", "#FFFF00"))
            )

        logger.info(f"✅ 保存标注成功: {doi}, {len(annotations)} 条")
        return {"success": True, "count": len(annotations)}

    except Exception as e:
        logger.error(f"❌ 保存标注失败: {e}")
        raise
