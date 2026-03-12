PaperRecord = dict[str, object]
PaperQueryResult = dict[str, object]


class PaperStore:
    def init_schema(self) -> None:
        raise NotImplementedError

    def save_raw_papers(self, _papers: list[PaperRecord]) -> int:
        raise NotImplementedError

    def save_relevant_papers(self, _papers: list[PaperRecord]) -> int:
        raise NotImplementedError

    def get_all_relevant_papers(self, _limit: int, _offset: int) -> PaperQueryResult:
        raise NotImplementedError

    def get_relevant_papers_by_date(self, _publication_year: str) -> list[PaperRecord]:
        raise NotImplementedError

    def get_paper_stats(self) -> dict[str, int]:
        raise NotImplementedError

    def is_paper_processed(self, _doi: str) -> bool:
        raise NotImplementedError

    def update_paper_mark(self, _doi: str, _is_marked: bool) -> bool:
        raise NotImplementedError

    def update_paper_comment(self, _doi: str, _comment: str) -> bool:
        raise NotImplementedError

    def delete_paper(self, _doi: str) -> bool:
        raise NotImplementedError

    def get_unprocessed_raw_papers(self, _limit: int) -> list[PaperRecord]:
        raise NotImplementedError

    def mark_papers_as_processed(self, _dois: list[str]) -> int:
        raise NotImplementedError

    def load_config(self, _config_name: str) -> object | None:
        raise NotImplementedError

    def save_config(self, _config_name: str, _config_value: object) -> bool:
        raise NotImplementedError

    def get_all_configs(self) -> dict[str, object]:
        raise NotImplementedError

    def enqueue_papers(self, _papers: list[PaperRecord]) -> int:
        raise NotImplementedError

    def dequeue_papers(self, _max_count: int) -> list[PaperRecord]:
        raise NotImplementedError

    def get_queue_size(self) -> int:
        raise NotImplementedError

    def get_queue_preview(self, _max_count: int) -> list[PaperRecord]:
        raise NotImplementedError

    def clear_queue(self) -> None:
        raise NotImplementedError

    def get_unpushed_papers(self, _limit: int) -> list[PaperRecord]:
        raise NotImplementedError

    def mark_papers_as_pushed(self, _dois: list[str]) -> int:
        raise NotImplementedError
