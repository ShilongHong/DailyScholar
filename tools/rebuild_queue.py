"""
清空并重建 paper_queue 队列
从 papers_relevant 表中获取所有 Stars >= 60 的论文，重新加入队列
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mysql_service import get_mysql_connection


logger = logging.getLogger(__name__)


def rebuild_queue():
    """清空队列并从 papers_relevant 重新加载高分论文"""

    conn = get_mysql_connection()
    if not conn:
        logger.error("数据库连接失败")
        return False

    try:
        with conn.cursor() as cursor:
            # 1. 检查当前队列中的论文数量
            cursor.execute("SELECT COUNT(*) as count FROM paper_queue")
            current_count = (cursor.fetchone() or {"count": 0})["count"]

            print(f"当前队列中有 {current_count} 篇论文")

            # 2. 检查 papers_relevant 中符合条件的论文数量
            cursor.execute(
                "SELECT COUNT(*) as count FROM papers_relevant WHERE Stars >= 60"
            )
            target_count = (cursor.fetchone() or {"count": 0})["count"]

            print(f"papers_relevant 表中有 {target_count} 篇评分 >= 60 的论文")

            # 3. 用户确认
            if current_count > 0:
                confirm = input(
                    f"\n确认要清空队列并重建吗？这将删除 {current_count} 篇论文，然后添加 {target_count} 篇新论文。(yes/no): "
                )
                if confirm.lower() not in ["yes", "y"]:
                    print("操作已取消")
                    return False

            # 4. 清空 paper_queue 表
            print("\n正在清空队列...")
            cursor.execute("DELETE FROM paper_queue")
            deleted_count = cursor.rowcount
            print(f"已删除 {deleted_count} 篇论文")

            # 5. 从 papers_relevant 中获取高分论文并插入队列
            print(f"\n正在从 papers_relevant 中获取评分 >= 60 的论文...")
            select_sql = """
                SELECT DOI, Title, TitleCN, Author, Affiliation, PublicationYear,
                       Abstract, AbstractCN, Link, PDFLink, Source, SubjectTerms,
                       Stars, RelevanceReason, PotentialHelp
                FROM papers_relevant
                WHERE Stars >= 60
                ORDER BY Stars DESC, created_at DESC
            """
            cursor.execute(select_sql)
            papers = cursor.fetchall()

            # 6. 批量插入队列
            print(f"正在插入 {len(papers)} 篇论文到队列...")
            insert_sql = """
                INSERT INTO paper_queue 
                (DOI, Title, TitleCN, Author, Affiliation, PublicationYear, 
                 Abstract, AbstractCN, Link, PDFLink, Source, SubjectTerms, 
                 Stars, RelevanceReason, PotentialHelp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            added_count = 0
            failed_count = 0
            for paper in papers:
                try:
                    cursor.execute(
                        insert_sql,
                        (
                            paper["DOI"],
                            paper["Title"],
                            paper.get("TitleCN", ""),
                            paper.get("Author", ""),
                            paper.get("Affiliation", ""),
                            paper.get("PublicationYear", ""),
                            paper.get("Abstract", ""),
                            paper.get("AbstractCN", ""),
                            paper.get("Link", ""),
                            paper.get("PDFLink", ""),
                            paper.get("Source", ""),
                            paper.get("SubjectTerms", ""),
                            paper.get("Stars", 0),
                            paper.get("RelevanceReason", ""),
                            paper.get("PotentialHelp", ""),
                        ),
                    )
                    added_count += 1
                    if added_count % 100 == 0:
                        print(f"已添加 {added_count}/{len(papers)} 篇论文...")
                except Exception as e:
                    failed_count += 1
                    logger.error(
                        f"插入论文失败 {paper.get('DOI', 'Unknown')}: {str(e)}"
                    )

            # 7. 提交事务
            conn.commit()

            print(f"\n✅ 队列重建完成！")
            print(f"   - 成功添加: {added_count} 篇")
            print(f"   - 失败: {failed_count} 篇")

            # 8. 验证结果
            cursor.execute("SELECT COUNT(*) as count FROM paper_queue")
            final_count = (cursor.fetchone() or {"count": 0})["count"]

            print(f"   - 当前队列总数: {final_count} 篇")

            # 显示评分分布
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN Stars >= 90 THEN '90-100'
                        WHEN Stars >= 80 THEN '80-89'
                        WHEN Stars >= 70 THEN '70-79'
                        WHEN Stars >= 60 THEN '60-69'
                        ELSE '0-59'
                    END as score_range,
                    COUNT(*) as count
                FROM paper_queue
                GROUP BY score_range
                ORDER BY MIN(Stars) DESC
            """)
            distribution = cursor.fetchall()
            print("\n评分分布:")
            for row in distribution:
                print(f"   {row['score_range']}: {row['count']} 篇")

            return True

    except Exception as e:
        logger.error(f"重建队列失败: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("重建推送队列")
    print("=" * 60)

    success = rebuild_queue()

    if success:
        print("\n操作成功完成！")
        sys.exit(0)
    else:
        print("\n操作失败，请查看日志")
        sys.exit(1)
