import html
from datetime import datetime
from typing import Any

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from config import (
    ADMIN_IDS,
    BUTTONS,
    MARZBAN_BASE_URL,
    MARZBAN_PASSWORD,
    MARZBAN_USERNAME,
    MESSAGES,
)
from services.marzban_service import MarzbanService
from utils.helpers import bytes_to_gigabytes, extract_username, format_ts_to_str


router = Router()
marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)

PAGE_SIZE = 5


class UserManageStates(StatesGroup):
    browsing = State()
    waiting_for_search_query = State()
    waiting_for_extend_days = State()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _is_cancel(text: str | None) -> bool:
    if not text:
        return False
    return text.strip().lower() in {"отмена", "cancel"}


def _status_badge(status: str | None) -> str:
    mapping = {
        "active": "🟢",
        "expired": "🔴",
        "disabled": "⚪",
        "limited": "🟡",
    }
    return mapping.get((status or "").lower(), "⚫")


def _short_expire(ts: Any) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d.%m.%y")
    except Exception:
        return "—"


async def _refresh_user_list(state: FSMContext) -> list[dict[str, Any]]:
    raw_users = await marzban_service.list_all_users()
    prepared: list[dict[str, Any]] = []
    for user in raw_users or []:
        username = user.get("username")
        if not isinstance(username, str) or not username.startswith("tg_"):
            continue
        tg_str = username.removeprefix("tg_")
        if not tg_str.isdigit():
            continue
        telegram_id = int(tg_str)
        note = user.get("note")
        expire_raw = user.get("expire")
        try:
            expire_ts = int(expire_raw) if expire_raw else None
        except (TypeError, ValueError):
            expire_ts = None

        used_raw = user.get("used_traffic")
        try:
            used_val = float(used_raw)
        except (TypeError, ValueError):
            used_val = 0.0

        data_limit_raw = user.get("data_limit")
        try:
            data_limit_val = float(data_limit_raw) if data_limit_raw else None
        except (TypeError, ValueError):
            data_limit_val = None

        prepared.append(
            {
                "telegram_id": telegram_id,
                "marzban_username": username,
                "status": user.get("status"),
                "expire": expire_ts,
                "used_traffic": used_val,
                "data_limit": data_limit_val,
                "subscription_url": user.get("subscription_url"),
                "note": note,
                "note_username": extract_username(note),
            }
        )
    prepared.sort(
        key=lambda item: ((item.get("expire") or 0), -item["telegram_id"]),
        reverse=True,
    )
    await state.update_data(user_list=prepared)
    return prepared


async def _load_user_list(state: FSMContext) -> list[dict[str, Any]]:
    data = await state.get_data()
    user_list = data.get("user_list")
    if isinstance(user_list, list) and user_list:
        return user_list
    return await _refresh_user_list(state)


def _ensure_page(users: list[dict[str, Any]], page: int) -> int:
    if not users:
        return 0
    max_page = max((len(users) - 1) // PAGE_SIZE, 0)
    if page < 0:
        return 0
    if page > max_page:
        return max_page
    return page


def _build_list_text(users: list[dict[str, Any]], page: int) -> str:
    total = len(users)
    if total == 0:
        return MESSAGES["admin_users_empty"]
    page = _ensure_page(users, page)
    pages = max((total - 1) // PAGE_SIZE + 1, 1)
    start_index = page * PAGE_SIZE
    page_users = users[start_index : start_index + PAGE_SIZE]
    lines = [
        "👥 <b>Управление пользователями</b>",
        "━━━━━━━━━━━━",
        "",
        f"Всего: <b>{total}</b>",
        f"Страница: <b>{page + 1}/{pages}</b>",
        "",
    ]
    for idx, entry in enumerate(page_users, start=start_index + 1):
        badge = _status_badge(entry.get("status"))
        expire_short = _short_expire(entry.get("expire"))
        alias = entry.get("note_username") or "—"
        lines.append(
            f"{idx}. {badge} <code>{entry['telegram_id']}</code> • {alias} • до {expire_short}"
        )
    lines.append("")
    return "\n".join(lines)


def _build_list_keyboard(users: list[dict[str, Any]], page: int) -> InlineKeyboardMarkup:
    keyboard_rows: list[list[InlineKeyboardButton]] = []
    total = len(users)
    if total:
        page = _ensure_page(users, page)
        start_index = page * PAGE_SIZE
        page_users = users[start_index : start_index + PAGE_SIZE]
        for entry in page_users:
            badge = _status_badge(entry.get("status"))
            expire_short = _short_expire(entry.get("expire"))
            label = f"{badge} {entry['telegram_id']} • до {expire_short}"
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=label,
                        callback_data=f"user_view:{entry['telegram_id']}",
                    )
                ]
            )
        nav_row: list[InlineKeyboardButton] = []
        if page > 0:
            nav_row.append(
                InlineKeyboardButton(
                    text="⬅️", callback_data=f"manage_users_page:{page - 1}"
                )
            )
        if (start_index + PAGE_SIZE) < total:
            nav_row.append(
                InlineKeyboardButton(
                    text="➡️", callback_data=f"manage_users_page:{page + 1}"
                )
            )
        if nav_row:
            keyboard_rows.append(nav_row)
    keyboard_rows.append(
        [
            InlineKeyboardButton(
                text=BUTTONS["admin_user_search"], callback_data="manage_users_search"
            ),
            InlineKeyboardButton(
                text=BUTTONS["admin_user_refresh"], callback_data="manage_users_refresh"
            ),
        ]
    )
    keyboard_rows.append(
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="admin_panel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard_rows)


async def _safe_edit_message(message: Message, text: str, keyboard: InlineKeyboardMarkup):
    try:
        await message.edit_text(text=text, reply_markup=keyboard)
    except TelegramBadRequest as err:
        if "message is not modified" not in (err.message or "").lower():
            raise


async def _render_user_list(
    message: Message, state: FSMContext, page: int = 0, refresh: bool = False
):
    users = await (_refresh_user_list(state) if refresh else _load_user_list(state))
    page = _ensure_page(users, page)
    text = _build_list_text(users, page)
    keyboard = _build_list_keyboard(users, page)
    await _safe_edit_message(message, text, keyboard)
    await state.update_data(
        manage_page=page,
        detail_user_id=None,
        detail_message_id=message.message_id,
        detail_chat_id=message.chat.id,
    )


async def _build_user_detail(
    telegram_id: int, state: FSMContext
) -> tuple[str, InlineKeyboardMarkup]:
    info = await marzban_service.get_user_info(telegram_id)
    if not info:
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=BUTTONS["admin_user_back"],
                        callback_data="manage_users_page:0",
                    )
                ]
            ]
        )
        return (
            f"❌ Пользователь <code>{telegram_id}</code> не найден.",
            keyboard,
        )

    data = await state.get_data()
    page = data.get("manage_page", 0)

    status = info.get("status")
    badge = _status_badge(status)

    expire = info.get("expire")
    expire_str = "—"
    if expire:
        try:
            expire_str = format_ts_to_str(int(expire))
        except Exception:
            expire_str = "—"

    used_bytes = info.get("used_traffic") or 0
    used_gb = bytes_to_gigabytes(used_bytes)
    data_limit = info.get("data_limit")
    limit_part = ""
    if data_limit:
        limit_part = f" / {bytes_to_gigabytes(data_limit)} ГБ"

    marzban_username = info.get("username") or f"tg_{telegram_id}"
    note = info.get("note")
    note_username = extract_username(note)
    subscription_url = info.get("subscription_url")

    lines = [
        f"👤 <b>Пользователь</b> <code>{telegram_id}</code>",
        "━━━━━━━━━━━━",
        f"Статус: {badge} <b>{status or 'unknown'}</b>",
        f"Истекает: <b>{expire_str}</b>",
        f"Трафик: <b>{used_gb}</b> ГБ{limit_part}",
        f"Логин Marzban: <code>{marzban_username}</code>",
    ]
    if note_username:
        lines.append(f"Username: {note_username}")
    if note:
        lines.append("Заметка:")
        lines.append(f"<code>{html.escape(str(note))}</code>")
    if subscription_url:
        lines.append("Ссылка для подключения:")
        lines.append(f"<code>{html.escape(str(subscription_url))}</code>")

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=BUTTONS["admin_user_extend"],
                    callback_data=f"user_extend:{telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BUTTONS["admin_user_expire"],
                    callback_data=f"user_expire:{telegram_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text=BUTTONS["admin_user_back"],
                    callback_data=f"manage_users_page:{page}",
                ),
                InlineKeyboardButton(
                    text=BUTTONS["admin_user_refresh"],
                    callback_data=f"user_refresh:{telegram_id}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text=BUTTONS["admin_user_search"],
                    callback_data="manage_users_search",
                )
            ],
        ]
    )

    return "\n".join(lines), keyboard


async def _render_user_detail(
    message: Message, state: FSMContext, telegram_id: int, refresh_list: bool = False
):
    if refresh_list:
        await _refresh_user_list(state)
    text, keyboard = await _build_user_detail(telegram_id, state)
    await _safe_edit_message(message, text, keyboard)
    await state.update_data(
        detail_user_id=telegram_id,
        detail_message_id=message.message_id,
        detail_chat_id=message.chat.id,
    )


async def _edit_detail_existing(bot, state: FSMContext, telegram_id: int):
    data = await state.get_data()
    message_id = data.get("detail_message_id")
    chat_id = data.get("detail_chat_id")
    if not message_id or not chat_id:
        return
    text, keyboard = await _build_user_detail(telegram_id, state)
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard,
        )
    except TelegramBadRequest as err:
        if "message is not modified" not in (err.message or "").lower():
            raise
    else:
        await state.update_data(detail_user_id=telegram_id)


@router.callback_query(F.data == "manage_users")
async def manage_users_entry(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(UserManageStates.browsing)
    try:
        await _render_user_list(callback.message, state, page=0, refresh=True)
    except TelegramBadRequest:
        await callback.message.answer(MESSAGES["admin_users_fetch_error"])
    await callback.answer()


@router.callback_query(F.data.startswith("manage_users_page:"))
async def manage_users_page(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    try:
        page = int(callback.data.split("manage_users_page:", 1)[1])
    except (TypeError, ValueError):
        page = 0
    await state.set_state(UserManageStates.browsing)
    await _render_user_list(callback.message, state, page=page, refresh=False)
    await callback.answer()


@router.callback_query(F.data == "manage_users_refresh")
async def manage_users_refresh(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    data = await state.get_data()
    page = data.get("manage_page", 0)
    await _render_user_list(callback.message, state, page=page, refresh=True)
    await callback.answer("Список обновлён")


@router.callback_query(F.data == "manage_users_search")
async def manage_users_search(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(UserManageStates.waiting_for_search_query)
    await callback.message.answer(MESSAGES["admin_users_search_prompt"])
    await callback.answer()


@router.message(UserManageStates.waiting_for_search_query)
async def manage_users_search_query(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return
    if _is_cancel(message.text):
        await state.set_state(UserManageStates.browsing)
        await message.answer(MESSAGES["admin_users_search_cancelled"])
        return

    query = (message.text or "").strip()
    if not query:
        await message.answer(MESSAGES["admin_users_search_no_results"])
        return

    users = await _refresh_user_list(state)

    matches: list[dict[str, Any]] = []
    if query.isdigit():
        target_id = int(query)
        matches = [u for u in users if u["telegram_id"] == target_id]
    else:
        normalized = query.lower().lstrip("@")
        for entry in users:
            note_user = (entry.get("note_username") or "").lstrip("@").lower()
            tg_id_str = str(entry["telegram_id"])
            marzban_username = entry.get("marzban_username", "").lower()
            if (
                normalized in note_user
                or normalized in marzban_username
                or normalized in tg_id_str
            ):
                matches.append(entry)

    if not matches:
        await message.answer(MESSAGES["admin_users_search_no_results"])
        return

    total_matches = len(matches)
    matches = matches[:10]
    shown = len(matches)
    rows = [
        [
            InlineKeyboardButton(
                text=f"{_status_badge(m['status'])} {m['telegram_id']}",
                callback_data=f"user_view:{m['telegram_id']}",
            )
        ]
        for m in matches
    ]
    rows.append(
        [InlineKeyboardButton(text=BUTTONS["admin_user_back"], callback_data="manage_users_page:0")]
    )

    text = MESSAGES["admin_users_search_results"].format(count=total_matches)
    if shown < total_matches:
        text = f"{text}\nПоказаны первые <b>{shown}</b>."

    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )
    await state.set_state(UserManageStates.browsing)


@router.callback_query(F.data.startswith("user_view:"))
async def manage_users_view(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    try:
        telegram_id = int(callback.data.split("user_view:", 1)[1])
    except (TypeError, ValueError):
        await callback.answer()
        return
    await state.set_state(UserManageStates.browsing)
    await _render_user_detail(callback.message, state, telegram_id, refresh_list=False)
    await callback.answer()


@router.callback_query(F.data.startswith("user_refresh:"))
async def manage_users_refresh_detail(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    try:
        telegram_id = int(callback.data.split("user_refresh:", 1)[1])
    except (TypeError, ValueError):
        await callback.answer()
        return
    await _render_user_detail(callback.message, state, telegram_id, refresh_list=True)
    await callback.answer("Обновлено")


@router.callback_query(F.data.startswith("user_extend:"))
async def manage_users_extend(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    try:
        telegram_id = int(callback.data.split("user_extend:", 1)[1])
    except (TypeError, ValueError):
        await callback.answer()
        return
    await state.update_data(
        target_user_id=telegram_id,
        detail_message_id=callback.message.message_id,
        detail_chat_id=callback.message.chat.id,
    )
    await state.set_state(UserManageStates.waiting_for_extend_days)
    await callback.message.answer(
        MESSAGES["admin_users_extend_prompt"].format(user_id=telegram_id)
    )
    await callback.answer()


@router.message(UserManageStates.waiting_for_extend_days)
async def manage_users_extend_days(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return

    if _is_cancel(message.text):
        await state.set_state(UserManageStates.browsing)
        await message.answer(MESSAGES["admin_users_extend_cancelled"])
        await state.update_data(target_user_id=None)
        return

    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(MESSAGES["admin_users_extend_invalid"])
        return

    days = int(text)
    if days <= 0:
        await message.answer(MESSAGES["admin_users_extend_invalid"])
        return

    data = await state.get_data()
    target_user = data.get("target_user_id")
    if not isinstance(target_user, int):
        await state.set_state(UserManageStates.browsing)
        await message.answer(MESSAGES["admin_users_fetch_error"])
        return

    try:
        result = await marzban_service.extend_by_days(target_user, days)
    except Exception:
        await message.answer(
            MESSAGES["admin_users_extend_failed"].format(user_id=target_user)
        )
        await state.set_state(UserManageStates.browsing)
        await state.update_data(target_user_id=None)
        return

    expire_ts = result.get("expire")
    expire_str = "—"
    if expire_ts:
        try:
            expire_str = format_ts_to_str(int(expire_ts))
        except Exception:
            expire_str = "—"

    await message.answer(
        MESSAGES["admin_users_extend_success"].format(
            user_id=target_user, days=days, expire_str=expire_str
        )
    )
    await state.set_state(UserManageStates.browsing)
    await _refresh_user_list(state)
    await _edit_detail_existing(message.bot, state, target_user)
    await state.update_data(target_user_id=None)


@router.callback_query(F.data.startswith("user_expire:"))
async def manage_users_expire(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.set_state(UserManageStates.browsing)
    try:
        telegram_id = int(callback.data.split("user_expire:", 1)[1])
    except (TypeError, ValueError):
        await callback.answer()
        return

    success = await marzban_service.expire_user(telegram_id)
    if not success:
        await callback.answer(MESSAGES["admin_users_expire_failed"], show_alert=True)
        return

    await callback.answer("Статус обновлён")
    await callback.message.answer(
        MESSAGES["admin_users_expire_success"].format(user_id=telegram_id)
    )
    await _refresh_user_list(state)
    await _render_user_detail(callback.message, state, telegram_id, refresh_list=False)

