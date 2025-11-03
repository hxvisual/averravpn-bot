import uuid
import hashlib
import hmac
from typing import Dict, Any
from urllib.parse import urlencode
import logging

logger = logging.getLogger(__name__)


class PaymentService:
    def __init__(self, wallet_id: str, notification_secret: str):
        self.wallet_id = wallet_id
        self.notification_secret = notification_secret
        self.payment_url = "https://yoomoney.ru/quickpay/confirm.xml"

    def generate_payment_url(self, amount: float, telegram_id: int, plan_key: str) -> str:
        """Генерация ссылки на оплату"""
        label = f"{telegram_id}_{plan_key}_{uuid.uuid4().hex[:8]}"
        
        params = {
            "receiver": self.wallet_id,
            "quickpay-form": "shop",
            "targets": "Averra VPN",
            "paymentType": "PC",
            "sum": str(amount),
            "label": label,
            "successURL": f"https://t.me/averravpnbot"
        }
        
        return f"{self.payment_url}?{urlencode(params)}"

    def verify_notification(self, data: Dict[str, Any]) -> bool:
        """Проверка подлинности уведомления от YooMoney (Quickpay HTTP-уведомления).

        Формат вычисления sha1_hash согласно документации:
        sha1("notification_type&operation_id&amount&currency&datetime&sender&codepro&notification_secret&label")
        """
        try:
            parts = [
                data.get('notification_type', ''),
                data.get('operation_id', ''),
                data.get('amount', ''),
                data.get('currency', ''),
                data.get('datetime', ''),
                data.get('sender', ''),
                data.get('codepro', ''),
                self.notification_secret or '',
                data.get('label', ''),
            ]
            sign_string = "&".join(parts)
            expected_sha1 = hashlib.sha1(sign_string.encode('utf-8')).hexdigest().lower()
            received_sha1 = (data.get('sha1_hash') or '').lower()
            ok = hmac.compare_digest(expected_sha1, received_sha1)
            if not ok:
                logger.warning(
                    "YooMoney signature mismatch: expected=%s received=%s label=%s",
                    expected_sha1,
                    received_sha1,
                    data.get('label')
                )
            return ok
        except Exception as e:
            logger.error(f"Payment verification error: {e}")
            return False

    def parse_payment_data(self, label: str) -> Dict[str, Any]:
        """Разобрать данные платежа из label.

        Возвращает словарь с ключами:
        - telegram_id: int
        - plan_key: str
        - payment_id: str

        Поддерживает plan_key с символами '_' (например, '1_month').
        Формат label: <telegram_id>_<plan_key>_<payment_id>
        Разбор: первый '_' отделяет telegram_id, последний '_' — payment_id, середина — plan_key.
        При ошибке возвращается пустой словарь.
        """
        try:
            if not label or '_' not in label:
                return {}
            first_sep = label.find('_')
            last_sep = label.rfind('_')
            if first_sep == -1 or last_sep == -1 or last_sep <= first_sep:
                return {}
            telegram_id_str = label[:first_sep]
            plan_key = label[first_sep + 1:last_sep]
            payment_id = label[last_sep + 1:]
            return {
                "telegram_id": int(telegram_id_str),
                "plan_key": plan_key,
                "payment_id": payment_id,
            }
        except Exception as e:
            logger.error(f"Failed to parse payment data: {e}")
            return {}


