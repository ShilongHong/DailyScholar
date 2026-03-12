from storage.base import PaperStore
from storage.sqlite_store import SQLiteStore


def create_store(settings: dict) -> PaperStore:
    database = settings["database"]
    engine = database["engine"]
    table_names = {
        "raw": database["table_raw"],
        "relevant": database["table_relevant"],
        "queue": database["table_queue"],
        "config": database["table_config"],
    }

    if engine == "sqlite":
        return SQLiteStore(db_path=database["sqlite_path"], table_names=table_names)

    if engine == "mysql":
        from storage.mysql_store import MySQLStore

        return MySQLStore(config=database, table_names=table_names)

    raise ValueError(f"Unsupported database engine: {engine}")
