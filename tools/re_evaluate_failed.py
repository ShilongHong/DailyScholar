"""
重新评估失败的论文
对 papers_relevant 中 RelevanceReason 包含"评估失败"或"默认评分"的论文重新评估
"""

import os
import sys
import logging
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.mysql_service import get_mysql_connection, get_all_configs_from_db
from services.llm_filter_service import LLMFilterService


logger = logging.getLogger(__name__)

# 线程锁用于安全地更新统计数据
stats_lock = Lock()
print_lock = Lock()


def get_failed_papers() -> List[Dict[str, Any]]:
    """获取评估失败的论文列表"""
    conn = get_mysql_connection()
    if not conn:
        logger.error("数据库连接失败")
        return []

    try:
        with conn.cursor() as cursor:
            sql = """
                SELECT DOI, Title, TitleCN, Author, Affiliation, PublicationYear,
                       Abstract, AbstractCN, Link, PDFLink, Source, SubjectTerms,
                       Stars, RelevanceReason, PotentialHelp, is_marked, is_pushed
                FROM papers_relevant
                WHERE RelevanceReason LIKE '%评估失败%' 
                   OR RelevanceReason LIKE '%默认评分%'
                   OR RelevanceReason LIKE '%解析失败%'
                ORDER BY created_at DESC
            """
            cursor.execute(sql)
            return list(cursor.fetchall() or [])

    except Exception as e:
        logger.error(f"获取失败论文列表出错: {str(e)}")
        return []
    finally:
        conn.close()


def update_paper_evaluation(
    doi: str, stars: int, reason: str, potential_help: str
) -> bool:
    """更新论文评估结果"""
    conn = get_mysql_connection()
    if not conn:
        return False

    try:
        with conn.cursor() as cursor:
            sql = """
                UPDATE papers_relevant 
                SET Stars = %s, RelevanceReason = %s, PotentialHelp = %s
                WHERE DOI = %s
            """
            cursor.execute(sql, (stars, reason, potential_help, doi))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"更新论文评估失败 {doi}: {str(e)}")
        return False
    finally:
        conn.close()


def process_single_paper(
    paper: Dict[str, Any],
    llm_service: LLMFilterService,
    index: int,
    total: int,
    stats: Dict[str, int],
) -> Dict[str, Any]:
    """处理单篇论文的评估"""
    doi = paper.get("DOI", "")
    title = paper.get("Title", "")[:80]
    old_score = paper.get("Stars", 0)

    result_info = {
        "doi": doi,
        "title": title,
        "old_score": old_score,
        "status": "failed",
    }

    try:
        # 准备论文数据用于评估
        paper_for_eval = {
            "Title": paper.get("Title", ""),
            "Abstract": paper.get("Abstract", ""),
            "Author": paper.get("Author", ""),
            "SubjectTerms": paper.get("SubjectTerms", ""),
        }

        # 调用 LLM 评估
        result = llm_service.evaluate_paper(paper_for_eval)

        if result and result.get("score", 0) > 0:
            new_score = result["score"]
            new_reason = result.get("reason", "")
            new_help = result.get("potential_help", "")

            # 更新数据库
            if update_paper_evaluation(doi, new_score, new_reason, new_help):
                result_info["status"] = "success"
                result_info["new_score"] = new_score
                result_info["reason"] = new_reason
                result_info["change"] = new_score - old_score

                with stats_lock:
                    stats["success"] += 1
            else:
                result_info["status"] = "db_failed"
                with stats_lock:
                    stats["failed"] += 1
        else:
            result_info["status"] = "skipped"
            with stats_lock:
                stats["skipped"] += 1

    except Exception as e:
        result_info["status"] = "error"
        result_info["error"] = str(e)
        with stats_lock:
            stats["failed"] += 1

    # 打印进度
    with print_lock:
        with stats_lock:
            current = stats["success"] + stats["failed"] + stats["skipped"]

        print(f"[{current}/{total}] {title}")
        if result_info["status"] == "success":
            print(
                f"   ✅ {old_score} → {result_info['new_score']} (变化: {result_info['change']:+d})"
            )
        elif result_info["status"] == "skipped":
            print(f"   ⚠️  评估失败，保持 {old_score}")
        elif result_info["status"] == "db_failed":
            print(f"   ❌ 数据库更新失败")
        else:
            print(f"   ❌ {result_info.get('error', '未知错误')}")

    return result_info


def re_evaluate_papers():
    """重新评估失败的论文（使用16线程）"""

    # 获取失败的论文
    print("正在获取评估失败的论文...")
    papers = get_failed_papers()

    if not papers:
        print("没有找到需要重新评估的论文")
        return

    print(f"找到 {len(papers)} 篇需要重新评估的论文")

    # 用户确认
    confirm = input(f"\n确认要重新评估这 {len(papers)} 篇论文吗？(yes/no): ")
    if confirm.lower() not in ["yes", "y"]:
        print("操作已取消")
        return

    # 获取运行时配置
    print("\n正在加载LLM配置...")
    configs = get_all_configs_from_db()
    llm_config = configs.get("llm_filter", {})

    # 初始化 LLM 服务
    llm_service = LLMFilterService(config=llm_config)

    # 统计
    stats = {"success": 0, "failed": 0, "skipped": 0}

    print(f"\n开始重新评估（使用 16 线程）...")
    print("=" * 80)

    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=16) as executor:
        futures = []
        for i, paper in enumerate(papers, 1):
            future = executor.submit(
                process_single_paper, paper, llm_service, i, len(papers), stats
            )
            futures.append(future)

        # 等待所有任务完成
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                logger.error(f"线程执行出错: {str(e)}")

    # 最终统计
    print("\n" + "=" * 80)
    print("✅ 重新评估完成！")
    print(f"   总数: {len(papers)} 篇")
    print(f"   成功: {stats['success']} 篇")
    print(f"   失败: {stats['failed']} 篇")
    print(f"   跳过: {stats['skipped']} 篇")

    # 显示评分变化统计
    conn = get_mysql_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
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
                    FROM papers_relevant
                    GROUP BY score_range
                    ORDER BY MIN(Stars) DESC
                """)
                distribution = cursor.fetchall()
                print("\n当前评分分布:")
                for row in distribution:
                    print(f"   {row['score_range']}: {row['count']} 篇")
        except Exception as e:
            logger.error(f"获取评分分布失败: {str(e)}")
        finally:
            conn.close()


if __name__ == "__main__":
    print("=" * 80)
    print("重新评估失败的论文")
    print("=" * 80)

    try:
        re_evaluate_papers()
        print("\n操作完成！")
    except KeyboardInterrupt:
        print("\n\n操作被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n操作失败: {str(e)}")
        logger.error(f"重新评估失败: {str(e)}", exc_info=True)
        sys.exit(1)
