import re
import time
from datetime import datetime


def now_ts() -> int:
    """Return current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def ts_to_str(ts: int, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Convert millisecond timestamp to formatted string."""
    return datetime.fromtimestamp(ts / 1000).strftime(fmt)


def clean_text(text: str) -> str:
    """Remove extra whitespace and normalize newlines."""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def truncate(text: str, max_len: int = 200) -> str:
    """Truncate text to max_len characters."""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "..."


def safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    return re.sub(r"[^\w\-_\.]", "_", name)
