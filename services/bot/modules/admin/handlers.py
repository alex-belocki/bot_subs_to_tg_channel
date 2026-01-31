from telegram.ext import filters

from core.constants.config import TG_ADMIN_LIST
from core.handlers.base import BaseHandler, CommandHandler

from .callbacks import admin_add, admin_extend, admin_remove, admin_stats, admin_users


class AdminHandler(BaseHandler):
    def __init__(self, session, close_conv_buttons=None) -> None:
        super().__init__(session)
        self.close_conv_buttons = close_conv_buttons

    async def handle(self):
        admin_filter = filters.User(TG_ADMIN_LIST)

        yield CommandHandler("users", admin_users, filters=admin_filter, order=1)
        yield CommandHandler("add", admin_add, filters=admin_filter, order=1)
        yield CommandHandler("extend", admin_extend, filters=admin_filter, order=1)
        yield CommandHandler("remove", admin_remove, filters=admin_filter, order=1)
        yield CommandHandler("stats", admin_stats, filters=admin_filter, order=1)

