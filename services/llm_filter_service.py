"""
LLM论文筛选服务
"""

import json
import logging
from typing import List, Dict, Any, Optional, Mapping, Match
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI
import httpx

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LLM_FILTER_CONFIG, RESEARCH_DESCRIPTION
from services.prompt_service import get_prompt, get_rendered_prompt

logger = logging.getLogger(__name__)


def get_research_description() -> str:
    """获取研究方向描述（优先使用运行时配置）"""
    try:
        from services.mysql_service import get_all_configs_from_db

        configs = get_all_configs_from_db()
        if configs and "research_description" in configs:
            research_description = configs["research_description"]
            if isinstance(research_description, str):
                return research_description
            if research_description is not None:
                return str(research_description)
    except Exception as e:
        logger.warning(f"从数据库获取研究方向失败: {e}")
    return RESEARCH_DESCRIPTION


class LLMFilterService:
    """LLM论文筛选服务类"""

    def __init__(self, config: Optional[Mapping[str, object]] = None):
        self.config: Mapping[str, object] = config or LLM_FILTER_CONFIG
        self.research_description = get_research_description()

        logger.info(f"LLMFilterService 接收到的配置键: {list(self.config.keys())}")

        api_key_raw = self.config.get("api_key")
        base_url_raw = self.config.get("base_url")
        api_key = api_key_raw if isinstance(api_key_raw, str) else None
        base_url = base_url_raw if isinstance(base_url_raw, str) else None

        http_client = httpx.Client(timeout=60.0, follow_redirects=True)

        if api_key and base_url:
            self.client = OpenAI(
                api_key=api_key, base_url=base_url, http_client=http_client
            )
            logger.info("OpenAI 客户端参数: ['http_client', 'api_key', 'base_url']")
        elif api_key:
            self.client = OpenAI(api_key=api_key, http_client=http_client)
            logger.info("OpenAI 客户端参数: ['http_client', 'api_key']")
        elif base_url:
            self.client = OpenAI(base_url=base_url, http_client=http_client)
            logger.info("OpenAI 客户端参数: ['http_client', 'base_url']")
        else:
            self.client = OpenAI(http_client=http_client)
            logger.info("OpenAI 客户端参数: ['http_client']")

        model_raw = self.config.get("model", "gpt-3.5-turbo")
        self.model = model_raw if isinstance(model_raw, str) else "gpt-3.5-turbo"

        temperature_raw = self.config.get("temperature", 0.1)
        self.temperature = (
            float(temperature_raw) if isinstance(temperature_raw, (int, float)) else 0.1
        )

        max_tokens_raw = self.config.get("max_tokens", 500)
        self.max_tokens = (
            int(max_tokens_raw) if isinstance(max_tokens_raw, (int, float)) else 500
        )

        logger.info("LLMFilterService初始化完成")

    def evaluate_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """评估单篇论文的相关度"""
        max_retries = 3
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                prompt = self._build_evaluation_prompt(paper)

                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": get_prompt("llm_system_prompt")},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                )

                content = response.choices[0].message.content
                raw_content = content or ""
                result = self._parse_response(raw_content)

                if len(raw_content) > 200:
                    debug_preview = raw_content[:200] + "..."
                else:
                    debug_preview = raw_content
                logger.debug(f"LLM响应预览: {debug_preview}")

                logger.debug(
                    f"论文 '{paper['Title'][:50]}...' 评分: {result['score']}分"
                )
                return result

            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(
                        f"LLM评估失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {str(e)}"
                    )
                    import time

                    time.sleep(retry_delay)
                else:
                    logger.error(f"评估论文时出错: {str(e)}")
                    return {
                        "score": 50,
                        "stars": 50,
                        "reason": "评估失败，使用默认评分",
                        "help": "需要进一步人工评估",
                        "raw_response": "",
                    }

        return {
            "score": 50,
            "stars": 50,
            "reason": "评估失败，使用默认评分",
            "help": "需要进一步人工评估",
            "raw_response": "",
        }

    def filter_papers(
        self, papers: List[Dict[str, Any]]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """批量筛选论文，返回 (成功评估的论文列表, 失败的论文列表)"""
        if not papers:
            return [], []

        max_workers_raw = self.config.get("max_workers", 16)
        max_workers = (
            int(max_workers_raw) if isinstance(max_workers_raw, (int, float)) else 16
        )
        logger.info(f"开始LLM筛选，共 {len(papers)} 篇论文，使用 {max_workers} 个线程")

        min_stars_raw = self.config.get("min_stars", 3)
        min_stars = int(min_stars_raw) if isinstance(min_stars_raw, (int, float)) else 3
        filtered_papers = []
        failed_papers = []
        completed_count = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_paper = {
                executor.submit(self.evaluate_paper, paper): paper for paper in papers
            }

            for future in as_completed(future_to_paper):
                paper = future_to_paper[future]
                completed_count += 1

                try:
                    evaluation = future.result()

                    paper["Stars"] = evaluation["stars"]
                    paper["RelevanceReason"] = evaluation["reason"]
                    paper["PotentialHelp"] = evaluation.get("help", "可作为研究参考")

                    if evaluation["score"] == 50 and "评估失败" in evaluation["reason"]:
                        failed_papers.append(paper)
                        logger.warning(
                            f"  [{completed_count}/{len(papers)}] ⚠️ {paper['Title'][:50]}... -> 评估失败，标记为未处理"
                        )
                    else:
                        filtered_papers.append(paper)
                        logger.info(
                            f"  [{completed_count}/{len(papers)}] ✅ {paper['Title'][:50]}... -> {evaluation['score']}分"
                        )

                except Exception as e:
                    logger.error(
                        f"  [{completed_count}/{len(papers)}] ❌ {paper['Title'][:50]}... -> 错误: {str(e)}"
                    )
                    paper["Stars"] = 50
                    paper["RelevanceReason"] = "评估失败，使用默认评分"
                    paper["PotentialHelp"] = "需要进一步人工评估"
                    failed_papers.append(paper)

        filtered_papers.sort(key=lambda x: x["Stars"], reverse=True)

        high_relevance = [p for p in filtered_papers if p["Stars"] >= min_stars]
        logger.info(
            f"筛选完成: {len(high_relevance)}/{len(papers)} 篇论文达到 {min_stars}星及以上"
        )

        return filtered_papers, failed_papers

    def _build_evaluation_prompt(self, paper: Dict[str, Any]) -> str:
        variables = {
            "research_description": self.research_description,
            "paper_title": paper.get("Title", "N/A"),
            "paper_abstract": paper.get("Abstract", "N/A"),
            "scoring_anchors": get_prompt("llm_scoring_anchors"),
            "few_shot_examples": get_prompt("llm_few_shot_examples"),
        }
        return get_rendered_prompt("llm_evaluation_template", variables)

    def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """解析LLM响应"""
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

            cleaned_json = self._clean_json_string(response_text)

            result = json.loads(cleaned_json)

            if "dimensions" in result and "total_score" in result:
                dim_sum = sum(d.get("score", 0) for d in result["dimensions"].values())
                total_score = result.get("total_score", dim_sum)
                if abs(dim_sum - total_score) > 2:
                    total_score = dim_sum

                total_score = max(0, min(100, int(total_score)))

                reason = result.get("reason", "").strip()
                if not reason:
                    reason = f"{total_score}分相关"

                action_items = result.get("action_items", [])
                if action_items and isinstance(action_items, list):
                    help_text = "; ".join(action_items[:3])
                else:
                    help_text = "可作为研究参考"

                return {
                    "score": total_score,
                    "stars": total_score,
                    "reason": reason,
                    "help": help_text,
                    "dimensions": result["dimensions"],
                    "action_items": action_items,
                    "raw_response": response_text,
                }

            elif "score" in result:
                score = int(result.get("score", 50))
                score = max(0, min(100, score))
            elif "stars" in result:
                stars = int(result.get("stars", 3))
                score = stars * 20
            else:
                score = 50

            reason = result.get("reason", "").strip()
            if not reason:
                reason = f"{score}分相关"

            help_text = result.get("help", "").strip()
            if not help_text:
                help_text = "可作为研究参考"

            return {
                "score": score,
                "stars": score,
                "reason": reason,
                "help": help_text,
                "raw_response": response_text,
            }

        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            try:
                cleaned_json = self._clean_json_string(response_text)
                result = json.loads(cleaned_json)
                if "dimensions" in result and "total_score" in result:
                    return self._process_new_format(result, response_text)
                else:
                    return self._process_legacy_format(result, response_text)
            except Exception as clean_error:
                logger.warning(f"清理JSON后仍然解析失败: {clean_error}")
                return self._extract_score_from_text(response_text)
        except Exception as e:
            logger.error(f"解析响应时出错: {e}")
            return {
                "score": 50,
                "stars": 50,
                "reason": "解析失败，使用默认评分",
                "help": "需要进一步人工评估",
                "raw_response": response_text,
            }

    def _clean_json_string(self, json_str: str) -> str:
        """清理和标准化JSON字符串，处理LLM返回的非标准格式"""
        import re

        json_str = re.sub(r"//.*?$", "", json_str, flags=re.MULTILINE)
        json_str = re.sub(r"/\*.*?\*/", "", json_str, flags=re.DOTALL)

        json_str = re.sub(r",\s*([}\]])", r"\1", json_str)

        json_str = re.sub(r"([{,]\s*)\'([^\'\n]+)\'(\s*:)", r'\1"\2"\3', json_str)

        def quote_unquoted_keys(match: Match[str]) -> str:
            return f'{match.group(1)}"{match.group(2)}"{match.group(3)}'

        json_str = re.sub(
            r"(?<!:)([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)(\s*:)",
            quote_unquoted_keys,
            json_str,
        )

        return json_str.strip()

    def _process_new_format(
        self, result: Dict[str, Any], raw_response: str
    ) -> Dict[str, Any]:
        """处理新格式（多维度评分）"""
        dim_sum = sum(d.get("score", 0) for d in result["dimensions"].values())
        total_score = result.get("total_score", dim_sum)
        if abs(dim_sum - total_score) > 2:
            total_score = dim_sum

        total_score = max(0, min(100, int(total_score)))

        reason = result.get("reason", "").strip()
        if not reason:
            reason = f"{total_score}分相关"

        action_items = result.get("action_items", [])
        if action_items and isinstance(action_items, list):
            help_text = "; ".join(action_items[:3])
        else:
            help_text = "可作为研究参考"

        return {
            "score": total_score,
            "stars": total_score,
            "reason": reason,
            "help": help_text,
            "dimensions": result["dimensions"],
            "action_items": action_items,
            "raw_response": raw_response,
        }

    def _process_legacy_format(
        self, result: Dict[str, Any], raw_response: str
    ) -> Dict[str, Any]:
        """处理旧格式（直接的score/stars）"""
        if "score" in result:
            score = int(result.get("score", 50))
        elif "stars" in result:
            stars = int(result.get("stars", 3))
            score = stars * 20
        else:
            score = 50

        score = max(0, min(100, score))

        reason = result.get("reason", "").strip()
        if not reason:
            reason = f"{score}分相关"

        help_text = result.get("help", "").strip()
        if not help_text:
            help_text = "可作为研究参考"

        return {
            "score": score,
            "stars": score,
            "reason": reason,
            "help": help_text,
            "raw_response": raw_response,
        }

    def _extract_score_from_text(self, text: str) -> Dict[str, Any]:
        """从文本中提取分数（降级处理）"""
        import re

        # 尝试提取 total_score
        total_match = re.search(r'["\']?total_score["\']?\s*[:：]\s*(\d{1,3})', text)
        if total_match:
            score = int(total_match.group(1))
            score = max(0, min(100, score))
        else:
            # 尝试提取维度分数并求和
            dim_pattern = r'["\']?(?:problem_relevance|method_transferability|data_resource|technical_depth)["\']?\s*[:：]\s*\{[^}]*["\']?score["\']?\s*[:：]\s*(\d{1,2})'
            dim_scores = re.findall(dim_pattern, text)
            if dim_scores:
                score = sum(min(25, int(s)) for s in dim_scores)
                score = max(0, min(100, score))
            else:
                # 尝试提取普通 score
                score_match = re.search(r'["\']?score["\']?\s*[:：]\s*(\d{1,3})', text)
                if score_match:
                    score = int(score_match.group(1))
                    score = max(0, min(100, score))
                else:
                    score = 50

        reason_match = re.search(
            r'["\']?reason["\']?\s*[:：]\s*["\']([^"\']+)["\']', text
        )
        if reason_match:
            reason = reason_match.group(1).strip()
        else:
            reason = f"{score}分相关"

        return {
            "score": score,
            "stars": score,
            "reason": reason,
            "help": "解析异常，建议人工审查",
            "raw_response": text,
        }


def filter_papers_with_llm(
    papers: List[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """使用LLM筛选论文的便捷函数"""
    service = LLMFilterService()
    return service.filter_papers(papers)
