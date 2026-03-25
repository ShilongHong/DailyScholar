"""
MySQL数据库服务
负责论文数据的持久化存储
"""

import logging
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ARXIV_CONFIG

# 配置日志
logger = logging.getLogger(__name__)

# 线程本地存储（每个线程独立的连接）
_thread_local = threading.local()


def _get_db_type() -> str:
    """获取当前数据库类型"""
    return ARXIV_CONFIG.get("mysql", {}).get("db_type", "sqlite")


def _get_placeholder() -> str:
    """获取参数占位符"""
    return "?" if _get_db_type() == "sqlite" else "%s"


def _normalize_sql(sql: str) -> str:
    """按数据库类型规范化 SQL"""
    if _get_db_type() == "sqlite":
        sql = sql.replace("%s", "?")
        sql = sql.replace("INSERT IGNORE", "INSERT OR IGNORE")
    return sql


def _normalize_publication_year(publication_year: Any) -> str:
    if publication_year is None:
        return ""

    if isinstance(publication_year, datetime):
        return publication_year.date().isoformat()

    if isinstance(publication_year, date):
        return publication_year.isoformat()

    value = str(publication_year).strip()
    if not value:
        return ""

    if len(value) == 4 and value.isdigit():
        return f"{value}-12-31"

    return value


def get_db_connection():
    """获取数据库连接（支持 MySQL 和 SQLite）"""
    db_config = ARXIV_CONFIG.get("mysql", {})
    if not db_config.get("enable", False):
        return None

    db_type = db_config.get("db_type", "sqlite")
    if db_type == "sqlite":
        return _get_sqlite_connection(db_config)
    return _get_mysql_connection(db_config)


def _get_sqlite_connection(db_config: Dict):
    """获取 SQLite 连接"""
    import os
    import sqlite3

    db_path = db_config.get("sqlite_path", "data/papers.db")
    os.makedirs(
        os.path.dirname(db_path) if os.path.dirname(db_path) else ".", exist_ok=True
    )

    if (
        hasattr(_thread_local, "sqlite_connection")
        and _thread_local.sqlite_connection is not None
    ):
        return _thread_local.sqlite_connection

    try:
        conn = sqlite3.connect(db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        _thread_local.sqlite_connection = conn
        _ensure_sqlite_tables_exist(conn, db_config)
        return conn
    except Exception as e:
        logger.warning(f"⚠️ SQLite连接失败: {str(e)}")
        return None


def _get_mysql_connection(db_config: Dict):
    """获取当前线程的MySQL连接（线程安全）"""
    if hasattr(_thread_local, "connection") and _thread_local.connection is not None:
        try:
            _thread_local.connection.ping(reconnect=True)
            return _thread_local.connection
        except Exception:
            _thread_local.connection = None

    try:
        import pymysql

        _thread_local.connection = pymysql.connect(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", ""),
            database=db_config.get("database", "arxiv_papers"),
            charset=db_config.get("charset", "utf8mb4"),
            cursorclass=pymysql.cursors.DictCursor,
        )
        _ensure_tables_exist(_thread_local.connection, db_config)
        return _thread_local.connection
    except ImportError:
        logger.warning("⚠️ pymysql未安装，跳过MySQL存储")
        return None
    except Exception as e:
        logger.warning(f"⚠️ MySQL连接失败: {str(e)}")
        return None


def _ensure_sqlite_tables_exist(conn, db_config: Dict):
    """确保 SQLite 数据表存在"""
    table_raw = db_config.get("table_raw", "papers_raw")
    table_relevant = db_config.get("table_relevant", "papers_relevant")

    cursor = conn.cursor()
    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_raw} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            DOI TEXT UNIQUE,
            Title TEXT,
            Author TEXT,
            Affiliation TEXT,
            PublicationYear TEXT,
            Abstract TEXT,
            Link TEXT,
            PDFLink TEXT,
            Source TEXT,
            SubjectTerms TEXT,
            processed INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_relevant} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            DOI TEXT UNIQUE,
            Title TEXT,
            TitleCN TEXT,
            Author TEXT,
            Affiliation TEXT,
            PublicationYear TEXT,
            Abstract TEXT,
            AbstractCN TEXT,
            Link TEXT,
            PDFLink TEXT,
            Source TEXT,
            SubjectTerms TEXT,
            Stars INTEGER,
            RelevanceReason TEXT,
            PotentialHelp TEXT,
            is_marked INTEGER DEFAULT 0,
            comment TEXT,
            is_pushed INTEGER DEFAULT 0,
            pushed_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS system_config (
            config_name TEXT PRIMARY KEY,
            config_value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_queue (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            DOI TEXT UNIQUE,
            Title TEXT,
            TitleCN TEXT,
            Author TEXT,
            Affiliation TEXT,
            PublicationYear TEXT,
            Abstract TEXT,
            AbstractCN TEXT,
            Link TEXT,
            PDFLink TEXT,
            Source TEXT,
            SubjectTerms TEXT,
            Stars INTEGER,
            RelevanceReason TEXT,
            PotentialHelp TEXT,
            paper_doi TEXT,
            paper_data TEXT,
            status TEXT DEFAULT 'pending',
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    conn.commit()


def close_mysql_connection():
    """关闭数据库连接"""
    db_type = _get_db_type()
    if db_type == "sqlite":
        conn = getattr(_thread_local, "sqlite_connection", None)
        if conn is not None:
            try:
                conn.close()
                logger.info("SQLite连接已关闭")
            except Exception:
                pass
            _thread_local.sqlite_connection = None
        return

    conn = getattr(_thread_local, "connection", None)
    if conn is not None:
        try:
            conn.close()
            logger.info("MySQL连接已关闭")
        except Exception:
            pass
        _thread_local.connection = None


def _ensure_tables_exist(conn, mysql_config: Dict):
    """确保数据表存在"""
    table_raw = mysql_config.get("table_raw", "papers_raw")
    table_relevant = mysql_config.get("table_relevant", "papers_relevant")

    create_raw_sql = f"""
    CREATE TABLE IF NOT EXISTS `{table_raw}` (
        `id` INT AUTO_INCREMENT PRIMARY KEY,
        `DOI` VARCHAR(50) UNIQUE,
        `Title` TEXT,
        `Author` TEXT,
        `Affiliation` TEXT,
        `PublicationYear` VARCHAR(20),
        `Abstract` LONGTEXT,
        `Link` VARCHAR(500),
        `PDFLink` VARCHAR(500),
        `Source` VARCHAR(200),
        `SubjectTerms` VARCHAR(500),
        `processed` BOOLEAN DEFAULT FALSE,
        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX `idx_publication_year` (`PublicationYear`),
        INDEX `idx_doi` (`DOI`),
        INDEX `idx_processed` (`processed`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    create_relevant_sql = f"""
    CREATE TABLE IF NOT EXISTS `{table_relevant}` (
        `id` INT AUTO_INCREMENT PRIMARY KEY,
        `DOI` VARCHAR(50) UNIQUE,
        `Title` TEXT,
        `TitleCN` TEXT,
        `Author` TEXT,
        `Affiliation` TEXT,
        `PublicationYear` VARCHAR(20),
        `Abstract` LONGTEXT,
        `AbstractCN` LONGTEXT,
        `Link` VARCHAR(500),
        `PDFLink` VARCHAR(500),
        `Source` VARCHAR(200),
        `SubjectTerms` VARCHAR(500),
        `Stars` INT,
        `RelevanceReason` TEXT,
        `PotentialHelp` TEXT,
        `is_marked` BOOLEAN DEFAULT FALSE,
        `is_pushed` BOOLEAN DEFAULT FALSE,
        `comment` TEXT,
        `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        INDEX `idx_publication_year` (`PublicationYear`),
        INDEX `idx_stars` (`Stars`),
        INDEX `idx_doi` (`DOI`),
        INDEX `idx_pushed` (`is_pushed`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """

    try:
        with conn.cursor() as cursor:
            cursor.execute(create_raw_sql)
            cursor.execute(create_relevant_sql)

            # 检查并添加 is_marked 列（针对旧表）
            try:
                cursor.execute(f"SHOW COLUMNS FROM `{table_relevant}` LIKE 'is_marked'")
                if not cursor.fetchone():
                    logger.info(f"Adding 'is_marked' column to {table_relevant}")
                    cursor.execute(
                        f"ALTER TABLE `{table_relevant}` ADD COLUMN `is_marked` BOOLEAN DEFAULT FALSE"
                    )
            except Exception as e:
                logger.warning(f"检查/添加 is_marked 列失败: {str(e)}")

            # 检查并添加 is_pushed 列（针对旧表）
            try:
                cursor.execute(f"SHOW COLUMNS FROM `{table_relevant}` LIKE 'is_pushed'")
                if not cursor.fetchone():
                    logger.info(f"Adding 'is_pushed' column to {table_relevant}")
                    cursor.execute(
                        f"ALTER TABLE `{table_relevant}` ADD COLUMN `is_pushed` BOOLEAN DEFAULT FALSE, ADD INDEX `idx_pushed` (`is_pushed`)"
                    )
            except Exception as e:
                logger.warning(f"检查/添加 is_pushed 列失败: {str(e)}")

            # 检查并添加 comment 列（针对旧表）
            try:
                cursor.execute(f"SHOW COLUMNS FROM `{table_relevant}` LIKE 'comment'")
                if not cursor.fetchone():
                    logger.info(f"Adding 'comment' column to {table_relevant}")
                    cursor.execute(
                        f"ALTER TABLE `{table_relevant}` ADD COLUMN `comment` TEXT"
                    )
            except Exception as e:
                logger.warning(f"检查/添加 comment 列失败: {str(e)}")
                logger.warning(f"检查/添加 is_pushed 列失败: {str(e)}")

            # 检查并添加 processed 列到 papers_raw（针对旧表）
            try:
                cursor.execute(f"SHOW COLUMNS FROM `{table_raw}` LIKE 'processed'")
                if not cursor.fetchone():
                    logger.info(f"Adding 'processed' column to {table_raw}")
                    cursor.execute(
                        f"ALTER TABLE `{table_raw}` ADD COLUMN `processed` BOOLEAN DEFAULT FALSE, ADD INDEX `idx_processed` (`processed`)"
                    )
            except Exception as e:
                logger.warning(f"检查/添加 processed 列失败: {str(e)}")

            # 创建系统配置表
            create_config_sql = """
            CREATE TABLE IF NOT EXISTS `system_config` (
                `config_name` VARCHAR(100) PRIMARY KEY,
                `config_value` LONGTEXT NOT NULL,
                `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_config_sql)

            # 创建推送队列表
            create_queue_sql = """
            CREATE TABLE IF NOT EXISTS `paper_queue` (
                `id` INT AUTO_INCREMENT PRIMARY KEY,
                `DOI` VARCHAR(50) UNIQUE,
                `Title` TEXT,
                `TitleCN` TEXT,
                `Author` TEXT,
                `Affiliation` TEXT,
                `PublicationYear` VARCHAR(20),
                `Abstract` LONGTEXT,
                `AbstractCN` LONGTEXT,
                `Link` VARCHAR(500),
                `PDFLink` VARCHAR(500),
                `Source` VARCHAR(200),
                `SubjectTerms` VARCHAR(500),
                `Stars` INT,
                `RelevanceReason` TEXT,
                `PotentialHelp` TEXT,
                `added_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                INDEX `idx_stars_time` (`Stars` DESC, `added_at` DESC),
                INDEX `idx_doi` (`DOI`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
            """
            cursor.execute(create_queue_sql)

        conn.commit()
        logger.info(
            f"✅ 数据表已确认: {table_raw}, {table_relevant}, system_config, paper_queue"
        )
        return True
    except Exception as e:
        logger.warning(f"⚠️ 创建数据表时出错: {str(e)}")
        return False


def save_raw_papers_to_mysql(papers: List[Dict[str, Any]]) -> int:
    """将原始论文保存到MySQL"""
    conn = get_db_connection()
    if not conn or not papers:
        return 0

    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table_raw = mysql_config.get("table_raw", "papers_raw")
    db_type = _get_db_type()

    insert_sql = f"""
    INSERT IGNORE INTO `{table_raw}` 
    (DOI, Title, Author, Affiliation, PublicationYear, Abstract, Link, PDFLink, Source, SubjectTerms)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    if db_type == "sqlite":
        insert_sql = insert_sql.replace("INSERT IGNORE", "INSERT OR IGNORE")

    saved_count = 0
    try:
        if db_type == "sqlite":
            cursor = conn.cursor()
            for paper in papers:
                try:
                    cursor.execute(
                        _normalize_sql(insert_sql),
                        (
                            paper.get("DOI", ""),
                            paper.get("Title", ""),
                            paper.get("Author", ""),
                            paper.get("Affiliation", ""),
                            _normalize_publication_year(paper.get("PublicationYear")),
                            paper.get("Abstract", ""),
                            paper.get("Link", ""),
                            paper.get("PDFLink", ""),
                            paper.get("Source", ""),
                            paper.get("SubjectTerms", ""),
                        ),
                    )
                    saved_count += cursor.rowcount
                except Exception as e:
                    logger.debug(f"保存论文时跳过: {str(e)}")
                    continue
        else:
            with conn.cursor() as cursor:
                for paper in papers:
                    try:
                        cursor.execute(
                            _normalize_sql(insert_sql),
                            (
                                paper.get("DOI", ""),
                                paper.get("Title", ""),
                                paper.get("Author", ""),
                                paper.get("Affiliation", ""),
                                _normalize_publication_year(
                                    paper.get("PublicationYear")
                                ),
                                paper.get("Abstract", ""),
                                paper.get("Link", ""),
                                paper.get("PDFLink", ""),
                                paper.get("Source", ""),
                                paper.get("SubjectTerms", ""),
                            ),
                        )
                        saved_count += cursor.rowcount
                    except Exception as e:
                        logger.debug(f"保存论文时跳过: {str(e)}")
                        continue
        conn.commit()
        logger.info(
            f"💾 MySQL: 保存了 {saved_count}/{len(papers)} 篇原始论文到 {table_raw}"
        )
    except Exception as e:
        logger.warning(f"⚠️ MySQL批量保存失败: {str(e)}")

    return saved_count


def save_relevant_papers_to_mysql(papers: List[Dict[str, Any]]) -> int:
    """将相关论文保存到MySQL"""
    conn = get_db_connection()
    if not conn or not papers:
        return 0

    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table_relevant = mysql_config.get("table_relevant", "papers_relevant")
    db_type = _get_db_type()

    insert_sql = f"""
    INSERT IGNORE INTO `{table_relevant}` 
    (DOI, Title, TitleCN, Author, Affiliation, PublicationYear, Abstract, AbstractCN, 
     Link, PDFLink, Source, SubjectTerms, Stars, RelevanceReason, PotentialHelp)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    if db_type == "sqlite":
        insert_sql = insert_sql.replace("INSERT IGNORE", "INSERT OR IGNORE")

    saved_count = 0
    try:
        if db_type == "sqlite":
            cursor = conn.cursor()
            for paper in papers:
                try:
                    cursor.execute(
                        _normalize_sql(insert_sql),
                        (
                            paper.get("DOI", ""),
                            paper.get("Title", ""),
                            paper.get("TitleCN", ""),
                            paper.get("Author", ""),
                            paper.get("Affiliation", ""),
                            _normalize_publication_year(paper.get("PublicationYear")),
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

                    saved_count += cursor.rowcount
                except Exception as e:
                    logger.debug(f"保存相关论文时跳过: {str(e)}")
                    continue
        else:
            with conn.cursor() as cursor:
                for paper in papers:
                    try:
                        cursor.execute(
                            _normalize_sql(insert_sql),
                            (
                                paper.get("DOI", ""),
                                paper.get("Title", ""),
                                paper.get("TitleCN", ""),
                                paper.get("Author", ""),
                                paper.get("Affiliation", ""),
                                _normalize_publication_year(
                                    paper.get("PublicationYear")
                                ),
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

                        saved_count += cursor.rowcount
                    except Exception as e:
                        logger.debug(f"保存相关论文时跳过: {str(e)}")
                        continue
        conn.commit()
        logger.info(
            f"💾 MySQL: 保存了 {saved_count}/{len(papers)} 篇相关论文到 {table_relevant}"
        )
    except Exception as e:
        logger.warning(f"⚠️ MySQL批量保存相关论文失败: {str(e)}")

    return saved_count


def execute_query(sql: str, params: tuple = None) -> List[Dict]:
    """执行查询SQL"""
    conn = get_db_connection()
    if not conn:
        return []

    try:
        db_type = _get_db_type()
        sql = _normalize_sql(sql)
        params = params or ()
        if db_type == "sqlite":
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()
    except Exception as e:
        logger.warning(f"⚠️ 查询执行失败: {str(e)}")
        return []


def execute_update(sql: str, params: tuple = None) -> int:
    """执行更新SQL"""
    conn = get_db_connection()
    if not conn:
        return 0

    try:
        db_type = _get_db_type()
        sql = _normalize_sql(sql)
        params = params or ()
        if db_type == "sqlite":
            cursor = conn.cursor()
            cursor.execute(sql, params)
            conn.commit()
            return cursor.rowcount
        with conn.cursor() as cursor:
            cursor.execute(sql, params)
            rowcount = cursor.rowcount
        conn.commit()
        return rowcount
    except Exception as e:
        logger.warning(f"⚠️ SQL执行失败: {str(e)}")
        return 0


def get_all_relevant_papers(
    limit: int = 100,
    offset: int = 0,
    show_pushed: bool = True,
    comment_filter: str = "all",
    min_stars: int = 0,
    only_marked: bool = False,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """获取所有相关论文

    Args:
        limit: 每页数量
        offset: 偏移量
        show_pushed: 是否显示已推送的论文
        comment_filter: 评论筛选 (all/with/without)
        min_stars: 最低分数
        only_marked: 仅显示已标记
        date_start: 开始日期
        date_end: 结束日期
        search: 搜索关键词（搜索标题、标题中文、作者）

    Returns:
        {'papers': List[Dict], 'total': int}
    """
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_relevant", "papers_relevant")

    # 构建WHERE条件
    where_conditions = []
    if not show_pushed:
        where_conditions.append("is_pushed = FALSE")

    # 添加评论筛选条件
    if comment_filter == "with":
        where_conditions.append("(comment IS NOT NULL AND comment != '')")
    elif comment_filter == "without":
        where_conditions.append("(comment IS NULL OR comment = '')")

    # 添加分数筛选
    if min_stars > 0:
        where_conditions.append(f"Stars >= {min_stars}")

    # 添加标记筛选
    if only_marked:
        where_conditions.append("is_marked = TRUE")

    # 添加日期筛选
    search_params = []
    if date_start and date_start.strip():
        where_conditions.append("PublicationYear >= %s")
        search_params.append(date_start.strip())
    if date_end and date_end.strip():
        where_conditions.append("PublicationYear <= %s")
        search_params.append(date_end.strip())

    # 添加搜索条件（使用占位符）
    if search:
        where_conditions.append("""(
            Title LIKE %s OR
            TitleCN LIKE %s OR
            Author LIKE %s
        )""")

    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

    # 构建搜索参数（如果有的话）
    if search:
        search_pattern = f"%{search}%"
        search_params.extend([search_pattern, search_pattern, search_pattern])

    # 获取总数
    count_sql = f"SELECT COUNT(*) as total FROM `{table}` {where_clause}"
    count_result = execute_query(count_sql, tuple(search_params))
    total = count_result[0]["total"] if count_result else 0

    # 获取数据（先按Stars降序，同分数按日期降序）
    sql = f"SELECT * FROM `{table}` {where_clause} ORDER BY Stars DESC, PublicationYear DESC, created_at DESC LIMIT %s OFFSET %s"
    query_params = tuple(search_params + [limit, offset])
    papers = execute_query(sql, query_params)

    return {"papers": papers, "total": total}


def get_relevant_papers_by_date(date: str) -> List[Dict]:
    """获取指定日期的相关论文"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_relevant", "papers_relevant")
    if _get_db_type() == "sqlite":
        sql = f"SELECT * FROM `{table}` WHERE date(created_at) = date(?) ORDER BY Stars DESC"
        return execute_query(sql, (date,))
    sql = f"SELECT * FROM `{table}` WHERE DATE(created_at) = %s ORDER BY Stars DESC"
    return execute_query(sql, (date,))


def get_paper_stats() -> Dict:
    """获取论文统计信息"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table_raw = mysql_config.get("table_raw", "papers_raw")
    table_relevant = mysql_config.get("table_relevant", "papers_relevant")

    stats = {
        "total_raw": 0,
        "total_relevant": 0,
        "today_raw": 0,
        "today_relevant": 0,
        "by_score_range": {},  # 改为分数段统计
    }

    conn = get_db_connection()
    if not conn:
        return stats

    try:
        # 总数
        result = execute_query(f"SELECT COUNT(*) as cnt FROM `{table_raw}`")
        stats["total_raw"] = result[0]["cnt"] if result else 0

        result = execute_query(f"SELECT COUNT(*) as cnt FROM `{table_relevant}`")
        stats["total_relevant"] = result[0]["cnt"] if result else 0

        # 今日
        if _get_db_type() == "sqlite":
            result = execute_query(
                f"SELECT COUNT(*) as cnt FROM `{table_raw}` WHERE date(created_at) = date('now')"
            )
        else:
            result = execute_query(
                f"SELECT COUNT(*) as cnt FROM `{table_raw}` WHERE DATE(created_at) = CURDATE()"
            )
        stats["today_raw"] = result[0]["cnt"] if result else 0

        if _get_db_type() == "sqlite":
            result = execute_query(
                f"SELECT COUNT(*) as cnt FROM `{table_relevant}` WHERE date(created_at) = date('now')"
            )
        else:
            result = execute_query(
                f"SELECT COUNT(*) as cnt FROM `{table_relevant}` WHERE DATE(created_at) = CURDATE()"
            )
        stats["today_relevant"] = result[0]["cnt"] if result else 0

        # 按分数段统计（100分制）
        score_ranges = [
            ("90-100", 90, 100),
            ("80-89", 80, 89),
            ("70-79", 70, 79),
            ("60-69", 60, 69),
            ("0-59", 0, 59),
        ]

        for range_name, min_score, max_score in score_ranges:
            result = execute_query(
                f"SELECT COUNT(*) as cnt FROM `{table_relevant}` WHERE Stars >= %s AND Stars <= %s",
                (min_score, max_score),
            )
            stats["by_score_range"][range_name] = result[0]["cnt"] if result else 0

    except Exception as e:
        logger.warning(f"获取统计信息失败: {str(e)}")

    return stats


def is_mysql_enabled() -> bool:
    """检查MySQL是否启用"""
    return ARXIV_CONFIG.get("mysql", {}).get("enable", False)


def is_paper_processed(doi: str, table: str = "papers_relevant") -> bool:
    """检查单篇论文是否已处理过"""
    if not doi:
        return False

    try:
        sql = f"SELECT 1 FROM `{table}` WHERE DOI = %s LIMIT 1"
        results = execute_query(sql, (doi,))
        return len(results) > 0
    except Exception as e:
        logger.debug(f"检查DOI时出错: {str(e)}")
        return False


def get_processed_dois(table: str = "papers_relevant") -> set:
    """获取已处理过的论文DOI集合"""
    try:
        sql = f"SELECT DOI FROM `{table}`"
        results = execute_query(sql)
        return {r["DOI"] for r in results if r.get("DOI")}
    except Exception as e:
        logger.warning(f"⚠️ 获取已处理DOI列表失败: {str(e)}")
        return set()


def update_paper_mark(doi: str, is_marked: bool) -> bool:
    """更新论文标记状态"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_relevant", "papers_relevant")

    sql = f"UPDATE `{table}` SET is_marked = %s WHERE DOI = %s"
    row_count = execute_update(sql, (is_marked, doi))
    return row_count > 0


def update_paper_comment(doi: str, comment: str) -> bool:
    """更新论文评论"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_relevant", "papers_relevant")

    sql = f"UPDATE `{table}` SET comment = %s WHERE DOI = %s"
    row_count = execute_update(sql, (comment, doi))
    return row_count > 0


def delete_paper(doi: str) -> bool:
    """删除论文"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_relevant", "papers_relevant")

    sql = f"DELETE FROM `{table}` WHERE DOI = %s"
    row_count = execute_update(sql, (doi,))
    return row_count > 0


def get_unprocessed_raw_papers(limit: int = 100) -> List[Dict]:
    """获取未处理的原始论文"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_raw", "papers_raw")

    sql = f"SELECT * FROM `{table}` WHERE processed = FALSE ORDER BY created_at DESC LIMIT %s"
    return execute_query(sql, (limit,))


def mark_papers_as_processed(dois: List[str]) -> int:
    """标记论文为已处理"""
    if not dois:
        return 0

    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_raw", "papers_raw")

    placeholders = ",".join([_get_placeholder()] * len(dois))
    sql = f"UPDATE `{table}` SET processed = TRUE WHERE DOI IN ({placeholders})"
    return execute_update(sql, tuple(dois))


def load_config_from_db(config_name: str) -> Optional[Dict]:
    """从数据库加载配置"""
    try:
        sql = "SELECT config_value FROM system_config WHERE config_name = %s"
        result = execute_query(sql, (config_name,))
        if result:
            import json

            return json.loads(result[0]["config_value"])
        return None
    except Exception as e:
        logger.error(f"从数据库加载配置失败: {str(e)}")
        return None


def save_config_to_db(config_name: str, config_value: Dict) -> bool:
    """保存配置到数据库"""
    try:
        import json

        db_type = _get_db_type()
        value = json.dumps(config_value, ensure_ascii=False)
        if db_type == "sqlite":
            sql = """
            INSERT INTO system_config (config_name, config_value, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT(config_name) DO UPDATE SET
                config_value = excluded.config_value,
                updated_at = CURRENT_TIMESTAMP
            """
            return execute_update(sql, (config_name, value)) > 0

        sql = """
        INSERT INTO system_config (config_name, config_value) 
        VALUES (%s, %s)
        ON DUPLICATE KEY UPDATE config_value = VALUES(config_value), updated_at = CURRENT_TIMESTAMP
        """
        return execute_update(sql, (config_name, value)) > 0
    except Exception as e:
        logger.error(f"保存配置到数据库失败: {str(e)}")
        return False


def get_all_configs_from_db() -> Dict[str, Dict]:
    """获取所有配置"""
    try:
        results = execute_query("SELECT config_name, config_value FROM system_config")
        import json

        configs = {}
        for row in results:
            try:
                configs[row["config_name"]] = json.loads(row["config_value"])
            except Exception:
                pass
        return configs
    except Exception as e:
        logger.error(f"获取所有配置失败: {str(e)}")
        return {}


def enqueue_papers_to_db(papers: List[Dict[str, Any]]) -> int:
    """将论文加入推送队列（数据库）"""
    conn = get_db_connection()
    if not conn or not papers:
        return 0

    db_type = _get_db_type()

    try:
        added_count = 0
        if db_type == "sqlite":
            cursor = conn.cursor()
            for paper in papers:
                sql = """
                INSERT INTO paper_queue 
                (DOI, Title, TitleCN, Author, Affiliation, PublicationYear, 
                 Abstract, AbstractCN, Link, PDFLink, Source, SubjectTerms, 
                 Stars, RelevanceReason, PotentialHelp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE DOI=DOI
                """
                if db_type == "sqlite":
                    sql = sql.replace("INSERT INTO", "INSERT OR IGNORE INTO")
                    sql = sql.replace("ON DUPLICATE KEY UPDATE DOI=DOI", "")
                    sql = sql.replace(
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    )
                try:
                    cursor.execute(
                        _normalize_sql(sql),
                        (
                            paper.get("DOI", ""),
                            paper.get("Title", ""),
                            paper.get("TitleCN", ""),
                            paper.get("Author", ""),
                            paper.get("Affiliation", ""),
                            _normalize_publication_year(paper.get("PublicationYear")),
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
                    if cursor.rowcount > 0:
                        added_count += 1
                except Exception as e:
                    logger.warning(f"添加论文到队列失败 {paper.get('DOI')}: {str(e)}")
                    continue
        else:
            with conn.cursor() as cursor:
                for paper in papers:
                    sql = """
                    INSERT INTO paper_queue 
                    (DOI, Title, TitleCN, Author, Affiliation, PublicationYear, 
                     Abstract, AbstractCN, Link, PDFLink, Source, SubjectTerms, 
                     Stars, RelevanceReason, PotentialHelp)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE DOI=DOI
                    """
                    try:
                        cursor.execute(
                            _normalize_sql(sql),
                            (
                                paper.get("DOI", ""),
                                paper.get("Title", ""),
                                paper.get("TitleCN", ""),
                                paper.get("Author", ""),
                                paper.get("Affiliation", ""),
                                _normalize_publication_year(
                                    paper.get("PublicationYear")
                                ),
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
                        if cursor.rowcount > 0:
                            added_count += 1
                    except Exception as e:
                        logger.warning(
                            f"添加论文到队列失败 {paper.get('DOI')}: {str(e)}"
                        )
                        continue

        conn.commit()
        logger.info(f"✅ 已将 {added_count} 篇新论文加入推送队列")
        return added_count
    except Exception as e:
        logger.error(f"批量添加论文到队列失败: {str(e)}")
        return 0


def dequeue_papers_from_db(max_count: int) -> List[Dict[str, Any]]:
    """从队列中取出论文（自定义策略：>80分全推，否则凑齐max_count，优先当天）"""
    try:
        sql = "SELECT * FROM paper_queue ORDER BY Stars DESC, added_at DESC LIMIT 100"
        all_papers = execute_query(sql)

        if not all_papers:
            return []

        high_score_papers = []
        normal_papers = []
        today = date.today()

        for paper in all_papers:
            stars = paper.get("Stars", 0)
            is_today = False
            added_at = paper.get("added_at")
            if added_at:
                if isinstance(added_at, str):
                    try:
                        dt_str = str(added_at)[:10]
                        added_at_date = datetime.strptime(dt_str, "%Y-%m-%d").date()
                        is_today = added_at_date == today
                    except Exception:
                        pass
                elif hasattr(added_at, "date"):
                    is_today = added_at.date() == today

            paper["_is_today"] = is_today
            if stars > 80:
                high_score_papers.append(paper)
            else:
                normal_papers.append(paper)

        selected_papers = high_score_papers[:]
        if len(selected_papers) < max_count:
            needed = max_count - len(selected_papers)
            normal_papers.sort(
                key=lambda x: (
                    1 if x.get("_is_today") else 0,
                    x.get("Stars", 0),
                    x.get("added_at") if x.get("added_at") else datetime.min,
                ),
                reverse=True,
            )
            selected_papers.extend(normal_papers[:needed])

        if selected_papers:
            dois = [p["DOI"] for p in selected_papers if p.get("DOI")]
            if dois:
                placeholders = ",".join([_get_placeholder()] * len(dois))
                delete_sql = f"DELETE FROM paper_queue WHERE DOI IN ({placeholders})"
                execute_update(delete_sql, tuple(dois))

            logger.info(
                f"✅ 从队列中取出 {len(selected_papers)} 篇论文 (高分>80: {len(high_score_papers)}, 补足: {len(selected_papers) - len(high_score_papers)})"
            )

            for p in selected_papers:
                p.pop("_is_today", None)

        return selected_papers

    except Exception as e:
        logger.error(f"从队列取出论文失败: {str(e)}")
        return []


def get_queue_size_from_db() -> int:
    """获取队列中的论文数量"""
    try:
        result = execute_query("SELECT COUNT(*) as count FROM paper_queue")
        return result[0]["count"] if result else 0
    except Exception as e:
        logger.error(f"获取队列大小失败: {str(e)}")
        return 0


def get_queue_preview_from_db(max_count: int = 10) -> List[Dict[str, Any]]:
    """获取队列预览（不删除）"""
    try:
        sql = """
        SELECT * FROM paper_queue 
        ORDER BY Stars DESC, added_at DESC 
        LIMIT %s
        """
        return execute_query(sql, (max_count,))
    except Exception as e:
        logger.error(f"获取队列预览失败: {str(e)}")
        return []


def clear_queue_in_db() -> bool:
    """清空推送队列"""
    try:
        execute_update("DELETE FROM paper_queue")
        logger.info("✅ 推送队列已清空")
        return True
    except Exception as e:
        logger.error(f"清空队列失败: {str(e)}")
        return False


def get_unpushed_papers(limit: int = 100) -> List[Dict[str, Any]]:
    """获取未推送的相关论文"""
    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_relevant", "papers_relevant")

    try:
        sql = f"""
        SELECT * FROM `{table}` 
        WHERE is_pushed = FALSE 
        ORDER BY Stars DESC, created_at DESC 
        LIMIT %s
        """
        papers = execute_query(sql, (limit,))
        logger.info(f"找到 {len(papers)} 篇未推送的论文")
        return papers
    except Exception as e:
        logger.error(f"获取未推送论文失败: {str(e)}")
        return []


def mark_papers_as_pushed(dois: List[str]) -> int:
    """标记论文为已推送"""
    if not dois:
        return 0

    mysql_config = ARXIV_CONFIG.get("mysql", {})
    table = mysql_config.get("table_relevant", "papers_relevant")

    placeholders = ",".join([_get_placeholder()] * len(dois))
    sql = f"UPDATE `{table}` SET is_pushed = TRUE WHERE DOI IN ({placeholders})"
    row_count = execute_update(sql, tuple(dois))
    if row_count > 0:
        logger.info(f"✅ 已标记 {row_count} 篇论文为已推送")
    return row_count


get_mysql_connection = get_db_connection
