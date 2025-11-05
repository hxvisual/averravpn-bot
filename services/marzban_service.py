import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from marzban import MarzbanAPI
from marzban.models import UserCreate, UserModify, ProxySettings

from utils.helpers import extract_referrer_id

logger = logging.getLogger(__name__)


class MarzbanService:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url
        self.username = username
        self.password = password
        self.api = MarzbanAPI(base_url=base_url)
        self.token: Optional[str] = None
        self.token_expires: Optional[datetime] = None
        
    async def get_token(self) -> str:
        """Получение и обновление токена"""
        if not self.token or (self.token_expires and datetime.now() >= self.token_expires):
            try:
                token_response = await self.api.get_token(
                    username=self.username, 
                    password=self.password
                )
                self.token = token_response.access_token
                # Токен действует 1 час, обновляем за 5 минут до истечения
                self.token_expires = datetime.now() + timedelta(minutes=55)
                logger.info("Token refreshed successfully")
            except Exception as e:
                logger.error(f"Failed to get token: {e}")
                raise
        return self.token

    async def get_user_info(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        """Получение информации о пользователе по Telegram ID"""
        try:
            token = await self.get_token()
            username = f"tg_{telegram_id}"
            
            user_info = await self.api.get_user(username=username, token=token)
            return {
                "username": user_info.username,
                "status": user_info.status,
                "expire": user_info.expire,
                "data_limit": user_info.data_limit,
                "used_traffic": user_info.used_traffic,
                "subscription_url": user_info.subscription_url,
                "note": getattr(user_info, "note", None),
            }
        except Exception as e:
            logger.warning(f"User {telegram_id} not found: {e}")
            return None

    async def create_user(self, telegram_id: int, plan: Dict[str, Any], note: Optional[str] = None) -> Dict[str, Any]:
        """Создание нового пользователя"""
        try:
            token = await self.get_token()
            username = f"tg_{telegram_id}"
            
            # Настройки прокси для VLESS Reality
            proxies = {
                "vless": ProxySettings(flow="xtls-rprx-vision")
            }
            
            expire_date = datetime.now() + timedelta(days=plan["days"])
            
            # Создаем пользователя без ограничения трафика (безлимит)
            new_user = UserCreate(
                username=username,
                proxies=proxies,
                data_limit=None,
                expire=int(expire_date.timestamp()),
                note=note,
            )
            
            created_user = await self.api.add_user(user=new_user, token=token)
            
            return {
                "username": created_user.username,
                "subscription_url": created_user.subscription_url,
                "expire": created_user.expire
            }
        except Exception as e:
            logger.error(f"Failed to create user {telegram_id}: {e}")
            raise

    async def extend_subscription(self, telegram_id: int, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Продление подписки существующего пользователя"""
        try:
            token = await self.get_token()
            username = f"tg_{telegram_id}"
            
            # Получаем текущую информацию о пользователе
            current_user = await self.api.get_user(username=username, token=token)
            
            # Если подписка еще активна, продлеваем от текущей даты истечения
            current_expire = datetime.fromtimestamp(current_user.expire)
            if current_expire > datetime.now():
                new_expire = current_expire + timedelta(days=plan["days"])
            else:
                new_expire = datetime.now() + timedelta(days=plan["days"])
            
            # Лимит трафика не изменяем (оставляем безлимит), продлеваем срок и активируем
            user_modify = UserModify(
                expire=int(new_expire.timestamp()),
                status="active"
            )
            
            modified_user = await self.api.modify_user(
                username=username, 
                user=user_modify, 
                token=token
            )
            
            return {
                "username": modified_user.username,
                "subscription_url": modified_user.subscription_url,
                "expire": modified_user.expire
            }
        except Exception as e:
            logger.error(f"Failed to extend subscription for {telegram_id}: {e}")
            raise

    async def extend_by_days(self, telegram_id: int, days: int) -> Dict[str, Any]:
        """Продлить подписку на указанное количество дней."""
        try:
            token = await self.get_token()
            username = f"tg_{telegram_id}"

            current_user = await self.api.get_user(username=username, token=token)
            current_expire = datetime.fromtimestamp(current_user.expire)
            if current_expire > datetime.now():
                new_expire = current_expire + timedelta(days=days)
            else:
                new_expire = datetime.now() + timedelta(days=days)

            user_modify = UserModify(
                expire=int(new_expire.timestamp()),
                status="active"
            )

            modified_user = await self.api.modify_user(
                username=username,
                user=user_modify,
                token=token,
            )

            return {
                "username": modified_user.username,
                "subscription_url": modified_user.subscription_url,
                "expire": modified_user.expire,
            }
        except Exception as e:
            logger.error(f"Failed to extend by days for {telegram_id}: {e}")
            raise

    async def set_user_note(self, telegram_id: int, note: str) -> bool:
        """Установить комментарий (note) у пользователя."""
        try:
            token = await self.get_token()
            username = f"tg_{telegram_id}"
            user_modify = UserModify(note=note)
            await self.api.modify_user(username=username, user=user_modify, token=token)
            return True
        except Exception as e:
            logger.error(f"Failed to set note for {telegram_id}: {e}")
            return False

    async def count_referrals_for(self, referrer_id: int) -> int:
        """Подсчитать число пользователей, у которых note начинается с ref:<referrer_id>."""
        try:
            token = await self.get_token()
            # Используем пагинацию, чтобы надёжно пройтись по всем пользователям
            offset = 0
            limit = 200
            total_count = 0
            while True:
                resp = await self.api.get_users(token=token, offset=offset, limit=limit)
                users = getattr(resp, "users", [])
                if not users:
                    break
                for u in users:
                    try:
                        ref_id = extract_referrer_id(getattr(u, "note", ""))
                        if ref_id == referrer_id:
                            total_count += 1
                    except Exception:
                        continue
                offset += limit
                if len(users) < limit:
                    break
            return total_count
        except Exception as e:
            logger.error(f"Failed to count referrals for {referrer_id}: {e}")
            return 0

    async def close(self):
        """Закрытие API клиента"""
        await self.api.close()

    async def list_all_users(self) -> list[Dict[str, Any]]:
        """Вернуть плоский список всех пользователей из Marzban.

        Каждый элемент содержит ключи: username, status, expire, data_limit, used_traffic, subscription_url, note.
        """
        try:
            token = await self.get_token()
            offset = 0
            limit = 200
            result: list[Dict[str, Any]] = []
            while True:
                resp = await self.api.get_users(token=token, offset=offset, limit=limit)
                users = getattr(resp, "users", [])
                if not users:
                    break
                for u in users:
                    try:
                        result.append({
                            "username": getattr(u, "username", None),
                            "status": getattr(u, "status", None),
                            "expire": getattr(u, "expire", None),
                            "data_limit": getattr(u, "data_limit", None),
                            "used_traffic": getattr(u, "used_traffic", None),
                            "subscription_url": getattr(u, "subscription_url", None),
                            "note": getattr(u, "note", None),
                        })
                    except Exception:
                        continue
                offset += limit
                if len(users) < limit:
                    break
            return result
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return []


