from storage.base import PaperQueryResult, PaperRecord, PaperStore
from services import mysql_service as mysql_backend
from typing import Final, cast, override


class MySQLStore(PaperStore):
    config: Final[dict[str, object]]
    table_names: Final[dict[str, str]]

    def __init__(self, config: dict[str, object], table_names: dict[str, str]):
        self.config = config
        self.table_names = table_names

    @override
    def init_schema(self) -> None:
        connection = mysql_backend.get_mysql_connection()
        if connection:
            mysql_backend._ensure_tables_exist(connection, cast(dict, self.config))

    @override
    def save_raw_papers(self, papers: list[PaperRecord]) -> int:
        return mysql_backend.save_raw_papers_to_mysql(papers)

    @override
    def save_relevant_papers(self, papers: list[PaperRecord]) -> int:
        return mysql_backend.save_relevant_papers_to_mysql(papers)

    @override
    def get_all_relevant_papers(self, limit: int, offset: int) -> PaperQueryResult:
        return mysql_backend.get_all_relevant_papers(limit=limit, offset=offset)

    @override
    def get_relevant_papers_by_date(self, publication_year: str) -> list[PaperRecord]:
        return cast(
            list[PaperRecord],
            mysql_backend.get_relevant_papers_by_date(publication_year),
        )

    @override
    def get_paper_stats(self) -> dict[str, int]:
        return cast(dict[str, int], mysql_backend.get_paper_stats())

    @override
    def is_paper_processed(self, doi: str) -> bool:
        return mysql_backend.is_paper_processed(doi)

    @override
    def update_paper_mark(self, doi: str, is_marked: bool) -> bool:
        return mysql_backend.update_paper_mark(doi, is_marked)

    @override
    def update_paper_comment(self, doi: str, comment: str) -> bool:
        return mysql_backend.update_paper_comment(doi, comment)

    @override
    def delete_paper(self, doi: str) -> bool:
        return mysql_backend.delete_paper(doi)

    @override
    def get_unprocessed_raw_papers(self, limit: int) -> list[PaperRecord]:
        return cast(list[PaperRecord], mysql_backend.get_unprocessed_raw_papers(limit))

    @override
    def mark_papers_as_processed(self, dois: list[str]) -> int:
        return mysql_backend.mark_papers_as_processed(dois)

    @override
    def load_config(self, config_name: str) -> object | None:
        return mysql_backend.load_config_from_db(config_name)

    @override
    def save_config(self, config_name: str, config_value: object) -> bool:
        return mysql_backend.save_config_to_db(config_name, cast(dict, config_value))

    @override
    def get_all_configs(self) -> dict[str, object]:
        return cast(dict[str, object], mysql_backend.get_all_configs_from_db())

    @override
    def enqueue_papers(self, papers: list[PaperRecord]) -> int:
        return mysql_backend.enqueue_papers_to_db(papers)

    @override
    def dequeue_papers(self, max_count: int) -> list[PaperRecord]:
        return cast(list[PaperRecord], mysql_backend.dequeue_papers_from_db(max_count))

    @override
    def get_queue_size(self) -> int:
        return mysql_backend.get_queue_size_from_db()

    @override
    def get_queue_preview(self, max_count: int) -> list[PaperRecord]:
        return cast(
            list[PaperRecord], mysql_backend.get_queue_preview_from_db(max_count)
        )

    @override
    def clear_queue(self) -> None:
        _ = mysql_backend.clear_queue_in_db()

    @override
    def get_unpushed_papers(self, limit: int) -> list[PaperRecord]:
        return cast(list[PaperRecord], mysql_backend.get_unpushed_papers(limit))

    @override
    def mark_papers_as_pushed(self, dois: list[str]) -> int:
        return mysql_backend.mark_papers_as_pushed(dois)
