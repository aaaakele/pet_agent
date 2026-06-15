from __future__ import annotations

import json
import os
from datetime import datetime

from config.settings import settings
from utils.logger import logger


class MemoryManager:
    """Three-layer memory: MEMORY.md (personality) + knowledge.json (facts) + archive."""

    def __init__(self):
        self._memory_path = settings.MEMORY_PATH
        self._knowledge_path = settings.KNOWLEDGE_PATH
        self._archive_path = settings.ARCHIVE_PATH
        self._facts: dict[str, dict] = {}
        self._ensure_files()
        self._load_facts()

    # ------------------------------------------------------------------
    # File init
    # ------------------------------------------------------------------

    def _ensure_files(self):
        for path in [self._memory_path, self._knowledge_path, self._archive_path]:
            d = os.path.dirname(path)
            if d:
                os.makedirs(d, exist_ok=True)

        if not os.path.exists(self._memory_path):
            with open(self._memory_path, "w", encoding="utf-8") as f:
                f.write(_DEFAULT_MEMORY_MD)

        if not os.path.exists(self._knowledge_path):
            with open(self._knowledge_path, "w", encoding="utf-8") as f:
                json.dump({}, f, ensure_ascii=False, indent=2)

        if not os.path.exists(self._archive_path):
            # Create empty JSONL archive file
            with open(self._archive_path, "w", encoding="utf-8") as f:
                f.write("")

    # ------------------------------------------------------------------
    # MEMORY.md
    # ------------------------------------------------------------------

    def read_memory_md(self) -> str:
        try:
            with open(self._memory_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read {self._memory_path}: {e}")
            return ""

    def update_memory_md(self, content: str) -> None:
        with open(self._memory_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.info("MEMORY.md updated")

    # ------------------------------------------------------------------
    # knowledge.json
    # ------------------------------------------------------------------

    def _load_facts(self):
        try:
            with open(self._knowledge_path, "r", encoding="utf-8") as f:
                self._facts = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load {self._knowledge_path}: {e}")
            self._facts = {}

    def get_facts(self) -> dict:
        return self._facts

    def set_fact(self, key: str, value: str, source: str = "user") -> None:
        """Store a structured fact with metadata."""
        self._facts[key] = {
            "value": value,
            "source": source,
            "timestamp": datetime.now().isoformat(),
            "access_count": self._facts.get(key, {}).get("access_count", 0),
        }
        self._save_facts()

    def get_fact(self, key: str) -> str | None:
        fact = self._facts.get(key)
        if fact:
            fact["access_count"] = fact.get("access_count", 0) + 1
            fact["last_accessed"] = datetime.now().isoformat()
            self._save_facts()
            return fact["value"]
        return None

    def forget_fact(self, key: str) -> bool:
        if key in self._facts:
            del self._facts[key]
            self._save_facts()
            return True
        return False

    def _save_facts(self):
        with open(self._knowledge_path, "w", encoding="utf-8") as f:
            json.dump(self._facts, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Archive (JSONL conversation log)
    # ------------------------------------------------------------------

    def append_to_archive(self, entry: dict) -> None:
        entry["_archived_at"] = datetime.now().isoformat()
        with open(self._archive_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def search_archive(self, query: str, limit: int = 5) -> list[dict]:
        """Simple keyword search over archive entries."""
        results = []
        try:
            with open(self._archive_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    if query.lower() in line.lower():
                        results.append(json.loads(line))
                        if len(results) >= limit:
                            break
        except Exception:
            pass
        return results

    # ------------------------------------------------------------------
    # System prompt injection
    # ------------------------------------------------------------------

    def get_memory_context(self) -> str:
        """Build memory context for injection into system prompt."""
        parts = []

        # MEMORY.md
        memory_md = self.read_memory_md()
        if memory_md.strip():
            # Only include the header + first meaningful section to save tokens
            lines = memory_md.strip().split("\n")
            # Skip YAML frontmatter if present
            start = 0
            if lines and lines[0].strip() == "---":
                for i, line in enumerate(lines[1:], 1):
                    if line.strip() == "---":
                        start = i + 1
                        break
            parts.append("[长期记忆 MEMORY.md]\n" + "\n".join(lines[start:start + 30]))

        # knowledge.json facts
        if self._facts:
            facts_str = "\n".join(
                f"- {k}: {v['value']}" for k, v in sorted(self._facts.items())
            )
            parts.append(f"[已知事实]\n{facts_str}")

        return "\n\n".join(parts)


_DEFAULT_MEMORY_MD = """# 桌宠记忆文件

你可以编辑这个文件来设定桌宠的长期记忆和人格。

## 人格设定
我是一只友善的桌面宠物，喜欢帮助主人解决问题。
我的语气是轻松、温暖、略带俏皮的。

## 知道的事情
- 主人的操作系统是 Windows
- 工作目录通常在 D 盘

## 偏好
- 回复尽量简洁，不超过 200 字
- 处理文件时优先用 pathlib 而不是 os.path
- 搜索信息时优先从官方文档获取

## 约束
- 绝不透露自己是 AI
- 不执行危险命令
- 涉及删除操作时必须确认
"""
