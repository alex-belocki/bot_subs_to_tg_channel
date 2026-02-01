import logging
import json
import datetime as dt

from pydantic import ValidationError
from sqlalchemy import update
from telegram import Bot

from common.events import PaymentSucceededEvent, SendCampaignEvent
from common.models.payments_models import Payment
from core.constants.config import CHANNEL_ID, TOKEN
from core.database.uow import SqlAlchemyUoW
from modules.subscriptions.services import SubscriptionService
import asyncio
import nats
from nats.js.api import StreamConfig
from nats.aio.msg import Msg

from modules.tasks.tasks import simple_task
from modules.tasks.broker import broker_context


logger = logging.getLogger(__name__)


async def _ensure_stream(
    js,
    *,
    name: str,
    subjects: list[str],
    max_msgs: int,
) -> None:
    stream_config = StreamConfig(
        name=name,
        subjects=subjects,
        retention="workqueue",
        max_msgs=max_msgs,
    )
    try:
        await js.add_stream(config=stream_config)
    except nats.js.errors.APIError as exc:
        if "stream name already in use" not in str(exc):
            raise


async def handle_event(msg: Msg):
    try:
        data = json.loads(msg.data.decode())
        logger.info("Получено событие: subject=%s payload=%s", msg.subject, data)

        if msg.subject == "campaign.send":
            await msg.ack()  # Подтверждаем получение сообщения
            async with broker_context():
                await simple_task.kiq()
            return

        if msg.subject == "payment.succeeded":
            event = PaymentSucceededEvent.model_validate(data)

            if not TOKEN:
                logger.error("TOKEN is not set, cannot notify user about payment")
                await msg.nak()
                return
            if not CHANNEL_ID:
                logger.error("CHANNEL_ID is not set, cannot grant subscription")
                await msg.nak()
                return

            async with SqlAlchemyUoW() as uow:
                now = dt.datetime.now(dt.timezone.utc)
                res = await uow.session.execute(
                    update(Payment)
                    .where(Payment.id == event.payment_id)
                    .where(Payment.processed_at.is_(None))
                    .values(processed_at=now)
                )
                if res.rowcount == 0:
                    # Уже обработано ранее.
                    await uow.commit()
                    await msg.ack()
                    return

                ss = SubscriptionService(uow)
                await ss.grant_90d(
                    user_id=event.user_id,
                    channel_id=CHANNEL_ID,
                    start_at=event.paid_at,
                )
                # Коммит нужен, чтобы подписка была консистентна для дальнейших действий.
                await uow.commit()

                bot = Bot(token=TOKEN)
                invite_link, expire_at, _ = await ss.create_invite_link(
                    bot=bot,
                    user_id=event.user_id,
                    channel_id=CHANNEL_ID,
                )
                await uow.commit()

                sub = await ss.get_active(user_id=event.user_id, channel_id=CHANNEL_ID)
                end_at_str = "—"
                if sub:
                    end_at_str = sub.end_at.astimezone(dt.timezone.utc).strftime(
                        "%Y-%m-%d %H:%M UTC"
                    )

                text = (
                    "Оплата успешна.\n"
                    f"Подписка активирована до: {end_at_str}\n\n"
                    f"Инвайт-ссылка (действует до {expire_at.strftime('%Y-%m-%d %H:%M UTC')}):\n"
                    f"{invite_link}"
                )
                await bot.send_message(chat_id=event.user_id, text=text)

            await msg.ack()
            return

        # Неизвестные события не должны ломать consumer.
        await msg.ack()

    except ValidationError as e:
        logger.error(f"Ошибка валидации события: {e}")
        await msg.ack()
    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await msg.nak()


async def nats_listener():
    try:
        nc = await nats.connect("nats://nats:4222")
        js = nc.jetstream()

        # Создаем стримы, если они еще не существуют
        await _ensure_stream(
            js, name="campaigns", subjects=["campaign.send"], max_msgs=10000
        )
        await _ensure_stream(
            js, name="payments", subjects=["payment.succeeded"], max_msgs=100000
        )

        # Подписываемся на сообщения
        await js.subscribe(
            "campaign.send",
            durable="campaign_processor",
            cb=handle_event,
            manual_ack=True
        )
        await js.subscribe(
            "payment.succeeded",
            durable="payment_processor",
            cb=handle_event,
            manual_ack=True,
        )

        # Держим соединение открытым
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Ошибка в NATS listener: {e}")
        raise
