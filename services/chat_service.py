"""论文精读对话服务"""

import json
import logging
from typing import Optional, Dict, Any, Generator, List
from openai import OpenAI
import httpx

from services.mysql_service import execute_query, execute_update

logger = logging.getLogger(__name__)

# 上下文窗口限制
MAX_HISTORY_MESSAGES = 20
MAX_MARKDOWN_CONTEXT_CHARS = 8000


class ChatService:
    """论文精读对话服务"""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            from config import LLM_FILTER_CONFIG
            config = LLM_FILTER_CONFIG

        self.config = config
        api_key = str(config.get("api_key", "")).strip()
        base_url = str(config.get("base_url", "")).strip()
        self.model = str(config.get("model", "gpt-3.5-turbo"))

        http_client = httpx.Client(timeout=120.0, follow_redirects=True, proxy=None, trust_env=False)
        kwargs = {"http_client": http_client}
        if api_key:
            kwargs["api_key"] = api_key
        if base_url:
            kwargs["base_url"] = base_url
        self.client = OpenAI(**kwargs)

    def _get_or_create_session(self, doi: str, title: str = "") -> int:
        """获取或创建对话会话（每篇论文一个）"""
        rows = execute_query(
            "SELECT id FROM paper_chat_sessions WHERE doi = %s ORDER BY updated_at DESC LIMIT 1",
            (doi,)
        )
        if rows:
            return rows[0]["id"]

        execute_update(
            "INSERT INTO paper_chat_sessions (doi, title) VALUES (%s, %s)",
            (doi, title or "")
        )
        rows = execute_query(
            "SELECT id FROM paper_chat_sessions WHERE doi = %s ORDER BY id DESC LIMIT 1",
            (doi,)
        )
        return rows[0]["id"] if rows else 0

    def _build_system_prompt(self, paper_context: Dict[str, Any]) -> str:
        """构建系统提示词"""
        from services.prompt_service import get_prompt
        template = get_prompt("chat_system_prompt")

        title = paper_context.get("Title", "")
        title_cn = paper_context.get("TitleCN", "")
        abstract = paper_context.get("Abstract", "")
        abstract_cn = paper_context.get("AbstractCN", "")
        score = paper_context.get("Stars", 0)
        reason = paper_context.get("RelevanceReason", "")

        title_cn_block = f"**中文标题**: {title_cn}" if title_cn else ""
        abstract_cn_block = f"**中文摘要**: {abstract_cn}" if abstract_cn else ""

        return template.replace("{{paper_title}}", title) \
                       .replace("{{paper_title_cn_block}}", title_cn_block) \
                       .replace("{{paper_abstract}}", abstract) \
                       .replace("{{paper_abstract_cn_block}}", abstract_cn_block) \
                       .replace("{{evaluation_score}}", str(score)) \
                       .replace("{{relevance_reason}}", reason)

    def send_message_stream(
        self,
        doi: str,
        user_message: str,
        paper_context: Dict[str, Any]
    ) -> Generator[str, None, None]:
        """发送消息并流式返回 SSE 数据"""
        title = paper_context.get("TitleCN") or paper_context.get("Title", "")
        session_id = self._get_or_create_session(doi, title)

        # 保存用户消息
        execute_update(
            "INSERT INTO paper_chat_messages (session_id, role, content) VALUES (%s, %s, %s)",
            (session_id, "user", user_message)
        )
        # 更新 session 时间戳
        execute_update(
            "UPDATE paper_chat_sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (session_id,)
        )

        # 构建消息列表
        messages = [{"role": "system", "content": self._build_system_prompt(paper_context)}]

        # 如果有 markdown 内容，作为补充 context
        md_content = paper_context.get("markdown_content", "")
        if md_content:
            truncated = md_content[:MAX_MARKDOWN_CONTEXT_CHARS]
            if len(md_content) > MAX_MARKDOWN_CONTEXT_CHARS:
                truncated += "\n\n...(内容过长已截断)"
            messages.append({
                "role": "system",
                "content": f"以下是论文的 Markdown 全文内容供参考：\n\n{truncated}"
            })

        # 加载历史消息
        history = execute_query(
            "SELECT role, content FROM paper_chat_messages "
            "WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
            (session_id, MAX_HISTORY_MESSAGES)
        )
        for msg in reversed(history):
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 流式调用 LLM
        full_response = ""
        try:
            stream = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.7,
                max_tokens=2048,
                stream=True
            )

            for chunk in stream:
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta and delta.content:
                    full_response += delta.content
                    yield f"data: {json.dumps({'content': delta.content}, ensure_ascii=False)}\n\n"

        except Exception as e:
            logger.error(f"❌ LLM 流式调用失败: {e}")
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        # 保存助手回复
        if full_response:
            execute_update(
                "INSERT INTO paper_chat_messages (session_id, role, content) VALUES (%s, %s, %s)",
                (session_id, "assistant", full_response)
            )

        yield "data: [DONE]\n\n"

    def get_chat_history(self, doi: str) -> List[Dict[str, Any]]:
        """获取对话历史"""
        sessions = execute_query(
            "SELECT id FROM paper_chat_sessions WHERE doi = %s ORDER BY updated_at DESC LIMIT 1",
            (doi,)
        )
        if not sessions:
            return []

        session_id = sessions[0]["id"]
        messages = execute_query(
            "SELECT role, content, created_at FROM paper_chat_messages "
            "WHERE session_id = %s ORDER BY created_at ASC",
            (session_id,)
        )
        return messages

    def clear_chat_history(self, doi: str) -> bool:
        """清空对话历史"""
        sessions = execute_query(
            "SELECT id FROM paper_chat_sessions WHERE doi = %s",
            (doi,)
        )
        if not sessions:
            return True

        for session in sessions:
            execute_update(
                "DELETE FROM paper_chat_messages WHERE session_id = %s",
                (session["id"],)
            )
        execute_update("DELETE FROM paper_chat_sessions WHERE doi = %s", (doi,))
        return True

    @staticmethod
    def get_suggestions(paper_data: Dict[str, Any]) -> List[str]:
        """生成推荐问题"""
        title = paper_data.get("TitleCN") or paper_data.get("Title", "这篇论文")
        return [
            "总结这篇论文的核心贡献和创新点",
            "详细解释论文使用的方法论",
            "分析这篇论文的局限性和改进方向",
            "解释论文中的关键公式和数学推导",
            "论文的实验设计有什么亮点和不足？",
        ]
