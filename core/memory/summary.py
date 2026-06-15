"""Rolling summary compression for long conversations."""

from __future__ import annotations

from core.history.storage import MessageStore
from utils.logger import logger


class SummaryManager:
    """Detects when chat is getting too long and generates a rolling summary."""

    def __init__(self, store: MessageStore | None = None, llm_client=None):
        self._store: MessageStore = store or MessageStore()
        self._llm = llm_client

    def needs_summary(self, session_id: int, max_messages: int = 40, max_chars: int = 20000) -> bool:
        count = self._store.count_messages_in_session(session_id)
        if count >= max_messages:
            return True
        chars = self._store.total_chars_in_session(session_id)
        return chars >= max_chars

    async def compress(self, session_id: int, llm_client=None) -> str | None:
        """Generate a summary, archive older messages, insert summary into messages. Returns the summary or None."""
        client = llm_client or self._llm
        if client is None:
            logger.warning("No LLM client available for summary")
            return None

        messages = self._store.get_recent_messages(session_id, limit=200)
        if len(messages) < 10:
            return None

        # Build summary prompt
        lines = []
        for m in messages:
            role_name = {"user": "用户", "assistant": "桌宠", "tool": "工具", "system": "系统"}.get(m.role, m.role)
            lines.append(f"[{role_name}] {m.content[:300]}")

        prompt = (
            "请将以下对话历史压缩为一段简短摘要（200字以内），"
            "保留关键决策、重要事实和工具调用结果：\n\n"
            + "\n".join(lines[-100:])
            + "\n\n摘要："
        )

        try:
            summary = await client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            summary = f"[对话统计: {len(messages)}条消息]"

        if summary:
            # Archive older messages and insert summary
            # Mark messages before the midpoint as archived
            mid_id = messages[len(messages) // 2].id
            self._store.archive_messages_before(session_id, mid_id)
            self._store.insert_message(
                role="system",
                content=f"[对话摘要] {summary}",
                session_id=session_id,
                message_type="summary",
            )
            logger.info(f"Summary generated and archived older messages for session {session_id}")

        return summary
