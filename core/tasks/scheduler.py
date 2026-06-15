"""Task scheduler — background loop for reminders and recurring tasks."""

from __future__ import annotations

import asyncio
import time

from PySide6.QtCore import QThread, Signal

from utils.logger import logger


class TaskScheduler(QThread):
    """Polls for due tasks and executes them via AgentExecutor."""

    task_fired = Signal(str)  # Notification message

    def __init__(self, agent, store):
        super().__init__()
        self._agent = agent
        self._store = store
        self._running = True
        self._poll_interval = 15  # seconds

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._run_loop())
        except Exception:
            logger.exception("TaskScheduler crashed")
        finally:
            try:
                loop.close()
            except Exception:
                pass

    async def _run_loop(self):
        while self._running:
            try:
                tasks = self._store.get_due_tasks()
                for task in tasks:
                    try:
                        logger.info(f"Firing task: {task.title}")
                        # Fire via agent
                        result = await self._agent.run(task.prompt)
                        # Update task state
                        if task.interval_minutes > 0:
                            # Recurring: calculate next trigger
                            next_ts = int(time.time() * 1000) + task.interval_minutes * 60000
                            self._store.complete_task(task.id, next_trigger_at=next_ts)
                        else:
                            # One-shot: disable
                            self._store.complete_task(task.id)
                        # Notify
                        msg = f"[提醒] {task.title}: {result[:200]}"
                        self.task_fired.emit(msg)
                        logger.info(f"Task completed: {task.title}")
                    except Exception:
                        logger.exception(f"Task {task.id} ({task.title}) failed")
                        self._store.cancel_task(task.id)
            except Exception:
                logger.exception("TaskScheduler poll error")

            await asyncio.sleep(self._poll_interval)

    def stop(self):
        self._running = False
