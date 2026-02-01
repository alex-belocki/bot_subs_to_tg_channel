import logging

import nats
from nats.js.api import StreamConfig

from common.events import PaymentSucceededEvent

logger = logging.getLogger(__name__)


async def publish_payment_succeeded_event(event: PaymentSucceededEvent) -> None:
    nc = await nats.connect("nats://nats:4222")
    js = nc.jetstream()

    stream_config = StreamConfig(
        name="payments",
        subjects=["payment.succeeded"],
        retention="workqueue",
        max_msgs=100000,
    )
    try:
        await js.add_stream(config=stream_config)
    except nats.js.errors.APIError as exc:
        if "stream name already in use" not in str(exc):
            raise

    payload = event.model_dump_json().encode("utf-8")
    await js.publish("payment.succeeded", payload)
    await nc.close()

