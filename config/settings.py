from __future__ import annotations

from pydantic_settings import BaseSettings

# Available model presets
MODEL_PRO = "deepseek-v4-pro"
MODEL_FLASH = "deepseek-v4-flash"


class Settings(BaseSettings):
    # DeepSeek API
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = MODEL_FLASH

    # Thinking mode (only effective for Flash; Pro ignores it)
    THINKING_ENABLED: bool = True

    # Context
    RESPONSE_TIMEOUT: int = 15
    RESPONSE_RETRY: int = 2
    TOOL_EXECUTION_TIMEOUT: int = 60  # max seconds per tool call

    # Storage paths
    DB_PATH: str = "storage/chat.db"
    CHROMA_PATH: str = "storage/chroma_db"

    # History
    MAX_HISTORY: int = 50

    # Desktop pet
    PET_AVATAR_PATH: str = "resources/wusaqi.gif"
    AGENT_SYSTEM_PROMPT: str = (
        "你是一只可爱的桌面宠物助手，住在用户的电脑里。"
        "你可以读写文件、查看目录、搜索代码、搜索网页、获取系统信息。"
        "你还能控制用户的电脑：打开浏览器/应用（open_app）、打开网址（open_url）、"
        "锁定/睡眠/调音量（system_control）。"
        "找视频或打开搜索结果时，务必使用 web_open 工具——它直接解析网页HTML找到目标链接并打开，"
        "比打开页面再点击浏览器界面可靠得多。比如用户说'打开B站xxx视频'，用 web_open(site=bilibili)。"
        "如果用户问最近的热门话题、趋势、新闻，优先使用 research_trends 工具进行深度研究。"
        "拿到 research_trends 或 web_search 返回的结果后，直接基于结果回答，不要再继续搜索。"
        "回复必须极其简洁，控制在1-3句话以内，像朋友聊天一样自然。"
        "不要客套、不要解释、不要废话，直接回答问题。"
        "不要说自己是AI，你就是一只桌宠。"
        "如果用户要求搜索信息，使用 web_search 工具，一次搜索足够，不要用不同关键词重复搜索同一个问题。"
    )

    # Memory
    MEMORY_PATH: str = "MEMORY.md"
    KNOWLEDGE_PATH: str = "knowledge.json"
    ARCHIVE_PATH: str = "data/conversation_archive.jsonl"

    # Summary
    SUMMARY_THRESHOLD_MESSAGES: int = 40
    SUMMARY_THRESHOLD_CHARS: int = 20000

    # --- QQ Bot (OneBot v11 via LLOneBot) ---
    QQ_ENABLED: bool = False
    QQ_WS_HOST: str = "127.0.0.1"
    QQ_WS_PORT: int = 3001
    QQ_WHITELIST: str = ""  # comma-separated QQ numbers, e.g. "123456789,987654321"
    QQ_HTTP_PORT: int = 3002  # HTTP API port for message forwarding
    QQ_ACCESS_TOKEN: str = ""

    @property
    def qq_whitelist_set(self) -> set[int]:
        """Parse whitelist string into a set of integers."""
        if not self.QQ_WHITELIST.strip():
            return set()
        return {int(x.strip()) for x in self.QQ_WHITELIST.split(",") if x.strip()}

    model_config = {"env_file": "config/.env", "env_file_encoding": "utf-8"}


settings = Settings()
