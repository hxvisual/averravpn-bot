import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from marzban import MarzbanAPI
from marzban.models import UserCreate, UserModify, ProxySettings

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
                "subscription_url": user_info.subscription_url
            }
        except Exception as e:
            logger.warning(f"User {telegram_id} not found: {e}")
            return None

    async def create_user(self, telegram_id: int, plan: Dict[str, Any]) -> Dict[str, Any]:
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
                expire=int(expire_date.timestamp())
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

    async def close(self):
        """Закрытие API клиента"""
        await self.api.close()


