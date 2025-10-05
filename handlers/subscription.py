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
        
        # Определяем текст действия
        if is_active:
            action_text = "⚠️ Перед подключением откройте кнопку \"Инструкция\" ниже и следуйте шагам."
        else:
            action_text = "Подписка истекла. Продлите её для продолжения использования."
        
        # Формируем текст с прямой ссылкой (если активна)
        link_block = ""
        if is_active and user_info.get("subscription_url"):
            link_block = (
                "\n\n🔗 <b>Ссылка для подключения</b>\n"
                f"<code>{user_info['subscription_url']}</code>"
            )

        text = (
            "📊 <b>Информация о подписке</b>\n"
            "━━━━━━━━━━━━\n\n"
            f"👤 Пользователь: <b>{display_username}</b>\n"
            f"⏳ Истекает: <b>{expire_date}</b>\n"
            f"📈 Использовано: <b>{used_gb} ГБ</b> / <b>{total_gb}</b>"
            f"{link_block}\n\n"
            f"{action_text}"
        )
        
        await callback.message.edit_text(
            text=text,
            reply_markup=get_subscription_menu(has_subscription=True)
        )
    
    await callback.answer()


@router.callback_query(F.data.in_(["buy_subscription", "extend_subscription"]))
async def show_plans(callback: CallbackQuery):
    """Показать тарифные планы"""
    await callback.message.edit_text(
        text=(
            "📦 <b>Выберите тарифный план</b>\n"
            "━━━━━━━━━━━━\n\n"
            "✅ Высокая скорость\n"
            "✅ Неограниченные устройства\n"
            "✅ Поддержка 24/7\n\n"
            "🌍 <b>Страны в подписке</b>: \n🇫🇮 Финляндия (✔️TikTok)\n🇷🇺 Россия (✔️Глушилки, ✔️Youtube)"
        ),
        reply_markup=get_plans_menu()
    )
    await callback.answer()


# Ручка получения ссылки больше не нужна — ссылка показывается прямо в профиле


