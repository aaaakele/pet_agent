<div align="center">
  <h1>🐾 Desktop Pet Agent</h1>
  <p><em>浮窗桌宠 · LLM 智能助手 · 本地工具 · QQ 远程控制</em></p>
  <p><em>A floating desktop pet with LLM AI, local tools, and QQ remote control</em></p>
  <br>
  <img src="resources/wusaqi.gif" width="150" alt="Pet Avatar">
  <br><br>
</div>

---

<div align="center">
  <h2>📖 中文</h2>
</div>

一只浮在桌面上的可爱宠物，内置 LLM 智能助手，能聊天、能搜索、能控制电脑、能通过 QQ 远程操控。

## ✨ 功能一览

### 🖥️ 桌面宠物
- **浮窗显示** — 无边框、透明背景、置顶显示
- **拖拽移动** — 按住宠物随意拖动位置
- **单击气泡** — 单击弹出快捷输入框
- **双击聊天** — 双击打开完整聊天窗口
- **右键菜单** — 聊天、换头像、隐藏、退出
- **系统托盘** — 右下角托盘图标
- **响应气泡** — 回复以气泡形式弹出，5秒自动消失

### 🧠 AI 对话引擎
- **DeepSeek 大模型** — 支持 Pro 和 Flash 双模型
- **Thinking 模式** — Flash 模型支持思维链（可开关）
- **模型切换** — 右键菜单一键切换 Pro / Flash
- **ReAct 循环** — 最多 5 轮工具调用，自动推理执行
- **上下文压缩** — 超阈值自动摘要，避免长对话溢出

### 🔧 工具列表（17个）

| 工具 | 说明 |
|------|------|
| `read_file` / `write_file` | 读写文件（带自动备份） |
| `list_directory` / `grep_code` | 目录浏览与代码搜索 |
| `web_search` | 多引擎搜索（Bing → DDGS） |
| `fetch_url` | 网页内容抓取 |
| `get_system_info` | 系统信息获取 |
| `run_command` | Shell 命令执行 |
| `open_app` | 打开本地应用（30+ 常用软件） |
| `open_url` | 浏览器打开网址 |
| `system_control` | 锁定 / 睡眠 / 音量 |
| `schedule_reminder` | 定时提醒（自然语言解析） |
| `research_trends` | 30天热点聚合研究 |
| `web_open` | 搜索并直接打开结果链接 |
| `click_ui` / `type_keys` | 桌面 UI 自动化 |

### 🌐 网络能力
- **多引擎降级** — cn.bing.com → www.bing.com → DuckDuckGo
- **B站 API 集成** — 按播放量排序直接打开视频
- **last30days 引擎** — 跨 Reddit、X、YouTube 等 17 平台搜索
- **搜索缓存** — 5 分钟 TTL 避免重复
- **连接池** — 共享 HTTP 连接复用

### 📱 QQ 远程控制
- **WebSocket 服务** — OneBot v11 协议（端口 3001）
- **HTTP API** — REST 接口（端口 3002）
- **QQ 白名单** — 仅允许指定 QQ 号操作
- **NapCat 集成** — 扫码登录 QQ，消息自动转发

### ⏰ 定时任务
- 自然语言设定（"5分钟后提醒我"）
- 循环提醒支持
- 到达时气泡推送

### 💾 数据存储
- **SQLite** — 对话历史、工具记录、任务持久化
- **自动迁移** — Schema 自动升级
- **消息归档** — 超限自动摘要压缩

---

## 🏗️ 项目结构 / Project Structure

```
pet_agent/
├── config/
│   ├── settings.py       # 配置项 / Settings (pydantic)
│   └── .env.example      # 环境变量模板 / Env template
├── core/
│   ├── agent/
│   │   ├── executor.py   # ReAct agent 主循环
│   │   └── tools.py      # 17个工具实现
│   ├── history/
│   │   └── storage.py    # SQLite 存储
│   ├── llm/
│   │   └── client.py     # DeepSeek API 客户端
│   ├── memory/
│   │   ├── manager.py    # 记忆管理
│   │   └── summary.py    # 对话摘要
│   ├── pet/
│   │   ├── window.py     # 悬浮窗口
│   │   ├── chat.py       # 聊天对话框
│   │   ├── bubble.py     # 快捷气泡
│   │   ├── tray.py       # 系统托盘
│   │   ├── icons.py      # 头像管理
│   │   └── model_switcher.py  # 模型切换
│   ├── qq/
│   │   ├── bot.py        # QQ Bot (WS + HTTP)
│   │   └── onebot.py     # OneBot v11 协议
│   └── tasks/
│       └── scheduler.py  # 定时任务
├── main.py               # 入口
├── resources/            # 图片资源
└── requirements.txt      # Python 依赖
```

---

## 🚀 快速开始 / Quick Start

### 1. 安装依赖 / Install

```bash
pip install -r requirements.txt
```

### 2. 配置 / Configure

```bash
cp config/.env.example config/.env
# 编辑 config/.env，填入你的 DeepSeek API Key
# Edit config/.env, fill in your DeepSeek API Key
```

### 3. 启动 / Run

```bash
python main.py
```

- **双击** 宠物 → 聊天
- **单击** 宠物 → 快捷提问
- **右键** 宠物 → 菜单 / 模型切换

### 4. QQ 远程连接（可选）

**NapCat 方案：**
1. 下载 NapCatQQ Shell 版到 `D:\NapCat`
2. 双击 `D:\NapCat\启动NapCat.bat`
3. 扫码登录 QQ，自动连接桌宠

**HTTP 桥接：**
```bash
curl -X POST http://127.0.0.1:3002/qq_message \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123456, "message": "你好"}'
```

---

## ⚙️ 配置说明 / Configuration

| 变量 / Variable | 默认值 / Default | 说明 / Description |
|----------------|-----------------|-------------------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `THINKING_ENABLED` | `true` | Thinking 模式 |
| `TOOL_EXECUTION_TIMEOUT` | `60` | 工具超时(秒) |
| `QQ_ENABLED` | `false` | QQ Bot 开关 |
| `QQ_WS_PORT` | `3001` | WebSocket 端口 |
| `QQ_HTTP_PORT` | `3002` | HTTP API 端口 |
| `QQ_WHITELIST` | — | 允许的 QQ 号 |

---

<div align="center">
  <h2>🌍 English</h2>
</div>

A cute floating desktop pet powered by LLM. It can chat, search the web, control your computer, and be remotely operated via QQ.

## ✨ Features

### 🖥️ Desktop Pet
- **Floating window** — Frameless, transparent, always-on-top
- **Drag & drop** — Move pet anywhere on screen
- **Quick bubble** — Single-click for fast input
- **Chat dialog** — Double-click for full conversation history
- **System tray** — Background operation with right-click menu
- **Response bubble** — Auto-hiding speech bubble (5s)

### 🧠 AI Engine
- **DeepSeek LLM** — Pro and Flash models supported
- **Thinking mode** — Chain-of-thought for Flash model
- **Model switching** — Switch between Pro/Flash on the fly
- **ReAct loop** — Up to 5 rounds of tool-augmented reasoning
- **Context compression** — Auto-summarize long conversations

### 🔧 Tools (17 total)

| Tool | Description |
|------|-------------|
| `read_file` / `write_file` | File I/O with auto-backup |
| `list_directory` / `grep_code` | Directory listing & code search |
| `web_search` | Multi-engine search (Bing → DDGS) |
| `fetch_url` | Web page content extraction |
| `get_system_info` | System information |
| `run_command` | Shell command execution |
| `open_app` | Launch 30+ local applications |
| `open_url` | Open URL in browser |
| `system_control` | Lock / Sleep / Volume |
| `schedule_reminder` | Natural language reminders |
| `research_trends` | 30-day multi-platform trend research |
| `web_open` | Search & open result links directly |
| `click_ui` / `type_keys` | Desktop UI automation |

### 🌐 Web Capabilities
- **Fallback chain** — cn.bing.com → www.bing.com → DuckDuckGo
- **Bilibili API** — Search and open top videos by play count
- **last30days engine** — Aggregate 17 platforms (Reddit, X, YouTube, HN...)
- **Search cache** — 5-minute TTL deduplication
- **Connection pooling** — Shared HTTP session reuse

### 📱 QQ Remote Control
- **WebSocket server** — OneBot v11 protocol (port 3001)
- **HTTP API** — RESTful interface (port 3002)
- **Whitelist** — Only authorized QQ numbers
- **NapCat integration** — QR code login, auto message forwarding

### ⏰ Task Scheduling
- Natural language time parsing ("remind me in 5 minutes")
- Recurring task support
- Push notification via pet bubble

### 💾 Storage
- **SQLite** — Messages, tool runs, tasks persistence
- **Auto migration** — Schema updates on startup
- **Context archiving** — Auto-summary for long sessions

---

## 🧩 Architecture / 技术架构

```
User Input → AgentExecutor (ReAct Loop, max 5 rounds)
                │
                ├─▶ DeepSeek API → decide tool calls
                │
                ├─▶ Parallel tool execution (asyncio.gather)
                │    ├─ Local (file, command, system)
                │    ├─ Web (search, fetch, API)
                │    └─ Remote (QQ, HTTP)
                │
                └─▶ Response → Bubble / Chat / QQ
```

### Concurrency Model / 并发模型
- **Main thread** — Qt GUI event loop
- **AgentWorker** — QThread per conversation, own asyncio loop
- **TaskScheduler** — Persistent QThread, 15s polling
- **QQBotThread** — Persistent QThread, WS + HTTP servers

---

## 📦 Dependencies / 依赖

| Package | Purpose |
|---------|---------|
| `PySide6` | Qt GUI framework |
| `openai` | DeepSeek API client |
| `SQLAlchemy` | ORM & SQLite |
| `websockets` | WebSocket server |
| `pydantic-settings` | Configuration management |
| `ddgs` | DuckDuckGo search (fallback) |
| `pyautogui` | Desktop automation |

---

## 📄 License / 协议

MIT
