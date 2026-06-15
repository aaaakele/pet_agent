"""QQ Bot integration via OneBot v11 WebSocket and HTTP protocols.

The bot supports TWO connection modes:
  A) WebSocket (ws://127.0.0.1:3001)  — reverse WS for LLOneBot
  B) HTTP   (http://127.0.0.1:3002)  — POST /qq_message for any HTTP bridge

Either or both can be used simultaneously.
"""

from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urlparse, parse_qs

from PySide6.QtCore import QThread, Signal

from websockets.asyncio.server import serve as ws_serve
from websockets.exceptions import ConnectionClosed

from config.settings import settings
from core.agent.executor import AgentExecutor
from core.qq.onebot import (
    PrivateMessageEvent,
    GroupMessageEvent,
    parse_event,
    send_private_msg,
    send_group_msg,
)

logger = logging.getLogger(__name__)

HTTP_PORT = settings.QQ_HTTP_PORT or 3002


# ---------------------------------------------------------------------------
# QQBot — multi-protocol async server
# ---------------------------------------------------------------------------

class QQBot:
    """Async server bridging QQ messages to the pet agent.

    Accepts messages via:
      - WebSocket reverse connection (LLOneBot / any OneBot WS client)
      - HTTP POST /qq_message  (for HTTP-only bridges / testing)
    """

    def __init__(self, agent: AgentExecutor):
        self._agent = agent
        self._ws = None
        self._stop_event = asyncio.Event()
        self._task_queue: asyncio.Queue = asyncio.Queue()
        self._processor_task = None
        self._http_server = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def start(self):
        """Start both WebSocket and HTTP servers."""
        self._processor_task = asyncio.create_task(self._process_queue())

        host = settings.QQ_WS_HOST or "127.0.0.1"
        ws_port = settings.QQ_WS_PORT or 3001

        # Start WebSocket server
        async def _run_ws():
            async with ws_serve(self._on_ws_connect, host, ws_port) as server:
                logger.info(f"QQ Bot WS listening on ws://{host}:{ws_port}")
                await self._stop_event.wait()

        # Start HTTP server
        async def _run_http():
            self._http_server = await asyncio.start_server(
                self._on_http_connect, host, HTTP_PORT,
            )
            logger.info(f"QQ Bot HTTP listening on http://{host}:{HTTP_PORT}/qq_message")
            async with self._http_server:
                await self._http_server.serve_forever()

        # Run both concurrently
        await asyncio.gather(
            _run_ws(),
            _run_http(),
        )

    async def stop(self):
        """Graceful shutdown."""
        self._stop_event.set()
        if self._processor_task:
            self._processor_task.cancel()
        if self._ws:
            await self._ws.close()
        if self._http_server:
            self._http_server.close()

    # ------------------------------------------------------------------
    # WebSocket handler
    # ------------------------------------------------------------------

    async def _on_ws_connect(self, ws):
        """Handle a new WebSocket connection."""
        peer = ws.remote_address
        logger.info(f"QQ Bot WS client connected from {peer}")

        old = self._ws
        self._ws = ws
        if old:
            await old.close()

        try:
            async for raw in ws:
                if self._stop_event.is_set():
                    break
                await self._on_raw(raw)
        except ConnectionClosed:
            logger.info("QQ Bot WS client disconnected")
        except Exception as e:
            logger.warning(f"QQ Bot WS error: {e}")
        finally:
            if self._ws is ws:
                self._ws = None

    # ------------------------------------------------------------------
    # HTTP handler
    # ------------------------------------------------------------------

    async def _on_http_connect(self, reader, writer):
        """Handle an HTTP connection."""
        try:
            raw_request = await asyncio.wait_for(reader.read(65536), timeout=10.0)
            request = raw_request.decode("utf-8", errors="replace")
        except (asyncio.TimeoutError, Exception) as e:
            writer.close()
            return

        # Parse the HTTP request
        lines = request.split("\r\n")
        if not lines:
            writer.close()
            return

        method, path, _ = lines[0].split(" ", 2) if len(lines[0].split()) == 3 else ("", "", "")

        # CORS and health check
        if method == "OPTIONS":
            await self._http_reply(writer, 204, "", cors=True)
            return

        if path == "/health" and method == "GET":
            await self._http_reply(writer, 200, json.dumps({"status": "ok"}))
            return

        if path == "/qq_message" and method == "POST":
            # Extract body
            body_start = request.find("\r\n\r\n")
            if body_start == -1:
                await self._http_reply(writer, 400, "Bad Request")
                return
            body = request[body_start + 4:].strip()

            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                await self._http_reply(writer, 400, "Invalid JSON")
                return

            user_id = data.get("user_id") or data.get("userId")
            message = data.get("message") or data.get("msg")

            if not user_id or not message:
                await self._http_reply(writer, 400, "Missing user_id or message")
                return

            # Create a pseudo-event and queue it
            event = PrivateMessageEvent(
                user_id=int(user_id),
                message=str(message),
                raw_message=str(message),
                message_id=0,
            )
            await self._task_queue.put(event)

            # Wait for the response (poll the queue response pattern)
            # Actually, the queue processor will handle it and try to send via WebSocket.
            # For HTTP, we return immediately and the response goes to WS (if connected)
            await self._http_reply(writer, 202, json.dumps({"status": "queued"}))
            return

        # Fallback: 404
        await self._http_reply(writer, 404, "Not Found")

    @staticmethod
    async def _http_reply(writer, status: int, body: str, cors: bool = False):
        """Send an HTTP response."""
        status_text = {200: "OK", 202: "Accepted", 204: "No Content", 400: "Bad Request", 404: "Not Found"}
        headers = [
            f"HTTP/1.1 {status} {status_text.get(status, 'Unknown')}",
            "Content-Type: application/json; charset=utf-8",
            f"Content-Length: {len(body.encode('utf-8'))}",
            "Connection: close",
        ]
        if cors:
            headers.append("Access-Control-Allow-Origin: *")
            headers.append("Access-Control-Allow-Methods: POST, GET, OPTIONS")
            headers.append("Access-Control-Allow-Headers: Content-Type")
        headers.append("")
        headers.append("")
        try:
            writer.write("\r\n".join(headers).encode("utf-8") + body.encode("utf-8"))
            await writer.drain()
        except Exception:
            pass
        finally:
            writer.close()

    # ------------------------------------------------------------------
    # Message handling (shared between WS and HTTP)
    # ------------------------------------------------------------------

    async def _on_raw(self, raw: str):
        """Parse and route an incoming WS message."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return

        event = parse_event(data)
        if event is None:
            return

        await self._task_queue.put(event)

    async def _process_queue(self):
        """Serialized agent call processor."""
        while not self._stop_event.is_set():
            try:
                event = await asyncio.wait_for(
                    self._task_queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            try:
                await self._handle_event(event)
            except Exception as e:
                logger.error(f"QQ event handler error: {e}")

    async def _handle_event(self, event: PrivateMessageEvent | GroupMessageEvent):
        """Process one QQ message event."""
        user_id = event.user_id
        text = event.message.strip()

        # Whitelist check
        whitelist = settings.qq_whitelist_set
        if whitelist and user_id not in whitelist:
            logger.info(f"Ignored message from non-whitelist QQ {user_id}")
            return

        if not text:
            return

        logger.info(f"QQ({user_id}): {text}")

        # Run agent
        try:
            response = await asyncio.wait_for(
                self._agent.run(text), timeout=120.0,
            )
        except asyncio.TimeoutError:
            response = "抱歉，思考太久了，请稍后再试～"

        # Send response via WebSocket if connected
        if self._ws:
            try:
                if isinstance(event, PrivateMessageEvent):
                    await self._ws.send(send_private_msg(user_id, response))
                elif isinstance(event, GroupMessageEvent):
                    await self._ws.send(send_group_msg(event.group_id, response))
            except Exception as e:
                logger.warning(f"Failed to send WS reply: {e}")

    async def send(self, text: str):
        """Send raw JSON action over the active WebSocket."""
        if self._ws:
            try:
                await self._ws.send(text)
            except Exception as e:
                logger.warning(f"Failed to send WS message: {e}")


# ---------------------------------------------------------------------------
# QQBotThread — QThread wrapper
# ---------------------------------------------------------------------------

class QQBotThread(QThread):
    """Dedicated thread running the QQ Bot servers."""

    status_changed = Signal(str)

    def __init__(self, agent: AgentExecutor, parent=None):
        super().__init__(parent)
        self._agent = agent
        self._bot: QQBot | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop

        try:
            self._bot = QQBot(self._agent)
            self.status_changed.emit("running")
            logger.info("QQ Bot thread started")
            loop.run_until_complete(self._bot.start())
        except Exception as e:
            logger.error(f"QQ Bot thread error: {e}")
            self.status_changed.emit(f"error: {e}")
        finally:
            loop.close()
            self._loop = None

    def stop(self):
        if self._bot and self._loop and self._loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._bot.stop(), self._loop,
            )
        self.wait(5000)
        self.status_changed.emit("stopped")
