import json
import os
import secrets
from typing import Dict, Optional, Tuple

from config import PROMO_CODES_FILE, SUBSCRIPTION_PLANS


def _read_store() -> Dict[str, Dict]:
    if not os.path.exists(PROMO_CODES_FILE):
        return {}
    try:
        with open(PROMO_CODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f) or {}
    except Exception:
        return {}


def _write_store(data: Dict[str, Dict]) -> None:
    tmp = PROMO_CODES_FILE + ".tmp"
    # sanitize: remove legacy 'used' keys
    sanitized: Dict[str, Dict] = {}
    for k, v in (data or {}).items():
        if isinstance(v, dict) and 'used' in v:
            v = {kk: vv for kk, vv in v.items() if kk != 'used'}
        sanitized[k] = v
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(sanitized, f, ensure_ascii=False, indent=2)
    os.replace(tmp, PROMO_CODES_FILE)


def generate_code(length: int = 12) -> str:
    return secrets.token_urlsafe(length)[:length]


def create_promo(plan_key: str) -> Optional[Tuple[str, Dict]]:
    if plan_key not in SUBSCRIPTION_PLANS:
        return None
    store = _read_store()
    code = generate_code()
    store[code] = {
        "plan_key": plan_key,
    }
    _write_store(store)
    return code, SUBSCRIPTION_PLANS[plan_key]


def consume_promo(code: str) -> Optional[str]:
    store = _read_store()
    item = store.get(code)
    if not item:
        return None
    if item.get("used"):
        return "USED"
    # Удаляем промокод после использования
    try:
        del store[code]
    except Exception:
        store.pop(code, None)
    _write_store(store)
    return item.get("plan_key")


