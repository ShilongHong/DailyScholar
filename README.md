# ArXiv 论文推送系统 v3.0 (三合一版)

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-orange.svg)](https://www.mysql.com/)

一个集成化的学术论文自动化追踪系统。单进程同时运行 **后端API**、**定时调度器** 和 **前端静态服务**。

核心工作流：`arXiv API` -> `MySQL` -> `LLM 智能筛选` -> `中英翻译` -> `钉钉推送`

---

## ✨ 核心特性

- **三合一架构**：无需配置 Nginx 或 Supervisor，直接运行 `python app.py` 即可启动所有服务。
- **智能筛选**：基于 LLM (DeepSeek/OpenAI) 对论文进行深度理解和打分，只推送真正相关的论文。
- **个性化定制**：通过自然语言描述 `RESEARCH_DESCRIPTION` 定义你的研究兴趣。
- **自动化工作流**：
  - 自动抓取最新论文
  - 自动重试失败任务
  - 自动推送至钉钉群
- **完善的后台管理**：提供 RESTful API 和 Swagger 文档，方便管理和监控。

## 📁 项目结构

```
daliy_paper_v3/
├── app.py                  # 系统主入口
├── config.py               # 配置文件（需从 config.demo.py 复制）
├── requirements.txt        # 依赖列表
├── services/               # 核心业务逻辑
│   ├── arxiv_service.py    # arXiv 抓取
│   ├── llm_filter_service.py # LLM 评分
│   └── ...
├── tools/                  # 运维工具脚本
│   ├── rebuild_queue.py    # 重建推送队列
│   └── rescore_papers.py   # 重新评分工具
├── static/                 # 前端静态资源
├── logs/                   # 运行日志
└── output/                 # 数据导出目录
```

## 🚀 快速开始

### 1. 环境准备
- Python 3.8 或更高版本
- MySQL 数据库

### 2. 安装依赖
```bash
pip install -r requirements.txt
```

### 3. 配置文件
复制示例配置并修改：
```bash
cp config.demo.py config.py
```

**关键配置项 (`config.py`)**:
- `RESEARCH_DESCRIPTION`: **最重要的配置**。用自然语言详细描述你的研究方向，LLM 将以此为基准进行论文筛选。
- `ARXIV_CONFIG`: 配置 arXiv 搜索关键词 (如 `cs.CL`, `cs.CV`)。
- `LLM_FILTER_CONFIG`: 配置 LLM API (支持 DeepSeek, OpenAI 等兼容接口)。
- `DINGTALK_CONFIG`: 配置钉钉机器人的 Access Token 和 Secret。
- `SCHEDULE_CONFIG`: 调整抓取和推送的定时任务时间。

### 4. 启动服务
```bash
python app.py
```
启动成功后，控制台将显示：
```
╔══════════════════════════════════════════════════════════╗
║         ArXiv论文推送系统 v3.0 - 三合一版                ║
║  端口：20001                                             ║
║  文档：http://localhost:20001/docs                       ║
╚══════════════════════════════════════════════════════════╝
```

## 🖥️ 访问服务

- **Web 界面**: [http://localhost:20001](http://localhost:20001)
- **API 文档**: [http://localhost:20001/docs](http://localhost:20001/docs)
- **健康检查**: [http://localhost:20001/api/health](http://localhost:20001/api/health)

## 🛠️ 运维工具 (`tools/`)

项目在 `tools/` 目录下提供了一系列实用脚本：

- `rebuild_queue.py`: 清空并重建待推送队列。
- `rescore_papers.py`: 使用新的 Prompt 或逻辑重新评估已抓取的论文。
- `fix_created_at.py`: 修复数据库中的时间字段问题。
- `reset_processed_2026.py`: 重置特定日期的处理状态（用于调试）。

## 📦 部署指南（宝塔面板）

1. **上传项目**: 将代码上传至 `/www/wwwroot/daliy_paper_v3`。
2. **安装依赖**: 在项目目录下运行 `pip install -r requirements.txt`。
3. **添加 Python 项目**:
   - 路径: `/www/wwwroot/daliy_paper_v3`
   - 启动文件: `app.py`
   - 端口: `20001`
4. **放行端口**: 在防火墙/安全组中放行 `20001` 端口。
5. **(可选) 反向代理**:
   ```nginx
   location / {
       proxy_pass http://127.0.0.1:20001;
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
   }
   ```

## ❓ 常见问题

**Q: 如何手动触发抓取或推送？**
A: 使用 API 接口：
- 抓取: `POST /api/actions/fetch-now`
- 推送: `POST /api/actions/push-now`

**Q: 数据库表需要手动创建吗？**
A: 不需要。系统启动时会自动检测并创建所需的数据库表结构 (`papers_raw`, `papers_relevant` 等)。

**Q: 前端页面显示 404？**
A: 请确保已将前端构建产物（`dist` 目录内容）复制到 `static/` 目录下。如果没有前端代码，可以直接使用 Swagger UI (`/docs`) 进行操作。

---
**Version**: 3.0.0
