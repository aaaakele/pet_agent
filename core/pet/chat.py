"""Chat dialog for interacting with the desktop pet."""

from __future__ import annotations

import asyncio

from PySide6.QtCore import Qt, Signal, QThread
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit,
    QPushButton, QLabel,
)

from utils.logger import logger


class AgentWorker(QThread):
    """Run the agent's asyncio loop in a background thread."""
    finished = Signal(str)

    def __init__(self, agent, query: str):
        super().__init__()
        self._agent = agent
        self._query = query

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(self._agent.run(self._query))
                self.finished.emit(result)
            except Exception as e:
                logger.exception("Agent execution failed")
                self.finished.emit(f"出错了: {e}")
            finally:
                try:
                    loop.close()
                except Exception:
                    pass
        except Exception as e:
            # Last-resort catch — prevent thread crash from killing the app
            logger.exception("AgentWorker fatal error")
            try:
                self.finished.emit(f"内部错误: {e}")
            except Exception:
                pass


class ChatDialog(QDialog):
    """Chat window for talking with the desktop pet agent."""

    def __init__(self, parent=None, agent=None, store=None):
        super().__init__(parent)
        self._agent = agent
        self._store = store
        self._worker = None

        self.setWindowTitle("和桌宠聊天")
        self.setWindowFlags(
            Qt.Window | Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint
        )
        self.setMinimumSize(420, 550)
        self.resize(450, 600)

        # Chat display
        self._display = QTextEdit(self)
        self._display.setReadOnly(True)
        font = QFont()
        font.setPointSize(11)
        self._display.setFont(font)

        # Input
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("输入消息，按回车发送...")
        self._input.returnPressed.connect(self._send_message)
        self._input.setMinimumHeight(32)

        send_btn = QPushButton("发送")
        send_btn.clicked.connect(self._send_message)
        send_btn.setMinimumHeight(32)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self._input, 1)
        input_layout.addWidget(send_btn, 0)

        # Status
        self._status = QLabel("")
        self._status.setStyleSheet("color: gray; font-size: 11px;")

        layout = QVBoxLayout(self)
        layout.addWidget(self._display, 1)
        layout.addWidget(self._status)
        layout.addLayout(input_layout)

        self._load_history()
        self._input.setFocus()

    def _load_history(self):
        """Load recent conversation from SQLite."""
        if not self._store:
            return
        messages = self._store.get_recent_messages(
            session_id=self._agent.session_id, limit=50
        )
        for msg in messages:
            if msg.message_type == "summary":
                self._display.append(
                    f'<i style="color:#888">📝 {msg.content}</i>'
                )
                self._display.append("")
            elif msg.role == "tool":
                self._display.append(
                    f'<span style="color:#888;font-size:10px">🔧 {msg.content[:200]}</span>'
                )
            elif msg.role == "user":
                self._display.append(
                    f'<b style="color:#2196F3">你:</b> {msg.content}'
                )
            elif msg.role == "assistant":
                if msg.message_type == "tool_call":
                    self._display.append(
                        f'<span style="color:#FF9800;font-size:10px">🔍 正在执行工具...</span>'
                    )
                else:
                    self._display.append(
                        f'<b style="color:#4CAF50">桌宠:</b> {msg.content}'
                    )
                    self._display.append("")
            elif msg.role == "system":
                self._display.append(
                    f'<i style="color:#888">{msg.content}</i>'
                )

    def _send_message(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return

        self._input.clear()
        self._input.setEnabled(False)
        self._status.setText("桌宠正在思考...")

        self._display.append(f'<b style="color:#2196F3">你:</b> {text}')

        # Agent saves the user message internally now
        self._worker = AgentWorker(self._agent, text)
        self._worker.finished.connect(self._on_response)
        self._worker.start()

    def _on_response(self, response: str):
        """Handle agent response."""
        try:
            if response.startswith("已清空所有对话历史"):
                self._display.clear()
                self._display.append(f'<b style="color:#4CAF50">桌宠:</b> {response}')
                self._display.append("")
            else:
                self._display.append(f'<b style="color:#4CAF50">桌宠:</b> {response}')
                self._display.append("")

                # Append tool runs for transparency
                if self._store and self._agent.session_id:
                    tool_runs = self._store.get_recent_tool_runs(self._agent.session_id, limit=5)
                    for tr in tool_runs:
                        if tr.is_error:
                            self._display.append(
                                f'<span style="color:#f44336;font-size:10px">❌ {tr.tool_name}: {tr.result_json[:150]}</span>'
                            )
                        else:
                            self._display.append(
                                f'<span style="color:#888;font-size:10px">✓ {tr.tool_name} ({tr.duration_ms:.0f}ms)</span>'
                            )
        except Exception:
            logger.exception("Failed to display response")
        finally:
            self._status.setText("")
            self._input.setEnabled(True)
            self._input.setFocus()
            self._worker = None

    def closeEvent(self, event):
        if self._worker is not None and self._worker.isRunning():
            self._worker.terminate()
            self._worker.wait(3000)
        super().closeEvent(event)
