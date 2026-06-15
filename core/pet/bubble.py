"""Quick bubble — single-click overlay for fast one-shot chat."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, QTimer, QRect
from PySide6.QtGui import QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel,
)

from core.pet.chat import AgentWorker


BUBBLE_MAX_WIDTH = 320
LABEL_FIXED_WIDTH = 280


class SpeechBubble(QWidget):
    """A rounded-rectangle label showing agent response text."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setFixedWidth(LABEL_FIXED_WIDTH)
        self._label.setStyleSheet(
            "color: #000; font-size: 14px; padding: 4px; font-weight: bold;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(self._label)

        self.setMaximumWidth(BUBBLE_MAX_WIDTH)

    def set_text(self, text: str):
        self._label.setText(text)
        self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QBrush(QColor("#E8F5E9")))
        painter.setPen(QPen(QColor("#A5D6A7"), 1))
        painter.drawRoundedRect(QRect(0, 0, self.width() - 1, self.height() - 1), 14, 14)


class ResponseBubble(QWidget):
    """Standalone frameless popup showing just the response speech bubble."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.ToolTip
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._bubble = SpeechBubble(self)
        layout.addWidget(self._bubble)

    def show_with_text(self, text: str, near: QWidget | None = None):
        self._bubble.set_text(text)
        self.adjustSize()
        if near:
            pet_center = near.mapToGlobal(near.rect().center())
            self.move(
                pet_center.x() - self.width() // 2,
                pet_center.y() - near.height() // 2 - self.height() - 10,
            )
        self.show()
        QTimer.singleShot(5000, self.hide)


class QuickBubble(QWidget):
    """Frameless popup: input line only. Hides on Enter, response shown separately."""

    response_ready = Signal(str)

    def __init__(self, agent, store, parent=None):
        super().__init__(parent)
        self._agent = agent
        self._store = store
        self._worker: AgentWorker | None = None

        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.ToolTip
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)

        # --- Layout ---
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(6)

        # Input row
        input_row = QHBoxLayout()
        self._input = QLineEdit(self)
        self._input.setPlaceholderText("输入问题，回车发送...")
        self._input.returnPressed.connect(self._send)
        self._input.setMinimumWidth(220)
        self._input.setStyleSheet(
            "QLineEdit { border: 1px solid #ccc; border-radius: 8px;"
            " padding: 6px 10px; font-size: 13px; background: white; color: #000; }"
        )
        input_row.addWidget(self._input)
        layout.addLayout(input_row)

        self.setFixedWidth(300)
        self.adjustSize()

    def _send(self):
        text = self._input.text().strip()
        if not text or self._worker is not None:
            return

        self._input.setEnabled(False)
        self.hide()

        self._worker = AgentWorker(self._agent, text)
        self._worker.finished.connect(self._on_response)
        self._worker.start()

    def _on_response(self, response: str):
        if self._worker is not None:
            self._worker.wait(1000)
        self._worker = None
        self.response_ready.emit(response)

    def _cleanup_worker(self):
        if self._worker is not None and self._worker.isRunning():
            self._worker.finished.disconnect(self._on_response)
            self._worker.terminate()
            self._worker.wait(3000)
        self._worker = None

    def closeEvent(self, event):
        self._cleanup_worker()
        super().closeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._input.clear()
        self._input.setEnabled(True)
        self._input.setFocus()
        self.adjustSize()
