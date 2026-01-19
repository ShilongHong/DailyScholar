"""
钉钉消息推送 - 原始HTTP实现（不使用SDK）
解决SDK在服务器上返回空响应的问题
"""
import requests
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import time

logger = logging.getLogger(__name__)


class DingTalkHTTPService:
    """使用原始HTTP请求的钉钉服务（不依赖SDK）"""
    
    def __init__(self, config: Optional[Dict] = None):
        from config import DINGTALK_CONFIG, MESSAGE_CONFIG
        self.config = config or DINGTALK_CONFIG
        self.message_config = MESSAGE_CONFIG
        self._access_token = None
        self._token_expire_time = 0
        logger.info("DingTalkHTTPService初始化完成（原始HTTP模式）")
    
    def get_access_token(self) -> str:
        """获取access_token"""
        current_time = time.time()
        if self._access_token and self._token_expire_time > current_time + 300:
            return self._access_token
        
        app_key = self.config.get('app_key')
        app_secret = self.config.get('app_secret')
        
        if not app_key or not app_secret:
            raise ValueError("请在config.py中配置有效的app_key和app_secret")
        
        try:
            logger.info("正在获取access_token...")
            url = "https://api.dingtalk.com/v1.0/oauth2/accessToken"
            headers = {"Content-Type": "application/json"}
            data = {
                "appKey": app_key,
                "appSecret": app_secret
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=10)
            logger.info(f"Token API响应: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                self._access_token = result.get('accessToken')
                expires_in = result.get('expireIn', 7200)
                self._token_expire_time = current_time + expires_in
                logger.info("✅ access_token获取成功")
                return self._access_token
            else:
                raise Exception(f"获取token失败: {response.status_code} - {response.text}")
                
        except Exception as e:
            raise Exception(f"网络请求失败: {str(e)}")
    
    def send_message(self, content: str, title: Optional[str] = None, msg_type: str = 'markdown') -> bool:
        """发送消息到钉钉"""
        try:
            access_token = self.get_access_token()
            
            # 构建消息参数
            if msg_type == 'markdown':
                msg_param = {
                    'title': title or '消息推送',
                    'text': content
                }
            else:
                msg_param = {
                    'content': content
                }
            
            logger.info(f"准备发送消息 - msg_type: {msg_type}")
            logger.info(f"  title: {repr(msg_param.get('title', 'N/A'))[:100]}")
            logger.info(f"  content length: {len(content)}")
            
            # 发送请求 - 使用正确的群聊接口
            url = "https://api.dingtalk.com/v1.0/robot/groupMessages/send"
            headers = {
                "x-acs-dingtalk-access-token": access_token,
                "Content-Type": "application/json"
            }
            
            data = {
                "msgKey": "sampleMarkdown" if msg_type == 'markdown' else "sampleText",
                "msgParam": json.dumps(msg_param, ensure_ascii=False),
                "robotCode": self.config['robot_code'],
                "openConversationId": self.config['open_conversation_id']
            }
            
            logger.info(f"  发送HTTP请求到: {url}")
            response = requests.post(url, json=data, headers=headers, timeout=10)
            
            logger.info(f"  HTTP响应状态码: {response.status_code}")
            logger.info(f"  响应头: {dict(response.headers)}")
            logger.info(f"  响应体长度: {len(response.content)}")
            logger.info(f"  响应体: {response.text[:500]}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"  响应JSON: {result}")
                logger.info("✅ 钉钉消息发送成功")
                return True
            else:
                logger.error(f"❌ 发送失败 - HTTP {response.status_code}")
                logger.error(f"  错误响应: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 发送钉钉消息时出错: {str(e)}")
            import traceback
            logger.error(f"  完整堆栈:\n{traceback.format_exc()}")
            return False
    
    def send_papers(self, papers: List[Dict[str, Any]]) -> bool:
        """发送论文列表到钉钉"""
        if not papers:
            title = self.message_config['title_template'].format(
                date=datetime.now().strftime('%Y年%m月%d日')
            )
            content = self.message_config['no_papers_message']
            return self.send_message(content, title, 'markdown')
        
        logger.info(f"准备发送 {len(papers)} 篇论文")
        
        success_count = 0
        fail_count = 0
        
        paper_template = self.message_config['paper_template']
        
        for idx, paper in enumerate(papers, 1):
            try:
                stars_count = paper.get('Stars', 3)
                stars_display = '⭐' * stars_count
                title = f"📚 论文推送 ({idx}/{len(papers)}) - {stars_display}"
                
                # 安全获取字段值
                title_cn = paper.get('TitleCN') or paper.get('Title') or '无标题'
                abstract_cn = paper.get('AbstractCN') or paper.get('Abstract') or '暂无摘要'
                author = paper.get('Author') or '未知作者'
                affiliation = paper.get('Affiliation') or '未提供单位信息'
                publication_year = paper.get('PublicationYear') or '未知'
                pdf_link = paper.get('PDFLink') or paper.get('Link') or ''
                link = paper.get('Link') or ''
                relevance_reason = paper.get('RelevanceReason') or '相关论文'
                potential_help = paper.get('PotentialHelp') or '可作为研究参考'
                doi = paper.get('DOI') or '无DOI'
                
                logger.info(f"  [{idx}/{len(papers)}] {title_cn[:50]}...")
                
                content = paper_template.format(
                    Stars=stars_count,
                    TitleCN=title_cn,
                    AbstractCN=abstract_cn,
                    Author=author,
                    Affiliation=affiliation,
                    PublicationYear=publication_year,
                    PDFLink=pdf_link,
                    Link=link,
                    RelevanceReason=relevance_reason,
                    PotentialHelp=potential_help,
                    DOI=doi
                )
                
                if self.send_message(content, title, 'markdown'):
                    success_count += 1
                    logger.info(f"  ✅ [{idx}/{len(papers)}] 发送成功")
                else:
                    fail_count += 1
                    logger.warning(f"  ❌ [{idx}/{len(papers)}] 发送失败")
                
                if idx < len(papers):
                    time.sleep(1)
                    
            except Exception as e:
                fail_count += 1
                logger.error(f"  ❌ [{idx}/{len(papers)}] 发送出错: {str(e)}")
        
        logger.info(f"发送完成: 成功 {success_count}/{len(papers)}，失败 {fail_count}/{len(papers)}")
        return fail_count == 0
