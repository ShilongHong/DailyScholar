import json
from pathlib import Path

from core.config_loader import load_settings
from storage.factory import create_store


def build_local_config(
    database_engine: str = "sqlite",
    sqlite_path: str = "data/paper2data.db",
    session_key: str = "main",
) -> dict[str, object]:
    return {
        "database": {
            "engine": database_engine,
            "sqlite_path": sqlite_path,
        },
        "openclaw": {
            "session_key": session_key,
        },
    }


def write_local_config(target: Path, config: dict[str, object]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def initialize_store(local_config_path: Path) -> None:
    settings = load_settings(local_config_path=str(local_config_path))
    store = create_store(settings)
    store.init_schema()


def run_init_wizard() -> Path:
    database_engine = (
        input("数据库类型（sqlite/mysql，默认 sqlite）: ").strip() or "sqlite"
    )
    sqlite_path = "data/paper2data.db"
    if database_engine == "sqlite":
        sqlite_path = (
            input("SQLite 文件路径（默认 data/paper2data.db）: ").strip() or sqlite_path
        )
    session_key = input("OpenClaw session key（默认 main）: ").strip() or "main"

    config = build_local_config(
        database_engine=database_engine,
        sqlite_path=sqlite_path,
        session_key=session_key,
    )
    target = Path(__file__).resolve().parents[1] / "config.local.json"
    write_local_config(target, config)
    initialize_store(target)
    return target
