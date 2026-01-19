"""
将2025-2026年创建的论文重置为未处理状态
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from services.mysql_service import get_mysql_connection, execute_update
from config import ARXIV_CONFIG
import logging

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def reset_papers_to_unprocessed(years=[2025, 2026]):
    """将指定年份创建的论文设置为未处理"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table_raw = mysql_config.get("table_raw", "papers_raw")
    table_relevant = mysql_config.get("table_relevant", "papers_relevant")

    year_filter = " OR ".join([f"YEAR(created_at) = {year}" for year in years])
    years_str = ", ".join(map(str, years))

    conn = get_mysql_connection()
    if not conn:
        logger.error("无法连接到数据库")
        return

    try:
        # 1. 重置 papers_raw 表中指定年份的论文为未处理
        logger.info(f"正在重置 {table_raw} 表中 {years_str} 年的论文...")
        sql_raw = f"""
            UPDATE `{table_raw}`
            SET processed = FALSE
            WHERE {year_filter}
        """
        count_raw = execute_update(sql_raw)
        logger.info(f"✅ {table_raw}: 已将 {count_raw} 篇论文设置为未处理")

        # 2. 可选：删除 papers_relevant 表中指定年份的论文（如果要重新评分）
        logger.info(
            f"\n是否要删除 {table_relevant} 表中 {years_str} 年的论文以重新评分？"
        )
        response = input("输入 'yes' 确认删除，或按回车跳过: ").strip().lower()

        if response == "yes":
            sql_relevant = f"""
                DELETE FROM `{table_relevant}`
                WHERE {year_filter}
            """
            count_relevant = execute_update(sql_relevant)
            logger.info(f"✅ {table_relevant}: 已删除 {count_relevant} 篇论文")
        else:
            logger.info(f"⏭️  跳过删除 {table_relevant} 表中的数据")

        logger.info("\n✅ 操作完成！")
        logger.info("现在可以运行系统重新处理这些论文了")

    except Exception as e:
        logger.error(f"❌ 操作失败: {str(e)}")
        raise


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("将2025-2026年创建的论文重置为未处理状态")
    logger.info("=" * 60)

    reset_papers_to_unprocessed()
