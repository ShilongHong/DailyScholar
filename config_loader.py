"""配置加载入口。

优先读取本地 config.py 中的同名常量；缺失时回退到 config_defaults.py。
这样干净仓库可以直接启动，同时仍支持本地敏感配置不入库。
"""

from __future__ import annotations

from copy import deepcopy
from importlib import import_module
from types import ModuleType
from typing import Any

import config_defaults as defaults


CONFIG_NAMES = [
    "ARXIV_CONFIG",
    "LLM_FILTER_CONFIG",
    "SCHEDULE_CONFIG",
    "DINGTALK_CONFIG",
    "MINERU_CONFIG",
    "MESSAGE_CONFIG",
    "OUTPUT_CONFIG",
    "LOGGING_CONFIG",
    "RESEARCH_DESCRIPTION",
]


def _deep_merge(base: Any, override: Any) -> Any:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged.get(key), value)
        return merged
    return deepcopy(override)


def _load_local_config() -> ModuleType | None:
    try:
        return import_module("config")
    except ModuleNotFoundError as exc:
        if exc.name == "config":
            return None
        raise


_local_config = _load_local_config()

for _name in CONFIG_NAMES:
    _default_value = deepcopy(getattr(defaults, _name))
    if _local_config and hasattr(_local_config, _name):
        globals()[_name] = _deep_merge(_default_value, getattr(_local_config, _name))
    else:
        globals()[_name] = _default_value


__all__ = CONFIG_NAMES