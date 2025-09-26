import logging
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from services.marzban_service import MarzbanService
from services.payment_service import PaymentService
from aiogram import Bot
from keyboards.inline import get_payment_menu
from config import (
    MESSAGES,
    SUBSCRIPTION_PLANS,
    YOOMONEY_WALLET_ID,
    YOOMONEY_NOTIFICATION_SECRET,
    MARZBAN_BASE_URL,
    MARZBAN_USERNAME,
    MARZBAN_PASSWORD,
)

router = Router()
logger = logging.getLogger(__name__)

marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)
payment_service = PaymentService(YOOMONEY_WALLET_ID, YOOMONEY_NOTIFICATION_SECRET)


@router.callback_query(F.data.startswith("plan_"))
async def process_plan_selection(callback: CallbackQuery):
    """Обработка выбора тарифного плана"""
    plan_key = callback.data.split("_", 1)[1]
    
    if plan_key not in SUBSCRIPTION_PLANS:
        await callback.answer("❌ Неверный тариф", show_alert=True)
        return
    
    plan = SUBSCRIPTION_PLANS[plan_key]
    telegram_id = callback.from_user.id
    
    # Генерируем ссылку на оплату
    payment_url = payment_service.generate_payment_url(
        amount=plan["price"],
        telegram_id=telegram_id,
        plan_key=plan_key
    )
    
    text = MESSAGES["payment_info"].format(
        plan_name=plan["name"],
        price=plan["price"],
        days=plan["days"]
    )
    
    await callback.message.edit_text(
        text=text,
        reply_markup=get_payment_menu(payment_url)
    )
    await callback.answer()


# Убрана кнопка проверки оплаты — статус проверяется вебхуком автоматически


# Webhook для обработки уведомлений от YooMoney (отдельный endpoint)
async def process_payment_notification(data: dict, bot: Bot | None = None):
    """Обработка уведомления об оплате"""
    if not payment_service.verify_notification(data):
        return False
    
    payment_data = payment_service.parse_payment_data(data.get("label", ""))
    if not payment_data:
        return False
    
    telegram_id = payment_data["telegram_id"]
    plan_key = payment_data["plan_key"]
    
    if plan_key not in SUBSCRIPTION_PLANS:
        return False
    
    plan = SUBSCRIPTION_PLANS[plan_key]
    
    try:
        # Проверяем, есть ли уже пользователь
        user_info = await marzban_service.get_user_info(telegram_id)
        
        if user_info:
            # Продлеваем подписку
            result = await marzban_service.extend_subscription(telegram_id, plan)
        else:
            # Создаем нового пользователя
            result = await marzban_service.create_user(telegram_id, plan)
        
        logger.info("Payment processed for user %s, until %s", telegram_id, result.get("expire"))

        # Notify user if bot instance provided
        if bot is not None:
            try:
                expire_ts = result.get("expire")
                expire_str = "—"
                try:
                    from utils.helpers import format_ts_to_str
                    if expire_ts:
                        expire_str = format_ts_to_str(expire_ts)
                except Exception:
                    pass

                status_line = "🎉 <b>Подписка активирована!</b>" 
                text = (
                    "✅ <b>Оплата получена</b>\n"
                    "━━━━━━━━━━━━\n\n"
                    f"{status_line}\n"
                    f"⏳ Действует до: <b>{expire_str}</b>\n\n"
                    "Откройте кнопку \"Моя подписка\" ниже, чтобы посмотреть статус и получить ссылку."
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="📊 Моя подписка", callback_data="my_subscription")]
                ])
                await bot.send_message(chat_id=telegram_id, text=text, reply_markup=keyboard)
            except Exception as notify_err:
                logger.error("Failed to notify user %s: %s", telegram_id, notify_err)
        return True
    except Exception as e:
        logger.error(f"Failed to process payment for user {telegram_id}: {e}")
        return False


