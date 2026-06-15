"""Desktop Pet — a floating character that chats with you using LLM agent."""

from __future__ import annotations

import sys
import os

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon

from config.settings import settings
from core.agent.executor import AgentExecutor
from core.history.storage import MessageStore
from core.memory.manager import MemoryManager
from core.tasks.scheduler import TaskScheduler
from core.pet.window import PetWindow
from core.pet.tray import SystemTray
from core.qq.bot import QQBotThread
from utils.logger import logger


def main():
    logger.info("Starting Desktop Pet...")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # --- Backend ---
    store = MessageStore()
    memory_mgr = MemoryManager()
    agent = AgentExecutor(store=store)
    agent.set_memory_manager(memory_mgr)

    # Ensure data dirs
    os.makedirs("data", exist_ok=True)

    # --- Scheduler ---
    scheduler = TaskScheduler(agent=agent, store=store)
    scheduler.start()

    # --- QQ Bot (optional) ---
    qq_bot_thread = None
    if settings.QQ_ENABLED and settings.qq_whitelist_set:
        qq_agent = AgentExecutor(store=store)
        qq_agent.set_memory_manager(memory_mgr)
        qq_bot_thread = QQBotThread(agent=qq_agent)
        qq_bot_thread.status_changed.connect(
            lambda status: logger.info(f"QQ Bot: {status}")
        )
        qq_bot_thread.start()
        logger.info(
            f"QQ Bot enabled, listening on ws://{settings.QQ_WS_HOST}:{settings.QQ_WS_PORT}"
        )
    else:
        logger.info(
            f"QQ Bot disabled (QQ_ENABLED={settings.QQ_ENABLED}, "
            f"whitelist={settings.QQ_WHITELIST!r})"
        )

    # --- GUI ---
    pet = PetWindow(agent=agent, store=store)

    # Connect scheduler notifications to pet bubble
    scheduler.task_fired.connect(pet._show_response)

    # Cleanup on quit — before Qt destroys objects
    def cleanup():
        scheduler.stop()
        scheduler.wait(3000)
        if qq_bot_thread is not None:
            qq_bot_thread.stop()
            qq_bot_thread.wait(5000)
        if pet._bubble is not None:
            pet._bubble._cleanup_worker()
        if pet._chat_dlg is not None:
            pet._chat_dlg.close()
        logger.info("Desktop Pet shutting down")
    app.aboutToQuit.connect(cleanup)

    if os.path.exists(settings.PET_AVATAR_PATH):
        app.setWindowIcon(QIcon(settings.PET_AVATAR_PATH))

    tray = SystemTray(parent=pet)

    # Position at bottom-right
    screen = app.primaryScreen()
    if screen:
        geo = screen.availableGeometry()
        pet.move(geo.right() - pet.width() - 40, geo.bottom() - pet.height() - 80)

    pet.show()
    tray.show()

    logger.info("Desktop Pet is running. Double-click the pet to chat.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
