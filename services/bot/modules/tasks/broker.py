from contextlib import asynccontextmanager
from nats.js.api import RetentionPolicy, StreamConfig
from taskiq_nats import PullBasedJetStreamBroker
from taskiq_nats.result_backend import NATSObjectStoreResultBackend


result_backend = NATSObjectStoreResultBackend(servers="nats://nats:4222")

stream_config = StreamConfig(
    retention=RetentionPolicy.WORK_QUEUE,
)

broker = PullBasedJetStreamBroker(
    servers="nats://nats:4222",
    queue="taskiq_queue",
    stream_config=stream_config,
).with_result_backend(result_backend=result_backend)


@asynccontextmanager
async def broker_context():
    await broker.startup()
    try:
        yield
    finally:
        await broker.shutdown()
