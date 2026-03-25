import os
import sys
from typing import Dict, Any, List, Optional
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.prompt_service import (
    get_prompt,
    render_template,
)


class PaperRelevanceScorer:
    DIMENSION_WEIGHTS = {
        "problem_relevance": 0.30,
        "method_transferability": 0.30,
        "data_resource": 0.20,
        "technical_depth": 0.20,
    }

    def __init__(
        self,
        research_description: str,
        custom_weights: Optional[Dict[str, float]] = None,
    ):
        self.research_description = research_description
        if custom_weights:
            self.DIMENSION_WEIGHTS.update(custom_weights)

    def _build_evaluation_prompt(self, paper: Dict[str, Any]) -> str:
        variables = {
            "research_description": self.research_description,
            "paper_title": paper.get("Title", "N/A"),
            "paper_abstract": paper.get("Abstract", "N/A"),
            "scoring_anchors": get_prompt("llm_scoring_anchors"),
            "few_shot_examples": get_prompt("llm_few_shot_examples"),
        }
        return render_template(get_prompt("llm_evaluation_template"), variables)

    def _build_batch_evaluation_prompt(self, papers: List[Dict[str, Any]]) -> str:
        papers_text = ""
        for i, paper in enumerate(papers, 1):
            papers_text += f"""
---
**论文{i}**
标题：{paper.get("Title", "N/A")}
摘要：{paper.get("Abstract", "N/A")}
"""

        scoring_anchors = get_prompt("llm_scoring_anchors")
        few_shot_examples = get_prompt("llm_few_shot_examples")

        prompt = f"""你是一位专业的科研论文评审专家。请批量评估以下论文与给定研究方向的相关度。

# 我的研究方向
{self.research_description}

# 待评估论文列表
{papers_text}

{scoring_anchors}

{few_shot_examples}

# 评估任务

对每篇论文，从4个维度评分（每项0-25分）：
1. problem_relevance（问题相关性）
2. method_transferability（方法可迁移性）  
3. data_resource（数据/资源价值）
4. technical_depth（技术深度匹配）

请严格按以下JSON格式输出：

```json
{{
  "evaluations": [
    {{
      "paper_index": 1,
      "dimensions": {{
        "problem_relevance": {{"score": 0-25, "note": "说明"}},
        "method_transferability": {{"score": 0-25, "note": "说明"}},
        "data_resource": {{"score": 0-25, "note": "说明"}},
        "technical_depth": {{"score": 0-25, "note": "说明"}}
      }},
      "total_score": 0-100,
      "reason": "一句话总结",
      "action_items": ["可借鉴内容"]
    }},
    ...
  ]
}}
```

只输出JSON。"""

        return prompt

    def parse_evaluation_result(self, llm_response: str) -> Dict[str, Any]:
        try:
            if "```json" in llm_response:
                json_str = llm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_response:
                json_str = llm_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_response.strip()

            result = json.loads(json_str)

            if "dimensions" not in result or "total_score" not in result:
                raise ValueError("Missing required fields")

            dim_sum = sum(d["score"] for d in result["dimensions"].values())
            if abs(dim_sum - result["total_score"]) > 2:
                result["total_score"] = dim_sum

            return result

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return {
                "error": str(e),
                "raw_response": llm_response,
                "total_score": 0,
                "reason": "解析失败",
            }

    def calibrate_scores(
        self,
        scores: List[Dict[str, Any]],
        target_mean: float = 50,
        target_std: float = 20,
    ) -> List[Dict[str, Any]]:
        if len(scores) < 3:
            return scores

        raw_scores = np.array([s.get("total_score", 0) for s in scores])

        original_mean = np.mean(raw_scores)
        original_std = np.std(raw_scores)

        if original_std < 1:
            original_std = 1

        calibrated_scores = (raw_scores - original_mean) / original_std
        calibrated_scores = calibrated_scores * target_std + target_mean

        calibrated_scores = np.clip(calibrated_scores, 0, 100).astype(int)

        for i, score_dict in enumerate(scores):
            score_dict["original_score"] = int(raw_scores[i])
            score_dict["calibrated_score"] = int(calibrated_scores[i])
            score_dict["total_score"] = int(calibrated_scores[i])

        return scores

    def get_priority_papers(
        self,
        evaluated_papers: List[Dict[str, Any]],
        threshold: int = 60,
        top_k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        sorted_papers = sorted(
            evaluated_papers, key=lambda x: x.get("total_score", 0), reverse=True
        )

        filtered = [p for p in sorted_papers if p.get("total_score", 0) >= threshold]

        if top_k:
            filtered = filtered[:top_k]

        return filtered


if __name__ == "__main__":
    research_desc = """
    我的研究方向是：多模态科学文献数据基座构建
    
    核心问题：
    1. 科学文献中图表（chart/figure）的自动解析与数据提取
    2. Chart-to-Table/Chart-to-JSON 转换方法
    3. 科学文档的跨模态信息抽取与知识图谱构建
    4. 材料科学领域的文献智能处理
    
    技术栈：多模态大语言模型、视觉-语言理解、文档布局分析、OCR、曲线检测
    """

    scorer = PaperRelevanceScorer(research_desc)

    sample_paper = {
        "Title": "ChartReader: A Unified Framework for Chart Information Extraction",
        "Abstract": "We present ChartReader, a unified framework for extracting structured data from various types of charts...",
        "Keywords": "chart understanding, information extraction, multimodal",
        "Year": "2024",
    }

    prompt = scorer._build_evaluation_prompt(sample_paper)
    print("=" * 60)
    print("生成的评估Prompt:")
    print("=" * 60)
    print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)

    mock_llm_response = """```json
{
  "dimensions": {
    "problem_relevance": {"score": 24, "note": "直接解决图表信息提取问题"},
    "method_transferability": {"score": 22, "note": "统一框架可直接应用"},
    "data_resource": {"score": 18, "note": "可能提供数据集"},
    "technical_depth": {"score": 21, "note": "技术深度匹配"}
  },
  "total_score": 85,
  "reason": "高度相关的图表理解研究",
  "action_items": ["复现其统一框架", "对比实验基准"]
}
```"""

    result = scorer.parse_evaluation_result(mock_llm_response)
    print("\n" + "=" * 60)
    print("解析后的评估结果:")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
