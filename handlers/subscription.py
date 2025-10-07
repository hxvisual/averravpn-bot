from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.marzban_service import MarzbanService
from keyboards.inline import get_subscription_menu, get_plans_menu
from config import MESSAGES, MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD, BUTTONS
from utils.helpers import (
    is_subscription_active,
    bytes_to_gigabytes,
    get_display_username,
    format_ts_to_str,
)

router = Router()
marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)


@router.callback_query(F.data == "my_subscription")
async def my_subscription_handler(callback: CallbackQuery):
    """Показать информацию о подписке"""
    telegram_id = callback.from_user.id
    user_info = await marzban_service.get_user_info(telegram_id)
    
    # Определяем активность
    is_active = is_subscription_active(user_info)

    if not user_info or not is_active:
        # Нет подписки (трактуем выключенный/истёкший профиль как отсутствие подписки)
        await callback.message.edit_text(
            text=MESSAGES["no_subscription"],
            reply_markup=get_plans_menu()
        )
    else:
        # Есть подписка
        expire_date = format_ts_to_str(int(user_info.get("expire", 0) or 0))
        used_gb = bytes_to_gigabytes(user_info.get("used_traffic", 0))
        total_gb = "∞" if not user_info.get("data_limit") else f"{bytes_to_gigabytes(user_info['data_limit'])} ГБ"
        display_username = get_display_username(user_info.get("username"))
        
        # Выбираем единый шаблон по состоянию
        if is_active:
            template = MESSAGES["subscription_active"]
        else:
            template = MESSAGES["subscription_expired"]

        text = template.format(
            display_username=display_username,
            expire_date=expire_date,
            used_gb=used_gb,
            total_gb=total_gb,
            subscription_url=user_info.get("subscription_url", "")
        )
        
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb = get_subscription_menu(has_subscription=True)
        # Добавим кнопку ввода промокода
        try:
            # Extend existing inline keyboard with promo button before Back
            rows = list(kb.inline_keyboard)
            rows.insert(0, [InlineKeyboardButton(text=BUTTONS["enter_promo"], callback_data="enter_promo")])
            kb = InlineKeyboardMarkup(inline_keyboard=rows)
        except Exception:
            pass
        await callback.message.edit_text(text=text, reply_markup=kb)
    
    await callback.answer()


@router.callback_query(F.data.in_(["buy_subscription", "extend_subscription"]))
async def show_plans(callback: CallbackQuery):
    """Показать тарифные планы"""
    await callback.message.edit_text(
        text=MESSAGES["no_subscription"],
        reply_markup=get_plans_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "enter_promo")
async def enter_promo(callback: CallbackQuery):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["back"], callback_data="my_subscription")]
    ])
    await callback.message.edit_text(MESSAGES.get("promo_prompt", "Введите промокод:"), reply_markup=kb)
    await callback.answer()


# Ручка получения ссылки больше не нужна — ссылка показывается прямо в профиле


