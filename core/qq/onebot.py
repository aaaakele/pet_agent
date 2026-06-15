"""OneBot v11 protocol types and helpers for QQ Bot integration."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Event types (inbound from QQ client)
# ---------------------------------------------------------------------------

@dataclass
class PrivateMessageEvent:
    """A private message sent to the bot's QQ account."""
    user_id: int
    message: str
    raw_message: str
    message_id: int
    message_type: str = "private"
    sub_type: str = ""
    font: int = 0
    sender: dict = field(default_factory=dict)
    self_id: int = 0
    time: int = 0
    post_type: str = "message"


@dataclass
class GroupMessageEvent:
    """A group message mentioning the bot."""
    user_id: int
    group_id: int
    message: str
    raw_message: str
    message_id: int
    message_type: str = "group"
    sub_type: str = ""
    font: int = 0
    sender: dict = field(default_factory=dict)
    self_id: int = 0
    time: int = 0
    post_type: str = "message"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def parse_event(raw: dict) -> PrivateMessageEvent | GroupMessageEvent | None:
    """Parse an inbound OneBot v11 JSON event into a typed event object."""
    post_type = raw.get("post_type")
    message_type = raw.get("message_type")

    if post_type != "message":
        return None

    if message_type == "private":
        return PrivateMessageEvent(
            user_id=int(raw.get("user_id", 0)),
            message=_extract_text(raw),
            raw_message=raw.get("raw_message", ""),
            message_id=int(raw.get("message_id", 0)),
            sub_type=raw.get("sub_type", ""),
            font=raw.get("font", 0),
            sender=raw.get("sender", {}),
            self_id=int(raw.get("self_id", 0)),
            time=int(raw.get("time", 0)),
        )

    if message_type == "group":
        return GroupMessageEvent(
            user_id=int(raw.get("user_id", 0)),
            group_id=int(raw.get("group_id", 0)),
            message=_extract_text(raw),
            raw_message=raw.get("raw_message", ""),
            message_id=int(raw.get("message_id", 0)),
            sub_type=raw.get("sub_type", ""),
            font=raw.get("font", 0),
            sender=raw.get("sender", {}),
            self_id=int(raw.get("self_id", 0)),
            time=int(raw.get("time", 0)),
        )

    return None


def _extract_text(raw: dict) -> str:
    """Extract plain text from message field which may be a string or array."""
    msg = raw.get("message", "")
    if isinstance(msg, str):
        return msg
    if isinstance(msg, list):
        parts = []
        for seg in msg:
            if isinstance(seg, dict) and seg.get("type") == "text":
                parts.append(seg.get("data", {}).get("text", ""))
        return "".join(parts).strip()
    return str(msg)


# ---------------------------------------------------------------------------
# Actions (outbound to QQ client)
# ---------------------------------------------------------------------------

def build_action(action: str, params: dict | None = None, echo: str = "") -> str:
    """Build a OneBot v11 action JSON string to send over WebSocket."""
    payload: dict[str, Any] = {
        "action": action,
        "params": params or {},
    }
    if echo:
        payload["echo"] = echo
    return json.dumps(payload, ensure_ascii=False)


def send_private_msg(user_id: int, message: str) -> str:
    """Build a 'send_private_msg' action."""
    return build_action("send_private_msg", {
        "user_id": user_id,
        "message": message,
    })


def send_group_msg(group_id: int, message: str) -> str:
    """Build a 'send_group_msg' action."""
    return build_action("send_group_msg", {
        "group_id": group_id,
        "message": message,
    })


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def parse_json(data: str) -> dict | None:
    """Safely parse a JSON string, returning None on failure."""
    try:
        return json.loads(data)
    except json.JSONDecodeError:
        return None
