import asyncio
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from keyboards.inline import get_main_menu
from config import MESSAGES, MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD, REFERRAL, BOT_USERNAME, BUTTONS, ADMIN_IDS
from services.marzban_service import MarzbanService
from utils.helpers import is_subscription_active, build_user_note, update_note_with_username
from utils.promo import consume_promo

router = Router()
marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)


class BroadcastStates(StatesGroup):
    waiting_for_message_all = State()
    waiting_for_user_id = State()
    waiting_for_message_single = State()


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def _is_cancel(message: Message) -> bool:
    if not message.text:
        return False
    return message.text.strip().lower() in {"отмена", "cancel"}


def _build_ref_link(user_id: int) -> str:
    param = REFERRAL.get("param", "ref")
    bot_username = BOT_USERNAME or "your_bot_username"
    return f"https://t.me/{bot_username}?start={param}_{user_id}"


@router.message(CommandStart())
async def start_handler(message: Message):
    """Обработчик команды /start"""
    # Определим текущий статус пользователя
    telegram_id = message.from_user.id
    raw_username = getattr(message.from_user, "username", None)
    created_trial = False
    try:
        user_info = await marzban_service.get_user_info(telegram_id)
    except Exception:
        user_info = None

    # Если пользователя нет — создаем пробный профиль на 3 дня
    if not user_info:
        # Извлекаем реферала из deep-link параметра
        referrer_id: int | None = None
        try:
            # message.text может быть вида "/start" или "/start <payload>"
            parts = (message.text or "").split(maxsplit=1)
            if len(parts) == 2:
                payload = parts[1]
                # ожидаем формат ref_<telegram_id>
                if payload.startswith(f"{REFERRAL['param']}_"):
                    ref_str = payload.split("_", 1)[1]
                    if ref_str.isdigit():
                        referrer_id = int(ref_str)
        except Exception:
            referrer_id = None

        try:
            trial_plan = {"name": "trial", "days": 3, "price": 0}
            note = build_user_note(referrer_id, raw_username)
            result = await marzban_service.create_user(telegram_id, trial_plan, note=note)
            created_trial = True
            # Сообщение об активации пробного периода
            try:
                from utils.helpers import format_ts_to_str
                expire_str = format_ts_to_str(result.get("expire", 0))
            except Exception:
                expire_str = "—"
            status_line = MESSAGES["trial_activated_title"]
            trial_text = MESSAGES["trial_activated"].format(
                status_line=status_line,
                expire_str=expire_str,
            )
            await message.answer(trial_text)
            # Обновим user_info для дальнейшей персонализации меню
            user_info = await marzban_service.get_user_info(telegram_id)
        except Exception:
            # Если не удалось создать пробный — продолжим без него
            created_trial = False

    is_active = is_subscription_active(user_info)

    await message.answer(
        text=MESSAGES["welcome"],
        reply_markup=get_main_menu(has_active=is_active, is_admin=message.from_user.id in ADMIN_IDS)
    )


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    # Определим активность для персонализации CTA
    try:
        user_info = await marzban_service.get_user_info(callback.from_user.id)
        is_active = is_subscription_active(user_info)
    except Exception:
        is_active = False
    await callback.message.edit_text(
        text=MESSAGES["welcome"],
        reply_markup=get_main_menu(has_active=is_active, is_admin=callback.from_user.id in ADMIN_IDS)
    )
    await callback.answer()


@router.callback_query(F.data == "ref_info")
async def show_ref_info(callback: CallbackQuery):
    """Показать информацию о реферальной программе и персональную ссылку"""
    ref_link = _build_ref_link(callback.from_user.id)

    # Считаем рефералов
    try:
        ref_count = await marzban_service.count_referrals_for(callback.from_user.id)
    except Exception:
        ref_count = 0
    text = MESSAGES["ref_info"].format(
        ref_link=ref_link,
        percent=REFERRAL.get("bonus_percent", 30),
        ref_count=ref_count,
    )
    # Добавим кнопку Назад
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["share_referral"], callback_data="ref_share")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text=text, reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "ref_share")
async def share_ref_message(callback: CallbackQuery):
    """Отправить пользователю заготовку сообщения для друга."""
    ref_link = _build_ref_link(callback.from_user.id)
    percent = REFERRAL.get("bonus_percent", 30)
    share_template = MESSAGES.get("ref_share_text")
    if share_template:
        text = share_template.format(ref_link=ref_link, percent=percent)
        await callback.message.answer(text)
    await callback.answer("Сообщение готово!")


@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from utils.maintenance import is_maintenance_enabled
    toggle_text = BUTTONS["maintenance_disable"] if is_maintenance_enabled() else BUTTONS["maintenance_enable"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="maintenance_toggle")],
        [InlineKeyboardButton(text=BUTTONS["backup"], callback_data="run_backup")],
        [InlineKeyboardButton(text=BUTTONS["manage_users"], callback_data="manage_users")],
        [InlineKeyboardButton(text=BUTTONS["create_promo"], callback_data="promo_create")],
        [InlineKeyboardButton(text=BUTTONS["sync_usernames"], callback_data="sync_usernames")],
        [InlineKeyboardButton(text=BUTTONS["broadcast"], callback_data="broadcast_menu")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_main")],
    ])
    await callback.message.edit_text(text=MESSAGES["admin_panel"], reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "maintenance_toggle")
async def toggle_maintenance(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    from utils.maintenance import set_maintenance_enabled, is_maintenance_enabled
    # Toggle current state
    enable = not is_maintenance_enabled()
    set_maintenance_enabled(enable)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    toggle_text = BUTTONS["maintenance_disable"] if is_maintenance_enabled() else BUTTONS["maintenance_enable"]
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=toggle_text, callback_data="maintenance_toggle")],
        [InlineKeyboardButton(text=BUTTONS["backup"], callback_data="run_backup")],
        [InlineKeyboardButton(text=BUTTONS["manage_users"], callback_data="manage_users")],
        [InlineKeyboardButton(text=BUTTONS["create_promo"], callback_data="promo_create")],
        [InlineKeyboardButton(text=BUTTONS["sync_usernames"], callback_data="sync_usernames")],
        [InlineKeyboardButton(text=BUTTONS["broadcast"], callback_data="broadcast_menu")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_main")],
    ])
    await callback.message.edit_text(text=MESSAGES["admin_panel"], reply_markup=kb)
    await callback.answer(MESSAGES["maintenance_enabled"] if enable else MESSAGES["maintenance_disabled"])


@router.callback_query(F.data == "sync_usernames")
async def sync_usernames(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return

    start_text = MESSAGES.get("sync_usernames_started") or "🔄 Начинаю синхронизацию юзернеймов..."
    await callback.answer(start_text)
    status_message = await callback.message.answer(start_text)

    try:
        users = await marzban_service.list_all_users()
    except Exception:
        await status_message.edit_text(MESSAGES.get("sync_usernames_error", "❌ Не удалось выполнить синхронизацию."))
        return

    candidates: list[tuple[int, dict]] = []
    for user in users or []:
        try:
            username_field = str(user.get("username") or "").strip()
            if not username_field.startswith("tg_"):
                continue
            tg_id_str = username_field.removeprefix("tg_")
            if not tg_id_str.isdigit():
                continue
            candidates.append((int(tg_id_str), user))
        except Exception:
            continue

    if not candidates:
        await status_message.edit_text(MESSAGES.get("sync_usernames_no_users", "⚠️ Пользователи не найдены."))
        return

    total = len(candidates)
    updated = 0
    unchanged = 0
    missing_username = 0
    errors = 0

    for tg_id, user in candidates:
        try:
            chat = await callback.bot.get_chat(tg_id)
            actual_username = getattr(chat, "username", None)
            if not actual_username:
                missing_username += 1

            new_note = update_note_with_username(user.get("note"), actual_username)
            current_note = user.get("note")
            if new_note == current_note:
                unchanged += 1
            else:
                try:
                    success = await marzban_service.set_user_note(tg_id, new_note)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    success = False

                if success:
                    updated += 1
                else:
                    errors += 1
        except asyncio.CancelledError:
            raise
        except Exception:
            errors += 1
        finally:
            await asyncio.sleep(0.03)

    summary_template = MESSAGES.get("sync_usernames_done")
    if summary_template:
        summary_text = summary_template.format(
            total=total,
            updated=updated,
            unchanged=unchanged,
            missing=missing_username,
            errors=errors,
        )
    else:
        summary_text = (
            f"Синхронизация завершена. Всего: {total}, обновлено: {updated}, "
            f"без изменений: {unchanged}, без username: {missing_username}, ошибок: {errors}."
        )

    await status_message.edit_text(summary_text)


@router.callback_query(F.data == "broadcast_menu")
async def broadcast_menu(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["broadcast_all"], callback_data="broadcast_all")],
        [InlineKeyboardButton(text=BUTTONS["broadcast_one"], callback_data="broadcast_one")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="admin_panel")],
    ])
    await callback.message.edit_text(text=MESSAGES["broadcast_menu"], reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "broadcast_all")
async def broadcast_all_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(BroadcastStates.waiting_for_message_all)
    await callback.message.answer(MESSAGES["broadcast_all_prompt"])
    await callback.answer()


@router.callback_query(F.data == "broadcast_one")
async def broadcast_one_prompt(callback: CallbackQuery, state: FSMContext):
    if not _is_admin(callback.from_user.id):
        await callback.answer()
        return
    await state.clear()
    await state.set_state(BroadcastStates.waiting_for_user_id)
    await callback.message.answer(MESSAGES["broadcast_user_prompt"])
    await callback.answer()


@router.message(BroadcastStates.waiting_for_user_id)
async def broadcast_user_id_received(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return
    if _is_cancel(message):
        await state.clear()
        await message.answer(MESSAGES["broadcast_cancelled"])
        return
    text = (message.text or "").strip()
    if not text.isdigit():
        await message.answer(MESSAGES["broadcast_invalid_user"])
        return
    target_id = int(text)
    await state.update_data(target_id=target_id)
    await state.set_state(BroadcastStates.waiting_for_message_single)
    await message.answer(MESSAGES["broadcast_enter_message"])


@router.message(BroadcastStates.waiting_for_message_all)
async def broadcast_message_all(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return
    if _is_cancel(message):
        await state.clear()
        await message.answer(MESSAGES["broadcast_cancelled"])
        return

    await message.answer(MESSAGES["broadcast_started"])

    try:
        users = await marzban_service.list_all_users()
    except Exception:
        users = []

    if not users:
        await message.answer(MESSAGES["broadcast_no_recipients"])
        await state.clear()
        return

    sent = 0
    total = 0
    seen_ids: set[int] = set()
    for user in users:
        try:
            username = (user.get("username") or "").strip()
            if not username.startswith("tg_"):
                continue
            tg_id_str = username.removeprefix("tg_")
            if not tg_id_str.isdigit():
                continue
            chat_id = int(tg_id_str)
            if chat_id in seen_ids:
                continue
            seen_ids.add(chat_id)
            total += 1
            try:
                await message.copy_to(chat_id=chat_id)
                sent += 1
            except Exception:
                continue
            await asyncio.sleep(0.05)
        except Exception:
            continue

    if total == 0:
        await message.answer(MESSAGES["broadcast_no_recipients"])
    else:
        await message.answer(MESSAGES["broadcast_done_all"].format(sent=sent, total=total))
    await state.clear()


@router.message(BroadcastStates.waiting_for_message_single)
async def broadcast_message_single(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id):
        await state.clear()
        return
    if _is_cancel(message):
        await state.clear()
        await message.answer(MESSAGES["broadcast_cancelled"])
        return

    data = await state.get_data()
    target_id = data.get("target_id")
    if not isinstance(target_id, int):
        await state.clear()
        await message.answer(MESSAGES["broadcast_cancelled"])
        return

    try:
        await message.copy_to(chat_id=target_id)
    except Exception:
        await message.answer(MESSAGES["broadcast_failed_one"].format(user_id=target_id))
    else:
        await message.answer(MESSAGES["broadcast_done_one"].format(user_id=target_id))
    finally:
        await state.clear()


@router.callback_query(F.data == "run_backup")
async def run_backup(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    from utils.backup import run_marzban_backup
    await callback.answer(MESSAGES["backup_started"], show_alert=True)
    ok, output, archive_path = await run_marzban_backup()
    if ok:
        # Отправим архив админу, если найден
        if archive_path:
            try:
                from aiogram.types import FSInputFile
                doc = FSInputFile(archive_path)
                await callback.message.answer_document(document=doc, caption=MESSAGES["backup_success"])
            except Exception:
                await callback.message.answer(MESSAGES["backup_success"]) 
        else:
            await callback.message.answer(MESSAGES["backup_success"]) 
    else:
        await callback.message.answer(f"{MESSAGES['backup_failed']}\n<code>{output[:1000]}</code>")


@router.message(F.text.regexp(r"^[A-Za-z0-9_-]{6,}$"))
async def promo_code_entered(message: Message):
    """Обработка ввода промокода в чате"""
    code = (message.text or "").strip()
    result = consume_promo(code)
    if result is None:
        await message.answer(MESSAGES.get("promo_invalid", "Неверный промокод"))
        return
    if result == "USED":
        await message.answer(MESSAGES.get("promo_used", "Промокод уже использован"))
        return
    plan_key = result
    from config import SUBSCRIPTION_PLANS
    plan = SUBSCRIPTION_PLANS.get(plan_key)
    if not plan:
        await message.answer(MESSAGES.get("promo_invalid", "Неверный промокод"))
        return
    # Активируем/продлеваем по промокоду
    try:
        user_info = await marzban_service.get_user_info(message.from_user.id)
        if user_info:
            res = await marzban_service.extend_subscription(message.from_user.id, plan)
        else:
            res = await marzban_service.create_user(message.from_user.id, plan)
        try:
            from utils.helpers import format_ts_to_str
            expire_str = format_ts_to_str(res.get("expire", 0))
        except Exception:
            expire_str = "—"
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=BUTTONS["my_subscription"], callback_data="my_subscription")]
        ])
        await message.answer(
            MESSAGES["promo_applied"].format(plan_name=plan['name'], expire_str=expire_str),
            reply_markup=kb,
        )
    except Exception:
        await message.answer(MESSAGES.get("promo_invalid", "Неверный промокод"))


@router.callback_query(F.data == "promo_create")
async def promo_create(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    from config import SUBSCRIPTION_PLANS
    buttons = []
    for plan_key, plan in SUBSCRIPTION_PLANS.items():
        buttons.append([InlineKeyboardButton(text=f"{plan['name']}", callback_data=f"promo_plan_{plan_key}")])
    buttons.append([InlineKeyboardButton(text=BUTTONS["back"], callback_data="admin_panel")])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await callback.message.edit_text(MESSAGES.get("promo_create_prompt", "Выберите тариф"), reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data.startswith("promo_plan_"))
async def promo_plan_selected(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer()
        return
    plan_key = callback.data.split("promo_plan_", 1)[1]
    from utils.promo import create_promo
    result = create_promo(plan_key)
    if not result:
        await callback.answer("Ошибка создания", show_alert=True)
        return
    code, plan = result
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="admin_panel")]
    ])
    await callback.message.edit_text(MESSAGES["promo_created"].format(plan_name=plan['name'], code=code), reply_markup=kb)
    await callback.answer()


