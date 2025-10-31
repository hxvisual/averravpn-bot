import asyncio
import contextlib
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN, WEBHOOK_HOST, WEBHOOK_PORT
from utils.reminder import run_expiry_reminders
from utils.maintenance import MaintenanceMiddleware
from handlers import start, subscription, payment
from webhook import create_app
import uvicorn

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_bot(bot: Bot) -> None:
    dp = Dispatcher()
    # Global middleware blocks non-admins when maintenance is enabled
    dp.update.outer_middleware(MaintenanceMiddleware())
    dp.include_router(start.router)
    dp.include_router(subscription.router)
    dp.include_router(payment.router)

    logger.info("Starting Averra VPN Bot...")
    await dp.start_polling(bot)


async def run_webhook(bot: Bot) -> None:
    app = create_app(bot)
    config = uvicorn.Config(app=app, host=WEBHOOK_HOST, port=WEBHOOK_PORT, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    bot_task = asyncio.create_task(run_bot(bot))
    webhook_task = asyncio.create_task(run_webhook(bot))

    async def _reminder_loop() -> None:
        # Run immediately on start, then periodically
        try:
            await run_expiry_reminders(bot)
        except Exception as e:
            logger.error("Reminder run failed: %s", e)
        while True:
            try:
                await asyncio.sleep(6 * 60 * 60)  # 6 * 60 * 60 every 6 hours
                await run_expiry_reminders(bot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Reminder run failed: %s", e)

    reminders_task = asyncio.create_task(_reminder_loop())

    # Wait until any of tasks finishes (e.g., Ctrl+C)
    try:
        await asyncio.wait([bot_task, webhook_task], return_when=asyncio.FIRST_COMPLETED)
    finally:
        reminders_task.cancel()
        with contextlib.suppress(Exception):
            await reminders_task
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())


