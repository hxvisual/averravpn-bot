from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from keyboards.inline import get_main_menu
from config import MESSAGES, MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD
from services.marzban_service import MarzbanService
from utils.helpers import is_subscription_active

router = Router()
marzban_service = MarzbanService(MARZBAN_BASE_URL, MARZBAN_USERNAME, MARZBAN_PASSWORD)


@router.message(CommandStart())
async def start_handler(message: Message):
    """Обработчик команды /start"""
    # Определим активность для персонализации CTA
    try:
        user_info = await marzban_service.get_user_info(message.from_user.id)
        is_active = is_subscription_active(user_info)
    except Exception:
        is_active = False
    await message.answer(
        text=MESSAGES["welcome"],
        reply_markup=get_main_menu(has_active=is_active)
    )


@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    # Определим активность для персонализации CTA
    try:
        user_info = await marzban_service.get_user_info(callback.from_user.id)
        is_active = is_subscription_active(user_info)
    except Exception:
        is_active = False
    await callback.message.edit_text(
        text=MESSAGES["welcome"],
        reply_markup=get_main_menu(has_active=is_active)
    )
    await callback.answer()


