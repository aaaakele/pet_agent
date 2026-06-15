"""Shared model-switching submenu used by tray and pet context menu."""

from PySide6.QtGui import QAction, QActionGroup
from PySide6.QtWidgets import QMenu

from config.settings import settings, MODEL_PRO, MODEL_FLASH


def build_model_menu(parent_menu: QMenu, status_callback=None) -> QMenu:
    """Append a 'Model' submenu to *parent_menu* and return it.

    If *status_callback* is provided it is called with a short status string
    whenever the model or thinking toggle changes (e.g. for tray tooltip).
    """
    sub = parent_menu.addMenu("模型切换")

    # -- Model radio group --
    group = QActionGroup(sub)
    group.setExclusive(True)

    pro_action = QAction(f"Pro ({MODEL_PRO})", group)
    pro_action.setCheckable(True)
    flash_action = QAction(f"Flash ({MODEL_FLASH})", group)
    flash_action.setCheckable(True)

    sub.addAction(pro_action)
    sub.addAction(flash_action)
    sub.addSeparator()

    think_action = QAction("Thinking 模式", sub)
    think_action.setCheckable(True)

    sub.addAction(think_action)

    # -- Initial state --
    _sync_menu_state(pro_action, flash_action, think_action)

    # -- Callbacks --
    def on_model_changed(action: QAction):
        if action is pro_action:
            settings.DEEPSEEK_MODEL = MODEL_PRO
        else:
            settings.DEEPSEEK_MODEL = MODEL_FLASH
        _sync_menu_state(pro_action, flash_action, think_action)
        if status_callback:
            status_callback(_status_text())

    def on_thinking_toggled(checked: bool):
        settings.THINKING_ENABLED = checked
        if status_callback:
            status_callback(_status_text())

    group.triggered.connect(on_model_changed)
    think_action.triggered.connect(on_thinking_toggled)

    return sub


def _sync_menu_state(pro: QAction, flash: QAction, think: QAction):
    """Refresh checkmarks and enabled state from current settings."""
    is_pro = settings.DEEPSEEK_MODEL == MODEL_PRO
    pro.setChecked(is_pro)
    flash.setChecked(not is_pro)
    think.setChecked(settings.THINKING_ENABLED)
    think.setEnabled(not is_pro)  # Pro has no thinking toggle


def _status_text() -> str:
    """Short label for tray tooltip / status bar."""
    model = "Pro" if settings.DEEPSEEK_MODEL == MODEL_PRO else "Flash"
    thinking = "+Thinking" if settings.THINKING_ENABLED else ""
    return f"模型: {model}{thinking}"
