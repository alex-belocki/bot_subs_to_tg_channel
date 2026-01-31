from telegram.ext import filters

from .callbacks import *
from core.handlers.base import (
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler
)


class CommonHandler(BaseHandler):
    def __init__(self, session, close_conv_buttons=None) -> None:
        super().__init__(session)
        self.close_conv_buttons = close_conv_buttons

    async def handle(self):
        pass
        # yield MessageHandler(
        #     filters.Regex(await self.pattern('btn-testimonials')),
        #     show_testimonials
        # )
