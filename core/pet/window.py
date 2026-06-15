"""Floating desktop pet window — frameless, transparent, always-on-top."""

from PySide6.QtCore import Qt, QPoint
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QMenu, QFileDialog, QApplication,
)

from config.settings import settings
from core.pet.icons import PetIconManager
from core.pet.model_switcher import build_model_menu

PET_SIZE = 150


class PetWindow(QWidget):
    """A frameless floating window showing the pet character."""

    def __init__(self, agent=None, store=None):
        super().__init__()
        self._agent = agent
        self._store = store
        self._dragging = False
        self._drag_pos = QPoint()
        self._movie = None
        self._avatar_path = settings.PET_AVATAR_PATH
        self._bubble = None          # QuickBubble instance (single-click)
        self._response_bubble = None  # ResponseBubble instance (standalone popup)
        self._chat_dlg = None        # ChatDialog instance (double-click)
        self._press_pos = QPoint()   # for tap vs drag detection
        self._tap_possible = False

        # --- Window flags: frameless, always on top, no taskbar ---
        self.setWindowFlags(
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(PET_SIZE + 20, PET_SIZE + 20)

        # --- Pet image label ---
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setFixedSize(PET_SIZE, PET_SIZE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.addWidget(self._label)

        # --- Load avatar ---
        self.set_avatar(self._avatar_path)

        # --- Enable drag-drop for avatar change ---
        self.setAcceptDrops(True)

        # --- Context menu ---
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    # ------------------------------------------------------------------
    # Avatar
    # ------------------------------------------------------------------

    def set_avatar(self, path: str):
        """Load and display a pet avatar image."""
        self._movie = PetIconManager.apply_to_label(self._label, path, PET_SIZE)
        self._avatar_path = path

    # ------------------------------------------------------------------
    # Mouse: tap (single-click bubble), drag, double-click (full chat)
    # ------------------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press_pos = event.scenePosition().toPoint()
            self._tap_possible = True
            self._dragging = False
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.LeftButton:
            delta = event.scenePosition().toPoint() - self._press_pos
            if self._tap_possible and (abs(delta.x()) > 8 or abs(delta.y()) > 8):
                # Moved enough — switch to drag mode
                self._tap_possible = False
                self._dragging = True
                self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                # Hide quick bubble while dragging
                if self._bubble is not None and self._bubble.isVisible():
                    self._bubble.hide()
                if self._response_bubble is not None and self._response_bubble.isVisible():
                    self._response_bubble.hide()
            if self._dragging:
                self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._tap_possible and not self._dragging:
                self._open_bubble()
            self._dragging = False
            self._tap_possible = False

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._tap_possible = False  # preempt single-click
            self.open_chat()

    # ------------------------------------------------------------------
    # Drag & drop avatar change
    # ------------------------------------------------------------------

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0]
            if url.isLocalFile() and PetIconManager.is_valid_image(url.toLocalFile()):
                event.acceptProposedAction()

    def dropEvent(self, event):
        path = event.mimeData().urls()[0].toLocalFile()
        self.set_avatar(path)
        settings.PET_AVATAR_PATH = path

    # ------------------------------------------------------------------
    # Context menu
    # ------------------------------------------------------------------

    def _show_context_menu(self, pos):
        menu = QMenu(self)
        chat_action = menu.addAction("聊天")
        chat_action.triggered.connect(self.open_chat)

        avatar_action = menu.addAction("更换头像...")
        avatar_action.triggered.connect(self.change_avatar_dialog)

        menu.addSeparator()

        # Model switch submenu
        build_model_menu(menu)

        hide_action = menu.addAction("隐藏")
        hide_action.triggered.connect(self.hide)

        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)

        menu.exec(self.mapToGlobal(pos))

    def _open_bubble(self):
        """Open or toggle the quick bubble (single-click)."""
        from core.pet.bubble import QuickBubble, ResponseBubble
        # If already visible, hide it
        if self._bubble is not None and self._bubble.isVisible():
            self._bubble.hide()
            return
        # If hidden but worker is running, ignore (prevent double-send)
        if self._bubble is not None and self._bubble._worker is not None:
            return
        if self._bubble is None:
            self._bubble = QuickBubble(self._agent, self._store)
            self._bubble.destroyed.connect(lambda obj=None: setattr(self, '_bubble', None))
            self._bubble.response_ready.connect(self._show_response)
        if self._response_bubble is None:
            self._response_bubble = ResponseBubble()
        # Position bubble above the pet
        pet_center = self.mapToGlobal(self.rect().center())
        self._bubble.move(
            pet_center.x() - self._bubble.width() // 2,
            pet_center.y() - self.height() // 2 - self._bubble.height() - 10,
        )
        self._bubble.show()

    def _show_response(self, text: str):
        """Show the agent response in a standalone speech bubble near the pet."""
        if self._response_bubble is None:
            from core.pet.bubble import ResponseBubble
            self._response_bubble = ResponseBubble()
        self._response_bubble.show_with_text(text, near=self)

    def open_chat(self):
        """Open the chat dialog (single instance, raise if already open)."""
        from core.pet.chat import ChatDialog
        if hasattr(self, '_chat_dlg') and self._chat_dlg is not None and self._chat_dlg.isVisible():
            self._chat_dlg.raise_()
            self._chat_dlg.activateWindow()
            return
        self._chat_dlg = ChatDialog(self, agent=self._agent, store=self._store)
        self._chat_dlg.setWindowIcon(self._make_icon())
        self._chat_dlg.destroyed.connect(lambda obj=None: setattr(self, '_chat_dlg', None))
        self._chat_dlg.show()

    def change_avatar_dialog(self):
        """Open file dialog to choose a new pet avatar."""
        path, _ = QFileDialog.getOpenFileName(
            self, "选择桌宠头像", "",
            "Images (*.png *.jpg *.jpeg *.gif *.webp *.bmp)"
        )
        if path:
            self.set_avatar(path)
            settings.PET_AVATAR_PATH = path

    def _make_icon(self):
        """Create a QIcon from the current avatar for dialog windows."""
        if PetIconManager.is_gif(self._avatar_path):
            return QIcon()
        return QIcon(self._avatar_path)
