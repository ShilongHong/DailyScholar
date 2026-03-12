import sqlite3
import json
from pathlib import Path
from typing import Final, cast, override

from storage.base import PaperQueryResult, PaperRecord, PaperStore


class SQLiteStore(PaperStore):
    db_path: Final[Path]
    table_names: Final[dict[str, str]]

    def __init__(self, db_path: str, table_names: dict[str, str]):
        self.db_path = Path(db_path)
        self.table_names = table_names
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @override
    def init_schema(self) -> None:
        raw_table = self.table_names["raw"]
        relevant_table = self.table_names["relevant"]
        queue_table = self.table_names["queue"]
        config_table = self.table_names["config"]

        with self._connect() as connection:
            _ = connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {raw_table} (
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
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            _ = connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {relevant_table} (
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
                    is_pushed INTEGER DEFAULT 0,
                    comment TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            _ = connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {queue_table} (
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
                    added_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            _ = connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {config_table} (
                    config_name TEXT PRIMARY KEY,
                    config_value TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def list_tables(self) -> set[str]:
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall(),
            )
        table_names: set[str] = set()
        for row in rows:
            table_names.add(str(cast(object, row[0])))
        return table_names

    def save_raw_papers(self, papers: list[PaperRecord]) -> int:
        raw_table = self.table_names["raw"]
        inserted = 0

        with self._connect() as connection:
            for paper in papers:
                cursor = connection.execute(
                    f"""
                    INSERT OR IGNORE INTO {raw_table} (
                        DOI, Title, Author, Affiliation, PublicationYear,
                        Abstract, Link, PDFLink, Source, SubjectTerms, processed
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper.get("DOI", ""),
                        paper.get("Title", ""),
                        paper.get("Author", ""),
                        paper.get("Affiliation", ""),
                        paper.get("PublicationYear", ""),
                        paper.get("Abstract", ""),
                        paper.get("Link", ""),
                        paper.get("PDFLink", ""),
                        paper.get("Source", ""),
                        paper.get("SubjectTerms", ""),
                        0,
                    ),
                )
                inserted += cursor.rowcount

        return inserted

    @override
    def save_relevant_papers(self, papers: list[PaperRecord]) -> int:
        relevant_table = self.table_names["relevant"]
        inserted = 0

        with self._connect() as connection:
            for paper in papers:
                cursor = connection.execute(
                    f"""
                    INSERT OR IGNORE INTO {relevant_table} (
                        DOI, Title, TitleCN, Author, Affiliation, PublicationYear,
                        Abstract, AbstractCN, Link, PDFLink, Source, SubjectTerms,
                        Stars, RelevanceReason, PotentialHelp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper.get("DOI", ""),
                        paper.get("Title", ""),
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
                inserted += cursor.rowcount

        return inserted

    @override
    def get_all_relevant_papers(self, limit: int, offset: int) -> PaperQueryResult:
        relevant_table = self.table_names["relevant"]

        with self._connect() as connection:
            count_row = cast(
                sqlite3.Row,
                connection.execute(f"SELECT COUNT(*) FROM {relevant_table}").fetchone(),
            )
            total = cast(int, count_row[0])
            rows = connection.execute(
                f"SELECT * FROM {relevant_table} ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
            rows = cast(list[sqlite3.Row], rows)

        return {
            "total": total,
            "items": [dict(row) for row in rows],
        }

    def get_relevant_papers_by_date(self, publication_year: str) -> list[PaperRecord]:
        relevant_table = self.table_names["relevant"]
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    f"SELECT * FROM {relevant_table} WHERE PublicationYear = ? ORDER BY created_at DESC",
                    (publication_year,),
                ).fetchall(),
            )
        return [dict(row) for row in rows]

    def get_paper_stats(self) -> dict[str, int]:
        raw_table = self.table_names["raw"]
        relevant_table = self.table_names["relevant"]
        queue_table = self.table_names["queue"]

        with self._connect() as connection:
            total_raw = cast(
                int,
                cast(
                    sqlite3.Row,
                    connection.execute(f"SELECT COUNT(*) FROM {raw_table}").fetchone(),
                )[0],
            )
            total_relevant = cast(
                int,
                cast(
                    sqlite3.Row,
                    connection.execute(
                        f"SELECT COUNT(*) FROM {relevant_table}"
                    ).fetchone(),
                )[0],
            )
            total_queue = cast(
                int,
                cast(
                    sqlite3.Row,
                    connection.execute(
                        f"SELECT COUNT(*) FROM {queue_table}"
                    ).fetchone(),
                )[0],
            )
        return {
            "raw_count": total_raw,
            "relevant_count": total_relevant,
            "queue_count": total_queue,
        }

    def is_paper_processed(self, doi: str) -> bool:
        raw_table = self.table_names["raw"]
        with self._connect() as connection:
            row = cast(
                sqlite3.Row | None,
                connection.execute(
                    f"SELECT processed FROM {raw_table} WHERE DOI = ? LIMIT 1",
                    (doi,),
                ).fetchone(),
            )
        return bool(row and row[0])

    def update_paper_mark(self, doi: str, is_marked: bool) -> bool:
        relevant_table = self.table_names["relevant"]
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE {relevant_table} SET is_marked = ? WHERE DOI = ?",
                (1 if is_marked else 0, doi),
            )
        return cursor.rowcount > 0

    def update_paper_comment(self, doi: str, comment: str) -> bool:
        relevant_table = self.table_names["relevant"]
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE {relevant_table} SET comment = ? WHERE DOI = ?",
                (comment, doi),
            )
        return cursor.rowcount > 0

    def delete_paper(self, doi: str) -> bool:
        relevant_table = self.table_names["relevant"]
        with self._connect() as connection:
            cursor = connection.execute(
                f"DELETE FROM {relevant_table} WHERE DOI = ?",
                (doi,),
            )
        return cursor.rowcount > 0

    def get_unprocessed_raw_papers(self, limit: int) -> list[PaperRecord]:
        raw_table = self.table_names["raw"]
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    f"SELECT * FROM {raw_table} WHERE processed = 0 ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall(),
            )
        return [dict(row) for row in rows]

    def mark_papers_as_processed(self, dois: list[str]) -> int:
        if not dois:
            return 0

        raw_table = self.table_names["raw"]
        placeholders = ", ".join(["?"] * len(dois))
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE {raw_table} SET processed = 1 WHERE DOI IN ({placeholders})",
                tuple(dois),
            )
        return cursor.rowcount

    def load_config(self, config_name: str) -> object | None:
        config_table = self.table_names["config"]
        with self._connect() as connection:
            row = cast(
                sqlite3.Row | None,
                connection.execute(
                    f"SELECT config_value FROM {config_table} WHERE config_name = ? LIMIT 1",
                    (config_name,),
                ).fetchone(),
            )
        if row is None:
            return None
        return json.loads(str(row[0]))

    def save_config(self, config_name: str, config_value: object) -> bool:
        config_table = self.table_names["config"]
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO {config_table} (config_name, config_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(config_name)
                DO UPDATE SET config_value = excluded.config_value, updated_at = CURRENT_TIMESTAMP
                """,
                (config_name, json.dumps(config_value, ensure_ascii=False)),
            )
        return True

    def get_all_configs(self) -> dict[str, object]:
        config_table = self.table_names["config"]
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    f"SELECT config_name, config_value FROM {config_table}"
                ).fetchall(),
            )
        return {str(row[0]): json.loads(str(row[1])) for row in rows}

    def enqueue_papers(self, papers: list[PaperRecord]) -> int:
        queue_table = self.table_names["queue"]
        inserted = 0
        with self._connect() as connection:
            for paper in papers:
                cursor = connection.execute(
                    f"""
                    INSERT OR IGNORE INTO {queue_table} (
                        DOI, Title, TitleCN, Author, Affiliation, PublicationYear,
                        Abstract, AbstractCN, Link, PDFLink, Source, SubjectTerms,
                        Stars, RelevanceReason, PotentialHelp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        paper.get("DOI", ""),
                        paper.get("Title", ""),
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
                inserted += cursor.rowcount
        return inserted

    def dequeue_papers(self, max_count: int) -> list[PaperRecord]:
        queue_table = self.table_names["queue"]
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    f"SELECT * FROM {queue_table} ORDER BY Stars DESC, added_at DESC LIMIT ?",
                    (max_count,),
                ).fetchall(),
            )
            dois = [str(row[1]) for row in rows if row[1]]
            if dois:
                placeholders = ", ".join(["?"] * len(dois))
                connection.execute(
                    f"DELETE FROM {queue_table} WHERE DOI IN ({placeholders})",
                    tuple(dois),
                )
        return [dict(row) for row in rows]

    def get_queue_size(self) -> int:
        queue_table = self.table_names["queue"]
        with self._connect() as connection:
            row = cast(
                sqlite3.Row,
                connection.execute(f"SELECT COUNT(*) FROM {queue_table}").fetchone(),
            )
        return cast(int, row[0])

    def get_queue_preview(self, max_count: int) -> list[PaperRecord]:
        queue_table = self.table_names["queue"]
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    f"SELECT * FROM {queue_table} ORDER BY Stars DESC, added_at DESC LIMIT ?",
                    (max_count,),
                ).fetchall(),
            )
        return [dict(row) for row in rows]

    def clear_queue(self) -> None:
        queue_table = self.table_names["queue"]
        with self._connect() as connection:
            _ = connection.execute(f"DELETE FROM {queue_table}")

    def get_unpushed_papers(self, limit: int) -> list[PaperRecord]:
        relevant_table = self.table_names["relevant"]
        with self._connect() as connection:
            rows = cast(
                list[sqlite3.Row],
                connection.execute(
                    f"SELECT * FROM {relevant_table} WHERE is_pushed = 0 ORDER BY Stars DESC, created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall(),
            )
        return [dict(row) for row in rows]

    def mark_papers_as_pushed(self, dois: list[str]) -> int:
        if not dois:
            return 0

        relevant_table = self.table_names["relevant"]
        placeholders = ", ".join(["?"] * len(dois))
        with self._connect() as connection:
            cursor = connection.execute(
                f"UPDATE {relevant_table} SET is_pushed = 1 WHERE DOI IN ({placeholders})",
                tuple(dois),
            )
        return cursor.rowcount
