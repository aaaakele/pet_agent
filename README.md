# 🐾 Desktop Pet Agent

一只浮在桌面上的可爱宠物，内置 LLM 智能助手，能聊天、能搜索、能控制电脑、能通过 QQ 远程操控。

![pet demo](resources/wusaqi.gif)

---

## ✨ 功能一览

### 🖥️ 桌面宠物
- **浮窗显示** — 无边框、透明背景、置顶显示，像真正的桌宠一样待在桌面上
- **拖拽移动** — 按住宠物可随意拖动位置
- **单击气泡** — 单击弹出快捷输入框，快速提问
- **双击聊天** — 双击打开完整聊天窗口，查看对话历史
- **右键菜单** — 聊天、换头像、隐藏、退出
- **系统托盘** — 右下角托盘图标，支持右键菜单和双击显示/隐藏
- **响应气泡** — 宠物回复会以气泡形式弹出在宠物上方，5秒自动消失

### 🧠 AI 对话引擎
- **DeepSeek 大模型** — 基于 DeepSeek API，支持 Pro 和 Flash 两种模型
- **Thinking 模式** — Flash 模型支持思维链显示（可在菜单中开关）
- **模型切换** — 右键菜单中一键切换 Pro / Flash，随时开关 Thinking
- **ReAct 循环** — 最多 5 轮工具调用，自动推理、执行工具、生成回答
- **上下文压缩** — 对话超过阈值时自动生成摘要，避免超长上下文

### 🔧 内置工具（17个）

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文本文件内容 |
| `write_file` | 写入文件（带自动备份） |
| `list_directory` | 列出目录内容 |
| `grep_code` | 在本地文件中搜索文本 |
| `web_search` | 搜索引擎查询（Bing → DDGS 多引擎降级） |
| `fetch_url` | 抓取网页正文（自动编码非ASCII URL） |
| `get_system_info` | 获取系统信息（OS、CPU、内存、磁盘） |
| `run_command` | 执行 Shell 命令 |
| `open_app` | 打开本地应用（Chrome、VSCode、计算器等 30+ 应用） |
| `open_url` | 在默认浏览器中打开网址 |
| `system_control` | 锁定、睡眠、调音量（安全操作，不含关机） |
| `schedule_reminder` | 设置定时提醒（自然语言解析时间） |
| `list_reminders` | 查看待执行提醒 |
| `cancel_reminder` | 取消提醒 |
| `research_trends` | 过去30天热点研究（多平台聚合搜索） |
| `web_open` | 搜索并直接打开结果链接（支持 B站 API 解析） |

### 🌐 网络搜索
- **多引擎降级** — cn.bing.com → www.bing.com → DuckDuckGo 三级备胎
- **Baidu 搜索** — 作为备用搜索引擎
- **B站 API 集成** — 直接调用 B站 搜索 API，按播放量排序打开视频
- **last30days 集成** — 跨 Reddit、X、YouTube、HN 等 17 个平台聚合搜索
- **搜索缓存** — 5 分钟 TTL，避免重复搜索
- **连接池** — 共享 HTTP opener，复用 TCP 连接

### 🔌 本地控制
- **打开应用** — 支持 Chrome、Edge、VSCode、微信、QQ音乐、计算器 等 30+ 常用应用
- **系统操作** — 锁定、睡眠、音量控制
- **桌面自动化** — (试验性) 点击 UI 元素、输入文字

### 📱 QQ 远程控制
- **WebSocket 服务** — 启动 OneBot v11 兼容的 WebSocket 服务端（端口 3001）
- **HTTP API** — 同时提供 HTTP 接口（端口 3002），方便任意 HTTP 客户端接入
- **QQ 号白名单** — 仅允许指定的 QQ 号发送指令
- **NapCat 集成** — 可通过 NapCatQQ 桥接 QQ 消息到桌宠

### ⏰ 定时任务
- 支持自然语言设定提醒（"5分钟后"、"明天上午9点"）
- 支持循环提醒
- 提醒到达时通过气泡推送通知

### 💾 数据存储
- **SQLite** — 对话历史、工具调用记录、定时任务持久化
- **自动迁移** — 数据库 schema 自动升级
- **消息归档** — 超出阈值时自动摘要压缩

---

## 🏗️ 项目结构

```
pet_agent/
├── config/
│   ├── settings.py      # 全局配置（pydantic-settings）
│   └── .env             # 环境变量（API Key、模型、QQ配置）
├── core/
│   ├── agent/
│   │   ├── executor.py  # Agent 主循环（ReAct + 工具调度）
│   │   └── tools.py     # 17个工具的实现（680+ 行）
│   ├── history/
│   │   └── storage.py   # SQLite 存储层
│   ├── llm/
│   │   └── client.py    # DeepSeek API 客户端
│   ├── memory/
│   │   ├── manager.py   # 记忆管理
│   │   └── summary.py   # 对话摘要
│   ├── pet/
│   │   ├── window.py    # 浮动窗口
│   │   ├── chat.py      # 聊天对话框
│   │   ├── bubble.py    # 快捷气泡 + 回复气泡
│   │   ├── tray.py      # 系统托盘
│   │   ├── icons.py     # 头像管理
│   │   └── model_switcher.py  # 模型切换菜单
│   ├── qq/
│   │   ├── bot.py       # QQ Bot 服务端（WS + HTTP 双协议）
│   │   └── onebot.py    # OneBot v11 协议解析
│   └── tasks/
│       └── scheduler.py # 定时任务调度器
├── main.py              # 应用入口
├── resources/           # 图片资源
├── storage/             # SQLite 数据文件
├── .agents/skills/      # last30days 技能插件
└── requirements.txt     # Python 依赖
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 `.env`

```env
DEEPSEEK_API_KEY=your_api_key_here
DEEPSEEK_MODEL=deepseek-v4-flash
THINKING_ENABLED=true

# QQ 远程控制（可选）
QQ_ENABLED=true
QQ_WS_PORT=3001
QQ_WHITELIST=你的QQ号
```

### 3. 启动

```bash
python main.py
```

双击宠物 → 聊天
单击宠物 → 快捷提问
右键宠物 → 菜单/模型切换

### 4. QQ 远程连接（可选）

**NapCat 方案：**
1. 下载 NapCatQQ Shell 版到 `D:\NapCat`
2. 双击 `D:\NapCat\启动NapCat.bat`
3. 扫码登录宠物 QQ
4. NapCat 自动连接桌宠的 WebSocket

**或 HTTP 桥接：**
```
POST http://127.0.0.1:3002/qq_message
Content-Type: application/json

{"user_id": 123456, "message": "你好"}
```

---

## ⚙️ 配置说明

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `THINKING_ENABLED` | `true` | 是否启用思维链（仅 Flash） |
| `TOOL_EXECUTION_TIMEOUT` | `60` | 单次工具调用超时(秒) |
| `QQ_ENABLED` | `false` | 启用 QQ Bot |
| `QQ_WS_PORT` | `3001` | WebSocket 端口 |
| `QQ_HTTP_PORT` | `3002` | HTTP API 端口 |
| `QQ_WHITELIST` | — | 允许的 QQ 号（逗号分隔） |

---

## 🧩 技术架构

```
用户输入
    │
    ▼
┌─────────────┐
│  AgentExecutor │  ReAct 循环（最多5轮）
│  (executor.py) │
└──────┬──────┘
       │
       ├─▶ DeepSeek API ──▶ 判断是否调用工具
       │
       ├─▶ 并行执行工具 ──▶ asyncio.gather
       │    │
       │    ├─ 本地工具（文件/命令/系统）
       │    ├─ 搜索工具（Bing/DDGS/B站API）
       │    └─ 远程工具（QQ/HTTP）
       │
       └─▶ 生成回复 ──▶ 显示在气泡/聊天/QQ
```

### 并发模型
- **Qt 主线程** — GUI 事件循环
- **AgentWorker** — 每次对话创建一个 QThread，独立 asyncio 事件循环
- **TaskScheduler** — 持久 QThread，15s 轮询定时任务
- **QQBotThread** — 持久 QThread，运行 WebSocket + HTTP 双协议服务

---

## 📦 依赖

- **PySide6** — Qt GUI 框架
- **openai** — DeepSeek API 客户端
- **SQLAlchemy** — ORM 数据存储
- **websockets** — WebSocket 服务端
- **pydantic-settings** — 配置管理
- **ddgs** — DuckDuckGo 搜索（备胎）
- **pyautogui** — 桌面自动化（备用）

---

## 📝 协议

MIT
