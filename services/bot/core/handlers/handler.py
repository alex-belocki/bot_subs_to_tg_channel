from telegram.ext import filters

from .base import (
    BaseMainHandler,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler
)
from core.constants.enums import Mode, ScreenName
import modules.users.callbacks.callbacks as user_cb
import modules.users.callbacks.cancel as cancel
from modules.common.handlers import CommonHandler
from modules.users.handlers import UserHandler
from modules.admin.handlers import AdminHandler


class Handler(BaseMainHandler):
    """
    Класс компоновщик
    """

    async def close_conv_buttons(self):
        return [
            MessageHandler(filters.Regex(await self.pattern('btn-cancel')), cancel.cancel)
        ]

    # async def get_payment_url_conv(self):
    #     slug_list = ['btn-tariffs', 'btn-subs', 'btn-feedback']
    #     pattern = await self.buttons_pattern(slug_list)
    #     return ConversationHandler(
    #         entry_points=[
    #             CallbackQueryHandler(send_fio, pattern=await self.pattern('btn-pay'))

    #             ],

    #         states={
    #             '1': self.close_conv_buttons + [
    #                 MessageHandler(filters.TEXT & ~filters.Regex(pattern), get_email)
    #             ]
    #         },
    #         fallbacks=[
    #             MessageHandler(
    #                 filters.Regex(await self.pattern('btn-tariffs')),
    #                 select_tariff
    #             ),

    #             MessageHandler(
    #                 filters.Regex(await self.pattern('btn-subs')),
    #                 show_subscription
    #             ),

    #             MessageHandler(
    #                 filters.Regex(await self.pattern('btn-feedback')),
    #                 show_feedback
    #             )

    #         ],
    #         allow_reentry=True
    #         )

    async def handlers(self):
        yield MessageHandler(filters.Regex('^/get_id$'), user_cb.get_my_id, order=2)



    async def handle(self):
        self.add_module_handler(UserHandler)
        self.add_module_handler(AdminHandler)
        # self.add_module_handler(CommonHandler)

        async for handler in super().handle():
            yield handler
