# ArXiv论文推送系统 v3.0 - 三合一版

一个命令启动：**后端API + 前端页面 + 定时调度**

## 📁 项目结构

```
daliy_paper_v3/
├── app.py              # 主程序（三合一）
├── config.py           # 配置文件
├── requirements.txt    # Python依赖
├── services/           # 业务服务模块
│   ├── __init__.py
│   ├── arxiv_service.py
│   ├── llm_filter_service.py
│   ├── translation_service.py
│   ├── dingtalk_service.py
│   ├── paper_queue_service.py
│   └── mysql_service.py
├── static/             # 前端静态文件（构建后复制到这里）
├── logs/               # 日志目录
└── output/             # 输出目录
```

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

编辑 `config.py`，填写：
- MySQL数据库连接信息
- 钉钉推送配置
- LLM API Key
- arXiv关键词

### 3. 启动

```bash
python app.py
```

访问地址：
- 前端页面: http://localhost:20001
- API文档: http://localhost:20001/docs

## 📦 部署前端

### 方法1：从旧项目复制
```bash
# 在 daliy_paper/web/frontend 目录
npm install
npm run build

# 复制到v3的static目录
cp -r dist/* ../daliy_paper_v3/static/
```

### 方法2：直接使用API
如果没有前端，直接访问 `/docs` 使用Swagger UI

## 🖥️ 服务器部署（宝塔）

### 1. 上传项目
将 `daliy_paper_v3` 文件夹上传到服务器，如 `/www/wwwroot/daliy_paper_v3`

### 2. 安装依赖
```bash
cd /www/wwwroot/daliy_paper_v3
pip3 install -r requirements.txt
```

### 3. 使用Python项目管理器

在宝塔面板 → 网站 → Python项目 → 添加项目：

| 配置项 | 值 |
|-------|-----|
| 项目名称 | paper-system |
| 项目路径 | /www/wwwroot/daliy_paper_v3 |
| 端口 | 20001 |
| 启动命令 | python3 app.py |

### 4. 配置反向代理（可选）

如果想用域名访问，添加反向代理：

```nginx
location / {
    proxy_pass http://127.0.0.1:20001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
}
```

### 5. 放行端口

在宝塔面板 → 安全 → 放行20001端口

## 🎯 API接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/papers` | GET | 获取论文列表 |
| `/api/papers/stats` | GET | 获取统计数据 |
| `/api/queue/status` | GET | 队列状态 |
| `/api/config/all` | GET | 获取所有配置 |
| `/api/config/{name}` | PUT | 更新配置 |
| `/api/scheduler/status` | GET | 调度器状态 |
| `/api/actions/fetch-now` | POST | 立即获取论文 |
| `/api/actions/push-now` | POST | 立即推送论文 |

## ⏰ 定时任务

启动后自动运行调度器：
- **论文获取**: 每天凌晨02:00
- **论文推送**: 每天09:00和14:30

可通过API或修改 `config.py` 调整时间。

## 🔧 配置说明

### config.py 主要配置

```python
# 调度配置
SCHEDULE_CONFIG = {
    'fetch_papers': {
        'enable': True,
        'time': '02:00',      # 获取时间
    },
    'push_papers': {
        'enable': True,
        'times': ['09:00', '14:30'],  # 推送时间
        'max_papers_per_push': 5,     # 每次推送数量
    },
}

# MySQL配置
ARXIV_CONFIG = {
    'mysql': {
        'enable': True,
        'host': 'your-host',
        'port': 3306,
        'user': 'your-user',
        'password': 'your-password',
        'database': 'your-database',
    },
}
```

## 📝 日志

日志文件位于 `logs/` 目录：
- `app_YYYYMMDD.log` - 每天一个日志文件

## ❓ 常见问题

### Q: 如何测试推送？
```bash
curl -X POST http://localhost:20001/api/actions/push-now
```

### Q: 如何查看队列？
```bash
curl http://localhost:20001/api/queue/status
```

### Q: 前端页面404？
确保 `static/index.html` 文件存在。没有前端时可以直接访问 `/docs`。

### Q: 如何后台运行？
使用 nohup 或 systemd：
```bash
nohup python3 app.py > /dev/null 2>&1 &
```

或者使用宝塔的Python项目管理器自动管理。

---

**Version**: 3.0.0 - 三合一版  
**特点**: 单文件运行，部署简单
