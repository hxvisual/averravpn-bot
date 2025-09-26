import logging
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from handlers.payment import process_payment_notification
from config import BOT_TOKEN

logger = logging.getLogger(__name__)


def create_app(bot: Bot | None = None) -> FastAPI:
    app = FastAPI(title="Averra VPN Webhooks")

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.on_event("startup")
    async def on_startup() -> None:
        nonlocal bot
        if bot is None:
            bot = Bot(
                token=BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.HTML)
            )
            app.state.owns_bot = True
        else:
            app.state.owns_bot = False
        app.state.bot = bot

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        # Close only if app created its own bot
        b: Bot | None = getattr(app.state, "bot", None)
        owns: bool = getattr(app.state, "owns_bot", False)
        if b is not None and owns:
            await b.session.close()

    @app.post("/yoomoney")
    async def yoomoney_webhook(request: Request):
        # Prefer parsing application/x-www-form-urlencoded to avoid python-multipart dependency
        data = {}
        content_type = request.headers.get("content-type", "")
        try:
            if "application/x-www-form-urlencoded" in content_type:
                from urllib.parse import parse_qs
                raw = (await request.body()).decode("utf-8", errors="ignore")
                parsed = parse_qs(raw, keep_blank_values=True)
                data = {k: v[0] for k, v in parsed.items()}
            else:
                # Fallback to starlette's form parser (requires python-multipart for multipart)
                form = await request.form()
                data = dict(form)
        except Exception as parse_err:
            logger.error("YooMoney webhook parse error: %s", parse_err)
            return PlainTextResponse("ERR", status_code=200)

        logger.info("YooMoney webhook received: %s", {k: v for k, v in data.items() if k != 'sha1_hash'})

        b: Bot | None = getattr(app.state, "bot", None)
        processed = await process_payment_notification(data, bot=b)
        if processed:
            return PlainTextResponse("OK", status_code=200)
        return PlainTextResponse("ERR", status_code=200)

    return app


# Backward compatibility when running uvicorn webhook:app
app = create_app()


