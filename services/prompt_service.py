import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

DEFAULT_PROMPT_CONFIG = {
    "llm_system_prompt": "你是一个学术论文评估专家，需要评估论文与给定研究方向的相关度。请使用100分制评分。",
    "llm_few_shot_examples": """## 评分示例

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
```""",
    "llm_scoring_anchors": """## 评分参考锚点

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
- 纯理论工作（无实验验证或实际应用）""",
    "llm_evaluation_template": """你是一位专业的科研论文评审专家。请评估以下论文与给定研究方向的相关度。

# 我的研究方向
{{research_description}}

# 待评估论文
**标题**：{{paper_title}}
**摘要**：{{paper_abstract}}

{{scoring_anchors}}

{{few_shot_examples}}

# 评估任务

请从以下4个维度分别评分（每项0-25分），然后计算总分：

1. **problem_relevance（问题相关性）**：论文解决的问题与我的研究问题是否相关
2. **method_transferability（方法可迁移性）**：论文方法是否可直接借鉴或改造应用到我的研究
3. **data_resource（数据/资源价值）**：论文是否提供可用的数据集、代码、基准测试
4. **technical_depth（技术深度匹配）**：技术栈和研究深度是否与我的研究匹配

请严格按以下JSON格式输出（不要有其他内容）：

**重要格式要求**：
- 所有键名必须用双引号包裹（例如："total_score"）
- 所有字符串值必须用双引号包裹（例如："reason"）
- 不要使用单引号，不要使用无引号的键名
- 不要添加注释（// 或 /* */）
- 尾部不要有多余的逗号

```json
{
  "dimensions": {
    "problem_relevance": {"score": 0-25, "note": "一句话说明"},
    "method_transferability": {"score": 0-25, "note": "一句话说明"},
    "data_resource": {"score": 0-25, "note": "一句话说明"},
    "technical_depth": {"score": 0-25, "note": "一句话说明"}
  },
  "total_score": 四项之和（0-100）,
  "reason": "一句话总结相关性（20字以内）",
  "action_items": ["具体可借鉴的内容1", "具体可借鉴的内容2"]
}
```

评分区间参考：
- 80-100分：高度相关，必读论文
- 60-79分：较相关，值得阅读
- 40-59分：弱相关，可选择性浏览
- 0-39分：不相关，可跳过

只输出JSON，不要有任何其他文字。""",
    "chat_system_prompt": """你是一位专业的学术论文精读助手，帮助用户深入理解论文。

# 论文信息
**标题**: {{paper_title}}
{{paper_title_cn_block}}
**摘要**: {{paper_abstract}}
{{paper_abstract_cn_block}}
**相关度评分**: {{evaluation_score}}/100
**推荐理由**: {{relevance_reason}}

# 你的能力
1. 总结论文核心贡献和创新点
2. 详细解释方法论和技术细节
3. 分析局限性和改进方向
4. 与相关领域工作进行比较
5. 解释关键公式和数学推导
6. 分析实验设计和结果

# 输出要求
- 使用 Markdown 格式回复
- 数学公式使用 LaTeX 语法（行内用 $...$，独立公式用 $$...$$）
- 回答要准确、专业、有条理
- 不确定的内容诚实说明""",
    "translation_system_prompt": "你是一个专业的学术论文翻译专家，擅长将英文论文翻译成准确流畅的中文。",
    "translation_template": """请将以下英文学术论文的标题和摘要翻译成中文。要求：
1. 翻译要准确、流畅、专业
2. 保留专业术语的准确性
3. 格式严格按照JSON输出

英文标题：
{{title}}

英文摘要：
{{abstract}}

请只输出JSON格式，不要有其他内容：
{
  "TitleCN": "中文标题",
  "AbstractCN": "中文摘要"
}""",
}


def get_prompt(key: str) -> str:
    try:
        from services.mysql_service import load_config_from_db

        db_config = load_config_from_db("prompt_config")

        if (
            db_config
            and isinstance(db_config, dict)
            and key in db_config
            and db_config[key]
        ):
            return db_config[key]
    except Exception as e:
        logger.warning(f"从数据库加载 prompt_config 失败: {e}，使用本地默认值")

    default = DEFAULT_PROMPT_CONFIG.get(key, "")
    if not default:
        logger.warning(f"未知的提示词key: {key}")
    return default


def render_template(template: str, variables: Dict[str, Any]) -> str:
    result = template
    for key, value in variables.items():
        result = result.replace(f"{{{{{key}}}}}", str(value))
    return result


def get_rendered_prompt(template_key: str, variables: Dict[str, Any]) -> str:
    template = get_prompt(template_key)
    return render_template(template, variables)
