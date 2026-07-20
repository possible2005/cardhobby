# 开发规范

## 1. 项目目录结构

```
card_env/
├── app/                       # 应用主包
│   ├── __init__.py           # Flask app 工厂
│   ├── config.py             # 配置（文件路径、端口等）
│   ├── models/
│   │   ├── __init__.py
│   │   ├── monitor.py        # 监控数据存储（config/history）
│   │   └── collection.py     # 凑套数据存储
│   ├── services/
│   │   ├── __init__.py
│   │   ├── scraper.py        # scrape_cardhobby 核心爬虫
│   │   ├── scheduler.py     # 定时调度线程
│   │   ├── matcher.py        # match_scraped_to_collections 匹配逻辑
│   │   └── parser.py         # 凑套文本解析
│   └── routes/
│       ├── __init__.py       # 蓝图注册
│       ├── index.py          # 首页
│       ├── scrape.py         # /api/search, /api/mark_bid, /api/scrape/match
│       ├── monitor.py        # /api/monitor/* 路由
│       └── collection.py     # /api/collections/* 路由
├── data/                      # 数据文件目录（运行时自动创建）
│   ├── monitor_config.json
│   ├── monitor_history.json
│   ├── collections.json
│   └── cardhobby_prices_*.csv
├── docs/
│   ├── PRD.md                # 产品需求文档
│   └── DEVELOPMENT.md        # 开发规范
├── index.html                 # 前端页面（静态文件）
├── run.py                     # 启动入口
├── requirements.txt           # 依赖清单
└── main.py                    # 旧版单文件（参考保留）
```

### 模块职责

| 模块 | 职责 |
| --- | --- |
| `app/config.py` | 统一管理所有文件路径、端口等配置 |
| `app/models/` | 数据存储层，负责 JSON 文件读写 |
| `app/services/` | 业务服务层，包含爬虫、调度、匹配、解析 |
| `app/routes/` | 路由层，使用 Blueprint 组织 API |

## 2. 环境搭建

### 2.1 Python 虚拟环境

```bash
cd /Users/donglin/Desktop/projects/card_env
python3 -m venv .
source bin/activate
```

### 2.2 依赖安装

```bash
pip install -r requirements.txt
```

### 2.3 Playwright 浏览器安装

```bash
playwright install chromium
```

## 3. 启动与停止

### 3.1 启动开发服务器

```bash
python run.py
```

服务监听 `0.0.0.0:5001`，启用调试模式。

### 3.2 通过 flask 命令启动（可选）

```bash
export FLASK_APP=run.py
flask run --port=5001
```

### 3.3 停止

`Ctrl+C` 终止前台进程即可，后台监控线程为 daemon 线程会自动退出。

## 4. 编码规范

### 4.1 命名

- 模块文件名：小写下划线，如 `monitor.py`、`collection.py`
- 函数名：小写下划线，如 `load_monitor_config`、`scrape_cardhobby`
- 类名（如有）：大驼峰，如 `MonitorService`
- 常量：全大写下划线，如 `MONITOR_CONFIG_FILE`、`DEFAULT_MONITOR_CONFIG`
- 蓝图变量：`<name>_bp`，如 `monitor_bp`、`scrape_bp`

### 4.2 注释

- 每个模块顶部使用三引号文档字符串说明用途
- 每个公开函数使用 docstring 说明参数与返回值
- 复杂逻辑使用行内注释，说明"为什么"而非"是什么"

### 4.3 错误处理

- 文件读写使用 `try/except (json.JSONDecodeError, IOError)` 兜底
- API 路由中所有可能抛错的逻辑用 `try/except` 包裹，返回 500 与错误信息
- 后台线程使用 `try/except` 防止单次异常导致线程退出
- 不要吞掉异常：至少打印日志或返回错误信息

## 5. API 设计规范

### 5.1 RESTful 约定

| 方法 | 用途 |
| --- | --- |
| GET | 读取资源 |
| POST | 创建/触发动作 |
| PUT | 更新资源 |
| DELETE | 删除资源 |

### 5.2 返回格式

所有 API 返回 JSON，统一字段：

- 成功：`{"success": true, ...业务字段}`
- 失败：`{"error": "错误描述"}`

HTTP 状态码：
- `200`：成功
- `400`：参数错误
- `404`：资源不存在
- `500`：服务器内部错误

### 5.3 路由分组

按业务域拆分到不同蓝图：
- `scrape_bp`：抓取相关
- `monitor_bp`：监控相关
- `collection_bp`：凑套相关
- `index_bp`：首页

## 6. 数据文件管理规范

### 6.1 路径管理

所有数据文件路径在 `app/config.py` 中定义，其他模块通过导入使用，**禁止在业务代码中硬编码文件名**。

### 6.2 目录自动创建

`create_app()` 启动时调用 `ensure_data_dir()` 自动创建 `data/` 目录。

### 6.3 并发安全

JSON 文件读写使用 `threading.Lock` 保护：
- `monitor_lock`：监控配置与历史
- `collection_lock`：凑套数据

### 6.4 CSV 文件命名

CSV 文件名格式：`cardhobby_prices_<keyword>.csv`，关键字中的空格替换为下划线。

使用 `app.config.get_csv_filename(keyword)` 生成路径。

## 7. 部署说明

### 7.1 开发部署

直接使用 `python run.py` 启动 Flask 内置开发服务器，适合本地调试。

### 7.2 生产部署（建议）

使用 gunicorn 或 uwsgi 作为 WSGI 容器：

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5001 "run:app"
```

注意：生产环境下应关闭 DEBUG 模式，并将 `app.config.DEBUG` 改为 `False`。

### 7.3 注意事项

- Playwright 需要安装 Chromium 浏览器
- 后台监控线程为 daemon，主进程退出时自动结束
- 数据文件写入 `data/` 目录，部署时确保该目录可写
- 旧版 `main.py` 保留作为参考，新代码统一在 `app/` 目录下
