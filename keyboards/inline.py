from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUBSCRIPTION_PLANS, INSTRUCTION_URL, SUPPORT_URL


def get_main_menu(has_active: bool = False) -> InlineKeyboardMarkup:
    """Главное меню"""
    cta_text = "🔄 Продлить подписку" if has_active else "💳 Купить подписку"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Моя подписка", callback_data="my_subscription")],
        [InlineKeyboardButton(text=cta_text, callback_data="buy_subscription")],
        [InlineKeyboardButton(text="💬 Поддержка", url=SUPPORT_URL)]
    ])


def get_subscription_menu(has_subscription: bool = False) -> InlineKeyboardMarkup:
    """Меню подписки"""
    buttons = []
    
    if has_subscription:
        buttons.append([InlineKeyboardButton(text="🔄 Продлить подписку", callback_data="extend_subscription")])
        buttons.append([InlineKeyboardButton(text="📖 Инструкция", url=INSTRUCTION_URL)])
    else:
        buttons.append([InlineKeyboardButton(text="💳 Купить подписку", callback_data="buy_subscription")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_plans_menu() -> InlineKeyboardMarkup:
    """Меню выбора тарифов"""
    buttons = []
    
    for plan_key, plan_info in SUBSCRIPTION_PLANS.items():
        text = f"{plan_info['name']} - {plan_info['price']} ₽"
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"plan_{plan_key}")])
    
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_menu(payment_url: str) -> InlineKeyboardMarkup:
    """Меню оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
        [InlineKeyboardButton(text="🔙 Назад к тарифам", callback_data="buy_subscription")]
    ])


