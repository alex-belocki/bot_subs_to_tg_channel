import logging

from telegram import Update
from telegram.ext import ContextTypes

from core.message_manager import MessageManager

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s',
    level=logging.INFO
    )
logger = logging.getLogger(__name__)

