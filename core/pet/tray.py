"""System tray integration for the desktop pet."""

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication

from config.settings import settings
from core.pet.model_switcher import build_model_menu


class SystemTray(QSystemTrayIcon):
    """System tray icon with right-click menu."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._parent = parent

        self.setIcon(QIcon(settings.PET_AVATAR_PATH))
        self.setToolTip("桌宠 — 随时陪你聊天")

        # --- Context menu ---
        menu = QMenu()

        show_action = menu.addAction("显示/隐藏")
        show_action.triggered.connect(self._toggle_visibility)

        avatar_action = menu.addAction("更换头像...")
        avatar_action.triggered.connect(self._change_avatar)

        menu.addSeparator()

        # Model switch submenu
        build_model_menu(menu, status_callback=self._update_tooltip)

        menu.addSeparator()

        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(QApplication.quit)

        self.setContextMenu(menu)

        # --- Double-click to show ---
        self.activated.connect(self._on_activated)

    def _toggle_visibility(self):
        if self._parent and self._parent.isVisible():
            self._parent.hide()
        elif self._parent:
            self._parent.show()
            self._parent.raise_()

    def _change_avatar(self):
        if self._parent:
            self._parent.change_avatar_dialog()

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self._toggle_visibility()
        elif reason == QSystemTrayIcon.MiddleClick:
            if self._parent:
                self._parent.open_chat()

    def _update_tooltip(self, status: str = ""):
        self.setToolTip(f"桌宠 — {status}" if status else "桌宠 — 随时陪你聊天")
