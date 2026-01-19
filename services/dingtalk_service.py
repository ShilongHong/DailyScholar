"""
钉钉消息推送服务
"""

import json
import time
import logging
import requests
from typing import Dict, List, Any, Optional
from datetime import datetime

from alibabacloud_dingtalk.robot_1_0.client import Client as dingtalkrobot_1_0Client
from alibabacloud_tea_openapi import models as open_api_models
from alibabacloud_dingtalk.robot_1_0 import models as dingtalkrobot__1__0_models
from alibabacloud_tea_util import models as util_models

# 从父目录导入配置
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DINGTALK_CONFIG, MESSAGE_CONFIG

logger = logging.getLogger(__name__)


class DingTalkService:
    """钉钉消息推送服务类"""
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or DINGTALK_CONFIG
        self.message_config = MESSAGE_CONFIG
        
        self._access_token = self.config.get('access_token', '')
        self._token_expire_time = self.config.get('token_expire_time', 0)
        
        logger.info("DingTalkService初始化完成")
    
    def get_access_token(self) -> str:
        """获取钉钉access_token"""
        current_time = time.time()
        if self._access_token and self._token_expire_time > current_time + 300:
            return self._access_token
        
        app_key = self.config.get('app_key')
        app_secret = self.config.get('app_secret')
        
        if not app_key or not app_secret:
            raise ValueError("请在config.py中配置有效的app_key和app_secret")
        
        try:
            url = self.config['token_url']
            params = {
                'appkey': app_key,
                'appsecret': app_secret
            }
            
            logger.info("正在获取access_token...")
            response = requests.get(url, params=params, timeout=10)
            result = response.json()
            
            if result['errcode'] == 0:
                self._access_token = result['access_token']
                self._token_expire_time = current_time + result.get('expires_in', 7200)
                logger.info(f"✅ access_token获取成功")
                return self._access_token
            else:
                raise Exception(f"获取access_token失败: {result.get('errmsg', '未知错误')}")
                
        except requests.RequestException as e:
            raise Exception(f"网络请求失败: {str(e)}")
    
    def _create_client(self) -> dingtalkrobot_1_0Client:
        """创建钉钉机器人客户端"""
        config = open_api_models.Config()
        config.protocol = 'https'
        config.region_id = 'central'
        return dingtalkrobot_1_0Client(config)
    
    def send_message(self, content: str, title: Optional[str] = None, msg_type: str = 'markdown') -> bool:
        """发送消息到钉钉"""
        try:
            access_token = self.get_access_token()
            
            if msg_type == 'markdown':
                msg_param = {
                    'title': title or '消息推送',
                    'text': content
                }
            else:
                msg_param = {
                    'content': content
                }
            
            # 调试：详细输出参数信息
            logger.info(f"准备发送消息 - msg_type: {msg_type}")
            logger.info(f"  title: {repr(msg_param.get('title', 'N/A'))[:100]}")
            logger.info(f"  content/text length: {len(str(msg_param.get('text') or msg_param.get('content', '')))}")
            
            # 确保没有空值
            if msg_type == 'markdown':
                if not msg_param.get('title'):
                    logger.warning("⚠️ title为空，使用默认值")
                    msg_param['title'] = '论文推送'
                if not msg_param.get('text'):
                    logger.error("❌ text为空，无法发送！")
                    return False
            
            # JSON序列化
            try:
                msg_param_json = json.dumps(msg_param, ensure_ascii=False)
                logger.info(f"  JSON序列化成功，长度: {len(msg_param_json)}")
            except Exception as json_err:
                logger.error(f"❌ JSON序列化失败: {str(json_err)}")
                logger.error(f"  msg_param内容: {repr(msg_param)[:500]}")
                return False
            
            client = self._create_client()
            
            headers = dingtalkrobot__1__0_models.OrgGroupSendHeaders()
            headers.x_acs_dingtalk_access_token = access_token
            
            # 构建请求
            logger.info(f"  robot_code: {repr(self.config.get('robot_code'))}")
            logger.info(f"  open_conversation_id: {repr(self.config.get('open_conversation_id'))}")
            
            request = dingtalkrobot__1__0_models.OrgGroupSendRequest(
                msg_param=msg_param_json,
                msg_key=f'sampleMarkdown' if msg_type == 'markdown' else 'sampleText',
                robot_code=self.config['robot_code'],
                open_conversation_id=self.config['open_conversation_id']
            )
            
            logger.info(f"  发送请求到钉钉API...")
            try:
                # 创建RuntimeOptions并启用详细日志
                runtime = util_models.RuntimeOptions()
                runtime.autoretry = False
                runtime.max_attempts = 1
                
                response = client.org_group_send_with_options(request, headers, runtime)
                logger.info(f"  收到响应 - status_code: {response.status_code}")
                
                # 尝试读取响应体
                if hasattr(response, 'body'):
                    logger.info(f"  响应体类型: {type(response.body)}")
                    logger.info(f"  响应体内容: {repr(response.body)[:500]}")
                
            except Exception as api_error:
                logger.error(f"  API调用异常: {type(api_error).__name__}")
                logger.error(f"  异常消息: {str(api_error)}")
                
                # 深度检查异常对象的所有属性
                for attr in dir(api_error):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(api_error, attr)
                            if not callable(value):
                                logger.error(f"  {attr}: {repr(value)[:200]}")
                        except:
                            pass
                
                raise
            
            if response.status_code == 200:
                logger.info("✅ 钉钉消息发送成功")
                return True
            else:
                logger.error(f"❌ 钉钉消息发送失败: {response.status_code}")
                logger.error(f"  响应内容: {repr(response.body)[:500] if hasattr(response, 'body') else 'N/A'}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 发送钉钉消息时出错: {str(e)}")
            logger.error(f"  错误类型: {type(e).__name__}")
            # 输出完整堆栈
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
                
                # 安全获取字段值，确保不会有None或空字符串导致JSON解析失败
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
                
                logger.info(f"  [{idx}/{len(papers)}] 准备发送论文: {title_cn[:50]}...")
                logger.info(f"    Stars: {stars_count}, Author: {author[:30]}")
                
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
                
                logger.info(f"    消息内容长度: {len(content)}")
                
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
                logger.error(f"     Paper DOI: {paper.get('DOI', 'N/A')}")
                logger.error(f"     Paper data: {repr(paper)[:300]}")
        
        logger.info(f"发送完成: 成功 {success_count}/{len(papers)}，失败 {fail_count}/{len(papers)}")
        return fail_count == 0
    
    def send_error_notification(self, error_message: str) -> bool:
        """发送错误通知"""
        title = "⚠️ 论文推送服务异常"
        content = f"**错误信息**: {error_message}\n\n**时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        return self.send_message(content, title, 'markdown')


def send_to_dingtalk(papers: List[Dict[str, Any]]) -> bool:
    """发送论文到钉钉的便捷函数"""
    service = DingTalkService()
    return service.send_papers(papers)
