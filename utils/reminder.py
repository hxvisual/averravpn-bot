import logging
from datetime import datetime, timedelta
from typing import Optional

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from services.marzban_service import MarzbanService
from config import (
    MESSAGES,
    BUTTONS,
    MARZBAN_BASE_URL,
    MARZBAN_USERNAME,
    MARZBAN_PASSWORD,
)
from utils.helpers import format_ts_to_str


logger = logging.getLogger(__name__)


def _today_tag() -> str:
    return datetime.now().strftime("%Y%m%d")


def _merge_note_with_notify_tag(existing: Optional[str], tag: str) -> str:
    """Merge existing note (may contain ref:...) with notify tag nd:<YYYYMMDD>.

    Preserves referral note prefix if present, uses '|' as separator.
    """
    base = (existing or "").strip()
    parts = [p for p in base.split("|") if p]
    # Remove previous nd:*
    parts = [p for p in parts if not p.startswith("nd:")]
    parts.append(f"nd:{tag}")
    return "|".join(parts) if parts else f"nd:{tag}"


def _already_notified_today(note: Optional[str]) -> bool:
    try:
        base = (note or "").strip()
        parts = [p for p in base.split("|") if p]
        for p in parts:
            if p.startswith("nd:") and p.removeprefix("nd:") == _today_tag():
                return True
        return False
    except Exception:
        return False


async def run_expiry_reminders(bot: Bot) -> None:
    """Send reminders to users whose subscription expires in ~24 hours.

    Uses Marzban usernames like 'tg_<telegram_id>' to determine chat ids.
    Stores per-day notification marker in user's Marzban note as 'nd:<YYYYMMDD>'.
    """
    service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)
    try:
        users = await service.list_all_users()
    except Exception as e:
        logger.error("Failed to load users for reminders: %s", e)
        return

    now = datetime.now()
    window_end = now + timedelta(days=1, hours=0)

    sent = 0
    for u in users:
        try:
            status = u.get("status")
            expire_ts = int(u.get("expire") or 0)
            username = u.get("username") or ""
            note = u.get("note")

            if status != "active" or not expire_ts or not username.startswith("tg_"):
                continue

            expire_dt = datetime.fromtimestamp(expire_ts)
            # Within (0, 24h]
            if not (now < expire_dt <= window_end):
                continue

            if _already_notified_today(note):
                continue

            tg_id_str = username.removeprefix("tg_")
            if not tg_id_str.isdigit():
                continue
            chat_id = int(tg_id_str)

            expire_str = format_ts_to_str(expire_ts)
            text = MESSAGES.get("subscription_expiring", "Ваша подписка скоро заканчивается: {expire_str}").format(
                expire_str=expire_str
            )
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=BUTTONS["extend_subscription"], callback_data="extend_subscription")],
                [InlineKeyboardButton(text=BUTTONS["my_subscription"], callback_data="my_subscription")],
            ])

            try:
                await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
                sent += 1
            except Exception as send_err:
                logger.warning("Failed to send reminder to %s: %s", chat_id, send_err)
                continue

            # Mark notified today in note
            try:
                new_note = _merge_note_with_notify_tag(note, _today_tag())
                await service.set_user_note(chat_id, new_note)
            except Exception as mark_err:
                logger.debug("Failed to set notify tag for %s: %s", chat_id, mark_err)

        except Exception:
            continue

    if sent:
        logger.info("Sent %d expiry reminders", sent)


