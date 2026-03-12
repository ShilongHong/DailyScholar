def test_sqlite_store_initializes_required_tables(tmp_path):
    from storage.sqlite_store import SQLiteStore

    db_path = tmp_path / "paper2data.db"
    store = SQLiteStore(
        db_path=str(db_path),
        table_names={
            "raw": "papers_raw",
            "relevant": "papers_relevant",
            "queue": "paper_queue",
            "config": "system_config",
        },
    )

    store.init_schema()

    tables = store.list_tables()
    assert {"papers_raw", "papers_relevant", "paper_queue", "system_config"}.issubset(
        tables
    )


def test_sqlite_store_saves_and_reads_relevant_papers(tmp_path):
    from storage.sqlite_store import SQLiteStore

    store = SQLiteStore(
        db_path=str(tmp_path / "app.db"),
        table_names={
            "raw": "papers_raw",
            "relevant": "papers_relevant",
            "queue": "paper_queue",
            "config": "system_config",
        },
    )
    store.init_schema()

    count = store.save_relevant_papers(
        [
            {
                "DOI": "x1",
                "Title": "Paper",
                "TitleCN": "论文",
                "Abstract": "Abstract",
                "AbstractCN": "摘要",
                "Stars": 88,
                "Link": "https://example.com/paper",
            }
        ]
    )

    assert count == 1
    result = store.get_all_relevant_papers(limit=10, offset=0)
    assert result["total"] == 1


def test_load_settings_prefers_local_file_over_defaults(tmp_path):
    from core.config_loader import load_settings

    local_file = tmp_path / "config.local.json"
    local_file.write_text('{"database": {"engine": "sqlite"}}', encoding="utf-8")

    settings = load_settings(local_config_path=str(local_file), runtime_store=None)
    assert settings["database"]["engine"] == "sqlite"


def test_bootstrap_writes_local_config(tmp_path):
    from core.bootstrap import write_local_config

    target = tmp_path / "config.local.json"
    write_local_config(target, {"database": {"engine": "sqlite"}})

    assert target.exists()


def test_create_store_returns_mysql_store_for_mysql_engine():
    from storage.factory import create_store

    store = create_store(
        {
            "database": {
                "engine": "mysql",
                "host": "localhost",
                "port": 3306,
                "user": "root",
                "password": "",
                "database": "paper2data",
                "charset": "utf8mb4",
                "table_raw": "papers_raw",
                "table_relevant": "papers_relevant",
                "table_queue": "paper_queue",
                "table_config": "system_config",
            }
        }
    )

    assert store.__class__.__name__ == "MySQLStore"
