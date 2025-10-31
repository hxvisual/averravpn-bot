from datetime import datetime
from typing import Any, Dict, Optional


def format_ts_to_str(ts: int) -> str:
    """Format unix timestamp to human-readable string."""
    return datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M")


def is_subscription_active(user_info: Optional[Dict[str, Any]]) -> bool:
    """Return True if user's subscription is active and not expired.

    Expects a mapping with keys: 'status' and 'expire' (unix timestamp seconds).
    """
    if not user_info:
        return False
    try:
        status = user_info.get("status")
        if status != "active":
            return False
        expire_raw = user_info.get("expire")
        # If no expiration is set in Marzban (None/0), treat as infinite subscription
        if not expire_raw:
            return True
        expire_ts = int(expire_raw)
        return datetime.fromtimestamp(expire_ts) > datetime.now()
    except Exception:
        return False


def bytes_to_gigabytes(value_in_bytes: int | float) -> float:
    """Convert bytes to gigabytes with 2 decimal precision."""
    try:
        return round(float(value_in_bytes) / (1024 ** 3), 2)
    except Exception:
        return 0.0


def get_display_username(username: Optional[str]) -> str:
    """Normalize username for displaying (remove 'tg_' prefix if present)."""
    if isinstance(username, str):
        return username.removeprefix("tg_")
    return ""

