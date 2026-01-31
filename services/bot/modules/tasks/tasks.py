import asyncio

from modules.tasks.broker import broker
import logging

import datetime as dt
from telegram import Bot
from telegram.error import TelegramError

from core.constants.config import CHANNEL_ID, TOKEN
from core.database.uow import SqlAlchemyUoW

logger = logging.getLogger(__name__)


@broker.task()
async def simple_task():
    logger.info('Simple task 1 is running')
    await asyncio.sleep(15)
    logger.info('Simple task 1 is done')


@broker.task(schedule=[{"cron": "*/1 * * * *", "args": [1]}])
async def heavy_task(value: int) -> int:
    result = value + 1
    logger.info(f"Heavy task result: {result}")
    return result


@broker.task(schedule=[{"cron": "*/10 * * * *"}])
async def subscriptions_expire_and_kick() -> None:
    """
    Периодическая задача:
    - ищет активные подписки с end_at < now()
    - пытается удалить пользователя из канала
    - помечает подписку expired
    """
    if not TOKEN:
        logger.warning("TOKEN is not set, skipping subscriptions_expire_and_kick")
        return
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID is not set, skipping subscriptions_expire_and_kick")
        return

    bot = Bot(token=TOKEN)
    now = dt.datetime.now(dt.timezone.utc)

    async with SqlAlchemyUoW() as uow:
        subs = await uow.subscription_repo.get_expired_active(now=now)
        if not subs:
            return

        for sub in subs:
            chat_id = sub.channel_id or CHANNEL_ID
            try:
                await bot.ban_chat_member(chat_id=chat_id, user_id=sub.user_id)
                await bot.unban_chat_member(chat_id=chat_id, user_id=sub.user_id)
            except TelegramError as exc:
                # Если пользователь уже не в канале — считаем успехом.
                msg = str(exc).lower()
                if "not a member" not in msg and "user not found" not in msg:
                    logger.exception(
                        "Failed to kick user_id=%s from chat_id=%s: %s",
                        sub.user_id,
                        chat_id,
                        exc,
                    )

            sub.status = "expired"

        await uow.commit()
