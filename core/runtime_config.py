import json
import logging
import os
from typing import cast

from config import ARXIV_CONFIG, LLM_FILTER_CONFIG, OPENCLAW_CONFIG, SCHEDULE_CONFIG
from services import get_all_configs_from_db, save_config_to_db


LOCAL_CONFIG_FILE = "config.local.json"
LEGACY_RUNTIME_CONFIG_FILE = "runtime_config.json"

ConfigMap = dict[str, object]


def _get_logger(logger: logging.Logger | None = None) -> logging.Logger:
    return logger or logging.getLogger("app")


def load_runtime_config(logger: logging.Logger | None = None) -> ConfigMap:
    active_logger = _get_logger(logger)

    try:
        configs = get_all_configs_from_db()
        if configs:
            active_logger.info(f"从数据库加载了 {len(configs)} 个配置")
            return configs
    except Exception as exc:
        active_logger.warning(f"从数据库加载配置失败: {exc}")

    for config_file in (LOCAL_CONFIG_FILE, LEGACY_RUNTIME_CONFIG_FILE):
        if not os.path.exists(config_file):
            continue

        try:
            with open(config_file, "r", encoding="utf-8") as file:
                configs = cast(ConfigMap, json.load(file))
            active_logger.info(f"从文件加载了 {len(configs)} 个配置")
            for name, value in configs.items():
                _ = save_config_to_db(name, value)
            active_logger.info(f"已将 {config_file} 中的配置迁移到数据库")
            return configs
        except Exception as exc:
            active_logger.warning(f"从文件 {config_file} 加载配置失败: {exc}")

    return {}


def save_runtime_config(
    config: ConfigMap, logger: logging.Logger | None = None
) -> None:
    active_logger = _get_logger(logger)

    success = True
    for name, value in config.items():
        if not save_config_to_db(name, value):
            success = False

    try:
        with open(LOCAL_CONFIG_FILE, "w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)
    except Exception as exc:
        active_logger.error(f"保存配置文件失败: {exc}")

    if not success:
        active_logger.error("部分配置保存失败")


def get_config(name: str, logger: logging.Logger | None = None) -> ConfigMap:
    runtime = load_runtime_config(logger=logger)
    config_map: dict[str, ConfigMap] = {
        "arxiv": cast(ConfigMap, ARXIV_CONFIG),
        "llm_filter": cast(ConfigMap, LLM_FILTER_CONFIG),
        "schedule": cast(ConfigMap, SCHEDULE_CONFIG),
        "openclaw": cast(ConfigMap, OPENCLAW_CONFIG),
    }

    base_config = dict(config_map.get(name, {}))
    runtime_value = runtime.get(name)
    if isinstance(runtime_value, dict):
        base_config.update(cast(ConfigMap, runtime_value))

    return base_config
