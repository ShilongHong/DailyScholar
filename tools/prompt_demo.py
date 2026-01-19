"""
论文相关度评分器 - 改进版
用于评估论文与研究方向的相关程度

改进点：
1. 多维度评分（问题相关性、方法可迁移性、数据资源价值、技术深度匹配）
2. Few-shot示例提升评分一致性
3. 关键词锚点辅助评分
4. 批量评分校准机制
"""

import os
import sys
from typing import Dict, Any, List, Optional
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PaperRelevanceScorer:
    """论文相关度评分器"""

    # 评分维度权重（可根据需求调整）
    DIMENSION_WEIGHTS = {
        "problem_relevance": 0.30,  # 问题相关性
        "method_transferability": 0.30,  # 方法可迁移性
        "data_resource": 0.20,  # 数据/资源价值
        "technical_depth": 0.20,  # 技术深度匹配
    }

    # Few-shot 示例
    FEW_SHOT_EXAMPLES = """
## 评分示例

### 示例1（高分论文）
标题：ChartLlama: A Multimodal LLM for Chart Understanding and Generation
摘要：We present ChartLlama, a multi-modal large language model for chart understanding...

评估结果：
```json
{
  "dimensions": {
    "problem_relevance": {"score": 24, "note": "直接解决图表理解核心问题"},
    "method_transferability": {"score": 23, "note": "多模态LLM方法可直接应用"},
    "data_resource": {"score": 20, "note": "提供图表理解数据集"},
    "technical_depth": {"score": 22, "note": "技术栈高度匹配"}
  },
  "total_score": 89,
  "reason": "直接解决图表理解核心问题，方法和数据均可借鉴",
  "action_items": ["复现其图表解析pipeline", "使用其数据集做基准测试"]
}
```

### 示例2（中等分数论文）
标题：DocParser: End-to-end Document Parsing with Transformers
摘要：We propose DocParser for structured document understanding using vision transformers...

评估结果：
```json
{
  "dimensions": {
    "problem_relevance": {"score": 18, "note": "文档解析相关，但非图表专用"},
    "method_transferability": {"score": 16, "note": "Transformer架构可参考，需适配"},
    "data_resource": {"score": 12, "note": "通用文档数据，需筛选科学文献"},
    "technical_depth": {"score": 15, "note": "技术深度适中"}
  },
  "total_score": 61,
  "reason": "文档解析方法可参考，但需针对科学图表场景改造",
  "action_items": ["参考其layout理解模块"]
}
```

### 示例3（低分论文）
标题：A Survey of Sentiment Analysis in Social Media
摘要：This survey reviews sentiment analysis methods for Twitter and social media platforms...

评估结果：
```json
{
  "dimensions": {
    "problem_relevance": {"score": 3, "note": "情感分析与科学文献IE无关"},
    "method_transferability": {"score": 5, "note": "NLP基础方法有微弱参考性"},
    "data_resource": {"score": 2, "note": "社交媒体数据不适用"},
    "technical_depth": {"score": 4, "note": "研究深度方向不匹配"}
  },
  "total_score": 14,
  "reason": "研究方向不相关，无直接参考价值",
  "action_items": []
}
```
"""

    # 评分锚点关键词
    SCORING_ANCHORS = """
## 评分参考锚点

### 高分信号（每项可得20-25分）
**问题相关关键词**：chart understanding, table extraction, figure parsing, scientific document, 
materials science, multimodal information extraction, knowledge graph construction, 
chart-to-table, formula recognition, scientific literature mining

**方法相关关键词**：vision-language model, multimodal LLM, document layout analysis, 
OCR, curve detection, data extraction, end-to-end parsing

**数据/资源关键词**：chart dataset, scientific figure benchmark, materials database, 
open-source implementation, reproducible

### 中等分数信号（每项10-19分）
- 通用多模态方法（需要适配才能用于科学图表）
- 相邻领域（如医学图像分析、通用文档理解）
- 基础技术组件（如目标检测、OCR改进）

### 低分信号（每项0-9分）
- 纯文本NLP任务（无视觉/多模态成分）
- 不相关领域（社交媒体、推荐系统、语音等）
- 过时方法（2019年前的非深度学习方法，除非是经典基准）
- 纯理论工作（无实验验证或实际应用）
"""

    def __init__(
        self,
        research_description: str,
        custom_weights: Optional[Dict[str, float]] = None,
    ):
        """
        初始化评分器

        Args:
            research_description: 研究方向描述
            custom_weights: 自定义维度权重（可选）
        """
        self.research_description = research_description
        if custom_weights:
            self.DIMENSION_WEIGHTS.update(custom_weights)

    def _build_evaluation_prompt(self, paper: Dict[str, Any]) -> str:
        """构建评估提示词"""

        prompt = f"""你是一位专业的科研论文评审专家。请评估以下论文与给定研究方向的相关度。

# 我的研究方向
{self.research_description}

# 待评估论文
**标题**：{paper.get("Title", "N/A")}
**摘要**：{paper.get("Abstract", "N/A")}
**关键词**：{paper.get("Keywords", "N/A")}
**发表年份**：{paper.get("Year", "N/A")}

{self.SCORING_ANCHORS}

{self.FEW_SHOT_EXAMPLES}

# 评估任务

请从以下4个维度分别评分（每项0-25分），然后计算总分：

1. **problem_relevance（问题相关性）**：论文解决的问题与我的研究问题是否相关
2. **method_transferability（方法可迁移性）**：论文方法是否可直接借鉴或改造应用到我的研究
3. **data_resource（数据/资源价值）**：论文是否提供可用的数据集、代码、基准测试
4. **technical_depth（技术深度匹配）**：技术栈和研究深度是否与我的研究匹配

请严格按以下JSON格式输出（不要有其他内容）：

```json
{{
  "dimensions": {{
    "problem_relevance": {{"score": 0-25, "note": "一句话说明"}},
    "method_transferability": {{"score": 0-25, "note": "一句话说明"}},
    "data_resource": {{"score": 0-25, "note": "一句话说明"}},
    "technical_depth": {{"score": 0-25, "note": "一句话说明"}}
  }},
  "total_score": 四项之和（0-100）,
  "reason": "一句话总结相关性（20字以内）",
  "action_items": ["具体可借鉴的内容1", "具体可借鉴的内容2"]
}}
```

评分区间参考：
- 80-100分：高度相关，必读论文
- 60-79分：较相关，值得阅读
- 40-59分：弱相关，可选择性浏览
- 0-39分：不相关，可跳过

只输出JSON，不要有任何其他文字。"""

        return prompt

    def _build_batch_evaluation_prompt(self, papers: List[Dict[str, Any]]) -> str:
        """构建批量评估提示词（适用于一次评估多篇论文）"""

        papers_text = ""
        for i, paper in enumerate(papers, 1):
            papers_text += f"""
---
**论文{i}**
标题：{paper.get("Title", "N/A")}
摘要：{paper.get("Abstract", "N/A")}
"""

        prompt = f"""你是一位专业的科研论文评审专家。请批量评估以下论文与给定研究方向的相关度。

# 我的研究方向
{self.research_description}

# 待评估论文列表
{papers_text}

{self.SCORING_ANCHORS}

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
        """
        解析LLM返回的评估结果

        Args:
            llm_response: LLM的原始响应文本

        Returns:
            解析后的评估结果字典
        """
        # 尝试提取JSON部分
        try:
            # 处理可能的markdown代码块
            if "```json" in llm_response:
                json_str = llm_response.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_response:
                json_str = llm_response.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_response.strip()

            result = json.loads(json_str)

            # 验证必要字段
            if "dimensions" not in result or "total_score" not in result:
                raise ValueError("Missing required fields")

            # 验证总分计算
            dim_sum = sum(d["score"] for d in result["dimensions"].values())
            if abs(dim_sum - result["total_score"]) > 2:  # 允许小误差
                result["total_score"] = dim_sum  # 修正总分

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
        """
        对一批评分进行校准，避免分数集中在某个区间

        Args:
            scores: 评估结果列表
            target_mean: 目标均值
            target_std: 目标标准差

        Returns:
            校准后的评估结果列表
        """
        if len(scores) < 3:
            return scores  # 样本太少，不做校准

        # 提取原始分数
        raw_scores = np.array([s.get("total_score", 0) for s in scores])

        # 计算原始统计量
        original_mean = np.mean(raw_scores)
        original_std = np.std(raw_scores)

        if original_std < 1:  # 避免除零
            original_std = 1

        # Z-score标准化后重映射
        calibrated_scores = (raw_scores - original_mean) / original_std
        calibrated_scores = calibrated_scores * target_std + target_mean

        # 截断到0-100范围
        calibrated_scores = np.clip(calibrated_scores, 0, 100).astype(int)

        # 更新结果
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
        """
        筛选高优先级论文

        Args:
            evaluated_papers: 已评估的论文列表（包含评分）
            threshold: 分数阈值
            top_k: 返回top k篇（可选）

        Returns:
            筛选后的论文列表
        """
        # 按分数排序
        sorted_papers = sorted(
            evaluated_papers, key=lambda x: x.get("total_score", 0), reverse=True
        )

        # 应用阈值筛选
        filtered = [p for p in sorted_papers if p.get("total_score", 0) >= threshold]

        # 应用top_k限制
        if top_k:
            filtered = filtered[:top_k]

        return filtered


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 定义研究方向
    research_desc = """
    我的研究方向是：多模态科学文献数据基座构建
    
    核心问题：
    1. 科学文献中图表（chart/figure）的自动解析与数据提取
    2. Chart-to-Table/Chart-to-JSON 转换方法
    3. 科学文档的跨模态信息抽取与知识图谱构建
    4. 材料科学领域的文献智能处理
    
    技术栈：多模态大语言模型、视觉-语言理解、文档布局分析、OCR、曲线检测
    """

    # 初始化评分器
    scorer = PaperRelevanceScorer(research_desc)

    # 示例论文
    sample_paper = {
        "Title": "ChartReader: A Unified Framework for Chart Information Extraction",
        "Abstract": "We present ChartReader, a unified framework for extracting structured data from various types of charts...",
        "Keywords": "chart understanding, information extraction, multimodal",
        "Year": "2024",
    }

    # 生成评估prompt
    prompt = scorer._build_evaluation_prompt(sample_paper)
    print("=" * 60)
    print("生成的评估Prompt:")
    print("=" * 60)
    print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)

    # 模拟LLM返回结果
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

    # 解析结果
    result = scorer.parse_evaluation_result(mock_llm_response)
    print("\n" + "=" * 60)
    print("解析后的评估结果:")
    print("=" * 60)
    print(json.dumps(result, indent=2, ensure_ascii=False))
