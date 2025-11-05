import asyncio
import logging
from typing import Iterable

from aiogram import Router
from aiogram.types import Message

from config import (
    MARZBAN_BASE_URL,
    MARZBAN_USERNAME,
    MARZBAN_PASSWORD,
    NEWS_CHANNEL_ID,
    NEWS_CHANNEL_USERNAME,
)
from services.marzban_service import MarzbanService

router = Router()
logger = logging.getLogger(__name__)

marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)


def _is_configured_channel(chat_id: int | None, chat_username: str | None) -> bool:
    if NEWS_CHANNEL_ID is None and not NEWS_CHANNEL_USERNAME:
        return False

    if NEWS_CHANNEL_ID is not None and chat_id is not None and chat_id != NEWS_CHANNEL_ID:
        return False

    if NEWS_CHANNEL_USERNAME:
        username_normalized = (chat_username or "").lstrip('@').lower()
        if username_normalized != NEWS_CHANNEL_USERNAME:
            return False

    return True


def _extract_chat_ids(users: Iterable[dict]) -> list[int]:
    seen: set[int] = set()
    chat_ids: list[int] = []
    for user in users:
        try:
            username = (user.get("username") or "").strip()
            if not username.startswith("tg_"):
                continue
            tg_id_str = username.removeprefix("tg_")
            if not tg_id_str.isdigit():
                continue
            chat_id = int(tg_id_str)
            if chat_id in seen:
                continue
            seen.add(chat_id)
            chat_ids.append(chat_id)
        except Exception:
            continue
    return chat_ids


@router.channel_post()
async def forward_news_post(message: Message) -> None:
    """Пересылает новый пост из новостного канала всем пользователям."""
    channel = message.chat
    if channel is None:
        return

    if not _is_configured_channel(channel.id, getattr(channel, "username", None)):
        return

    try:
        users = await marzban_service.list_all_users()
    except Exception as exc:
        logger.error("Failed to list users for news forwarding: %s", exc)
        return

    recipients = _extract_chat_ids(users)
    if not recipients:
        logger.info("No recipients found for news forwarding")
        return

    sent = 0
    errors = 0

    for chat_id in recipients:
        try:
            await message.forward(chat_id=chat_id)
            sent += 1
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            errors += 1
            logger.debug("Failed to forward news to %s: %s", chat_id, exc)
        finally:
            await asyncio.sleep(0.03)

    logger.info(
        "News post forwarded: chat_id=%s, post_id=%s, recipients=%s, sent=%s, errors=%s",
        channel.id,
        message.message_id,
        len(recipients),
        sent,
        errors,
    )

