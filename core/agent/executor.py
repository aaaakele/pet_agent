from __future__ import annotations

import asyncio
import json
import time

from config.settings import settings
from core.llm.client import DeepSeekClient
from core.history.storage import MessageStore
from core.history.retriever import HistoryRetriever
from core.agent.tools import ToolRegistry, ToolResult
from utils.logger import logger


class AgentExecutor:

    MAX_TOOL_ROUNDS = 5

    def __init__(self, store: MessageStore | None = None):
        self._llm = DeepSeekClient()
        self._store = store or MessageStore()
        self._retriever = HistoryRetriever()
        self._tools = ToolRegistry()
        ToolRegistry._store = self._store  # inject store for scheduler tools
        self._session = self._store.get_latest_session()
        self._memory_mgr = None

    @property
    def session_id(self) -> int:
        return self._session.id

    def set_memory_manager(self, mgr):
        self._memory_mgr = mgr

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    async def run(self, user_input: str) -> str:
        # Handle "clear" command — wipe all history
        if user_input.strip().lower() == "clear":
            self._store.clear_session(self.session_id)
            self._session = self._store.create_session()
            return "已清空所有对话历史，让我们重新开始吧～"

        # 1. Recent history (skip RAG for speed)
        history = self._store.get_recent_messages(self.session_id, limit=20)

        # 2. Build system prompt
        system = self._build_system([])

        # 3. Build message list — only last 8 text messages
        messages = [{"role": "system", "content": system}]
        count = 0
        for msg in reversed(history):
            if msg.message_type == "text" and count < 8:
                entry = {"role": msg.role, "content": msg.content}
                if msg.reasoning_content:
                    entry["reasoning_content"] = msg.reasoning_content
                messages.insert(1, entry)
                count += 1
        messages.append({"role": "user", "content": user_input})

        # Save user message
        self._store.insert_message(
            role="user", content=user_input, session_id=self.session_id, message_type="text"
        )

        # 5. ReAct loop
        self._llm.clear_reasoning()
        tool_defs = self._tools.get_definitions()
        search_count = 0   # per-run counter

        for round_idx in range(self.MAX_TOOL_ROUNDS):
            # DeepSeek thinking mode: must pass reasoning_content back
            messages = self._llm.inject_reasoning(messages)

            # Debug: log reasoning status on assistant messages
            _dump_reasoning_status(messages, round_idx)

            try:
                response = await self._llm.chat_with_tools(
                    messages=messages, tools=tool_defs,
                )
            except Exception as e:
                logger.error(f"LLM call failed: {e}")
                return "抱歉，我现在有点迷糊，稍等一下再试试～"

            choice = response.get("choices", [{}])[0]
            msg = choice.get("message", {})
            reasoning = msg.get("reasoning_content")

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                reply = msg.get("content", "") or "嗯..."
                self._store.insert_message(
                    role="assistant", content=reply, session_id=self.session_id,
                    message_type="text", reasoning_content=reasoning,
                )
                return reply

            # -- Tool calls --
            self._store.insert_message(
                role="assistant",
                content=msg.get("content") or "",
                session_id=self.session_id,
                message_type="tool_call",
                reasoning_content=reasoning,
            )
            assistant_msg = {
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
            }
            if reasoning:
                assistant_msg["reasoning_content"] = reasoning
            messages.append(assistant_msg)

            # Parse args first (fast, sequential)
            parsed: list[tuple[dict, str, dict]] = []
            for tc in tool_calls:
                func_name = tc["function"]["name"]
                try:
                    func_args = json.loads(tc["function"]["arguments"])
                except json.JSONDecodeError:
                    func_args = {}
                parsed.append((tc, func_name, func_args))

            # Execute all tools in parallel
            async def _run_one(name: str, args: dict):
                t0 = time.time()
                try:
                    result: ToolResult = await asyncio.wait_for(
                        self._tools.execute(name, args),
                        timeout=settings.TOOL_EXECUTION_TIMEOUT,
                    )
                except asyncio.TimeoutError:
                    result = ToolResult(
                        f"工具 '{name}' 执行超时（{settings.TOOL_EXECUTION_TIMEOUT}s）",
                        is_error=True,
                    )
                elapsed = (time.time() - t0) * 1000
                return result, elapsed

            results = await asyncio.gather(
                *[_run_one(name, args) for _, name, args in parsed]
            )

            for (tc, func_name, func_args), (result, elapsed) in zip(parsed, results):
                if func_name == "web_search":
                    search_count += 1

                # Log tool run
                self._store.insert_tool_run(
                    tool_name=func_name,
                    args=func_args,
                    result_content=result.content,
                    is_error=result.is_error,
                    metadata=result.metadata,
                    duration_ms=elapsed,
                    session_id=self.session_id,
                )

                # If result is an artifact (webpage, search, file), save it
                if func_name in ("web_search", "fetch_url") and not result.is_error:
                    self._store.insert_artifact(
                        artifact_type="webpage" if func_name == "fetch_url" else "search_result",
                        url_or_path=result.metadata.get("url", result.metadata.get("query", "")),
                        content=result.content[:20000],
                        metadata=result.metadata,
                        session_id=self.session_id,
                    )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": f"[ERROR] {result.content}" if result.is_error else result.content,
                })
                self._store.insert_message(
                    role="tool",
                    content=result.content,
                    session_id=self.session_id,
                    message_type="tool_result",
                )

            # Cap searches: if LLM keeps re-searching, force it to answer now
            if search_count >= 2:
                messages.append({
                    "role": "user",
                    "content": "[系统提示] 你已经搜索了足够多次，请直接基于已有结果回答用户的问题，不要再调用 web_search。",
                })

            # -- Rolling summary check --
            await self._maybe_summarize()

        return "这个问题有点复杂，让我想想再回答你～"

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    async def _maybe_summarize(self) -> None:
        msg_count = self._store.count_messages_in_session(self.session_id)
        total_chars = self._store.total_chars_in_session(self.session_id)
        if msg_count < settings.SUMMARY_THRESHOLD_MESSAGES and total_chars < settings.SUMMARY_THRESHOLD_CHARS:
            return

        logger.info(f"Compressing context: {msg_count} msgs, {total_chars} chars")
        try:
            summary = await self._generate_summary()
            if summary:
                self._store.insert_message(
                    role="system", content=summary,
                    session_id=self.session_id, message_type="summary",
                )
                logger.info("Context compressed")
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")

    async def _generate_summary(self) -> str:
        messages = self._store.get_recent_messages(self.session_id, limit=100)
        if len(messages) < 10:
            return ""

        lines = [f"{m.role}: {m.content[:200]}" for m in messages]
        prompt = (
            "请将以下对话历史压缩为一段简短摘要（200字以内），保留关键决策、重要事实和工具调用结果：\n\n"
            + "\n".join(lines[-80:])
            + "\n\n摘要："
        )

        try:
            return await self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
        except Exception:
            # Graceful: generate a simple statistical summary
            user_msgs = sum(1 for m in messages if m.role == "user")
            asst_msgs = sum(1 for m in messages if m.role == "assistant")
            tool_msgs = sum(1 for m in messages if m.role == "tool")
            return f"对话统计: {len(messages)} 条消息 ({user_msgs} 用户, {asst_msgs} 助手, {tool_msgs} 工具)"

    # ------------------------------------------------------------------
    # System prompt
    # ------------------------------------------------------------------

    def _build_system(self, rag_context: list[str]) -> str:
        parts = [settings.AGENT_SYSTEM_PROMPT]

        # Memory from MEMORY.md + knowledge.json
        if self._memory_mgr:
            mem = self._memory_mgr.get_memory_context()
            if mem:
                parts.append(f"\n{mem}")

        if rag_context:
            parts.append("\n以下是记忆中的相关内容（仅供参考）：")
            for i, ctx in enumerate(rag_context, 1):
                parts.append(f"{i}. {ctx}")

        return "\n".join(parts)


# ------------------------------------------------------------------
# Debug helper
# ------------------------------------------------------------------

def _dump_reasoning_status(messages: list[dict], round_idx: int) -> None:
    """Log whether each assistant msg carries reasoning_content."""
    for i, m in enumerate(messages):
        if m.get("role") == "assistant":
            has_rc = "reasoning_content" in m
            has_tc = "tool_calls" in m
            logger.debug(
                f"[ReAct round {round_idx}] msg[{i}] assistant: "
                f"has_reasoning={has_rc}, has_tool_calls={has_tc}, "
                f"content_len={len(m.get('content', '') or '')}"
            )
