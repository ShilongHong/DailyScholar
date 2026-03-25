"""
论文翻译服务
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional, Mapping
from openai import OpenAI
import httpx

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LLM_FILTER_CONFIG
from services.prompt_service import get_prompt, get_rendered_prompt

logger = logging.getLogger(__name__)


class TranslationService:
    """论文翻译服务类"""

    def __init__(self, config: Optional[Mapping[str, object]] = None):
        self.config: Mapping[str, object] = config or LLM_FILTER_CONFIG

        api_key_raw = self.config.get("api_key")
        base_url_raw = self.config.get("base_url")
        api_key = api_key_raw if isinstance(api_key_raw, str) else None
        base_url = base_url_raw if isinstance(base_url_raw, str) else None

        http_client = httpx.Client(timeout=60.0, follow_redirects=True)

        if api_key and base_url:
            self.client = OpenAI(
                api_key=api_key, base_url=base_url, http_client=http_client
            )
        elif api_key:
            self.client = OpenAI(api_key=api_key, http_client=http_client)
        elif base_url:
            self.client = OpenAI(base_url=base_url, http_client=http_client)
        else:
            self.client = OpenAI(http_client=http_client)

        model_raw = self.config.get("model", "gpt-3.5-turbo")
        self.model = model_raw if isinstance(model_raw, str) else "gpt-3.5-turbo"

        temperature_raw = self.config.get("translation_temperature", 0.3)
        self.temperature = (
            float(temperature_raw) if isinstance(temperature_raw, (int, float)) else 0.3
        )

        max_tokens_raw = self.config.get("translation_max_tokens", 4096)
        self.max_tokens = (
            int(max_tokens_raw) if isinstance(max_tokens_raw, (int, float)) else 4096
        )

        logger.info("TranslationService初始化完成")

    def translate_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """翻译论文标题和摘要"""
        try:
            title = paper["Title"]
            abstract = paper["Abstract"]

            variables = {"title": title, "abstract": abstract}
            prompt = get_rendered_prompt("translation_template", variables)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": get_prompt("translation_system_prompt"),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content
            result = self._parse_translation(content or "")

            paper["TitleCN"] = result["TitleCN"]
            paper["AbstractCN"] = result["AbstractCN"]

            logger.debug(f"翻译完成: {result['TitleCN'][:30]}...")

            return paper

        except Exception as e:
            logger.error(f"翻译论文时出错: {str(e)}")
            paper["TitleCN"] = paper["Title"]
            paper["AbstractCN"] = paper["Abstract"]
            return paper

    def translate_papers(self, papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量翻译论文"""
        if not papers:
            return []

        logger.info(f"开始翻译，共 {len(papers)} 篇论文")

        translated_papers = []
        for idx, paper in enumerate(papers, 1):
            logger.info(f"  [{idx}/{len(papers)}] 翻译: {paper['Title'][:50]}...")
            translated_paper = self.translate_paper(paper)
            translated_papers.append(translated_paper)

        logger.info("翻译完成")
        return translated_papers

    def _parse_translation(self, response_text: str) -> Dict[str, str]:
        """解析翻译响应"""
        try:
            response_text = response_text.strip()

            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                response_text = response_text[start:end].strip()

            result = json.loads(response_text)

            return {
                "TitleCN": result.get("TitleCN", result.get("title_zh", "")).strip(),
                "AbstractCN": result.get(
                    "AbstractCN", result.get("abstract_zh", "")
                ).strip(),
            }

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return self._extract_translation_from_text(response_text)
        except Exception as e:
            logger.error(f"解析翻译响应时出错: {e}")
            return {"TitleCN": "", "AbstractCN": ""}

    def _extract_translation_from_text(self, text: str) -> Dict[str, str]:
        """从文本中提取翻译"""
        title_cn = ""
        abstract_cn = ""

        title_match = re.search(
            r'["\']?(?:TitleCN|title_zh)["\']?\s*[:：]\s*["\']([^"\']+)["\']',
            text,
            re.DOTALL,
        )
        if title_match:
            title_cn = title_match.group(1).strip()

        abstract_match = re.search(
            r'["\']?(?:AbstractCN|abstract_zh)["\']?\s*[:：]\s*["\']([^"\']+)["\']',
            text,
            re.DOTALL,
        )
        if abstract_match:
            abstract_cn = abstract_match.group(1).strip()

        return {"TitleCN": title_cn, "AbstractCN": abstract_cn}


def translate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """翻译论文的便捷函数"""
    service = TranslationService()
    return service.translate_papers(papers)
