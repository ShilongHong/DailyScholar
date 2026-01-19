"""
修复 papers_relevant 和 papers_raw 表中的 created_at 字段
将 created_at 改为与 PublicationYear 一致
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mysql_service import get_mysql_connection


logger = logging.getLogger(__name__)


def fix_created_at():
    """将 papers_relevant 和 papers_raw 表的 created_at 改为 PublicationYear"""

    conn = get_mysql_connection()
    if not conn:
        logger.error("数据库连接失败")
        return False

    try:
        with conn.cursor() as cursor:
            # 1. 检查 papers_relevant 表
            print("=" * 80)
            print("papers_relevant 表统计:")
            print("=" * 80)
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(DISTINCT PublicationYear) as distinct_years
                FROM papers_relevant
                WHERE PublicationYear IS NOT NULL AND PublicationYear != ''
            """)
            stats = cursor.fetchone() or {"total": 0, "distinct_years": 0}
            print(f"  总论文数: {stats['total']}")
            print(f"  不同的 PublicationYear 值数: {stats['distinct_years']}")

            cursor.execute("""
                SELECT DOI, Title, PublicationYear, created_at
                FROM papers_relevant
                LIMIT 3
            """)
            samples = cursor.fetchall()
            print(f"\n示例数据（前3条）:")
            for sample in samples:
                print(f"  Title: {sample['Title'][:50]}")
                print(f"  PublicationYear: {sample['PublicationYear']}")
                print(f"  created_at: {sample['created_at']}")
                print()

            # 2. 检查 papers_raw 表
            print("=" * 80)
            print("papers_raw 表统计:")
            print("=" * 80)
            cursor.execute("""
                SELECT COUNT(*) as total,
                       COUNT(DISTINCT PublicationYear) as distinct_years
                FROM papers_raw
                WHERE PublicationYear IS NOT NULL AND PublicationYear != ''
            """)
            stats_raw = cursor.fetchone() or {"total": 0, "distinct_years": 0}
            print(f"  总论文数: {stats_raw['total']}")
            print(f"  不同的 PublicationYear 值数: {stats_raw['distinct_years']}")

            cursor.execute("""
                SELECT DOI, Title, PublicationYear, created_at
                FROM papers_raw
                LIMIT 3
            """)
            samples_raw = cursor.fetchall()
            print(f"\n示例数据（前3条）:")
            for sample in samples_raw:
                print(f"  Title: {sample['Title'][:50]}")
                print(f"  PublicationYear: {sample['PublicationYear']}")
                print(f"  created_at: {sample['created_at']}")
                print()

            # 3. 用户确认
            print("=" * 80)
            confirm = input(
                "\n确认要将两个表的 created_at 更新为 PublicationYear 吗？(yes/no): "
            )
            if confirm.lower() not in ["yes", "y"]:
                print("操作已取消")
                return False

            # 4. 更新 papers_relevant 表
            print("\n正在更新 papers_relevant 表...")
            update_sql = """
                UPDATE papers_relevant
                SET created_at = PublicationYear
                WHERE PublicationYear IS NOT NULL 
                  AND PublicationYear != ''
            """
            cursor.execute(update_sql)
            updated_relevant = cursor.rowcount
            print(f"✅ papers_relevant: 更新了 {updated_relevant} 条记录")

            # 5. 更新 papers_raw 表
            print("\n正在更新 papers_raw 表...")
            update_sql_raw = """
                UPDATE `papers_raw`
                SET created_at = PublicationYear
                WHERE PublicationYear IS NOT NULL 
                  AND PublicationYear != ''
            """
            cursor.execute(update_sql_raw)
            updated_raw = cursor.rowcount
            print(f"✅ papers_raw: 更新了 {updated_raw} 条记录")

            conn.commit()

            print(f"\n" + "=" * 80)
            print(f"✅ 更新完成！")
            print(f"   papers_relevant: {updated_relevant} 条")
            print(f"   papers_raw: {updated_raw} 条")
            print(f"   总计: {updated_relevant + updated_raw} 条")
            print("=" * 80)

            # 6. 验证结果
            print("\n验证更新结果...")
            cursor.execute("""
                SELECT DOI, Title, PublicationYear, created_at
                FROM papers_relevant
                LIMIT 3
            """)
            samples_after = cursor.fetchall()
            print(f"\npapers_relevant 更新后（前3条）:")
            for sample in samples_after:
                print(f"  Title: {sample['Title'][:50]}")
                print(f"  PublicationYear: {sample['PublicationYear']}")
                print(f"  created_at: {sample['created_at']}")
                match = (
                    "✅"
                    if str(sample["PublicationYear"]) == str(sample["created_at"])
                    else "❌"
                )
                print(f"  匹配: {match}")
                print()

            cursor.execute("""
                SELECT DOI, Title, PublicationYear, created_at
                FROM papers_raw
                LIMIT 3
            """)
            samples_raw_after = cursor.fetchall()
            print(f"papers_raw 更新后（前3条）:")
            for sample in samples_raw_after:
                print(f"  Title: {sample['Title'][:50]}")
                print(f"  PublicationYear: {sample['PublicationYear']}")
                print(f"  created_at: {sample['created_at']}")
                match = (
                    "✅"
                    if str(sample["PublicationYear"]) == str(sample["created_at"])
                    else "❌"
                )
                print(f"  匹配: {match}")
                print()

            return True

    except Exception as e:
        logger.error(f"更新失败: {str(e)}")
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    print("=" * 80)
    print("修复 papers_relevant 表的 created_at 字段")
    print("=" * 80)

    try:
        success = fix_created_at()
        if success:
            print("\n操作成功完成！")
            sys.exit(0)
        else:
            print("\n操作失败或已取消")
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n操作失败: {str(e)}")
        logging.error(f"修复 created_at 失败: {str(e)}", exc_info=True)
        sys.exit(1)
