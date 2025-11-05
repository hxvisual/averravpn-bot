from datetime import datetime
from typing import Any, Dict, Optional


NOTE_KNOWN_KEYS = {"ref", "username"}


def _normalize_username(username: Optional[str]) -> Optional[str]:
    if not username:
        return None
    value = username.strip()
    if not value:
        return None
    if not value.startswith("@"):
        value = f"@{value}"
    return value


def parse_note_components(note: Optional[str]) -> tuple[Dict[str, str], list[str]]:
    """Split note string into known key-value pairs and leftover lines."""
    fields: Dict[str, str] = {}
    extras: list[str] = []
    if not note:
        return fields, extras
    try:
        lines = [line.strip() for line in str(note).splitlines() if line and line.strip()]
    except Exception:
        return fields, extras
    for line in lines:
        if ":" in line:
            key, value = line.split(":", 1)
            key_lower = key.strip().lower()
            value_str = value.strip()
            if key_lower in NOTE_KNOWN_KEYS:
                fields[key_lower] = value_str
                continue
        extras.append(line)
    return fields, extras


def assemble_note_components(fields: Dict[str, str], extras: list[str]) -> Optional[str]:
    """Compose note string keeping known keys ordered and extras appended."""
    lines: list[str] = []
    ref_val = fields.get("ref")
    if ref_val:
        lines.append(f"ref:{ref_val}")
    username_val = fields.get("username")
    if username_val:
        lines.append(f"username:{username_val}")
    for extra in extras:
        extra_str = extra.strip()
        if extra_str:
            lines.append(extra_str)
    return "\n".join(lines) if lines else None


def build_user_note(ref_id: Optional[int] = None, username: Optional[str] = None, extras: Optional[list[str]] = None) -> Optional[str]:
    fields: Dict[str, str] = {}
    if ref_id is not None:
        fields["ref"] = str(ref_id)
    normalized_username = _normalize_username(username)
    if normalized_username:
        fields["username"] = normalized_username
    return assemble_note_components(fields, extras or [])


def update_note_with_username(note: Optional[str], username: Optional[str]) -> Optional[str]:
    fields, extras = parse_note_components(note)
    ref_id = extract_referrer_id(note)
    if ref_id is not None:
        fields["ref"] = str(ref_id)
    elif fields.get("ref") in {"", None}:
        fields.pop("ref", None)
    normalized_username = _normalize_username(username)
    if normalized_username:
        fields["username"] = normalized_username
    else:
        fields.pop("username", None)
    return assemble_note_components(fields, extras)


def extract_referrer_id(note: Optional[str]) -> Optional[int]:
    fields, _ = parse_note_components(note)
    ref_val = fields.get("ref")
    if not ref_val:
        return None
    candidate = ref_val.split("|")[0].split(";")[0].split(",")[0].strip()
    if candidate.isdigit():
        return int(candidate)
    return None


def extract_username(note: Optional[str]) -> Optional[str]:
    fields, _ = parse_note_components(note)
    return _normalize_username(fields.get("username"))


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

