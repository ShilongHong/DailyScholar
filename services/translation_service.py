"""
论文翻译服务
"""

import json
import re
import logging
from typing import Dict, Any, List, Optional
from openai import OpenAI
import httpx

# 从父目录导入配置
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LLM_FILTER_CONFIG

logger = logging.getLogger(__name__)


class TranslationService:
    """论文翻译服务类"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or LLM_FILTER_CONFIG
        
        # 只提取需要的配置参数
        api_key = self.config.get('api_key')
        base_url = self.config.get('base_url')
        
        # 创建一个明确的 httpx 客户端，不使用代理
        http_client = httpx.Client(
            timeout=60.0,
            follow_redirects=True
        )
        
        # 只传入 OpenAI 客户端明确支持的参数
        client_kwargs = {
            'http_client': http_client
        }
        
        if api_key:
            client_kwargs['api_key'] = api_key
        if base_url:
            client_kwargs['base_url'] = base_url
        
        self.client = OpenAI(**client_kwargs)
        
        self.model = self.config.get('model', 'gpt-3.5-turbo')
        self.temperature = 0.3
        self.max_tokens = 1000
        
        logger.info("TranslationService初始化完成")
    
    def translate_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """翻译论文标题和摘要"""
        try:
            title = paper['Title']
            abstract = paper['Abstract']
            
            prompt = f"""请将以下英文学术论文的标题和摘要翻译成中文。要求：
1. 翻译要准确、流畅、专业
2. 保留专业术语的准确性
3. 格式严格按照JSON输出

英文标题：
{title}

英文摘要：
{abstract}

请只输出JSON格式，不要有其他内容：
{{
  "TitleCN": "中文标题",
  "AbstractCN": "中文摘要"
}}"""
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是一个专业的学术论文翻译专家，擅长将英文论文翻译成准确流畅的中文。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            
            result = self._parse_translation(response.choices[0].message.content)
            
            paper['TitleCN'] = result['TitleCN']
            paper['AbstractCN'] = result['AbstractCN']
            
            logger.debug(f"翻译完成: {result['TitleCN'][:30]}...")
            
            return paper
            
        except Exception as e:
            logger.error(f"翻译论文时出错: {str(e)}")
            paper['TitleCN'] = paper['Title']
            paper['AbstractCN'] = paper['Abstract']
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
            
            if '```json' in response_text:
                start = response_text.find('```json') + 7
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()
            elif '```' in response_text:
                start = response_text.find('```') + 3
                end = response_text.find('```', start)
                response_text = response_text[start:end].strip()
            
            result = json.loads(response_text)
            
            return {
                'TitleCN': result.get('TitleCN', result.get('title_zh', '')).strip(),
                'AbstractCN': result.get('AbstractCN', result.get('abstract_zh', '')).strip()
            }
            
        except json.JSONDecodeError as e:
            logger.warning(f"JSON解析失败: {e}")
            return self._extract_translation_from_text(response_text)
        except Exception as e:
            logger.error(f"解析翻译响应时出错: {e}")
            return {
                'TitleCN': '',
                'AbstractCN': ''
            }
    
    def _extract_translation_from_text(self, text: str) -> Dict[str, str]:
        """从文本中提取翻译"""
        title_cn = ''
        abstract_cn = ''
        
        title_match = re.search(r'["\']?(?:TitleCN|title_zh)["\']?\s*[:：]\s*["\']([^"\']+)["\']', text, re.DOTALL)
        if title_match:
            title_cn = title_match.group(1).strip()
        
        abstract_match = re.search(r'["\']?(?:AbstractCN|abstract_zh)["\']?\s*[:：]\s*["\']([^"\']+)["\']', text, re.DOTALL)
        if abstract_match:
            abstract_cn = abstract_match.group(1).strip()
        
        return {
            'TitleCN': title_cn,
            'AbstractCN': abstract_cn
        }


def translate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """翻译论文的便捷函数"""
    service = TranslationService()
    return service.translate_papers(papers)
