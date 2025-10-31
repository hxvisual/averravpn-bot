from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import SUBSCRIPTION_PLANS, INSTRUCTION_URL, SUPPORT_URL, NEWS_URL, BUTTONS, MESSAGES


def get_main_menu(has_active: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    """Главное меню"""
    cta_text = BUTTONS["extend_subscription"] if has_active else BUTTONS["buy_subscription"]
    rows = [
        [
            InlineKeyboardButton(text=BUTTONS["my_subscription"], callback_data="my_subscription"),
            InlineKeyboardButton(text=cta_text, callback_data="buy_subscription"),
        ],
        [InlineKeyboardButton(text=BUTTONS["referrals"], callback_data="ref_info")],
    ]
    support_news_row = []
    if SUPPORT_URL:
        support_news_row.append(InlineKeyboardButton(text=BUTTONS["support"], url=SUPPORT_URL))
    if NEWS_URL:
        support_news_row.append(InlineKeyboardButton(text=BUTTONS["news"], url=NEWS_URL))
    # Добавим кнопку админки для админов по отдельному вызову — здесь оставляем публичное меню
    if support_news_row:
        rows.append(support_news_row)
    if is_admin:
        rows.append([InlineKeyboardButton(text=BUTTONS["admin_panel"], callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_subscription_menu(has_subscription: bool = False) -> InlineKeyboardMarkup:
    """Меню подписки"""
    buttons = []
    
    if has_subscription:
        buttons.append([InlineKeyboardButton(text=BUTTONS["extend_subscription"], callback_data="extend_subscription")])
        if INSTRUCTION_URL:
            buttons.append([InlineKeyboardButton(text=BUTTONS["instruction"], url=INSTRUCTION_URL)])
    else:
        buttons.append([InlineKeyboardButton(text=BUTTONS["buy_subscription"], callback_data="buy_subscription")])
    
    buttons.append([InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_plans_menu() -> InlineKeyboardMarkup:
    """Меню выбора тарифов"""
    buttons = []
    # Переносим кнопку ввода промокода в экран покупки/продления
    buttons.append([InlineKeyboardButton(text=BUTTONS["enter_promo"], callback_data="enter_promo")])
    
    for plan_key, plan_info in SUBSCRIPTION_PLANS.items():
        text = MESSAGES["plan_button"].format(name=plan_info['name'], price=plan_info['price'])
        buttons.append([InlineKeyboardButton(text=text, callback_data=f"plan_{plan_key}")])
    
    buttons.append([InlineKeyboardButton(text=BUTTONS["back"], callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_payment_menu(payment_url: str) -> InlineKeyboardMarkup:
    """Меню оплаты"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=BUTTONS["pay"], url=payment_url)],
        [InlineKeyboardButton(text=BUTTONS["back_to_plans"], callback_data="buy_subscription")]
    ])


