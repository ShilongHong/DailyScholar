"""本地配置示例。

如需用文件覆盖默认配置，复制本文件为 config.py 并填入真实密钥。
config.py 已被 .gitignore 忽略，请不要提交真实密钥。
"""

from config_defaults import (  # noqa: F401
    ARXIV_CONFIG,
    DINGTALK_CONFIG,
    LLM_FILTER_CONFIG,
    LOGGING_CONFIG,
    MESSAGE_CONFIG,
    MINERU_CONFIG,
    OUTPUT_CONFIG,
    RESEARCH_DESCRIPTION,
    SCHEDULE_CONFIG,
)

# 示例：覆盖 LLM 配置
# LLM_FILTER_CONFIG.update({
#     "api_key": "sk-...",
#     "base_url": "https://api.openai.com/v1",
#     "model": "gpt-4o-mini",
# })

# 示例：切换到 MySQL
# ARXIV_CONFIG["mysql"].update({
#     "db_type": "mysql",
#     "host": "localhost",
#     "port": 3306,
#     "user": "root",
#     "password": "your-password",
#     "database": "arxiv_papers",
# })