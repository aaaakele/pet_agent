from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, Text, Float, ForeignKey, create_engine,
)
from sqlalchemy.orm import declarative_base, Session, relationship

Base = declarative_base()

from config.settings import settings


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class SessionModel(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, default="")
    parent_id = Column(Integer, nullable=True)
    summary_message_id = Column(Integer, nullable=True)
    created_at = Column(Integer, nullable=False, index=True)
    updated_at = Column(Integer, nullable=False)

    messages = relationship("MessageModel", back_populates="session", order_by="MessageModel.created_at")


class MessageModel(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    role = Column(String, nullable=False)     # 'user' | 'assistant' | 'system'
    content = Column(Text, nullable=False)
    message_type = Column(String, default="text")  # 'text' | 'tool_call' | 'tool_result' | 'summary'
    reasoning_content = Column(Text, nullable=True)  # DeepSeek thinking mode
    created_at = Column(Integer, nullable=False, index=True)
    embedded = Column(Boolean, default=False)

    session = relationship("SessionModel", back_populates="messages")


class ToolRunModel(Base):
    __tablename__ = "tool_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    args_json = Column(Text, default="{}")
    result_json = Column(Text, default="")
    is_error = Column(Boolean, default=False)
    metadata_json = Column(Text, default="{}")
    duration_ms = Column(Float, default=0)
    created_at = Column(Integer, nullable=False)


class ArtifactModel(Base):
    __tablename__ = "artifacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    artifact_type = Column(String, nullable=False)  # 'file' | 'webpage' | 'search_result' | 'screenshot'
    url_or_path = Column(String, default="")
    content = Column(Text, default="")
    metadata_json = Column(Text, default="{}")
    created_at = Column(Integer, nullable=False)


class ScheduledTaskModel(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False, index=True)
    title = Column(String, default="")
    task_type = Column(String, nullable=False)  # 'reminder' | 'recurring'
    trigger_at = Column(Integer, nullable=False, index=True)  # next fire unix ms
    interval_minutes = Column(Integer, default=0)   # 0 = one-shot
    prompt = Column(Text, nullable=False)
    enabled = Column(Boolean, default=True)
    last_fired_at = Column(Integer, default=0)
    created_at = Column(Integer, nullable=False)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

_engine = None


def _migrate_reasoning_column(engine):
    """Add reasoning_content column if it doesn't exist (safe on existing DBs)."""
    import sqlalchemy
    with engine.begin() as conn:
        cols = [row[1] for row in conn.execute(
            sqlalchemy.text("PRAGMA table_info(messages)")
        ).fetchall()]
        if "reasoning_content" not in cols:
            conn.execute(sqlalchemy.text(
                "ALTER TABLE messages ADD COLUMN reasoning_content TEXT"
            ))


def _get_engine():
    global _engine
    if _engine is None:
        import os
        os.makedirs("storage", exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{settings.DB_PATH}",
            echo=False,
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(_engine)
        _migrate_reasoning_column(_engine)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------

class MessageStore:

    def __init__(self):
        self.engine = _get_engine()

    # -- sessions --

    def create_session(self, title: str = "") -> SessionModel:
        now = _now()
        s = SessionModel(title=title, created_at=now, updated_at=now)
        with get_session() as sess:
            sess.add(s)
            sess.commit()
            sess.refresh(s)
            return s

    def get_session(self, session_id: int) -> SessionModel | None:
        with get_session() as sess:
            return sess.query(SessionModel).filter(SessionModel.id == session_id).first()

    def get_latest_session(self) -> SessionModel:
        with get_session() as sess:
            s = sess.query(SessionModel).order_by(SessionModel.updated_at.desc()).first()
            if not s:
                return self.create_session()
            return s

    def update_session_title(self, session_id: int, title: str) -> None:
        with get_session() as sess:
            sess.query(SessionModel).filter(SessionModel.id == session_id).update(
                {"title": title, "updated_at": _now()}, synchronize_session=False
            )
            sess.commit()

    def clear_session(self, session_id: int) -> None:
        """Delete all messages, tool_runs, artifacts, and tasks for a session."""
        with get_session() as sess:
            sess.query(MessageModel).filter(MessageModel.session_id == session_id).delete()
            sess.query(ToolRunModel).filter(ToolRunModel.session_id == session_id).delete()
            sess.query(ArtifactModel).filter(ArtifactModel.session_id == session_id).delete()
            sess.query(ScheduledTaskModel).filter(ScheduledTaskModel.session_id == session_id).delete()
            sess.commit()

    # -- messages --

    def insert_message(
        self,
        role: str,
        content: str,
        session_id: int | None = None,
        message_type: str = "text",
        created_at: int | None = None,
        reasoning_content: str | None = None,
    ) -> MessageModel:
        if session_id is None:
            session_id = self.get_latest_session().id
        if created_at is None:
            created_at = _now()

        msg = MessageModel(
            session_id=session_id,
            role=role,
            content=content,
            message_type=message_type,
            reasoning_content=reasoning_content,
            created_at=created_at,
        )
        with get_session() as sess:
            sess.add(msg)
            # bump session updated_at
            sess.query(SessionModel).filter(SessionModel.id == session_id).update(
                {"updated_at": _now()}, synchronize_session=False
            )
            sess.commit()
            sess.refresh(msg)
            return msg

    def get_recent_messages(self, session_id: int | None = None, limit: int = 50) -> list[MessageModel]:
        if session_id is None:
            session_id = self.get_latest_session().id
        with get_session() as sess:
            return (
                sess.query(MessageModel)
                .filter(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at.desc())
                .limit(limit)
                .all()
            )[::-1]

    def get_unembedded_messages(self, limit: int = 100) -> list[MessageModel]:
        with get_session() as sess:
            return (
                sess.query(MessageModel)
                .filter(MessageModel.embedded == False)
                .limit(limit)
                .all()
            )

    def mark_embedded(self, msg_ids: list[int]) -> None:
        with get_session() as sess:
            sess.query(MessageModel).filter(
                MessageModel.id.in_(msg_ids)
            ).update({"embedded": True}, synchronize_session=False)
            sess.commit()

    def archive_messages_before(self, session_id: int, message_id: int) -> list[MessageModel]:
        """Mark messages before `message_id` as archived (for summary replacement)."""
        with get_session() as sess:
            older = (
                sess.query(MessageModel)
                .filter(
                    MessageModel.session_id == session_id,
                    MessageModel.id < message_id,
                    MessageModel.embedded == False,
                )
                .all()
            )
            ids = [m.id for m in older]
            if ids:
                sess.query(MessageModel).filter(
                    MessageModel.id.in_(ids)
                ).update({"embedded": True}, synchronize_session=False)
                sess.commit()
            return older

    def count_messages_in_session(self, session_id: int) -> int:
        with get_session() as sess:
            return (
                sess.query(MessageModel)
                .filter(MessageModel.session_id == session_id)
                .count()
            )

    def total_chars_in_session(self, session_id: int) -> int:
        with get_session() as sess:
            rows = (
                sess.query(MessageModel.content)
                .filter(MessageModel.session_id == session_id)
                .all()
            )
            return sum(len(r.content) for r in rows)

    # -- tool runs --

    def insert_tool_run(
        self,
        tool_name: str,
        args: dict,
        result_content: str,
        is_error: bool,
        metadata: dict,
        duration_ms: float,
        session_id: int | None = None,
    ) -> ToolRunModel:
        if session_id is None:
            session_id = self.get_latest_session().id
        tr = ToolRunModel(
            session_id=session_id,
            tool_name=tool_name,
            args_json=json.dumps(args, ensure_ascii=False),
            result_json=result_content[:8000],
            is_error=is_error,
            metadata_json=json.dumps(metadata, ensure_ascii=False),
            duration_ms=duration_ms,
            created_at=_now(),
        )
        with get_session() as sess:
            sess.add(tr)
            sess.commit()
            sess.refresh(tr)
            return tr

    def get_recent_tool_runs(self, session_id: int, limit: int = 20) -> list[ToolRunModel]:
        with get_session() as sess:
            return (
                sess.query(ToolRunModel)
                .filter(ToolRunModel.session_id == session_id)
                .order_by(ToolRunModel.created_at.desc())
                .limit(limit)
                .all()
            )[::-1]

    # -- artifacts --

    def insert_artifact(
        self,
        artifact_type: str,
        url_or_path: str,
        content: str,
        metadata: dict | None = None,
        session_id: int | None = None,
    ) -> ArtifactModel:
        if session_id is None:
            session_id = self.get_latest_session().id
        a = ArtifactModel(
            session_id=session_id,
            artifact_type=artifact_type,
            url_or_path=url_or_path,
            content=content[:20000],
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
            created_at=_now(),
        )
        with get_session() as sess:
            sess.add(a)
            sess.commit()
            sess.refresh(a)
            return a

    # -- scheduled tasks --

    def create_task(
        self, title: str, task_type: str, trigger_at: int, prompt: str,
        interval_minutes: int = 0, session_id: int | None = None,
    ) -> ScheduledTaskModel:
        if session_id is None:
            session_id = self.get_latest_session().id
        t = ScheduledTaskModel(
            session_id=session_id, title=title, task_type=task_type,
            trigger_at=trigger_at, interval_minutes=interval_minutes,
            prompt=prompt, enabled=True, created_at=_now(),
        )
        with get_session() as sess:
            sess.add(t)
            sess.commit()
            sess.refresh(t)
            return t

    def get_due_tasks(self, now_ms: int | None = None) -> list[ScheduledTaskModel]:
        if now_ms is None:
            now_ms = _now()
        with get_session() as sess:
            return (
                sess.query(ScheduledTaskModel)
                .filter(
                    ScheduledTaskModel.enabled == True,
                    ScheduledTaskModel.trigger_at <= now_ms,
                )
                .order_by(ScheduledTaskModel.trigger_at.asc())
                .limit(10)
                .all()
            )

    def get_pending_tasks(self, session_id: int | None = None) -> list[ScheduledTaskModel]:
        with get_session() as sess:
            q = sess.query(ScheduledTaskModel).filter(ScheduledTaskModel.enabled == True)
            if session_id is not None:
                q = q.filter(ScheduledTaskModel.session_id == session_id)
            return q.order_by(ScheduledTaskModel.trigger_at.asc()).all()

    def complete_task(self, task_id: int, next_trigger_at: int | None = None):
        with get_session() as sess:
            t = sess.get(ScheduledTaskModel, task_id)
            if t:
                t.last_fired_at = _now()
                if next_trigger_at is not None:
                    t.trigger_at = next_trigger_at
                else:
                    t.enabled = False  # one-shot, disable after firing
                sess.commit()

    def cancel_task(self, task_id: int) -> bool:
        with get_session() as sess:
            t = sess.get(ScheduledTaskModel, task_id)
            if t:
                t.enabled = False
                sess.commit()
                return True
            return False


def _now() -> int:
    return int(datetime.now().timestamp() * 1000)
