import logging
import json
from pydantic import ValidationError
from common.events import SendCampaignEvent
import asyncio
import nats
from nats.js.api import StreamConfig
from nats.aio.msg import Msg

from modules.tasks.tasks import simple_task
from modules.tasks.broker import broker_context


logger = logging.getLogger(__name__)


async def handle_event(msg: Msg):
    try:
        data = json.loads(msg.data.decode())
        logger.info(f"Получено событие рассылки: {data}")

        if msg.subject == "campaign.send":
            await msg.ack()  # Подтверждаем получение сообщения
            async with broker_context():
                await simple_task.kiq()


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

        # Создаем стрим, если он еще не существует
        stream_config = StreamConfig(
            name="campaigns",
            subjects=["campaign.send"],
            retention="workqueue",
            max_msgs=10000
        )

        try:
            # Пробуем создать стрим
            await js.add_stream(config=stream_config)
        except nats.js.errors.APIError as e:
            # Игнорируем ошибку, если стрим уже существует
            if not "stream name already in use" in str(e):
                raise

        # Подписываемся на сообщения
        sub = await js.subscribe(
            "campaign.send",
            durable="campaign_processor",
            cb=handle_event,
            manual_ack=True
        )

        # Держим соединение открытым
        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"Ошибка в NATS listener: {e}")
        raise
