import os
from typing import Dict
from dotenv import load_dotenv

# Load environment variables from .env if present
load_dotenv()

# Telegram Bot
BOT_TOKEN = os.getenv('BOT_TOKEN')

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
        "price": 99,
    },
    "3_months": {
        "name": "3 месяца",
        "days": 90,
        "price": 249,
        
    },
    "6_months": {
        "name": "6 месяцев",
        "days": 180,
        "price": 399,
        
    }
}

# Тексты сообщений (HTML)
MESSAGES = {
    "welcome": (
        "🌐 <b>Averra VPN</b>\n"
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
        "🌍 <b>Страны в подписке</b>: \n🇫🇮 Финляндия (✔️TikTok)\n🇷🇺 Россия (✔️Глушилки, ✔️Youtube)"
    ),

    "payment_info": (
        "💳 <b>Оплата подписки</b>\n"
        "━━━━━━━━━━━━\n\n"
        "📦 Тариф: <b>{plan_name}</b>\n"
        "💰 Стоимость: <b>{price} ₽</b>\n"
        "📅 Срок: <b>{days} дней</b>\n\n"
        "Оплата проверяется автоматически. Нажмите кнопку ниже для оплаты:"
    )
}


