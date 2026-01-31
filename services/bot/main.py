import asyncio
import logging
import os
import pytz
import sys

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, Defaults, filters

from modules.common.error_handler import error_handler
from modules.nats_listener import nats_listener
from core.constants.config import DEV_MODE, TG_ADMIN_LIST
from core.database.database import async_session_maker
from core.handlers.handler import Handler
from core.interface.services import BotInterfaceService


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO
    )

aps_logger = logging.getLogger('apscheduler')
aps_logger.setLevel(logging.WARNING)

logging.getLogger("httpx").setLevel(logging.WARNING)


async def get_handlers():
    async with async_session_maker() as session:
        handler = Handler(session)

        handlers = handler.handle()
        handlers = [item async for item in handlers]
        return sorted(handlers, key=lambda x: x.order)


async def get_token():
    async with async_session_maker() as session:
        token = await BotInterfaceService(session).get_token()
        return token


async def restart(update: Update, context) -> None:
    context.bot_data["restart"] = True
    await update.message.reply_text("Bot is restarting...")
    await context.application.stop()


async def main():
    asyncio.create_task(nats_listener())

    defaults = Defaults(
        tzinfo=pytz.timezone('Europe/Moscow'),
        parse_mode=ParseMode.HTML
        )

    token = await get_token()

    app = (
        Application.builder()
        .token(token)
        .concurrent_updates(True)
        .defaults(defaults)
        .build()
    )

    await asyncio.sleep(5)

    app.bot_data['restart'] = False
    app.add_handler(CommandHandler('r', restart, filters=filters.User(TG_ADMIN_LIST)))

    handlers = await get_handlers()
    for handler in handlers:
        app.add_handler(handler, group=handler.group)

    app.add_error_handler(error_handler)

    async with app:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)

        try:
            while True:
                await asyncio.sleep(0.01)
                if app.bot_data["restart"]:
                    os.execl(sys.executable, sys.executable, *sys.argv)

        except Exception:
            await app.updater.stop()
            await app.stop()


if __name__ == '__main__':
    asyncio.run(main())
