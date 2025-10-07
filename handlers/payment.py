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
    BUTTONS,
    REFERRAL,
)
from utils.maintenance import is_maintenance_enabled
from config import ADMIN_IDS, ADMIN_IDS_STR

router = Router()
logger = logging.getLogger(__name__)

marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)
payment_service = PaymentService(YOOMONEY_WALLET_ID, YOOMONEY_NOTIFICATION_SECRET)


@router.callback_query(F.data.startswith("plan_"))
async def process_plan_selection(callback: CallbackQuery):
    """Обработка выбора тарифного плана"""
    plan_key = callback.data.split("_", 1)[1]
    # Блокируем оплату в режиме обслуживания для НЕ-админов
    if is_maintenance_enabled() and callback.from_user:
        uid = getattr(callback.from_user, 'id', None)
        if uid is not None and (uid not in ADMIN_IDS and str(uid) not in ADMIN_IDS_STR):
            await callback.answer(MESSAGES["maintenance_active"], show_alert=True)
            return
        await callback.answer(MESSAGES["maintenance_active"], show_alert=True)
        return
    
    if plan_key not in SUBSCRIPTION_PLANS:
        await callback.answer(MESSAGES["invalid_plan_alert"], show_alert=True)
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
    # Уведомления об оплате принимаем, даже если обслуживание включено
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

                status_line = MESSAGES["payment_activated_title"]
                text = MESSAGES["payment_received"].format(
                    status_line=status_line,
                    expire_str=expire_str,
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text=BUTTONS["my_subscription"], callback_data="my_subscription")]
                ])
                await bot.send_message(chat_id=telegram_id, text=text, reply_markup=keyboard)
            except Exception as notify_err:
                logger.error("Failed to notify user %s: %s", telegram_id, notify_err)
        
        # Реферальный бонус: если у платящего пользователя есть реферер (в note), начисляем 30% от купленных дней
        try:
            user_info_after = await marzban_service.get_user_info(telegram_id)
            note = (user_info_after or {}).get("note") or ""
            ref_prefix = REFERRAL.get("note_prefix", "ref:")
            if isinstance(note, str) and note.startswith(ref_prefix):
                ref_id_str = note.removeprefix(ref_prefix)
                if ref_id_str.isdigit():
                    referrer_id = int(ref_id_str)
                    purchased_days = int(plan.get("days", 0))
                    bonus_days = max(1, (purchased_days * 3) // 10)
                    bonus_res = await marzban_service.extend_by_days(referrer_id, bonus_days)
                    if bot is not None:
                        try:
                            from utils.helpers import format_ts_to_str
                            expire_str = "—"
                            exp_ts = bonus_res.get("expire")
                            if exp_ts:
                                expire_str = format_ts_to_str(exp_ts)
                            bonus_title = MESSAGES["ref_bonus_title"]
                            bonus_body = MESSAGES["ref_bonus_body"].format(bonus_days=bonus_days, expire_str=expire_str)
                            await bot.send_message(chat_id=referrer_id, text=f"{bonus_title}\n\n{bonus_body}")
                        except Exception as ref_notify_err:
                            logger.error("Failed to notify referrer %s: %s", referrer_id, ref_notify_err)
        except Exception as ref_err:
            logger.error("Referral bonus error for payer %s: %s", telegram_id, ref_err)
        return True
    except Exception as e:
        logger.error(f"Failed to process payment for user {telegram_id}: {e}")
        return False


