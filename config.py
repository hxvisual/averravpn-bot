import os
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv('BOT_TOKEN')
BOT_USERNAME = os.getenv('BOT_USERNAME')

# Marzban API
MARZBAN_BASE_URL = os.getenv('MARZBAN_BASE_URL')
MARZBAN_USERNAME = os.getenv('MARZBAN_USERNAME')
MARZBAN_PASSWORD = os.getenv('MARZBAN_PASSWORD')

# YooMoney
YOOMONEY_WALLET_ID = os.getenv('YOOMONEY_WALLET_ID')
YOOMONEY_NOTIFICATION_SECRET = os.getenv('YOOMONEY_NOTIFICATION_SECRET')

# Инструкция (Teletype) для подключения
INSTRUCTION_URL = os.getenv('INSTRUCTION_URL')

# Поддержка (URL чата/ник)
SUPPORT_URL = os.getenv('SUPPORT_URL')
 
# Новостной канал (URL)
NEWS_URL = os.getenv('NEWS_URL')

# Администраторы (через запятую)
ADMIN_IDS = []
ADMIN_IDS_STR = []
_raw_admins = os.getenv('ADMIN_IDS', '').strip()
if _raw_admins:
    try:
        parts = [x for x in _raw_admins.replace(' ', '').split(',') if x]
        ADMIN_IDS_STR = parts
        ADMIN_IDS = [int(x) for x in parts if x.isdigit()]
    except Exception:
        ADMIN_IDS = []
        ADMINIDS_STR = []
_single_admin = os.getenv('ADMIN_ID', '').strip()
if _single_admin:
    try:
        if _single_admin.isdigit():
            aid = int(_single_admin)
            if aid not in ADMIN_IDS:
                ADMIN_IDS.append(aid)
        if _single_admin not in ADMIN_IDS_STR:
            ADMIN_IDS_STR.append(_single_admin)
    except Exception:
        pass

# Режим обслуживания — файл-флаг (можно переопределить через env)
MAINTENANCE_FLAG_FILE = os.getenv('MAINTENANCE_FLAG_FILE', 'maintenance.lock')

# Webhook server (FastAPI)
# Provide safe defaults to avoid crashes when env vars are missing in dev
WEBHOOK_HOST = os.getenv('WEBHOOK_HOST', '0.0.0.0')
try:
    WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', '8080'))
except ValueError:
    WEBHOOK_PORT = 8080

# Подписки и цены
SUBSCRIPTION_PLANS: Dict[str, Dict] = {
    "1_month": {
        "name": "1 месяц",
        "days": 30,
        "price": 149,
    },
    "3_months": {
        "name": "3 месяца",
        "days": 90,
        "price": 299,
        
    },
    "6_months": {
        "name": "6 месяцев",
        "days": 180,
        "price": 449,
        
    }
}

# Тексты сообщений (HTML)
MESSAGES = {
    "welcome": (
        "🌐 <b>AverraVPN</b>\n"
        "━━━━━━━━━━━━\n\n"
        "<i>Надёжный и быстрый VPN для безопасного интернета.</i>\n\n"
        "🧩 <b>Преимущества</b>\n"
        "• ⚡ Высокая скорость\n"
        "• 📱 Неограниченные устройства\n"
        "• 🖥️ Все платформы\n"
        "• 🛟 Техподдержка 24/7\n\n"
        "Выберите действие ниже:"
    ),

    "no_subscription": (
        "📦 <b>Выберите тарифный план</b>\n"
        "━━━━━━━━━━━━\n\n"
        "✅ Высокая скорость\n"
        "✅ Неограниченные устройства\n"
        "✅ Поддержка 24/7\n\n"
        "🌍 <b>Страны в подписке</b>: \n🇫🇮 Финляндия\n\n‼Обход глушилок работает только на Т2, МТС, Ростелеком"
    ),

    "payment_info": (
        "💳 <b>Оплата подписки</b>\n"
        "━━━━━━━━━━━━\n\n"
        "📦 Тариф: <b>{plan_name}</b>\n"
        "💰 Стоимость: <b>{price} ₽</b>\n"
        "📅 Срок: <b>{days} дней</b>\n\n"
        "Оплата проверяется автоматически. Нажмите кнопку ниже для оплаты:"
    ),

    # Подписка — единые шаблоны сообщения
    "subscription_active": (
        "📊 <b>Информация о подписке</b>\n"
        "━━━━━━━━━━━━\n\n"
        "👤 Пользователь: <b>{display_username}</b>\n"
        "⏳ Истекает: <b>{expire_date}</b>\n"
        "📈 Использовано: <b>{used_gb} ГБ</b> / <b>{total_gb}</b>\n\n"
        "🔗 <b>Ссылка для подключения</b>\n<code>{subscription_url}</code>\n\n"
        "⚠️ Перед подключением откройте кнопку \"Инструкция\" ниже и следуйте шагам."
    ),
    "subscription_expired": (
        "⛔ <b>Подписка истекла</b>\n"
        "━━━━━━━━━━━━\n\n"
        "Доступ приостановлен. Продлите подписку, чтобы продолжить пользоваться сервисом.\n\n"
        "Нажмите кнопку \"Продлить подписку\" ниже и выберите подходящий тариф."
    ),

    # Кнопки тарифов
    "plan_button": "{name} - {price} ₽",

    # Ошибки/алерты
    "invalid_plan_alert": "❌ Неверный тариф",

    # Уведомления об оплате
    "payment_activated_title": "🎉 <b>Подписка активирована!</b>",
    "payment_received": (
        "✅ <b>Оплата получена</b>\n"
        "━━━━━━━━━━━━\n\n"
        "{status_line}\n"
        "⏳ Действует до: <b>{expire_str}</b>\n\n"
        "Откройте кнопку \"Моя подписка\" ниже, чтобы посмотреть статус и получить ссылку."
    ),

    # Пробный период
    "trial_activated_title": "🎁 <b>Пробный период активирован!</b>",
    "trial_activated": (
        "✅ <b>Активирован пробный доступ</b>\n"
        "━━━━━━━━━━━━\n\n"
        "{status_line}\n"
        "⏳ Действует до: <b>{expire_str}</b>\n\n"
        "Откройте кнопку \"Моя подписка\" ниже, чтобы получить ссылку и инструкции."
    ),
}


# Тексты кнопок (UI)
BUTTONS = {
    "my_subscription": "📊 Моя подписка",
    "buy_subscription": "💳 Купить подписку",
    "extend_subscription": "🔄 Продлить подписку",
    "instruction": "📖 Инструкция",
    "back": "🔙 Назад",
    "pay": "💳 Оплатить",
    "back_to_plans": "🔙 Назад к тарифам",
    "support": "💬 Поддержка",
    "news": "📰 Новостной канал",
    "referrals": "👥 Реферальная программа",
    "admin_panel": "🛠️ Админ панель",
    "maintenance_enable": "🟥 Включить обслуживание",
    "maintenance_disable": "🟩 Выключить обслуживание",
    "backup": "🗄️ Бэкап Marzban",
    "create_promo": "🎟️ Создать промокод",
    "enter_promo": "🎟️ Ввести промокод",
}

# Рефералы
REFERRAL = {
    "param": "ref",  # имя параметра deep-link
    "note_prefix": "ref:",  # префикс заметки (note) в профиле
    "bonus_percent": 30,
}

# Сообщения о реферальном бонусе
MESSAGES.update({
    "ref_bonus_title": "🎁 <b>Начислен реферальный бонус</b>",
    "ref_bonus_body": (
        "Вам начислено <b>{bonus_days} д.</b> за оплату приглашённого пользователя.\n"
        "Текущая подписка продлена до: <b>{expire_str}</b>."
    ),
})

# Информация о реферальной программе
MESSAGES.update({
    "ref_info": (
        "👥 <b>Реферальная программа</b>\n"
        "━━━━━━━━━━━━\n\n"
        "🔗 <b>Ваша ссылка</b>\n<code>{ref_link}</code>\n\n"
        "📊 <b>Ваши рефералы</b>: <b>{ref_count}</b>\n\n"
        "💡 За каждую оплату по вашей ссылке вы получаете <b>{percent}%</b> дней от купленного тарифа.\n\n"
        "Приглашайте друзей и продлевайте подписку выгодно!"
    )
})

# Режим обслуживания
MESSAGES.update({
    "maintenance_active": (
        "🚧 Режим обслуживания\n"
        "━━━━━━━━━━━━\n\n"
        "Бот временно недоступен. Пожалуйста, зайдите позже."
    ),
    "admin_panel": (
        "🛠️ <b>Админ панель</b>\n"
        "━━━━━━━━━━━━\n\n"
        "Выберите действие:"
    ),
    "maintenance_enabled": "✅ Режим обслуживания включён",
    "maintenance_disabled": "✅ Режим обслуживания выключен",
    "backup_started": "⏳ Запускаю бэкап...",
    "backup_success": "✅ Бэкап успешно выполнен",
    "backup_failed": "❌ Ошибка при выполнении бэкапа",
})

# Промокоды
PROMO_CODES_FILE = os.getenv('PROMO_CODES_FILE', 'promocodes.json')
MESSAGES.update({
    "promo_create_prompt": (
        "🎟️ <b>Создание промокода</b>\n"
        "━━━━━━━━━━━━\n\n"
        "Выберите тариф:"
    ),
    "promo_created": (
        "✅ <b>Промокод создан</b>\n"
        "━━━━━━━━━━━━\n\n"
        "Тариф: <b>{plan_name}</b>\n"
        "Код: <code>{code}</code>"
    ),
    "promo_prompt": "🎟️ Введите промокод одним сообщением:",
    "promo_invalid": "❌ Неверный промокод",
    "promo_used": "⚠️ Этот промокод уже использован",
    "promo_applied": (
        "🎉 <b>Промокод применён!</b>\n"
        "━━━━━━━━━━━━\n\n"
        "Тариф: <b>{plan_name}</b>\n"
        "Подписка действует до: <b>{expire_str}</b>"
    ),
})


