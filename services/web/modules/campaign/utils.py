import logging

import nats
from nats.js.api import StreamConfig
from sqlalchemy import and_

from core.database.database import db
from common.events import SendCampaignEvent
from common.models.interface_models import Button, Menu


logger = logging.getLogger(__name__)


def get_menus_without_variable_buttons():
    """Отбираем меню без переменных"""
    subquery = (
        db.session.query(Menu.id)
        .join(Menu.buttons_list)
        .filter(
            and_(
                Button.callback_data.contains('{'),
                Button.callback_data.contains('}')
            )
        )
        .subquery()
    )

    # Main query to find menus without buttons containing variables
    query = (
        db.session.query(Menu)
        .filter(~Menu.id.in_(subquery))
    )

    return query.all()


async def publish_send_campaign_event(event: SendCampaignEvent):
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

        # Публикуем событие
        payload = event.model_dump_json().encode()
        await js.publish("campaign.send", payload)

        await nc.close()
    except Exception as e:
        logger.error(f"Ошибка при публикации события: {e}")
        raise
