from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from keyboards.inline import get_main_menu
from config import MESSAGES, MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD, REFERRAL, BOT_USERNAME, BUTTONS, ADMIN_IDS
from services.marzban_service import MarzbanService
from utils.helpers import is_subscription_active
from utils.promo import consume_promo

router = Router()
marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)


@router.message(CommandStart())
async def start_handler(message: Message):
    """Обработчик команды /start"""
    # Определим текущий статус пользователя
    created_trial = False
    try:
        user_info = await marzban_service.get_user_info(message.from_user.id)
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
            note = None
            if referrer_id:
                note = f"{REFERRAL['note_prefix']}{referrer_id}"
            result = await marzban_service.create_user(message.from_user.id, trial_plan, note=note)
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
            user_info = await marzban_service.get_user_info(message.from_user.id)
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
    try:
        ref_payload = f"{REFERRAL['param']}_{callback.from_user.id}"
        bot_username = BOT_USERNAME or 'your_bot_username'
        ref_link = f"https://t.me/{bot_username}?start={ref_payload}"
    except Exception:
        ref_link = f"https://t.me/{BOT_USERNAME or 'your_bot_username'}?start={REFERRAL['param']}_{callback.from_user.id}"

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
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_main")]
    ])
    await callback.message.edit_text(text=text, reply_markup=kb)
    await callback.answer()


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
        [InlineKeyboardButton(text=BUTTONS["create_promo"], callback_data="promo_create")],
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
        [InlineKeyboardButton(text=BUTTONS["create_promo"], callback_data="promo_create")],
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_main")],
    ])
    await callback.message.edit_text(text=MESSAGES["admin_panel"], reply_markup=kb)
    await callback.answer(MESSAGES["maintenance_enabled"] if enable else MESSAGES["maintenance_disabled"])


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


