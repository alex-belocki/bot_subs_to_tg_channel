from telegram.ext import filters

from .callbacks.callbacks import *
from .callbacks.subscriptions import *
from core.handlers.base import (
    BaseHandler,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler
)


class UserHandler(BaseHandler):
    def __init__(self, session, close_conv_buttons=None) -> None:
        super().__init__(session)
        self.close_conv_buttons = close_conv_buttons

    async def handle(self):
        yield CommandHandler('start', start, order=1)

        yield CallbackQueryHandler(
            buy_subscription_stub,
            pattern=await self.pattern('btn-buy-subscription'),
        )
        yield CallbackQueryHandler(
            pay_robokassa,
            pattern=await self.pattern("btn-pay-robokassa"),
        )
        yield CallbackQueryHandler(
            pay_ton,
            pattern=await self.pattern("btn-pay-ton"),
        )
        yield CallbackQueryHandler(
            my_subscription,
            pattern=await self.pattern('btn-my-subscription'),
        )
        yield CallbackQueryHandler(
            support,
            pattern=await self.pattern('btn-support'),
        )
        yield CallbackQueryHandler(
            get_invite,
            pattern=await self.pattern('btn-get-invite'),
        )
        yield CallbackQueryHandler(
            show_privacy,
            pattern=await self.pattern('btn-privacy'),
        )
        yield CallbackQueryHandler(
            show_offer,
            pattern=await self.pattern('btn-offer'),
        )
        yield CallbackQueryHandler(
            back_to_main,
            pattern=await self.pattern('btn-back'),
        )

        yield CallbackQueryHandler(delete_message,
                                   pattern=await self.pattern('btn-close'))

