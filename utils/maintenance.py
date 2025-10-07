from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from typing import Callable, Awaitable, Dict, Any
import os

from config import ADMIN_IDS, ADMIN_IDS_STR, MAINTENANCE_FLAG_FILE, MESSAGES


def is_maintenance_enabled() -> bool:
    try:
        return os.path.exists(MAINTENANCE_FLAG_FILE)
    except Exception:
        return False


def set_maintenance_enabled(enabled: bool) -> None:
    try:
        if enabled:
            with open(MAINTENANCE_FLAG_FILE, 'w', encoding='utf-8') as f:
                f.write('1')
        else:
            if os.path.exists(MAINTENANCE_FLAG_FILE):
                os.remove(MAINTENANCE_FLAG_FILE)
    except Exception:
        pass


class MaintenanceMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        try:
            user_id = event.from_user.id if getattr(event, 'from_user', None) else None
            if not user_id:
                return await handler(event, data)
            # Администраторы не блокируются (по int и str ID)
            if user_id in ADMIN_IDS or str(user_id) in ADMIN_IDS_STR:
                return await handler(event, data)
            if is_maintenance_enabled():
                # Block non-admins
                if isinstance(event, CallbackQuery):
                    await event.message.edit_text(MESSAGES["maintenance_active"])
                    await event.answer()
                else:
                    await event.answer(MESSAGES["maintenance_active"])
                return None
            return await handler(event, data)
        except Exception:
            return await handler(event, data)
