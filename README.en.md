<div align="center">
  <h1>🐾 Desktop Pet Agent</h1>
  <p>A floating desktop pet powered by LLM — chat, search, control your PC, and remote access via QQ</p>
  <br>
  <img src="resources/wusaqi.gif" width="150" alt="Pet Avatar">
  <br><br>
  <p>
    <a href="README.md"><strong>🏠 Home</strong></a> ·
    <a href="README.zh.md"><strong>🇨🇳 中文</strong></a>
  </p>
  <br>
</div>

---

A cute floating desktop pet powered by LLM. It can chat, search the web, control your computer, and be remotely controlled via QQ.

## ✨ Features

### 🖥️ Desktop Pet
- **Floating window** — Frameless, transparent, always-on-top
- **Drag & move** — Hold and drag pet anywhere
- **Single-click bubble** — Quick input popup
- **Double-click chat** — Full conversation history dialog
- **Right-click menu** — Chat, change avatar, hide, quit
- **System tray** — Background operation with tray icon
- **Response bubble** — Reply popup with 5s auto-hide

### 🧠 AI Engine
- **DeepSeek LLM** — Pro and Flash models supported
- **Thinking mode** — Chain-of-thought for Flash model (toggleable)
- **Model switching** — Switch Pro/Flash on the fly via menu
- **ReAct loop** — Up to 5 rounds of tool-augmented reasoning
- **Context compression** — Auto-summarize to prevent overflow

### 🔧 Tools (17 total)

| Tool | Description |
|------|-------------|
| `read_file` / `write_file` | File I/O with auto-backup |
| `list_directory` / `grep_code` | Directory listing & code search |
| `web_search` | Multi-engine search (Bing → DDGS) |
| `fetch_url` | Web page content extraction |
| `get_system_info` | System information (OS, CPU, RAM, disk) |
| `run_command` | Shell command execution |
| `open_app` | Launch 30+ local applications |
| `open_url` | Open URL in default browser |
| `system_control` | Lock / Sleep / Volume control |
| `schedule_reminder` | Natural language reminders |
| `research_trends` | 30-day multi-platform trend research |
| `web_open` | Search & open result links directly |
| `click_ui` / `type_keys` | Desktop UI automation |

### 🌐 Web Capabilities
- **Fallback chain** — cn.bing.com → www.bing.com → DuckDuckGo
- **Bilibili API** — Search and open top video by play count
- **last30days engine** — Aggregate 17 platforms (Reddit, X, YouTube, HN...)
- **Search cache** — 5-minute TTL deduplication
- **Connection pooling** — Shared HTTP session for performance

### 📱 QQ Remote Control
- **WebSocket server** — OneBot v11 protocol (port 3001)
- **HTTP API** — RESTful interface (port 3002)
- **QQ whitelist** — Only authorized QQ numbers can control
- **NapCat integration** — QR code login, auto message forwarding

### ⏰ Task Scheduling
- Natural language time parsing ("remind me in 5 minutes")
- Recurring task support
- Push notification via pet response bubble

### 💾 Storage
- **SQLite** — Messages, tool runs, scheduled tasks
- **Auto migration** — Schema upgrades on startup
- **Context archiving** — Auto-summary for long conversations

---

## 🏗️ Project Structure

```
pet_agent/
├── config/
│   ├── settings.py       # Configuration (pydantic-settings)
│   └── .env.example      # Environment variable template
├── core/
│   ├── agent/
│   │   ├── executor.py   # ReAct agent main loop
│   │   └── tools.py      # 17 tool implementations
│   ├── history/
│   │   └── storage.py    # SQLite storage layer
│   ├── llm/
│   │   └── client.py     # DeepSeek API client
│   ├── memory/
│   │   ├── manager.py    # Memory management
│   │   └── summary.py    # Conversation summarizer
│   ├── pet/
│   │   ├── window.py     # Floating window widget
│   │   ├── chat.py       # Chat dialog
│   │   ├── bubble.py     # Quick input & response bubble
│   │   ├── tray.py       # System tray icon
│   │   ├── icons.py      # Avatar management
│   │   └── model_switcher.py  # Model switch menu
│   ├── qq/
│   │   ├── bot.py        # QQ Bot (WS + HTTP servers)
│   │   └── onebot.py     # OneBot v11 protocol parser
│   └── tasks/
│       └── scheduler.py  # Task scheduler
├── main.py               # Application entry point
├── resources/            # Image assets
└── requirements.txt      # Python dependencies
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure

```bash
cp config/.env.example config/.env
# Edit config/.env, fill in your DeepSeek API Key
```

### 3. Run

```bash
python main.py
```

| Action | Result |
|--------|--------|
| Double-click pet | Open chat window |
| Single-click pet | Quick input bubble |
| Right-click pet | Context menu / model switch |

### 4. QQ Remote Access (Optional)

**NapCat method:**
1. Download NapCatQQ to `D:\NapCat`
2. Run `D:\NapCat\启动NapCat.bat`
3. Scan QR code to login, auto-connects to pet

**HTTP bridge:**
```bash
curl -X POST http://127.0.0.1:3002/qq_message \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123456, "message": "hello"}'
```

---

## ⚙️ Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPSEEK_API_KEY` | — | DeepSeek API key |
| `DEEPSEEK_MODEL` | `deepseek-v4-flash` | Model name |
| `THINKING_ENABLED` | `true` | Enable thinking mode |
| `TOOL_EXECUTION_TIMEOUT` | `60` | Tool timeout (seconds) |
| `QQ_ENABLED` | `false` | Enable QQ Bot |
| `QQ_WS_PORT` | `3001` | WebSocket port |
| `QQ_HTTP_PORT` | `3002` | HTTP API port |
| `QQ_WHITELIST` | — | Allowed QQ numbers (comma-separated) |

---

## 🧩 Architecture

```
User Input → AgentExecutor (ReAct Loop, max 5 rounds)
                │
                ├─▶ DeepSeek API → decide tool calls
                │
                ├─▶ Parallel tool execution (asyncio.gather)
                │    ├─ Local (file, command, system)
                │    ├─ Web (search, fetch, Bilibili API)
                │    └─ Remote (QQ, HTTP)
                │
                └─▶ Response → Bubble / Chat Window / QQ
```

### Concurrency Model
- **Main thread** — Qt GUI event loop
- **AgentWorker** — QThread per conversation, own asyncio loop
- **TaskScheduler** — Persistent QThread, 15s polling interval
- **QQBotThread** — Persistent QThread, WS + HTTP dual servers

---

## 📦 Dependencies

| Package | Purpose |
|---------|---------|
| `PySide6` | Qt GUI framework |
| `openai` | DeepSeek API client |
| `SQLAlchemy` | ORM & SQLite storage |
| `websockets` | WebSocket server |
| `pydantic-settings` | Configuration management |
| `ddgs` | DuckDuckGo search (fallback) |
| `pyautogui` | Desktop automation |

---

## 📄 License

MIT
