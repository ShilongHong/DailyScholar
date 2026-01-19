"""
重新评分脚本
对已有的论文使用新的100分制评分标准重新评估
"""

import sys
import os
import logging
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from config import LLM_FILTER_CONFIG, ARXIV_CONFIG
from services.llm_filter_service import LLMFilterService
from services.mysql_service import get_mysql_connection, execute_query, execute_update

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            f"logs/rescore_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)


def get_papers_to_rescore(
    limit: int | None = None,
    min_old_stars: int | None = None,
    max_old_stars: int | None = None,
) -> list:
    """获取需要重新评分的论文"""
    table = ARXIV_CONFIG["mysql"]["table_relevant"]

    sql = (
        f"SELECT DOI, Title, Abstract, Stars, RelevanceReason FROM `{table}` WHERE 1=1"
    )
    params = []

    # 可选：只重新评估特定星级范围的论文
    if min_old_stars is not None:
        sql += " AND Stars >= %s"
        params.append(min_old_stars)
    if max_old_stars is not None:
        sql += " AND Stars <= %s"
        params.append(max_old_stars)

    sql += " ORDER BY created_at DESC"

    if limit:
        sql += f" LIMIT {limit}"

    if params:
        return execute_query(sql, tuple(params)) or []
    return execute_query(sql) or []


def update_paper_score(
    doi: str, new_score: int, new_reason: str, new_help: str
) -> bool:
    """更新论文评分"""
    table = ARXIV_CONFIG["mysql"]["table_relevant"]

    sql = f"""
    UPDATE `{table}` 
    SET Stars = %s, RelevanceReason = %s, PotentialHelp = %s
    WHERE DOI = %s
    """

    return bool(execute_update(sql, (new_score, new_reason, new_help, doi)))


def rescore_paper(llm_service: LLMFilterService, paper: dict) -> dict:
    """重新评估单篇论文"""
    try:
        result = llm_service.evaluate_paper(paper)
        return {
            "doi": paper["DOI"],
            "title": paper["Title"][:50],
            "old_score": paper["Stars"],
            "new_score": result["score"],
            "reason": result["reason"],
            "help": result.get("help", ""),
            "success": True,
        }
    except Exception as e:
        logger.error(f"评估论文 {paper['DOI']} 失败: {e}")
        return {
            "doi": paper["DOI"],
            "title": paper["Title"][:50],
            "old_score": paper["Stars"],
            "new_score": None,
            "success": False,
            "error": str(e),
        }


def main():
    parser = argparse.ArgumentParser(description="重新评分已有论文")
    parser.add_argument("--limit", type=int, default=None, help="最多处理多少篇论文")
    parser.add_argument(
        "--min-old", type=int, default=None, help="只处理旧评分>=该值的论文"
    )
    parser.add_argument(
        "--max-old", type=int, default=None, help="只处理旧评分<=该值的论文"
    )
    parser.add_argument("--workers", type=int, default=12, help="并行线程数")
    parser.add_argument("--dry-run", action="store_true", help="只评估不更新数据库")
    parser.add_argument(
        "--convert-only",
        action="store_true",
        help="只转换旧5星制为100分制（不重新LLM评估）",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("开始重新评分任务")
    logger.info(
        f"参数: limit={args.limit}, min_old={args.min_old}, max_old={args.max_old}"
    )
    logger.info(
        f"      workers={args.workers}, dry_run={args.dry_run}, convert_only={args.convert_only}"
    )
    logger.info("=" * 60)

    # 获取需要重新评分的论文
    papers = get_papers_to_rescore(
        limit=args.limit, min_old_stars=args.min_old, max_old_stars=args.max_old
    )

    if not papers:
        logger.info("没有找到需要重新评分的论文")
        return

    logger.info(f"找到 {len(papers)} 篇论文需要处理")

    # 如果只是转换旧格式
    if args.convert_only:
        logger.info("模式: 仅转换5星制为100分制")
        converted = 0
        for paper in papers:
            old_score = paper["Stars"]
            if old_score is not None and old_score <= 5:
                # 旧的5星制，转换为100分制
                new_score = old_score * 20
                if not args.dry_run:
                    update_paper_score(
                        paper["DOI"],
                        new_score,
                        paper.get("RelevanceReason", ""),
                        paper.get("PotentialHelp", ""),
                    )
                logger.info(
                    f"  {paper['Title'][:40]}... : {old_score}星 -> {new_score}分"
                )
                converted += 1
        logger.info(f"转换完成: {converted} 篇论文")
        return

    # 使用LLM重新评估
    llm_service = LLMFilterService()

    results = []
    success_count = 0
    fail_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(rescore_paper, llm_service, p): p for p in papers}

        for i, future in enumerate(as_completed(futures), 1):
            result = future.result()
            results.append(result)

            if result["success"]:
                success_count += 1
                old_display = (
                    f"{result['old_score']}星"
                    if result["old_score"] <= 5
                    else f"{result['old_score']}分"
                )
                logger.info(
                    f"[{i}/{len(papers)}] ✅ {result['title']}... : "
                    f"{old_display} -> {result['new_score']}分"
                )

                # 更新数据库
                if not args.dry_run:
                    update_paper_score(
                        result["doi"],
                        result["new_score"],
                        result["reason"],
                        result["help"],
                    )
            else:
                fail_count += 1
                logger.error(f"[{i}/{len(papers)}] ❌ {result['title']}... : 失败")

    # 统计结果
    logger.info("=" * 60)
    logger.info("重新评分完成!")
    logger.info(f"成功: {success_count} 篇")
    logger.info(f"失败: {fail_count} 篇")

    if results:
        # 统计分数分布
        scores = [
            r["new_score"]
            for r in results
            if r["success"] and r["new_score"] is not None
        ]
        if scores:
            logger.info(f"分数分布:")
            logger.info(
                f"  90-100分 (高度相关): {len([s for s in scores if s >= 90])} 篇"
            )
            logger.info(
                f"  80-89分 (很相关):   {len([s for s in scores if 80 <= s < 90])} 篇"
            )
            logger.info(
                f"  70-79分 (较相关):   {len([s for s in scores if 70 <= s < 80])} 篇"
            )
            logger.info(
                f"  60-69分 (中等相关): {len([s for s in scores if 60 <= s < 70])} 篇"
            )
            logger.info(
                f"  <60分 (不合格):     {len([s for s in scores if s < 60])} 篇"
            )
            logger.info(f"  平均分: {sum(scores) / len(scores):.1f}")

    if args.dry_run:
        logger.info("⚠️ 这是试运行模式，数据库未更新")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
