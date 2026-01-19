# ArXiv 论文推送系统 - AI Coding 指南

## 项目概述
这是一个 **三合一** 学术论文推送系统：FastAPI 后端 + 定时调度器 + 静态前端服务，运行端口 `20001`。

## 核心架构

### 数据流
```
arXiv API → papers_raw(MySQL) → LLM筛选 → 翻译 → papers_relevant → paper_queue → 钉钉推送
```

### 服务模块 (`services/`)
| 服务 | 职责 |
|------|------|
| `arxiv_service.py` | 从 arXiv API 拉取论文，支持分类代码(如`cs.CL`)和关键词搜索 |
| `llm_filter_service.py` | 使用 OpenAI 兼容 API 评估论文相关度(1-5星) |
| `translation_service.py` | 中英翻译论文标题和摘要 |
| `mysql_service.py` | 所有数据库操作，包含表自动创建/迁移逻辑 |
| `dingtalk_http_service.py` | 钉钉推送(推荐HTTP版本而非SDK) |
| `paper_queue_service.py` | 论文推送队列(封装数据库队列函数) |

### 关键设计模式

1. **配置层级**: `config.py` 定义默认值 → `runtime_config.json` 覆盖 → 数据库 `system_config` 表优先
2. **线程本地连接**: MySQL 使用 `threading.local()` 保证线程安全
3. **后台处理**: 论文获取使用生产者-消费者模式，主线程拉取，后台线程处理
4. **表自动迁移**: `_ensure_tables_exist()` 检测并添加缺失列

## 开发指南

### 启动项目
```bash
pip install -r requirements.txt
python app.py  # 访问 http://localhost:20001/docs
```

### 配置修改
- **研究方向**: 修改 `config.py` 中的 `RESEARCH_DESCRIPTION`
- **arXiv 分类**: 修改 `ARXIV_CONFIG['keywords']`，支持 `cs.CL`、`cs.CV` 等分类代码
- **LLM 筛选阈值**: `LLM_FILTER_CONFIG['min_score']` (100分制，默认60分及格)

### API 路由约定
- 所有 API 路径以 `/api/` 开头
- 返回格式: `{"success": bool, "data": ..., "message": ...}`
- 使用 Pydantic BaseModel 定义请求体

### 添加新服务
1. 在 `services/` 下创建 `xxx_service.py`
2. 类名使用 `XxxService` 格式
3. 在 `services/__init__.py` 中导出
4. 从 `config.py` 导入配置而非硬编码

### MySQL 操作规范
```python
# 正确方式：使用线程安全连接
conn = get_mysql_connection()
with conn.cursor() as cursor:
    cursor.execute(sql)
conn.commit()

# 避免：直接创建连接或使用全局连接
```

### LLM 服务注意事项
- 使用 `httpx.Client` 显式禁用代理
- 重试逻辑: 3次重试，5秒间隔
- 并行处理: `max_workers` 可配置

## 数据库表结构
- `papers_raw`: 原始论文，含 `processed` 标记
- `papers_relevant`: 筛选后论文，含翻译、评分、`is_pushed` 标记
- `paper_queue`: 待推送队列
- `system_config`: 运行时配置

## 常见任务

### 修改论文评分逻辑
编辑 `llm_filter_service.py` 中的 `_build_evaluation_prompt()` 方法。评分标准：
- 100分制，60分及格
- `Stars` 字段实际存储分数值(0-100)，保持数据库兼容

### 重新评分已有论文
```bash
# 试运行（不更新数据库）
python rescore_papers.py --dry-run --limit 10

# 只转换旧5星制为100分制
python rescore_papers.py --convert-only

# 完整重新评估
python rescore_papers.py --workers 8
```

### 添加新的推送渠道
参考 `dingtalk_http_service.py` 实现新服务，在 `run_push_papers()` 中调用

### 调整定时任务
修改 `SCHEDULE_CONFIG`，调度器会在 `/api/scheduler/reload` 时重新加载
