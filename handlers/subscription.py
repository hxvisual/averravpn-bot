from aiogram import Router, F
from aiogram.types import CallbackQuery
from services.marzban_service import MarzbanService
from keyboards.inline import get_subscription_menu, get_plans_menu
from config import MESSAGES, MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD
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

    if not user_info:
        # Пользователь ещё ни разу не оформлял подписку
        await callback.message.edit_text(
            text=MESSAGES["no_subscription"],
            reply_markup=get_plans_menu()
        )
    elif not is_active:
        # Профиль есть, но подписка истекла — показываем предупреждение, без моментального перехода к оплате
        await callback.message.edit_text(
            text=MESSAGES["subscription_expired"],
            reply_markup=get_subscription_menu(has_subscription=False)
        )
    else:
        # Есть активная подписка
        # Показ бесконечного срока, если дата не установлена в Marzban
        _raw_exp = user_info.get("expire")
        expire_date = "∞" if not _raw_exp else format_ts_to_str(int(_raw_exp))
        used_gb = bytes_to_gigabytes(user_info.get("used_traffic", 0))
        total_gb = "∞" if not user_info.get("data_limit") else f"{bytes_to_gigabytes(user_info['data_limit'])} ГБ"
        display_username = get_display_username(user_info.get("username"))

        text = MESSAGES["subscription_active"].format(
            display_username=display_username,
            expire_date=expire_date,
            used_gb=used_gb,
            total_gb=total_gb,
            subscription_url=user_info.get("subscription_url", "")
        )

        kb = get_subscription_menu(has_subscription=True)
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
    prompt = MESSAGES.get("promo_prompt", "Введите промокод одним сообщением")
    await callback.answer(prompt, show_alert=True)


# Ручка получения ссылки больше не нужна — ссылка показывается прямо в профиле


