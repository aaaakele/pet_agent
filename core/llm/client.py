from __future__ import annotations

import asyncio
from openai import AsyncOpenAI, BadRequestError
from config.settings import settings, MODEL_PRO
from utils.logger import logger


class DeepSeekClient:
    def __init__(self):
        self._client = AsyncOpenAI(
            api_key=settings.DEEPSEEK_API_KEY,
            base_url=settings.DEEPSEEK_BASE_URL,
            timeout=float(settings.RESPONSE_TIMEOUT),
        )
        self._pending_reasoning: str | None = None

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    @property
    def is_thinking(self) -> bool:
        """Whether thinking mode is currently active."""
        if settings.DEEPSEEK_MODEL == MODEL_PRO:
            return False
        return settings.THINKING_ENABLED

    def clear_reasoning(self) -> None:
        self._pending_reasoning = None

    def inject_reasoning(self, messages: list[dict]) -> list[dict]:
        """Inject pending reasoning_content into the last assistant message.

        DeepSeek thinking mode requires that reasoning_content returned by the
        API is passed back verbatim on the next request.  When thinking is
        disabled we deliberately skip this so the API never sees stale
        reasoning and doesn't demand it back.
        """
        if not self.is_thinking or not self._pending_reasoning or not messages:
            return messages
        rc = self._pending_reasoning
        self._pending_reasoning = None
        for m in reversed(messages):
            if m.get("role") == "assistant":
                if m.get("reasoning_content"):
                    break  # already present (loaded from DB or appended inline)
                m["reasoning_content"] = rc
                break
        return messages

    # ------------------------------------------------------------------
    # Low-level API calls
    # ------------------------------------------------------------------

    @staticmethod
    def _is_non_retryable(error: Exception) -> bool:
        """400-level errors are parameter errors — retrying won't help."""
        if isinstance(error, BadRequestError):
            return True
        msg = str(error)
        return "400" in msg or "invalid_request_error" in msg

    async def chat(self, messages: list[dict], temperature: float = 0.8) -> str:
        """Simple chat without tools. Returns text response."""
        last_error = None
        for attempt in range(settings.RESPONSE_RETRY + 1):
            try:
                response = await self._client.chat.completions.create(
                    model=settings.DEEPSEEK_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=512,
                    stream=False,
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                if self._is_non_retryable(e):
                    break
                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")
                if attempt < settings.RESPONSE_RETRY:
                    await asyncio.sleep(2 ** attempt)
        raise last_error or RuntimeError("All LLM attempts failed")

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.8,
    ) -> dict:
        """Call LLM with tool definitions. Returns full API response dict."""
        last_error = None
        for attempt in range(settings.RESPONSE_RETRY + 1):
            try:
                kwargs = {
                    "model": settings.DEEPSEEK_MODEL,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": 768,
                    "stream": False,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = tool_choice

                response = await self._client.chat.completions.create(**kwargs)

                # Capture reasoning from the raw Pydantic model BEFORE model_dump,
                # because model_dump may drop fields unknown to the OpenAI SDK.
                raw_msg = response.choices[0].message
                raw_reasoning = getattr(raw_msg, "reasoning_content", None)

                data = response.model_dump()
                choice = data.get("choices", [{}])[0]
                msg = choice.get("message", {})

                # Re-inject reasoning into the dict if it was dropped by model_dump
                if raw_reasoning and not msg.get("reasoning_content"):
                    msg["reasoning_content"] = raw_reasoning

                if self.is_thinking and raw_reasoning:
                    self._pending_reasoning = raw_reasoning
                elif not self.is_thinking and "reasoning_content" in msg:
                    del msg["reasoning_content"]

                return data
            except Exception as e:
                last_error = e
                if self._is_non_retryable(e):
                    break  # 400 errors: fail fast, no retry
                logger.warning(f"LLM tool call attempt {attempt + 1} failed: {e}")
                if attempt < settings.RESPONSE_RETRY:
                    await asyncio.sleep(2 ** attempt)
        raise last_error or RuntimeError("All LLM attempts failed")
