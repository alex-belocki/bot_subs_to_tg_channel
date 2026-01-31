import logging

from taskiq.schedule_sources import LabelScheduleSource
from taskiq import TaskiqScheduler

from modules.tasks.broker import broker
# from modules.tasks.tasks import *


logger = logging.getLogger(__name__)


scheduler = TaskiqScheduler(
    broker=broker,
    sources=[LabelScheduleSource(broker)],
)
