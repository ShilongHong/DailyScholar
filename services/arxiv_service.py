"""
arXiv论文获取服务
"""

import feedparser
import requests
import time
import csv
import os
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import quote
from datetime import datetime, timedelta
import pytz

# 从父目录导入配置
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import ARXIV_CONFIG, OUTPUT_CONFIG, SCHEDULE_CONFIG

# 尝试导入MySQL服务
try:
    from .mysql_service import is_paper_processed, is_mysql_enabled, save_raw_papers_to_mysql
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False

logger = logging.getLogger(__name__)


class ArxivService:
    """arXiv论文获取服务类"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or ARXIV_CONFIG
        self.api_url = self.config['api_url']
        self.batch_size = self.config['batch_size']
        self.request_delay = self.config['request_delay']
        self.max_results_per_keyword = self.config['max_results_per_keyword']
        
        self.consecutive_duplicate_threshold = self.config.get('consecutive_duplicate_threshold', 100)
        
        self.enable_duplicate_check = MYSQL_AVAILABLE and is_mysql_enabled()
        if self.enable_duplicate_check:
            logger.info(f"  已启用实时DOI去重检测")
        
        eastern = pytz.timezone('US/Eastern')
        now_eastern = datetime.now(eastern)
        
        # 根据配置的 recent_days 动态生成日期范围
        self.recent_days = self.config.get('recent_days', 3)
        self.target_dates = []
        for i in range(self.recent_days):
            date = (now_eastern - timedelta(days=i)).strftime('%Y-%m-%d')
            self.target_dates.append(date)
        
        self.today = self.target_dates[0]
        self.oldest_date = self.target_dates[-1]
        
        logger.info(f"ArxivService初始化完成")
        logger.info(f"  当前arXiv时间: {now_eastern.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info(f"  筛选日期范围: 最近 {self.recent_days} 天 ({self.oldest_date} ~ {self.today})")
    
    def search_papers(self, keywords: Optional[List[str]] = None, batch_callback=None) -> List[Dict[str, Any]]:
        """根据关键词搜索论文
        
        Args:
            keywords: 关键词列表
            batch_callback: 每获取一批论文后的回调函数 callback(papers_batch)
        """
        keywords = keywords or self.config['keywords']
        all_papers = []
        seen_ids = set()
        
        logger.info(f"开始搜索，共 {len(keywords)} 个关键词")
        
        for idx, keyword in enumerate(keywords, 1):
            logger.info(f"[{idx}/{len(keywords)}] 搜索关键词: {keyword}")
            
            try:
                papers = self._search_by_keyword(keyword, batch_callback=batch_callback)
                
                for paper in papers:
                    if paper['DOI'] not in seen_ids:
                        all_papers.append(paper)
                        seen_ids.add(paper['DOI'])
                
                logger.info(f"  找到 {len(papers)} 篇论文，当前总数: {len(all_papers)}")
                
            except Exception as e:
                logger.error(f"搜索关键词 '{keyword}' 时出错: {str(e)}")
                continue
        
        logger.info(f"搜索完成，共获取 {len(all_papers)} 篇不重复的论文")
        return all_papers
    
    def _search_by_keyword(self, keyword: str, batch_callback=None) -> List[Dict[str, Any]]:
        """根据单个关键词搜索论文
        
        Args:
            keyword: 搜索关键词
            batch_callback: 每获取一批论文后的回调函数 callback(papers_batch)
        """
        # 判断是分类代码还是普通关键词
        if keyword.startswith('cat:') or '.' in keyword and keyword.split('.')[0] in ['cs', 'math', 'physics', 'eess', 'q-bio', 'q-fin', 'stat']:
            # arXiv 分类代码 (如 cs.CL, cs.CV)
            if not keyword.startswith('cat:'):
                encoded_query = quote(f'cat:{keyword}')
            else:
                encoded_query = quote(keyword)
        else:
            # 普通关键词搜索
            encoded_query = quote(f'all:"{keyword}"')
        
        all_papers = []
        start = 0
        total_results = None
        max_results = self.max_results_per_keyword
        consecutive_duplicates = 0
        
        while True:
            batch = min(self.batch_size, max_results - start) if max_results else self.batch_size
            url = f"{self.api_url}?search_query={encoded_query}&start={start}&max_results={batch}&sortBy=submittedDate&sortOrder=descending"
            
            time.sleep(self.request_delay)
            
            max_retries = 3
            retry_delay = 5
            feed = None
            
            # 使用 requests 先获取内容，避免 SSL 证书问题
            for attempt in range(max_retries):
                try:
                    # 先用 requests 获取 XML 内容
                    headers = {
                        'User-Agent': 'Mozilla/5.0 (compatible; ArxivPaperBot/1.0)',
                        'Accept': 'application/atom+xml',
                    }
                    response = requests.get(url, headers=headers, timeout=15)
                    response.raise_for_status()
                    
                    # 将获取的内容传给 feedparser 解析
                    feed = feedparser.parse(response.content)
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(f"  API请求失败（尝试 {attempt + 1}/{max_retries}），{retry_delay}秒后重试: {str(e)}")
                        time.sleep(retry_delay)
                    else:
                        logger.error(f"  API请求失败，已达最大重试次数: {str(e)}")
                        return all_papers
            
            if feed is None:
                return all_papers
            
            if total_results is None:
                total_results = int(feed.feed.get('opensearch_totalresults', 0))
                logger.info(f"  关键词 '{keyword}' 共有 {total_results} 篇相关论文")
            
            if not feed.entries:
                break
            
            batch_papers = 0
            found_older = False
            stop_due_to_duplicates = False
            
            for entry in feed.entries:
                paper = self._extract_metadata(entry, keyword)
                paper_date = paper['PublicationYear']
                paper_doi = paper['DOI']
                
                if paper_date in self.target_dates:
                    if self.enable_duplicate_check and paper_doi and is_paper_processed(paper_doi, table='papers_raw'):
                        consecutive_duplicates += 1
                        if consecutive_duplicates >= self.consecutive_duplicate_threshold:
                            logger.info(f"  [STOP] 连续 {consecutive_duplicates} 篇已检索，停止当前关键词搜索")
                            stop_due_to_duplicates = True
                            break
                    else:
                        consecutive_duplicates = 0
                        all_papers.append(paper)
                        batch_papers += 1
                elif paper_date < self.oldest_date:
                    found_older = True
                    break
            
            start += len(feed.entries)
            logger.info(f"  第 {start//batch} 批：找到 {batch_papers} 篇新论文，累计 {len(all_papers)} 篇")
            
            # 立即保存这批新论文到raw数据库
            if batch_papers > 0:
                batch_to_save = all_papers[-batch_papers:]
                if MYSQL_AVAILABLE:
                    save_raw_papers_to_mysql(batch_to_save)
                    logger.info(f"  ✅ 已保存 {batch_papers} 篇论文到raw数据库")
            
            # 如果有回调函数且这批有新论文，立即处理
            if batch_callback and batch_papers > 0:
                # 取出这批新添加的论文
                batch_to_process = all_papers[-batch_papers:]
                batch_callback(batch_to_process)
            
            if stop_due_to_duplicates or found_older:
                break
            
            if max_results and len(all_papers) >= max_results:
                break
            if start >= total_results:
                break
        
        return all_papers
    
    def _extract_metadata(self, entry: Any, keyword: str) -> Dict[str, Any]:
        """提取论文元数据"""
        arxiv_id = entry.id.split('/abs/')[-1]
        
        authors = []
        affiliations = []
        for author in entry.authors:
            authors.append(author.name)
            if hasattr(author, 'affiliation') and author.affiliation:
                affiliations.append(author.affiliation)
        
        authors_str = ', '.join(authors)
        affiliations_str = '; '.join(affiliations) if affiliations else '未提供单位信息'
        published_date = entry.published.split('T')[0]
        abstract = ' '.join(entry.summary.split())
        pdf_link = entry.link.replace('/abs/', '/pdf/') + '.pdf'
        
        return {
            'DOI': arxiv_id,
            'Title': entry.title,
            'Author': authors_str,
            'Affiliation': affiliations_str,
            'PublicationYear': published_date,
            'Abstract': abstract,
            'Link': entry.link,
            'PDFLink': pdf_link,
            'Source': keyword,
            'SubjectTerms': ', '.join([tag.term for tag in entry.tags]),
        }
    
    def save_to_csv(self, papers: List[Dict[str, Any]], filename: Optional[str] = None, prefix: str = '') -> str:
        """保存论文列表到CSV文件"""
        if not papers:
            logger.warning("没有论文可保存")
            return ""
        
        if not filename:
            date_str = datetime.now().strftime('%Y%m%d')
            filename = OUTPUT_CONFIG['filename_format'].format(date=date_str)
            if prefix:
                filename = f"{prefix}{filename}"
        
        output_dir = OUTPUT_CONFIG['output_dir']
        os.makedirs(output_dir, exist_ok=True)
        filepath = os.path.join(output_dir, filename)
        
        fieldnames = ['DOI', 'Title', 'Author', 'Affiliation', 'PublicationYear', 'Abstract', 'Link', 'PDFLink', 'Source', 'SubjectTerms']
        
        if papers and 'TitleCN' in papers[0]:
            fieldnames.extend(['TitleCN', 'AbstractCN', 'Stars', 'RelevanceReason', 'PotentialHelp'])
        
        try:
            file_exists = os.path.exists(filepath)
            mode = 'a' if file_exists else 'w'
            
            existing_dois = set()
            if file_exists:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        existing_dois = {row.get('DOI', '') for row in reader if row.get('DOI')}
                except Exception:
                    mode = 'w'
                    existing_dois = set()
            
            new_papers = [p for p in papers if p.get('DOI', '') not in existing_dois]
            
            if not new_papers and file_exists:
                logger.info(f"所有论文已在文件中: {filepath}")
                return filepath
            
            with open(filepath, mode, newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
                if not file_exists:
                    writer.writeheader()
                writer.writerows(new_papers)
            
            action = '追加' if file_exists else '保存'
            logger.info(f"论文列表已{action}到: {filepath} ({len(new_papers)} 篇)")
            return filepath
            
        except Exception as e:
            logger.error(f"保存CSV文件时出错: {str(e)}")
            return ""
    
    def get_today_papers(self) -> List[Dict[str, Any]]:
        """获取最近发布的相关论文"""
        papers = self.search_papers()
        
        if OUTPUT_CONFIG.get('save_to_file', True) and papers:
            self.save_to_csv(papers, prefix='raw_')
        
        return papers


def get_arxiv_papers(keywords: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    """获取arXiv论文的便捷函数"""
    service = ArxivService()
    return service.search_papers(keywords)
