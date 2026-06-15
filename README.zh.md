<div align="center">
  <h1>🐾 Desktop Pet Agent</h1>
  <p>浮窗桌宠 · LLM 智能助手 · 本地工具 · QQ 远程控制</p>
  <br>
  <img src="resources/wusaqi.gif" width="150" alt="Pet Avatar">
  <br><br>
  <p>
    <a href="README.md"><strong>🏠 首页</strong></a> ·
    <a href="README.en.md"><strong>🇬🇧 English</strong></a>
  </p>
  <br>
</div>

---

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

## 🏗️ 项目结构

```
pet_agent/
├── config/
│   ├── settings.py       # 配置项 (pydantic-settings)
│   └── .env.example      # 环境变量模板
├── core/
│   ├── agent/
│   │   ├── executor.py   # ReAct agent 主循环
│   │   └── tools.py      # 17个工具实现
│   ├── history/
│   │   └── storage.py    # SQLite 存储层
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
│   │   └── model_switcher.py  # 模型切换菜单
│   ├── qq/
│   │   ├── bot.py        # QQ Bot (WS + HTTP 双协议)
│   │   └── onebot.py     # OneBot v11 协议解析
│   └── tasks/
│       └── scheduler.py  # 定时任务调度器
├── main.py               # 应用入口
├── resources/            # 图片资源
├── storage/              # SQLite 数据文件
├── .agents/skills/       # last30days 技能插件
└── requirements.txt      # Python 依赖
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp config/.env.example config/.env
# 编辑 config/.env，填入你的 DeepSeek API Key
```

### 3. 启动

```bash
python main.py
```

| 操作 | 效果 |
|------|------|
| 双击宠物 | 打开聊天窗口 |
| 单击宠物 | 快捷提问气泡 |
| 右键宠物 | 菜单 / 模型切换 |

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

## ⚙️ 配置说明

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API 密钥 |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | 模型名称 |
| `THINKING_ENABLED` | `true` | 是否启用 Thinking 模式 |
| `TOOL_EXECUTION_TIMEOUT` | `60` | 单次工具调用超时(秒) |
| `QQ_ENABLED` | `false` | 启用 QQ Bot |
| `QQ_WS_PORT` | `3001` | WebSocket 端口 |
| `QQ_HTTP_PORT` | `3002` | HTTP API 端口 |
| `QQ_WHITELIST` | — | 允许的 QQ 号（逗号分隔） |

---

## 🧩 技术架构

```
用户输入 → AgentExecutor (ReAct 循环，最多 5 轮)
                │
                ├─▶ DeepSeek API → 判断是否调用工具
                │
                ├─▶ 并行执行工具 (asyncio.gather)
                │    ├─ 本地工具（文件/命令/系统）
                │    ├─ 搜索工具（Bing/DDGS/B站API）
                │    └─ 远程工具（QQ/HTTP）
                │
                └─▶ 生成回复 → 气泡 / 聊天 / QQ
```

### 并发模型
- **主线程** — Qt GUI 事件循环
- **AgentWorker** — 每次对话创建 QThread，独立 asyncio 事件循环
- **TaskScheduler** — 持久 QThread，15 秒轮询定时任务
- **QQBotThread** — 持久 QThread，运行 WS + HTTP 双协议服务

---

## 📦 依赖

| 包 | 用途 |
|----|------|
| `PySide6` | Qt GUI 框架 |
| `openai` | DeepSeek API 客户端 |
| `SQLAlchemy` | ORM 数据存储 |
| `websockets` | WebSocket 服务端 |
| `pydantic-settings` | 配置管理 |
| `ddgs` | DuckDuckGo 搜索（备胎） |
| `pyautogui` | 桌面自动化 |

---

## 📄 协议

MIT
