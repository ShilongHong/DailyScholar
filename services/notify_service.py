from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from importlib import import_module
from typing import cast

import logging
import threading

logger = logging.getLogger(__name__)

_NOTIFY_PUSH_CONFIG_LOCK = threading.Lock()


FORBIDDEN_BROADCAST_KEYS = {
    "broadcast",
    "broadcast_channels",
    "channels_enabled",
    "enabled_channels",
    "fanout",
    "multi_channel",
    "all_channels",
}


NOTIFY_CHANNEL_ENV_MAPPING: dict[str, dict[str, str]] = {
    "console": {
        "CONSOLE": "CONSOLE",
        "HITOKOTO": "HITOKOTO",
    },
    "bark": {
        "BARK_PUSH": "BARK_PUSH",
        "BARK_ARCHIVE": "BARK_ARCHIVE",
        "BARK_GROUP": "BARK_GROUP",
        "BARK_SOUND": "BARK_SOUND",
        "BARK_ICON": "BARK_ICON",
        "BARK_LEVEL": "BARK_LEVEL",
        "BARK_URL": "BARK_URL",
        "HITOKOTO": "HITOKOTO",
    },
    "dingtalk_webhook": {
        "DD_BOT_TOKEN": "DD_BOT_TOKEN",
        "DD_BOT_SECRET": "DD_BOT_SECRET",
        "HITOKOTO": "HITOKOTO",
    },
    "feishu": {
        "FSKEY": "FSKEY",
        "FSSECRET": "FSSECRET",
        "HITOKOTO": "HITOKOTO",
    },
    "telegram": {
        "TG_BOT_TOKEN": "TG_BOT_TOKEN",
        "TG_USER_ID": "TG_USER_ID",
        "TG_API_HOST": "TG_API_HOST",
        "TG_PROXY_AUTH": "TG_PROXY_AUTH",
        "TG_PROXY_HOST": "TG_PROXY_HOST",
        "TG_PROXY_PORT": "TG_PROXY_PORT",
        "HITOKOTO": "HITOKOTO",
    },
    "smtp": {
        "SMTP_SERVER": "SMTP_SERVER",
        "SMTP_SSL": "SMTP_SSL",
        "SMTP_EMAIL": "SMTP_EMAIL",
        "SMTP_PASSWORD": "SMTP_PASSWORD",
        "SMTP_NAME": "SMTP_NAME",
        "HITOKOTO": "HITOKOTO",
    },
    "wxpusher": {
        "WXPUSHER_APP_TOKEN": "WXPUSHER_APP_TOKEN",
        "WXPUSHER_TOPIC_IDS": "WXPUSHER_TOPIC_IDS",
        "WXPUSHER_UIDS": "WXPUSHER_UIDS",
        "HITOKOTO": "HITOKOTO",
    },
}


CHANNEL_REGISTRY: dict[str, dict[str, object]] = {
    "console": {
        "display_name": "控制台",
        "required_keys": ["CONSOLE"],
        "send_mode": "direct",
        "supports_markdown": False,
        "optional_keys": ["HITOKOTO"],
        "field_mapping": NOTIFY_CHANNEL_ENV_MAPPING["console"],
        "field_defaults": {"HITOKOTO": False},
    },
    "bark": {
        "display_name": "Bark",
        "required_keys": ["BARK_PUSH"],
        "send_mode": "direct",
        "supports_markdown": True,
        "optional_keys": [
            "BARK_ARCHIVE",
            "BARK_GROUP",
            "BARK_SOUND",
            "BARK_ICON",
            "BARK_LEVEL",
            "BARK_URL",
            "HITOKOTO",
        ],
        "field_mapping": NOTIFY_CHANNEL_ENV_MAPPING["bark"],
        "field_defaults": {"HITOKOTO": False},
    },
    "dingtalk_app": {
        "display_name": "钉钉应用机器人",
        "required_keys": [
            "app_key",
            "app_secret",
            "robot_code",
            "open_conversation_id",
        ],
        "send_mode": "adapter",
        "supports_markdown": True,
        "optional_keys": [],
        "field_mapping": {
            "app_key": "DINGTALK_CONFIG.app_key",
            "app_secret": "DINGTALK_CONFIG.app_secret",
            "robot_code": "DINGTALK_CONFIG.robot_code",
            "open_conversation_id": "DINGTALK_CONFIG.open_conversation_id",
        },
    },
    "dingtalk_webhook": {
        "display_name": "钉钉Webhook机器人",
        "required_keys": ["DD_BOT_TOKEN"],
        "send_mode": "direct",
        "supports_markdown": False,
        "optional_keys": ["DD_BOT_SECRET", "HITOKOTO"],
        "field_mapping": NOTIFY_CHANNEL_ENV_MAPPING["dingtalk_webhook"],
        "field_defaults": {"HITOKOTO": False},
    },
    "feishu": {
        "display_name": "飞书机器人",
        "required_keys": ["FSKEY"],
        "send_mode": "direct",
        "supports_markdown": False,
        "optional_keys": ["FSSECRET", "HITOKOTO"],
        "field_mapping": NOTIFY_CHANNEL_ENV_MAPPING["feishu"],
        "field_defaults": {"HITOKOTO": False},
    },
    "telegram": {
        "display_name": "Telegram",
        "required_keys": ["TG_BOT_TOKEN", "TG_USER_ID"],
        "send_mode": "direct",
        "supports_markdown": False,
        "optional_keys": [
            "TG_API_HOST",
            "TG_PROXY_AUTH",
            "TG_PROXY_HOST",
            "TG_PROXY_PORT",
            "HITOKOTO",
        ],
        "field_mapping": NOTIFY_CHANNEL_ENV_MAPPING["telegram"],
        "field_defaults": {"HITOKOTO": False},
    },
    "smtp": {
        "display_name": "SMTP 邮件",
        "required_keys": [
            "SMTP_SERVER",
            "SMTP_SSL",
            "SMTP_EMAIL",
            "SMTP_PASSWORD",
            "SMTP_NAME",
        ],
        "send_mode": "direct",
        "supports_markdown": False,
        "optional_keys": ["HITOKOTO"],
        "field_mapping": NOTIFY_CHANNEL_ENV_MAPPING["smtp"],
        "field_defaults": {"HITOKOTO": False},
    },
    "wxpusher": {
        "display_name": "WxPusher",
        "required_keys": ["WXPUSHER_APP_TOKEN"],
        "send_mode": "direct",
        "supports_markdown": True,
        "optional_keys": ["WXPUSHER_TOPIC_IDS", "WXPUSHER_UIDS", "HITOKOTO"],
        "field_mapping": NOTIFY_CHANNEL_ENV_MAPPING["wxpusher"],
        "field_defaults": {"HITOKOTO": False},
    },
}


NOTIFY_CHANNEL_SCHEMA = CHANNEL_REGISTRY


DEFAULT_NOTIFY_CONFIG: dict[str, object] = {
    "active_channel": "",
    "channels": {},
}


def _is_empty_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def _as_set(items: Iterable[str]) -> set[str]:
    return {item for item in items}


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in cast(list[object], value):
        if isinstance(item, str):
            result.append(item)
    return result


def _get_channel_spec(channel_id: str) -> dict[str, object]:
    return get_channel_spec(channel_id)


def get_channel_spec(channel_id: str) -> dict[str, object]:
    if channel_id not in CHANNEL_REGISTRY:
        raise ValueError(f"不支持的 channel: {channel_id}")
    return CHANNEL_REGISTRY[channel_id]


def _validate_required_keys(
    channel_id: str, channel_config: Mapping[str, object]
) -> None:
    spec = _get_channel_spec(channel_id)
    required_keys = _as_string_list(spec.get("required_keys"))
    for key in required_keys:
        if key not in channel_config:
            raise ValueError(f"通道 {channel_id} 缺少必填字段: {key}")

        value = channel_config.get(key)
        if key == "CONSOLE":
            if value is not True:
                raise ValueError("通道 console 的 CONSOLE 必须为 true")
            continue

        if _is_empty_value(value):
            raise ValueError(f"通道 {channel_id} 的字段 {key} 不能为空")


def _validate_wxpusher(channel_config: Mapping[str, object]) -> None:
    topic_ids = channel_config.get("WXPUSHER_TOPIC_IDS")
    uids = channel_config.get("WXPUSHER_UIDS")
    if _is_empty_value(topic_ids) and _is_empty_value(uids):
        raise ValueError(
            "通道 wxpusher 需要至少配置 WXPUSHER_TOPIC_IDS 或 WXPUSHER_UIDS"
        )


def _validate_channel_keys(
    channel_id: str, channel_config: Mapping[str, object]
) -> None:
    spec = _get_channel_spec(channel_id)
    required_keys = _as_string_list(spec.get("required_keys"))
    optional_keys = _as_string_list(spec.get("optional_keys"))
    allowed_keys = _as_set(required_keys) | _as_set(optional_keys)

    unknown_keys = [key for key in channel_config if key not in allowed_keys]
    if unknown_keys:
        raise ValueError(f"通道 {channel_id} 包含未定义字段: {', '.join(unknown_keys)}")

    forbidden_keys = [key for key in channel_config if key in FORBIDDEN_BROADCAST_KEYS]
    if forbidden_keys:
        raise ValueError(f"通道 {channel_id} 包含广播字段: {', '.join(forbidden_keys)}")


def validate_notify_config(config: object) -> None:
    if not isinstance(config, Mapping):
        raise TypeError("notify 配置必须是对象")

    typed_config = cast(Mapping[str, object], config)

    if "active_channel" not in typed_config or "channels" not in typed_config:
        raise ValueError("notify 配置必须包含 active_channel 和 channels")

    top_forbidden_keys = [
        key for key in typed_config if key in FORBIDDEN_BROADCAST_KEYS
    ]
    if top_forbidden_keys:
        raise ValueError(f"notify 配置不允许广播字段: {', '.join(top_forbidden_keys)}")

    unknown_top_keys = [
        key for key in typed_config.keys() if key not in DEFAULT_NOTIFY_CONFIG.keys()
    ]
    if unknown_top_keys:
        raise ValueError(
            f"notify 配置包含未定义顶层字段: {', '.join(unknown_top_keys)}"
        )

    active_channel = typed_config.get("active_channel")
    channels = typed_config.get("channels")

    if not isinstance(active_channel, str) or not active_channel.strip():
        raise ValueError("active_channel 必须为非空字符串")

    if active_channel not in NOTIFY_CHANNEL_SCHEMA:
        raise ValueError(f"不支持的 active_channel: {active_channel}")

    if not isinstance(channels, Mapping):
        raise TypeError("channels 必须是对象")

    typed_channels = cast(Mapping[str, object], channels)
    active_config = typed_channels.get(active_channel)
    if not isinstance(active_config, Mapping):
        raise ValueError(f"active_channel={active_channel} 缺少对应的 channel 配置")

    for channel_id, channel_config in typed_channels.items():
        if channel_id not in NOTIFY_CHANNEL_SCHEMA:
            raise ValueError(f"不支持的 channel: {channel_id}")
        if not isinstance(channel_config, Mapping):
            raise TypeError(f"通道 {channel_id} 的配置必须是对象")

        typed_channel_config = cast(Mapping[str, object], channel_config)

        _validate_channel_keys(channel_id, typed_channel_config)
        _validate_required_keys(channel_id, typed_channel_config)

        if channel_id == "wxpusher":
            _validate_wxpusher(typed_channel_config)


NOTIFY_CHANNEL_FUNCTIONS: dict[str, str] = {
    "console": "console",
    "bark": "bark",
    "dingtalk_webhook": "dingding_bot",
    "feishu": "feishu_bot",
    "telegram": "telegram_bot",
    "smtp": "smtp",
    "wxpusher": "wxpusher_bot",
}


def _build_notify_push_config(
    channel_id: str, channel_config: Mapping[str, object]
) -> dict[str, object]:
    spec = get_channel_spec(channel_id)
    merged_config: dict[str, object] = {}

    field_defaults = spec.get("field_defaults")
    if isinstance(field_defaults, Mapping):
        merged_config.update(cast(dict[str, object], field_defaults))

    merged_config.update(dict(channel_config))
    return merged_config


def _get_notify_module() -> object:
    return import_module("services.notify")


def _dispatch_notify_lazy_channel(
    channel_id: str,
    title: str,
    content: str,
    channel_config: Mapping[str, object],
) -> bool:
    notify_module = _get_notify_module()
    function_name = NOTIFY_CHANNEL_FUNCTIONS.get(channel_id)
    if not function_name:
        raise ValueError(f"通道 {channel_id} 未定义发送函数")

    notify_function = getattr(notify_module, function_name, None)
    if not callable(notify_function):
        raise ValueError(f"通道 {channel_id} 的发送函数不存在: {function_name}")

    with _NOTIFY_PUSH_CONFIG_LOCK:
        original_push_config = dict(
            cast(Mapping[str, object], getattr(notify_module, "push_config", {}))
        )
        try:
            setattr(
                notify_module,
                "push_config",
                _build_notify_push_config(channel_id, channel_config),
            )
            typed_notify_function = cast(Callable[[str, str], None], notify_function)
            typed_notify_function(title, content)
            return True
        finally:
            setattr(notify_module, "push_config", original_push_config)


def _dispatch_dingtalk_app_channel(
    title: str,
    content: str,
    channel_config: Mapping[str, object],
) -> bool:
    from services.dingtalk_http_service import DingTalkHTTPService

    adapter_config = {
        "app_key": channel_config.get("app_key"),
        "app_secret": channel_config.get("app_secret"),
        "robot_code": channel_config.get("robot_code"),
        "open_conversation_id": channel_config.get("open_conversation_id"),
    }
    adapter = DingTalkHTTPService(config=adapter_config)
    return adapter.send_message(content=content, title=title, msg_type="markdown")


ADAPTER_DISPATCHERS: dict[str, Callable[[str, str, Mapping[str, object]], bool]] = {
    "dingtalk_app": _dispatch_dingtalk_app_channel,
}


def dispatch_single_channel(
    channel_id: str,
    title: str,
    content: str,
    channel_config: Mapping[str, object],
) -> bool:
    spec = get_channel_spec(channel_id)
    send_mode = spec.get("send_mode")

    if send_mode == "adapter":
        adapter_dispatcher = ADAPTER_DISPATCHERS.get(channel_id)
        if not adapter_dispatcher:
            raise ValueError(f"通道 {channel_id} 尚未实现 adapter 发送")
        return adapter_dispatcher(title, content, channel_config)

    if send_mode == "direct":
        return _dispatch_notify_lazy_channel(channel_id, title, content, channel_config)

    if send_mode == "lazy":
        return _dispatch_notify_lazy_channel(channel_id, title, content, channel_config)

    raise ValueError(f"通道 {channel_id} 的 send_mode 非法: {send_mode}")


class NotifyService:
    """统一通知服务 — 单通道 dispatch 模型"""

    def __init__(self, config: object | None = None) -> None:
        if config is None:
            config = self._load_config_from_db()

        validate_notify_config(config)

        typed_config = cast(Mapping[str, object], config)
        self._active_channel: str = str(typed_config["active_channel"])
        self._channels: Mapping[str, object] = cast(
            Mapping[str, object], typed_config["channels"]
        )
        logger.info(f"NotifyService 初始化完成，激活通道: {self._active_channel}")

    @staticmethod
    def _load_config_from_db() -> dict[str, object]:
        from services.mysql_service import load_config_from_db

        db_config = load_config_from_db("notify")
        if db_config is None:
            raise ValueError(
                "数据库中未找到 notify 配置，请先通过 API 或数据库写入配置"
            )
        return db_config

    def get_active_channel(self) -> str:
        return self._active_channel

    def send(self, title: str, content: str) -> bool:
        channel_id = self._active_channel
        channel_config = self._channels.get(channel_id)
        if not isinstance(channel_config, Mapping):
            logger.error(f"激活通道 {channel_id} 缺少配置，发送中止")
            return False

        try:
            result = dispatch_single_channel(
                channel_id,
                title,
                content,
                cast(Mapping[str, object], channel_config),
            )
            if result:
                logger.info(f"通道 {channel_id} 发送成功")
            else:
                logger.warning(f"通道 {channel_id} 发送失败")
            return result
        except Exception as e:
            logger.error(f"通道 {channel_id} 发送异常: {e}")
            return False

    def send_papers_with_result(
        self, papers: list[dict[str, object]]
    ) -> dict[str, object]:
        from config_loader import MESSAGE_CONFIG
        import time
        import sys

        if not papers:
            logger.info("开始推送 0 篇论文")
            return {
                "success": True,
                "total": 0,
                "success_count": 0,
                "failure_count": 0,
                "successful_dois": [],
            }

        channel_id = self._active_channel
        channel_config = self._channels.get(channel_id)
        if not isinstance(channel_config, Mapping):
            logger.error(f"激活通道 {channel_id} 缺少配置，论文推送中止")
            return {
                "success": False,
                "total": len(papers),
                "success_count": 0,
                "failure_count": len(papers),
                "successful_dois": [],
            }

        channel_spec = get_channel_spec(channel_id)
        supports_markdown = bool(channel_spec.get("supports_markdown", False))
        paper_template = str(MESSAGE_CONFIG["paper_template"])

        total = len(papers)
        success_count = 0
        successful_dois: list[str] = []

        logger.info(f"开始推送 {total} 篇论文")

        for idx, paper in enumerate(papers, 1):
            raw_stars = paper.get("Stars", 0)
            if isinstance(raw_stars, bool):
                stars = int(raw_stars)
            elif isinstance(raw_stars, int | float | str):
                try:
                    stars = int(raw_stars)
                except ValueError:
                    stars = 0
            else:
                stars = 0

            title_cn = str(paper.get("TitleCN") or paper.get("Title") or "无标题")
            abstract_cn = str(
                paper.get("AbstractCN") or paper.get("Abstract") or "暂无摘要"
            )
            author = str(paper.get("Author") or "未知作者")
            affiliation = str(paper.get("Affiliation") or "未提供单位信息")
            publication_year = str(paper.get("PublicationYear") or "未知")
            pdf_link = str(paper.get("PDFLink") or paper.get("Link") or "")
            link = str(paper.get("Link") or "")
            relevance_reason = str(paper.get("RelevanceReason") or "相关论文")
            potential_help = str(paper.get("PotentialHelp") or "可作为研究参考")
            doi = str(paper.get("DOI") or "无DOI")

            message_title = f"📚 论文推送 ({idx}/{total}) - {'⭐' * min(stars, 5)}"
            logger.info(f"发送论文 [{idx}/{total}]: {title_cn}")

            if supports_markdown:
                message_content = paper_template.format(
                    Stars=stars,
                    TitleCN=title_cn,
                    AbstractCN=abstract_cn,
                    Author=author,
                    Affiliation=affiliation,
                    PublicationYear=publication_year,
                    PDFLink=pdf_link,
                    Link=link,
                    RelevanceReason=relevance_reason,
                    PotentialHelp=potential_help,
                    DOI=doi,
                )
            else:
                message_content = (
                    f"📚 {title_cn}\n"
                    f"作者: {author}\n"
                    f"发布: {publication_year}\n"
                    f"摘要: {abstract_cn}\n"
                    f"链接: {link}\n"
                    f"评分: {stars}分/100"
                )

            send_title = message_title
            send_content = message_content
            if channel_id == "console":
                output_encoding = sys.stdout.encoding or "utf-8"
                send_title = send_title.encode(
                    output_encoding, errors="replace"
                ).decode(output_encoding, errors="replace")
                send_content = send_content.encode(
                    output_encoding, errors="replace"
                ).decode(output_encoding, errors="replace")

            send_ok = self.send(send_title, send_content)
            if send_ok:
                logger.info(f"论文发送成功 [{idx}/{total}]: {title_cn}")
                success_count += 1
                raw_doi = paper.get("DOI")
                if raw_doi:
                    successful_dois.append(str(raw_doi))
            else:
                logger.error(f"论文发送失败 [{idx}/{total}]: {title_cn}")

            if idx < total:
                time.sleep(1)

        failure_count = total - success_count
        return {
            "success": failure_count == 0,
            "total": total,
            "success_count": success_count,
            "failure_count": failure_count,
            "successful_dois": successful_dois,
        }

    def send_papers(self, papers: list[dict[str, object]]) -> bool:
        result = self.send_papers_with_result(papers)
        return bool(result.get("success", False))
